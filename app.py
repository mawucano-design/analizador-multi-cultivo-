import streamlit as st
from streamlit_folium import st_folium
import geopandas as gpd
import folium
import tempfile
import os
import pandas as pd
import numpy as np
import hashlib

# --- Configuración ---
st.set_page_config(page_title="Fertilidad + ESRI", layout="wide")

# Inicializar session_state
if "map_key" not in st.session_state:
    st.session_state.map_key = 0
if "last_file_hash" not in st.session_state:
    st.session_state.last_file_hash = None

# --- Título ---
st.title("Analizador de Fertilidad + Mapa ESRI")
st.markdown("Sube un **SHP** → análisis → mapa interactivo **sin errores**.")

# --- Sidebar ---
cultivo = st.sidebar.selectbox("Cultivo:", ["Trigo", "Maíz", "Soja", "Sorgo", "Girasol"])

# --- Carga de archivos ---
uploaded_files = st.file_uploader(
    "Sube archivos SHP (.shp, .shx, .dbf, .prj...)",
    type=['shp', 'shx', 'dbf', 'prj', 'cpg', 'qpj'],
    accept_multiple_files=True,
    key="uploader"
)

# --- Función para generar hash único del conjunto de archivos ---
def get_files_hash(uploaded_files):
    if not uploaded_files:
        return None
    hash_str = ""
    for f in sorted(uploaded_files, key=lambda x: x.name):
        hash_str += f.name + str(f.size)
    return hashlib.md5(hash_str.encode()).hexdigest()

# --- Procesar SHP ---
gdf = None
if uploaded_files:
    current_hash = get_files_hash(uploaded_files)

    # Solo recargar si cambió el archivo
    if current_hash != st.session_state.last_file_hash:
        st.session_state.last_file_hash = current_hash
        st.session_state.map_key += 1  # Forzar nuevo key

    # Cargar SHP
    shp_file = next((f for f in uploaded_files if f.name.lower().endswith('.shp')), None)
    if not shp_file:
        st.error("Falta el archivo `.shp`")
        st.stop()

    with tempfile.TemporaryDirectory() as tmpdir:
        for f in uploaded_files:
            with open(os.path.join(tmpdir, f.name), "wb") as buffer:
                buffer.write(f.getbuffer())

        try:
            gdf = gpd.read_file(os.path.join(tmpdir, shp_file.name))
            if gdf.empty:
                st.error("SHP vacío")
                st.stop()
        except Exception as e:
            st.error(f"Error leyendo SHP: {e}")
            st.stop()

    st.success(f"Polígono: {len(gdf)} feature(s)")
    area_ha = gdf.to_crs(epsg=3857).geometry.area.sum() / 10000
    st.metric("Área total", f"{area_ha:,.2f} ha")

    # --- Análisis simulado ---
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

    # --- MAPA con st_folium + key único ---
    st.header("Mapa ESRI")

    # Contenedor vacío para el mapa
    map_container = st.empty()

    with map_container:
        centroid = gdf.geometry.union_all().centroid
        center = [centroid.y, centroid.x]

        m = folium.Map(location=center, zoom_start=14, tiles=None)

        # Capas ESRI
        folium.TileLayer(
            tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}',
            attr='Esri',
            name='Calles',
            overlay=False
        ).add_to(m)

        folium.TileLayer(
            tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
            attr='Esri',
            name='Satélite',
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

        # Key único para evitar DOM conflicts
        st_folium(m, width=800, height=500, key=f"map_{st.session_state.map_key}")

else:
    st.info("Sube un SHP para comenzar.")
    st.markdown("**Tip:** Exporta tu lote desde QGIS como Shapefile.")

# --- Footer ---
st.markdown("---")
st.caption("Sin errores de DOM | st_folium + key dinámico + st.empty()")
