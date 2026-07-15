import streamlit as st

# 1. Konfiguracija stranice
st.set_page_config(
    page_title="Gasilski Operativni Center",
    page_icon="🚒",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 2. POPRAVLJENI CSS: Kompletne ivice oko svake opcije u meniju
st.markdown("""
    <style>
        /* Sakrivanje sidebar-a */
        [data-testid="stSidebar"] { display: none !important; }
        [data-testid="stSidebarCollapseButton"] { display: none !important; }
        
        /* Pomeranje sadržaja skroz gore */
        .main .block-container {
            padding-top: 20px !important;
            padding-bottom: 30px !important;
        }
        
        /* Pozadina cele stranice */
        .stApp {
            background-color: #f4f6f9 !important;
        }
        
        /* OKVIR ZA CELU TRAKU MENIJA */
        div[data-testid="stTabBar"] {
            background-color: #ffffff !important;
            padding: 10px 14px !important;
            border-radius: 8px !important;
            border: 1px solid #bdc3c7 !important; /* Spoljni sivi ram oko celog menija */
            box-shadow: 0px 4px 12px rgba(0, 0, 0, 0.05) !important;
            gap: 12px !important;
            margin-bottom: 25px !important;
        }
        
        /* SVE ČETIRI IVICE ZA SVAKO POJEDINAČNO DUGME (KADA NISU KLIKNUTA) */
        button[data-testid="stBaseButton-tab"] {
            background-color: #f8f9fa !important;
            color: #2c3e50 !important;
            
            /* KLJUČNA POPRAVKA: Kompletna tanka siva ivica oko svakog dugmeta */
            border: 1px solid #cccccc !important; 
            
            border-radius: 6px !important;
            padding: 8px 20px !important;
            font-weight: 500 !important;
            transition: all 0.2s ease;
        }
        
        /* Efekat kada se mišem pređe preko pojedinačnog dugmeta */
        button[data-testid="stBaseButton-tab"]:hover {
            border-color: #A30000 !important;
            color: #A30000 !important;
            background-color: #fdeded !important;
        }
        
        /* IVICE I IZGLED ZA AKTIVNO (KLIKNUTO) DUGME */
        button[aria-selected="true"] {
            background-color: #A30000 !important;
            color: white !important;
            border: 1px solid #A30000 !important; /* Crveni ram za aktivno dugme */
            font-weight: bold !important;
            box-shadow: 0px 4px 8px rgba(163, 0, 0, 0.3) !important;
        }
        
        /* Potpuno uklanjanje fabričkih linija koje Streamlit podmeće ispod menija */
        div[data-testid="stTabBarTabListIndicator"] {
            background-color: transparent !important;
        }
        .st-emotion-cache-6w7g63 {
            border-bottom: none !important;
        }
    </style>
""", unsafe_allow_html=True)

# 3. NASLOV NA SAMOM VRHU
st.markdown("""
    <div style="text-align: center; margin-top: -15px; margin-bottom: 25px;">
        <h1 style="color: #A30000; font-family: sans-serif; font-size: 36px; margin: 0; font-weight: 800; letter-spacing: 0.5px;">
            🚒 GASILSKI OPERATIVNI CENTER
        </h1>
        <p style="color: #475569; margin: 6px 0 0 0; font-size: 15px; font-weight: 500; letter-spacing: 0.3px;">
            Sistem za zgodnje opozarjanje in spremljanje naravnih katastrof | Republika Slovenija
        </p>
    </div>
""", unsafe_allow_html=True)

# 4. GORNJI WEB MENI - Sredi redosled da odgovara tvojim "with" blokovima
tab_home, tab_fires, tab_floods, tab_earthquakes, tab_satelit, tab_help, tab_about = st.tabs([
    "🏠 Začetna", 
    "🔥 Požari", 
    "🌊 Poplave", 
    "🌋 Potresi", 
    "🛰️ Satelit",
    "ℹ️ Pomoč in protokoli", 
    "👥 O projektu"
])

# Sada redosled "with" blokova odgovara gornjoj listi:
with tab_home:
    from pages import home_UI
    home_UI.render()

with tab_fires:
    from pages import fires_UI
    fires_UI.render()

with tab_floods:
    from pages import floods_UI
    floods_UI.render()

with tab_earthquakes:
    from pages import earthquakes_UI
    earthquakes_UI.render()

with tab_satelit:
    from pages import satellite_UI
    satellite_UI.render()

with tab_help:
    from pages import pomoc_UI
    pomoc_UI.render()

with tab_about:
    from pages import o_nama_UI
    o_nama_UI.render()

# 6. FIKSNI FOOTER
st.markdown("<br><hr>", unsafe_allow_html=True)
st.markdown("""
    <div style="text-align:center; color:#7f8c8d; font-size:12px; padding:5px;">
        © 2026 Gasilski Operativni Center | Fakulteta za elektrotehniko / računalništvo | Integrisani Neon Cloud i NASA/ARSO/EMSC sistemi
    </div>
""", unsafe_allow_html=True)