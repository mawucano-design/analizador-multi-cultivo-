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
    SHConfig, SentinelHubRequest, DataCollection, BBox, CRS, Geometry,
    MimeType, bbox_to_dimensions, parse_time, Evalscript
)

# --- Configuración de página (primero) ---
st.set_page_config(page_title="Analizador Fertilidad Sentinel Hub + ESRI Satélite", layout="wide")

# --- Autenticación Sentinel Hub con Secrets ---
@st.cache_resource
def init_sentinel_hub():
    try:
        if "sentinel_hub" in st.secrets:
            config = SHConfig()
            config.sh_client_id = st.secrets["sentinel_hub"]["client_id"]
            config.sh_client_secret = st.secrets["sentinel_hub"]["client_secret"]
            st.success("Sentinel Hub autenticado")
            return config
        else:
            st.warning("No se encontraron secrets de Sentinel Hub. Usando simulación.")
            return None
    except Exception as e:
        st.error(f"Error Sentinel Hub: {e}")
        return None

config = init_sentinel_hub()

# --- Session State ---
if "map_key" not in st.session_state:
    st.session_state.map_key = 0
if "last_hash" not in st.session_state:
    st.session_state.last_hash = None

# --- Título ---
st.title("🌾 Analizador de Fertilidad con Sentinel Hub + Mapas ESRI Satélite")
st.markdown("**Reemplazo de GEE por Sentinel Hub**: Análisis N/P/K con Sentinel-2, recomendaciones por cultivo, 5 mapas interactivos en **ESRI World Imagery**.")

# --- Sidebar ---
cultivo = st.sidebar.selectbox("Cultivo:", ["Trigo", "Maíz", "Soja", "Sorgo", "Girasol"])

# --- Carga SHP / GeoJSON ---
st.header("Carga Polígono")
try:
    import fiona
    SHP_OK = True
except:
    SHP_OK = False
    st.warning("Fiona no disponible. Usa GeoJSON.")

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

# --- Análisis con Sentinel Hub (reemplaza GEE) ---
@st.cache_data
def analyze_nutrients_sentinel(geom, config):
    if not config:
        np.random.seed(42)
        return {'N': np.random.uniform(20, 80), 'P': np.random.uniform(10, 60), 'K': np.random.uniform(30, 90)}
    
    # Evalscript para proxies de nutrientes (NDVI ~ N, NDWI ~ P/K humedad)
    evalscript_ndvi = """
    //VERSION=3
    function setup() {
      return {
        input: ["B04", "B08", "dataMask"],
        output: { bands: 1, sampleType: "FLOAT32" }
      };
    }
    function evaluatePixel(sample) {
      let ndvi = (sample.B08 - sample.B04) / (sample.B08 + sample.B04);
      return [ndvi * 100];  // Escala para ppm-like
    }
    """
    evalscript_ndwi = """
    //VERSION=3
    function setup() {
      return {
        input: ["B03", "B08", "dataMask"],
        output: { bands: 1, sampleType: "FLOAT32" }
      };
    }
    function evaluatePixel(sample) {
      let ndwi = (sample.B03 - sample.B08) / (sample.B03 + sample.B08);
      return [ndwi * 100 + 50];  // Proxy para P/K
    }
    """
    
    # BBox y request (último mes, resolución 10m)
    bbox = BBox(bbox=geom.bounds, crs=CRS.WGS84)
    resolution = bbox_to_dimensions(bbox, resolution=10)
    time_interval = parse_time("2025-10-01", "2025-11-03")  # Ajusta fechas
    
    # Request NDVI (proxy N)
    request_ndvi = SentinelHubRequest(
        evalscript=evalscript_ndvi,
        input_data=[SentinelHubRequest.input_data(data_collection=DataCollection.SENTINEL2_L2A, time_interval=time_interval)],
        responses=[SentinelHubRequest.output_response('default', MimeType.TIFF)],
        bbox=bbox,
        size=resolution,
        config=config
    )
    ndvi_stats = request_ndvi.get_data_mean()  # Media
    
    # Request NDWI (proxy P/K)
    request_ndwi = SentinelHubRequest(
        evalscript=evalscript_ndwi,
        input_data=[SentinelHubRequest.input_data(data_collection=DataCollection.SENTINEL2_L2A, time_interval=time_interval)],
        responses=[SentinelHubRequest.output_response('default', MimeType.TIFF)],
        bbox=bbox,
        size=resolution,
        config=config
    )
    ndwi_stats = request_ndwi.get_data_mean()
    
    return {
        'N': abs(ndvi_stats[0][0]) if ndvi_stats.size > 0 else 50,  # NDVI como N
        'P': abs(ndwi_stats[0][0]) if ndwi_stats.size > 0 else 30,   # NDWI como P
        'K': abs(ndwi_stats[0][0] + 20) if ndwi_stats.size > 0 else 60  # Variación para K
    }

nutrients = analyze_nutrients_sentinel(geoms[0], config)  # Usa primer polígono
N, P, K = nutrients['N'], nutrients['P'], nutrients['K']

# --- Recomendaciones (del repo original) ---
def get_recs(cultivo, N, P, K):
    base = {
        "Trigo":    (140, 70, 90),
        "Maíz":     (200, 80, 110),
        "Soja":     (30, 50, 70),
        "Sorgo":    (150, 70, 100),
        "Girasol":  (90, 80, 80)
    }
    n_req, p_req, k_req = base.get(cultivo, (100, 60, 80))
    return max(0, n_req - N), max(0, p_req - P), max(0, k_req - K)

rec_N, rec_P, rec_K = get_recs(cultivo, N, P, K)

cols = st.columns(3)
cols[0].metric("N (NDVI proxy)", f"{N:.1f}", f"+{rec_N:.0f} kg/ha")
cols[1].metric("P (NDWI proxy)", f"{P:.1f}", f"+{rec_P:.0f} kg/ha")
cols[2].metric("K (NDWI proxy)", f"{K:.1f}", f"+{rec_K:.0f} kg/ha")

df_result = pd.DataFrame({
    "Nutriente": ["N", "P", "K"],
    "Actual (proxy)": [N, P, K],
    "Recomendación (kg/ha)": [rec_N, rec_P, rec_K]
})
st.table(df_result)

# --- Función para mapas ESRI Satélite ---
def make_map(title, value=None, legend="", color='blue'):
    st.subheader(title)
    center = geoms[0].centroid
    m = folium.Map(location=[center.y, center.x], zoom_start=15, tiles=None)
    
    # Base ESRI Satélite
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Esri', name='Satélite', overlay=False
    ).add_to(m)
    
    # Polígono con color por valor
    for g in geoms:
        folium.GeoJson(g.__geo_interface__, style_function=lambda x: {
            'fillColor': color,
            'color': 'black',
            'weight': 3,
            'fillOpacity': 0.5
        }).add_to(m)
    
    if value is not None:
        folium.Marker(
            [center.y, center.x],
            popup=f"{legend}: {value:.1f}",
            icon=folium.Icon(color="red")
        ).add_to(m)
    
    folium.LayerControl().add_to(m)
    folium_static(m, width=700, height=400, key=f"{title}_{st.session_state.map_key}")

# --- 5 Mapas ---
make_map("1. Polígono Base (ESRI Satélite)")
make_map("2. Nitrógeno (N)", N, "N proxy", "green")
make_map("3. Fósforo (P)", P, "P proxy", "orange")
make_map("4. Potasio (K)", K, "K proxy", "purple")
make_map("5. Recomendación Total (N+P+K)", rec_N + rec_P + rec_K, "kg/ha total", "red")

# --- Footer ---
st.markdown("---")
st.caption("Sentinel Hub + Sentinel-2 para análisis real | Evalscripts para proxies NDVI/NDWI | ESRI Satélite multi-mapas")
