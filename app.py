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

# =============================================================================
# CONFIGURACIÓN INICIAL
# =============================================================================

st.set_page_config(
    page_title="🌱 Analizador Multi-Cultivo",
    page_icon="🌱",
    layout="wide"
)

st.title("🌱 ANALIZADOR MULTI-CULTIVO - SENTINEL 2 + ESRI")
st.markdown("---")

# Configuración para shapefiles
os.environ['SHAPE_RESTORE_SHX'] = 'YES'

# =============================================================================
# MAPAS BASE ESRI
# =============================================================================

MAPAS_BASE = {
    "ESRI Satélite": {
        "url": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        "attribution": "Esri, Maxar, Earthstar Geographics"
    },
    "ESRI Calles": {
        "url": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}",
        "attribution": "Esri, HERE, Garmin"
    },
    "OpenStreetMap": {
        "url": "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        "attribution": "OpenStreetMap contributors"
    }
}

# =============================================================================
# PARÁMETROS DE CULTIVOS
# =============================================================================

PARAMETROS_CULTIVOS = {
    'TRIGO': {'NITROGENO': {'min': 120, 'max': 180}, 'NDVI_OPTIMO': 0.7},
    'MAÍZ': {'NITROGENO': {'min': 150, 'max': 220}, 'NDVI_OPTIMO': 0.75},
    'SOJA': {'NITROGENO': {'min': 80, 'max': 120}, 'NDVI_OPTIMO': 0.65},
    'SORGO': {'NITROGENO': {'min': 100, 'max': 150}, 'NDVI_OPTIMO': 0.6},
    'GIRASOL': {'NITROGENO': {'min': 90, 'max': 130}, 'NDVI_OPTIMO': 0.55}
}

ICONOS_CULTIVOS = {
    'TRIGO': '🌾', 'MAÍZ': '🌽', 'SOJA': '🫘', 'SORGO': '🌾', 'GIRASOL': '🌻'
}

# =============================================================================
# FUNCIONES BÁSICAS
# =============================================================================

def crear_mapa_base(centro, zoom=12, mapa_seleccionado="ESRI Satélite"):
    """Crea mapa base con ESRI"""
    m = folium.Map(
        location=centro,
        zoom_start=zoom,
        tiles=MAPAS_BASE[mapa_seleccionado]["url"],
        attr=MAPAS_BASE[mapa_seleccionado]["attribution"],
        control_scale=True
    )
    return m

def calcular_superficie(gdf):
    """Calcula superficie en hectáreas"""
    try:
        if gdf.crs and gdf.crs.is_geographic:
            gdf_proj = gdf.to_crs('EPSG:3857')
            return gdf_proj.geometry.area / 10000
        return gdf.geometry.area / 10000
    except:
        return gdf.geometry.area / 10000

def dividir_parcela(gdf, n_zonas):
    """Divide parcela en zonas"""
    if len(gdf) == 0:
        return gdf
    
    try:
        parcela = gdf.iloc[0].geometry
        bounds = parcela.bounds
        minx, miny, maxx, maxy = bounds
        
        sub_poligonos = []
        n_cols = math.ceil(math.sqrt(n_zonas))
        n_rows = math.ceil(n_zonas / n_cols)
        
        width = (maxx - minx) / n_cols
        height = (maxy - miny) / n_rows
        
        for i in range(n_rows):
            for j in range(n_cols):
                if len(sub_poligonos) >= n_zonas:
                    break
                    
                cell = Polygon([
                    (minx + j * width, miny + i * height),
                    (minx + (j + 1) * width, miny + i * height),
                    (minx + (j + 1) * width, miny + (i + 1) * height),
                    (minx + j * width, miny + (i + 1) * height)
                ])
                
                intersection = parcela.intersection(cell)
                if not intersection.is_empty:
                    sub_poligonos.append(intersection)
        
        if sub_poligonos:
            return gpd.GeoDataFrame({
                'id_zona': range(1, len(sub_poligonos) + 1),
                'geometry': sub_poligonos
            }, crs=gdf.crs)
        return gdf
        
    except Exception as e:
        st.error(f"Error dividiendo parcela: {e}")
        return gdf

# =============================================================================
# SIDEBAR
# =============================================================================

with st.sidebar:
    st.header("⚙️ Configuración")
    
    # Cultivo y análisis
    cultivo = st.selectbox("🌱 Cultivo:", list(PARAMETROS_CULTIVOS.keys()))
    analisis_tipo = st.selectbox("📊 Tipo de Análisis:", 
                               ["FERTILIDAD ACTUAL", "RECOMENDACIONES NPK"])
    nutriente = st.selectbox("🧪 Nutriente:", ["NITRÓGENO", "FÓSFORO", "POTASIO"])
    
    # Configuración Sentinel
    st.subheader("🛰️ Configuración Satelital")
    fecha_imagen = st.date_input(
        "Fecha de imagen:",
        value=datetime.now() - timedelta(days=30),
        max_value=datetime.now()
    )
    
    # División de parcela
    st.subheader("📐 División de Parcela")
    n_divisiones = st.slider("Número de zonas:", 16, 48, 24)
    
    # Mapa base
    st.subheader("🗺️ Mapa Base")
    mapa_base = st.selectbox("Estilo de mapa:", list(MAPAS_BASE.keys()), index=0)
    
    # Carga de archivos
    st.subheader("📤 Cargar Parcela")
    uploaded_zip = st.file_uploader("Subir shapefile (ZIP):", type=['zip'])

# =============================================================================
# CONTENIDO PRINCIPAL
# =============================================================================

if uploaded_zip:
    with st.spinner("Cargando y procesando parcela..."):
        try:
            # Extraer y cargar shapefile
            with tempfile.TemporaryDirectory() as tmp_dir:
                with zipfile.ZipFile(uploaded_zip, 'r') as zip_ref:
                    zip_ref.extractall(tmp_dir)
                
                shp_files = [f for f in os.listdir(tmp_dir) if f.endswith('.shp')]
                if shp_files:
                    gdf = gpd.read_file(os.path.join(tmp_dir, shp_files[0]))
                    
                    # Información básica
                    area_total = calcular_superficie(gdf).sum()
                    centro = [gdf.geometry.centroid.y.mean(), gdf.geometry.centroid.x.mean()]
                    
                    st.success(f"✅ Parcela cargada: {len(gdf)} polígono(s), {area_total:.1f} ha")
                    
                    # Dividir parcela
                    gdf_dividido = dividir_parcela(gdf, n_divisiones)
                    
                    if gdf_dividido is not None:
                        st.info(f"📐 Parcela dividida en {len(gdf_dividido)} zonas")
                        
                        # Calcular áreas
                        areas_ha = calcular_superficie(gdf_dividido)
                        gdf_dividido['area_ha'] = areas_ha
                        
                        # Simular datos Sentinel 2
                        st.info("🛰️ Simulando datos Sentinel 2...")
                        
                        # Simulación de índices satelitales
                        np.random.seed(42)  # Para resultados consistentes
                        gdf_dividido['ndvi'] = np.random.uniform(0.3, 0.8, len(gdf_dividido))
                        gdf_dividido['ndre'] = gdf_dividido['ndvi'] * 0.8 + np.random.normal(0, 0.05, len(gdf_dividido))
                        gdf_dividido['biomasa_kg_ha'] = (gdf_dividido['ndvi'] * 2000).astype(int)
                        
                        # MOSTRAR RESULTADOS
                        st.header("📊 Resultados del Análisis")
                        
                        # Métricas principales
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("Zonas Analizadas", len(gdf_dividido))
                        with col2:
                            st.metric("Área Total", f"{area_total:.1f} ha")
                        with col3:
                            ndvi_prom = gdf_dividido['ndvi'].mean()
                            st.metric("NDVI Promedio", f"{ndvi_prom:.3f}")
                        with col4:
                            st.metric("Cultivo", cultivo)
                        
                        # MAPA INTERACTIVO CON ESRI
                        st.header("🗺️ Mapa de Resultados - ESRI")
                        
                        mapa = crear_mapa_base(centro, 13, mapa_base)
                        
                        # Agregar polígonos al mapa
                        for idx, row in gdf_dividido.iterrows():
                            ndvi = row['ndvi']
                            
                            # Color basado en NDVI
                            if ndvi < 0.4:
                                color = '#FF6B6B'  # Rojo - bajo
                            elif ndvi < 0.6:
                                color = '#FFD54F'  # Amarillo - medio
                            else:
                                color = '#66BB6A'  # Verde - alto
                            
                            tooltip = f"Zona {row['id_zona']}<br>NDVI: {ndvi:.3f}<br>Área: {row['area_ha']:.1f} ha<br>Biomasa: {row['biomasa_kg_ha']} kg/ha"
                            
                            folium.GeoJson(
                                row['geometry'],
                                style_function=lambda x, color=color: {
                                    'fillColor': color,
                                    'color': 'black',
                                    'weight': 1,
                                    'fillOpacity': 0.7
                                },
                                tooltip=tooltip
                            ).add_to(mapa)
                        
                        # Leyenda
                        legend_html = '''
                        <div style="position: fixed; top: 10px; right: 10px; background: white; 
                                    padding: 10px; border: 1px solid grey; z-index: 9999; border-radius: 5px;">
                            <h4 style="margin: 0 0 8px 0;">🌿 Leyenda NDVI</h4>
                            <p style="margin: 2px 0;"><span style="color: #FF6B6B">■</span> Bajo (< 0.4)</p>
                            <p style="margin: 2px 0;"><span style="color: #FFD54F">■</span> Medio (0.4-0.6)</p>
                            <p style="margin: 2px 0;"><span style="color: #66BB6A">■</span> Alto (> 0.6)</p>
                        </div>
                        '''
                        mapa.get_root().html.add_child(folium.Element(legend_html))
                        
                        folium_static(mapa, width=1000, height=600)
                        
                        # TABLA DE RESULTADOS
                        st.header("📋 Detalles por Zona")
                        
                        tabla = gdf_dividido[['id_zona', 'area_ha', 'ndvi', 'ndre', 'biomasa_kg_ha']].copy()
                        tabla.columns = ['Zona', 'Área (ha)', 'NDVI', 'NDRE', 'Biomasa (kg/ha)']
                        
                        st.dataframe(tabla, use_container_width=True)
                        
                        # DESCARGA
                        st.header("💾 Exportar Resultados")
                        
                        csv = tabla.to_csv(index=False)
                        st.download_button(
                            "📥 Descargar CSV",
                            csv,
                            f"analisis_{cultivo}_{datetime.now().strftime('%Y%m%d')}.csv",
                            "text/csv"
                        )
                        
                    else:
                        st.error("Error al dividir la parcela")
                else:
                    st.error("No se encontró archivo .shp en el ZIP")
                    
        except Exception as e:
            st.error(f"Error procesando archivo: {str(e)}")

else:
    # Pantalla de bienvenida
    st.info("📁 Sube un archivo ZIP con shapefile para comenzar el análisis")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🌱 Cultivos Soportados")
        for cultivo, icono in ICONOS_CULTIVOS.items():
            st.write(f"{icono} **{cultivo}**")
            params = PARAMETROS_CULTIVOS[cultivo]
            st.caption(f"N: {params['NITROGENO']['min']}-{params['NITROGENO']['max']} kg/ha")
    
    with col2:
        st.subheader("🛰️ Datos Satelitales")
        st.write("✅ **Simulación Sentinel 2**")
        st.write("✅ **Metodología GEE**")
        st.write("✅ **Mapas ESRI en tiempo real**")
        st.write("✅ **Análisis por zonas**")
    
    st.markdown("---")
    st.subheader("🚀 Cómo usar la aplicación:")
    st.write("1. **Sube** un ZIP con shapefile de tu parcela")
    st.write("2. **Configura** cultivo y parámetros en el sidebar")
    st.write("3. **Visualiza** resultados en mapas ESRI interactivos")
    st.write("4. **Descarga** los resultados en CSV")

st.markdown("---")
st.caption("🌱 Analizador Multi-Cultivo - Metodología GEE + ESRI")
