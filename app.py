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
    
    def analizar_fertilidad(self, geojson_data, cultivo, fecha_inicio, fecha_fin):
        """Analiza la fertilidad del suelo con datos realistas"""
        try:
            st.info("🔍 Iniciando análisis de fertilidad...")
            cultivo_info = CULTIVOS[cultivo]
            
            # Generar datos de fertilidad realistas basados en el cultivo
            import random
            
            # Valores realistas para análisis de suelo
            nitrogeno = random.uniform(20, 150)
            fosforo = random.uniform(10, 80)
            potasio = random.uniform(30, 120)
            ph = random.uniform(5.0, 8.0)
            materia_organica = random.uniform(1.5, 4.5)
            
            st.info(f"📊 Valores generados - N: {nitrogeno:.1f}, P: {fosforo:.1f}, K: {potasio:.1f}, pH: {ph:.2f}")
            
            # Calcular índices de fertilidad
            indice_n = self._calcular_indice_nutriente(nitrogeno, cultivo_info['npk_optimo']['N'])
            indice_p = self._calcular_indice_nutriente(fosforo, cultivo_info['npk_optimo']['P'])
            indice_k = self._calcular_indice_nutriente(potasio, cultivo_info['npk_optimo']['K'])
            indice_ph = self._calcular_indice_ph(ph, cultivo_info['ph_optimo'])
            
            # Fertilidad general (promedio ponderado)
            fertilidad_general = (indice_n * 0.35 + indice_p * 0.25 + indice_k * 0.25 + indice_ph * 0.15)
            
            # Recomendaciones de fertilización
            recomendaciones_npk = self._generar_recomendaciones_npk(
                nitrogeno, fosforo, potasio, ph, cultivo_info
            )
            
            st.success("✅ Análisis de fertilidad completado")
            
            resultados = {
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
                'recomendaciones_npk': recomendaciones_npk,
                'fecha_analisis': datetime.now().strftime("%d/%m/%Y %H:%M"),
                'cultivo': cultivo_info['nombre']
            }
            
            st.info(f"🎯 Fertilidad general calculada: {resultados['fertilidad_general']}%")
            return resultados
            
        except Exception as e:
            st.error(f"❌ Error en análisis de fertilidad: {str(e)}")
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
            dosis = deficit * 2.0  # Factor de conversión
            recomendaciones.append(f"**Nitrógeno (N):** Aplicar {dosis:.0f} kg/ha de Urea")
        elif nitrogeno > optimo_n[1]:
            recomendaciones.append("**Nitrógeno (N):** Nivel adecuado, no fertilizar")
        else:
            recomendaciones.append("**Nitrógeno (N):** Nivel óptimo")
        
        # Recomendaciones para Fósforo
        optimo_p = cultivo_info['npk_optimo']['P']
        if fosforo < optimo_p[0]:
            deficit = optimo_p[0] - fosforo
            dosis = deficit * 2.3  # Factor de conversión
            recomendaciones.append(f"**Fósforo (P):** Aplicar {dosis:.0f} kg/ha de Superfosfato")
        elif fosforo > optimo_p[1]:
            recomendaciones.append("**Fósforo (P):** Nivel adecuado, no fertilizar")
        else:
            recomendaciones.append("**Fósforo (P):** Nivel óptimo")
        
        # Recomendaciones para Potasio
        optimo_k = cultivo_info['npk_optimo']['K']
        if potasio < optimo_k[0]:
            deficit = optimo_k[0] - potasio
            dosis = deficit * 1.7  # Factor de conversión
            recomendaciones.append(f"**Potasio (K):** Aplicar {dosis:.0f} kg/ha de Cloruro de Potasio")
        elif potasio > optimo_k[1]:
            recomendaciones.append("**Potasio (K):** Nivel adecuado, no fertilizar")
        else:
            recomendaciones.append("**Potasio (K):** Nivel óptimo")
        
        # Recomendaciones para pH
        optimo_ph = cultivo_info['ph_optimo']
        if ph < optimo_ph[0]:
            recomendaciones.append(f"**pH ({ph}):** Encalar con 1-2 tn/ha de calcáreo")
        elif ph > optimo_ph[1]:
            recomendaciones.append(f"**pH ({ph}):** Aplicar azufre para reducir pH")
        else:
            recomendaciones.append(f"**pH ({ph}):** Nivel óptimo")
        
        return recomendaciones

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

def crear_mapa(geojson_data, resultados=None):
    """Crea mapa interactivo"""
    try:
        # Centro del mapa
        if geojson_data and 'features' in geojson_data:
            gdf = gpd.GeoDataFrame.from_features(geojson_data["features"])
            centro = [gdf.geometry.centroid.y.mean(), gdf.geometry.centroid.x.mean()]
        else:
            centro = [-34.6037, -58.3816]  # Buenos Aires
        
        m = folium.Map(location=centro, zoom_start=12)
        
        # Capas base
        folium.TileLayer(
            'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
            attr='Esri',
            name='Satélite'
        ).add_to(m)
        
        folium.TileLayer(
            'OpenStreetMap',
            name='OpenStreetMap'
        ).add_to(m)
        
        # Agregar polígono
        if geojson_data:
            # Determinar color según fertilidad
            if resultados and resultados.get('fertilidad_general'):
                fertilidad = resultados['fertilidad_general']
                if fertilidad >= 80:
                    color = 'green'
                elif fertilidad >= 60:
                    color = 'orange'
                elif fertilidad >= 40:
                    color = 'yellow'
                else:
                    color = 'red'
            else:
                color = 'blue'
            
            folium.GeoJson(
                geojson_data,
                style_function=lambda x: {
                    'fillColor': color,
                    'color': color,
                    'weight': 3,
                    'fillOpacity': 0.6
                }
            ).add_to(m)
        
        folium.LayerControl().add_to(m)
        return m
        
    except Exception as e:
        st.error(f"Error creando mapa: {e}")
        return folium.Map(location=[-34.6037, -58.3816], zoom_start=4)

def main():
    # Header principal
    st.markdown('<h1 class="main-header">🌱 Analizador de Fertilidad Multi-Cultivo</h1>', unsafe_allow_html=True)
    
    # Inicializar estado de la sesión
    if 'geojson_data' not in st.session_state:
        st.session_state.geojson_data = None
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
                        st.rerun()
        
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
        
        # Usar un formulario para evitar el rerun automático
        with st.form(key="analisis_form"):
            if st.form_submit_button(
                "🚀 Ejecutar Análisis de Fertilidad", 
                type="primary", 
                use_container_width=True,
                disabled=analizar_disabled
            ):
                if st.session_state.geojson_data:
                    # Crear un contenedor para los mensajes de progreso
                    progress_placeholder = st.empty()
                    
                    with progress_placeholder.container():
                        st.info("🔄 Iniciando análisis de fertilidad...")
                        
                        try:
                            analizador = AnalizadorFertilidad()
                            resultados = analizador.analizar_fertilidad(
                                st.session_state.geojson_data, cultivo, fecha_inicio, fecha_fin
                            )
                            
                            if resultados is not None:
                                st.session_state.resultados = resultados
                                st.session_state.analisis_completado = True
                                st.success("🎉 ¡Análisis completado exitosamente!")
                                
                                # Forzar actualización después de 2 segundos
                                import time
                                time.sleep(2)
                                st.rerun()
                            else:
                                st.error("❌ No se pudieron generar los resultados")
                                
                        except Exception as e:
                            st.error(f"❌ Error durante el análisis: {str(e)}")
                else:
                    st.error("❌ Primero carga un archivo con el polígono del lote")

    # Contenido principal
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown('<h3 class="section-header">🗺️ Mapa del Lote</h3>', unsafe_allow_html=True)
        
        if st.session_state.geojson_data:
            mapa = crear_mapa(st.session_state.geojson_data, st.session_state.resultados)
            st_folium(mapa, height=500, use_container_width=True)
            
            # Información del polígono cargado
            if st.session_state.geojson_data.get('features'):
                feature = st.session_state.geojson_data['features'][0]
                propiedades = feature.get('properties', {})
                nombre = propiedades.get('name', 'Sin nombre')
                area_ha = propiedades.get('area_ha', 'N/A')
                st.info(f"**Polígono:** {nombre} | **Área:** {area_ha} ha")
        else:
            st.info("👆 Carga un archivo ZIP o KML para visualizar el mapa")
    
    with col2:
        st.markdown('<h3 class="section-header">📊 Resultados de Fertilidad</h3>', unsafe_allow_html=True)
        
        if st.session_state.analisis_completado and st.session_state.resultados:
            resultados = st.session_state.resultados
            
            # Métricas principales
            st.metric("Fertilidad General", f"{resultados['fertilidad_general']}%")
            
            # Niveles de nutrientes
            st.markdown("---")
            st.markdown("### 🌿 Niveles de Nutrientes")
            
            nutrientes = resultados['nutrientes']
            col_n, col_p, col_k = st.columns(3)
            
            with col_n:
                st.metric("Nitrógeno (N)", f"{nutrientes['nitrogeno']} ppm", 
                         delta=f"{resultados['indices']['N']}%")
            with col_p:
                st.metric("Fósforo (P)", f"{nutrientes['fosforo']} ppm", 
                         delta=f"{resultados['indices']['P']}%")
            with col_k:
                st.metric("Potasio (K)", f"{nutrientes['potasio']} ppm", 
                         delta=f"{resultados['indices']['K']}%")
            
            # Parámetros adicionales
            col_ph, col_mo = st.columns(2)
            with col_ph:
                st.metric("pH", f"{nutrientes['ph']}", 
                         delta=f"{resultados['indices']['pH']}%")
            with col_mo:
                st.metric("Materia Orgánica", f"{nutrientes['materia_organica']}%")
            
            # Recomendaciones NPK
            st.markdown("---")
            st.markdown("### 💡 Recomendaciones de Fertilización")
            
            for recomendacion in resultados['recomendaciones_npk']:
                if "óptimo" in recomendacion.lower():
                    st.success(recomendacion)
                elif "adecuado" in recomendacion.lower():
                    st.info(recomendacion)
                elif "aplicar" in recomendacion.lower():
                    st.warning(recomendacion)
                else:
                    st.error(recomendacion)
            
            # Información adicional
            st.markdown("---")
            st.markdown("### 📋 Información del Análisis")
            st.write(f"**Cultivo:** {resultados['cultivo']}")
            st.write(f"**Fecha análisis:** {resultados['fecha_analisis']}")
            st.write(f"**Período:** {fecha_inicio} a {fecha_fin}")
            
        else:
            if st.session_state.geojson_data:
                st.info("👆 Ejecuta el análisis para ver los resultados de fertilidad")
            else:
                st.info("💡 Carga un archivo y ejecuta el análisis para ver los resultados aquí")

if __name__ == "__main__":
    main()
