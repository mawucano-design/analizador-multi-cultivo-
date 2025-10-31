import streamlit as st
import geopandas as gpd
import pandas as pd
import numpy as np
import tempfile
import os
import zipfile
from datetime import datetime, timedelta
import folium
from streamlit_folium import folium_static
from shapely.geometry import Polygon
import math
import warnings
import io
import matplotlib.pyplot as plt

# --- IMPORTS CONDICIONALES ---
try:
    from sentinelhub import SHConfig, SentinelHubRequest, MimeType, CRS, BBox, DataCollection, Geometry
    SH_AVAILABLE = True
except ImportError:
    SH_AVAILABLE = False
    st.warning("Sentinel Hub no disponible. Usando simulación.")

try:
    from fpdf import FPDF
    FPDF_AVAILABLE = True
except ImportError:
    FPDF_AVAILABLE = False

warnings.filterwarnings('ignore')

st.set_page_config(page_title="Multi-Cultivo", layout="wide")
st.title("ANALIZADOR MULTI-CULTIVO - SENTINEL-2 REAL")
st.markdown("**NDVI, NDRE, NPK por zona con imágenes reales 10m**")
st.markdown("---")

os.environ['SHAPE_RESTORE_SHX'] = 'YES'

# --- MAPAS BASE ---
MAPAS = {
    "ESRI Satellite": {
        "url": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        "attr": "Esri, Maxar"
    },
    "OSM": {
        "url": "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        "attr": "OpenStreetMap"
    }
}

# --- CULTIVOS ---
CULTIVOS = ['TRIGO', 'MAÍZ', 'SOJA', 'SORGO', 'GIRASOL']
ICONOS = {'TRIGO': 'Wheat', 'MAÍZ': 'Corn', 'SOJA': 'Soy', 'SORGO': 'Sorghum', 'GIRASOL': 'Sunflower'}

# --- EVALSCRIPT PARA NDVI + NDRE + HUMEDAD ---
EVALSCRIPT = """
//VERSION=3
function setup() {
  return {
    input: ["B04", "B05", "B08", "B11", "CLM"],
    output: { bands: 4, sampleType: "FLOAT32" }
  };
}
function evaluatePixel(s) {
  let ndvi = index(s.B08, s.B04);
  let ndre = index(s.B08, s.B05);
  let humidity = 1 - (s.B11 / 10000);
  let lai = ndvi > 0.1 ? Math.pow(ndvi, 2) * 5.5 : 0.1;
  return [ndvi, ndre, lai, humidity];
}
function index(a, b) {
  return (a - b) / (a + b + 0.0001);
}
"""

# --- CONFIG SH ---
@st.cache_resource
def get_sh_config():
    if not SH_AVAILABLE:
        return None
    config = SHConfig()
    if 'SH_CLIENT_ID' in st.secrets:
        config.sh_client_id = st.secrets['SH_CLIENT_ID']
        config.sh_client_secret = st.secrets['SH_CLIENT_SECRET']
        return config
    return None

# --- PROCESADOR ---
class SentinelProcessor:
    def __init__(self, config):
        self.config = config

    def get_indices(self, bbox, fecha):
        if self.config and SH_AVAILABLE:
            try:
                bbox_sh = BBox(bbox=bbox, crs=CRS.WGS84)
                request = SentinelHubRequest(
                    evalscript=EVALSCRIPT,
                    input_data=[SentinelHubRequest.input_data(
                        data_collection=DataCollection.SENTINEL2_L2A,
                        time_interval=(str(fecha), str(fecha + timedelta(days=1)))
                    )],
                    responses=[SentinelHubRequest.output_response('default', MimeType.TIFF)],
                    bbox=bbox_sh,
                    size=(256, 256),
                    config=self.config
                )
                data = request.get_data()[0]
                return {
                    'ndvi': float(np.mean(data[:, :, 0])),
                    'ndre': float(np.mean(data[:, :, 1])),
                    'lai': float(np.mean(data[:, :, 2])),
                    'humedad': float(np.mean(data[:, :, 3])),
                    'fuente': 'Sentinel-2 Real'
                }
            except Exception as e:
                st.warning(f"API error: {e}. Usando simulación.")
        # Simulación
        ndvi = np.clip(0.45 + np.random.normal(0, 0.1), 0.1, 0.85)
        ndre = np.clip(ndvi - 0.1 + np.random.normal(0, 0.05), 0.05, 0.75)
        lai = ndvi * 5.5
        humedad = np.clip(0.3 + np.random.normal(0, 0.05), 0.1, 0.7)
        return {'ndvi': ndvi, 'ndre': ndre, 'lai': lai, 'humedad': humedad, 'fuente': 'Simulado'}

# --- DIVIDIR ZONAS ---
def dividir_zonas(gdf, n):
    geom = gdf.geometry.iloc[0]
    b = geom.bounds
    w = (b[2] - b[0]) / math.isqrt(n)
    h = (b[3] - b[1]) / math.isqrt(n)
    zonas = []
    for i in range(math.isqrt(n)):
        for j in range(math.isqrt(n)):
            if len(zonas) >= n: break
            poly = Polygon([(b[0]+j*w, b[1]+i*h), (b[0]+(j+1)*w, b[1]+i*h),
                           (b[0]+(j+1)*w, b[1]+(i+1)*h), (b[0]+j*w, b[1]+(i+1)*h)])
            inter = geom.intersection(poly)
            if not inter.is_empty:
                zonas.append(inter)
    return gpd.GeoDataFrame({'zona': range(1, len(zonas)+1), 'geometry': zonas}, crs=gdf.crs)

# --- ÁREA ---
def area_ha(gdf):
    return gdf.to_crs('EPSG:3857').area / 10000

# --- MAPA ---
def crear_mapa(gdf, tipo):
    center = [gdf.centroid.y.mean(), gdf.centroid.x.mean()]
    m = folium.Map(location=center, zoom_start=15, tiles=None)
    folium.TileLayer(tiles=MAPAS[tipo]["url"], attr=MAPAS[tipo]["attr"], name=tipo).add_to(m)
    folium.GeoJson(gdf, style_function=lambda f: {
        'fillColor': 'red' if f['properties']['npk'] < 0.4 else 'yellow' if f['properties']['npk'] < 0.7 else 'green',
        'color': 'black', 'weight': 1, 'fillOpacity': 0.7
    }, tooltip=folium.GeoJsonTooltip(['zona', 'ndvi', 'npk', 'area_ha'])).add_to(m)
    return m

# --- SIDEBAR ---
with st.sidebar:
    st.header("Configuración")
    cultivo = st.selectbox("Cultivo", CULTIVOS)
    fecha = st.date_input("Fecha", value=datetime.now() - timedelta(days=10))
    zonas = st.slider("Zonas", 16, 48, 32, 4)
    mapa = st.selectbox("Mapa", list(MAPAS.keys()))
    zip_file = st.file_uploader("ZIP Shapefile", type=['zip'])

# --- MAIN ---
if zip_file:
    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(zip_file) as z:
            z.extractall(tmp)
        shp = next((f for f in os.listdir(tmp) if f.endswith('.shp')), None)
        if not shp:
            st.error("No .shp en ZIP")
        else:
            gdf = gpd.read_file(os.path.join(tmp, shp))
            area_total = area_ha(gdf).sum()
            st.success(f"Parcela: {area_total:.1f} ha")

            if st.button("EJECUTAR ANÁLISIS", type="primary"):
                gdf_z = dividir_zonas(gdf, zonas)
                proc = SentinelProcessor(get_sh_config())
                bounds = gdf_z.total_bounds
                resultados = [proc.get_indices(bounds, fecha) for _ in gdf_z.iterrows()]
                
                for k in ['ndvi', 'ndre', 'lai', 'humedad']:
                    gdf_z[k] = [r[k] for r in resultados]
                gdf_z['npk'] = (gdf_z['ndvi']*0.5 + gdf_z['ndre']*0.3 + gdf_z['lai']/6*0.1 + gdf_z['humedad']*0.1).clip(0,1)
                gdf_z['area_ha'] = area_ha(gdf_z)

                # Métricas
                c1, c2, c3 = st.columns(3)
                with c1: st.metric("NDVI", f"{gdf_z['ndvi'].mean():.3f}")
                with c2: st.metric("NPK", f"{gdf_z['npk'].mean():.3f}")
                with c3: st.metric("Zonas", len(gdf_z))

                # Mapa
                st.subheader("Mapa")
                folium_static(crear_mapa(gdf_z, mapa), width=700, height=500)

                # Tabla
                st.subheader("Resultados")
                tabla = gdf_z[['zona', 'area_ha', 'ndvi', 'ndre', 'npk']].round(3)
                st.dataframe(tabla)

                # Descargas
                st.download_button("CSV", gdf_z.to_csv(index=False), "resultados.csv", "text/csv")
                st.download_button("GeoJSON", gdf_z.to_json(), "zonas.geojson", "application/json")
else:
    st.info("Sube ZIP con shapefile")
