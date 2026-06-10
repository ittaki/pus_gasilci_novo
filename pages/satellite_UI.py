import streamlit as st
import folium
import os
from folium import plugins
from streamlit_folium import st_folium
from dotenv import load_dotenv

from sentinelhub import (
    SentinelHubRequest,
    SentinelHubCatalog,
    BBox,
    CRS,
    MimeType,
    SHConfig
)

from datetime import datetime, timedelta
import pandas as pd

# =====================================================
# CONFIG
# =====================================================

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")

load_dotenv()

# =====================================================
# EVALSCRIPTS
# =====================================================
RGB_SCRIPT = """

function setup() {
    return {
        input: ["B04", "B03", "B02"],
        output: { bands: 3 }
    };
}

function evaluatePixel(sample) {
    return [2.5 * sample.B04, 2.5 * sample.B03, 2.5 * sample.B02];
}

"""

FIRE_SCRIPT = """

function setup() {
    return {
        input: ["B12", "B08", "B04"],
        output: { bands: 3 }
    };
}

function evaluatePixel(sample) {
    return [2.5 * sample.B12, 2.5 * sample.B08, 2.5 * sample.B04];
}

"""
# =====================================================
# SH CONFIG
# =====================================================
def get_config():
    config = SHConfig()
    config.sh_client_id = CLIENT_ID
    config.sh_client_secret = CLIENT_SECRET
    return config

config = get_config()


# =====================================================
# SEARCH SCENES
# =====================================================
def search_scenes(bbox, cloud_filter=None):
    catalog = SentinelHubCatalog(config=config)

    params = {
        "collection": "sentinel-2-l2a",
        "bbox": bbox,
        "time": ("2024-01-01", "2030-01-01"),
        "fields": {
            "include": ["properties.datetime", "properties.eo:cloud_cover"]
        }
    }

    if cloud_filter:
        params["filter"] = cloud_filter

    results = list(catalog.search(**params))

    if not results:
        return []

    results.sort(key=lambda x: x["properties"]["datetime"], reverse=True)
    return results

# =====================================================
# IMAGE REQUEST
# =====================================================
def get_image(bbox, dt_str, script):
    dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))

    from_time = (dt - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    to_time = (dt + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")

    request = SentinelHubRequest(
        evalscript=script,
        input_data=[{
            "type": "sentinel-2-l2a",
            "dataFilter": {
                "timeRange": {
                    "from": from_time,
                    "to": to_time

                }

            }

        }],

        responses=[
            SentinelHubRequest.output_response("default", MimeType.PNG)

        ],
        bbox=bbox,
        size=[1024, 1024],
        config=config

    )

    data = request.get_data()
    return data[0] if data else None

# ====================================================
# SCENE BUILDER
# =====================================================
def build_scene(bbox, scene):
    if not scene:
        return None

    dt = scene["properties"]["datetime"]
    cloud = scene["properties"].get("eo:cloud_cover")

    return {
        "datetime": dt,
        "cloud": cloud,
        "rgb": get_image(bbox, dt, RGB_SCRIPT),
        "fire": get_image(bbox, dt, FIRE_SCRIPT)
    }

# =====================================================
# STREAMLIT APP
# =====================================================
def render():
    
    st.title("🛰️ Sentinel-2 Fire Monitoring")

    # =================================================
    # SESSION STATE
    # =================================================
    if "aoi" not in st.session_state:
        st.session_state.aoi = None

    if "aoi_hash" not in st.session_state:
        st.session_state.aoi_hash = None

    if "run" not in st.session_state:
        st.session_state.run = False

    # =================================================
    # MAP
    # =================================================
    st.subheader("📍 Draw AOI (rectangle)")

    m = folium.Map(location=[44.8, 20.4], zoom_start=7)

    draw = plugins.Draw(
        draw_options={
            "rectangle": True,
            "polygon": False,
            "circle": False,
            "polyline": False,
            "marker": False
        }
    )

    draw.add_to(m)

    map_data = st_folium(
        m,
        height=500,
        width=None,
        key="map",
        returned_objects=["all_drawings"]
    )

    # =================================================
    # FIX: USE LAST DRAWN RECTANGLE ONLY
    # =================================================
    drawings = map_data.get("all_drawings") if map_data else None

    if drawings and len(drawings) > 0:
        # take LAST rectangle, not first
        coords = drawings[-1]["geometry"]["coordinates"][0]

        new_aoi = [
            min(p[0] for p in coords),
            min(p[1] for p in coords),
            max(p[0] for p in coords),
            max(p[1] for p in coords)
        ]

        new_hash = str(new_aoi)

        if st.session_state.aoi_hash != new_hash:
            st.session_state.aoi = new_aoi
            st.session_state.aoi_hash = new_hash
            st.session_state.run = False
            st.info("AOI updated. Click 'Load satellite data'")

    # =================================================
    # HANDLE DELETE (TRASHCAN)
    # =================================================
    if not drawings or len(drawings) == 0:
        st.session_state.aoi = None
        st.session_state.aoi_hash = None
        st.session_state.run = False

    # =================================================
    # BUTTONS
    # =================================================

    if st.session_state.aoi:
        if st.button("🛰️ Load satellite data"):
            st.session_state.run = True
            st.rerun()


    if st.button("🔄 Reset AOI"):
        st.session_state.aoi = None
        st.session_state.aoi_hash = None
        st.session_state.run = False
        st.rerun()

    # =================================================
    # BLOCK UNTIL USER CLICK
    # =================================================
    if not st.session_state.run:
        st.info("Draw AOI → click Load satellite data")
        st.stop()


    # =================================================
    # LOAD DATA ONLY ON BUTTON
    # =================================================
    bbox = BBox(st.session_state.aoi, CRS.WGS84)

    usable_scenes = search_scenes(bbox, cloud_filter="eo:cloud_cover < 20")
    raw_scenes = search_scenes(bbox)

    usable_scene = usable_scenes[0] if usable_scenes else None
    raw_scene = raw_scenes[0]

    with st.spinner("Loading satellite data..."):
        usable = build_scene(bbox, usable_scene)
        raw = build_scene(bbox, raw_scene)

    # =================================================
    # TABLE
    # =================================================

    st.subheader("📊 Latest RAW scenes")

    df = pd.DataFrame([
        {
            "datetime": s["properties"]["datetime"],
            "cloud": s["properties"].get("eo:cloud_cover")
        }

        for s in raw_scenes[:10]

    ])

    st.dataframe(df)

    # =================================================
    # DISPLAY
    # ================================================

    col1, col2 = st.columns(2)
    col3, col4 = st.columns(2)

    with col1:
        st.subheader("✅ Usable RGB")

        if usable:
            st.image(usable["rgb"], width=None)
            st.caption(f"{usable['datetime']} | cloud {usable['cloud']}")

    with col2:
        st.subheader("🔥 Usable FIRE")
        if usable:
            st.image(usable["fire"], width=None)
            st.caption(f"{usable['datetime']} | cloud {usable['cloud']}")

    with col3:
        st.subheader("☁️ RAW RGB")
        st.image(raw["rgb"], width=None)
        st.caption(f"{raw['datetime']} | cloud {raw['cloud']}")

    with col4:
        st.subheader("🔥 RAW FIRE")

        if raw:
            st.image(raw["fire"], width=None)
            st.caption(f"{raw['datetime']} | cloud {raw['cloud']}")
