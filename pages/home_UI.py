import streamlit as st
import folium
from streamlit_folium import st_folium
import streamlit.components.v1 as components
import pandas as pd
from etl.db_utils import get_db_connection

# Konfiguracija boja za infrastrukturu
KATEGORIJE_BOJA = {
    "Bolnica": "red", "Gasilski dom": "orange", "Policija": "blue",
    "Vrtic": "green", "Sola": "darkgreen", "Staracki dom": "purple",
    "Apoteka": "lightred", "Benzinska pumpa": "gray", "Trafo stanica": "black",
    "Hidrant": "cadetblue", "Klinika": "pink", "Zdravnik": "lightblue",
}

@st.cache_data(ttl=600, show_spinner=False)
def fetch_from_db(lat, lon, radius_m, kategorije_tuple):
    results = {}
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        for naziv in kategorije_tuple:
            cur.execute("""
                SELECT ime, naslov, lat, lon,
                    ROUND(earth_distance(ll_to_earth(%s, %s), ll_to_earth(lat, lon))::numeric, 0) AS razdalja_m
                FROM kriticna_infrastruktura
                WHERE kategorija = %s AND earth_box(ll_to_earth(%s, %s), %s) @> ll_to_earth(lat, lon)
                ORDER BY razdalja_m ASC LIMIT 100
            """, (lat, lon, naziv, lat, lon, radius_m))
            rows = cur.fetchall()
            results[naziv] = [{"ime": r[0] or "Neznano", "naslov": r[1] or "", "lat": r[2], "lon": r[3], "razdalja_m": int(r[4])} for r in rows]
        conn.close()
    except Exception as e:
        st.error(f"DB greška: {e}")
    return results

def dohvati_prometne_podatke_za_mapu():
    try:
        conn = get_db_connection()
        query = "SELECT cesta, vzrok, opis, lat, lon, updated FROM prometni_dogodki WHERE updated > NOW() - INTERVAL '48 hours' ORDER BY updated DESC"
        df = pd.read_sql_query(query, conn)
        if not df.empty:
            df['updated'] = pd.to_datetime(df['updated'])
        conn.close()
        return df
    except Exception as e:
        st.error(f"Greška pri povezivanju sa bazom: {e}")
        return pd.DataFrame()

def render():
    st.title("🚨 Operativni sistem za zaštitu i spašavanje")
    st.markdown("---")

    # 1) NAČRTOVANJE INTERVENCIJE (Analiza)
    st.markdown("### 🛠️ 1. Planiranje intervencije")
    radius = st.number_input("Radijus pretrage (metara)", min_value=100, max_value=10000, value=2000, step=100)
    izbrane = st.multiselect("Kategorije objekata:", list(KATEGORIJE_BOJA.keys()), default=["Bolnica", "Gasilski dom", "Hidrant"])
    
    if "sel_lat" not in st.session_state:
        st.session_state.sel_lat, st.session_state.sel_lon = None, None

    m_analiza = folium.Map(location=[st.session_state.sel_lat or 46.0569, st.session_state.sel_lon or 14.5058], zoom_start=11)
    
    if st.session_state.sel_lat:
        # 1. Marker za centar
        folium.Marker([st.session_state.sel_lat, st.session_state.sel_lon], icon=folium.Icon(color="red", icon="exclamation-sign")).add_to(m_analiza)
        
        # 2. DODATO: Crveni krug koji prikazuje radijus
        folium.Circle(
            location=[st.session_state.sel_lat, st.session_state.sel_lon],
            radius=radius,  # Ovo koristi tvoj input
            color='red',
            fill=True,
            fill_color='red',
            fill_opacity=0.1
        ).add_to(m_analiza)
        
        # 3. Prikazivanje pronađenih objekata
        rezultati = fetch_from_db(st.session_state.sel_lat, st.session_state.sel_lon, radius, tuple(izbrane))
        for naziv, lista in rezultati.items():
            for obj in lista:
                # DODATNI FILTER: Ako je razdalja veća od radijusa, preskoči marker
                if obj['razdalja_m'] <= radius:
                    folium.Marker(
                        [obj['lat'], obj['lon']], 
                        tooltip=f"{obj['ime']} ({obj['razdalja_m']}m)", 
                        icon=folium.Icon(color=KATEGORIJE_BOJA.get(naziv, "blue"))
                    ).add_to(m_analiza)

    map_data = st_folium(m_analiza, width="100%", height=400, key="analiza_map")
    
    if map_data and map_data.get("last_clicked"):
        if map_data["last_clicked"]["lat"] != st.session_state.sel_lat:
            st.session_state.sel_lat, st.session_state.sel_lon = map_data["last_clicked"]["lat"], map_data["last_clicked"]["lng"]
            st.rerun()

    if st.session_state.sel_lat:
        rezultati = fetch_from_db(st.session_state.sel_lat, st.session_state.sel_lon, radius, tuple(izbrane))
        st.metric("Ukupno resursa u radijusu", sum(len(v) for v in rezultati.values()))
        for naziv in izbrane:
            objekti = rezultati.get(naziv, [])
            st.write(f"• **{naziv}:** {len(objekti)} objekata")
            for obj in objekti:
                st.caption(f"  - {obj['ime']} ({obj['naslov']}) ~ {obj['razdalja_m']}m")

    st.markdown("---")

    # 2) PROMETNI DOGAĐAJI
    st.markdown("### 🚗 2. Prometni događaji")
    df = dohvati_prometne_podatke_za_mapu()
    if not df.empty:
        najnovije = df['updated'].max()
        najcesca_cesta = df['cesta'].mode()[0] if not df['cesta'].mode().empty else "N/A"
        st.caption(f"🕒 Zadnji podaci: {najnovije.strftime('%d.%m. %H:%M')}")
        st.caption(f"Ukupno incidenata: **{len(df)}** | Zapor/blokad: **{df[df['opis'].str.contains('zapora|blokada', case=False, na=False)].shape[0]}**")
        st.caption(f"Najkritičnija cesta: **{najcesca_cesta}**")

        m_promet = folium.Map(location=[46.1512, 14.9955], zoom_start=8)
        for _, row in df.iterrows():
            if pd.notna(row['lat']) and pd.notna(row['lon']):
                vzrok = str(row['vzrok']).lower()
                color = "orange" if "delo" in vzrok else ("red" if "nesreća" in vzrok else "blue")
                popup_text = f"<div style='width: 200px'><b>🕒 {row['updated'].strftime('%d.%m. %H:%M')}</b><br><b>⚠️ {row['vzrok']}</b><br>{row['opis']}</div>"
                folium.Marker([row['lat'], row['lon']], tooltip=row['cesta'], popup=folium.Popup(popup_text, max_width=250), icon=folium.Icon(color=color)).add_to(m_promet)
        st_folium(m_promet, width="100%", height=400, key="promet_map")

    st.markdown("---")

    # 3) GURS PROSTORNI SISTEM
    st.markdown("### 📍 3. GURS Prostorni sistem")
    st.components.v1.iframe("https://ipi.eprostor.gov.si/jv/", height=500, scrolling=True)

    st.markdown("---")

    # 4) VREMENSKA PROGNOZA
    st.markdown("### 🌤️ 4. Vremenska prognoza")
    st.info("Ovde će biti integrisani podaci o vremenskoj prognozi.")

if __name__ == "__main__":
    render()