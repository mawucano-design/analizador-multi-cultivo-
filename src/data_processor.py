import geopandas as gpd
import pandas as pd
import numpy as np
import math
from shapely.geometry import Polygon

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

# PALETAS GEE MEJORADAS
PALETAS_GEE = {
    'FERTILIDAD': ['#d73027', '#f46d43', '#fdae61', '#fee08b', '#d9ef8b', '#a6d96a', '#66bd63', '#1a9850', '#006837'],
    'NITROGENO': ['#00ff00', '#80ff00', '#ffff00', '#ff8000', '#ff0000'],
    'FOSFORO': ['#0000ff', '#4040ff', '#8080ff', '#c0c0ff', '#ffffff'],
    'POTASIO': ['#4B0082', '#6A0DAD', '#8A2BE2', '#9370DB', '#D8BFD8']
}

def calcular_superficie(gdf):
    try:
        if gdf.crs and gdf.crs.is_geographic:
            area_m2 = gdf.geometry.area * 10000000000
        else:
            area_m2 = gdf.geometry.area
        return area_m2 / 10000
    except:
        return gdf.geometry.area / 10000

def dividir_parcela_en_zonas(gdf, n_zonas):
    if len(gdf) == 0:
        return gdf
    
    parcela_principal = gdf.iloc[0].geometry
    bounds = parcela_principal.bounds
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

def calcular_indices_satelitales_gee_mejorado(gdf, cultivo, usar_sentinel=True, fecha_imagen=None):
    """Calcula índices satelitales mejorados con Sentinel-2"""
    
    n_poligonos = len(gdf)
    resultados = []
    
    # Inicializar procesador Sentinel-2
    from src.sentinel_processor import SentinelHubProcessor
    processor = SentinelHubProcessor()
    
    # Obtener bbox del área total
    bounds = gdf.total_bounds
    bbox = [bounds[0], bounds[1], bounds[2], bounds[3]]
    
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
        if usar_sentinel and fecha_imagen:
            datos_sentinel = processor.get_sentinel2_data(
                row.geometry, fecha_imagen, bbox
            )
        
        # Normalizar posición para simular variación espacial
        x_norm = (row['x'] - x_min) / (x_max - x_min) if x_max != x_min else 0.5
        y_norm = (row['y'] - y_min) / (y_max - y_min) if y_max != y_min else 0.5
        
        patron_espacial = (x_norm * 0.6 + y_norm * 0.4)
        
        # Usar datos Sentinel-2 si están disponibles, sino simular
        if datos_sentinel and datos_sentinel['fuente'] == 'Sentinel-2 Harmonized':
            # Datos reales de Sentinel-2
            ndvi = datos_sentinel['ndvi']
            ndre = datos_sentinel['ndre']
            fuente = "Sentinel-2 L2A"
            
            # Calcular materia orgánica basada en SWIR
            swir = datos_sentinel.get('swir', 0.2)
            materia_organica = params['MATERIA_ORGANICA_OPTIMA'] * (0.7 + swir * 0.6)
            
            # Calcular humedad basada en NIR y SWIR
            nir = datos_sentinel.get('nir', 0.4)
            humedad_suelo = params['HUMEDAD_OPTIMA'] * (0.8 + (nir - swir) * 0.4)
            
        else:
            # Simulación (mantener lógica original como fallback)
            fuente = "Simulado"
            
            # 1. MATERIA ORGÁNICA - Adaptada por cultivo
            base_mo = params['MATERIA_ORGANICA_OPTIMA'] * 0.7
            variabilidad_mo = patron_espacial * (params['MATERIA_ORGANICA_OPTIMA'] * 0.6)
            materia_organica = base_mo + variabilidad_mo + np.random.normal(0, 0.2)
            
            # 2. HUMEDAD SUELO - Adaptada por requerimientos del cultivo
            base_humedad = params['HUMEDAD_OPTIMA'] * 0.8
            variabilidad_humedad = patron_espacial * (params['HUMEDAD_OPTIMA'] * 0.4)
            humedad_suelo = base_humedad + variabilidad_humedad + np.random.normal(0, 0.05)
            
            # 3. NDVI - Específico por cultivo
            ndvi_base = params['NDVI_OPTIMO'] * 0.6
            ndvi_variacion = patron_espacial * (params['NDVI_OPTIMO'] * 0.5)
            ndvi = ndvi_base + ndvi_variacion + np.random.normal(0, 0.06)
            
            # 4. NDRE - Específico por cultivo
            ndre_base = params['NDRE_OPTIMO'] * 0.7
            ndre_variacion = patron_espacial * (params['NDRE_OPTIMO'] * 0.4)
            ndre = ndre_base + ndre_variacion + np.random.normal(0, 0.04)
        
        # Asegurar límites
        materia_organica = max(0.5, min(8.0, materia_organica))
        humedad_suelo = max(0.1, min(0.8, humedad_suelo))
        ndvi = max(0.1, min(0.9, ndvi))
        ndre = max(0.05, min(0.7, ndre))
        
        # 5. ÍNDICE NPK ACTUAL - Fórmula mejorada con Sentinel-2
        npk_actual = (ndvi * 0.35) + (ndre * 0.35) + ((materia_organica / 8) * 0.2) + (humedad_suelo * 0.1)
        npk_actual = max(0, min(1, npk_actual))
        
        resultados.append({
            'materia_organica': round(materia_organica, 2),
            'humedad_suelo': round(humedad_suelo, 3),
            'ndvi': round(ndvi, 3),
            'ndre': round(ndre, 3),
            'npk_actual': round(npk_actual, 3),
            'fuente_datos': fuente,
            'resolucion': datos_sentinel['resolucion'] if datos_sentinel else '10m simulado',
            'procesamiento': datos_sentinel['procesamiento'] if datos_sentinel else 'L2A simulado'
        })
    
    return resultados

def calcular_recomendaciones_npk_gee(indices, nutriente, cultivo):
    """Calcula recomendaciones NPK basadas en la metodología GEE específica por cultivo"""
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
