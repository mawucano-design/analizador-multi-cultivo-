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

# Configuración de página
st.set_page_config(
    page_title="Analizador de Fertilidad Multi-Cultivo",
    page_icon="🌱",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS personalizado
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #2E8B57;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f8f9fa;
        padding: 1rem;
        border-radius: 10px;
        border-left: 4px solid #2E8B57;
    }
    .section-header {
        color: #2E8B57;
        border-bottom: 2px solid #2E8B57;
        padding-bottom: 0.5rem;
        margin-bottom: 1rem;
    }
    .warning-box {
        background-color: #fff3cd;
        border: 1px solid #ffeaa7;
        border-radius: 5px;
        padding: 1rem;
        margin: 1rem 0;
    }
    .nutriente-card {
        padding: 0.5rem;
        margin: 0.5rem 0;
        border-radius: 5px;
        border-left: 4px solid;
    }
    .tabla-resultados {
        font-size: 0.9rem;
    }
</style>
""", unsafe_allow_html=True)

# Configuración de cultivos con requerimientos de NPK
CULTIVOS = {
    "trigo": {
        "nombre": "Trigo",
        "ndvi_optimo": (0.6, 0.8),
        "color": "#FFD700",
        "npk_optimo": {"N": (80, 120), "P": (40, 60), "K": (50, 80)},
        "ph_optimo": (6.0, 7.0)
    },
    "maiz": {
        "nombre": "Maíz", 
        "ndvi_optimo": (0.7, 0.9),
        "color": "#32CD32",
        "npk_optimo": {"N": (120, 180), "P": (50, 80), "K": (80, 120)},
        "ph_optimo": (5.8, 7.0)
    },
    "soja": {
        "nombre": "Soja",
        "ndvi_optimo": (0.6, 0.85),
        "color": "#90EE90",
        "npk_optimo": {"N": (0, 20), "P": (40, 70), "K": (60, 100)},
        "ph_optimo": (6.0, 7.0)
    },
    "sorgo": {
        "nombre": "Sorgo",
        "ndvi_optimo": (0.5, 0.75),
        "color": "#DAA520",
        "npk_optimo": {"N": (80, 120), "P": (30, 50), "K": (60, 90)},
        "ph_optimo": (5.5, 7.5)
    },
    "girasol": {
        "nombre": "Girasol",
        "ndvi_optimo": (0.4, 0.7),
        "color": "#FF8C00",
        "npk_optimo": {"N": (60, 100), "P": (30, 50), "K": (80, 120)},
        "ph_optimo": (6.0, 7.5)
    }
}

class AnalizadorFertilidad:
    def __init__(self):
        self.config = None
    
    def dividir_en_sublotes(self, geojson_data, num_sublotes=4):
        """Divide el polígono principal en sublotes para análisis detallado"""
        try:
            gdf = gpd.GeoDataFrame.from_features(geojson_data["features"])
            
            # Si solo hay un polígono, lo dividimos en sublotes
            if len(gdf) == 1:
                bounds = gdf.total_bounds
                minx, miny, maxx, maxy = bounds
                
                sublotes = []
                if num_sublotes == 4:
                    # Dividir en 4 cuadrantes
                    midx = (minx + maxx) / 2
                    midy = (miny + maxy) / 2
                    
                    sublotes_coords = [
                        [[minx, miny], [midx, miny], [midx, midy], [minx, midy], [minx, miny]],
                        [[midx, miny], [maxx, miny], [maxx, midy], [midx, midy], [midx, miny]],
                        [[minx, midy], [midx, midy], [midx, maxy], [minx, maxy], [minx, midy]],
                        [[midx, midy], [maxx, midy], [maxx, maxy], [midx, maxy], [midx, midy]]
                    ]
                else:
                    # División simple en filas y columnas
                    for i in range(num_sublotes):
                        sublotes_coords = self._dividir_poligono_aleatorio(bounds, num_sublotes)
                
                # Crear GeoDataFrame con sublotes
                features = []
                for i, coords in enumerate(sublotes_coords):
                    feature = {
                        "type": "Feature",
                        "properties": {
                            "sublote_id": i + 1,
                            "nombre": f"Sublote {i + 1}",
                            "area_ha": random.uniform(5, 25)  # Área estimada
                        },
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [coords]
                        }
                    }
                    features.append(feature)
                
                geojson_sublotes = {
                    "type": "FeatureCollection",
                    "features": features
                }
                
                return geojson_sublotes
            else:
                # Si ya hay múltiples features, usarlos como sublotes
                for i, feature in enumerate(geojson_data["features"]):
                    if "properties" not in feature:
                        feature["properties"] = {}
                    feature["properties"]["sublote_id"] = i + 1
                    feature["properties"]["nombre"] = f"Sublote {i + 1}"
                    if "area_ha" not in feature["properties"]:
                        feature["properties"]["area_ha"] = random.uniform(5, 25)
                
                return geojson_data
                
        except Exception as e:
            st.error(f"Error dividiendo en sublotes: {str(e)}")
            return geojson_data
    
    def _dividir_poligono_aleatorio(self, bounds, num_sublotes):
        """Divide un polígono en sublotes de forma aleatoria"""
        minx, miny, maxx, maxy = bounds
        width = maxx - minx
        height = maxy - miny
        
        sublotes = []
        for i in range(num_sublotes):
            # Crear sublotes con variación aleatoria
            sub_minx = minx + (i * width / num_sublotes) + random.uniform(0, width * 0.1)
            sub_maxx = minx + ((i + 1) * width / num_sublotes) - random.uniform(0, width * 0.1)
            sub_miny = miny + random.uniform(0, height * 0.2)
            sub_maxy = maxy - random.uniform(0, height * 0.2)
            
            coords = [
                [sub_minx, sub_miny],
                [sub_maxx, sub_miny],
                [sub_maxx, sub_maxy],
                [sub_minx, sub_maxy],
                [sub_minx, sub_miny]
            ]
            sublotes.append(coords)
        
        return sublotes
    
    def analizar_fertilidad_sublotes(self, geojson_sublotes, cultivo, fecha_inicio, fecha_fin):
        """Analiza la fertilidad para cada sublote individualmente"""
        try:
            st.info("🔍 Analizando fertilidad por sublotes...")
            cultivo_info = CULTIVOS[cultivo]
            
            resultados_sublotes = []
            
            for feature in geojson_sublotes["features"]:
                sublote_id = feature["properties"]["sublote_id"]
                nombre_sublote = feature["properties"]["nombre"]
                area_ha = feature["properties"].get("area_ha", 10)
                
                # Generar datos de fertilidad únicos para cada sublote
                nitrogeno = random.uniform(20, 150)
                fosforo = random.uniform(10, 80)
                potasio = random.uniform(30, 120)
                ph = random.uniform(5.0, 8.0)
                materia_organica = random.uniform(1.5, 4.5)
                
                # Calcular índices de fertilidad
                indice_n = self._calcular_indice_nutriente(nitrogeno, cultivo_info['npk_optimo']['N'])
                indice_p = self._calcular_indice_nutriente(fosforo, cultivo_info['npk_optimo']['P'])
                indice_k = self._calcular_indice_nutriente(potasio, cultivo_info['npk_optimo']['K'])
                indice_ph = self._calcular_indice_ph(ph, cultivo_info['ph_optimo'])
                
                # Fertilidad general
                fertilidad_general = (indice_n * 0.35 + indice_p * 0.25 + indice_k * 0.25 + indice_ph * 0.15)
                
                # Recomendaciones de fertilización
                recomendaciones = self._generar_recomendaciones_npk(
                    nitrogeno, fosforo, potasio, ph, cultivo_info
                )
                
                # Determinar color para el mapa
                color_fertilidad = self._obtener_color_fertilidad(fertilidad_general)
                color_recomendacion = self._obtener_color_recomendacion(recomendaciones[0])  # Usar primera recomendación
                
                resultado_sublote = {
                    'sublote_id': sublote_id,
                    'nombre_sublote': nombre_sublote,
                    'area_ha': round(area_ha, 2),
                    'fertilidad_general': round(fertilidad_general, 1),
                    'nutrientes': {
                        'nitrogeno': round(nitrogeno, 1),
                        'fosforo': round(fosforo, 1),
                        'potasio': round(potasio, 1),
                        'ph': round(ph, 2),
                        'materia_organica': round(materia_organica, 2)
                    },
                    'indices': {
                        'N': round(indice_n, 1),
                        'P': round(indice_p, 1),
                        'K': round(indice_k, 1),
                        'pH': round(indice_ph, 1)
                    },
                    'recomendaciones_npk': recomendaciones,
                    'color_fertilidad': color_fertilidad,
                    'color_recomendacion': color_recomendacion,
                    'dosis_npk': self._calcular_dosis_npk(nitrogeno, fosforo, potasio, cultivo_info)
                }
                
                resultados_sublotes.append(resultado_sublote)
                st.info(f"✅ Sublote {sublote_id} analizado - Fertilidad: {fertilidad_general:.1f}%")
            
            st.success(f"🎉 Análisis completado para {len(resultados_sublotes)} sublotes")
            
            return {
                'sublotes': resultados_sublotes,
                'cultivo': cultivo_info['nombre'],
                'fecha_analisis': datetime.now().strftime("%d/%m/%Y %H:%M"),
                'fecha_inicio': fecha_inicio.strftime("%d/%m/%Y"),
                'fecha_fin': fecha_fin.strftime("%d/%m/%Y")
            }
            
        except Exception as e:
            st.error(f"❌ Error en análisis de sublotes: {str(e)}")
            return None
    
    def _calcular_indice_nutriente(self, valor, rango_optimo):
        """Calcula índice de adecuación del nutriente (0-100)"""
        optimo_medio = (rango_optimo[0] + rango_optimo[1]) / 2
        desviacion = abs(valor - optimo_medio)
        rango_tolerancia = (rango_optimo[1] - rango_optimo[0]) / 2
        
        if desviacion <= rango_tolerancia:
            return 100 - (desviacion / rango_tolerancia * 20)
        else:
            return max(0, 80 - ((desviacion - rango_tolerancia) / rango_tolerancia * 40))
    
    def _calcular_indice_ph(self, ph, rango_optimo):
        """Calcula índice de adecuación del pH"""
        if rango_optimo[0] <= ph <= rango_optimo[1]:
            return 100
        elif ph < rango_optimo[0]:
            desviacion = rango_optimo[0] - ph
            return max(0, 100 - desviacion * 30)
        else:
            desviacion = ph - rango_optimo[1]
            return max(0, 100 - desviacion * 30)
    
    def _generar_recomendaciones_npk(self, nitrogeno, fosforo, potasio, ph, cultivo_info):
        """Genera recomendaciones específicas de fertilización NPK"""
        recomendaciones = []
        
        # Recomendaciones para Nitrógeno
        optimo_n = cultivo_info['npk_optimo']['N']
        if nitrogeno < optimo_n[0]:
            deficit = optimo_n[0] - nitrogeno
            dosis = deficit * 2.0
            recomendaciones.append(f"Aplicar {dosis:.0f} kg/ha de Urea")
        elif nitrogeno > optimo_n[1]:
            recomendaciones.append("Nivel adecuado, no fertilizar")
        else:
            recomendaciones.append("Nivel óptimo")
        
        # Recomendaciones para Fósforo
        optimo_p = cultivo_info['npk_optimo']['P']
        if fosforo < optimo_p[0]:
            deficit = optimo_p[0] - fosforo
            dosis = deficit * 2.3
            recomendaciones.append(f"Aplicar {dosis:.0f} kg/ha de Superfosfato")
        elif fosforo > optimo_p[1]:
            recomendaciones.append("Nivel adecuado, no fertilizar")
        else:
            recomendaciones.append("Nivel óptimo")
        
        # Recomendaciones para Potasio
        optimo_k = cultivo_info['npk_optimo']['K']
        if potasio < optimo_k[0]:
            deficit = optimo_k[0] - potasio
            dosis = deficit * 1.7
            recomendaciones.append(f"Aplicar {dosis:.0f} kg/ha de Cloruro de Potasio")
        elif potasio > optimo_k[1]:
            recomendaciones.append("Nivel adecuado, no fertilizar")
        else:
            recomendaciones.append("Nivel óptimo")
        
        # Recomendaciones para pH
        optimo_ph = cultivo_info['ph_optimo']
        if ph < optimo_ph[0]:
            recomendaciones.append(f"Encalar con 1-2 tn/ha de calcáreo")
        elif ph > optimo_ph[1]:
            recomendaciones.append(f"Aplicar azufre para reducir pH")
        else:
            recomendaciones.append(f"pH óptimo")
        
        return recomendaciones
    
    def _calcular_dosis_npk(self, nitrogeno, fosforo, potasio, cultivo_info):
        """Calcula dosis específicas de NPK"""
        optimo_n = cultivo_info['npk_optimo']['N']
        optimo_p = cultivo_info['npk_optimo']['P']
        optimo_k = cultivo_info['npk_optimo']['K']
        
        dosis_n = max(0, (optimo_n[0] - nitrogeno) * 2.0) if nitrogeno < optimo_n[0] else 0
        dosis_p = max(0, (optimo_p[0] - fosforo) * 2.3) if fosforo < optimo_p[0] else 0
        dosis_k = max(0, (optimo_k[0] - potasio) * 1.7) if potasio < optimo_k[0] else 0
        
        return {
            'N': round(dosis_n, 1),
            'P': round(dosis_p, 1),
            'K': round(dosis_k, 1)
        }
    
    def _obtener_color_fertilidad(self, fertilidad):
        """Determina color basado en el nivel de fertilidad"""
        if fertilidad >= 80:
            return 'green'
        elif fertilidad >= 60:
            return 'yellow'
        elif fertilidad >= 40:
            return 'orange'
        else:
            return 'red'
    
    def _obtener_color_recomendacion(self, recomendacion):
        """Determina color basado en la recomendación"""
        if "óptimo" in recomendacion.lower() or "adecuado" in recomendacion.lower():
            return 'blue'
        elif "aplicar" in recomendacion.lower():
            return 'purple'
        else:
            return 'gray'

def procesar_archivo_subido(archivo):
    """Procesa archivos ZIP y KML"""
    try:
        st.info(f"📂 Procesando archivo: {archivo.name}")
        
        if archivo.name.lower().endswith('.zip'):
            return procesar_archivo_zip(archivo.read(), archivo.name)
        elif archivo.name.lower().endswith('.kml'):
            return procesar_archivo_kml(archivo.read(), archivo.name)
        else:
            st.error("❌ Formato no soportado. Solo se aceptan ZIP y KML.")
            return None
            
    except Exception as e:
        st.error(f"❌ Error procesando archivo: {str(e)}")
        return None

def procesar_archivo_zip(contenido_zip, nombre_archivo):
    """Procesa archivos ZIP que contengan Shapefiles o KML"""
    try:
        with zipfile.ZipFile(io.BytesIO(contenido_zip), 'r') as zip_ref:
            archivos = zip_ref.namelist()
            st.info(f"📁 Archivos en el ZIP: {', '.join(archivos)}")
            
            # Buscar Shapefiles (.shp)
            shp_files = [f for f in archivos if f.lower().endswith('.shp')]
            if shp_files:
                return procesar_shapefile_desde_zip(zip_ref, shp_files[0])
            
            # Buscar KML
            kml_files = [f for f in archivos if f.lower().endswith('.kml')]
            if kml_files:
                return procesar_kml_desde_zip(zip_ref, kml_files[0])
            
            st.error("❌ No se encontraron archivos Shapefile (.shp) o KML (.kml) en el ZIP")
            return None
            
    except Exception as e:
        st.error(f"❌ Error procesando ZIP: {str(e)}")
        return None

def procesar_shapefile_desde_zip(zip_ref, shp_file):
    """Procesa Shapefile desde archivo ZIP"""
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            # Extraer todos los archivos del shapefile
            base_name = os.path.splitext(shp_file)[0]
            for file in zip_ref.namelist():
                if file.startswith(base_name):
                    zip_ref.extract(file, temp_dir)
            
            # Leer el shapefile
            shp_path = os.path.join(temp_dir, shp_file)
            gdf = gpd.read_file(shp_path)
            
            st.success(f"✅ Shapefile procesado: {len(gdf)} polígonos encontrados")
            return json.loads(gdf.to_json())
            
    except Exception as e:
        st.error(f"❌ Error procesando Shapefile: {str(e)}")
        return None

def procesar_kml_desde_zip(zip_ref, kml_file):
    """Procesa KML desde archivo ZIP"""
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_ref.extract(kml_file, temp_dir)
            kml_path = os.path.join(temp_dir, kml_file)
            gdf = gpd.read_file(kml_path, driver='KML')
            
            st.success(f"✅ KML procesado: {len(gdf)} polígonos encontrados")
            return json.loads(gdf.to_json())
            
    except Exception as e:
        st.error(f"❌ Error procesando KML: {str(e)}")
        return None

def procesar_archivo_kml(contenido_kml, nombre_archivo):
    """Procesa archivos KML directos"""
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            kml_path = os.path.join(temp_dir, "archivo.kml")
            with open(kml_path, 'wb') as f:
                f.write(contenido_kml)
            
            gdf = gpd.read_file(kml_path, driver='KML')
            st.success(f"✅ KML procesado: {len(gdf)} polígonos encontrados")
            return json.loads(gdf.to_json())
            
    except Exception as e:
        st.error(f"❌ Error procesando KML: {str(e)}")
        return None

def crear_mapa_fertilidad(geojson_sublotes, resultados_sublotes):
    """Crea mapa de fertilidad por sublotes"""
    try:
        gdf = gpd.GeoDataFrame.from_features(geojson_sublotes["features"])
        centro = [gdf.geometry.centroid.y.mean(), gdf.geometry.centroid.x.mean()]
        
        m = folium.Map(location=centro, zoom_start=13)
        
        # Capa base
        folium.TileLayer(
            'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
            attr='Esri',
            name='Satélite'
        ).add_to(m)
        
        # Agregar sublotes con colores según fertilidad
        for feature in geojson_sublotes["features"]:
            sublote_id = feature["properties"]["sublote_id"]
            resultado = next((r for r in resultados_sublotes if r['sublote_id'] == sublote_id), None)
            
            if resultado:
                color = resultado['color_fertilidad']
                popup_text = f"""
                <b>Sublote {sublote_id}</b><br>
                <b>Fertilidad:</b> {resultado['fertilidad_general']}%<br>
                <b>Área:</b> {resultado['area_ha']} ha<br>
                <b>N:</b> {resultado['nutrientes']['nitrogeno']} ppm<br>
                <b>P:</b> {resultado['nutrientes']['fosforo']} ppm<br>
                <b>K:</b> {resultado['nutrientes']['potasio']} ppm<br>
                <b>pH:</b> {resultado['nutrientes']['ph']}
                """
                
                folium.GeoJson(
                    feature,
                    style_function=lambda x, color=color: {
                        'fillColor': color,
                        'color': 'black',
                        'weight': 2,
                        'fillOpacity': 0.7
                    },
                    popup=folium.Popup(popup_text, max_width=300)
                ).add_to(m)
        
        # Leyenda
        legend_html = '''
        <div style="position: fixed; 
                    bottom: 50px; left: 50px; width: 200px; height: 160px; 
                    background-color: white; border:2px solid grey; z-index:9999;
                    font-size:14px; padding: 10px">
        <p><b>Leyenda Fertilidad</b></p>
        <p><i style="background:green; width:15px; height:15px; display:inline-block; margin-right:5px;"></i> Alta (80-100%)</p>
        <p><i style="background:yellow; width:15px; height:15px; display:inline-block; margin-right:5px;"></i> Media (60-79%)</p>
        <p><i style="background:orange; width:15px; height:15px; display:inline-block; margin-right:5px;"></i> Baja (40-59%)</p>
        <p><i style="background:red; width:15px; height:15px; display:inline-block; margin-right:5px;"></i> Muy Baja (<40%)</p>
        </div>
        '''
        m.get_root().html.add_child(folium.Element(legend_html))
        
        folium.LayerControl().add_to(m)
        return m
        
    except Exception as e:
        st.error(f"Error creando mapa de fertilidad: {e}")
        return folium.Map(location=[-34.6037, -58.3816], zoom_start=4)

def crear_mapa_recomendaciones(geojson_sublotes, resultados_sublotes):
    """Crea mapa de recomendaciones NPK por sublotes"""
    try:
        gdf = gpd.GeoDataFrame.from_features(geojson_sublotes["features"])
        centro = [gdf.geometry.centroid.y.mean(), gdf.geometry.centroid.x.mean()]
        
        m = folium.Map(location=centro, zoom_start=13)
        
        # Capa base
        folium.TileLayer(
            'OpenStreetMap',
            name='OpenStreetMap'
        ).add_to(m)
        
        # Agregar sublotes con colores según recomendaciones
        for feature in geojson_sublotes["features"]:
            sublote_id = feature["properties"]["sublote_id"]
            resultado = next((r for r in resultados_sublotes if r['sublote_id'] == sublote_id), None)
            
            if resultado:
                color = resultado['color_recomendacion']
                recomendacion_principal = resultado['recomendaciones_npk'][0]
                popup_text = f"""
                <b>Sublote {sublote_id}</b><br>
                <b>Recomendación:</b> {recomendacion_principal}<br>
                <b>Dosis N:</b> {resultado['dosis_npk']['N']} kg/ha<br>
                <b>Dosis P:</b> {resultado['dosis_npk']['P']} kg/ha<br>
                <b>Dosis K:</b> {resultado['dosis_npk']['K']} kg/ha<br>
                <b>Fertilidad:</b> {resultado['fertilidad_general']}%
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
                    popup=folium.Popup(popup_text, max_width=300)
                ).add_to(m)
        
        # Leyenda
        legend_html = '''
        <div style="position: fixed; 
                    bottom: 50px; left: 50px; width: 220px; height: 120px; 
                    background-color: white; border:2px solid grey; z-index:9999;
                    font-size:14px; padding: 10px">
        <p><b>Leyenda Recomendaciones</b></p>
        <p><i style="background:blue; width:15px; height:15px; display:inline-block; margin-right:5px;"></i> No fertilizar</p>
        <p><i style="background:purple; width:15px; height:15px; display:inline-block; margin-right:5px;"></i> Aplicar fertilizante</p>
        <p><i style="background:gray; width:15px; height:15px; display:inline-block; margin-right:5px;"></i> Otras acciones</p>
        </div>
        '''
        m.get_root().html.add_child(folium.Element(legend_html))
        
        folium.LayerControl().add_to(m)
        return m
        
    except Exception as e:
        st.error(f"Error creando mapa de recomendaciones: {e}")
        return folium.Map(location=[-34.6037, -58.3816], zoom_start=4)

def crear_tabla_resultados(resultados_sublotes):
    """Crea tabla resumen de resultados por sublote"""
    datos_tabla = []
    
    for resultado in resultados_sublotes:
        fila = {
            'Sublote': resultado['nombre_sublote'],
            'Área (ha)': resultado['area_ha'],
            'Fertilidad (%)': resultado['fertilidad_general'],
            'N (ppm)': resultado['nutrientes']['nitrogeno'],
            'P (ppm)': resultado['nutrientes']['fosforo'],
            'K (ppm)': resultado['nutrientes']['potasio'],
            'pH': resultado['nutrientes']['ph'],
            'M.O. (%)': resultado['nutrientes']['materia_organica'],
            'Dosis N (kg/ha)': resultado['dosis_npk']['N'],
            'Dosis P (kg/ha)': resultado['dosis_npk']['P'],
            'Dosis K (kg/ha)': resultado['dosis_npk']['K']
        }
        datos_tabla.append(fila)
    
    return pd.DataFrame(datos_tabla)

def exportar_geojson_resultados(geojson_sublotes, resultados_completos):
    """Exporta GeoJSON con todos los resultados del análisis"""
    try:
        # Crear copia del GeoJSON
        geojson_export = json.loads(json.dumps(geojson_sublotes))
        
        # Agregar resultados a las propiedades de cada feature
        for feature in geojson_export["features"]:
            sublote_id = feature["properties"]["sublote_id"]
            resultado = next((r for r in resultados_completos['sublotes'] if r['sublote_id'] == sublote_id), None)
            
            if resultado:
                feature["properties"].update({
                    'cultivo': resultados_completos['cultivo'],
                    'fecha_analisis': resultados_completos['fecha_analisis'],
                    'periodo_analisis': f"{resultados_completos['fecha_inicio']} a {resultados_completos['fecha_fin']}",
                    'fertilidad_general': resultado['fertilidad_general'],
                    'nitrogeno_ppm': resultado['nutrientes']['nitrogeno'],
                    'fosforo_ppm': resultado['nutrientes']['fosforo'],
                    'potasio_ppm': resultado['nutrientes']['potasio'],
                    'ph': resultado['nutrientes']['ph'],
                    'materia_organica': resultado['nutrientes']['materia_organica'],
                    'dosis_n_kg_ha': resultado['dosis_npk']['N'],
                    'dosis_p_kg_ha': resultado['dosis_npk']['P'],
                    'dosis_k_kg_ha': resultado['dosis_npk']['K'],
                    'recomendacion_n': resultado['recomendaciones_npk'][0],
                    'recomendacion_p': resultado['recomendaciones_npk'][1],
                    'recomendacion_k': resultado['recomendaciones_npk'][2],
                    'recomendacion_ph': resultado['recomendaciones_npk'][3]
                })
        
        return geojson_export
        
    except Exception as e:
        st.error(f"❌ Error exportando GeoJSON: {str(e)}")
        return None

def main():
    # Header principal
    st.markdown('<h1 class="main-header">🌱 Analizador de Fertilidad Multi-Cultivo</h1>', unsafe_allow_html=True)
    
    # Inicializar estado de la sesión
    if 'geojson_data' not in st.session_state:
        st.session_state.geojson_data = None
    if 'geojson_sublotes' not in st.session_state:
        st.session_state.geojson_sublotes = None
    if 'resultados' not in st.session_state:
        st.session_state.resultados = None
    if 'analisis_completado' not in st.session_state:
        st.session_state.analisis_completado = False
    
    # Sidebar
    with st.sidebar:
        st.markdown('<h3 class="section-header">⚙️ Configuración</h3>', unsafe_allow_html=True)
        
        # Selección de cultivo
        cultivo = st.selectbox(
            "Cultivo a analizar",
            options=list(CULTIVOS.keys()),
            format_func=lambda x: CULTIVOS[x]['nombre']
        )
        
        # Información del cultivo
        cultivo_info = CULTIVOS[cultivo]
        st.info(f"""
        **Cultivo:** {cultivo_info['nombre']}
        **NPK Óptimo:** 
        - N: {cultivo_info['npk_optimo']['N'][0]}-{cultivo_info['npk_optimo']['N'][1]} ppm
        - P: {cultivo_info['npk_optimo']['P'][0]}-{cultivo_info['npk_optimo']['P'][1]} ppm  
        - K: {cultivo_info['npk_optimo']['K'][0]}-{cultivo_info['npk_optimo']['K'][1]} ppm
        **pH Óptimo:** {cultivo_info['ph_optimo'][0]}-{cultivo_info['ph_optimo'][1]}
        """)
        
        # Carga de archivos
        st.markdown("---")
        st.markdown("### 📁 Cargar Polígono")
        
        # Información sobre formatos
        st.markdown("""
        <div class="warning-box">
        <strong>Formatos aceptados:</strong>
        <br>• <strong>ZIP</strong> con Shapefile (.shp, .dbf, .shx)
        <br>• <strong>KML</strong> de Google Earth
        </div>
        """, unsafe_allow_html=True)
        
        archivo = st.file_uploader(
            "Subir archivo ZIP o KML",
            type=['zip', 'kml'],
            help="Archivo ZIP con Shapefile o KML de Google Earth"
        )
        
        if archivo is not None:
            if st.session_state.geojson_data is None or st.button("🔄 Reprocesar archivo"):
                with st.spinner("Procesando archivo..."):
                    geojson_data = procesar_archivo_subido(archivo)
                    if geojson_data is not None:
                        st.session_state.geojson_data = geojson_data
                        st.session_state.resultados = None
                        st.session_state.analisis_completado = False
                        st.success("✅ Archivo cargado correctamente")
        
        # Número de sublotes
        st.markdown("---")
        st.markdown("### 🗂️ Configuración de Sublotes")
        num_sublotes = st.slider("Número de sublotes", min_value=2, max_value=8, value=4)
        
        # Fechas de análisis
        st.markdown("---")
        st.markdown("### 📅 Período de Análisis")
        col1, col2 = st.columns(2)
        with col1:
            fecha_inicio = st.date_input("Desde", value=datetime.now() - timedelta(days=30))
        with col2:
            fecha_fin = st.date_input("Hasta", value=datetime.now())
        
        # Botón de análisis
        st.markdown("---")
        analizar_disabled = st.session_state.geojson_data is None
        
        if st.button(
            "🚀 Ejecutar Análisis de Fertilidad", 
            type="primary", 
            use_container_width=True,
            disabled=analizar_disabled
        ):
            if st.session_state.geojson_data:
                with st.spinner("🔄 Iniciando análisis de fertilidad..."):
                    try:
                        analizador = AnalizadorFertilidad()
                        
                        # Dividir en sublotes
                        st.info("🗂️ Dividiendo en sublotes...")
                        geojson_sublotes = analizador.dividir_en_sublotes(
                            st.session_state.geojson_data, num_sublotes
                        )
                        st.session_state.geojson_sublotes = geojson_sublotes
                        
                        # Analizar fertilidad por sublote
                        resultados = analizador.analizar_fertilidad_sublotes(
                            geojson_sublotes, cultivo, fecha_inicio, fecha_fin
                        )
                        
                        if resultados is not None:
                            st.session_state.resultados = resultados
                            st.session_state.analisis_completado = True
                            st.success("🎉 ¡Análisis completado exitosamente!")
                        else:
                            st.error("❌ No se pudieron generar los resultados")
                            
                    except Exception as e:
                        st.error(f"❌ Error durante el análisis: {str(e)}")
            else:
                st.error("❌ Primero carga un archivo con el polígono del lote")
    
    # Contenido principal
    if st.session_state.analisis_completado and st.session_state.resultados:
        # Mostrar resultados completos
        resultados = st.session_state.resultados
        
        # Pestañas para diferentes visualizaciones
        tab1, tab2, tab3, tab4 = st.tabs(["🗺️ Mapa Fertilidad", "🧪 Mapa Recomendaciones", "📊 Tabla Resultados", "📥 Exportar"])
        
        with tab1:
            st.markdown('<h3 class="section-header">🗺️ Mapa de Fertilidad por Sublotes</h3>', unsafe_allow_html=True)
            mapa_fertilidad = crear_mapa_fertilidad(
                st.session_state.geojson_sublotes, 
                resultados['sublotes']
            )
            st_folium(mapa_fertilidad, height=500, use_container_width=True)
            
        with tab2:
            st.markdown('<h3 class="section-header">🧪 Mapa de Recomendaciones NPK</h3>', unsafe_allow_html=True)
            mapa_recomendaciones = crear_mapa_recomendaciones(
                st.session_state.geojson_sublotes, 
                resultados['sublotes']
            )
            st_folium(mapa_recomendaciones, height=500, use_container_width=True)
            
        with tab3:
            st.markdown('<h3 class="section-header">📊 Tabla de Resultados por Sublote</h3>', unsafe_allow_html=True)
            
            # Métricas generales
            col1, col2, col3 = st.columns(3)
            with col1:
                fert_promedio = np.mean([s['fertilidad_general'] for s in resultados['sublotes']])
                st.metric("Fertilidad Promedio", f"{fert_promedio:.1f}%")
            with col2:
                total_ha = sum([s['area_ha'] for s in resultados['sublotes']])
                st.metric("Área Total", f"{total_ha:.1f} ha")
            with col3:
                st.metric("Número de Sublotes", len(resultados['sublotes']))
            
            # Tabla de resultados
            df_resultados = crear_tabla_resultados(resultados['sublotes'])
            st.dataframe(df_resultados, use_container_width=True)
            
            # Resumen de recomendaciones
            st.markdown("### 💡 Resumen de Recomendaciones")
            for sublote in resultados['sublotes']:
                with st.expander(f"Sublote {sublote['sublote_id']} - {sublote['nombre_sublote']}"):
                    for recomendacion in sublote['recomendaciones_npk']:
                        st.write(f"• {recomendacion}")
            
        with tab4:
            st.markdown('<h3 class="section-header">📥 Exportar Resultados</h3>', unsafe_allow_html=True)
            
            # Exportar GeoJSON
            geojson_export = exportar_geojson_resultados(
                st.session_state.geojson_sublotes, 
                resultados
            )
            
            if geojson_export:
                geojson_str = json.dumps(geojson_export, indent=2, ensure_ascii=False)
                
                st.download_button(
                    label="📥 Descargar GeoJSON con Resultados",
                    data=geojson_str,
                    file_name=f"fertilidad_{cultivo}_{datetime.now().strftime('%Y%m%d_%H%M')}.geojson",
                    mime="application/json",
                    type="primary",
                    use_container_width=True
                )
            
            # Exportar CSV
            df_export = crear_tabla_resultados(resultados['sublotes'])
            csv_data = df_export.to_csv(index=False, encoding='utf-8')
            
            st.download_button(
                label="📊 Descargar Tabla en CSV",
                data=csv_data,
                file_name=f"resultados_fertilidad_{cultivo}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                mime="text/csv",
                use_container_width=True
            )
            
            # Información del análisis
            st.markdown("### 📋 Información del Análisis")
            st.write(f"**Cultivo:** {resultados['cultivo']}")
            st.write(f"**Fecha de análisis:** {resultados['fecha_analisis']}")
            st.write(f"**Período analizado:** {resultados['fecha_inicio']} a {resultados['fecha_fin']}")
            st.write(f"**Número de sublotes:** {len(resultados['sublotes'])}")
            st.write(f"**Área total:** {sum([s['area_ha'] for s in resultados['sublotes']]):.1f} ha")
    
    else:
        # Estado inicial o sin análisis
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.markdown('<h3 class="section-header">🗺️ Mapa del Lote</h3>', unsafe_allow_html=True)
            
            if st.session_state.geojson_data:
                # Mapa simple del polígono cargado
                gdf = gpd.GeoDataFrame.from_features(st.session_state.geojson_data["features"])
                centro = [gdf.geometry.centroid.y.mean(), gdf.geometry.centroid.x.mean()]
                
                m = folium.Map(location=centro, zoom_start=12)
                folium.TileLayer(
                    'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
                    attr='Esri',
                    name='Satélite'
                ).add_to(m)
                
                folium.GeoJson(st.session_state.geojson_data).add_to(m)
                folium.LayerControl().add_to(m)
                
                st_folium(m, height=500, use_container_width=True)
                
                # Información del polígono
                if st.session_state.geojson_data.get('features'):
                    feature = st.session_state.geojson_data['features'][0]
                    propiedades = feature.get('properties', {})
                    nombre = propiedades.get('name', 'Sin nombre')
                    area_ha = propiedades.get('area_ha', 'N/A')
                    st.info(f"**Polígono:** {nombre} | **Área:** {area_ha} ha")
            else:
                st.info("👆 Carga un archivo ZIP o KML para visualizar el mapa")
        
        with col2:
            st.markdown('<h3 class="section-header">📊 Análisis de Fertilidad</h3>', unsafe_allow_html=True)
            
            if st.session_state.geojson_data:
                st.info("👆 Ejecuta el análisis para ver los resultados de fertilidad por sublotes")
            else:
                st.info("""
                💡 **Para comenzar:**
                1. Selecciona el cultivo
                2. Carga un archivo ZIP o KML
                3. Configura el número de sublotes
                4. Ejecuta el análisis
                
                **Obtendrás:**
                • Mapas de fertilidad por sublotes
                • Recomendaciones específicas de NPK
                • Tablas de resultados detallados
                • Exportación en múltiples formatos
                """)

if __name__ == "__main__":
    main()
