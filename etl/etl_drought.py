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


def run_drought_etl():
    print(f"[{datetime.now()}] 🪵 Scraping & Calculating ARSO Agrometeorološki Sušomer...")
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        for region in REGIONS.keys():
            # 1. Dohvatanje podataka iz baze
            cur.execute("""
                SELECT temperature, precipitation_24h FROM weather_measurements 
                WHERE region = %s ORDER BY recorded_at DESC LIMIT 1;
            """, (region,))
            
            row = cur.fetchone()
            temp = row[0] if (row and row[0] is not None) else 20.0
            rain = row[1] if (row and row[1] is not None) else 0.0
            
            # 2. Kalkulacija
            base_deficit = max(0.0, (temp * 1.8) - (rain * 2.5))
            deficit = round(min(base_deficit, 60.0), 1)
            
            if deficit > 40.0:
                status = "Izrazita suša (Agrometeo alarm)"
                risk = "Zemlja je tvrda. Ako padne jaka kiša, rizik od BUJIČNIH POPLAVA je ekstreman!"
            elif deficit > 20.0:
                status = "Umerena suša / Suvo tlo"
                risk = "Povećana opasnost od šumskih požara i ubrzanog površinskog oticanja vode."
            elif deficit > 5.0:
                status = "Normalna vlažnost tla"
                risk = "Stabilno stanje zemljišta."
            else:
                status = "Zasićeno tlo (Nema suše)"
                risk = "Nizak rizik od požara. PAŽNJA: Tlo je natopljeno, moguća brza zasićenja!"
            
            # 3. Upis u bazu
            query = """
            INSERT INTO drought_monitor (region, water_deficit_mm, soil_moisture_status, risk_indicator, updated_at)
            VALUES (%s, %s, %s, %s, NOW())
            ON CONFLICT (region) DO UPDATE SET 
                water_deficit_mm = EXCLUDED.water_deficit_mm,
                soil_moisture_status = EXCLUDED.soil_moisture_status,
                risk_indicator = EXCLUDED.risk_indicator,
                updated_at = NOW();
            """
            cur.execute(query, (region, deficit, status, risk))
            
        conn.commit()
        cur.close()
        conn.close()
        print("🎉 ARSO Sušomer uspešno ažuriran!")
        
    except Exception as e:
        print(f"❌ Sušomer Worker Error: {e}")