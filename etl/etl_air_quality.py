# etl/air_quality.py

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


OPEN_METEO_AQ_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"


AQI_CATEGORY = {
    (0,   20):  "Odlično",
    (20,  40):  "Dobro",
    (40,  60):  "Umjereno",
    (60,  80):  "Loše",
    (80,  100): "Vrlo loše",
    (100, 9999):"Opasno",
}


def get_aqi_category(aqi: float | None) -> str:
    if aqi is None:
        return "Nepoznato"
    for (lo, hi), label in AQI_CATEGORY.items():
        if lo <= aqi < hi:
            return label
    return "Opasno"


def fetch_air_quality(region: str, lat: float, lon: float) -> list[dict]:
    params = {
        "latitude":  lat,
        "longitude": lon,
        "hourly": [
            "pm10",
            "pm2_5",
            "carbon_monoxide",
            "nitrogen_dioxide",
            "sulphur_dioxide",
            "ozone",
            "european_aqi",
            "european_aqi_pm2_5",
            "european_aqi_pm10",
            "european_aqi_no2",
            "european_aqi_o3",
            "european_aqi_so2",
            "dust",
            "uv_index",
        ],
        "timezone":      "Europe/Ljubljana",
        "forecast_days": 5,  # AQ API podrzava do 5 dana
    }

    resp = requests.get(OPEN_METEO_AQ_URL, params=params, timeout=15)
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
        aqi_val   = data["european_aqi"][i]

        records.append({
            "region":              region,
            "lat":                 lat,
            "lon":                 lon,
            "forecast_time":       forecast_time.isoformat(),
            "forecast_horizon_h":  horizon_h,
            "pm10":                data["pm10"][i],
            "pm2_5":               data["pm2_5"][i],
            "carbon_monoxide":     data["carbon_monoxide"][i],
            "nitrogen_dioxide":    data["nitrogen_dioxide"][i],
            "sulphur_dioxide":     data["sulphur_dioxide"][i],
            "ozone":               data["ozone"][i],
            "european_aqi":        aqi_val,
            "european_aqi_pm2_5":  data["european_aqi_pm2_5"][i],
            "european_aqi_pm10":   data["european_aqi_pm10"][i],
            "european_aqi_no2":    data["european_aqi_no2"][i],
            "european_aqi_o3":     data["european_aqi_o3"][i],
            "european_aqi_so2":    data["european_aqi_so2"][i],
            "dust":                data["dust"][i],
            "uv_index":            data["uv_index"][i],
            "aqi_category":        get_aqi_category(aqi_val),
        })

    return records


def upsert_air_quality(records: list[dict]):
    if not records:
        return

    conn = get_db_connection()
    cur  = conn.cursor()

    query = """
        INSERT INTO air_quality_forecast (
            region, lat, lon,
            forecast_time, forecast_horizon_h,
            pm10, pm2_5,
            carbon_monoxide, nitrogen_dioxide, sulphur_dioxide, ozone,
            european_aqi, european_aqi_pm2_5, european_aqi_pm10,
            european_aqi_no2, european_aqi_o3, european_aqi_so2,
            dust, uv_index,
            aqi_category,
            fetched_at
        ) VALUES (
            %(region)s, %(lat)s, %(lon)s,
            %(forecast_time)s, %(forecast_horizon_h)s,
            %(pm10)s, %(pm2_5)s,
            %(carbon_monoxide)s, %(nitrogen_dioxide)s, %(sulphur_dioxide)s, %(ozone)s,
            %(european_aqi)s, %(european_aqi_pm2_5)s, %(european_aqi_pm10)s,
            %(european_aqi_no2)s, %(european_aqi_o3)s, %(european_aqi_so2)s,
            %(dust)s, %(uv_index)s,
            %(aqi_category)s,
            NOW()
        )
        ON CONFLICT (region, forecast_time) DO UPDATE SET
            forecast_horizon_h   = EXCLUDED.forecast_horizon_h,
            pm10                 = EXCLUDED.pm10,
            pm2_5                = EXCLUDED.pm2_5,
            carbon_monoxide      = EXCLUDED.carbon_monoxide,
            nitrogen_dioxide     = EXCLUDED.nitrogen_dioxide,
            sulphur_dioxide      = EXCLUDED.sulphur_dioxide,
            ozone                = EXCLUDED.ozone,
            european_aqi         = EXCLUDED.european_aqi,
            european_aqi_pm2_5   = EXCLUDED.european_aqi_pm2_5,
            european_aqi_pm10    = EXCLUDED.european_aqi_pm10,
            european_aqi_no2     = EXCLUDED.european_aqi_no2,
            european_aqi_o3      = EXCLUDED.european_aqi_o3,
            european_aqi_so2     = EXCLUDED.european_aqi_so2,
            dust                 = EXCLUDED.dust,
            uv_index             = EXCLUDED.uv_index,
            aqi_category         = EXCLUDED.aqi_category,
            fetched_at           = NOW();
    """

    cur.executemany(query, records)
    conn.commit()
    cur.close()
    conn.close()


def run_air_quality_etl():
    print(f"[{datetime.now()}] 💨 Pokrećem Air Quality ETL...")

    total = 0
    try:
        for region, coords in CITIES.items():
            records = fetch_air_quality(region, coords["lat"], coords["lon"])
            upsert_air_quality(records)
            total += len(records)
            print(f"  ✅ {region}: {len(records)} sati upisano")

        print(f"🎉 Air Quality ETL gotov! Ukupno: {total} redova.")

    except Exception as e:
        print(f"❌ Air Quality ETL Error: {e}")
        raise
