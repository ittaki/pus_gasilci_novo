import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from datetime import datetime
from etl.db_utils import get_db_connection


def get_earthquakes_from_db(days):
    """Povlači potrese iz Neon baze filtrirane prema broju dana koji je korisnik izabrao."""
    try:
        conn = get_db_connection()
        query = f"""
            SELECT cas, mag, globina_km, lokacija, lat, lon 
            FROM potresi_gasilci 
            WHERE cas >= NOW() - INTERVAL '{days} days'
            ORDER BY cas DESC;
        """
        df = pd.read_sql(query, conn)
        if not df.empty:
            df["cas"] = pd.to_datetime(df["cas"])
        conn.close()
        return df, None
    except Exception as e:
        return pd.DataFrame(), str(e)


def mag_color(mag):
    try:
        m = float(mag)
    except:
        return "gray"
    if m >= 4.0:
        return "red"
    elif m >= 2.5:
        return "orange"
    else:
        return "green"


def render():
    st.title("🌋 Potresi - Operativni Seizmički Monitor")
    st.caption(f"Podaci se sinhronizuju uživo preko Neon Cloud baze | Osveženo: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    

    days = st.slider("Obdobje prikaza (v dneh)", 7, 90, 30, 7)
    
    with st.spinner("Učitavam seizmičke podatke iz baze..."):
        df, err = get_earthquakes_from_db(days)
        
    if err:
        st.error(f"Napaka pri branju iz baze: {err}")
        return
    if df.empty:
        st.info("Ni zabeleženih potresov v tem obdobju.")
        return
        
    # --- METRIKE NA VRHU ---
    c1, c2, c3 = st.columns(3)
    c1.metric(f"Potresi v zadnjih {days} dneh", len(df))
    c2.metric("Nevarnost (Mag >= 2.0)", len(df[df["mag"] >= 2.0]))
    
    # Zadnji potres iz baze
    najnoviji = df.iloc[0]
    zadnji_cas = najnoviji["cas"].strftime('%d.%m.%Y ob %H:%M')
    c3.metric("Zadnji potres", zadnji_cas)
    
    # Pametni alarmni sistem za vatrogasce na osnovu poslednjeg potresa
    if najnoviji['mag'] >= 4.0:
        st.error(f"🚨 **KRITIČNO STANJE:** Zabeležen močan potres M{najnoviji['mag']} ({najnoviji['lokacija']})! Pokrenuti protokole provere infrastrukture.")
    elif najnoviji['mag'] >= 2.5:
        st.warning(f"⚠️ **POVEČANA PRIPRAVLJENOST:** Zmeren potres M{najnoviji['mag']} ({najnoviji['lokacija']}). Stanovništvo je osetilo potres.")
    else:
        st.success(f"✅ **Mirno stanje:** Zadnji potres je bil šibek M{najnoviji['mag']} ({najnoviji['lokacija']}) i ne predstavlja opasnost.")
        
    st.markdown("---")
    
    # --- RASPORED: MAPA LEVO, GRAFIKON DESNO ---
    col_map, col_chart = st.columns([3, 2])
    
    with col_map:
        st.subheader("🗺️ Interaktivna karta potresov")
        # Centriramo mapu na Sloveniju
        m = folium.Map(location=[46.1, 14.8], zoom_start=7, tiles="CartoDB positron")
        
        for _, row in df.iterrows():
            if pd.isna(row["lat"]) or pd.isna(row["lon"]): 
                continue
            color = mag_color(row["mag"])
            radius = max(5, float(row["mag"] or 1) * 3)
            popup = (f"<b>Mag:</b> {row['mag']}<br>"
                     f"<b>Čas:</b> {row['cas'].strftime('%d.%m %H:%M')}<br>"
                     f"<b>Globina:</b> {row['globina_km']} km<br>"
                     f"<b>Lokacija:</b> {row['lokacija']}")
            
            folium.CircleMarker(
                location=[row["lat"], row["lon"]],
                radius=radius, color=color, fill=True, fill_opacity=0.7,
                popup=folium.Popup(popup, max_width=250),
                tooltip=f"M{row['mag']} - {row['lokacija']}"
            ).add_to(m)
            
        st_folium(m, width="100%", height=450, returned_objects=[])
        
    with col_chart:
        st.subheader("📈 Trend magnitud skozi čas")
        chart_data = df[["cas", "mag"]].dropna().set_index("cas").sort_index()
        st.line_chart(chart_data, height=430)
        
    st.markdown("---")
    
    # --- TABELA NA DNU ---
    st.subheader("📋 Seznam potresov iz baze")
    
    df_prikaz = df.copy()
    df_prikaz["cas"] = df_prikaz["cas"].dt.strftime('%d.%m.%Y %H:%M')
    df_prikaz.columns = ["Čas (UTC)", "Magnituda (M)", "Globina (km)", "Lokacija / Regija", "Latitude", "Longitude"]
    
    st.dataframe(df_prikaz.head(50), width='stretch')