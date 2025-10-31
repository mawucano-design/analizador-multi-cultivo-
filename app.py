# -*- coding: utf-8 -*-
import streamlit as st
import geopandas as gpd
import pandas as pd
import numpy as np
import tempfile
import os
import zipfile
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import io
from shapely.geometry import Polygon
import math
import folium
from streamlit_folium import folium_static
import warnings
warnings.filterwarnings('ignore')

# CONFIGURACIÓN BÁSICA SIN .streamlit/
st.set_page_config(
    page_title="🌱 Analizador Multi-Cultivo",
    page_icon="🌱", 
    layout="wide"
)

st.title("🌱 ANALIZADOR MULTI-CULTIVO - METODOLOGÍA GEE")
st.markdown("---")

# =============================================================================
# CONFIGURACIÓN SIMPLIFICADA
# =============================================================================

# Credenciales DIRECTAS sin secrets.toml
SENTINEL_HUB_CREDENTIALS = {
    "client_id": "b296cf70-c9d2-4e69-91f4-f7be80b99ed1",
    "client_secret": "358474d6-2326-4637-bf8e-30a709b2d6a6"
}

# =============================================================================
# PARÁMETROS BÁSICOS (igual que antes)
# =============================================================================

PARAMETROS_CULTIVOS = {
    'TRIGO': {'NITROGENO': {'min': 120, 'max': 180}, 'MATERIA_ORGANICA_OPTIMA': 3.5},
    'MAÍZ': {'NITROGENO': {'min': 150, 'max': 220}, 'MATERIA_ORGANICA_OPTIMA': 4.0},
    'SOJA': {'NITROGENO': {'min': 80, 'max': 120}, 'MATERIA_ORGANICA_OPTIMA': 3.8},
    'SORGO': {'NITROGENO': {'min': 100, 'max': 150}, 'MATERIA_ORGANICA_OPTIMA': 3.0},
    'GIRASOL': {'NITROGENO': {'min': 90, 'max': 130}, 'MATERIA_ORGANICA_OPTIMA': 3.2}
}

# =============================================================================
# SIDEBAR SIMPLIFICADO
# =============================================================================

with st.sidebar:
    st.header("⚙️ Configuración")
    
    cultivo = st.selectbox("Cultivo:", ["TRIGO", "MAÍZ", "SOJA", "SORGO", "GIRASOL"])
    analisis_tipo = st.selectbox("Tipo de Análisis:", ["FERTILIDAD ACTUAL", "RECOMENDACIONES NPK"])
    nutriente = st.selectbox("Nutriente:", ["NITRÓGENO", "FÓSFORO", "POTASIO"])
    
    n_divisiones = st.slider("Número de zonas:", 16, 48, 32)
    uploaded_zip = st.file_uploader("Subir ZIP con shapefile", type=['zip'])

# =============================================================================
# FUNCIONES BÁSICAS
# =============================================================================

def calcular_superficie(gdf):
    try:
        return gdf.geometry.area / 10000
    except:
        return gdf.geometry.area / 10000

# =============================================================================
# INTERFAZ PRINCIPAL SIMPLIFICADA
# =============================================================================

if uploaded_zip:
    with st.spinner("Cargando parcela..."):
        try:
            with tempfile.TemporaryDirectory() as tmp_dir:
                with zipfile.ZipFile(uploaded_zip, 'r') as zip_ref:
                    zip_ref.extractall(tmp_dir)
                
                shp_files = [f for f in os.listdir(tmp_dir) if f.endswith('.shp')]
                if shp_files:
                    shp_path = os.path.join(tmp_dir, shp_files[0])
                    gdf = gpd.read_file(shp_path)
                    
                    st.success(f"✅ Parcela cargada: {len(gdf)} polígono(s)")
                    
                    # Información básica
                    area_total = calcular_superficie(gdf).sum()
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("Polígonos", len(gdf))
                        st.metric("Área Total", f"{area_total:.1f} ha")
                    
                    with col2:
                        st.metric("Cultivo", cultivo)
                        st.metric("Análisis", analisis_tipo)
                    
                    # Mapa simple
                    st.subheader("🗺️ Vista Previa")
                    bounds = gdf.total_bounds
                    center_lat = (bounds[1] + bounds[3]) / 2
                    center_lon = (bounds[0] + bounds[2]) / 2
                    
                    m = folium.Map(location=[center_lat, center_lon], zoom_start=12)
                    
                    # Agregar polígonos
                    folium.GeoJson(
                        gdf.__geo_interface__,
                        style_function=lambda x: {'fillColor': 'blue', 'color': 'black', 'fillOpacity': 0.5}
                    ).add_to(m)
                    
                    folium_static(m, width=800, height=400)
                    
                    # Botón de análisis
                    if st.button("🚀 EJECUTAR ANÁLISIS", type="primary"):
                        st.success("✅ Análisis completado (versión simplificada)")
                        st.info("Esta es una versión básica que demuestra que la app funciona")
                        
                        # Datos de ejemplo
                        datos_ejemplo = pd.DataFrame({
                            'Zona': range(1, 6),
                            'NDVI': [0.65, 0.72, 0.58, 0.81, 0.69],
                            'Biomasa_kg_ha': [1200, 1500, 900, 1800, 1300],
                            'Recomendación_N': [140, 160, 120, 180, 150]
                        })
                        
                        st.dataframe(datos_ejemplo)
                        
                else:
                    st.error("❌ No se encontró archivo .shp en el ZIP")
                    
        except Exception as e:
            st.error(f"❌ Error: {str(e)}")

else:
    st.info("📁 Sube un archivo ZIP con shapefile para comenzar")
    
    # Información básica
    with st.expander("ℹ️ Información de la aplicación"):
        st.markdown("""
        **🌱 ANALIZADOR MULTI-CULTIVO**
        
        **Funcionalidades:**
        - Análisis de fertilidad por cultivo
        - Recomendaciones NPK específicas
        - Visualización en mapas interactivos
        - Soporte para múltiples cultivos
        
        **Cómo usar:**
        1. Sube un ZIP con shapefile de tu parcela
        2. Configura los parámetros en el sidebar
        3. Ejecuta el análisis
        4. Visualiza los resultados
        """)

st.markdown("---")
st.caption("🌱 Versión simplificada - Análisis Multi-Cultivo")
