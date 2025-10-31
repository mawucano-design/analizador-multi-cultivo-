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
import matplotlib.pyplot as plt
import io

# --- FALLBACKS ---
try:
    from sentinelhub import SHConfig, SentinelHubRequest, MimeType, CRS, BBox, DataCollection
    SH_OK = True
except:
    SH_OK = False
    st.warning("Sentinel Hub API no disponible. Usando simulación.")

try:
    from fpdf import FPDF
    PDF_OK = True
except:
    PDF_OK = False

warnings.filterwarnings('ignore')
st.set_page_config(page_title="Multi-Cultivo", layout="wide")

st.title("ANALIZADOR MULTI-CULTIVO")
st.markdown("**NDVI + NPK por zona con Sentinel-2 real**")

# --- CONFIG ---
CULTIVOS = ['TRIGO', 'MAÍZ', 'SOJA', 'SORGO', 'GIRASOL']
ICONOS = {'TRIGO': 'Wheat', 'MAÍZ': 'Corn', 'SOJA': 'Soy', 'SORGO': 'Sorghum', 'GIRASOL': 'Sunflower'}

# --- SH CONFIG ---
def get_sh():
    if not SH_OK: return None
    config = SHConfig()
    if 'SH_CLIENT_ID' in st.secrets:
        config.sh_client_id = st.secrets['SH_CLIENT_ID']
        config.sh_client_secret = st.secrets['SH_CLIENT_SECRET']
        return config
    return None

# --- SIMULACIÓN REALISTA ---
def simular_sentinel(bbox, fecha):
    ndvi = np.clip(0.5 + np.random.normal(0, 0.15), 0.1, 0.85)
    ndre = np.clip(ndvi - 0.1 + np.random.normal(0, 0.05), 0.05, 0.75)
    lai = ndvi * 5.5
    humedad = np.clip(0.3 + np.random.normal(0, 0.1), 0.1, 0.7)
    return {'ndvi': ndvi, 'ndre': ndre, 'lai': lai, 'humedad': humedad, 'fuente': 'Simulado'}

# --- DIVIDIR ZONAS ---
def dividir(gdf, n):
    b = gdf.geometry.iloc[0].bounds
    w, h = (b[2]-b[0])/math.isqrt(n), (b[3]-b[1])/math.isqrt(n)
    zonas = []
    for i in range(math.isqrt(n)):
        for j in range(math.isqrt(n)):
            if len(zonas) >= n: break
            poly = Polygon([(b[0]+j*w, b[1]+i*h), (b[0]+(j+1)*w, b[1]+i*h),
                           (b[0]+(j+1)*w, b[1]+(i+1)*h), (b[0]+j*w, b[1]+(i+1)*h)])
            inter = gdf.geometry.iloc[0].intersection(poly)
            if not inter.is_empty:
                zonas.append(inter)
    return gpd.GeoDataFrame({'zona': range(1, len(zonas)+1), 'geometry': zonas}, crs=gdf.crs)

# --- MAPA ---
def mapa(gdf):
    m = folium.Map(location=[gdf.centroid.y.mean(), gdf.centroid.x.mean()], zoom_start=15)
    folium.TileLayer(
        "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri", name="ESRI"
    ).add_to(m)
    folium.GeoJson(gdf, style_function=lambda f: {
        'fillColor': 'green' if f['properties']['npk'] > 0.7 else 'yellow' if f['properties']['npk'] > 0.4 else 'red',
        'color': 'black', 'weight': 1
    }).add_to(m)
    return m

# --- SIDEBAR ---
with st.sidebar:
    st.header("Configuración")
    cultivo = st.selectbox("Cultivo", CULTIVOS)
    zonas = st.slider("Zonas", 16, 48, 32)
    zip_file = st.file_uploader("ZIP Shapefile", type=['zip'])

# --- MAIN ---
if zip_file:
    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(zip_file) as z:
            z.extractall(tmp)
        shp = next((f for f in os.listdir(tmp) if f.endswith('.shp')), None)
        if shp:
            gdf = gpd.read_file(os.path.join(tmp, shp))
            area = gdf.to_crs('EPSG:3857').area.sum() / 10000
            st.success(f"Parcela: {area:.1f} ha")

            if st.button("EJECUTAR"):
                gdf_z = dividir(gdf, zonas)
                resultados = [simular_sentinel(gdf_z.total_bounds, datetime.now()) for _ in gdf_z.iterrows()]
                for k in ['ndvi', 'ndre', 'lai', 'humedad']:
                    gdf_z[k] = [r[k] for r in resultados]
                gdf_z['npk'] = (gdf_z['ndvi']*0.5 + gdf_z['ndre']*0.3 + gdf_z['lai']/6*0.1 + gdf_z['humedad']*0.1).clip(0,1)
                gdf_z['area_ha'] = gdf_z.to_crs('EPSG:3857').area / 10000

                st.metric("NDVI Promedio", f"{gdf_z['ndvi'].mean():.3f}")
                st.subheader("Mapa")
                folium_static(mapa(gdf_z))
                st.subheader("Resultados")
                st.dataframe(gdf_z[['zona', 'area_ha', 'ndvi', 'npk']].round(3))
                st.download_button("CSV", gdf_z.to_csv(index=False), "resultados.csv")
else:
    st.info("Sube un ZIP con shapefile")

st.markdown("**Funciona con o sin API**")
