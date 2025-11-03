import streamlit as st
from streamlit_folium import folium_static
import folium
import tempfile
import os
import json
import pandas as pd
import numpy as np
from shapely.geometry import shape
import ee  # Google Earth Engine

# Inicializar GEE (autenticación requerida)
try:
    ee.Initialize()
    GEE_OK = True
except Exception as e:
    GEE_OK = False
    st.warning(f"GEE no inicializado: {e}. Usando simulación.")

# --- Configuración ---
st.set_page_config(page_title="Analizador Fertilidad GEE + ESRI Satélite", layout="wide")

if "map_key" not in st.session_state:
    st.session_state.map_key = 0
if "last_hash" not in st.session_state:
    st.session_state.last_hash = None

# --- Título ---
st.title("🌾 Analizador de Fertilidad GEE + Mapas ESRI Satélite")
st.markdown("Integración completa del repo original: Análisis N/P/K con GEE, recomendaciones por cultivo, mapas interactivos en **ESRI World Imagery (Satélite)** con overlays de resultados.")

# --- Sidebar ---
cultivo = st.sidebar.selectbox("Cultivo:", ["Trigo", "Maíz", "Soja", "Sorgo", "Girasol"])

# --- Carga SHP / GeoJSON ---
st.header("Carga Polígono (SHP o GeoJSON)")
try:
    import fiona
    SHP_OK = True
except:
    SHP_OK = False

uploaded_files = st.file_uploader("Archivos SHP", type=['shp', 'shx', 'dbf', 'prj'], accept_multiple_files=True) if SHP_OK else None
geojson_text = st.text_area("O pega GeoJSON:", height=120)

# --- Procesar geometría ---
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
                with fiona.open(os.path.join(tmp, shp.name)) as src:
                    geoms = [shape(f['geometry']) for f in src]
                st.success(f"SHP: {len(geoms)} polígonos")
            except Exception as e:
                st.error(f"Error SHP: {e}")

# GeoJSON
if not geoms and geojson_text.strip():
    try:
        data = json.loads(geojson_text)
        features = data.get('features', [])
        geoms = [shape(f['geometry']) for f in features if 'geometry' in f]
        st.success(f"GeoJSON: {len(geoms)} polígonos")
    except Exception as e:
        st.error(f"Error GeoJSON: {e}")

if not geoms:
    st.info("Sube SHP o pega GeoJSON.")
    st.code('''{"type": "FeatureCollection", "features": [{"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[-58.4,-34.6],[-58.3,-34.6],[-58.3,-34.5],[-58.4,-34.5],[-58.4,-34.6]]]}}]}''')
    st.stop()

# --- Función del repo original: Análisis GEE de nutrientes ---
@st.cache_data
def analyze_nutrients_gee(geometry, cultivo):
    if not GEE_OK:
        # Simulación (del repo original)
        np.random.seed(42)
        return {
            'N': np.random.uniform(20, 80),
            'P': np.random.uniform(10, 60),
            'K': np.random.uniform(30, 90)
        }
    
    # Lógica GEE real (basada en repo original: usa OpenLandMap para nutrientes)
    ee_geom = ee.Geometry.Polygon([[[coord[0], coord[1]] for coord in poly.exterior.coords] for poly in geoms][0])
    
    # Cargar imágenes GEE (ej. N, P, K de OpenLandMap)
    n_image = ee.Image("OpenLandMap/SOL/SOL_ORGANIC-CARBON_USDA-4A1A2A/SOL_ORGCOBT_N.v2").select('b0').clip(ee_geom)
    p_image = ee.Image("OpenLandMap/SOL/SOL_PH-H2O_USDA-4C1A1A/SOL_PHCLABO_M.v2").select('b0').clip(ee_geom)  # Proxy para P
    k_image = ee.Image("OpenLandMap/SOL/SOL_CLAY-WFRA-USDA-4B1B/SOL_CLAYFRA_N.v2").select('b0').clip(ee_geom)  # Proxy para K
    
    # Reducir a media en el polígono
    scale = 30
    n_mean = n_image.reduceRegion(reducer=ee.Reducer.mean(), geometry=ee_geom, scale=scale, maxPixels=1e9).getInfo()['b0']
    p_mean = p_image.reduceRegion(reducer=ee.Reducer.mean(), geometry=ee_geom, scale=scale, maxPixels=1e9).getInfo()['b0']
    k_mean = k_image.reduceRegion(reducer=ee.Reducer.mean(), geometry=ee_geom, scale=scale, maxPixels=1e9).getInfo()['b0']
    
    return {'N': n_mean or 50, 'P': p_mean or 30, 'K': k_mean or 60}

# --- Función del repo original: Recomendaciones por cultivo ---
def get_recommendations(n, p, k, cultivo):
    thresholds = {
        "Trigo": {'N': 120, 'P': 60, 'K': 80},
        "Maíz": {'N': 200, 'P': 80, 'K': 100},
        "Soja": {'N': 20, 'P': 40, 'K': 60},
        "Sorgo": {'N': 140, 'P': 60, 'K': 90},
        "Girasol": {'N': 80, 'P': 70, 'K': 70}
    }
    base = thresholds.get(cultivo, {'N': 100, 'P': 50, 'K': 70})
    return {
        'rec_N': max(0, base['N'] - n),
        'rec_P': max(0, base['P'] - p),
        'rec_K': max(0, base['K'] - k)
    }

# --- Análisis ---
if geoms:
    area = sum(g.area for g in geoms)
    st.metric("Área", f"{area:.6f} unidades²")

    st.header("🔬 Análisis de Nutrientes (GEE)")
    nutrients = analyze_nutrients_gee(geoms, cultivo)
    N, P, K = nutrients['N'], nutrients['P'], nutrients['K']
    recs = get_recommendations(N, P, K, cultivo)
    rec_N, rec_P, rec_K = recs['rec_N'], recs['rec_P'], recs['rec_K']

    cols = st.columns(3)
    cols[0].metric("N", f"{N:.1f} ppm", f"+{rec_N:.0f} kg/ha")
    cols[1].metric("P", f"{P:.1f} ppm", f"+{rec_P:.0f} kg/ha")
    cols[2].metric("K", f"{K:.1f} ppm", f"+{rec_K:.0f} kg/ha")

    df_result = pd.DataFrame({
        "Nutriente": ["N", "P", "K"],
        "Actual (ppm)": [N, P, K],
        "Recomendación (kg/ha)": [rec_N, rec_P, rec_K]
    })
    st.table(df_result)

    # --- Función para crear mapa ESRI Satélite ---
    def create_esri_sat_map(geoms, center, extra_layers=None):
        m = folium.Map(location=center, zoom_start=15, tiles=None)
        
        # Base ESRI Satélite (por defecto)
        folium.TileLayer(
            tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
            attr='Esri',
            name='ESRI Satélite'
        ).add_to(m)
        
        # Alternativa: ESRI Calles
        folium.TileLayer(
            tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}',
            attr='Esri',
            name='ESRI Calles'
        ).add_to(m)
        
        # Polígono base
        for g in geoms:
            folium.GeoJson(
                g.__geo_interface__,
                style_function=lambda x: {'fillColor': 'blue', 'color': 'black', 'weight': 2, 'fillOpacity': 0.2}
            ).add_to(m)
        
        # Capas extras (nutrientes/recomendaciones)
        if extra_layers:
            for layer_data in extra_layers:
                folium.Choropleth(
                    geo_data=geojson_data,  # Global para simplicidad
                    data=layer_data['data'],
                    columns=['feature', 'value'],
                    key_on='feature',
                    fill_color='YlOrRd',
                    legend_name=layer_data['name']
                ).add_to(m)
        
        folium.LayerControl().add_to(m)
        return m

    # GeoJSON para choropleth
    geojson_data = {"type": "FeatureCollection", "features": [{"type": "Feature", "id": "poly1", "geometry": g.__geo_interface__} for g in geoms[:1]]}  # Asume 1 poly para demo

    center = geoms[0].centroid
    center_coords = [center.y, center.x]

    # --- Mapa 1: Base Polígono en ESRI Satélite ---
    st.subheader("🗺️ 1. Polígono Base (ESRI Satélite)")
    m1 = create_esri_sat_map(geoms, center_coords)
    folium_static(m1, width=700, height=400, key=f"m1_{st.session_state.map_key}")

    # --- Mapa 2: Niveles de N ---
    st.subheader("🗺️ 2. Niveles de N (Choropleth en ESRI Satélite)")
    m2 = create_esri_sat_map(geoms, center_coords, extra_layers=[{'data': pd.DataFrame({'feature': ['poly1'], 'value': [N]}), 'name': 'N ppm'}])
    folium_static(m2, width=700, height=400, key=f"m2_{st.session_state.map_key}")

    # --- Mapa 3: Niveles de P ---
    st.subheader("🗺️ 3. Niveles de P (Choropleth en ESRI Satélite)")
    m3 = create_esri_sat_map(geoms, center_coords, extra_layers=[{'data': pd.DataFrame({'feature': ['poly1'], 'value': [P]}), 'name': 'P ppm'}])
    folium_static(m3, width=700, height=400, key=f"m3_{st.session_state.map_key}")

    # --- Mapa 4: Niveles de K ---
    st.subheader("🗺️ 4. Niveles de K (Choropleth en ESRI Satélite)")
    m4 = create_esri_sat_map(geoms, center_coords, extra_layers=[{'data': pd.DataFrame({'feature': ['poly1'], 'value': [K]}), 'name': 'K ppm'}])
    folium_static(m4, width=700, height=400, key=f"m4_{st.session_state.map_key}")

    # --- Mapa 5: Recomendaciones ---
    st.subheader("🗺️ 5. Recomendaciones de Fertilizante (Overlay en ESRI Satélite)")
    rec_data = pd.DataFrame({'feature': ['poly1'], 'rec_N': [rec_N], 'rec_P': [rec_P], 'rec_K': [rec_K]})
    m5 = create_esri_sat_map(geoms, center_coords, extra_layers=[
        {'data': rec_data[['feature', 'rec_N']], 'name': 'Rec N kg/ha'},
        {'data': rec_data[['feature', 'rec_P']], 'name': 'Rec P kg/ha'},
        {'data': rec_data[['feature', 'rec_K']], 'name': 'Rec K kg/ha'}
    ])
    folium_static(m5, width=700, height=400, key=f"m5_{st.session_state.map_key}")

# --- Footer ---
st.markdown("---")
st.caption("Basado en repo original GEE + ESRI Satélite multi-mapas | Autentica GEE para datos reales")
