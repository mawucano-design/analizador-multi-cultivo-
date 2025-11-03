import streamlit as st
import folium
from streamlit_folium import st_folium
import tempfile
import os
import json
import pandas as pd
import numpy as np
from shapely.geometry import shape  # Para GeoJSON
try:
    import fiona  # Solo para SHP
    SHP_SUPPORTED = True
except ImportError:
    SHP_SUPPORTED = False
    st.warning("Fiona no disponible. Usa coordenadas GeoJSON en su lugar.")

# --- Configuración ---
st.set_page_config(page_title="Fertilidad + ESRI Map", layout="wide")

# Session state
if "map_key" not in st.session_state:
    st.session_state.map_key = 0
if "last_input_hash" not in st.session_state:
    st.session_state.last_input_hash = None

# --- Título ---
st.title("🌾 Analizador de Fertilidad + Mapa ESRI")
st.markdown("Sube **SHP** o pega **GeoJSON** → Análisis N/P/K → Mapa interactivo **sin errores**.")

# --- Sidebar ---
cultivo = st.sidebar.selectbox("Cultivo:", ["Trigo", "Maíz", "Soja", "Sorgo", "Girasol"])

# --- Opción 1: Carga SHP (con fiona) ---
st.header("Opción 1: Carga Polígono SHP")
uploaded_files = None
if SHP_SUPPORTED:
    uploaded_files = st.file_uploader(
        "Sube archivos SHP (.shp, .shx, .dbf, .prj...)",
        type=['shp', 'shx', 'dbf', 'prj', 'cpg', 'qpj'],
        accept_multiple_files=True
    )

# --- Opción 2: GeoJSON (siempre funciona, sin dependencias pesadas) ---
st.header("Opción 2: Pega Coordenadas GeoJSON")
geojson_text = st.text_area(
    "Pega tu GeoJSON aquí (ej. desde QGIS > Exportar > GeoJSON)",
    placeholder='{"type": "FeatureCollection", "features": [{"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[lon1,lat1], [lon2,lat2], ...]]}}]}',
    height=150
)

# --- Procesar Input ---
gdf_like = None  # Dict simulando GeoDataFrame
input_type = None

# Hash para key único
def get_input_hash():
    if uploaded_files:
        return hash(tuple(sorted([f.name + str(f.size) for f in uploaded_files])))
    elif geojson_text:
        return hash(geojson_text)
    return None

current_hash = get_input_hash()
if current_hash != st.session_state.last_input_hash:
    st.session_state.last_input_hash = current_hash
    st.session_state.map_key += 1

# Cargar desde SHP (si disponible)
if SHP_SUPPORTED and uploaded_files:
    shp_file = next((f for f in uploaded_files if f.name.lower().endswith('.shp')), None)
    if shp_file:
        with tempfile.TemporaryDirectory() as tmpdir:
            for f in uploaded_files:
                with open(os.path.join(tmpdir, f.name), "wb") as buffer:
                    buffer.write(f.getbuffer())
            try:
                with fiona.open(os.path.join(tmpdir, shp_file.name)) as src:
                    features = []
                    for feat in src:
                        geom = shape(feat['geometry'])
                        props = feat['properties']
                        features.append({'geometry': geom, 'properties': props})
                    gdf_like = {'features': features}  # Simula GeoDataFrame
                    input_type = 'SHP'
                    st.success(f"SHP cargado: {len(features)} features")
            except Exception as e:
                st.error(f"Error en SHP: {e}. Prueba con GeoJSON.")

# Cargar desde GeoJSON
if geojson_text and not gdf_like:
    try:
        geojson_data = json.loads(geojson_text)
        if geojson_data['type'] == 'FeatureCollection':
            features = []
            for feat in geojson_data['features']:
                geom = shape(feat['geometry'])
                props = feat.get('properties', {})
                features.append({'geometry': geom, 'properties': props})
            gdf_like = {'features': features}
            input_type = 'GeoJSON'
            st.success(f"GeoJSON cargado: {len(features)} features")
    except json.JSONDecodeError:
        st.error("JSON inválido. Verifica el formato.")
    except Exception as e:
        st.error(f"Error en GeoJSON: {e}")

# --- Si hay datos ---
if gdf_like:
    features = gdf_like['features']
    if not features:
        st.warning("No hay geometrías válidas.")
        st.stop()

    # Área aproximada (en grados, para demo; usa pyproj para precisión si necesitas)
    total_area = sum(f['geometry'].area for f in features)  # Aprox. en grados²
    st.metric("Features", len(features))
    st.metric("Área aprox.", f"{total_area:.4f} unidades")

    # --- Análisis simulado (REEMPLAZA CON GEE) ---
    st.header("🔬 Análisis de Suelo")
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

    # Tabla
    df_result = pd.DataFrame({
        "Nutriente": ["N", "P", "K"],
        "Actual (ppm)": [N, P, K],
        "Recomendación (kg/ha)": [rec_N, rec_P, rec_K]
    })
    st.table(df_result)

    # --- MAPA ESRI ---
    st.header("🗺️ Mapa Interactivo ESRI")

    # Centro (centroid de primera feature)
    centroid = features[0]['geometry'].centroid
    center = [centroid.y, centroid.x]

    # Mapa Folium
    m = folium.Map(location=center, zoom_start=14, tiles=None)

    # Capas ESRI
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}',
        attr='Esri',
        name='ESRI Calles',
        overlay=False
    ).add_to(m)

    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Esri',
        name='ESRI Satélite',
        overlay=False
    ).add_to(m)

    # Agregar features como GeoJson
    geojson_data = {
        "type": "FeatureCollection",
        "features": [{"type": "Feature", "geometry": f["geometry"].__geo_interface__, "properties": f["properties"]} for f in features]
    }
    folium.GeoJson(
        geojson_data,
        style_function=lambda x: {
            'fillColor': '#3388ff',
            'color': 'black',
            'weight': 3,
            'fillOpacity': 0.4
        },
        popup=folium.GeoJsonPopup()
    ).add_to(m)

    # Marcador central
    folium.CircleMarker(
        location=center,
        radius=10,
        popup=f"<b>{cultivo}</b><br>N: {N:.1f} ppm<br>P: {P:.1f}<br>K: {K:.1f}",
        color='red',
        fill=True
    ).add_to(m)

    folium.LayerControl().add_to(m)

    # Contenedor y render (con key único)
    map_container = st.empty()
    with map_container:
        st_folium(m, width=800, height=500, key=f"map_{st.session_state.map_key}")

else:
    st.info("👆 Sube SHP o pega GeoJSON para analizar.")
    st.markdown("""
    ### Cómo obtener GeoJSON:
    1. En **QGIS/Google Earth Engine**: Dibuja tu polígono → Exportar como **GeoJSON**.
    2. Pega el contenido aquí.
    3. ¡Más simple que SHP, sin archivos múltiples!
    """)

# --- Footer ---
st.markdown("---")
st.caption("Streamlit + Folium + ESRI | Sin GDAL/geopandas – Deploy garantizado")
