import time
from etl.etl_floods import run_floods_etl
from etl.etl_weather import run_weather_etl
from etl.etl_rivers import run_rivers_etl
from etl.etl_drought import run_drought_etl
from etl.etl_fires import run_fires_etl
from etl.etl_earthquake import run_quakes_etl
from etl.etl_osm import run_osm_etl
from etl.etl_promet import run_promet_etl
from etl.etl_air_quality import run_air_quality_etl
from etl.etl_wather_forecast import run_weather_forecast_etl


def main():
    while True:
        print("--- CIKLUS POČINJE ---")
        run_weather_etl()
        time.sleep(2)
        run_rivers_etl()
        time.sleep(2)
        run_floods_etl()
        time.sleep(2)
        run_drought_etl()
        time.sleep(2)
        run_fires_etl()
        time.sleep(2)
        run_quakes_etl()
        time.sleep(2)
        run_weather_forecast_etl() 
        time.sleep(2)
        run_air_quality_etl()   
        time.sleep(2)
        #run_osm_etl()
        run_promet_etl()
        time.sleep(2)
        print("--- CIKLUS ZAVRŠEN. ČEKAM 15 MINUTA ---")
        time.sleep(900)

if __name__ == "__main__":
    main()