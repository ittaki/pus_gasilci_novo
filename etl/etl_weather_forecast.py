import requests
from datetime import datetime
from datetime import timezone
from .db_utils import get_db_connection

CITIES = {
    "Ljubljana":      {"lat": 46.0569, "lon": 14.5058},
    "Maribor":        {"lat": 46.5547, "lon": 15.6459},
    "Celje":          {"lat": 46.2397, "lon": 15.2677},
    "Kranj":          {"lat": 46.2389, "lon": 14.3556},
    "Koper":          {"lat": 45.5481, "lon": 13.7302},
    "Novo Mesto":     {"lat": 45.8030, "lon": 15.1689},
    "Murska Sobota":  {"lat": 46.6625, "lon": 16.1664},
    "Nova Gorica":    {"lat": 45.9560, "lon": 13.6484},
}

WMO_CODES = {
    0: "Vedro", 1: "Pretežno vedro", 2: "Delno oblačno", 3: "Oblačno",
    45: "Megla", 48: "Poledica (megla)",
    51: "Slaba rosica", 53: "Rosica", 55: "Gusta rosica",
    61: "Slaba kiša", 63: "Kiša", 65: "Jaka kiša",
    71: "Slab sneg", 73: "Sneg", 75: "Jak sneg",
    80: "Pljusak", 81: "Jaki pljuskovi", 82: "Olujni pljuskovi",
    95: "Grmljavinska oluja", 96: "Oluja s gradom", 99: "Jaka oluja s gradom",
}

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

def fetch_forecast(region: str, lat: float, lon: float) -> list[dict]:
    params = {
        "latitude":   lat,
        "longitude":  lon,
        "hourly": [
            "temperature_2m",
            "apparent_temperature",
            "precipitation_probability",
            "precipitation",
            "snowfall",
            "weather_code",
            "cloud_cover",
            "wind_speed_10m",
            "wind_gusts_10m",
            "wind_direction_10m",
            "relative_humidity_2m",
        ],
        "timezone":        "Europe/Ljubljana",
        "forecast_days":   7,   # 7 dana = 168h unapred
        "wind_speed_unit": "kmh",
    }

    resp = requests.get(OPEN_METEO_URL, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()["hourly"]

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    records = []

    for i, timestamp_str in enumerate(data["time"]):
        forecast_time = datetime.fromisoformat(timestamp_str)

        # Preskoci prošlost
        if forecast_time <= now:
            continue

        horizon_h = round((forecast_time - now).total_seconds() / 3600)
        wcode = data["weather_code"][i]

        records.append({
            "region":               region,
            "lat":                  lat,
            "lon":                  lon,
            "forecast_time":        forecast_time.isoformat(),
            "forecast_horizon_h":   horizon_h,
            "temperature_2m":       data["temperature_2m"][i],
            "apparent_temperature": data["apparent_temperature"][i],
            "precipitation":        data["precipitation"][i],
            "precipitation_prob":   data["precipitation_probability"][i],
            "snowfall":             data["snowfall"][i],
            "wind_speed_10m":       data["wind_speed_10m"][i],
            "wind_gusts_10m":       data["wind_gusts_10m"][i],
            "wind_direction_10m":   data["wind_direction_10m"][i],
            "humidity_2m":          data["relative_humidity_2m"][i],
            "cloud_cover":          data["cloud_cover"][i],
            "weather_code":         wcode,
            "weather_description":  WMO_CODES.get(wcode, f"Kod {wcode}"),
        })

    return records


def upsert_forecast(records: list[dict]):
    if not records:
        return

    conn = get_db_connection()
    cur  = conn.cursor()

    query = """
        INSERT INTO weather_forecast (
            region, lat, lon,
            forecast_time, forecast_horizon_h,
            temperature_2m, apparent_temperature,
            precipitation, precipitation_prob, snowfall,
            wind_speed_10m, wind_gusts_10m, wind_direction_10m,
            humidity_2m, cloud_cover,
            weather_code, weather_description,
            fetched_at
        ) VALUES (
            %(region)s, %(lat)s, %(lon)s,
            %(forecast_time)s, %(forecast_horizon_h)s,
            %(temperature_2m)s, %(apparent_temperature)s,
            %(precipitation)s, %(precipitation_prob)s, %(snowfall)s,
            %(wind_speed_10m)s, %(wind_gusts_10m)s, %(wind_direction_10m)s,
            %(humidity_2m)s, %(cloud_cover)s,
            %(weather_code)s, %(weather_description)s,
            NOW()
        )
        ON CONFLICT (region, forecast_time) DO UPDATE SET
            forecast_horizon_h   = EXCLUDED.forecast_horizon_h,
            temperature_2m       = EXCLUDED.temperature_2m,
            apparent_temperature = EXCLUDED.apparent_temperature,
            precipitation        = EXCLUDED.precipitation,
            precipitation_prob   = EXCLUDED.precipitation_prob,
            snowfall             = EXCLUDED.snowfall,
            wind_speed_10m       = EXCLUDED.wind_speed_10m,
            wind_gusts_10m       = EXCLUDED.wind_gusts_10m,
            wind_direction_10m   = EXCLUDED.wind_direction_10m,
            humidity_2m          = EXCLUDED.humidity_2m,
            cloud_cover          = EXCLUDED.cloud_cover,
            weather_code         = EXCLUDED.weather_code,
            weather_description  = EXCLUDED.weather_description,
            fetched_at           = NOW();
    """

    cur.executemany(query, records)
    conn.commit()
    cur.close()
    conn.close()


def run_weather_forecast_etl():
    print(f"[{datetime.now()}] 🌤️ Pokrećem Weather Forecast ETL...")

    total = 0
    try:
        for region, coords in CITIES.items():
            records = fetch_forecast(region, coords["lat"], coords["lon"])
            upsert_forecast(records)
            total += len(records)
            print(f"  ✅ {region}: {len(records)} prognoznih sati upisano")

        print(f"🎉 Weather Forecast ETL gotov! Ukupno: {total} redova.")

    except Exception as e:
        print(f"❌ Weather Forecast ETL Error: {e}")
        raise

