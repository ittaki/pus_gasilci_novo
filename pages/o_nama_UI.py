import streamlit as st
from etl.db_utils import get_db_connection

def render():
    st.header("👥 O projektu GOC")
    st.write("Sistem je razvijen kao projektni zadatak za unapređenje digitalizacije u vatrogasnim jedinicama (Gasilci) Slovenije.")
    st.info("Mentor: [Ime Mentora] | Autori: [Tvoje ime] & Luka")

if __name__ == "__main__": render()