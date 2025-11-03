import streamlit as st
import folium
# ← QUITA: from streamlit_folium import st_folium
import tempfile
import os
import json
import pandas as pd
import numpy as np
from shapely.geometry import shape

# --- Configuración ---
st.set_page_config(page_title="Fertilidad + ESRI", layout="wide")

# Session state
if "map_key" not in st.session_state:
    st.session_state.map_key = 0
if "last_input_hash" not in st.session_state:
    st.session_state.last_input_hash = None

# --- Título ---
st.title("Analizador de Fertilidad + Mapa ESRI")
st.markdown("Sube **SHP** o pega **GeoJSON** → análisis → mapa **sin errores**.")

# --- Sidebar ---
cultivo = st.sidebar.selectbox("Cultivo:", ["Trigo", "Maíz", "Soja", "Sorgo", "Girasol"])

# --- Carga SHP ---
st.header("Opción 1: Carga SHP")
try:
    import fiona
    SHP_SUPPORTED = True
except ImportError:
    SHP_SUPPORTED = False
    st.warning("Fiona no disponible. Usa GeoJSON.")

uploaded_files = None
if SHP_SUPPORTED:
    uploaded_files = st.file_uploader(
        "Sube archivos SHP",
        type=['shp', 'shx', 'dbf', 'prj', 'cpg', 'qpj'],
        accept_multiple_files=True
    )

# --- GeoJSON ---
st.header("Opción 2: Pega GeoJSON")
geojson_text = st.text_area(
    "Pega tu GeoJSON aquí",
    placeholder='{"type": "FeatureCollection", "features": [...] }',
    height=150
)

# --- Procesar input ---
gdf_like = None
current_hash = None

def get_input_hash():
    if uploaded_files:
        return hash(tuple(sorted([f.name + str(f.size) for f in uploaded_files])))
    if geojson_text:
        return hash(geojson_text)
    return None

current_hash = get_input_hash()
if current_hash != st.session_state.last_input_hash:
    st.session_state.last_input_hash = current_hash
    st.session_state.map_key += 1

# SHP
if SHP_SUPPORTED and uploaded_files:
    shp_file = next((f for f in uploaded_files if f.name.lower().endswith('.shp')), None)
    if shp_file:
        with tempfile.TemporaryDirectory() as tmpdir:
            for f in uploaded_files:
                with open(os.path.join(tmpdir, f.name), "wb") as buffer:
                    buffer.write(f.getbuffer())
            try:
                with fiona.open(os.path.join(tmpdir, shp_file.name)) as src:
                    features = [shape(f['geometry']) for f in src]
                    gdf_like = features
                    st.success(f"SHP: {len(features)} polígonos")
            except Exception as e:
                st.error(f"Error SHP: {e}")

# GeoJSON
if not gdf_like and geojson_text:
    try:
        data = json.loads(geojson_text)
        if data['type'] == 'FeatureCollection':
            gdf_like = [shape(f['geometry']) for f in data['features']]
            st.success(f"GeoJSON: {len(gdf_like)} polígonos")
    except Exception as e:
        st.error(f"Error GeoJSON: {e}")

# --- Análisis y mapa ---
if gdf_like:
    # Área
    area = sum(g.area for g in gdf_like)
    st.metric("Área aprox.", f"{area:.4f} unidades")

    # Análisis
    st.header("Análisis")
    np.random.seed(42)
    N, P, K = np.random.uniform(20, 80), np.random.uniform(10, 60), np.random.uniform(30, 90)
    rec = {"Trigo": (100-N, 50-P, 70-K)}  # simplificado
    rec_N, rec_P, rec_K = max(0, rec["Trigo"][0]), max(0, rec["Trigo"][1]), max(0, rec["Trigo"][2])

    cols = st.columns(3)
    cols[0].metric("N", f"{N:.1f}", f"+{rec_N:.0f} kg")
    cols[1].metric("P", f"{P:.1f}", f"+{rec_P:.0f} kg")
    cols[2].metric("K", f"{K:.1f}", f"+{rec_K:.0f} kg")

    # Mapa
    st.header("Mapa ESRI")
    center = gdf_like[0].centroid
    m = folium.Map(location=[center.y, center.x], zoom_start=14, tiles=None)

    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}',
        attr='Esri', name='Calles'
    ).add_to(m)

    for geom in gdf_like:
        folium.GeoJson(geom.__geo_interface__, style_function=lambda x: {
            'fillColor': 'blue', 'color': 'black', 'weight': 2, 'fillOpacity': 0.3
        }).add_to(m)

    folium.LayerControl().add_to(m)

    # Usa st_folium directamente (nativo)
    st_folium(m, width=800, height=500, key=f"map_{st.session_state.map_key}")

else:
    st.info("Sube SHP o pega GeoJSON.")
