import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from folium.plugins import HeatMap  # <-- Dodat plugin za toplotnu mapu
from datetime import datetime
from etl.db_utils import get_db_connection

def get_fires_from_db():
    conn = get_db_connection()
    try:
        query = "SELECT acq_date, acq_time, latitude, longitude, frp, confidence, satellite FROM pozari_firms ORDER BY acq_date DESC, acq_time DESC;"
        df = pd.read_sql(query, conn)
        if not df.empty:
            df["acq_date"] = pd.to_datetime(df["acq_date"]).dt.date
        return df, None
    except Exception as e:
        return pd.DataFrame(), str(e)

def get_air_quality_from_db():
    conn = get_db_connection()
    try:
        query = """
            SELECT DISTINCT ON (region)
                region, forecast_time, pm2_5, pm10, nitrogen_dioxide,
                ozone, sulphur_dioxide, carbon_monoxide, dust, uv_index,
                european_aqi, aqi_category
            FROM air_quality_forecast
            ORDER BY region, forecast_time DESC;
        """
        df = pd.read_sql(query, conn)
        return df, None
    except Exception as e:
        return pd.DataFrame(), str(e)

def render():
    st.title("🔥 Aktivni požari - FIRMS Satelitski Nadzor")
    st.caption(f"Podatki so sinhronizirani preko Neon baze | NASA FIRMS VIIRS C2 | Osveženo: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    
    with st.spinner("Nalagam požarne podatke iz baze..."):
        df, err = get_fires_from_db()
        
    if err:
        st.error(f"Napaka pri branju iz baze: {err}")
        return
        
    # --- METRIKE ---
    c1, c2, c3 = st.columns(3)
    c1.metric("Zaznani požari (SLO okolica)", len(df))
    
    if not df.empty:
        c2.metric("Max FRP (Moč požara)", f"{df['frp'].max():.1f} MW")
        c3.metric("Zadnji zaznani", str(df["acq_date"].max()))
        
    st.markdown("---")
    
    # --- STATUSNA PORUKA ---
    st.subheader("Karta požarnih žarišč (Heatmap)")
    if not df.empty:
        st.info(f"📊 Toplotna karta prikazuje koncentracijo {len(df)} satelitskih zaznav. Močnejša rdeča barva označuje večjo intenzivnost termalnih anomalij.")
    else:
        st.success("✅ Ni aktivnih požarov v SLO območju (zadnjih 7 dni)")

    # --- TOPLOTNA KARTA POŽARA ---
    # Koristimo "CartoDB positron" podlogu jer je siva i minimalistička, pa se crveni toplotni oblaci savršeno vide
    m = folium.Map(location=[46.1, 14.8], zoom_start=7, tiles="CartoDB positron")
    
    if not df.empty:
        # Pripremamo podatke za toplotnu mapu: lista formata [latitude, longitude, intenzitet]
        # Kao intenzitet (težinu) koristimo 'frp' (Fire Radiative Power - snagu požara u megavatima)
        heat_data = [[row['latitude'], row['longitude'], row['frp']] for _, row in df.iterrows()]
        
        # Dodajemo toplotni sloj na mapu
        # radius kontroliše veličinu mrlje, blur zamućenje ivica, a max_zoom kada mapa prestaje da spaja tačke
        HeatMap(heat_data, radius=18, blur=12, max_zoom=9).add_to(m)
        
        # Pored toplotne mape, dodaćemo diskretne prozirne tačkice na koje vatrogasci mogu da kliknu i vide detalje
        for _, row in df.iterrows():
            popup_text = (f"<b>🔥 Detajli očitavanja</b><br>"
                          f"<b>Datum:</b> {row.get('acq_date','?')}<br>"
                          f"<b>Ura:</b> {row.get('acq_time','?')} UTC<br>"
                          f"<b>Moč (FRP):</b> {row.get('frp','?')} MW<br>"
                          f"<b>Zaupanje:</b> {row.get('confidence','?')}")
            
            folium.CircleMarker(
                location=[row["latitude"], row["longitude"]],
                radius=4, color="red", fill=True, fill_opacity=0.2,
                popup=folium.Popup(popup_text, max_width=200),
                tooltip=f"Moč: {row.get('frp','?')} MW"
            ).add_to(m)
            
    else:
        # Ako nema požara, stavljamo zeleni marker koji potvrđuje stabilno stanje
        folium.Marker([46.1, 14.8], popup="Slovenija je varna",
                      icon=folium.Icon(color="green", icon="check")).add_to(m)
                      
    st_folium(m, width="100%", height=500, returned_objects=[])
    
    # --- TABELA ---
    if not df.empty:
        st.markdown("---")
        st.subheader("Tabela aktivnih lokacij")
        cols = [c for c in ["acq_date", "acq_time", "latitude", "longitude", "frp", "confidence", "satellite"] if c in df.columns]
        
        df_prikaz = df[cols].copy()
        df_prikaz.columns = ["Datum", "Ura (UTC)", "Latitude", "Longitude", "FRP (MW)", "Zaupanje", "Satelit"]
        
        st.dataframe(df_prikaz, use_container_width=True)
        # --- AIR QUALITY SECTION ---
    st.markdown("---")
    st.subheader("🌫️ Kakovost zraka — Regionalna prognoza")
    st.caption("Vir: Open-Meteo Air Quality API | Evropski AQI indeks")

    with st.spinner("Nalagam podatke o kakovosti zraka..."):
        df_aq, err_aq = get_air_quality_from_db()

    if err_aq:
        st.error(f"Napaka pri branju kakovosti zraka: {err_aq}")
    elif df_aq.empty:
        st.info("Ni podatkov o kakovosti zraka.")
    else:
        # AQI boja po kategoriji
        def aqi_color(cat):
            return {
                "Good": "🟢", "Fair": "🟡", "Moderate": "🟠",
                "Poor": "🔴", "Very Poor": "🟣", "Extremely Poor": "⚫"
            }.get(cat, "⚪")

        # Metrike za prvih 4 regiona
        top_regions = df_aq.head(4)
        cols = st.columns(len(top_regions))
        for i, (_, row) in enumerate(top_regions.iterrows()):
            with cols[i]:
                ikona = aqi_color(row.get('aqi_category', ''))
                st.markdown(f"""
                <div style='background:#f9f8f5; border:1px solid rgba(0,0,0,0.08);
                            border-radius:12px; padding:12px 8px; text-align:center;'>
                    <div style='font-weight:600; color:#555; font-size:11px'>{row['region']}</div>
                    <div style='font-size:28px; margin:4px 0'>{ikona}</div>
                    <div style='font-weight:700; font-size:18px'>{row['european_aqi']:.0f} AQI</div>
                    <div style='font-size:11px; color:#888; margin-top:2px'>{row.get('aqi_category','?')}</div>
                    <div style='margin-top:6px; font-size:11px; color:#555'>
                        PM2.5: <b>{row['pm2_5']:.1f}</b> · PM10: <b>{row['pm10']:.1f}</b>
                    </div>
                    <div style='font-size:11px; color:#3a7abf'>
                        NO₂: {row['nitrogen_dioxide']:.1f} · O₃: {row['ozone']:.1f}
                    </div>
                    <span></span>
                </div>
                """, unsafe_allow_html=True)

        # Detaljna tabela
        st.markdown("#### Podrobna tabela")
        prikaz = df_aq[[
            "region", "european_aqi", "aqi_category", "pm2_5", "pm10",
            "nitrogen_dioxide", "ozone", "sulphur_dioxide", "carbon_monoxide",
            "dust", "uv_index", "forecast_time"
        ]].copy()
        prikaz.columns = [
            "Regija", "EU AQI", "Kategorija", "PM2.5", "PM10",
            "NO₂", "O₃", "SO₂", "CO", "Prah", "UV indeks", "Čas napovedi"
        ]
        st.dataframe(prikaz, use_container_width=True)