import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from .db_utils import get_db_connection

def run_rivers_etl():
    print(f"[{datetime.now()}] 🌊 Scraping ARSO river data for entire Slovenia...")
    
    try:
        # 1. Dohvatanje podataka sa interneta
        url = "https://www.arso.gov.si/xml/vode/hidro_podatki_dnevno_porocilo.xml"
        r = requests.get(url, timeout=15)
        r.raise_for_status() # Ovo je dobro dodati da baci grešku ako sajt ne radi
        root = ET.fromstring(r.content)
        
        # 2. Konekcija na bazu preko zajedničkog alata
        conn = get_db_connection()
        cur = conn.cursor()
        
        query = """
        INSERT INTO river_measurements (river, station, water_level, flow_rate)
        VALUES (%s, %s, %s, %s);
        """
        
        # 3. Procesiranje podataka
        for postaja in root.findall(".//postaja"):
            river = postaja.findtext("reka")
            name = postaja.findtext("ime") or postaja.findtext("merilno_mesto") or f"{river} Station"
            level = postaja.findtext("vodostaj")
            flow = postaja.findtext("pretok")
            
            if river:
                water_level = int(level) if level and level.isdigit() else None
                try:
                    flow_rate = float(flow) if flow else None
                except ValueError:
                    flow_rate = None
                
                cur.execute(query, (river, name, water_level, flow_rate))
        
        # 4. Potvrda i zatvaranje
        conn.commit()
        cur.close()
        conn.close()
        print("🎉 River matrix successfully archived in Neon!")
        
    except Exception as e:
        print(f"❌ River Worker Error: {e}")