import requests
import json
from datetime import datetime, timezone
from .db_utils import get_db_connection

def run_quakes_etl():
    print(f"[{datetime.now()}] 🌋 Pokrećem ETL za potrese (u tabelu potresi_gasilci)...")
    
    try:
        # 1. Dohvatanje podataka
        url = (
            "https://www.seismicportal.eu/fdsnws/event/1/query"
            "?format=json&limit=100"
            "&minlat=45.4&maxlat=46.9"
            "&minlon=13.3&maxlon=16.6"
            "&orderby=time"
        )
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        events = resp.json().get("features", [])
        
        if not events:
            print("Nema novih podataka o potresima.")
            return

        # 2. Konekcija
        conn = get_db_connection()
        cur = conn.cursor()
        
        # 3. Parsiranje i Upis u POSTOJEĆU tabelu 'potresi_gasilci'
        for event in events:
            props = event.get("properties", {})
            coords = event.get("geometry", {}).get("coordinates", [0, 0, 0])
            
            lon = float(coords[0])
            lat = float(coords[1])
            depth = float(coords[2]) if len(coords) > 2 else 0.0
            
            time_str = props.get("time", "")
            try:
                event_time = datetime.strptime(time_str[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
            except:
                continue
                
            mag = float(props.get("mag", 0) or 0)
            region = props.get("flynn_region", "")
            
            # Upisujemo u tvoju tabelu: potresi_gasilci
            # Kolone: cas, mag, globina_km, lokacija, lat, lon
            cur.execute("""
                INSERT INTO potresi_gasilci (cas, mag, globina_km, lokacija, lat, lon)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
            """, (event_time, mag, depth, region, lat, lon))
        
        conn.commit()
        cur.close()
        conn.close()
        print("🎉 Quakes ETL uspešno završen!")
        
    except Exception as e:
        print(f"❌ Quakes ETL Error: {e}")