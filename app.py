import streamlit as st
import os
import json
import geopandas as gpd
import folium
from folium import plugins
from streamlit_folium import st_folium
import numpy as np
from datetime import datetime, timedelta
import tempfile
import zipfile
import io

# Configuración de la página
st.set_page_config(
    page_title="Analizador Multi-Cultivo",
    page_icon="🌱",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Configuración de cultivos
CULTIVOS = {
    "trigo": {
        "nombre": "Trigo",
        "ndvi_optimo": (0.6, 0.8),
        "ndwi_optimo": (0.2, 0.4),
        "color": "#FFD700"
    },
    "maiz": {
        "nombre": "Maíz", 
        "ndvi_optimo": (0.7, 0.9),
        "ndwi_optimo": (0.3, 0.5),
        "color": "#32CD32"
    },
    "soja": {
        "nombre": "Soja",
        "ndvi_optimo": (0.6, 0.85),
        "ndwi_optimo": (0.25, 0.45),
        "color": "#90EE90"
    },
    "sorgo": {
        "nombre": "Sorgo",
        "ndvi_optimo": (0.5, 0.75),
        "ndwi_optimo": (0.2, 0.4),
        "color": "#DAA520"
    },
    "girasol": {
        "nombre": "Girasol",
        "ndvi_optimo": (0.4, 0.7),
        "ndwi_optimo": (0.15, 0.35),
        "color": "#FF8C00"
    }
}

def crear_ejemplo_geojson():
    """Crea un archivo GeoJSON de ejemplo en zona agrícola"""
    ejemplo_geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "name": "Campo Ejemplo - Zona Agrícola",
                    "area_ha": 250,
                    "cultivo": "maiz"
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[
                        [-61.5, -32.9],
                        [-61.4, -32.9],
                        [-61.4, -32.8],
                        [-61.5, -32.8],
                        [-61.5, -32.9]
                    ]]
                }
            }
        ]
    }
    return ejemplo_geojson

def procesar_archivo_subido(archivo):
    """Procesa archivos GeoJSON o ZIP con polígonos"""
    try:
        if archivo.name.endswith('.geojson') or archivo.name.endswith('.json'):
            # Es un GeoJSON directo
            geojson_data = json.load(archivo)
            return geojson_data
        
        elif archivo.name.endswith('.zip'):
            # Es un ZIP, extraer GeoJSON
            with zipfile.ZipFile(archivo, 'r') as zip_ref:
                # Buscar archivos GeoJSON en el ZIP
                geojson_files = [f for f in zip_ref.namelist() if f.endswith(('.geojson', '.json'))]
                
                if not geojson_files:
                    st.error("❌ No se encontraron archivos GeoJSON en el ZIP")
                    return None
                
                # Tomar el primer GeoJSON encontrado
                with zip_ref.open(geojson_files[0]) as geojson_file:
                    geojson_data = json.load(geojson_file)
                    return geojson_data
        
        else:
            st.error("❌ Formato de archivo no soportado. Usa .geojson, .json o .zip")
            return None
            
    except Exception as e:
        st.error(f"❌ Error procesando archivo: {str(e)}")
        return None

def simular_analisis_sentinel(cultivo, area_ha=100):
    """
    Simula el análisis de Sentinel-2 (para demo)
    En producción, aquí iría la integración real con Sentinel Hub
    """
    import random
    
    # Simular resultados de análisis
    cultivo_info = CULTIVOS[cultivo]
    ndvi_optimo = cultivo_info['ndvi_optimo']
    ndwi_optimo = cultivo_info['ndwi_optimo']
    
    # Generar valores realistas según el cultivo
    ndvi_media = random.uniform(ndvi_optimo[0] - 0.2, ndvi_optimo[1] + 0.1)
    ndwi_media = random.uniform(ndwi_optimo[0] - 0.15, ndwi_optimo[1] + 0.1)
    
    # Calcular salud general
    salud_ndvi = max(0, min(100, (ndvi_media - (ndvi_optimo[0] - 0.3)) / (ndvi_optimo[1] - (ndvi_optimo[0] - 0.3)) * 100))
    salud_ndwi = max(0, min(100, (ndwi_media - (ndwi_optimo[0] - 0.2)) / (ndwi_optimo[1] - (ndwi_optimo[0] - 0.2)) * 100))
    salud_general = (salud_ndvi * 0.7 + salud_ndwi * 0.3)
    
    return {
        'salud_general': salud_general,
        'ndvi_stats': {
            'media': ndvi_media,
            'max': min(1.0, ndvi_media + 0.2),
            'min': max(0.0, ndvi_media - 0.2),
            'std': 0.1
        },
        'ndwi_stats': {
            'media': ndwi_media,
            'max': min(1.0, ndwi_media + 0.15),
            'min': max(-1.0, ndwi_media - 0.15),
            'std': 0.08
        },
        'ndvi_en_rango': max(0, min(100, 100 - abs(ndvi_media - np.mean(ndvi_optimo)) * 100)),
        'ndwi_en_rango': max(0, min(100, 100 - abs(ndwi_media - np.mean(ndwi_optimo)) * 100)),
        'fecha_analisis': datetime.now().isoformat(),
        'area_ha': area_ha
    }

def crear_mapa_interactivo(geojson_data, resultados, cultivo, key_suffix=""):
    """Crea un mapa interactivo con los resultados"""
    
    # Determinar centro del mapa desde el GeoJSON
    coords = geojson_data['features'][0]['geometry']['coordinates'][0]
    lats = [coord[1] for coord in coords]
    lons = [coord[0] for coord in coords]
    centro = [np.mean(lats), np.mean(lons)]
    
    # Crear mapa
    m = folium.Map(
        location=centro,
        zoom_start=12,
        tiles='OpenStreetMap'
    )
    
    # Agregar capas base ESRI
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Esri',
        name='Esri Satélite',
        overlay=False
    ).add_to(m)
    
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}',
        attr='Esri',
        name='Esri Calles',
        overlay=False
    ).add_to(m)
    
    # Estilo según salud del cultivo
    if resultados:
        salud = resultados.get('salud_general', 50)
        if salud >= 80:
            color = 'green'
            fill_color = 'green'
        elif salud >= 60:
            color = 'yellow'
            fill_color = 'yellow'
        elif salud >= 40:
            color = 'orange'
            fill_color = 'orange'
        else:
            color = 'red'
            fill_color = 'red'
    else:
        color = 'blue'
        fill_color = 'blue'
    
    # Agregar polígono
    folium.GeoJson(
        geojson_data,
        name='Área de Cultivo',
        style_function=lambda x: {
            'fillColor': fill_color,
            'color': color,
            'weight': 3,
            'fillOpacity': 0.6,
            'dashArray': '5, 5'
        },
        tooltip=folium.GeoJsonTooltip(
            fields=['name', 'area_ha', 'cultivo'],
            aliases=['Nombre:', 'Área (ha):', 'Cultivo:'],
            style=("background-color: white; color: #333333; font-family: arial; font-size: 12px; padding: 10px;")
        )
    ).add_to(m)
    
    # Agregar plugins
    plugins.Fullscreen().add_to(m)
    plugins.MeasureControl().add_to(m)
    
    # Control de capas
    folium.LayerControl().add_to(m)
    
    return m

def main():
    # Header principal
    st.title("🌱 Analizador Multi-Cultivo con Sentinel-2")
    st.markdown("---")
    
    # Inicializar estado de sesión
    if 'geojson_data' not in st.session_state:
        st.session_state.geojson_data = crear_ejemplo_geojson()
    if 'resultados' not in st.session_state:
        st.session_state.resultados = None
    if 'map_key' not in st.session_state:
        st.session_state.map_key = 0
    
    # Sidebar para configuración
    with st.sidebar:
        st.header("⚙️ Configuración")
        
        # Selección de cultivo
        cultivo = st.selectbox(
            "Selecciona el cultivo:",
            options=list(CULTIVOS.keys()),
            format_func=lambda x: CULTIVOS[x]['nombre'],
            key="cultivo_select"
        )
        
        # Información del cultivo seleccionado
        cultivo_info = CULTIVOS[cultivo]
        st.info(f"""
        **Cultivo:** {cultivo_info['nombre']}
        **NDVI Óptimo:** {cultivo_info['ndvi_optimo'][0]} - {cultivo_info['ndvi_optimo'][1]}
        **NDWI Óptimo:** {cultivo_info['ndwi_optimo'][0]} - {cultivo_info['ndwi_optimo'][1]}
        """)
        
        # Opciones de análisis
        st.subheader("📁 Datos de Entrada")
        usar_ejemplo = st.checkbox("Usar polígono de ejemplo", value=True, key="usar_ejemplo")
        
        if not usar_ejemplo:
            archivo_subido = st.file_uploader(
                "Subir archivo GeoJSON o ZIP",
                type=['geojson', 'json', 'zip'],
                help="Sube un archivo GeoJSON o ZIP que contenga polígonos de tu campo",
                key="file_uploader"
            )
            
            if archivo_subido is not None:
                with st.spinner("Procesando archivo..."):
                    nuevo_geojson = procesar_archivo_subido(archivo_subido)
                    if nuevo_geojson is not None:
                        st.session_state.geojson_data = nuevo_geojson
                        st.session_state.map_key += 1  # Forzar actualización del mapa
                        st.success(f"✅ Archivo procesado: {archivo_subido.name}")
        
        # Configuración Sentinel Hub (para futura integración)
        st.subheader("🛰️ Configuración Sentinel Hub")
        st.warning("""
        ⚠️ **Modo Demo Activado**
        
        Esta versión usa datos simulados. Para análisis con imágenes reales de Sentinel-2, configura tus credenciales:
        """)
        
        client_id = st.text_input("Client ID", type="password", placeholder="Tu Client ID de Sentinel Hub", key="b296cf70-c9d2-4e69-91f4-f7be80b99ed1")
        client_secret = st.text_input("Client Secret", type="password", placeholder="Tu Client Secret de Sentinel Hub", key="358474d6-2326-4637-bf8e-30a709b2d6a6")
        
        # Botón de análisis
        analizar = st.button("🚀 Ejecutar Análisis", type="primary", use_container_width=True, key="analizar_btn")
        
        if analizar:
            with st.spinner("🔍 Analizando con Sentinel-2..."):
                # Simular análisis (en producción esto se conectaría con Sentinel Hub)
                st.session_state.resultados = simular_analisis_sentinel(cultivo)
                st.session_state.map_key += 1  # Forzar actualización del mapa
    
    # Contenido principal
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("🗺️ Mapa del Área")
        
        # Mostrar información del área
        if 'name' in st.session_state.geojson_data['features'][0]['properties']:
            nombre_campo = st.session_state.geojson_data['features'][0]['properties']['name']
            st.info(f"📍 **Área:** {nombre_campo}")
        else:
            st.info("📍 **Área:** Polígono cargado")
        
        # Crear y mostrar mapa con clave única
        mapa = crear_mapa_interactivo(
            st.session_state.geojson_data, 
            st.session_state.resultados, 
            cultivo,
            key_suffix=str(st.session_state.map_key)
        )
        
        # Usar st_folium con una clave única
        map_data = st_folium(
            mapa, 
            width=400, 
            height=500,
            key=f"map_{st.session_state.map_key}"
        )
    
    with col2:
        st.subheader("📊 Panel de Análisis")
        
        if st.session_state.resultados:
            resultados = st.session_state.resultados
            
            # Mostrar resultados
            st.success("✅ Análisis completado")
            
            # Métricas principales
            col_met1, col_met2, col_met3 = st.columns(3)
            
            with col_met1:
                st.metric(
                    label="🌱 Salud General",
                    value=f"{resultados['salud_general']:.1f}%",
                    delta=None
                )
            
            with col_met2:
                st.metric(
                    label="📈 NDVI Medio",
                    value=f"{resultados['ndvi_stats']['media']:.3f}",
                    delta=None
                )
            
            with col_met3:
                st.metric(
                    label="💧 NDWI Medio", 
                    value=f"{resultados['ndwi_stats']['media']:.3f}",
                    delta=None
                )
            
            # Gráficos de indicadores
            st.subheader("📈 Índices de Vegetación")
            
            col_idx1, col_idx2 = st.columns(2)
            
            with col_idx1:
                # Simular gráfico NDVI
                import plotly.graph_objects as go
                
                fig_ndvi = go.Figure()
                fig_ndvi.add_trace(go.Indicator(
                    mode = "gauge+number",
                    value = resultados['ndvi_stats']['media'],
                    title = {'text': "NDVI"},
                    domain = {'x': [0, 1], 'y': [0, 1]},
                    gauge = {
                        'axis': {'range': [0, 1]},
                        'bar': {'color': "darkgreen"},
                        'steps': [
                            {'range': [0, 0.3], 'color': "lightgray"},
                            {'range': [0.3, 0.6], 'color': "yellow"},
                            {'range': [0.6, 1], 'color': "green"}
                        ],
                        'threshold': {
                            'line': {'color': "red", 'width': 4},
                            'thickness': 0.75,
                            'value': resultados['ndvi_stats']['media']
                        }
                    }
                ))
                fig_ndvi.update_layout(height=300)
                st.plotly_chart(fig_ndvi, use_container_width=True)
            
            with col_idx2:
                # Simular gráfico NDWI
                fig_ndwi = go.Figure()
                fig_ndwi.add_trace(go.Indicator(
                    mode = "gauge+number",
                    value = resultados['ndwi_stats']['media'],
                    title = {'text': "NDWI"},
                    domain = {'x': [0, 1], 'y': [0, 1]},
                    gauge = {
                        'axis': {'range': [-1, 1]},
                        'bar': {'color': "darkblue"},
                        'steps': [
                            {'range': [-1, 0], 'color': "lightgray"},
                            {'range': [0, 0.5], 'color': "lightblue"},
                            {'range': [0.5, 1], 'color': "blue"}
                        ]
                    }
                ))
                fig_ndwi.update_layout(height=300)
                st.plotly_chart(fig_ndwi, use_container_width=True)
            
            # Estadísticas detalladas
            st.subheader("📋 Estadísticas Detalladas")
            
            col_stat1, col_stat2 = st.columns(2)
            
            with col_stat1:
                st.write("**NDVI**")
                st.write(f"• Máximo: {resultados['ndvi_stats']['max']:.3f}")
                st.write(f"• Mínimo: {resultados['ndvi_stats']['min']:.3f}")
                st.write(f"• Desviación: {resultados['ndvi_stats']['std']:.3f}")
                st.write(f"• En rango óptimo: {resultados['ndvi_en_rango']:.1f}%")
            
            with col_stat2:
                st.write("**NDWI**")
                st.write(f"• Máximo: {resultados['ndwi_stats']['max']:.3f}")
                st.write(f"• Mínimo: {resultados['ndwi_stats']['min']:.3f}")
                st.write(f"• Desviación: {resultados['ndwi_stats']['std']:.3f}")
                st.write(f"• En rango óptimo: {resultados['ndwi_en_rango']:.1f}%")
            
            # Recomendaciones
            st.subheader("💡 Recomendaciones")
            salud = resultados['salud_general']
            
            if salud >= 80:
                st.success("""
                **✅ Excelente Estado**
                - El cultivo está en condiciones óptimas
                - Continuar con el manejo actual
                - Monitoreo rutinario
                """)
            elif salud >= 60:
                st.warning("""
                **⚠️ Buen Estado**
                - El cultivo se desarrolla adecuadamente
                - Mantener riego y fertilización
                - Monitorear posibles plagas
                """)
            elif salud >= 40:
                st.warning("""
                **🔶 Estado Regular**
                - Considerar ajustes en fertilización
                - Revisar sistema de riego
                - Evaluar presencia de plagas
                """)
            else:
                st.error("""
                **🔴 Estado Crítico**
                - Revisión urgente del manejo
                - Consultar con técnico agrícola
                - Evaluar resiembra
                """)
        
        else:
            # Estado inicial
            st.info("""
            ## 🚀 Bienvenido al Analizador Multi-Cultivo
            
            **Para comenzar:**
            1. Selecciona un cultivo en el panel izquierdo
            2. Configura las opciones de análisis
            3. Haz clic en **"Ejecutar Análisis"**
            
            **Características:**
            - 🌱 Análisis de 5 cultivos diferentes
            - 🛰️ Integración con Sentinel-2 (modo demo)
            - 📊 Métricas de salud vegetal
            - 💡 Recomendaciones automáticas
            - 🗺️ Mapas interactivos con ESRI
            - 📁 Soporte para GeoJSON y ZIP
            """)
            
            # Instrucciones para cargar archivos
            if not st.session_state.get('usar_ejemplo', True):
                st.subheader("📁 Formatos Soportados")
                st.write("""
                **GeoJSON:** Archivo .geojson o .json con polígonos
                **ZIP:** Archivo comprimido que contenga GeoJSON
                
                **Estructura esperada:**
                ```json
                {
                  "type": "FeatureCollection",
                  "features": [
                    {
                      "type": "Feature",
                      "properties": {
                        "name": "Nombre del Campo",
                        "area_ha": 100
                      },
                      "geometry": {
                        "type": "Polygon",
                        "coordinates": [...]
                      }
                    }
                  ]
                }
                ```
                """)
    
    # Footer
    st.markdown("---")
    st.markdown(
        """
        <div style='text-align: center; color: gray;'>
        🌱 Analizador Multi-Cultivo | 🛰️ Sentinel-2 | 📍 Streamlit Cloud
        </div>
        """,
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()
