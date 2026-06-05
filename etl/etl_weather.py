import requests
from datetime import datetime
from .db_utils import get_db_connection

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

def run_weather_etl():
    print(f"[{datetime.now()}] 🌤️ Učitavam vreme...")
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        for region, cfg in REGIONS.items():
            url = "https://api.open-meteo.com/v1/forecast"
            params = {
                "latitude": cfg["lat"], "longitude": cfg["lon"],
                "current": ["temperature_2m", "wind_speed_10m", "precipitation"],
                "hourly": ["precipitation"], "forecast_days": 1,
            }
            r = requests.get(url, params=params, timeout=15)
            data = r.json()
            current = data["current"]
            rain_24h = round(sum(data["hourly"]["precipitation"]), 1)
            query = """
            INSERT INTO weather_measurements (region, temperature, precipitation_now, precipitation_24h, wind_speed)
            VALUES (%s, %s, %s, %s, %s);
            """
            cur.execute(query, (region, current["temperature_2m"], current["precipitation"], rain_24h, current["wind_speed_10m"]))
        conn.commit()
    finally:
        cur.close(); conn.close()
