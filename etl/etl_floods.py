import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from .db_utils import get_db_connection # Uvozimo našu konekciju

# REGIONS definiciju stavi u poseban fajl ili je kopiraj ovde
REGIONS = {
    "Ljubljana": {"lat": 46.0569, "lon": 14.5058, "rivers": ["Ljubljanica", "Sava", "Gradaščica", "Iška"]},
    "Maribor": {"lat": 46.5547, "lon": 15.6459, "rivers": ["Drava", "Dravinja", "Pesnica"]},
    "Celje": {"lat": 46.2397, "lon": 15.2677, "rivers": ["Savinja", "Voglajna", "Hudinja"]},
    "Kranj": {"lat": 46.2389, "lon": 14.3556, "rivers": ["Sava", "Kokra", "Sora"]},
    "Koper": {"lat": 45.5481, "lon": 13.7302, "rivers": ["Rižana", "Dragonja", "Badaševica"]},
    "Novo Mesto": {"lat": 45.8030, "lon": 15.1689, "rivers": ["Krka", "Kolpa", "Temenica"]},
    "Murska Sobota": {"lat": 46.6625, "lon": 16.1664, "rivers": ["Mura", "Ledava", "Ščavnica"]},
    "Nova Gorica": {"lat": 45.9560, "lon": 13.6484, "rivers": ["Soča", "Vipava", "Idrijca"]},
}


def run_floods_etl():
    print(f"[{datetime.now()}] 🌊 Pokrećem ETL za poplave...")
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 1. Dohvatanje podataka sa ARSO-a
        arso_url = "https://www.arso.gov.si/xml/vode/hidro_podatki_dnevno_porocilo.xml"
        arso_res = requests.get(arso_url, timeout=20)
        arso_stations = []
        
        if arso_res.status_code == 200:
            root = ET.fromstring(arso_res.content)
            for postaja in root.findall(".//postaja"):
                arso_stations.append({
                    "river": postaja.findtext("reka"),
                    "name": postaja.findtext("ime"),
                    "level": postaja.findtext("vodostaj"),
                    "flow": postaja.findtext("pretok"),
                })
        
        # 2. Iteracija kroz regione i Open-Meteo
        for reg_name, cfg in REGIONS.items():
            meteo_url = "https://api.open-meteo.com/v1/forecast"
            params = {
                "latitude": cfg["lat"], "longitude": cfg["lon"],
                "current": ["temperature_2m", "wind_speed_10m", "precipitation"],
                "hourly": ["precipitation"], "forecast_days": 1
            }
            m_res = requests.get(meteo_url, params=params, timeout=20).json()
            
            temp = m_res["current"]["temperature_2m"]
            rain_now = m_res["current"]["precipitation"]
            rain_24h = round(sum(m_res["hourly"]["precipitation"]), 1)
            wind = m_res["current"]["wind_speed_10m"]
            
            matched_stations = [s for s in arso_stations if s["river"] in cfg["rivers"]]
            
            cursor.execute("DELETE FROM floods_data WHERE region = %s", (reg_name,))
            
            if matched_stations:
                for st in matched_stations:
                    cursor.execute("""
                        INSERT INTO floods_data (region, river, station_name, water_level, flow, temp, rain_now, rain_24h, wind, drought_level)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (reg_name, st["river"], st["name"], st["level"], st["flow"], temp, rain_now, rain_24h, wind, "Low concern"))
            else:
                cursor.execute("""
                    INSERT INTO floods_data (region, river, station_name, water_level, flow, temp, rain_now, rain_24h, wind, drought_level)
                    VALUES (%s, NULL, NULL, NULL, NULL, %s, %s, %s, %s, %s)
                """, (reg_name, temp, rain_now, rain_24h, wind, "Low concern"))
        
        conn.commit()
        cursor.close()
        conn.close()
        print("🎉 Floods ETL uspešno završen!")
        
    except Exception as e:
        print(f"❌ Floods ETL Error: {e}")