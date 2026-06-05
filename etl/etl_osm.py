import osmium
import psycopg2
import requests
import os
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from .db_utils import get_db_connection


PBF_URL = "https://download.geofabrik.de/europe/slovenia-latest.osm.pbf"
PBF_FILE = "slovenia-latest.osm.pbf"


AMENITY_MAP = {
    "hospital": "Bolnica",
    "fire_station": "Gasilski dom",
    "police": "Policija",
    "kindergarten": "Vrtic",
    "school": "Sola",
    "nursing_home": "Staracki dom",
    "social_facility": "Staracki dom",
    "pharmacy": "Apoteka",
    "fuel": "Benzinska pumpa",
    "clinic": "Klinika",
    "doctors": "Zdravnik",
    "assembly_point": "Zbirno mesto",
}
HEALTHCARE_MAP = {
    "hospital": "Bolnica",
    "clinic": "Klinika",
    "centre": "Klinika",
    "doctor": "Zdravnik",
    "general_practitioner": "Zdravnik",
    "pharmacy": "Apoteka",
    "nursing_home": "Staracki dom",
}
SOCIAL_MAP = {
    "nursing_home": "Staracki dom",
    "assisted_living": "Staracki dom",
    "group_home": "Staracki dom",
}
POWER_MAP = {
    "substation": "Trafo stanica",
    "transformer": "Trafo stanica",
}
EMERGENCY_MAP = {
    "fire_hydrant": "Hidrant",
    "assembly_point": "Zbirno mesto",
}
BUILDING_MAP = {
    "hospital": "Bolnica",
    "fire_station": "Gasilski dom",
    "police": "Policija",
    "school": "Sola",
    "kindergarten": "Vrtic",
}


class OSMHandler(osmium.SimpleHandler):
    def __init__(self):
        super().__init__()
        self.objects = []

    def _process(self, obj, lat, lon):
        tags = {t.k: t.v for t in obj.tags}
        # Tvoja logika za mapiranje ostaje ista
        kategorija = (
            AMENITY_MAP.get(tags.get("amenity", "")) or
            HEALTHCARE_MAP.get(tags.get("healthcare", "")) or
            SOCIAL_MAP.get(tags.get("social_facility", "")) or
            POWER_MAP.get(tags.get("power", "")) or
            EMERGENCY_MAP.get(tags.get("emergency", "")) or
            BUILDING_MAP.get(tags.get("building", ""))
        )
        if not kategorija and tags.get("social_facility:for") in ("senior", "elderly"):
            kategorija = "Staracki dom"
        
        if kategorija:
            ime = tags.get("name") or tags.get("name:sl") or tags.get("name:en") or ""
            naslov = (tags.get("addr:street", "") + " " + tags.get("addr:housenumber", "")).strip()
            self.objects.append((kategorija, ime, naslov, lat, lon))

    def node(self, n):
        if n.location.valid(): self._process(n, n.location.lat, n.location.lon)

    def way(self, w):
        try:
            lats = [nd.location.lat for nd in w.nodes if nd.location.valid()]
            lons = [nd.location.lon for nd in w.nodes if nd.location.valid()]
            if lats: self._process(w, sum(lats)/len(lats), sum(lons)/len(lons))
        except: pass

def run_osm_etl():
    print(f"[{datetime.now()}] 🗺️ Pokrećem OSM ETL (ovo može potrajati)...")
    
    # 1. Download
    if not os.path.exists(PBF_FILE):
        print("Preuzimam .pbf fajl...")
        r = requests.get(PBF_URL, stream=True, timeout=300)
        with open(PBF_FILE, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024*1024): f.write(chunk)
    
    # 2. Parsiranje
    handler = OSMHandler()
    handler.apply_file(PBF_FILE, locations=True, idx='flex_mem')
    
    # 3. Upis u bazu
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("TRUNCATE TABLE kriticna_infrastruktura RESTART IDENTITY;")
    
    BATCH = 500
    total = len(handler.objects)
    for i in range(0, total, BATCH):
        batch = handler.objects[i:i+BATCH]
        cur.executemany("""
            INSERT INTO kriticna_infrastruktura (kategorija, ime, naslov, lat, lon)
            VALUES (%s, %s, %s, %s, %s)
        """, batch)
    
    conn.commit()
    cur.close()
    conn.close()
    print(f"🎉 OSM ETL gotov! Upisano {total} objekata.")