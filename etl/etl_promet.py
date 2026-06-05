import requests
from datetime import datetime, timezone
from psycopg2.extras import execute_values
from .db_utils import get_db_connection
from dotenv import load_dotenv
import os

load_dotenv()

def run_promet_etl():
    print(f"[{datetime.now()}] 🚗 Pokrećem ETL za promet (NAP b2b)...")
    url = "https://b2b.nap.si/data/b2b.events.geojson.sl_SI"
    
    USER = os.getenv("USER")
    PASS = os.getenv("PASS")
    
    try:
        # Koristimo Session za stabilniju konekciju i duži timeout
        session = requests.Session()
        resp = session.get(url, auth=(USER, PASS), timeout=60)
        resp.raise_for_status()
        data = resp.json()
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Pripremamo listu podataka za grupni unos
        values = []
        for feature in data.get("features", []):
            props = feature.get("properties", {})
            coords = feature.get("geometry", {}).get("coordinates", [0, 0])
            
            # Parsiranje vremena
            try:
                updated_str = props.get("updated", "")
                if updated_str:
                    updated_dt = datetime.fromisoformat(updated_str.replace("Z", "+00:00"))
                else:
                    updated_dt = datetime.now(timezone.utc)
            except:
                updated_dt = datetime.now(timezone.utc)
            
            # Dodajemo u listu (red po red)
            values.append((
                props.get("id"), props.get("cesta"), props.get("vzrok"), 
                props.get("opis"), props.get("dodatnoPojasnilo"), 
                coords[0], coords[1], updated_dt
            ))
            
        # Bulk upsert upit
        query = """
            INSERT INTO prometni_dogodki (id, cesta, vzrok, opis, dodatno_pojasnilo, lon, lat, updated)
            VALUES %s
            ON CONFLICT (id) DO UPDATE SET
                cesta = EXCLUDED.cesta,
                vzrok = EXCLUDED.vzrok,
                opis = EXCLUDED.opis,
                dodatno_pojasnilo = EXCLUDED.dodatno_pojasnilo,
                lon = EXCLUDED.lon,
                lat = EXCLUDED.lat,
                updated = EXCLUDED.updated;
        """
        
        # Grupno izvršavanje
        if values:
            execute_values(cur, query, values)
            conn.commit()
            print(f"🎉 Promet ETL završen! Ažurirano {len(values)} događaja.")
        else:
            print("ℹ️ Nema novih podataka za ažuriranje.")
            
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Promet ETL Error: {e}")