import streamlit as st
import psycopg2
import pandas as pd
import folium
import time
import streamlit.components.v1 as components
from etl.db_utils import get_db_connection


REGIONS = {
    "Ljubljana": {"lat": 46.0569, "lon": 14.5058},
    "Maribor": {"lat": 46.5547, "lon": 15.6459},
    "Celje": {"lat": 46.2397, "lon": 15.2677},
    "Kranj": {"lat": 46.2389, "lon": 14.3556},
    "Koper": {"lat": 45.5481, "lon": 13.7302},
    "Novo Mesto": {"lat": 45.8030, "lon": 15.1689},
    "Murska Sobota": {"lat": 46.6625, "lon": 16.1664},
    "Nova Gorica": {"lat": 45.9560, "lon": 13.6484},
}

def load_data_from_db(region_name):
    """Povezivanje na PostgreSQL i čitanje podataka o vodostajima"""
    try:
        conn = get_db_connection()
        query = "SELECT * FROM floods_data WHERE region = %s"
        df = pd.read_sql_query(query, conn, params=(region_name,))
        conn.close()
        return df
    except Exception as e:
        st.error(f"Greška pri povezivanju sa PostgreSQL bazom (floods): {e}")
        return pd.DataFrame()

def load_cameras_from_db(region_name):
    """NOVO: Čitanje lokacija operativnih kamera direktno iz baze podataka"""
    try:
        conn = get_db_connection()
        query = "SELECT name, lat, lon, type, url FROM kamere_lokacije WHERE region = %s"
        df = pd.read_sql_query(query, conn, params=(region_name,))
        conn.close()
        # Pretvaramo u listu rečnika da bi ostatak Ajnine logike za mapu radio bez izmena
        return df.to_dict(orient="records")
    except Exception as e:
        st.error(f"Greška pri čitanju kamera iz baze: {e}")
        return []

def render():
    st.markdown("## 🌊 Spremljanje poplav in rečnih tokov (ARSO)")
    st.caption("Operativni hidrološki in vremenski podatki osveženi iz Neon Cloud baze.")
    
    # Selektor regiona
    selected_region = st.selectbox("Izberite operativno območje:", list(REGIONS.keys()))
    df = load_data_from_db(selected_region)
    
    if df.empty:
        st.warning(f"Trenutno ni podatkov v bazi za regijo {selected_region}. Zaženite pozadinskega delavca.")
        return
        
    # Izvlačenje meteo metrika
    sample_row = df.iloc[0]
    temp = sample_row['temp']
    rain_now = sample_row['rain_now']
    rain_24h = sample_row['rain_24h']
    wind = sample_row['wind']
    
    # --- METRIC PANEL ---
    st.markdown("### 🌤️ Trenutne vremenske razmere v regiji")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Temperatura", f"{temp} °C")
    m2.metric("Padavine trenutno", f"{rain_now} mm")
    m3.metric("Skupne padavine (24h)", f"{rain_24h} mm")
    m4.metric("Hitrost vetra", f"{wind} m/s")
    
    # --- RISK ASSESSMENT ---
    st.markdown("### 🚨 Ocena nevarnosti poplav")
    if rain_now > 10 or rain_24h > 60:
        st.error("⚠️ CRVENI ALARM: Visoka nevarnost poplav glede na intenzivnost padavin!")
    elif rain_now > 4 or rain_24h > 25:
        st.warning("⚡ RUMENI ALARM: Povečana nevarnost razlivanja vodotokov.")
    else:
        st.success("✅ Stanje je stabilno. Nevarnost poplav je trenutno nizka.")
        
    # --- RASPORED: LEVO MAPA SA KAMERAMA, DESNO VODOSTAJI ---
    col_left, col_right = st.columns([3, 2])
    
    with col_left:
        st.markdown("### 📹 Operativne kamere in kritični koridorji")
        
        reg_center = REGIONS[selected_region]
        m = folium.Map(location=[reg_center["lat"], reg_center["lon"]], zoom_start=10)
        
        # Marker za centar regiona
        folium.Marker([reg_center["lat"], reg_center["lon"]], tooltip=selected_region, icon=folium.Icon(color="blue")).add_to(m)
        
        # POPRAVLJENO: Povlačenje kamera iz baze umesto iz hardkodovanog rečnika
        cams = load_cameras_from_db(selected_region)
        refresh_token = int(time.time())
        
        for c in cams:
            img_url = f"{c['url']}?refresh={refresh_token}"
            popup_html = f"""
            <div style='width:250px'>
                <b>{c['name']}</b><br><small>{c['type']}</small><br><br>
                <img src='{img_url}' width='230' style='border-radius:4px;'><br><br>
                <a href='{c['url']}' target='_blank'>Odpri sliko v polni velikosti</a>
            </div>
            """
            folium.Marker(
                [c["lat"], c["lon"]],
                popup=folium.Popup(popup_html, max_width=300),
                tooltip=c["name"],
                icon=folium.Icon(color="red", icon="camera")
            ).add_to(m)
            
        html_string = m._repr_html_()
        components.html(html_string, height=450, scrolling=True)
        
    with col_right:
        st.markdown("### 🌊 Stanje rečnih strug (ARSO)")
        
        df_rivers = df[df['river'].notna()]
        
        if df_rivers.empty:
            st.info("Na tem območju ni registriranih ARSO hidroloških postaj.")
        else:
            for _, row in df_rivers.iterrows():
                with st.container(border=True):
                    st.markdown(f"📍 **{row['river']}** — {row['station_name']}")
                    r1, r2 = st.columns(2)
                    r1.write(f"**Vodostaj:** {row['water_level'] if row['water_level'] else 'N/A'} cm")
                    r2.write(f"**Pretok:** {row['flow'] if row['flow'] else 'N/A'} m³/s")

if __name__ == "__main__":
    render()