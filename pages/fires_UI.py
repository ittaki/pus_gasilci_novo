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