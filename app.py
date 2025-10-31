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

warnings.filterwarnings('ignore')

st.set_page_config(page_title="Analizador Multi-Cultivo", layout="wide")
st.title("🌱 ANALIZADOR MULTI-CULTIVO - Sentinel-2 + ESRI")
st.markdown("**Análisis NPK por zonas con mapas interactivos**")
st.markdown("---")

os.environ['SHAPE_RESTORE_SHX'] = 'YES'

# Mapas base ESRI
MAPAS_BASE = {
    "ESRI Satellite": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    "OSM": "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
}

# Parámetros cultivos
CULTIVOS = ['TRIGO', 'MAÍZ', 'SOJA', 'SORGO', 'GIRASOL']
ICONOS = {'TRIGO': '🌾', 'MAÍZ': '🌽', 'SOJA': '🫘', 'SORGO': '🌾', 'GIRASOL': '🌻'}

# Función para dividir parcela
def dividir_parcela(gdf, n_zonas):
    if len(gdf) == 0:
        return gdf
    geom = gdf.geometry.iloc[0]
    bounds = geom.bounds
    minx, miny, maxx, maxy = bounds
    n_cols = math.isqrt(n_zonas)
    n_rows = math.ceil(n_zonas / n_cols)
    width = (maxx - minx) / n_cols
    height = (maxy - miny) / n_rows
    zonas = []
    for i in range(n_rows):
        for j in range(n_cols):
            if len(zonas) >= n_zonas:
                break
            poly = Polygon([
                (minx + j * width, miny + i * height),
                (minx + (j + 1) * width, miny + i * height),
                (minx + (j + 1) * width, miny + (i + 1) * height),
                (minx + j * width, miny + (i + 1) * height)
            ])
            inter = geom.intersection(poly)
            if not inter.is_empty:
                zonas.append(inter)
    return gpd.GeoDataFrame({'zona': range(1, len(zonas) + 1), 'geometry': zonas}, crs=gdf.crs)

# Función para calcular área
def calcular_area(gdf):
    return gdf.to_crs('EPSG:3857').area / 10000

# Función para simular índices Sentinel-2
def simular_indices(gdf_zonas):
    resultados = []
    for _, row in gdf_zonas.iterrows():
        centroid = row.geometry.centroid
        ndvi = np.clip(0.5 + np.random.normal(0, 0.1), 0.1, 0.9)
        npk = np.clip(ndvi * 0.8 + np.random.normal(0, 0.05), 0, 1)
        resultados.append({'ndvi': ndvi, 'npk': npk})
    return resultados

# Crear mapa Folium
def crear_mapa(gdf_zonas, mapa_tipo="ESRI Satellite"):
    bounds = gdf_zonas.unary_union.bounds
    m = folium.Map(location=[(bounds[1] + bounds[3])/2, (bounds[0] + bounds[2])/2], zoom_start=14)
    folium.TileLayer(tiles=MAPAS_BASE[mapa_tipo], attr=mapa_tipo).add_to(m)
    
    def estilo(feature):
        npk = feature['properties']['npk']
        color = 'red' if npk < 0.4 else 'yellow' if npk < 0.6 else 'green'
        return {'fillColor': color, 'color': 'black', 'weight': 2, 'fillOpacity': 0.6}
    
    folium.GeoJson(gdf_zonas, style_function=estilo, 
                   tooltip=folium.GeoJsonTooltip(fields=['zona', 'ndvi', 'npk', 'area_ha'])).add_to(m)
    return m

# Sidebar
with st.sidebar:
    st.header("⚙️ Configuración")
    cultivo = st.selectbox("🌱 Cultivo", CULTIVOS)
    n_zonas = st.slider("🎯 Nº Zonas", 16, 48, 32)
    mapa_tipo = st.selectbox("🗺️ Mapa Base", list(MAPAS_BASE.keys()))
    uploaded_zip = st.file_uploader("📤 ZIP Shapefile", type=['zip'])

# Main
if uploaded_zip:
    with st.spinner("Cargando..."):
        try:
            with tempfile.TemporaryDirectory() as tmp_dir:
                with zipfile.ZipFile(uploaded_zip, 'r') as zip_ref:
                    zip_ref.extractall(tmp_dir)
                shp_files = [f for f in os.listdir(tmp_dir) if f.endswith('.shp')]
                if shp_files:
                    gdf = gpd.read_file(os.path.join(tmp_dir, shp_files[0]))
                    area_total = calcular_area(gdf).sum()
                    st.success(f"✅ Parcela cargada: {area_total:.1f} ha | {len(gdf)} polígonos")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.info(f"🌱 Cultivo: {ICONOS[cultivo]} {cultivo}")
                    with col2:
                        st.info(f"🎯 Zonas: {n_zonas}")
                    
                    if st.button("🚀 ANALIZAR", type="primary"):
                        gdf_zonas = dividir_parcela(gdf, n_zonas)
                        indices = simular_indices(gdf_zonas)
                        gdf_zonas['ndvi'] = [i['ndvi'] for i in indices]
                        gdf_zonas['npk'] = [i['npk'] for i in indices]
                        gdf_zonas['area_ha'] = calcular_area(gdf_zonas)
                        
                        # Métricas
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("NDVI Promedio", f"{gdf_zonas['ndvi'].mean():.2f}")
                        with col2:
                            st.metric("NPK Promedio", f"{gdf_zonas['npk'].mean():.2f}")
                        with col3:
                            st.metric("Área Total", f"{gdf_zonas['area_ha'].sum():.1f} ha")
                        
                        # Mapa
                        st.subheader("🗺️ Mapa Interactivo")
                        m = crear_mapa(gdf_zonas, mapa_tipo)
                        folium_static(m, width="100%", height=500)
                        
                        # Tabla
                        st.subheader("📊 Resultados por Zona")
                        tabla = gdf_zonas[['zona', 'area_ha', 'ndvi', 'npk']].round(3)
                        st.dataframe(tabla)
                        
                        # Descargas
                        st.subheader("💾 Descargar")
                        csv = gdf_zonas.to_csv(index=False).encode('utf-8')
                        st.download_button("📥 CSV", csv, f"analisis_{cultivo}.csv", "text/csv")
                        
                        # Gráfico simple
                        fig, ax = plt.subplots()
                        ax.bar(tabla['zona'], tabla['npk'], color='green')
                        ax.set_title(f'Índice NPK por Zona - {cultivo}')
                        ax.set_xlabel('Zona')
                        ax.set_ylabel('NPK (0-1)')
                        st.pyplot(fig)
                else:
                    st.error("❌ No se encontró .shp en el ZIP")
        except Exception as e:
            st.error(f"❌ Error: {e}")
else:
    st.info("👆 Sube un ZIP con tu shapefile (.shp + .shx + .dbf) para analizar.")
    with st.expander("ℹ️ ¿Cómo usar?"):
        st.markdown("""
        1. Comprime tu shapefile en ZIP.
        2. Selecciona cultivo y zonas.
        3. Sube y analiza → Obtén mapa + tabla + CSV.
        """)

st.markdown("---")
st.markdown("*Powered by Streamlit + GeoPandas*")
