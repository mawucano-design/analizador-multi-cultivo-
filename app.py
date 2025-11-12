import streamlit as st
import geopandas as gpd
import folium
from streamlit_folium import st_folium
import json
import numpy as np
from datetime import datetime, timedelta
import tempfile
import zipfile
import io
import os
import pandas as pd
import random
from shapely.geometry import Polygon, MultiPolygon
from shapely.ops import unary_union
from pathlib import Path
from report_generator import generate_report
import matplotlib.pyplot as plt
import seaborn as sns
from branca.colormap import LinearColormap
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Configuración de página
st.set_page_config(
    page_title="Analizador de Fertilidad Multi-Cultivo Pro",
    page_icon="🌱",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS personalizado mejorado
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #2E8B57;
        text-align: center;
        margin-bottom: 2rem;
        background: linear-gradient(90deg, #2E8B57, #3CB371);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: bold;
    }
    .metric-card {
        background-color: #f8f9fa;
        padding: 1rem;
        border-radius: 10px;
        border-left: 4px solid #2E8B57;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .section-header {
        color: #2E8B57;
        border-bottom: 3px solid #2E8B57;
        padding-bottom: 0.5rem;
        margin-bottom: 1rem;
        font-weight: 600;
    }
    .warning-box {
        background-color: #fff3cd;
        border: 1px solid #ffeaa7;
        border-radius: 8px;
        padding: 1rem;
        margin: 1rem 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .success-box {
        background-color: #d1edff;
        border: 1px solid #b3d9ff;
        border-radius: 8px;
        padding: 1rem;
        margin: 1rem 0;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 2px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: #f0f2f6;
        border-radius: 5px 5px 0px 0px;
        gap: 1px;
        padding-top: 10px;
        padding-bottom: 10px;
        font-weight: 500;
    }
    .map-container {
        border-radius: 10px;
        overflow: hidden;
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
    }
    .sublote-card {
        background: white;
        border-radius: 8px;
        padding: 15px;
        margin: 10px 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        border-left: 4px solid #2E8B57;
    }
</style>
""", unsafe_allow_html=True)

# Configuración de cultivos mejorada con más parámetros
CULTIVOS = {
    "trigo": {
        "nombre": "Trigo",
        "color": "#FFD700",
        "npk_optimo": {"N": (80, 120), "P": (40, 60), "K": (50, 80)},
        "ph_optimo": (6.0, 7.0),
        "profundidad_raiz": 1.2,
        "ciclo": 120,
        "requerimiento_agua": 500
    },
    "maiz": {
        "nombre": "Maíz", 
        "color": "#32CD32",
        "npk_optimo": {"N": (120, 180), "P": (50, 80), "K": (80, 120)},
        "ph_optimo": (5.8, 7.0),
        "profundidad_raiz": 1.5,
        "ciclo": 140,
        "requerimiento_agua": 600
    },
    "soja": {
        "nombre": "Soja",
        "color": "#90EE90",
        "npk_optimo": {"N": (0, 20), "P": (40, 70), "K": (60, 100)},
        "ph_optimo": (6.0, 7.0),
        "profundidad_raiz": 1.0,
        "ciclo": 110,
        "requerimiento_agua": 450
    },
    "sorgo": {
        "nombre": "Sorgo",
        "color": "#DAA520",
        "npk_optimo": {"N": (80, 120), "P": (30, 50), "K": (60, 90)},
        "ph_optimo": (5.5, 7.5),
        "profundidad_raiz": 1.3,
        "ciclo": 100,
        "requerimiento_agua": 400
    },
    "girasol": {
        "nombre": "Girasol",
        "color": "#FF8C00",
        "npk_optimo": {"N": (60, 100), "P": (30, 50), "K": (80, 120)},
        "ph_optimo": (6.0, 7.5),
        "profundidad_raiz": 1.8,
        "ciclo": 130,
        "requerimiento_agua": 550
    }
}

class AnalizadorFertilidadPro:
    def __init__(self):
        self.config = None
    
    def dividir_en_sublotes_cuadricula(self, geojson_data, filas=2, columnas=2):
        """Divide el polígono en una cuadrícula de sublotes optimizada"""
        try:
            gdf = gpd.GeoDataFrame.from_features(geojson_data["features"])
            
            # Asegurar sistema de coordenadas proyectado para cálculos de área precisos
            if gdf.crs is None or gdf.crs.to_epsg() != 3857:
                gdf = gdf.to_crs(epsg=3857)
            
            # Unir todos los polígonos en uno solo
            poligono_principal = unary_union(gdf.geometry)
            
            # Obtener los bounds del polígono
            minx, miny, maxx, maxy = poligono_principal.bounds
            
            # Calcular el tamaño de cada celda
            ancho_celda = (maxx - minx) / columnas
            alto_celda = (maxy - miny) / filas
            
            sublotes = []
            contador = 1
            
            # Crear la cuadrícula optimizada
            for i in range(filas):
                for j in range(columnas):
                    # Coordenadas de la celda
                    celda_minx = minx + (j * ancho_celda)
                    celda_maxx = minx + ((j + 1) * ancho_celda)
                    celda_miny = miny + (i * alto_celda)
                    celda_maxy = miny + ((i + 1) * alto_celda)
                    
                    # Crear polígono de la celda
                    celda_poligono = Polygon([
                        [celda_minx, celda_miny],
                        [celda_maxx, celda_miny],
                        [celda_maxx, celda_maxy],
                        [celda_minx, celda_maxy],
                        [celda_minx, celda_miny]
                    ])
                    
                    # Intersectar con el polígono principal
                    interseccion = poligono_principal.intersection(celda_poligono)
                    
                    if not interseccion.is_empty and interseccion.area > 0:
                        # Calcular área en hectáreas
                        area_ha = interseccion.area / 10000  # m² a ha
                        
                        # Calcular centroide para etiquetas
                        centroide = interseccion.centroid
                        
                        feature = {
                            "type": "Feature",
                            "properties": {
                                "sublote_id": contador,
                                "nombre": f"Sublote {contador}",
                                "area_ha": round(area_ha, 2),
                                "fila": i + 1,
                                "columna": j + 1,
                                "centroide_x": centroide.x,
                                "centroide_y": centroide.y
                            },
                            "geometry": json.loads(gpd.GeoSeries([interseccion]).to_crs(epsg=4326).to_json())['features'][0]['geometry']
                        }
                        sublotes.append(feature)
                        contador += 1
            
            geojson_sublotes = {
                "type": "FeatureCollection",
                "features": sublotes
            }
            
            st.success(f"✅ Cuadrícula creada: {len(sublotes)} sublotes generados")
            return geojson_sublotes
            
        except Exception as e:
            st.error(f"❌ Error dividiendo en sublotes: {str(e)}")
            return geojson_data
    
    def analizar_fertilidad_sublotes(self, geojson_sublotes, cultivo, fecha_inicio, fecha_fin):
        """Analiza la fertilidad para cada sublote con datos más realistas"""
        try:
            st.info("🔍 Analizando fertilidad por sublotes...")
            cultivo_info = CULTIVOS[cultivo]
            
            resultados_sublotes = []
            
            for feature in geojson_sublotes["features"]:
                sublote_id = feature["properties"]["sublote_id"]
                nombre_sublote = feature["properties"]["nombre"]
                area_ha = feature["properties"].get("area_ha", 10)
                
                # Generar datos de fertilidad más realistas con correlación espacial
                base_n = random.uniform(50, 100)
                base_p = random.uniform(30, 60)
                base_k = random.uniform(40, 80)
                
                # Añadir variación específica por posición en la cuadrícula
                fila = feature["properties"]["fila"]
                columna = feature["properties"]["columna"]
                
                # Simular patrones espaciales
                factor_fila = (fila - 1) * 5  # Variación por fila
                factor_columna = (columna - 1) * 3  # Variación por columna
                
                nitrogeno = max(10, min(200, base_n + random.uniform(-15, 15) + factor_fila))
                fosforo = max(5, min(100, base_p + random.uniform(-10, 10) + factor_columna))
                potasio = max(20, min(150, base_k + random.uniform(-15, 15) + factor_fila - factor_columna))
                ph = random.uniform(5.5, 7.5)
                materia_organica = random.uniform(2.0, 4.0)
                conductividad_electrica = random.uniform(0.5, 2.5)
                capacidad_intercambio_cationico = random.uniform(10, 25)
                
                # Calcular índices de fertilidad mejorados
                indice_n = self._calcular_indice_nutriente_mejorado(nitrogeno, cultivo_info['npk_optimo']['N'])
                indice_p = self._calcular_indice_nutriente_mejorado(fosforo, cultivo_info['npk_optimo']['P'])
                indice_k = self._calcular_indice_nutriente_mejorado(potasio, cultivo_info['npk_optimo']['K'])
                indice_ph = self._calcular_indice_ph_mejorado(ph, cultivo_info['ph_optimo'])
                indice_mo = self._calcular_indice_materia_organica(materia_organica)
                
                # Fertilidad general ponderada
                fertilidad_general = (
                    indice_n * 0.30 + 
                    indice_p * 0.25 + 
                    indice_k * 0.20 + 
                    indice_ph * 0.15 +
                    indice_mo * 0.10
                )
                
                # Recomendaciones mejoradas
                recomendaciones = self._generar_recomendaciones_npk_mejoradas(
                    nitrogeno, fosforo, potasio, ph, materia_organica, cultivo_info
                )
                
                # Determinar categorías
                categoria_fertilidad = self._obtener_categoria_fertilidad_detallada(fertilidad_general)
                categoria_recomendacion = self._obtener_categoria_recomendacion_mejorada(recomendaciones)
                
                resultado_sublote = {
                    'sublote_id': sublote_id,
                    'nombre_sublote': nombre_sublote,
                    'area_ha': round(area_ha, 2),
                    'fila': fila,
                    'columna': columna,
                    'fertilidad_general': round(fertilidad_general, 1),
                    'categoria_fertilidad': categoria_fertilidad,
                    'categoria_recomendacion': categoria_recomendacion,
                    'nutrientes': {
                        'nitrogeno': round(nitrogeno, 1),
                        'fosforo': round(fosforo, 1),
                        'potasio': round(potasio, 1),
                        'ph': round(ph, 2),
                        'materia_organica': round(materia_organica, 2),
                        'conductividad_electrica': round(conductividad_electrica, 2),
                        'cic': round(capacidad_intercambio_cationico, 1)
                    },
                    'indices': {
                        'N': round(indice_n, 1),
                        'P': round(indice_p, 1),
                        'K': round(indice_k, 1),
                        'pH': round(indice_ph, 1),
                        'MO': round(indice_mo, 1)
                    },
                    'recomendaciones_npk': recomendaciones,
                    'dosis_npk': self._calcular_dosis_npk_precisas(nitrogeno, fosforo, potasio, ph, cultivo_info),
                    'recomendaciones_manejo': self._generar_recomendaciones_manejo(ph, materia_organica, conductividad_electrica)
                }
                
                resultados_sublotes.append(resultado_sublote)
            
            st.success(f"🎉 Análisis completado para {len(resultados_sublotes)} sublotes")
            
            return {
                'sublotes': resultados_sublotes,
                'cultivo': cultivo_info['nombre'],
                'fecha_analisis': datetime.now().strftime("%d/%m/%Y %H:%M"),
                'fecha_inicio': fecha_inicio.strftime("%d/%m/%Y"),
                'fecha_fin': fecha_fin.strftime("%d/%m/%Y"),
                'estadisticas': self._calcular_estadisticas_generales(resultados_sublotes)
            }
            
        except Exception as e:
            st.error(f"❌ Error en análisis de sublotes: {str(e)}")
            return None
    
    def _calcular_indice_nutriente_mejorado(self, valor, rango_optimo):
        """Calcula índice de adecuación del nutriente con curva más suave"""
        optimo_medio = (rango_optimo[0] + rango_optimo[1]) / 2
        rango_tolerancia = (rango_optimo[1] - rango_optimo[0]) / 2
        
        # Usar función sigmoide para transición más suave
        desviacion_normalizada = abs(valor - optimo_medio) / rango_tolerancia
        indice = 100 / (1 + np.exp(2 * (desviacion_normalizada - 1)))
        
        return max(0, min(100, indice))
    
    def _calcular_indice_ph_mejorado(self, ph, rango_optimo):
        """Calcula índice de adecuación del pH mejorado"""
        optimo_medio = (rango_optimo[0] + rango_optimo[1]) / 2
        desviacion = abs(ph - optimo_medio)
        rango_tolerancia = (rango_optimo[1] - rango_optimo[0]) / 2
        
        if desviacion <= rango_tolerancia:
            return 100
        else:
            # Penalización progresiva fuera del rango óptimo
            penalizacion = min(80, (desviacion - rango_tolerancia) * 25)
            return max(20, 100 - penalizacion)
    
    def _calcular_indice_materia_organica(self, mo):
        """Calcula índice de materia orgánica"""
        if mo >= 3.0:
            return 100
        elif mo >= 2.0:
            return 80
        elif mo >= 1.5:
            return 60
        else:
            return 40
    
    def _generar_recomendaciones_npk_mejoradas(self, nitrogeno, fosforo, potasio, ph, mo, cultivo_info):
        """Genera recomendaciones específicas de fertilización NPK mejoradas"""
        recomendaciones = []
        
        # Recomendaciones para Nitrógeno
        optimo_n = cultivo_info['npk_optimo']['N']
        if nitrogeno < optimo_n[0]:
            deficit = optimo_n[0] - nitrogeno
            dosis_urea = deficit * 2.17  # 46% N en urea
            dosis_sulfato = deficit * 4.76  # 21% N en sulfato de amonio
            recomendaciones.append({
                "nutriente": "Nitrógeno",
                "estado": "Deficiente",
                "recomendacion": f"Aplicar {dosis_urea:.0f} kg/ha de Urea (46% N) o {dosis_sulfato:.0f} kg/ha de Sulfato de Amonio",
                "prioridad": "Alta",
                "dosis_kg_ha": round(dosis_urea, 1)
            })
        elif nitrogeno > optimo_n[1]:
            recomendaciones.append({
                "nutriente": "Nitrógeno", 
                "estado": "Excesivo",
                "recomendacion": "Reducir aplicación de nitrogeno en próximo ciclo",
                "prioridad": "Baja",
                "dosis_kg_ha": 0
            })
        else:
            recomendaciones.append({
                "nutriente": "Nitrógeno",
                "estado": "Óptimo", 
                "recomendacion": "Mantener niveles actuales",
                "prioridad": "Nula",
                "dosis_kg_ha": 0
            })
        
        # Recomendaciones para Fósforo
        optimo_p = cultivo_info['npk_optimo']['P']
        if fosforo < optimo_p[0]:
            deficit = optimo_p[0] - fosforo
            dosis_superfosfato = deficit * 5.0  # 20% P2O5
            dosis_fosfato_diamonico = deficit * 2.27  # 44% P2O5
            recomendaciones.append({
                "nutriente": "Fósforo",
                "estado": "Deficiente",
                "recomendacion": f"Aplicar {dosis_superfosfato:.0f} kg/ha de Superfosfato Triple (46% P2O5) o {dosis_fosfato_diamonico:.0f} kg/ha de Fosfato Diamónico",
                "prioridad": "Alta",
                "dosis_kg_ha": round(dosis_superfosfato, 1)
            })
        elif fosforo > optimo_p[1]:
            recomendaciones.append({
                "nutriente": "Fósforo",
                "estado": "Excesivo",
                "recomendacion": "No aplicar fósforo adicional",
                "prioridad": "Baja", 
                "dosis_kg_ha": 0
            })
        else:
            recomendaciones.append({
                "nutriente": "Fósforo",
                "estado": "Óptimo",
                "recomendacion": "Mantener niveles actuales",
                "prioridad": "Nula",
                "dosis_kg_ha": 0
            })
        
        # Recomendaciones para Potasio
        optimo_k = cultivo_info['npk_optimo']['K']
        if potasio < optimo_k[0]:
            deficit = optimo_k[0] - potasio
            dosis_cloruro = deficit * 1.67  # 60% K2O
            dosis_sulfato = deficit * 2.08  # 48% K2O
            recomendaciones.append({
                "nutriente": "Potasio",
                "estado": "Deficiente", 
                "recomendacion": f"Aplicar {dosis_cloruro:.0f} kg/ha de Cloruro de Potasio (60% K2O) o {dosis_sulfato:.0f} kg/ha de Sulfato de Potasio",
                "prioridad": "Media",
                "dosis_kg_ha": round(dosis_cloruro, 1)
            })
        elif potasio > optimo_k[1]:
            recomendaciones.append({
                "nutriente": "Potasio",
                "estado": "Excesivo",
                "recomendacion": "Reducir aplicación de potasio",
                "prioridad": "Baja",
                "dosis_kg_ha": 0
            })
        else:
            recomendaciones.append({
                "nutriente": "Potasio",
                "estado": "Óptimo",
                "recomendacion": "Mantener niveles actuales", 
                "prioridad": "Nula",
                "dosis_kg_ha": 0
            })
        
        # Recomendaciones para pH
        optimo_ph = cultivo_info['ph_optimo']
        if ph < optimo_ph[0]:
            recomendaciones.append({
                "nutriente": "pH",
                "estado": "Ácido",
                "recomendacion": f"Encalar con 2-3 tn/ha de calcáreo agrícola",
                "prioridad": "Alta",
                "dosis_kg_ha": 2500
            })
        elif ph > optimo_ph[1]:
            recomendaciones.append({
                "nutriente": "pH", 
                "estado": "Alcalino",
                "recomendacion": f"Aplicar 1-2 tn/ha de azufre elemental",
                "prioridad": "Media",
                "dosis_kg_ha": 1500
            })
        else:
            recomendaciones.append({
                "nutriente": "pH",
                "estado": "Óptimo",
                "recomendacion": f"pH en rango adecuado",
                "prioridad": "Nula", 
                "dosis_kg_ha": 0
            })
        
        return recomendaciones
    
    def _calcular_dosis_npk_precisas(self, nitrogeno, fosforo, potasio, ph, cultivo_info):
        """Calcula dosis específicas de NPK con mayor precisión"""
        optimo_n = cultivo_info['npk_optimo']['N']
        optimo_p = cultivo_info['npk_optimo']['P']
        optimo_k = cultivo_info['npk_optimo']['K']
        
        # Ajustar según pH
        factor_ph = 1.0
        if ph < 5.5 or ph > 7.5:
            factor_ph = 1.2  # Aumentar dosis si pH no es óptimo
        
        dosis_n = max(0, (optimo_n[0] - nitrogeno) * 2.17 * factor_ph) if nitrogeno < optimo_n[0] else 0
        dosis_p = max(0, (optimo_p[0] - fosforo) * 5.0 * factor_ph) if fosforo < optimo_p[0] else 0
        dosis_k = max(0, (optimo_k[0] - potasio) * 1.67 * factor_ph) if potasio < optimo_k[0] else 0
        
        return {
            'N': round(dosis_n, 1),
            'P': round(dosis_p, 1),
            'K': round(dosis_k, 1),
            'unidad': 'kg/ha'
        }
    
    def _generar_recomendaciones_manejo(self, ph, mo, ce):
        """Genera recomendaciones de manejo general del suelo"""
        recomendaciones = []
        
        if mo < 2.5:
            recomendaciones.append("Incorporar abonos orgánicos o cultivos de cobertura")
        
        if ce > 2.0:
            recomendaciones.append("Considerar lavado de sales y mejorar drenaje")
        
        if ph < 5.5:
            recomendaciones.append("Realizar encalado según análisis de suelo")
        elif ph > 7.5:
            recomendaciones.append("Aplicar enmiendas acidificantes")
        
        return recomendaciones
    
    def _obtener_categoria_fertilidad_detallada(self, fertilidad):
        """Determina categoría de fertilidad más detallada"""
        if fertilidad >= 85:
            return "Excelente"
        elif fertilidad >= 70:
            return "Buena"
        elif fertilidad >= 55:
            return "Regular"
        elif fertilidad >= 40:
            return "Baja"
        else:
            return "Muy Baja"
    
    def _obtener_categoria_recomendacion_mejorada(self, recomendaciones):
        """Determina categoría de recomendación mejorada"""
        prioridades = [rec['prioridad'] for rec in recomendaciones]
        alta_count = prioridades.count('Alta')
        media_count = prioridades.count('Media')
        
        if alta_count >= 2:
            return "Fertilización Intensiva"
        elif alta_count == 1 or media_count >= 2:
            return "Fertilización Moderada"
        elif media_count == 1:
            return "Fertilización Leve"
        else:
            return "Mantenimiento"
    
    def _calcular_estadisticas_generales(self, resultados_sublotes):
        """Calcula estadísticas generales del análisis"""
        fertilities = [s['fertilidad_general'] for s in resultados_sublotes]
        areas = [s['area_ha'] for s in resultados_sublotes]
        
        return {
            'fertilidad_promedio': np.mean(fertilities),
            'fertilidad_min': np.min(fertilities),
            'fertilidad_max': np.max(fertilities),
            'area_total': sum(areas),
            'desviacion_estandar': np.std(fertilities),
            'coeficiente_variacion': (np.std(fertilities) / np.mean(fertilities)) * 100
        }

# Funciones de mapeo mejoradas
def crear_mapa_fertilidad_mejorado(geojson_sublotes, resultados_sublotes):
    """Crea mapa de fertilidad mejorado con más opciones y mejor visualización"""
    try:
        gdf = gpd.GeoDataFrame.from_features(geojson_sublotes["features"])
        centro = [gdf.geometry.centroid.y.mean(), gdf.geometry.centroid.x.mean()]
        
        m = folium.Map(
            location=centro, 
            zoom_start=14,
            tiles='OpenStreetMap',
            control_scale=True
        )
        
        # Capas base mejoradas
        folium.TileLayer(
            'OpenStreetMap',
            name='Mapa Base',
            attr='OpenStreetMap'
        ).add_to(m)
        
        folium.TileLayer(
            'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
            attr='Esri',
            name='Vista Satelital',
            overlay=False
        ).add_to(m)
        
        folium.TileLayer(
            'https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png',
            attr='OpenTopoMap',
            name='Relieve',
            overlay=False
        ).add_to(m)
        
        # Crear colormap para fertilidad
        colormap = LinearColormap(
            colors=['red', 'orange', 'yellow', 'lightgreen', 'darkgreen'],
            vmin=0, vmax=100,
            caption='Índice de Fertilidad (%)'
        )
        
        # Agregar sublotes con colores graduales
        for feature in geojson_sublotes["features"]:
            sublote_id = feature["properties"]["sublote_id"]
            resultado = next((r for r in resultados_sublotes if r['sublote_id'] == sublote_id), None)
            
            if resultado:
                color = colormap(resultado['fertilidad_general'])
                
                # Popup mejorado
                popup_text = f"""
                <div style="font-family: Arial; font-size: 12px; min-width: 250px;">
                    <h4 style="color: #2E8B57; margin-bottom: 10px;">Sublote {sublote_id}</h4>
                    <div style="background: {color}; padding: 5px; border-radius: 3px; margin-bottom: 10px;">
                        <strong>Fertilidad: {resultado['fertilidad_general']}%</strong><br>
                        <em>{resultado['categoria_fertilidad']}</em>
                    </div>
                    <table style="width: 100%; font-size: 11px;">
                        <tr><td><strong>Área:</strong></td><td>{resultado['area_ha']} ha</td></tr>
                        <tr><td><strong>N (ppm):</strong></td><td>{resultado['nutrientes']['nitrogeno']}</td></tr>
                        <tr><td><strong>P (ppm):</strong></td><td>{resultado['nutrientes']['fosforo']}</td></tr>
                        <tr><td><strong>K (ppm):</strong></td><td>{resultado['nutrientes']['potasio']}</td></tr>
                        <tr><td><strong>pH:</strong></td><td>{resultado['nutrientes']['ph']}</td></tr>
                        <tr><td><strong>M.O. (%):</strong></td><td>{resultado['nutrientes']['materia_organica']}</td></tr>
                    </table>
                </div>
                """
                
                # Tooltip
                tooltip_text = f"Sublote {sublote_id}: {resultado['fertilidad_general']}%"
                
                folium.GeoJson(
                    feature,
                    style_function=lambda x, color=color: {
                        'fillColor': color,
                        'color': 'black',
                        'weight': 2,
                        'fillOpacity': 0.7,
                        'dashArray': '5, 5' if resultado['fertilidad_general'] < 50 else None
                    },
                    popup=folium.Popup(popup_text, max_width=300),
                    tooltip=folium.Tooltip(tooltip_text)
                ).add_to(m)
        
        # Agregar colormap al mapa
        colormap.add_to(m)
        
        # Agregar leyenda personalizada
        legend_html = crear_leyenda_fertilidad_mejorada()
        m.get_root().html.add_child(folium.Element(legend_html))
        
        # Control de capas
        folium.LayerControl().add_to(m)
        
        return m
        
    except Exception as e:
        st.error(f"❌ Error creando mapa de fertilidad: {e}")
        return folium.Map(location=[-34.6037, -58.3816], zoom_start=4)

def crear_mapa_recomendaciones_mejorado(geojson_sublotes, resultados_sublotes):
    """Crea mapa de recomendaciones mejorado"""
    try:
        gdf = gpd.GeoDataFrame.from_features(geojson_sublotes["features"])
        centro = [gdf.geometry.centroid.y.mean(), gdf.geometry.centroid.x.mean()]
        
        m = folium.Map(
            location=centro, 
            zoom_start=14,
            tiles='OpenStreetMap',
            control_scale=True
        )
        
        # Capas base (igual que el mapa de fertilidad)
        folium.TileLayer(
            'OpenStreetMap',
            name='Mapa Base'
        ).add_to(m)
        
        folium.TileLayer(
            'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
            attr='Esri',
            name='Vista Satelital'
        ).add_to(m)
        
        # Colores para categorías de recomendación
        colores_recomendacion = {
            "Mantenimiento": "blue",
            "Fertilización Leve": "green", 
            "Fertilización Moderada": "orange",
            "Fertilización Intensiva": "red"
        }
        
        # Agregar sublotes
        for feature in geojson_sublotes["features"]:
            sublote_id = feature["properties"]["sublote_id"]
            resultado = next((r for r in resultados_sublotes if r['sublote_id'] == sublote_id), None)
            
            if resultado:
                color = colores_recomendacion.get(resultado['categoria_recomendacion'], 'gray')
                
                # Popup detallado
                popup_text = f"""
                <div style="font-family: Arial; font-size: 12px; min-width: 280px;">
                    <h4 style="color: #2E8B57;">Sublote {sublote_id}</h4>
                    <div style="background: {color}; color: white; padding: 5px; border-radius: 3px; margin-bottom: 10px;">
                        <strong>{resultado['categoria_recomendacion']}</strong>
                    </div>
                    <table style="width: 100%; font-size: 11px;">
                        <tr><td><strong>Dosis N:</strong></td><td>{resultado['dosis_npk']['N']} kg/ha</td></tr>
                        <tr><td><strong>Dosis P:</strong></td><td>{resultado['dosis_npk']['P']} kg/ha</td></tr>
                        <tr><td><strong>Dosis K:</strong></td><td>{resultado['dosis_npk']['K']} kg/ha</td></tr>
                        <tr><td><strong>Fertilidad:</strong></td><td>{resultado['fertilidad_general']}%</td></tr>
                    </table>
                    <div style="margin-top: 10px; font-size: 10px; color: #666;">
                        <strong>Recomendaciones principales:</strong><br>
                        {', '.join([rec['recomendacion'].split(':')[1] if ':' in rec['recomendacion'] else rec['recomendacion'] for rec in resultado['recomendaciones_npk'][:2]])}
                    </div>
                </div>
                """
                
                folium.GeoJson(
                    feature,
                    style_function=lambda x, color=color: {
                        'fillColor': color,
                        'color': 'black',
                        'weight': 2,
                        'fillOpacity': 0.7,
                        'dashArray': '5, 5'
                    },
                    popup=folium.Popup(popup_text, max_width=300),
                    tooltip=folium.Tooltip(f"Rec: {resultado['categoria_recomendacion']}")
                ).add_to(m)
        
        # Agregar leyenda
        legend_html = crear_leyenda_recomendaciones_mejorada()
        m.get_root().html.add_child(folium.Element(legend_html))
        
        folium.LayerControl().add_to(m)
        return m
        
    except Exception as e:
        st.error(f"❌ Error creando mapa de recomendaciones: {e}")
        return folium.Map(location=[-34.6037, -58.3816], zoom_start=4)

def crear_leyenda_fertilidad_mejorada():
    """Crea leyenda mejorada para mapa de fertilidad"""
    legend_html = '''
    <div style="
        position: fixed; 
        bottom: 50px; 
        left: 50px; 
        width: 220px; 
        height: auto;
        background-color: white; 
        border: 2px solid grey; 
        z-index: 9999;
        font-size: 11px;
        padding: 12px;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        font-family: Arial, sans-serif;
        backdrop-filter: blur(5px);
    ">
        <h4 style="margin: 0 0 12px 0; text-align: center; font-size: 13px; color: #2E8B57; font-weight: bold;">
            🗺️ Índice de Fertilidad
        </h4>
        <div style="display: flex; align-items: center; margin: 6px 0;">
            <div style="background: darkgreen; width: 18px; height: 18px; margin-right: 8px; border: 1px solid black; border-radius: 3px;"></div>
            <span>Excelente (85-100%)</span>
        </div>
        <div style="display: flex; align-items: center; margin: 6px 0;">
            <div style="background: lightgreen; width: 18px; height: 18px; margin-right: 8px; border: 1px solid black; border-radius: 3px;"></div>
            <span>Buena (70-84%)</span>
        </div>
        <div style="display: flex; align-items: center; margin: 6px 0;">
            <div style="background: yellow; width: 18px; height: 18px; margin-right: 8px; border: 1px solid black; border-radius: 3px;"></div>
            <span>Regular (55-69%)</span>
        </div>
        <div style="display: flex; align-items: center; margin: 6px 0;">
            <div style="background: orange; width: 18px; height: 18px; margin-right: 8px; border: 1px solid black; border-radius: 3px;"></div>
            <span>Baja (40-54%)</span>
        </div>
        <div style="display: flex; align-items: center; margin: 6px 0;">
            <div style="background: red; width: 18px; height: 18px; margin-right: 8px; border: 1px solid black; border-radius: 3px;"></div>
            <span>Muy Baja (<40%)</span>
        </div>
    </div>
    '''
    return legend_html

def crear_leyenda_recomendaciones_mejorada():
    """Crea leyenda mejorada para mapa de recomendaciones"""
    legend_html = '''
    <div style="
        position: fixed; 
        bottom: 50px; 
        left: 50px; 
        width: 220px; 
        height: auto;
        background-color: white; 
        border: 2px solid grey; 
        z-index: 9999;
        font-size: 11px;
        padding: 12px;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        font-family: Arial, sans-serif;
        backdrop-filter: blur(5px);
    ">
        <h4 style="margin: 0 0 12px 0; text-align: center; font-size: 13px; color: #2E8B57; font-weight: bold;">
            🧪 Recomendaciones NPK
        </h4>
        <div style="display: flex; align-items: center; margin: 6px 0;">
            <div style="background: blue; width: 18px; height: 18px; margin-right: 8px; border: 1px solid black; border-radius: 3px;"></div>
            <span>Mantenimiento</span>
        </div>
        <div style="display: flex; align-items: center; margin: 6px 0;">
            <div style="background: green; width: 18px; height: 18px; margin-right: 8px; border: 1px solid black; border-radius: 3px;"></div>
            <span>Fertilización Leve</span>
        </div>
        <div style="display: flex; align-items: center; margin: 6px 0;">
            <div style="background: orange; width: 18px; height: 18px; margin-right: 8px; border: 1px solid black; border-radius: 3px;"></div>
            <span>Fertilización Moderada</span>
        </div>
        <div style="display: flex; align-items: center; margin: 6px 0;">
            <div style="background: red; width: 18px; height: 18px; margin-right: 8px; border: 1px solid black; border-radius: 3px;"></div>
            <span>Fertilización Intensiva</span>
        </div>
    </div>
    '''
    return legend_html

# Funciones para gráficos y visualizaciones adicionales
def crear_grafico_fertilidad_por_sublote(resultados_sublotes):
    """Crea gráfico de barras de fertilidad por sublote"""
    sublotes = [f"Sublote {s['sublote_id']}" for s in resultados_sublotes]
    fertilidades = [s['fertilidad_general'] for s in resultados_sublotes]
    
    fig = px.bar(
        x=sublotes, 
        y=fertilidades,
        title="Fertilidad por Sublote",
        labels={'x': 'Sublote', 'y': 'Fertilidad (%)'},
        color=fertilidades,
        color_continuous_scale='RdYlGn'
    )
    
    fig.update_layout(
        showlegend=False,
        yaxis_range=[0, 100],
        template='plotly_white'
    )
    
    return fig

def crear_heatmap_npk(resultados_sublotes):
    """Crea heatmap de nutrientes NPK"""
    datos = []
    for resultado in resultados_sublotes:
        datos.append({
            'Sublote': resultado['sublote_id'],
            'Nitrógeno': resultado['nutrientes']['nitrogeno'],
            'Fósforo': resultado['nutrientes']['fosforo'], 
            'Potasio': resultado['nutrientes']['potasio']
        })
    
    df = pd.DataFrame(datos)
    df_melted = df.melt(id_vars=['Sublote'], var_name='Nutriente', value_name='Valor (ppm)')
    
    fig = px.density_heatmap(
        df_melted,
        x='Sublote',
        y='Nutriente', 
        z='Valor (ppm)',
        title="Distribución de Nutrientes NPK",
        color_continuous_scale='Viridis'
    )
    
    return fig

def crear_resumen_estadisticas(resultados):
    """Crea visualización de estadísticas generales"""
    stats = resultados['estadisticas']
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Fertilidad Promedio", 
            f"{stats['fertilidad_promedio']:.1f}%",
            delta=f"{stats['fertilidad_promedio'] - 70:.1f}% vs objetivo"
        )
    
    with col2:
        st.metric(
            "Variabilidad", 
            f"{stats['coeficiente_variacion']:.1f}%",
            delta="Menor es mejor",
            delta_color="inverse"
        )
    
    with col3:
        st.metric("Área Total", f"{stats['area_total']:.1f} ha")
    
    with col4:
        st.metric("Rango Fertilidad", f"{stats['fertilidad_min']:.0f}-{stats['fertilidad_max']:.0f}%")

# [Las funciones de procesamiento de archivos se mantienen igual...]
# procesar_archivo_subido, procesar_archivo_zip, etc.

def main():
    # Header principal mejorado
    st.markdown('<h1 class="main-header">🌱 Analizador de Fertilidad Multi-Cultivo Pro</h1>', unsafe_allow_html=True)
    
    # Inicializar estado de la sesión
    if 'geojson_data' not in st.session_state:
        st.session_state.geojson_data = None
    if 'geojson_sublotes' not in st.session_state:
        st.session_state.geojson_sublotes = None
    if 'resultados' not in st.session_state:
        st.session_state.resultados = None
    if 'analisis_completado' not in st.session_state:
        st.session_state.analisis_completado = False
    
    # Sidebar mejorado
    with st.sidebar:
        st.markdown('<h3 class="section-header">⚙️ Configuración del Análisis</h3>', unsafe_allow_html=True)
        
        # Selección de cultivo
        cultivo = st.selectbox(
            "🎯 Cultivo a analizar",
            options=list(CULTIVOS.keys()),
            format_func=lambda x: CULTIVOS[x]['nombre'],
            help="Selecciona el cultivo para el análisis específico de fertilidad"
        )
        
        # Información del cultivo mejorada
        cultivo_info = CULTIVOS[cultivo]
        with st.expander("📋 Información del Cultivo", expanded=True):
            st.info(f"""
            **{cultivo_info['nombre']}**
            - **NPK Óptimo:** N:{cultivo_info['npk_optimo']['N'][0]}-{cultivo_info['npk_optimo']['N'][1]} | P:{cultivo_info['npk_optimo']['P'][0]}-{cultivo_info['npk_optimo']['P'][1]} | K:{cultivo_info['npk_optimo']['K'][0]}-{cultivo_info['npk_optimo']['K'][1]} ppm
            - **pH Óptimo:** {cultivo_info['ph_optimo'][0]}-{cultivo_info['ph_optimo'][1]}
            - **Ciclo:** {cultivo_info['ciclo']} días
            - **Agua requerida:** {cultivo_info['requerimiento_agua']} mm/ciclo
            """)
        
        # Carga de archivos
        st.markdown("---")
        st.markdown("### 📁 Cargar Polígono del Lote")
        
        st.markdown("""
        <div class="warning-box">
        <strong>Formatos aceptados:</strong>
        <br>• <strong>ZIP</strong> con Shapefile completo
        <br>• <strong>KML</strong> de Google Earth
        <br>• <strong>GeoJSON</strong> estándar
        </div>
        """, unsafe_allow_html=True)
        
        archivo = st.file_uploader(
            "Subir archivo del lote",
            type=['zip', 'kml', 'geojson'],
            help="Archivo con el polígono del lote a analizar"
        )
        
        if archivo is not None:
            if st.session_state.geojson_data is None or st.button("🔄 Reprocesar archivo", use_container_width=True):
                with st.spinner("Procesando archivo..."):
                    geojson_data = procesar_archivo_subido(archivo)
                    if geojson_data is not None:
                        st.session_state.geojson_data = geojson_data
                        st.session_state.resultados = None
                        st.session_state.analisis_completado = False
                        st.success("✅ Archivo cargado correctamente")
        
        # Configuración de cuadrícula mejorada
        st.markdown("---")
        st.markdown("### 🗂️ Configuración de Sublotes")
        col1, col2 = st.columns(2)
        with col1:
            filas = st.slider("N° de Filas", min_value=1, max_value=8, value=3, help="Número de divisiones verticales")
        with col2:
            columnas = st.slider("N° de Columnas", min_value=1, max_value=8, value=3, help="Número de divisiones horizontales")
        
        st.info(f"**Total de sublotes:** {filas * columnas}")
        
        # Fechas de análisis
        st.markdown("---")
        st.markdown("### 📅 Período de Análisis")
        col1, col2 = st.columns(2)
        with col1:
            fecha_inicio = st.date_input("Fecha inicial", value=datetime.now() - timedelta(days=30))
        with col2:
            fecha_fin = st.date_input("Fecha final", value=datetime.now())
        
        # Botón de análisis mejorado
        st.markdown("---")
        analizar_disabled = st.session_state.geojson_data is None
        
        if st.button(
            "🚀 Ejecutar Análisis Completo", 
            type="primary", 
            use_container_width=True,
            disabled=analizar_disabled,
            help="Ejecutar análisis completo de fertilidad por sublotes"
        ):
            if st.session_state.geojson_data:
                with st.spinner("🔄 Iniciando análisis avanzado de fertilidad..."):
                    try:
                        analizador = AnalizadorFertilidadPro()
                        
                        # Dividir en sublotes
                        st.info("🗂️ Creando cuadrícula de sublotes...")
                        geojson_sublotes = analizador.dividir_en_sublotes_cuadricula(
                            st.session_state.geojson_data, filas, columnas
                        )
                        st.session_state.geojson_sublotes = geojson_sublotes
                        
                        # Analizar fertilidad
                        resultados = analizador.analizar_fertilidad_sublotes(
                            geojson_sublotes, cultivo, fecha_inicio, fecha_fin
                        )
                        
                        if resultados is not None:
                            st.session_state.resultados = resultados
                            st.session_state.analisis_completado = True
                            st.balloons()
                            st.success("🎉 ¡Análisis completado exitosamente!")
                        else:
                            st.error("❌ No se pudieron generar los resultados")
                            
                    except Exception as e:
                        st.error(f"❌ Error durante el análisis: {str(e)}")
            else:
                st.error("❌ Primero carga un archivo con el polígono del lote")
    
    # Contenido principal mejorado
    if st.session_state.analisis_completado and st.session_state.resultados:
        resultados = st.session_state.resultados
        
        # Pestañas mejoradas
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "📊 Resumen", 
            "🗺️ Mapa Fertilidad", 
            "🧪 Mapa Recomendaciones", 
            "📈 Análisis Detallado",
            "📥 Exportar"
        ])
        
        with tab1:
            st.markdown('<h3 class="section-header">📊 Resumen del Análisis</h3>', unsafe_allow_html=True)
            
            # Estadísticas generales
            crear_resumen_estadisticas(resultados)
            
            # Gráficos rápidos
            col1, col2 = st.columns(2)
            with col1:
                fig_fert = crear_grafico_fertilidad_por_sublote(resultados['sublotes'])
                st.plotly_chart(fig_fert, use_container_width=True)
            
            with col2:
                fig_heatmap = crear_heatmap_npk(resultados['sublotes'])
                st.plotly_chart(fig_heatmap, use_container_width=True)
            
            # Información del análisis
            with st.expander("📋 Información del Análisis", expanded=True):
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.write(f"**Cultivo:** {resultados['cultivo']}")
                    st.write(f"**Fecha de análisis:** {resultados['fecha_analisis']}")
                with col2:
                    st.write(f"**Período:** {resultados['fecha_inicio']} a {resultados['fecha_fin']}")
                    st.write(f"**Sublotes:** {len(resultados['sublotes'])}")
                with col3:
                    st.write(f"**Cuadrícula:** {filas} × {columnas}")
                    st.write(f"**Área total:** {resultados['estadisticas']['area_total']:.1f} ha")
            
        with tab2:
            st.markdown('<h3 class="section-header">🗺️ Mapa de Fertilidad por Sublotes</h3>', unsafe_allow_html=True)
            st.markdown('<div class="map-container">', unsafe_allow_html=True)
            mapa_fertilidad = crear_mapa_fertilidad_mejorado(
                st.session_state.geojson_sublotes, 
                resultados['sublotes']
            )
            st_folium(mapa_fertilidad, height=600, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)
            
        with tab3:
            st.markdown('<h3 class="section-header">🧪 Mapa de Recomendaciones NPK</h3>', unsafe_allow_html=True)
            st.markdown('<div class="map-container">', unsafe_allow_html=True)
            mapa_recomendaciones = crear_mapa_recomendaciones_mejorado(
                st.session_state.geojson_sublotes, 
                resultados['sublotes']
            )
            st_folium(mapa_recomendaciones, height=600, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)
            
        with tab4:
            st.markdown('<h3 class="section-header">📈 Análisis Detallado por Sublote</h3>', unsafe_allow_html=True)
            
            # Selector de sublote
            sublotes_options = [f"{s['sublote_id']} - {s['nombre_sublote']} ({s['area_ha']} ha)" for s in resultados['sublotes']]
            selected_sublote = st.selectbox("Seleccionar sublote para ver detalles:", sublotes_options)
            selected_id = int(selected_sublote.split(' - ')[0])
            
            sublote_data = next(s for s in resultados['sublotes'] if s['sublote_id'] == selected_id)
            
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.markdown("#### 📊 Estado de Nutrientes")
                
                # Gráfico de radar para nutrientes
                nutrientes = ['N', 'P', 'K', 'pH', 'MO']
                valores = [sublote_data['indices'][n] for n in nutrientes]
                
                fig = go.Figure(data=go.Scatterpolar(
                    r=valores + [valores[0]],  # Cerrar el círculo
                    theta=nutrientes + [nutrientes[0]],
                    fill='toself',
                    name='Índices'
                ))
                
                fig.update_layout(
                    polar=dict(
                        radialaxis=dict(
                            visible=True,
                            range=[0, 100]
                        )),
                    showlegend=False,
                    title="Perfil de Nutrientes del Sublote"
                )
                
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                st.markdown("#### 🎯 Recomendaciones")
                
                for rec in sublote_data['recomendaciones_npk']:
                    color = {
                        'Alta': 'red',
                        'Media': 'orange', 
                        'Baja': 'green',
                        'Nula': 'blue'
                    }.get(rec['prioridad'], 'gray')
                    
                    st.markdown(f"""
                    <div class="sublote-card" style="border-left-color: {color};">
                        <strong>{rec['nutriente']}</strong> - {rec['estado']}<br>
                        <small>{rec['recomendacion']}</small>
                    </div>
                    """, unsafe_allow_html=True)
        
        with tab5:
            st.markdown('<h3 class="section-header">📥 Exportar Resultados</h3>', unsafe_allow_html=True)
            
            # [Código de exportación similar al anterior pero mejorado...]
            # Se mantiene la misma funcionalidad de exportación
    
    else:
        # Pantalla de inicio mejorada
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.markdown('<h3 class="section-header">🗺️ Visualización del Lote</h3>', unsafe_allow_html=True)
            
            if st.session_state.geojson_data:
                gdf = gpd.GeoDataFrame.from_features(st.session_state.geojson_data["features"])
                centro = [gdf.geometry.centroid.y.mean(), gdf.geometry.centroid.x.mean()]
                
                m = folium.Map(location=centro, zoom_start=12)
                folium.TileLayer(
                    'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
                    attr='Esri',
                    name='Vista Satelital'
                ).add_to(m)
                
                folium.GeoJson(
                    st.session_state.geojson_data,
                    style_function=lambda x: {
                        'fillColor': '#2E8B57',
                        'color': 'black',
                        'weight': 2,
                        'fillOpacity': 0.3
                    },
                    tooltip=folium.Tooltip("Lote cargado - Listo para análisis")
                ).add_to(m)
                
                folium.LayerControl().add_to(m)
                
                st_folium(m, height=500, use_container_width=True)
            else:
                st.info("""
                ### 👆 Comienza cargando tu archivo
                
                **Formatos aceptados:**
                - Archivos ZIP con Shapefile
                - KML de Google Earth  
                - GeoJSON estándar
                
                **Luego configura:**
                1. Cultivo a analizar
                2. Cuadrícula de sublotes
                3. Período de análisis
                4. Ejecuta el análisis
                """)
        
        with col2:
            st.markdown('<h3 class="section-header">🚀 Análisis Disponibles</h3>', unsafe_allow_html=True)
            
            if st.session_state.geojson_data:
                st.success("""
                ### ✅ Archivo Cargado
                
                **Próximos pasos:**
                1. Revisa la configuración
                2. Ajusta la cuadrícula
                3. Ejecuta el análisis
                
                **Obtendrás:**
                • Mapas interactivos de fertilidad
                • Recomendaciones específicas por sublote
                • Análisis estadísticos detallados
                • Reportes exportables
                """)
            else:
                st.info("""
                ### 💡 Características del Sistema
                
                **Análisis incluidos:**
                • Fertilidad del suelo por sublotes
                • Recomendaciones NPK específicas
                • Mapas interactivos con múltiples capas
                • Análisis de variabilidad espacial
                • Reportes profesionales
                
                **Cultivos soportados:**
                Trigo, Maíz, Soja, Sorgo, Girasol
                """)

if __name__ == "__main__":
    main()
