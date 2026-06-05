import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()
DB_URL = os.getenv("DB_URL")

def get_db_connection():
    conn = psycopg2.connect(
        DB_URL,
        connect_timeout=30, # Povećaj na 30 sekundi
        keepalives=1,
        keepalives_idle=30,
        keepalives_interval=10,
        keepalives_count=5
    )
    # Postavi timeout za sam upit da se ne prekida tokom obrade
    with conn.cursor() as cur:
        cur.execute("SET statement_timeout = '60s';")
    return conn