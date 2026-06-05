import requests
import json
from datetime import datetime, timezone
from .db_utils import get_db_connection
from dotenv import load_dotenv
import os

load_dotenv()
FIRMS_KEY = os.getenv("NASA_FIRMS_KEY")

if not FIRMS_KEY:
    raise ValueError("❌ Greška: NASA_FIRMS_KEY nije pronađen u .env fajlu!")
SOURCE_NAME = "NASA FIRMS"



def run_fires_etl():
    print(f"[{datetime.now()}] 🔥 Pokrećem ETL za požare (NASA FIRMS)...")
    
    try:
        # 1. Dohvatanje podataka
        url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{FIRMS_KEY}/VIIRS_SNPP_NRT/13.3,45.4,16.6,46.9/10"
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        
        lines = resp.text.strip().split("\n")
        if len(lines) < 2:
            print("Nema podataka o požarima.")
            return

        headers = [h.strip() for h in lines[0].split(",")]
        rows = []
        for line in lines[1:]:
            vals = [v.strip() for v in line.split(",")]
            if len(vals) == len(headers):
                rows.append(dict(zip(headers, vals)))

        # 2. Konekcija i upis
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Pronađi source_id
        cur.execute("SELECT id FROM source_system WHERE name = %s", (SOURCE_NAME,))
        source_row = cur.fetchone()
        if not source_row:
            print(f"Greška: Izvor {SOURCE_NAME} nije pronađen u bazi.")
            return
        source_id = source_row[0]

        # 3. Parsiranje i Upis
        for row in rows:
            try:
                lat = float(row.get("latitude", 0))
                lon = float(row.get("longitude", 0))
                conf = row.get("confidence", "0")
                conf = int(conf) if conf.isdigit() else 50
                frp = float(row.get("frp", 0) or 0)
                sat = row.get("satellite", "VIIRS")
                
                dt_str = f"{row.get('acq_date')} {row.get('acq_time', '0000')[:2]}:{row.get('acq_time', '0000')[2:]}"
                detected_at = datetime.strptime(dt_str, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
                
                geom_wkt = f"SRID=4326;POINT({lon} {lat})"
                
                cur.execute("""
                    INSERT INTO fire_hotspot (source_id, detected_at, geom, confidence, frp, satellite, raw_data)
                    VALUES (%s, %s, ST_GeomFromEWKT(%s), %s, %s, %s, %s::jsonb)
                    ON CONFLICT DO NOTHING
                """, (source_id, detected_at, geom_wkt, conf, frp, sat, json.dumps(row)))
            except Exception as e:
                continue # Preskoči red ako parsiranje ne uspe

        conn.commit()
        cur.close()
        conn.close()
        print("🎉 Fire ETL uspešno završen!")
        
    except Exception as e:
        print(f"❌ Fire ETL Error: {e}")