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

def cargar_geojson(archivo):
    """Carga y procesa archivos GeoJSON"""
    try:
        if archivo.name.endswith('.zip'):
            with zipfile.ZipFile(archivo, 'r') as zip_ref:
                # Buscar GeoJSON en el ZIP
                for file in zip_ref.namelist():
                    if file.endswith(('.geojson', '.json')):
                        with zip_ref.open(file) as f:
                            return json.load(f)
        else:
            return json.load(archivo)
    except Exception as e:
        st.error(f"Error cargando archivo: {e}")
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
        
        # Agregar polígono
        if geojson_data:
            color = 'green' if resultados and resultados.get('salud_general', 0) > 60 else 'red'
            folium.GeoJson(
                geojson_data,
                style_function=lambda x: {
                    'fillColor': color,
                    'color': color,
                    'weight': 2,
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
        archivo = st.file_uploader(
            "Subir GeoJSON o ZIP",
            type=['geojson', 'json', 'zip'],
            help="Archivo GeoJSON o ZIP que contenga el polígono del lote"
        )
        
        if archivo:
            with st.spinner("Procesando archivo..."):
                geojson_data = cargar_geojson(archivo)
                if geojson_data:
                    st.session_state.geojson_data = geojson_data
                    st.success("✅ Archivo cargado correctamente")
        
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
        if st.button("🚀 Ejecutar Análisis", type="primary", use_container_width=True):
            if st.session_state.geojson_data:
                with st.spinner("Analizando cultivo..."):
                    analizador = AnalizadorCultivos()
                    st.session_state.resultados = analizador.analizar_cultivo(
                        st.session_state.geojson_data, cultivo, fecha_inicio, fecha_fin
                    )
            else:
                st.error("Primero carga un archivo GeoJSON")
    
    # Contenido principal
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown('<h3 class="section-header">🗺️ Mapa del Lote</h3>', unsafe_allow_html=True)
        
        if st.session_state.geojson_data:
            mapa = crear_mapa(st.session_state.geojson_data, st.session_state.resultados)
            st_folium(mapa, height=500, use_container_width=True)
        else:
            st.info("Carga un archivo GeoJSON para visualizar el mapa")
    
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
            st.info("Ejecuta el análisis para ver los resultados")

if __name__ == "__main__":
    main()
