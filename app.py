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

# Configuración de página
st.set_page_config(
    page_title="Analizador Multi-Cultivo",
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
</style>
""", unsafe_allow_html=True)

# Configuración de cultivos
CULTIVOS = {
    "trigo": {"nombre": "Trigo", "ndvi_optimo": (0.6, 0.8), "color": "#FFD700"},
    "maiz": {"nombre": "Maíz", "ndvi_optimo": (0.7, 0.9), "color": "#32CD32"},
    "soja": {"nombre": "Soja", "ndvi_optimo": (0.6, 0.85), "color": "#90EE90"},
    "sorgo": {"nombre": "Sorgo", "ndvi_optimo": (0.5, 0.75), "color": "#DAA520"},
    "girasol": {"nombre": "Girasol", "ndvi_optimo": (0.4, 0.7), "color": "#FF8C00"}
}

class AnalizadorCultivos:
    def __init__(self):
        self.config = None
    
    def analizar_cultivo(self, geojson_data, cultivo, fecha_inicio, fecha_fin):
        """Analiza el cultivo con datos simulados"""
        try:
            # Simulación de análisis basado en el cultivo
            cultivo_info = CULTIVOS[cultivo]
            ndvi_optimo = cultivo_info['ndvi_optimo']
            
            # Datos simulados realistas
            import random
            ndvi_media = random.uniform(ndvi_optimo[0] - 0.1, ndvi_optimo[1] + 0.1)
            ndvi_media = max(0.1, min(0.95, ndvi_media))
            
            # Calcular salud
            salud = max(0, min(100, (ndvi_media - 0.2) / 0.6 * 100))
            
            return {
                'salud_general': round(salud, 1),
                'ndvi_media': round(ndvi_media, 3),
                'biomasa_estimada': round(random.uniform(2000, 8000), 0),
                'recomendacion': self._generar_recomendacion(salud, cultivo),
                'fecha_analisis': datetime.now().strftime("%d/%m/%Y %H:%M")
            }
        except Exception as e:
            st.error(f"Error en análisis: {str(e)}")
            return None
    
    def _generar_recomendacion(self, salud, cultivo):
        if salud >= 80:
            return "✅ Condiciones óptimas. Continuar con manejo actual."
        elif salud >= 60:
            return "⚠️ Buen estado. Monitorear desarrollo."
        elif salud >= 40:
            return "🔶 Estado regular. Evaluar fertilización."
        else:
            return "🔴 Estado crítico. Revisión urgente necesaria."

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
            # Determinar color según salud
            if resultados and resultados.get('salud_general'):
                salud = resultados['salud_general']
                if salud >= 80:
                    color = 'green'
                elif salud >= 60:
                    color = 'orange'
                elif salud >= 40:
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
    st.markdown('<h1 class="main-header">🌱 Analizador Multi-Cultivo</h1>', unsafe_allow_html=True)
    
    # Inicializar estado
    if 'geojson_data' not in st.session_state:
        st.session_state.geojson_data = None
    if 'resultados' not in st.session_state:
        st.session_state.resultados = None
    
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
        st.info(f"""
        **Cultivo seleccionado:** {CULTIVOS[cultivo]['nombre']}
        **NDVI óptimo:** {CULTIVOS[cultivo]['ndvi_optimo'][0]} - {CULTIVOS[cultivo]['ndvi_optimo'][1]}
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
        
        if archivo:
            with st.spinner("Procesando archivo..."):
                geojson_data = procesar_archivo_subido(archivo)
                if geojson_data:
                    st.session_state.geojson_data = geojson_data
                    st.session_state.resultados = None  # Resetear resultados anteriores
        
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
            "🚀 Ejecutar Análisis", 
            type="primary", 
            use_container_width=True,
            disabled=analizar_disabled
        ):
            if st.session_state.geojson_data:
                with st.spinner("Analizando cultivo..."):
                    analizador = AnalizadorCultivos()
                    st.session_state.resultados = analizador.analizar_cultivo(
                        st.session_state.geojson_data, cultivo, fecha_inicio, fecha_fin
                    )
            else:
                st.error("Primero carga un archivo con el polígono del lote")
    
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
                st.info(f"**Polígono cargado:** {nombre}")
        else:
            st.info("👆 Carga un archivo ZIP o KML para visualizar el mapa")
    
    with col2:
        st.markdown('<h3 class="section-header">📊 Resultados</h3>', unsafe_allow_html=True)
        
        if st.session_state.resultados:
            resultados = st.session_state.resultados
            
            # Métricas principales
            col_a, col_b = st.columns(2)
            with col_a:
                st.metric("Salud General", f"{resultados['salud_general']}%")
            with col_b:
                st.metric("NDVI Medio", f"{resultados['ndvi_media']}")
            
            st.metric("Biomasa Estimada", f"{resultados['biomasa_estimada']} kg/ha")
            
            # Recomendación
            st.markdown("---")
            st.markdown("### 💡 Recomendación")
            st.info(resultados['recomendacion'])
            
            # Información adicional
            st.markdown("---")
            st.markdown("### 📋 Información")
            st.write(f"**Cultivo:** {CULTIVOS[cultivo]['nombre']}")
            st.write(f"**Fecha análisis:** {resultados['fecha_analisis']}")
            st.write(f"**Período:** {fecha_inicio} a {fecha_fin}")
            
        else:
            if st.session_state.geojson_data:
                st.info("👆 Ejecuta el análisis para ver los resultados")
            else:
                st.info("💡 Carga un archivo y ejecuta el análisis para ver los resultados aquí")

if __name__ == "__main__":
    main()
