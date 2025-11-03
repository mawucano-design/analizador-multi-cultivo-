import streamlit as st
from streamlit_folium import st_folium  # <-- NUEVA FORMA
import geopandas as gpd
import folium
import tempfile
import os
import pandas as pd
import numpy as np

# --- Configuración ---
st.set_page_config(
    page_title="Fertilidad + ESRI Map",
    page_icon="🌾",
    layout="wide"
)

# Cache para evitar re-render del mapa
@st.cache_data(show_spinner=False)
def load_shapefile(uploaded_files):
    if not uploaded_files:
        return None

    shp_file = None
    for f in uploaded_files:
        if f.name.lower().endswith('.shp'):
            shp_file = f
            break
    if not shp_file:
        return None

    with tempfile.TemporaryDirectory() as tmpdir:
        file_paths = {}
        for f in uploaded_files:
            path = os.path.join(tmpdir, f.name)
            with open(path, "wb") as buffer:
                buffer.write(f.getbuffer())
            file_paths[f.name.lower()] = path

        shp_path = file_paths[shp_file.name.lower()]
        try:
            gdf = gpd.read_file(shp_path)
            if gdf.empty:
                return None
            return gdf
        except Exception as e:
            st.error(f"Error leyendo SHP: {e}")
            return None

# --- Título ---
st.title("🌾 Analizador de Fertilidad + Mapa ESRI")
st.markdown("Carga un **SHP** → Análisis de N, P, K → Mapa interactivo con **ESRI World Street Map**")

# --- Sidebar ---
cultivo = st.sidebar.selectbox("Cultivo:", ["Trigo", "Maíz", "Soja", "Sorgo", "Girasol"])

# --- Carga de archivos ---
uploaded_files = st.file_uploader(
    "Sube archivos SHP (.shp, .shx, .dbf, .prj...)",
    type=['shp', 'shx', 'dbf', 'prj', 'cpg', 'qpj'],
    accept_multiple_files=True,
    key="shp_uploader"
)

# --- Procesar SHP ---
gdf = load_shapefile(uploaded_files)

if gdf is not None:
    st.success(f"Polígono cargado: {len(gdf)} feature(s)")

    # Área en hectáreas
    area_ha = gdf.to_crs(epsg=3857).geometry.area.sum() / 10000
    col1, col2 = st.columns(2)
    col1.metric("Polígonos", len(gdf))
    col2.metric("Área", f"{area_ha:,.2f} ha")

    # --- Análisis simulado (REEMPLAZA CON GEE) ---
    st.header("Análisis de Suelo")
    np.random.seed(42)
    N, P, K = np.random.uniform(20, 80), np.random.uniform(10, 60), np.random.uniform(30, 90)

    rec = {
        "Trigo":    (max(0, 100 - N), max(0, 50 - P), max(0, 70 - K)),
        "Maíz":     (max(0, 180 - N), max(0, 80 - P), max(0, 100 - K)),
        "Soja":     (max(0, 40 - N),  max(0, 60 - P), max(0, 50 - K)),
        "Sorgo":    (max(0, 120 - N), max(0, 60 - P), max(0, 80 - K)),
        "Girasol":  (max(0, 60 - N),  max(0, 70 - P), max(0, 60 - K)),
    }
    rec_N, rec_P, rec_K = rec[cultivo]

    cols = st.columns(3)
    cols[0].metric("N", f"{N:.1f} ppm", f"+{rec_N:.0f} kg/ha")
    cols[1].metric("P", f"{P:.1f} ppm", f"+{rec_P:.0f} kg/ha")
    cols[2].metric("K", f"{K:.1f} ppm", f"+{rec_K:.0f} kg/ha")

    # --- MAPA CON st_folium (SIN ERRORES) ---
    st.header("Mapa ESRI")

    centroid = gdf.geometry.union_all().centroid
    center = [centroid.y, centroid.x]

    m = folium.Map(location=center, zoom_start=14, tiles=None)

    # Capas ESRI
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}',
        attr='Esri',
        name='ESRI Streets',
        overlay=False
    ).add_to(m)

    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Esri',
        name='ESRI Satélite',
        overlay=False
    ).add_to(m)

    # Polígono
    folium.GeoJson(
        gdf,
        style_function=lambda x: {
            'fillColor': '#3388ff',
            'color': 'black',
            'weight': 3,
            'fillOpacity': 0.4
        }
    ).add_to(m)

    # Marcador
    folium.CircleMarker(
        location=center,
        radius=10,
        color='red',
        fill=True,
        popup=f"<b>{cultivo}</b><br>N: {N:.1f}<br>P: {P:.1f}<br>K: {K:.1f}"
    ).add_to(m)

    folium.LayerControl().add_to(m)

    # --- MOSTRAR MAPA CON st_folium ---
    map_data = st_folium(m, width=800, height=500, key="mapa_esri")

else:
    st.info("Sube un archivo SHP para comenzar.")
    st.markdown("**Tip:** Usa QGIS para exportar tu lote como SHP.")

# --- Footer ---
st.markdown("---")
st.caption("Streamlit + Folium + ESRI | Sin `streamlit-folium` → Sin errores de DOM")
