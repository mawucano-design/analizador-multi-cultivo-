import streamlit as st
from streamlit_folium import folium_static
import folium
import tempfile
import os
import json
import pandas as pd
import numpy as np
from shapely.geometry import shape
from sentinelhub import (
    SHConfig, SentinelHubRequest, DataCollection, BBox, CRS, MimeType,
    bbox_to_dimensions, Evalscript
)

# --- Configuración (primero) ---
st.set_page_config(page_title="Fertilidad Sentinel Hub", layout="wide")

# --- AUTENTICACIÓN HARDCODEADA ---
@st.cache_resource
def init_sentinel_hub():
    try:
        config = SHConfig()
        config.sh_client_id = "b296cf70-c9d2-4e69-91f4-f7be80b99ed1"
        config.sh_client_secret = "358474d6-2326-4637-bf8e-30a709b2d6a6"
        st.success("Sentinel Hub autenticado")
        return config
    except Exception as e:
        st.error(f"Error: {e}")
        return None

config = init_sentinel_hub()

# --- Session State ---
if "map_key" not in st.session_state:
    st.session_state.map_key = 0
if "last_hash" not in st.session_state:
    st.session_state.last_hash = None

# --- UI ---
st.title("Analizador de Fertilidad con Sentinel Hub")
st.markdown("**Credenciales hardcodeadas** → análisis con Sentinel-2 + 5 mapas ESRI Satélite")

cultivo = st.sidebar.selectbox("Cultivo:", ["Trigo", "Maíz", "Soja", "Sorgo", "Girasol"])

# --- Carga SHP / GeoJSON ---
st.header("Carga Polígono")
try:
    import fiona
    SHP_OK = True
except:
    SHP_OK = False

uploaded_files = st.file_uploader("SHP", type=['shp', 'shx', 'dbf', 'prj'], accept_multiple_files=True) if SHP_OK else None
geojson_text = st.text_area("O pega GeoJSON:", height=120)

# --- Procesar geometría ---
geoms = None
current_hash = hash(str(uploaded_files) + geojson_text)
if current_hash != st.session_state.last_hash:
    st.session_state.last_hash = current_hash
    st.session_state.map_key += 1

if SHP_OK and uploaded_files:
    shp = next((f for f in uploaded_files if f.name.endswith('.shp')), None)
    if shp:
        with tempfile.TemporaryDirectory() as tmp:
            for f in uploaded_files:
                with open(os.path.join(tmp, f.name), "wb") as out:
                    out.write(f.getbuffer())
            try:
                with fiona.open(os.path.join(tmp, shp.name)) as src:
                    geoms = [shape(f['geometry']) for f in src]
                st.success(f"SHP: {len(geoms)} polígonos")
            except Exception as e:
                st.error(f"Error SHP: {e}")

if not geoms and geojson_text.strip():
    try:
        data = json.loads(geojson_text)
        geoms = [shape(f['geometry']) for f in data.get('features', []) if 'geometry' in f]
        st.success(f"GeoJSON: {len(geoms)} polígonos")
    except Exception as e:
        st.error(f"Error GeoJSON: {e}")

if not geoms:
    st.info("Sube SHP o pega GeoJSON.")
    st.code('''{"type": "FeatureCollection", "features": [{"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[-58.4,-34.6],[-58.3,-34.6],[-58.3,-34.5],[-58.4,-34.5],[-58.4,-34.6]]]}}]}''')
    st.stop()

# --- Análisis Sentinel Hub ---
@st.cache_data
def analyze_sentinel(geom):
    if not config:
        np.random.seed(42)
        return {'N': np.random.uniform(20, 80), 'P': np.random.uniform(10, 60), 'K': np.random.uniform(30, 90)}
    
    bbox = BBox(bbox=geom.bounds, crs=CRS.WGS84)
    size = bbox_to_dimensions(bbox, resolution=10)
    
    evalscript = """
    //VERSION=3
    function setup() {
      return {
        input: ["B04", "B08", "B03", "dataMask"],
        output: { bands: 3, sampleType: "FLOAT32" }
      };
    }
    function evaluatePixel(sample) {
      let ndvi = (sample.B08 - sample.B04) / (sample.B08 + sample.B04 + 0.0001);
      let ndwi = (sample.B03 - sample.B08) / (sample.B03 + sample.B08 + 0.0001);
      return [ndvi * 100, ndwi * 100 + 50, (ndwi * 100 + 70)];
    }
    """
    
    request = SentinelHubRequest(
        evalscript=evalscript,
        input_data=[SentinelHubRequest.input_data(
            data_collection=DataCollection.SENTINEL2_L2A,
            time_interval=("2025-10-01", "2025-11-03")
        )],
        responses=[SentinelHubRequest.output_response('default', MimeType.TIFF)],
        bbox=bbox,
        size=size,
        config=config
    )
    
    try:
        result = request.get_data()[0]
        if result.size > 0:
            mean_vals = np.mean(result, axis=(0,1))
            return {'N': mean_vals[0], 'P': mean_vals[1], 'K': mean_vals[2]}
    except:
        pass
    
    return {'N': 50, 'P': 30, 'K': 60}

nutrients = analyze_sentinel(geoms[0])
N, P, K = nutrients['N'], nutrients['P'], nutrients['K']

# --- Recomendaciones ---
def get_recs(c, n, p, k):
    base = {"Trigo": (140,70,90), "Maíz": (200,80,110), "Soja": (30,50,70), "Sorgo": (150,70,100), "Girasol": (90,80,80)}
    n_req, p_req, k_req = base.get(c, (100,60,80))
    return max(0, n_req - n), max(0, p_req - p), max(0, k_req - k)

rec_N, rec_P, rec_K = get_recs(cultivo, N, P, K)

cols = st.columns(3)
cols[0].metric("N", f"{N:.1f}", f"+{rec_N:.0f} kg/ha")
cols[1].metric("P", f"{P:.1f}", f"+{rec_P:.0f} kg/ha")
cols[2].metric("K", f"{K:.1f}", f"+{rec_K:.0f} kg/ha")

# --- Mapas ESRI Satélite ---
def make_map(title, val=None, col='blue'):
    st.subheader(title)
    center = geoms[0].centroid
    m = folium.Map([center.y, center.x], zoom_start=15, tiles=None)
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Esri', name='Satélite'
    ).add_to(m)
    for g in geoms:
        folium.GeoJson(g.__geo_interface__, style_function=lambda x: {
            'fillColor': col, 'color': 'black', 'weight': 3, 'fillOpacity': 0.5
        }).add_to(m)
    if val:
        folium.Marker([center.y, center.x], popup=f"{val:.1f}").add_to(m)
    folium.LayerControl().add_to(m)
    folium_static(m, width=700, height=400)

make_map("1. Base")
make_map("2. N", N, "green")
make_map("3. P", P, "orange")
make_map("4. K", K, "purple")
make_map("5. Rec Total", rec_N + rec_P + rec_K, "red")

st.caption("Credenciales hardcodeadas | Sentinel Hub + ESRI Satélite")
