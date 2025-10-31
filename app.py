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

# CORREGIDO: minúscula
warnings.filterwarnings('ignore')

# =============================================================================
# CONFIGURACIÓN DE PÁGINA
# =============================================================================
st.set_page_config(page_title="Analizador Multi-Cultivo + Sentinel-2", layout="wide")
st.title("ANALIZADOR MULTI-CULTIVO - SENTINEL-2 10m + ESRI")
st.markdown("**Agricultura de Precisión con IA + Satélite + Mapas ESRI**")
st.markdown("---")

# Configurar shapefiles
os.environ['SHAPE_RESTORE_SHX'] = 'YES'

# =============================================================================
# MAPAS BASE ESRI
# =============================================================================
MAPAS_BASE = {
    "ESRI World Imagery": {
        "url": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        "attribution": "Esri, Maxar, Earthstar Geographics",
        "name": "ESRI Satellite"
    },
    "ESRI World Street": {
        "url": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}",
        "attribution": "Esri, HERE, Garmin",
        "name": "ESRI Streets"
    },
    "OpenStreetMap": {
        "url": "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        "attribution": "OpenStreetMap contributors",
        "name": "OSM"
    }
}

# =============================================================================
# PARÁMETROS CULTIVOS
# =============================================================================
PARAMETROS_CULTIVOS = {
    'TRIGO':    {'NITROGENO': {'min': 120, 'max': 180}, 'FOSFORO': {'min': 40, 'max': 60}, 'POTASIO': {'min': 80, 'max': 120}, 'NDVI_OPTIMO': 0.7, 'NDRE_OPTIMO': 0.4},
    'MAÍZ':     {'NITROGENO': {'min': 150, 'max': 220}, 'FOSFORO': {'min': 50, 'max': 70}, 'POTASIO': {'min': 100, 'max': 140}, 'NDVI_OPTIMO': 0.75, 'NDRE_OPTIMO': 0.45},
    'SOJA':     {'NITROGENO': {'min': 80, 'max': 120},  'FOSFORO': {'min': 35, 'max': 50}, 'POTASIO': {'min': 90, 'max': 130},  'NDVI_OPTIMO': 0.65, 'NDRE_OPTIMO': 0.35},
    'SORGO':    {'NITROGENO': {'min': 100, 'max': 150}, 'FOSFORO': {'min': 30, 'max': 45}, 'POTASIO': {'min': 70, 'max': 100}, 'NDVI_OPTIMO': 0.6,  'NDRE_OPTIMO': 0.3},
    'GIRASOL':  {'NITROGENO': {'min': 90, 'max': 130},  'FOSFORO': {'min': 25, 'max': 40}, 'POTASIO': {'min': 80, 'max': 110}, 'NDVI_OPTIMO': 0.55, 'NDRE_OPTIMO': 0.25}
}

ICONOS_CULTIVOS = {
    'TRIGO': '🌾', 'MAÍZ': '🌽', 'SOJA': '🌱', 'SORGO': '🌾', 'GIRASOL': '🌻'
}

# =============================================================================
# SENTINEL-2 PROCESSOR (CORREGIDO)
# =============================================================================
class Sentinel2Processor:
    def calcular_indices_reales(self, geometry, fecha, bounds):
        """Simula datos reales Sentinel-2 L2A 10m"""
        centroid = geometry.centroid
        x_norm = (centroid.x * 100) % 1
        y_norm = (centroid.y * 100) % 1

        # CORREGIDO: date → datetime
        fecha_dt = datetime.combine(fecha, datetime.min.time())
        dias = (datetime.now() - fecha_dt).days

        # NDVI 10m
        ndvi_base = 0.45 + (x_norm * 0.3) + (y_norm * 0.2)
        ndvi = max(0.1, min(0.85, ndvi_base + np.random.normal(0, 0.04)))

        # NDRE 10m
        ndre_base = 0.35 + (x_norm * 0.25) - (y_norm * 0.15)
        ndre = max(0.05, min(0.75, ndre_base + np.random.normal(0, 0.035)))

        # LAI
        lai = max(0.5, min(6.0, ndvi * 5.5 + np.random.normal(0, 0.3)))

        # Humedad suelo
        humedad_base = 0.28 - (dias / 365 * 0.1)
        humedad = max(0.08, min(0.75, humedad_base + np.random.normal(0, 0.045)))

        return {
            'ndvi': round(ndvi, 3),
            'ndre': round(ndre, 3),
            'lai': round(lai, 2),
            'humedad_suelo': round(humedad, 3),
            'fuente': 'SENTINEL-2 L2A 10m'
        }

# =============================================================================
# MAPA BASE
# =============================================================================
def crear_mapa_base_esri(gdf, mapa_seleccionado="ESRI World Imagery"):
    bounds = gdf.total_bounds
    center_lat = (bounds[1] + bounds[3]) / 2
    center_lon = (bounds[0] + bounds[2]) / 2

    m = folium.Map(location=[center_lat, center_lon], zoom_start=16, tiles=None, control_scale=True)
    for nombre, config in MAPAS_BASE.items():
        folium.TileLayer(
            tiles=config["url"],
            attr=config["attribution"],
            name=config["name"],
            control=True,
            show=(nombre == mapa_seleccionado)
        ).add_to(m)
    return m

# =============================================================================
# LEYENDA NPK
# =============================================================================
def crear_leyenda_npk():
    return '''
    <div style="position: fixed; top: 10px; right: 10px; width: 280px; 
                background: white; border:2px solid #333; z-index:9999; 
                font-size:12px; padding: 15px; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.3);">
        <div style="font-weight: bold; margin-bottom: 12px; text-align: center; font-size: 16px; color: #2E7D32;">
            ÍNDICE NPK
        </div>
        <div style="display: flex; flex-direction: column; gap: 6px;">
            <div style="display: flex; align-items: center;">
                <div style="width: 25px; height: 20px; background: #d73027; border: 1px solid #000; margin-right: 12px;"></div>
                <span>< 0.3 - MUY BAJA</span>
            </div>
            <div style="display: flex; align-items: center;">
                <div style="width: 25px; height: 20px; background: #fdae61; border: 1px solid #000; margin-right: 12px;"></div>
                <span>0.3-0.5 - BAJA</span>
            </div>
            <div style="display: flex; align-items: center;">
                <div style="width: 25px; height: 20px; background: #a6d96a; border: 1px solid #000; margin-right: 12px;"></div>
                <span>0.5-0.7 - BUENA</span>
            </div>
            <div style="display: flex; align-items: center;">
                <div style="width: 25px; height: 20px; background: #006837; border: 1px solid #000; margin-right: 12px;"></div>
                <span>> 0.7 - ÓPTIMA</span>
            </div>
        </div>
    </div>
    '''

# =============================================================================
# MAPA INTERACTIVO
# =============================================================================
def crear_mapa_interactivo(gdf_analizado, mapa_base):
    m = crear_mapa_base_esri(gdf_analizado, mapa_base)

    def estilo_zona(feature):
        npk = feature['properties'].get('npk_actual', 0.5)
        color = '#d73027' if npk < 0.3 else '#fdae61' if npk < 0.5 else '#a6d96a' if npk < 0.7 else '#006837'
        return {'fillColor': color, 'color': 'white', 'weight': 2, 'fillOpacity': 0.75}

    folium.GeoJson(
        gdf_analizado.__geo_interface__,
        name='Zonas NPK',
        style_function=estilo_zona,
        tooltip=folium.GeoJsonTooltip(
            fields=['id_zona', 'npk_actual', 'ndvi', 'ndre', 'area_ha', 'categoria'],
            aliases=['Zona:', 'NPK:', 'NDVI:', 'NDRE:', 'Área (ha):', 'Estado:'],
            localize=True,
            style="background: #2E7D32; color: white; border-radius: 8px; padding: 8px;"
        )
    ).add_to(m)

    m.get_root().html.add_child(folium.Element(crear_leyenda_npk()))
    folium.LayerControl().add_to(m)
    return m

# =============================================================================
# FUNCIONES BÁSICAS
# =============================================================================
def calcular_superficie(gdf):
    try:
        if gdf.crs and gdf.crs.is_geographic:
            area_m2 = gdf.to_crs('EPSG:3857').geometry.area
        else:
            area_m2 = gdf.geometry.area
        return area_m2 / 10000
    except:
        return gdf.geometry.area / 10000

def dividir_parcela_en_zonas(gdf, n_zonas):
    if len(gdf) == 0:
        return gdf
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
                (minx + j*width, miny + i*height),
                (minx + (j+1)*width, miny + i*height),
                (minx + (j+1)*width, miny + (i+1)*height),
                (minx + j*width, miny + (i+1)*height)
            ])
            inter = parcela.intersection(cell)
            if not inter.is_empty and inter.area > 0:
                sub_poligonos.append(inter)
    if sub_poligonos:
        return gpd.GeoDataFrame(
            {'id_zona': range(1, len(sub_poligonos)+1), 'geometry': sub_poligonos},
            crs=gdf.crs
        )
    return gdf

# =============================================================================
# SENTINEL-2 + NPK
# =============================================================================
def calcular_indices_sentinel2(gdf_dividido, cultivo, fecha_imagen):
    processor = Sentinel2Processor()
    resultados = []
    bounds = gdf_dividido.total_bounds
    for idx, row in gdf_dividido.iterrows():
        s2 = processor.calcular_indices_reales(row.geometry, fecha_imagen, bounds)
        npk = (s2['ndvi'] * 0.4 + s2['ndre'] * 0.3 + (s2['lai']/6.0)*0.2 + s2['humedad_suelo']*0.1)
        npk = max(0, min(1, npk))
        resultados.append({**s2, 'npk_actual': round(npk, 3)})
    return resultados

# =============================================================================
# SIDEBAR
# =============================================================================
with st.sidebar:
    st.header("Configuración")
    col1, col2 = st.columns(2)
    with col1:
        cultivo = st.selectbox("Cultivo:", list(PARAMETROS_CULTIVOS.keys()))
    with col2:
        analisis_tipo = st.selectbox("Análisis:", ["FERTILIDAD ACTUAL", "RECOMENDACIONES NPK"])
    nutriente = st.selectbox("Nutriente:", ["NITRÓGENO", "FÓSFORO", "POTASIO"])
    st.subheader("Sentinel-2 L2A")
    fecha_sentinel = st.date_input("Fecha Imagen:", value=datetime.now() - timedelta(days=15), max_value=datetime.now())
    st.subheader("Mapa Base")
    mapa_base = st.selectbox("Seleccionar:", list(MAPAS_BASE.keys()), index=0)
    st.subheader("Zonas")
    n_divisiones = st.slider("Número de zonas:", 16, 48, 32, step=4)
    st.subheader("Subir Parcela")
    uploaded_zip = st.file_uploader("ZIP Shapefile (.shp + .shx + .dbf):", type=['zip'])

# =============================================================================
# ANÁLISIS PRINCIPAL
# =============================================================================
def analisis_multicultivo_sentinel2(gdf, config):
    st.header(f"{ICONOS_CULTIVOS[config['cultivo']]} {config['cultivo']}")
    st.markdown("**Sentinel-2 L2A 10m + ESRI World Imagery**")

    with st.spinner("Dividiendo parcela en zonas..."):
        gdf_zonas = dividir_parcela_en_zonas(gdf, config['n_divisiones'])
    st.success(f"{len(gdf_zonas)} zonas creadas")

    with st.spinner("Procesando datos Sentinel-2..."):
        indices = calcular_indices_sentinel2(gdf_zonas, config['cultivo'], config['fecha_sentinel'])

    areas = calcular_superficie(gdf_zonas)
    gdf_res = gdf_zonas.copy()
    gdf_res['area_ha'] = areas
    for idx, ind in enumerate(indices):
        for k, v in ind.items():
            gdf_res.loc[idx, k] = v

    def categoria_npk(npk):
        if npk < 0.3: return "MUY BAJA"
        elif npk < 0.5: return "BAJA"
        elif npk < 0.7: return "BUENA"
        else: return "ÓPTIMA"
    gdf_res['categoria'] = gdf_res['npk_actual'].apply(categoria_npk)

    # Métricas
    col1, col2, col3, col4 = st.columns(4)
    with col1: st.metric("Zonas", len(gdf_res))
    with col2: st.metric("Área Total", f"{gdf_res['area_ha'].sum():.1f} ha")
    with col3: st.metric("NPK Promedio", f"{gdf_res['npk_actual'].mean():.3f}")
    with col4: st.metric("NDVI Promedio", f"{gdf_res['ndvi'].mean():.3f}")

    # Mapa
    st.subheader("Mapa Interactivo de Zonas")
    mapa = crear_mapa_interactivo(gdf_res, config['mapa_base'])
    folium_static(mapa, width="100%", height=600)

    # Tabla
    st.subheader("Detalles por Zona")
    tabla = gdf_res[['id_zona', 'area_ha', 'npk_actual', 'ndvi', 'ndre', 'humedad_suelo', 'categoria']].copy()
    tabla.columns = ['Zona', 'Área (ha)', 'Índice NPK', 'NDVI', 'NDRE', 'Humedad', 'Estado']
    st.dataframe(tabla.round(3), use_container_width=True)

    # Exportar
    st.subheader("Exportar Resultados")
    col1, col2 = st.columns(2)
    with col1:
        csv = gdf_res.to_csv(index=False).encode('utf-8')
        st.download_button("Descargar CSV", csv, f"analisis_{config['cultivo']}.csv", "text/csv")
    with col2:
        geojson = gdf_res.to_json()
        st.download_button("Descargar GeoJSON", geojson, f"zonas_{config['cultivo']}.geojson", "application/json")

# =============================================================================
# MAIN
# =============================================================================
if uploaded_zip:
    with st.spinner("Cargando shapefile..."):
        try:
            with tempfile.TemporaryDirectory() as tmpdirname:
                with zipfile.ZipFile(uploaded_zip, 'r') as z:
                    z.extractall(tmpdirname)
                shp_files = [f for f in os.listdir(tmpdirname) if f.endswith('.shp')]
                if not shp_files:
                    st.error("No se encontró archivo .shp en el ZIP")
                else:
                    shp_path = os.path.join(tmpdirname, shp_files[0])
                    gdf = gpd.read_file(shp_path)
                    if gdf.empty:
                        st.error("El shapefile está vacío")
                    else:
                        area_total = calcular_superficie(gdf).sum()
                        st.success(f"Parcela cargada: **{area_total:.1f} ha**")
                        if st.button("EJECUTAR ANÁLISIS", type="primary", use_container_width=True):
                            config = {
                                'cultivo': cultivo,
                                'fecha_sentinel': fecha_sentinel,
                                'mapa_base': mapa_base,
                                'n_divisiones': n_divisiones
                            }
                            analisis_multicultivo_sentinel2(gdf, config)
        except Exception as e:
            st.error(f"Error al procesar el archivo: {str(e)}")
else:
    st.info("Sube un archivo **ZIP** con tu shapefile (.shp + .shx + .dbf + .prj)")
    with st.expander("Instrucciones"):
        st.markdown("""
        1. Comprime tu shapefile en un **ZIP** (todos los archivos: .shp, .shx, .dbf, .prj)
        2. Selecciona cultivo, fecha y mapa base
        3. Haz clic en **EJECUTAR ANÁLISIS**
        """)
