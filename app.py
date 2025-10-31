import streamlit as st
import geopandas as gpd
import pandas as pd
import numpy as np
import tempfile
import os
import zipfile
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.colors import LinearSegmentedColormap
import io
from shapely.geometry import Polygon
import math
import warnings
warnings.filterwarnings('ignore')

# Configuración simple para evitar problemas de dependencias
try:
    from streamlit_folium import folium_static
    import folium
    FOLIUM_AVAILABLE = True
except ImportError:
    FOLIUM_AVAILABLE = False
    st.warning("Folium no está disponible. Las funciones de mapas interactivos estarán deshabilitadas.")

st.set_page_config(page_title="🌱 Analizador Multi-Cultivo", layout="wide")
st.title("🌱 ANALIZADOR MULTI-CULTIVO - METODOLOGÍA GEE")
st.markdown("---")

# Configurar para restaurar .shx automáticamente
os.environ['SHAPE_RESTORE_SHX'] = 'YES'

# PARÁMETROS GEE POR CULTIVO
PARAMETROS_CULTIVOS = {
    'TRIGO': {
        'NITROGENO': {'min': 120, 'max': 180},
        'FOSFORO': {'min': 40, 'max': 60},
        'POTASIO': {'min': 80, 'max': 120},
        'MATERIA_ORGANICA_OPTIMA': 3.5,
        'HUMEDAD_OPTIMA': 0.25,
        'NDVI_OPTIMO': 0.7,
        'NDRE_OPTIMO': 0.4
    },
    'MAÍZ': {
        'NITROGENO': {'min': 150, 'max': 220},
        'FOSFORO': {'min': 50, 'max': 70},
        'POTASIO': {'min': 100, 'max': 140},
        'MATERIA_ORGANICA_OPTIMA': 4.0,
        'HUMEDAD_OPTIMA': 0.3,
        'NDVI_OPTIMO': 0.75,
        'NDRE_OPTIMO': 0.45
    },
    'SOJA': {
        'NITROGENO': {'min': 80, 'max': 120},
        'FOSFORO': {'min': 35, 'max': 50},
        'POTASIO': {'min': 90, 'max': 130},
        'MATERIA_ORGANICA_OPTIMA': 3.8,
        'HUMEDAD_OPTIMA': 0.28,
        'NDVI_OPTIMO': 0.65,
        'NDRE_OPTIMO': 0.35
    },
    'SORGO': {
        'NITROGENO': {'min': 100, 'max': 150},
        'FOSFORO': {'min': 30, 'max': 45},
        'POTASIO': {'min': 70, 'max': 100},
        'MATERIA_ORGANICA_OPTIMA': 3.0,
        'HUMEDAD_OPTIMA': 0.22,
        'NDVI_OPTIMO': 0.6,
        'NDRE_OPTIMO': 0.3
    },
    'GIRASOL': {
        'NITROGENO': {'min': 90, 'max': 130},
        'FOSFORO': {'min': 25, 'max': 40},
        'POTASIO': {'min': 80, 'max': 110},
        'MATERIA_ORGANICA_OPTIMA': 3.2,
        'HUMEDAD_OPTIMA': 0.26,
        'NDVI_OPTIMO': 0.55,
        'NDRE_OPTIMO': 0.25
    }
}

# ICONOS POR CULTIVO
ICONOS_CULTIVOS = {
    'TRIGO': '🌾',
    'MAÍZ': '🌽', 
    'SOJA': '🫘',
    'SORGO': '🌾',
    'GIRASOL': '🌻'
}

# PALETAS GEE
PALETAS_GEE = {
    'FERTILIDAD': ['#d73027', '#f46d43', '#fdae61', '#fee08b', '#d9ef8b', '#a6d96a', '#66bd63', '#1a9850'],
    'NITROGENO': ['#00ff00', '#80ff00', '#ffff00', '#ff8000', '#ff0000'],
    'FOSFORO': ['#0000ff', '#4040ff', '#8080ff', '#c0c0ff', '#ffffff'],
    'POTASIO': ['#4B0082', '#6A0DAD', '#8A2BE2', '#9370DB', '#D8BFD8']
}

# Sidebar
with st.sidebar:
    st.header("⚙️ Configuración")
    
    cultivo = st.selectbox("Cultivo:", ["TRIGO", "MAÍZ", "SOJA", "SORGO", "GIRASOL"])
    
    analisis_tipo = st.selectbox("Tipo de Análisis:", ["FERTILIDAD ACTUAL", "RECOMENDACIONES NPK"])
    
    nutriente = st.selectbox("Nutriente:", ["NITRÓGENO", "FÓSFORO", "POTASIO"])
    
    st.subheader("🛰️ Datos Satelitales")
    usar_sentinel = st.checkbox("Simular datos Sentinel-2", value=True)
    
    st.subheader("🎯 División de Parcela")
    n_divisiones = st.slider("Número de zonas de manejo:", min_value=16, max_value=48, value=32)
    
    st.subheader("📤 Subir Parcela")
    uploaded_zip = st.file_uploader("Subir ZIP con shapefile de tu parcela", type=['zip'])

# Función para calcular superficie
def calcular_superficie(gdf):
    try:
        if gdf.crs and gdf.crs.is_geographic:
            # Convertir a un sistema de coordenadas proyectado para cálculo de área
            gdf_proj = gdf.to_crs('EPSG:3857')  # Web Mercator
            area_m2 = gdf_proj.geometry.area
        else:
            area_m2 = gdf.geometry.area
        return area_m2 / 10000  # Convertir a hectáreas
    except Exception as e:
        st.warning(f"Advertencia en cálculo de área: {e}")
        # Fallback: cálculo simple
        return gdf.geometry.area / 10000

# FUNCIÓN PARA DIVIDIR PARCELA
def dividir_parcela_en_zonas(gdf, n_zonas):
    if len(gdf) == 0:
        return gdf
    
    try:
        parcela_principal = gdf.iloc[0].geometry
        bounds = parcela_principal.bounds
        minx, miny, maxx, maxy = bounds
        
        sub_poligonos = []
        
        # Cuadrícula regular
        n_cols = math.ceil(math.sqrt(n_zonas))
        n_rows = math.ceil(n_zonas / n_cols)
        
        width = (maxx - minx) / n_cols
        height = (maxy - miny) / n_rows
        
        for i in range(n_rows):
            for j in range(n_cols):
                if len(sub_poligonos) >= n_zonas:
                    break
                    
                cell_minx = minx + (j * width)
                cell_maxx = minx + ((j + 1) * width)
                cell_miny = miny + (i * height)
                cell_maxy = miny + ((i + 1) * height)
                
                cell_poly = Polygon([
                    (cell_minx, cell_miny),
                    (cell_maxx, cell_miny),
                    (cell_maxx, cell_maxy),
                    (cell_minx, cell_maxy)
                ])
                
                intersection = parcela_principal.intersection(cell_poly)
                if not intersection.is_empty and intersection.area > 0:
                    sub_poligonos.append(intersection)
        
        if sub_poligonos:
            nuevo_gdf = gpd.GeoDataFrame({
                'id_zona': range(1, len(sub_poligonos) + 1),
                'geometry': sub_poligonos
            }, crs=gdf.crs)
            return nuevo_gdf
        else:
            return gdf
            
    except Exception as e:
        st.error(f"Error dividiendo parcela: {e}")
        return gdf

# SIMULACIÓN DE DATOS SENTINEL-2
def simular_datos_sentinel2(geometry):
    """Simula datos de Sentinel-2 Harmonizados"""
    try:
        centroid = geometry.centroid
        x_norm = (centroid.x * 100) % 1
        y_norm = (centroid.y * 100) % 1
        
        # Patrones espaciales realistas
        if x_norm < 0.2 or y_norm < 0.2:
            ndvi = 0.15 + np.random.normal(0, 0.03)
        elif x_norm > 0.7 and y_norm > 0.7:
            ndvi = 0.78 + np.random.normal(0, 0.02)
        else:
            ndvi = 0.52 + np.random.normal(0, 0.04)
        
        return {
            'ndvi': max(0.1, min(0.85, ndvi)),
            'ndre': max(0.05, min(0.7, ndvi * 0.8 + np.random.normal(0, 0.03))),
            'fuente': 'Sentinel-2 Simulado',
            'resolucion': '10m',
            'procesamiento': 'L2A'
        }
    except:
        return {
            'ndvi': 0.5,
            'ndre': 0.3,
            'fuente': 'Simulado',
            'resolucion': '10m',
            'procesamiento': 'L2A'
        }

# CÁLCULO DE ÍNDICES SATELITALES
def calcular_indices_satelitales_gee(gdf, cultivo, usar_sentinel=True):
    n_poligonos = len(gdf)
    resultados = []
    
    # Obtener centroides para gradiente espacial
    gdf_centroids = gdf.copy()
    gdf_centroids['centroid'] = gdf_centroids.geometry.centroid
    gdf_centroids['x'] = gdf_centroids.centroid.x
    gdf_centroids['y'] = gdf_centroids.centroid.y
    
    x_coords = gdf_centroids['x'].tolist()
    y_coords = gdf_centroids['y'].tolist()
    
    x_min, x_max = min(x_coords), max(x_coords)
    y_min, y_max = min(y_coords), max(y_coords)
    
    # Parámetros específicos del cultivo
    params = PARAMETROS_CULTIVOS[cultivo]
    
    for idx, row in gdf_centroids.iterrows():
        # Obtener datos Sentinel-2 si está habilitado
        datos_sentinel = None
        if usar_sentinel:
            datos_sentinel = simular_datos_sentinel2(row.geometry)
        
        # Normalizar posición para variación espacial
        x_norm = (row['x'] - x_min) / (x_max - x_min) if x_max != x_min else 0.5
        y_norm = (row['y'] - y_min) / (y_max - y_min) if y_max != y_min else 0.5
        
        patron_espacial = (x_norm * 0.6 + y_norm * 0.4)
        
        # Usar datos Sentinel-2 si están disponibles
        if datos_sentinel and datos_sentinel['fuente'] == 'Sentinel-2 Simulado':
            ndvi = datos_sentinel['ndvi']
            ndre = datos_sentinel['ndre']
            fuente = "Sentinel-2 Simulado"
            
            # Calcular otros parámetros basados en NDVI
            materia_organica = params['MATERIA_ORGANICA_OPTIMA'] * (0.7 + ndvi * 0.4)
            humedad_suelo = params['HUMEDAD_OPTIMA'] * (0.8 + ndvi * 0.3)
            
        else:
            # Simulación tradicional
            fuente = "Simulado"
            
            base_mo = params['MATERIA_ORGANICA_OPTIMA'] * 0.7
            variabilidad_mo = patron_espacial * (params['MATERIA_ORGANICA_OPTIMA'] * 0.6)
            materia_organica = base_mo + variabilidad_mo + np.random.normal(0, 0.2)
            
            base_humedad = params['HUMEDAD_OPTIMA'] * 0.8
            variabilidad_humedad = patron_espacial * (params['HUMEDAD_OPTIMA'] * 0.4)
            humedad_suelo = base_humedad + variabilidad_humedad + np.random.normal(0, 0.05)
            
            ndvi_base = params['NDVI_OPTIMO'] * 0.6
            ndvi_variacion = patron_espacial * (params['NDVI_OPTIMO'] * 0.5)
            ndvi = ndvi_base + ndvi_variacion + np.random.normal(0, 0.06)
            
            ndre_base = params['NDRE_OPTIMO'] * 0.7
            ndre_variacion = patron_espacial * (params['NDRE_OPTIMO'] * 0.4)
            ndre = ndre_base + ndre_variacion + np.random.normal(0, 0.04)
        
        # Asegurar límites
        materia_organica = max(0.5, min(8.0, materia_organica))
        humedad_suelo = max(0.1, min(0.8, humedad_suelo))
        ndvi = max(0.1, min(0.9, ndvi))
        ndre = max(0.05, min(0.7, ndre))
        
        # ÍNDICE NPK ACTUAL
        npk_actual = (ndvi * 0.4) + (ndre * 0.3) + ((materia_organica / 8) * 0.2) + (humedad_suelo * 0.1)
        npk_actual = max(0, min(1, npk_actual))
        
        resultados.append({
            'materia_organica': round(materia_organica, 2),
            'humedad_suelo': round(humedad_suelo, 3),
            'ndvi': round(ndvi, 3),
            'ndre': round(ndre, 3),
            'npk_actual': round(npk_actual, 3),
            'fuente_datos': fuente
        })
    
    return resultados

# FUNCIÓN PARA RECOMENDACIONES NPK
def calcular_recomendaciones_npk_gee(indices, nutriente, cultivo):
    recomendaciones = []
    params = PARAMETROS_CULTIVOS[cultivo]
    
    for idx in indices:
        ndre = idx['ndre']
        materia_organica = idx['materia_organica']
        humedad_suelo = idx['humedad_suelo']
        ndvi = idx['ndvi']
        
        if nutriente == "NITRÓGENO":
            factor_n = ((1 - ndre) * 0.6 + (1 - ndvi) * 0.4)
            n_recomendado = (factor_n * 
                           (params['NITROGENO']['max'] - params['NITROGENO']['min']) + 
                           params['NITROGENO']['min'])
            n_recomendado = max(params['NITROGENO']['min'] * 0.8, 
                              min(params['NITROGENO']['max'] * 1.2, n_recomendado))
            recomendaciones.append(round(n_recomendado, 1))
            
        elif nutriente == "FÓSFORO":
            factor_p = ((1 - (materia_organica / 8)) * 0.7 + (1 - humedad_suelo) * 0.3)
            p_recomendado = (factor_p * 
                           (params['FOSFORO']['max'] - params['FOSFORO']['min']) + 
                           params['FOSFORO']['min'])
            p_recomendado = max(params['FOSFORO']['min'] * 0.8, 
                              min(params['FOSFORO']['max'] * 1.2, p_recomendado))
            recomendaciones.append(round(p_recomendado, 1))
            
        else:  # POTASIO
            factor_k = ((1 - ndre) * 0.4 + (1 - humedad_suelo) * 0.4 + (1 - (materia_organica / 8)) * 0.2)
            k_recomendado = (factor_k * 
                           (params['POTASIO']['max'] - params['POTASIO']['min']) + 
                           params['POTASIO']['min'])
            k_recomendado = max(params['POTASIO']['min'] * 0.8, 
                              min(params['POTASIO']['max'] * 1.2, k_recomendado))
            recomendaciones.append(round(k_recomendado, 1))
    
    return recomendaciones

# FUNCIÓN PARA CREAR MAPA GEE
def crear_mapa_gee(gdf, nutriente, analisis_tipo, cultivo):
    try:
        fig, ax = plt.subplots(1, 1, figsize=(12, 8))
        
        # Seleccionar paleta según el análisis
        if analisis_tipo == "FERTILIDAD ACTUAL":
            cmap = LinearSegmentedColormap.from_list('fertilidad_gee', PALETAS_GEE['FERTILIDAD'])
            vmin, vmax = 0, 1
            columna = 'npk_actual'
            titulo_sufijo = 'Índice NPK Actual (0-1)'
        else:
            if nutriente == "NITRÓGENO":
                cmap = LinearSegmentedColormap.from_list('nitrogeno_gee', PALETAS_GEE['NITROGENO'])
                vmin, vmax = (PARAMETROS_CULTIVOS[cultivo]['NITROGENO']['min'] * 0.8, 
                            PARAMETROS_CULTIVOS[cultivo]['NITROGENO']['max'] * 1.2)
            elif nutriente == "FÓSFORO":
                cmap = LinearSegmentedColormap.from_list('fosforo_gee', PALETAS_GEE['FOSFORO'])
                vmin, vmax = (PARAMETROS_CULTIVOS[cultivo]['FOSFORO']['min'] * 0.8, 
                            PARAMETROS_CULTIVOS[cultivo]['FOSFORO']['max'] * 1.2)
            else:
                cmap = LinearSegmentedColormap.from_list('potasio_gee', PALETAS_GEE['POTASIO'])
                vmin, vmax = (PARAMETROS_CULTIVOS[cultivo]['POTASIO']['min'] * 0.8, 
                            PARAMETROS_CULTIVOS[cultivo]['POTASIO']['max'] * 1.2)
            
            columna = 'valor_recomendado'
            titulo_sufijo = f'Recomendación {nutriente} (kg/ha)'
        
        # Plotear cada polígono
        for idx, row in gdf.iterrows():
            valor = row[columna]
            valor_norm = (valor - vmin) / (vmax - vmin)
            valor_norm = max(0, min(1, valor_norm))
            color = cmap(valor_norm)
            
            gdf.iloc[[idx]].plot(ax=ax, color=color, edgecolor='black', linewidth=1)
            
            # Etiqueta con valor
            centroid = row.geometry.centroid
            ax.annotate(f"Z{row['id_zona']}\n{valor:.1f}", (centroid.x, centroid.y), 
                       xytext=(3, 3), textcoords="offset points", 
                       fontsize=6, color='black', weight='bold',
                       bbox=dict(boxstyle="round,pad=0.2", facecolor='white', alpha=0.8))
        
        # Configuración del mapa
        ax.set_title(f'{ICONOS_CULTIVOS[cultivo]} ANÁLISIS GEE - {cultivo}\n{analisis_tipo}', 
                    fontsize=14, fontweight='bold', pad=15)
        
        ax.set_xlabel('Longitud')
        ax.set_ylabel('Latitud')
        ax.grid(True, alpha=0.3)
        
        # Barra de colores
        sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(vmin=vmin, vmax=vmax))
        sm.set_array([])
        cbar = plt.colorbar(sm, ax=ax, shrink=0.8)
        cbar.set_label(titulo_sufijo, fontsize=10, fontweight='bold')
        
        plt.tight_layout()
        
        # Convertir a imagen
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=120, bbox_inches='tight')
        buf.seek(0)
        plt.close()
        
        return buf
        
    except Exception as e:
        st.error(f"❌ Error creando mapa: {str(e)}")
        return None

# FUNCIÓN PRINCIPAL DE ANÁLISIS
def analisis_gee_completo(gdf, nutriente, analisis_tipo, n_divisiones, cultivo, usar_sentinel):
    try:
        st.header(f"{ICONOS_CULTIVOS[cultivo]} ANÁLISIS {cultivo} - METODOLOGÍA GEE")
        
        if usar_sentinel:
            st.success("🛰️ Usando simulación de datos Sentinel-2 Harmonizados")
        else:
            st.info("📊 Usando datos simulados tradicionales")
        
        # DIVIDIR PARCELA
        st.subheader("📐 DIVIDIENDO PARCELA")
        with st.spinner("Dividiendo parcela..."):
            gdf_dividido = dividir_parcela_en_zonas(gdf, n_divisiones)
        
        st.success(f"✅ Parcela dividida en {len(gdf_dividido)} zonas")
        
        # Calcular áreas
        areas_ha = calcular_superficie(gdf_dividido)
        area_total = areas_ha.sum()
        
        # CALCULAR ÍNDICES
        st.subheader("🛰️ CALCULANDO ÍNDICES SATELITALES")
        with st.spinner(f"Ejecutando análisis para {cultivo}..."):
            indices_gee = calcular_indices_satelitales_gee(gdf_dividido, cultivo, usar_sentinel)
        
        # Crear dataframe con resultados
        gdf_analizado = gdf_dividido.copy()
        gdf_analizado['area_ha'] = areas_ha
        
        # Añadir índices GEE
        for idx, indice in enumerate(indices_gee):
            for key, value in indice.items():
                gdf_analizado.loc[gdf_analizado.index[idx], key] = value
        
        # CALCULAR RECOMENDACIONES
        if analisis_tipo == "RECOMENDACIONES NPK":
            with st.spinner("Calculando recomendaciones NPK..."):
                recomendaciones = calcular_recomendaciones_npk_gee(indices_gee, nutriente, cultivo)
                gdf_analizado['valor_recomendado'] = recomendaciones
                columna_valor = 'valor_recomendado'
        else:
            columna_valor = 'npk_actual'
        
        # CATEGORIZAR
        def categorizar_gee(valor, nutriente, analisis_tipo, cultivo):
            params = PARAMETROS_CULTIVOS[cultivo]
            
            if analisis_tipo == "FERTILIDAD ACTUAL":
                if valor < 0.3: return "MUY BAJA"
                elif valor < 0.5: return "BAJA"
                elif valor < 0.6: return "MEDIA"
                elif valor < 0.7: return "BUENA"
                else: return "ÓPTIMA"
            else:
                if nutriente == "NITRÓGENO":
                    rango = params['NITROGENO']['max'] - params['NITROGENO']['min']
                    if valor < params['NITROGENO']['min'] + 0.2 * rango: return "MUY BAJO"
                    elif valor < params['NITROGENO']['min'] + 0.4 * rango: return "BAJO"
                    elif valor < params['NITROGENO']['min'] + 0.6 * rango: return "MEDIO"
                    elif valor < params['NITROGENO']['min'] + 0.8 * rango: return "ALTO"
                    else: return "MUY ALTO"
                elif nutriente == "FÓSFORO":
                    rango = params['FOSFORO']['max'] - params['FOSFORO']['min']
                    if valor < params['FOSFORO']['min'] + 0.2 * rango: return "MUY BAJO"
                    elif valor < params['FOSFORO']['min'] + 0.4 * rango: return "BAJO"
                    elif valor < params['FOSFORO']['min'] + 0.6 * rango: return "MEDIO"
                    elif valor < params['FOSFORO']['min'] + 0.8 * rango: return "ALTO"
                    else: return "MUY ALTO"
                else:
                    rango = params['POTASIO']['max'] - params['POTASIO']['min']
                    if valor < params['POTASIO']['min'] + 0.2 * rango: return "MUY BAJO"
                    elif valor < params['POTASIO']['min'] + 0.4 * rango: return "BAJO"
                    elif valor < params['POTASIO']['min'] + 0.6 * rango: return "MEDIO"
                    elif valor < params['POTASIO']['min'] + 0.8 * rango: return "ALTO"
                    else: return "MUY ALTO"
        
        gdf_analizado['categoria'] = [
            categorizar_gee(row[columna_valor], nutriente, analisis_tipo, cultivo) 
            for idx, row in gdf_analizado.iterrows()
        ]
        
        # MOSTRAR RESULTADOS
        st.subheader("📊 RESULTADOS DEL ANÁLISIS")
        
        # Estadísticas principales
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Zonas Analizadas", len(gdf_analizado))
        with col2:
            st.metric("Área Total", f"{area_total:.1f} ha")
        with col3:
            if analisis_tipo == "FERTILIDAD ACTUAL":
                valor_prom = gdf_analizado['npk_actual'].mean()
                st.metric("Índice NPK Promedio", f"{valor_prom:.3f}")
            else:
                valor_prom = gdf_analizado['valor_recomendado'].mean()
                st.metric(f"{nutriente} Promedio", f"{valor_prom:.1f} kg/ha")
        with col4:
            coef_var = (gdf_analizado[columna_valor].std() / gdf_analizado[columna_valor].mean() * 100)
            st.metric("Coef. Variación", f"{coef_var:.1f}%")
        
        # MAPA GEE
        st.subheader("🗺️ MAPA DE RESULTADOS")
        mapa_buffer = crear_mapa_gee(gdf_analizado, nutriente, analisis_tipo, cultivo)
        if mapa_buffer:
            st.image(mapa_buffer, use_container_width=True)
            
            st.download_button(
                "📥 Descargar Mapa",
                mapa_buffer,
                f"mapa_gee_{cultivo}_{analisis_tipo.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M')}.png",
                "image/png"
            )
        
        # TABLA DE RESULTADOS
        st.subheader("📋 DETALLES POR ZONA")
        
        columnas_indices = ['id_zona', 'npk_actual', 'materia_organica', 'ndvi', 'ndre', 'humedad_suelo', 'categoria']
        if analisis_tipo == "RECOMENDACIONES NPK":
            columnas_indices.insert(2, 'valor_recomendado')
        
        tabla_indices = gdf_analizado[columnas_indices].copy()
        tabla_indices.columns = ['Zona', 'NPK Actual'] + (['Recomendación'] if analisis_tipo == "RECOMENDACIONES NPK" else []) + [
            'Materia Org (%)', 'NDVI', 'NDRE', 'Humedad', 'Categoría'
        ]
        
        st.dataframe(tabla_indices, use_container_width=True)
        
        # DESCARGA
        st.subheader("📥 DESCARGAR RESULTADOS")
        
        csv = gdf_analizado.to_csv(index=False)
        st.download_button(
            "📋 Descargar CSV",
            csv,
            f"analisis_gee_{cultivo}_{analisis_tipo.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            "text/csv"
        )
        
        return True
        
    except Exception as e:
        st.error(f"❌ Error en análisis: {str(e)}")
        return False

# INTERFAZ PRINCIPAL
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
                    
                    st.success(f"✅ **Parcela cargada:** {len(gdf)} polígono(s)")
                    
                    # Información de la parcela
                    area_total = calcular_superficie(gdf).sum()
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write("**📊 INFORMACIÓN DE LA PARCELA:**")
                        st.write(f"- Polígonos: {len(gdf)}")
                        st.write(f"- Área total: {area_total:.1f} ha")
                        st.write(f"- CRS: {gdf.crs}")
                    
                    with col2:
                        st.write("**🎯 CONFIGURACIÓN:**")
                        st.write(f"- Cultivo: {ICONOS_CULTIVOS[cultivo]} {cultivo}")
                        st.write(f"- Análisis: {analisis_tipo}")
                        st.write(f"- Nutriente: {nutriente}")
                        st.write(f"- Zonas: {n_divisiones}")
                        st.write(f"- Datos: {'Sentinel-2 Simulado' if usar_sentinel else 'Tradicional'}")
                    
                    # EJECUTAR ANÁLISIS
                    if st.button("🚀 EJECUTAR ANÁLISIS GEE", type="primary"):
                        analisis_gee_completo(gdf, nutriente, analisis_tipo, n_divisiones, cultivo, usar_sentinel)
                        
        except Exception as e:
            st.error(f"Error cargando shapefile: {str(e)}")

else:
    st.info("📁 Sube el ZIP de tu parcela para comenzar el análisis")
    
    with st.expander("ℹ️ INFORMACIÓN SOBRE LA METODOLOGÍA"):
        st.markdown("""
        **🌱 SISTEMA DE ANÁLISIS MULTI-CULTIVO (GEE)**
        
        **📊 CULTIVOS SOPORTADOS:**
        - **🌾 TRIGO, 🌽 MAÍZ, 🫘 SOJA, 🌾 SORGO, 🌻 GIRASOL**
        
        **🚀 FUNCIONALIDADES:**
        - **🌱 Fertilidad Actual:** Estado NPK del suelo
        - **💊 Recomendaciones NPK:** Dosis específicas por cultivo
        - **🛰️ Datos Satelitales:** Simulación Sentinel-2 Harmonizados
        - **🎯 Agricultura Precisión:** Mapas por zonas de manejo
        
        **🔬 METODOLOGÍA:**
        - Análisis basado en índices de vegetación
        - Parámetros específicos para cada cultivo
        - Cálculo de recomendaciones científicas
        """)
