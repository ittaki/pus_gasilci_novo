import streamlit as st
import folium
from streamlit_folium import st_folium
import streamlit.components.v1 as components
import pandas as pd
from etl.db_utils import get_db_connection

# Konfiguracija boja za infrastrukturu
KATEGORIJE_BOJA = {
    "Bolnišnica": "red", "Gasilski dom": "orange", "Policija": "blue",
    "Vrtec": "green", "Šola": "darkgreen", "Dom za starejše": "purple",
    "Lekarna": "lightred", "Bencinski servis": "gray", "Transformatorska postaja": "black",
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

@st.cache_data(ttl=600, show_spinner=False)
def fetch_weather_forecast():
    try:
        conn = get_db_connection()
        query = """
            SELECT region, forecast_time, temperature_2m, apparent_temperature,
                   precipitation, precipitation_prob, snowfall,
                   wind_speed_10m, wind_gusts_10m, wind_direction_10m,
                   humidity_2m, cloud_cover, weather_description
            FROM weather_forecast
            WHERE forecast_time >= NOW()
            ORDER BY region, forecast_time ASC
        """
        df = pd.read_sql_query(query, conn)
        conn.close()
        if not df.empty:
            df['forecast_time'] = pd.to_datetime(df['forecast_time'], utc=True)
            df['forecast_time'] = df['forecast_time'].dt.tz_convert('Europe/Ljubljana')
            df['dan'] = df['forecast_time'].dt.date
            df['sat'] = df['forecast_time'].dt.strftime('%H:%M')
        return df
    except Exception as e:
        st.error(f"Greška pri učitavanju prognoze: {e}")
        return pd.DataFrame()

def weather_icon(opis):
    opis = str(opis).lower()
    if "snow" in opis: return "❄️"
    elif "rain" in opis or "drizzle" in opis: return "🌧️"
    elif "thunder" in opis: return "⛈️"
    elif "fog" in opis or "mist" in opis: return "🌫️"
    elif "cloud" in opis: return "⛅"
    elif "clear" in opis or "sunny" in opis: return "☀️"
    else: return "🌤️"

def wind_direction_arrow(degrees):
    arrows = ['↑','↗','→','↘','↓','↙','←','↖']
    idx = round(degrees / 45) % 8
    return arrows[idx]

def render():
    #st.title("🚨 Operativni sistem za zaštitu i spašavanje")
    #st.markdown("---")

    # 1) PLANIRANJE INTERVENCIJE
    st.markdown("### 🛠️ 1. Planiranje intervencije")
    radius = st.number_input("Radij iskanja (metri)", min_value=100, max_value=10000, value=2000, step=100)
    izbrane = st.multiselect("Kategorije objektov:", list(KATEGORIJE_BOJA.keys()), default=["Bolnišnica", "Gasilski dom", "Hidrant"])

    if "sel_lat" not in st.session_state:
        st.session_state.sel_lat, st.session_state.sel_lon = None, None

    m_analiza = folium.Map(location=[st.session_state.sel_lat or 46.0569, st.session_state.sel_lon or 14.5058], zoom_start=11)

    if st.session_state.sel_lat:
        folium.Marker([st.session_state.sel_lat, st.session_state.sel_lon], icon=folium.Icon(color="red", icon="exclamation-sign")).add_to(m_analiza)
        folium.Circle(
            location=[st.session_state.sel_lat, st.session_state.sel_lon],
            radius=radius,
            color='red', fill=True, fill_color='red', fill_opacity=0.1
        ).add_to(m_analiza)
        rezultati = fetch_from_db(st.session_state.sel_lat, st.session_state.sel_lon, radius, tuple(izbrane))
        for naziv, lista in rezultati.items():
            for obj in lista:
                if obj['razdalja_m'] <= radius:
                    folium.Marker(
                        [obj['lat'], obj['lon']],
                        tooltip=f"{obj['ime']} ({obj['razdalja_m']}m)",
                        icon=folium.Icon(color=KATEGORIJE_BOJA.get(naziv, "blue"))
                    ).add_to(m_analiza)

    map_data = st_folium(m_analiza, width="100%", height=400, key="analiza_map")

    if map_data and map_data.get("last_clicked"):
        if map_data["last_clicked"]["lat"] != st.session_state.sel_lat:
            st.session_state.sel_lat = map_data["last_clicked"]["lat"]
            st.session_state.sel_lon = map_data["last_clicked"]["lng"]
            st.rerun()

    if st.session_state.sel_lat:
        rezultati = fetch_from_db(st.session_state.sel_lat, st.session_state.sel_lon, radius, tuple(izbrane))
        st.metric("Skupaj virov v radiju", sum(len(v) for v in rezultati.values()))
        for naziv in izbrane:
            objekti = rezultati.get(naziv, [])
            st.write(f"• **{naziv}:** {len(objekti)}")
            for obj in objekti:
                st.caption(f"  - {obj['ime']} ({obj['naslov']}) ~ {obj['razdalja_m']}m")

    st.markdown("---")

    # 2) PROMETNI DOGAĐAJI
    st.markdown("### 🚗 2. Prometni dogodki")
    df = dohvati_prometne_podatke_za_mapu()
    if not df.empty:
        najnovije = df['updated'].max()
        najcesca_cesta = df['cesta'].mode()[0] if not df['cesta'].mode().empty else "N/A"
        st.caption(f"🕒 Zadnji podatki: {najnovije.strftime('%d.%m. %H:%M')}")
        st.caption(f"Skupaj incidentov: **{len(df)}** | Zapor/blokad: **{df[df['opis'].str.contains('zapora|blokada', case=False, na=False)].shape[0]}**")
        st.caption(f"Najbolj kritična cesta:: **{najcesca_cesta}**")
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
    #st.iframe("https://ipi.eprostor.gov.si/jv/", height=500)
    components.iframe("https://ipi.eprostor.gov.si/jv/", height=500)

    st.markdown("---")

    # 4) VREMENSKA PROGNOZA
    st.markdown("### 🌤️ 4. Vremenska napoved")
    df_w = fetch_weather_forecast()

    if not df_w.empty:
        regije = sorted(df_w['region'].unique())
        col_reg, col_mode = st.columns([2, 2])
        with col_reg:
            sel_region = st.selectbox("📍 Regija:", regije, index=regije.index("Ljubljana") if "Ljubljana" in regije else 0)
        with col_mode:
            prikaz = st.radio("Prikaz:", ["Po dnevih", "Po urah"], horizontal=True)

        df_region = df_w[df_w['region'] == sel_region].copy()

        if prikaz == "Po dnevih":
            df_daily = df_region.groupby('dan').agg(
                temp_min=('temperature_2m', 'min'),
                temp_max=('temperature_2m', 'max'),
                precipitation=('precipitation', 'sum'),
                precip_prob_max=('precipitation_prob', 'max'),
                wind_max=('wind_speed_10m', 'max'),
                gusts_max=('wind_gusts_10m', 'max'),
                snowfall=('snowfall', 'sum'),
                humidity_avg=('humidity_2m', 'mean'),
                opis=('weather_description', lambda x: x.mode()[0] if not x.mode().empty else x.iloc[0])
            ).reset_index()

            st.markdown(f"#### 📅 7-dnevna napoved — {sel_region}")
            cols = st.columns(len(df_daily))
            for i, (_, row) in enumerate(df_daily.iterrows()):
                with cols[i]:
                    dan_naziv = pd.Timestamp(row['dan']).strftime('%a\n%d.%m')
                    ikona = weather_icon(row['opis'])
                    snowfall_div = (
                        f'<div style="font-size:11px; color:#7ab">❄️ {row["snowfall"]:.1f}cm</div>'
                        if row['snowfall'] > 0
                        else '<span></span>'
                    )
                    st.markdown(f"""
                    <div style='background: var(--color-surface, #f9f8f5); border: 1px solid rgba(0,0,0,0.08);
                                        border-radius: 12px; padding: 10px 6px; text-align: center; font-size: 13px;'>
                        <div style='font-weight:600; color:#555; font-size:11px'>{dan_naziv}</div>
                        <div style='font-size:28px; margin:4px 0'>{ikona}</div>
                        <div style='font-size:12px; color:#888; margin-bottom:4px'>{row['opis'][:20]}</div>
                        <div style='font-weight:700; font-size:15px'>{row['temp_max']:.0f}° / <span style='color:#888'>{row['temp_min']:.0f}°</span></div>
                        <div style='margin-top:5px; font-size:11px; color:#3a7abf'>🌧️ {row['precip_prob_max']}% · {row['precipitation']:.1f}mm</div>
                        <div style='font-size:11px; color:#555'>💨 {row['wind_max']:.0f} km/h</div>
                        {snowfall_div}
                    </div>
                    """, unsafe_allow_html=True)

            st.markdown("##### 📊 Podrobna tabela")
            df_table = df_daily.copy()
            df_table['dan'] = df_table['dan'].apply(lambda d: pd.Timestamp(d).strftime('%A, %d.%m.%Y'))
            df_table.columns = ['Dan', 'Min temp (°C)', 'Max temp (°C)', 'Padavine (mm)',
                                'Vjer. kiše (%)', 'Max vjetar (km/h)', 'Max udari (km/h)',
                                'Snijeg (cm)', 'Vlažnost (%)', 'Opis']
            st.dataframe(df_table.round(1), width='stretch', hide_index=True)

        else:  # Po satima
            dani = sorted(df_region['dan'].unique())
            sel_dan = st.selectbox("📅 Dan:", dani, format_func=lambda d: pd.Timestamp(d).strftime('%A, %d.%m.%Y'))
            df_sat = df_region[df_region['dan'] == sel_dan].copy()

            st.markdown(f"#### 🕐 Urna napoved — {sel_region}, {pd.Timestamp(sel_dan).strftime('%d.%m.%Y')}")
            for _, row in df_sat.iterrows():
                ikona = weather_icon(row['weather_description'])
                arrow = wind_direction_arrow(row['wind_direction_10m'] if pd.notna(row['wind_direction_10m']) else 0)
                with st.container():
                    c1, c2, c3, c4, c5 = st.columns([1, 2, 2, 2, 3])
                    with c1:
                        st.markdown(f"**{row['sat']}**")
                        st.markdown(f"<span style='font-size:22px'>{ikona}</span>", unsafe_allow_html=True)
                    with c2:
                        st.metric("🌡️ Temp", f"{row['temperature_2m']:.1f}°C", delta=f"osj. {row['apparent_temperature']:.1f}°C", delta_color="off")
                    with c3:
                        st.metric("🌧️ Padavine", f"{row['precipitation']:.1f}mm", delta=f"{row['precipitation_prob']}% vjerovatnoća", delta_color="off")
                    with c4:
                        st.metric(f"💨 Veter {arrow}", f"{row['wind_speed_10m']:.0f} km/h", delta=f"udari {row['wind_gusts_10m']:.0f} km/h", delta_color="off")
                    with c5:
                        st.caption(f"💧 Vlažnost: **{row['humidity_2m']}%** &nbsp;|&nbsp; ☁️ Oblačnost: **{row['cloud_cover']}%**")
                        if pd.notna(row['snowfall']) and row['snowfall'] > 0:
                            st.caption(f"❄️ Sneg: **{row['snowfall']:.1f}cm**")
                        st.caption(f"_{row['weather_description']}_")
                    st.divider()

            st.markdown("##### 📊 Tabela urnih podatkov")
            df_sat_table = df_sat[['sat', 'temperature_2m', 'apparent_temperature',
                                    'precipitation', 'precipitation_prob',
                                    'wind_speed_10m', 'wind_gusts_10m',
                                    'humidity_2m', 'cloud_cover', 'weather_description']].copy()
            df_sat_table.columns = ['Ura', 'Temp (°C)', 'Obč. temp (°C)', 'Padavine (mm)',
                                     'Verj. dežja (%)', 'Veter (km/h)', 'Sunki (km/h)',
                                     'Vlažnost (%)', 'Oblačnost (%)', 'Opis']
            st.dataframe(df_sat_table.round(1), width='stretch', hide_index=True)

    else:
        st.warning("⚠️ V bazi ni podatkov o vremenski napovedi.")

if __name__ == "__main__":
    render()