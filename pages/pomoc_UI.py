import streamlit as st
from etl.db_utils import get_db_connection

def render():
    st.header("ℹ️ Pomoć i Operativni Protokoli")
    st.write("Ovde komandiri mogu pronaći standardne operativne procedure (SOP) u slučaju crvenog meteo-alarma ili zemljotresa.")
    st.markdown("""
        1. **Požar:** Ako FRP pređe 50MW, obavestiti regionalni centar.
        2. **Poplava:** Pratiti ARSO stanice sa nivoom iznad 300cm.
        3. **Potres:** Magnitude iznad 4.0 zahtevaju automatski izlazak na proveru mostova.
    """)

if __name__ == "__main__": render()