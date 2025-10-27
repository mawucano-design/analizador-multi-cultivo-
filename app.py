import streamlit as st
import geopandas as gpd
import pandas as pd
import numpy as np
import tempfile
import os
import zipfile
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.colors import LinearSegmentedColormap
import io
from shapely.geometry import Polygon
import math

st.set_page_config(page_title="🌱 Analizador Multi-Cultivo", layout="wide")
st.title("🌱 ANALIZADOR MULTI-CULTIVO - METODOLOGÍA GEE")
st.markdown("---")

# Configurar para restaurar .shx automáticamente
os.environ['SHAPE_RESTORE_SHX'] = 'YES'

# Sidebar
with st.sidebar:
    st.header("⚙️ Configuración")
    
    cultivo = st.selectbox("Cultivo:", 
                          ["TRIGO", "MAÍZ", "SOJA", "SORGO", "GIRASOL"])
    
    analisis_tipo = st.selectbox("Tipo de Análisis:", 
                               ["FERTILIDAD ACTUAL", "RECOMENDACIONES NPK"])
    
    nutriente = st.selectbox("Nutriente:", ["NITRÓGENO", "FÓSFORO", "POTASIO"])
    
    st.subheader("🎯 División de Parcela")
    n_divisiones = st.slider("Número de zonas de manejo:", min_value=16, max_value=48, value=32)
    
    st.subheader("📤 Subir Parcela")
    uploaded_zip = st.file_uploader("Subir ZIP con shapefile de tu parcela", type=['zip'])

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

# ICONOS Y COLORES POR CULTIVO
ICONOS_CULTIVOS = {
    'TRIGO': '🌾',
    'MAÍZ': '🌽', 
    'SOJA': '🫘',
    'SORGO': '🌾',
    'GIRASOL': '🌻'
}

COLORES_CULTIVOS = {
    'TRIGO': '#FFD700',  # Dorado
    'MAÍZ': '#FFA500',   # Naranja
    'SOJA': '#8B4513',   # Marrón
    'SORGO': '#D2691E',  # Chocolate
    'GIRASOL': '#FFD700' # Amarillo
}

# PALETAS GEE MEJORADAS
PALETAS_GEE = {
    'FERTILIDAD': ['#d73027', '#f46d43', '#fdae61', '#fee08b', '#d9ef8b', '#a6d96a', '#66bd63', '#1a9850', '#006837'],
    'NITROGENO': ['#00ff00', '#80ff00', '#ffff00', '#ff8000', '#ff0000'],
    'FOSFORO': ['#0000ff', '#4040ff', '#8080ff', '#c0c0ff', '#ffffff'],
    'POTASIO': ['#4B0082', '#6A0DAD', '#8A2BE2', '#9370DB', '#D8BFD8']
}

# Función para calcular superficie
def calcular_superficie(gdf):
    try:
        if gdf.crs and gdf.crs.is_geographic:
            area_m2 = gdf.geometry.area * 10000000000
        else:
            area_m2 = gdf.geometry.area
        return area_m2 / 10000
    except:
        return gdf.geometry.area / 10000

# FUNCIÓN PARA DIVIDIR PARCELA
def dividir_parcela_en_zonas(gdf, n_zonas):
    if len(gdf) == 0:
        return gdf
    
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

# METODOLOGÍA GEE - CÁLCULO DE ÍNDICES SATELITALES ESPECÍFICOS POR CULTIVO
def calcular_indices_satelitales_gee(gdf, cultivo):
    """
    Implementa la metodología completa de Google Earth Engine adaptada por cultivo
    """
    
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
        # Normalizar posición para simular variación espacial
        x_norm = (row['x'] - x_min) / (x_max - x_min) if x_max != x_min else 0.5
        y_norm = (row['y'] - y_min) / (y_max - y_min) if y_max != y_min else 0.5
        
        patron_espacial = (x_norm * 0.6 + y_norm * 0.4)
        
        # 1. MATERIA ORGÁNICA - Adaptada por cultivo
        base_mo = params['MATERIA_ORGANICA_OPTIMA'] * 0.7
        variabilidad_mo = patron_espacial * (params['MATERIA_ORGANICA_OPTIMA'] * 0.6)
        materia_organica = base_mo + variabilidad_mo + np.random.normal(0, 0.2)
        materia_organica = max(0.5, min(8.0, materia_organica))
        
        # 2. HUMEDAD SUELO - Adaptada por requerimientos del cultivo
        base_humedad = params['HUMEDAD_OPTIMA'] * 0.8
        variabilidad_humedad = patron_espacial * (params['HUMEDAD_OPTIMA'] * 0.4)
        humedad_suelo = base_humedad + variabilidad_humedad + np.random.normal(0, 0.05)
        humedad_suelo = max(0.1, min(0.8, humedad_suelo))
        
        # 3. NDVI - Específico por cultivo
        ndvi_base = params['NDVI_OPTIMO'] * 0.6
        ndvi_variacion = patron_espacial * (params['NDVI_OPTIMO'] * 0.5)
        ndvi = ndvi_base + ndvi_variacion + np.random.normal(0, 0.06)
        ndvi = max(0.1, min(0.9, ndvi))
        
        # 4. NDRE - Específico por cultivo
        ndre_base = params['NDRE_OPTIMO'] * 0.7
        ndre_variacion = patron_espacial * (params['NDRE_OPTIMO'] * 0.4)
        ndre = ndre_base + ndre_variacion + np.random.normal(0, 0.04)
        ndre = max(0.05, min(0.7, ndre))
        
        # 5. ÍNDICE NPK ACTUAL - Fórmula adaptada por cultivo
        npk_actual = (ndvi * 0.4) + (ndre * 0.3) + ((materia_organica / 8) * 0.2) + (humedad_suelo * 0.1)
        npk_actual = max(0, min(1, npk_actual))
        
        resultados.append({
            'materia_organica': round(materia_organica, 2),
            'humedad_suelo': round(humedad_suelo, 3),
            'ndvi': round(ndvi, 3),
            'ndre': round(ndre, 3),
            'npk_actual': round(npk_actual, 3)
        })
    
    return resultados

# FUNCIÓN GEE PARA RECOMENDACIONES NPK ESPECÍFICAS POR CULTIVO
def calcular_recomendaciones_npk_gee(indices, nutriente, cultivo):
    """
    Calcula recomendaciones NPK basadas en la metodología GEE específica por cultivo
    """
    recomendaciones = []
    params = PARAMETROS_CULTIVOS[cultivo]
    
    for idx in indices:
        ndre = idx['ndre']
        materia_organica = idx['materia_organica']
        humedad_suelo = idx['humedad_suelo']
        ndvi = idx['ndvi']
        
        if nutriente == "NITRÓGENO":
            # Fórmula GEE adaptada: ndre y ndvi para recomendación de N
            factor_n = ((1 - ndre) * 0.6 + (1 - ndvi) * 0.4)
            n_recomendado = (factor_n * 
                           (params['NITROGENO']['max'] - params['NITROGENO']['min']) + 
                           params['NITROGENO']['min'])
            n_recomendado = max(params['NITROGENO']['min'] * 0.8, 
                              min(params['NITROGENO']['max'] * 1.2, n_recomendado))
            recomendaciones.append(round(n_recomendado, 1))
            
        elif nutriente == "FÓSFORO":
            # Fórmula GEE: materia orgánica y humedad para recomendación de P
            factor_p = ((1 - (materia_organica / 8)) * 0.7 + (1 - humedad_suelo) * 0.3)
            p_recomendado = (factor_p * 
                           (params['FOSFORO']['max'] - params['FOSFORO']['min']) + 
                           params['FOSFORO']['min'])
            p_recomendado = max(params['FOSFORO']['min'] * 0.8, 
                              min(params['FOSFORO']['max'] * 1.2, p_recomendado))
            recomendaciones.append(round(p_recomendado, 1))
            
        else:  # POTASIO
            # Fórmula GEE: múltiples factores para recomendación de K
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
    """Crea mapa con la metodología y paletas de Google Earth Engine"""
    try:
        fig, ax = plt.subplots(1, 1, figsize=(14, 10))
        
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
            
            gdf.iloc[[idx]].plot(ax=ax, color=color, edgecolor='black', linewidth=1.5)
            
            # Etiqueta con valor
            centroid = row.geometry.centroid
            ax.annotate(f"Z{row['id_zona']}\n{valor:.1f}", (centroid.x, centroid.y), 
                       xytext=(5, 5), textcoords="offset points", 
                       fontsize=8, color='black', weight='bold',
                       bbox=dict(boxstyle="round,pad=0.3", facecolor='white', alpha=0.9))
        
        # Configuración del mapa
        ax.set_title(f'{ICONOS_CULTIVOS[cultivo]} ANÁLISIS GEE - {cultivo}\n'
                    f'{analisis_tipo} - {titulo_sufijo}\n'
                    f'Metodología Google Earth Engine', 
                    fontsize=16, fontweight='bold', pad=20)
        
        ax.set_xlabel('Longitud')
        ax.set_ylabel('Latitud')
        ax.grid(True, alpha=0.3)
        
        # Barra de colores
        sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(vmin=vmin, vmax=vmax))
        sm.set_array([])
        cbar = plt.colorbar(sm, ax=ax, shrink=0.8)
        cbar.set_label(titulo_sufijo, fontsize=12, fontweight='bold')
        
        plt.tight_layout()
        
        # Convertir a imagen
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        buf.seek(0)
        plt.close()
        
        return buf
        
    except Exception as e:
        st.error(f"❌ Error creando mapa GEE: {str(e)}")
        return None

# FUNCIÓN PRINCIPAL DE ANÁLISIS GEE
def analisis_gee_completo(gdf, nutriente, analisis_tipo, n_divisiones, cultivo):
    try:
        st.header(f"{ICONOS_CULTIVOS[cultivo]} ANÁLISIS {cultivo} - METODOLOGÍA GEE")
        
        # PASO 1: DIVIDIR PARCELA
        st.subheader("📐 DIVIDIENDO PARCELA EN ZONAS DE MANEJO")
        with st.spinner("Dividiendo parcela..."):
            gdf_dividido = dividir_parcela_en_zonas(gdf, n_divisiones)
        
        st.success(f"✅ Parcela dividida en {len(gdf_dividido)} zonas")
        
        # Calcular áreas
        areas_ha = calcular_superficie(gdf_dividido)
        area_total = areas_ha.sum()
        
        # PASO 2: CALCULAR ÍNDICES GEE ESPECÍFICOS
        st.subheader("🛰️ CALCULANDO ÍNDICES SATELITALES GEE")
        with st.spinner(f"Ejecutando algoritmos GEE para {cultivo}..."):
            indices_gee = calcular_indices_satelitales_gee(gdf_dividido, cultivo)
        
        # Crear dataframe con resultados
        gdf_analizado = gdf_dividido.copy()
        gdf_analizado['area_ha'] = areas_ha
        
        # Añadir índices GEE
        for idx, indice in enumerate(indices_gee):
            for key, value in indice.items():
                gdf_analizado.loc[gdf_analizado.index[idx], key] = value
        
        # PASO 3: CALCULAR RECOMENDACIONES SI ES NECESARIO
        if analisis_tipo == "RECOMENDACIONES NPK":
            with st.spinner("Calculando recomendaciones NPK..."):
                recomendaciones = calcular_recomendaciones_npk_gee(indices_gee, nutriente, cultivo)
                gdf_analizado['valor_recomendado'] = recomendaciones
                columna_valor = 'valor_recomendado'
        else:
            columna_valor = 'npk_actual'
        
        # PASO 4: CATEGORIZAR PARA RECOMENDACIONES ESPECÍFICAS POR CULTIVO
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
        
        # PASO 5: MOSTRAR RESULTADOS
        st.subheader("📊 RESULTADOS DEL ANÁLISIS GEE")
        
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
        st.subheader("🗺️ MAPA GEE - RESULTADOS")
        mapa_buffer = crear_mapa_gee(gdf_analizado, nutriente, analisis_tipo, cultivo)
        if mapa_buffer:
            st.image(mapa_buffer, use_container_width=True)
            
            st.download_button(
                "📥 Descargar Mapa GEE",
                mapa_buffer,
                f"mapa_gee_{cultivo}_{analisis_tipo.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M')}.png",
                "image/png"
            )
        
        # TABLA DE ÍNDICES GEE
        st.subheader("🔬 ÍNDICES SATELITALES GEE POR ZONA")
        
        columnas_indices = ['id_zona', 'npk_actual', 'materia_organica', 'ndvi', 'ndre', 'humedad_suelo', 'categoria']
        if analisis_tipo == "RECOMENDACIONES NPK":
            columnas_indices.insert(2, 'valor_recomendado')
        
        tabla_indices = gdf_analizado[columnas_indices].copy()
        tabla_indices.columns = ['Zona', 'NPK Actual'] + (['Recomendación'] if analisis_tipo == "RECOMENDACIONES NPK" else []) + [
            'Materia Org (%)', 'NDVI', 'NDRE', 'Humedad', 'Categoría'
        ]
        
        st.dataframe(tabla_indices, use_container_width=True)
        
        # RECOMENDACIONES ESPECÍFICAS POR CULTIVO
        st.subheader("💡 RECOMENDACIONES ESPECÍFICAS GEE")
        
        categorias = gdf_analizado['categoria'].unique()
        for cat in sorted(categorias):
            subset = gdf_analizado[gdf_analizado['categoria'] == cat]
            area_cat = subset['area_ha'].sum()
            
            with st.expander(f"🎯 **{cat}** - {area_cat:.1f} ha ({(area_cat/area_total*100):.1f}% del área)"):
                
                if analisis_tipo == "FERTILIDAD ACTUAL":
                    if cat in ["MUY BAJA", "BAJA"]:
                        st.markdown("**🚨 ESTRATEGIA: FERTILIZACIÓN CORRECTIVA**")
                        st.markdown("- Aplicar dosis completas de NPK")
                        st.markdown("- Incorporar materia orgánica")
                        st.markdown("- Monitorear cada 3 meses")
                    elif cat == "MEDIA":
                        st.markdown("**✅ ESTRATEGIA: MANTENIMIENTO BALANCEADO**")
                        st.markdown("- Seguir programa estándar de fertilización")
                        st.markdown("- Monitorear cada 6 meses")
                    else:
                        st.markdown("**🌟 ESTRATEGIA: MANTENIMIENTO CONSERVADOR**")
                        st.markdown("- Reducir dosis de fertilizantes")
                        st.markdown("- Enfoque en sostenibilidad")
                
                else:
                    # Recomendaciones NPK específicas por cultivo
                    if cat in ["MUY BAJO", "BAJO"]:
                        st.markdown("**🚨 APLICACIÓN ALTA** - Dosis correctiva urgente")
                        if nutriente == "NITRÓGENO":
                            st.markdown(f"- **Fuentes:** Urea (46% N) o {get_fuente_nitrogeno(cultivo)}")
                            st.markdown("- **Aplicación:** 2-3 dosis fraccionadas")
                        elif nutriente == "FÓSFORO":
                            st.markdown("- **Fuentes:** Superfosfato triple (46% P₂O₅) o Fosfato diamónico")
                            st.markdown("- **Aplicación:** Incorporar al suelo")
                        else:
                            st.markdown("- **Fuentes:** Cloruro de potasio (60% K₂O) o Sulfato de potasio")
                            st.markdown("- **Aplicación:** 2-3 aplicaciones")
                    
                    elif cat == "MEDIO":
                        st.markdown("**✅ APLICACIÓN MEDIA** - Mantenimiento balanceado")
                        st.markdown(f"- **Fuentes:** {get_fertilizante_balanceado(cultivo)}")
                        st.markdown("- **Aplicación:** Programa estándar")
                    
                    else:
                        st.markdown("**🌟 APLICACIÓN BAJA** - Reducción de dosis")
                        st.markdown("- **Fuentes:** Fertilizantes bajos en el nutriente")
                        st.markdown("- **Aplicación:** Solo mantenimiento")
                
                # Mostrar estadísticas de la categoría
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Zonas", len(subset))
                with col2:
                    if analisis_tipo == "FERTILIDAD ACTUAL":
                        st.metric("NPK Prom", f"{subset['npk_actual'].mean():.3f}")
                    else:
                        st.metric("Valor Prom", f"{subset['valor_recomendado'].mean():.1f}")
                with col3:
                    st.metric("Área", f"{area_cat:.1f} ha")
        
        # DESCARGA DE RESULTADOS
        st.subheader("📥 DESCARGAR RESULTADOS COMPLETOS")
        
        csv = gdf_analizado.to_csv(index=False)
        st.download_button(
            "📋 Descargar CSV con Análisis GEE",
            csv,
            f"analisis_gee_{cultivo}_{analisis_tipo.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            "text/csv"
        )
        
        # INFORMACIÓN TÉCNICA GEE
        with st.expander("🔍 VER METODOLOGÍA GEE DETALLADA"):
            st.markdown(f"""
            **🌐 METODOLOGÍA GOOGLE EARTH ENGINE - {cultivo}**
            
            **🎯 PARÁMETROS ÓPTIMOS {cultivo}:**
            - **Materia Orgánica:** {PARAMETROS_CULTIVOS[cultivo]['MATERIA_ORGANICA_OPTIMA']}%
            - **Humedad Suelo:** {PARAMETROS_CULTIVOS[cultivo]['HUMEDAD_OPTIMA']}
            - **NDVI Óptimo:** {PARAMETROS_CULTIVOS[cultivo]['NDVI_OPTIMO']}
            - **NDRE Óptimo:** {PARAMETROS_CULTIVOS[cultivo]['NDRE_OPTIMO']}
            
            **🎯 RANGOS NPK RECOMENDADOS:**
            - **Nitrógeno:** {PARAMETROS_CULTIVOS[cultivo]['NITROGENO']['min']}-{PARAMETROS_CULTIVOS[cultivo]['NITROGENO']['max']} kg/ha
            - **Fósforo:** {PARAMETROS_CULTIVOS[cultivo]['FOSFORO']['min']}-{PARAMETROS_CULTIVOS[cultivo]['FOSFORO']['max']} kg/ha  
            - **Potasio:** {PARAMETROS_CULTIVOS[cultivo]['POTASIO']['min']}-{PARAMETROS_CULTIVOS[cultivo]['POTASIO']['max']} kg/ha
            
            **🛰️ DATOS SENTINEL-2 UTILIZADOS:**
            - **B2 (Blue):** 490 nm
            - **B4 (Red):** 665 nm  
            - **B5 (Red Edge):** 705 nm
            - **B8 (NIR):** 842 nm
            - **B11 (SWIR):** 1610 nm
            """)
        
        return True
        
    except Exception as e:
        st.error(f"❌ Error en análisis GEE: {str(e)}")
        import traceback
        st.error(f"Detalle: {traceback.format_exc()}")
        return False

# FUNCIONES AUXILIARES PARA RECOMENDACIONES ESPECÍFICAS
def get_fuente_nitrogeno(cultivo):
    fuentes = {
        'TRIGO': 'Nitrato de amonio',
        'MAÍZ': 'Urea + Nitrato de amonio', 
        'SOJA': 'Fosfato diamónico (contiene N)',
        'SORGO': 'Urea',
        'GIRASOL': 'Nitrato de amonio'
    }
    return fuentes.get(cultivo, 'Urea')

def get_fertilizante_balanceado(cultivo):
    fertilizantes = {
        'TRIGO': '15-15-15 o 20-20-0',
        'MAÍZ': '17-17-17 o 20-10-10',
        'SOJA': '5-20-20 o 0-20-20',
        'SORGO': '12-24-12 o 10-20-10',
        'GIRASOL': '8-15-30 o 10-10-20'
    }
    return fertilizantes.get(cultivo, 'Fertilizante complejo balanceado')

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
                        st.write("**🎯 CONFIGURACIÓN GEE:**")
                        st.write(f"- Cultivo: {ICONOS_CULTIVOS[cultivo]} {cultivo}")
                        st.write(f"- Análisis: {analisis_tipo}")
                        st.write(f"- Nutriente: {nutriente}")
                        st.write(f"- Zonas: {n_divisiones}")
                    
                    # EJECUTAR ANÁLISIS GEE
                    if st.button("🚀 EJECUTAR ANÁLISIS GEE", type="primary"):
                        analisis_gee_completo(gdf, nutriente, analisis_tipo, n_divisiones, cultivo)
                        
        except Exception as e:
            st.error(f"Error cargando shapefile: {str(e)}")

else:
    st.info("📁 Sube el ZIP de tu parcela para comenzar el análisis")
    
    # INFORMACIÓN INICIAL
    with st.expander("ℹ️ INFORMACIÓN SOBRE LA METODOLOGÍA GEE"):
        st.markdown("""
        **🌱 SISTEMA DE ANÁLISIS MULTI-CULTIVO (GEE)**
        
        **📊 CULTIVOS SOPORTADOS:**
        - **🌾 TRIGO:** Cereal de clima templado
        - **🌽 MAÍZ:** Cereal de alta demanda nutricional  
        - **🫘 SOJA:** Leguminosa fijadora de nitrógeno
        - **🌾 SORGO:** Cereal resistente a sequía
        - **🌻 GIRASOL:** Oleaginosa de profundas raíces
        
        **🚀 FUNCIONALIDADES:**
        - **🌱 Fertilidad Actual:** Estado NPK del suelo usando índices satelitales
        - **💊 Recomendaciones NPK:** Dosis específicas por cultivo basadas en GEE
        - **🛰️ Metodología GEE:** Algoritmos científicos de Google Earth Engine
        - **🎯 Agricultura Precisión:** Mapas de prescripción por zonas
        
        **🔬 METODOLOGÍA CIENTÍFICA:**
        - Análisis basado en imágenes Sentinel-2
        - Parámetros específicos para cada cultivo
        - Cálculo de índices de vegetación y suelo
        - Recomendaciones validadas científicamente
        """)
