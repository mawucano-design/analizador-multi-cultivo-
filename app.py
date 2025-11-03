import streamlit as st
import folium
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
if "last_hash" not in st.session_state:
    st.session_state.last_hash = None

# --- Título ---
st.title("Analizador de Fertilidad + Mapa ESRI")
st.markdown("Sube SHP o pega GeoJSON → análisis → mapa interactivo.")

# --- Sidebar ---
cultivo = st.sidebar.selectbox("Cultivo:", ["Trigo", "Maíz", "Soja", "Sorgo", "Girasol"])

# --- Carga SHP ---
st.header("Carga SHP")
try:
    import fiona
    SHP_OK = True
except:
    SHP_OK = False
    st.warning("Fiona no disponible. Usa GeoJSON.")

uploaded_files = None
if SHP_OK:
    uploaded_files = st.file_uploader(
        "Archivos SHP",
        type=['shp', 'shx', 'dbf', 'prj'],
        accept_multiple_files=True
    )

# --- GeoJSON ---
st.header("O pega GeoJSON")
geojson_text = st.text_area("GeoJSON:", height=120)

# --- Procesar ---
geoms = None
current_hash = hash(str(uploaded_files) + geojson_text)

if current_hash != st.session_state.last_hash:
    st.session_state.last_hash = current_hash
    st.session_state.map_key += 1

# SHP
if SHP_OK and uploaded_files:
    shp = next((f for f in uploaded_files if f.name.endswith('.shp')), None)
    if shp:
        with tempfile.TemporaryDirectory() as tmp:
            for f in uploaded_files:
                with open(os.path.join(tmp, f.name), "wb") as out:
                    out.write(f.getbuffer())
            try:
                import fiona
                with fiona.open(os.path.join(tmp, shp.name)) as src:
                    geoms = [shape(f['geometry']) for f in src]
                st.success(f"SHP: {len(geoms)} polígonos")
            except Exception as e:
                st.error(f"SHP error: {e}")

# GeoJSON
if not geoms and geojson_text.strip():
    try:
        data = json.loads(geojson_text)
        features = data.get('features', [])
        geoms = [shape(f['geometry']) for f in features if 'geometry' in f]
        st.success(f"GeoJSON: {len(geoms)} polígonos")
    except Exception as e:
        st.error(f"GeoJSON error: {e}")

# --- Análisis y mapa ---
if geoms and len(geoms) > 0:
    # Área
    area = sum(g.area for g in geoms)
    st.metric("Área", f"{area:.6f} unidades²")

    # Análisis simulado
    np.random.seed(42)
    N, P, K = np.random.uniform(20, 80), np.random.uniform(10, 60), np.random.uniform(30, 90)
    rec_N = max(0, 100 - N) if cultivo == "Trigo" else max(0, 180 - N)
    rec_P = max(0, 50 - P) if cultivo in ["Trigo", "Soja"] else max(0, 80 - P)
    rec_K = max(0, 70 - K)

    cols = st.columns(3)
    cols[0].metric("N", f"{N:.1f} ppm", f"+{rec_N:.0f} kg/ha")
    cols[1].metric("P", f"{P:.1f} ppm", f"+{rec_P:.0f} kg/ha")
    cols[2].metric("K", f"{K:.1f} ppm", f"+{rec_K:.0f} kg/ha")

    # Mapa
    st.header("Mapa ESRI")
    center = geoms[0].centroid
    m = folium.Map(location=[center.y, center.x], zoom_start=15, tiles=None)

    # Capas ESRI
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}',
        attr='Esri', name='Calles', overlay=False
    ).add_to(m)

    # Polígonos
    for g in geoms:
        folium.GeoJson(
            g.__geo_interface__,
            style_function=lambda x: {'fillColor': 'blue', 'color': 'black', 'weight': 2, 'fillOpacity': 0.4}
        ).add_to(m)

    folium.LayerControl().add_to(m)

    # Usa st_folium directamente (SIN import)
    st_folium(m, width=800, height=500, key=f"map_{st.session_state.map_key}")

else:
    st.info("Sube SHP o pega GeoJSON para empezar.")
    st.code('''{"type": "FeatureCollection", "features": [{"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[-58.4,-34.6],[-58.3,-34.6],[-58.3,-34.5],[-58.4,-34.5],[-58.4,-34.6]]]]}}]}''', language="json")

# --- Footer ---
st.markdown("---")
st.caption("Streamlit 1.38.0 + folium → st_folium nativo")
