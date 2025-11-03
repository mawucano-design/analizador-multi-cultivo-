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
import fiona
from sentinelhub import (
    SHConfig,
    BBox,
    CRS,
    DataCollection,
    MimeType,
    MosaickingOrder,
    SentinelHubRequest,
    bbox_to_dimensions,
)

# Configuración de la página
st.set_page_config(
    page_title="Analizador Multi-Cultivo con Sentinel-2",
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

class SentinelAnalizador:
    def __init__(self, client_id, client_secret):
        """Inicializa el cliente de Sentinel Hub"""
        self.config = SHConfig()
        self.config.sh_client_id = client_id
        self.config.sh_client_secret = client_secret
        self.config.save()
    
    def obtener_imagen_sentinel2(self, bbox, fecha_inicio, fecha_fin, tamaño=(512, 512)):
        """Obtiene imagen Sentinel-2 L2A (harmonizada) para el área y fecha especificadas"""
        
        # Evalscript para NDVI, NDWI y bandas naturales
        evalscript = """
        //VERSION=3
        function setup() {
            return {
                input: [{
                    bands: ["B02", "B03", "B04", "B08", "B11"],
                    units: "REFLECTANCE"
                }],
                output: {
                    bands: 6,
                    sampleType: "FLOAT32"
                }
            };
        }

        function evaluatePixel(sample) {
            // Calcular NDVI
            let ndvi = (sample.B08 - sample.B04) / (sample.B08 + sample.B04);
            
            // Calcular NDWI
            let ndwi = (sample.B03 - sample.B08) / (sample.B03 + sample.B08);
            
            // Calcular NDBI (Índice de Área Construida)
            let ndbi = (sample.B11 - sample.B08) / (sample.B11 + sample.B08);
            
            // Retornar RGB + índices
            return [sample.B04, sample.B03, sample.B02, ndvi, ndwi, ndbi];
        }
        """
        
        try:
            # Usar Sentinel-2 L2A (nivel 2A - corrección atmosférica aplicada)
            request = SentinelHubRequest(
                evalscript=evalscript,
                input_data=[
                    SentinelHubRequest.input_data(
                        data_collection=DataCollection.SENTINEL2_L2A,
                        time_interval=(fecha_inicio, fecha_fin),
                        mosaicking_order=MosaickingOrder.LEAST_CC,  # Menor cobertura de nubes
                    )
                ],
                responses=[SentinelHubRequest.output_response("default", MimeType.TIFF)],
                bbox=bbox,
                size=tamaño,
                config=self.config,
            )
            
            # Ejecutar request
            datos = request.get_data()
            return datos[0] if datos else None
            
        except Exception as e:
            st.error(f"❌ Error obteniendo imagen Sentinel-2 L2A: {str(e)}")
            return None
    
    def calcular_indices(self, imagen):
        """Calcula índices de vegetación a partir de la imagen Sentinel-2"""
        if imagen is None:
            return None
            
        try:
            # La imagen tiene [R, G, B, NDVI, NDWI, NDBI]
            ndvi = imagen[:, :, 3]
            ndwi = imagen[:, :, 4]
            ndbi = imagen[:, :, 5]
            
            # Limpiar valores inválidos
            ndvi = np.nan_to_num(ndvi, nan=0.0, posinf=1.0, neginf=-1.0)
            ndwi = np.nan_to_num(ndwi, nan=0.0, posinf=1.0, neginf=-1.0)
            ndbi = np.nan_to_num(ndbi, nan=0.0, posinf=1.0, neginf=-1.0)
            
            return {
                'ndvi': ndvi,
                'ndwi': ndwi,
                'ndbi': ndbi,
                'rgb': imagen[:, :, :3]  # Bandas RGB naturales
            }
        except Exception as e:
            st.error(f"❌ Error calculando índices: {str(e)}")
            return None
    
    def analizar_salud_cultivo(self, indices, cultivo):
        """Analiza la salud del cultivo basado en los índices Sentinel-2"""
        if indices is None:
            return None
            
        try:
            ndvi = indices['ndvi']
            ndwi = indices['ndwi']
            ndbi = indices['ndbi']
            
            # Filtrar píxeles válidos (excluir nubes, agua, etc.)
            mascara_valida = (ndvi > -1) & (ndvi < 1) & (ndwi > -1) & (ndwi < 1)
            ndvi_filtrado = ndvi[mascara_valida]
            ndwi_filtrado = ndwi[mascara_valida]
            
            if len(ndvi_filtrado) == 0:
                st.warning("⚠️ No se encontraron píxeles válidos para análisis")
                return None
            
            # Estadísticas básicas
            stats_ndvi = {
                'media': float(np.nanmean(ndvi_filtrado)),
                'max': float(np.nanmax(ndvi_filtrado)),
                'min': float(np.nanmin(ndvi_filtrado)),
                'std': float(np.nanstd(ndvi_filtrado)),
                'percentil_25': float(np.nanpercentile(ndvi_filtrado, 25)),
                'percentil_75': float(np.nanpercentile(ndvi_filtrado, 75))
            }
            
            stats_ndwi = {
                'media': float(np.nanmean(ndwi_filtrado)),
                'max': float(np.nanmax(ndwi_filtrado)),
                'min': float(np.nanmin(ndwi_filtrado)),
                'std': float(np.nanstd(ndwi_filtrado))
            }
            
            # Evaluar salud según rangos óptimos del cultivo
            cultivo_info = CULTIVOS[cultivo]
            ndvi_optimo = cultivo_info['ndvi_optimo']
            ndwi_optimo = cultivo_info['ndwi_optimo']
            
            # Calcular porcentaje de píxeles en rango óptimo
            ndvi_en_rango = np.sum((ndvi_filtrado >= ndvi_optimo[0]) & (ndvi_filtrado <= ndvi_optimo[1])) / len(ndvi_filtrado)
            ndwi_en_rango = np.sum((ndwi_filtrado >= ndwi_optimo[0]) & (ndwi_filtrado <= ndwi_optimo[1])) / len(ndwi_filtrado)
            
            # Salud general (promedio ponderado)
            salud_general = (ndvi_en_rango * 0.7 + ndwi_en_rango * 0.3) * 100
            
            # Detección de posibles problemas
            problemas = []
            if stats_ndvi['media'] < ndvi_optimo[0]:
                problemas.append("NDVI bajo - posible estrés hídrico o nutricional")
            if stats_ndwi['media'] < ndwi_optimo[0]:
                problemas.append("NDWI bajo - posible falta de humedad")
            if np.mean(ndbi) > 0.1:  # Umbral para áreas construidas
                problemas.append("Presencia de áreas no agrícolas detectada")
            
            return {
                'salud_general': salud_general,
                'ndvi_stats': stats_ndvi,
                'ndwi_stats': stats_ndwi,
                'ndvi_en_rango': ndvi_en_rango * 100,
                'ndwi_en_rango': ndwi_en_rango * 100,
                'problemas': problemas,
                'pixeles_analizados': len(ndvi_filtrado),
                'fecha_analisis': datetime.now().isoformat()
            }
            
        except Exception as e:
            st.error(f"❌ Error analizando salud del cultivo: {str(e)}")
            return None

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
    """Procesa archivos GeoJSON, Shapefile (ZIP) u otros formatos geoespaciales"""
    try:
        # Leer el contenido del archivo en memoria
        contenido = archivo.read()
        
        # Intentar como GeoJSON primero
        if archivo.name.lower().endswith(('.geojson', '.json')):
            try:
                archivo.seek(0)  # Volver al inicio del archivo
                geojson_data = json.load(archivo)
                st.success("✅ Archivo GeoJSON procesado correctamente")
                return geojson_data
            except json.JSONDecodeError:
                st.error("❌ El archivo no es un GeoJSON válido")
                return None
        
        # Procesar archivo ZIP (posible Shapefile u otros)
        elif archivo.name.lower().endswith('.zip'):
            return procesar_archivo_zip(contenido, archivo.name)
        
        else:
            st.error("❌ Formato de archivo no soportado")
            return None
            
    except Exception as e:
        st.error(f"❌ Error procesando archivo: {str(e)}")
        return None

def procesar_archivo_zip(contenido_zip, nombre_archivo):
    """Procesa archivos ZIP que pueden contener Shapefiles, GeoJSON, etc."""
    try:
        with zipfile.ZipFile(io.BytesIO(contenido_zip), 'r') as zip_ref:
            # Listar todos los archivos en el ZIP
            archivos = zip_ref.namelist()
            st.info(f"📁 Archivos en el ZIP: {', '.join(archivos)}")
            
            # Buscar Shapefiles (.shp, .dbf, .shx, .prj)
            shp_files = [f for f in archivos if f.lower().endswith('.shp')]
            if shp_files:
                return procesar_shapefile_desde_zip(zip_ref, shp_files[0])
            
            # Buscar GeoJSON
            geojson_files = [f for f in archivos if f.lower().endswith(('.geojson', '.json'))]
            if geojson_files:
                return procesar_geojson_desde_zip(zip_ref, geojson_files[0])
            
            # Buscar KML
            kml_files = [f for f in archivos if f.lower().endswith('.kml')]
            if kml_files:
                return procesar_kml_desde_zip(zip_ref, kml_files[0])
            
            st.error("❌ No se encontraron archivos geoespaciales en el ZIP")
            return None
            
    except Exception as e:
        st.error(f"❌ Error procesando ZIP: {str(e)}")
        return None

def procesar_shapefile_desde_zip(zip_ref, shp_file):
    """Procesa Shapefile desde archivo ZIP"""
    try:
        # Crear directorio temporal
        with tempfile.TemporaryDirectory() as temp_dir:
            # Extraer todos los archivos del shapefile
            for file in zip_ref.namelist():
                if file.startswith(os.path.splitext(shp_file)[0]):
                    zip_ref.extract(file, temp_dir)
            
            # Leer el shapefile con geopandas
            shp_path = os.path.join(temp_dir, shp_file)
            gdf = gpd.read_file(shp_path)
            
            # Convertir a GeoJSON
            geojson_data = json.loads(gdf.to_json())
            
            st.success(f"✅ Shapefile procesado: {len(gdf)} features encontrados")
            return geojson_data
            
    except Exception as e:
        st.error(f"❌ Error procesando Shapefile: {str(e)}")
        return None

def procesar_geojson_desde_zip(zip_ref, geojson_file):
    """Procesa GeoJSON desde archivo ZIP"""
    try:
        with zip_ref.open(geojson_file) as f:
            geojson_data = json.load(f)
            st.success(f"✅ GeoJSON procesado: {geojson_file}")
            return geojson_data
    except Exception as e:
        st.error(f"❌ Error procesando GeoJSON {geojson_file}: {str(e)}")
        return None

def procesar_kml_desde_zip(zip_ref, kml_file):
    """Procesa KML desde archivo ZIP"""
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            # Extraer KML
            kml_path = os.path.join(temp_dir, kml_file)
            zip_ref.extract(kml_file, temp_dir)
            
            # Leer KML con geopandas
            gdf = gpd.read_file(kml_path, driver='KML')
            
            # Convertir a GeoJSON
            geojson_data = json.loads(gdf.to_json())
            
            st.success(f"✅ KML procesado: {len(gdf)} features encontrados")
            return geojson_data
            
    except Exception as e:
        st.error(f"❌ Error procesando KML: {str(e)}")
        return None

def obtener_bbox_desde_geojson(geojson_data):
    """Obtiene el BBox desde datos GeoJSON"""
    try:
        gdf = gpd.GeoDataFrame.from_features(geojson_data["features"])
        bounds = gdf.total_bounds
        bbox = BBox(bbox=[bounds[0], bounds[1], bounds[2], bounds[3]], crs=CRS.WGS84)
        return bbox
    except Exception as e:
        st.error(f"❌ Error obteniendo BBox: {str(e)}")
        return None

def obtener_fechas_analisis():
    """Obtiene fechas para análisis (últimos 30 días)"""
    fecha_fin = datetime.now()
    fecha_inicio = fecha_fin - timedelta(days=30)
    return fecha_inicio.strftime("%Y-%m-%d"), fecha_fin.strftime("%Y-%m-%d")

def crear_mapa_interactivo(geojson_data, resultados, cultivo, key_suffix=""):
    """Crea un mapa interactivo con los resultados"""
    
    try:
        # Determinar centro del mapa desde el GeoJSON
        if 'features' in geojson_data and len(geojson_data['features']) > 0:
            feature = geojson_data['features'][0]
            if 'geometry' in feature and 'coordinates' in feature['geometry']:
                coords = feature['geometry']['coordinates'][0]
                lats = [coord[1] for coord in coords]
                lons = [coord[0] for coord in coords]
                centro = [np.mean(lats), np.mean(lons)]
            else:
                centro = [-34.6037, -58.3816]
        else:
            centro = [-34.6037, -58.3816]
        
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
            },
            tooltip=folium.GeoJsonTooltip(
                fields=['name', 'area_ha', 'cultivo'] if 'features' in geojson_data and geojson_data['features'] and 'properties' in geojson_data['features'][0] else [],
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
        
    except Exception as e:
        st.error(f"❌ Error creando el mapa: {str(e)}")
        return folium.Map(location=[-34.6037, -58.3816], zoom_start=4)

def main():
    # Header principal
    st.title("🌱 Analizador Multi-Cultivo con Sentinel-2 L2A")
    st.markdown("---")
    
    # Inicializar estado de sesión
    if 'geojson_data' not in st.session_state:
        st.session_state.geojson_data = crear_ejemplo_geojson()
    if 'resultados' not in st.session_state:
        st.session_state.resultados = None
    if 'map_key' not in st.session_state:
        st.session_state.map_key = 0
    if 'archivo_procesado' not in st.session_state:
        st.session_state.archivo_procesado = False
    
    # Sidebar para configuración
    with st.sidebar:
        st.header("⚙️ Configuración Sentinel Hub")
        
        # Credenciales de Sentinel Hub
        st.info("""
        **Credenciales Requeridas**
        Para usar imágenes reales de Sentinel-2 L2A
        """)
        
        client_id = st.text_input(
            "Client ID", 
            value="b296cf70-c9d2-4e69-91f4-f7be80b99ed1",
            type="password",
            help="Tu Client ID de Sentinel Hub"
        )
        
        client_secret = st.text_input(
            "Client Secret", 
            type="password",
            placeholder="Ingresa tu Client Secret",
            help="Tu Client Secret de Sentinel Hub"
        )
        
        # Selección de cultivo
        st.subheader("🌱 Cultivo")
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
            st.info("""
            **Formatos soportados:**
            - 🔹 GeoJSON (.geojson, .json)
            - 🔹 Shapefile (.zip con .shp, .dbf, .shx)
            - 🔹 KML (.kml, .zip con .kml)
            """)
            
            archivo_subido = st.file_uploader(
                "Subir archivo geoespacial",
                type=['geojson', 'json', 'zip', 'kml'],
                help="Sube Shapefile (ZIP), GeoJSON o KML con polígonos de tu campo",
                key="file_uploader"
            )
            
            if archivo_subido is not None:
                if not st.session_state.archivo_procesado or st.button("Reprocesar archivo"):
                    with st.spinner("🔍 Analizando archivo..."):
                        nuevo_geojson = procesar_archivo_subido(archivo_subido)
                        if nuevo_geojson is not None:
                            st.session_state.geojson_data = nuevo_geojson
                            st.session_state.map_key += 1
                            st.session_state.archivo_procesado = True
                            st.session_state.resultados = None
                            st.rerun()
        
        # Configuración de fechas
        st.subheader("📅 Período de Análisis")
        col_fecha1, col_fecha2 = st.columns(2)
        with col_fecha1:
            fecha_inicio = st.date_input(
                "Fecha inicio",
                value=datetime.now() - timedelta(days=30),
                max_value=datetime.now()
            )
        with col_fecha2:
            fecha_fin = st.date_input(
                "Fecha fin", 
                value=datetime.now(),
                max_value=datetime.now()
            )
        
        # Botón de análisis
        analizar = st.button("🚀 Ejecutar Análisis con Sentinel-2", type="primary", use_container_width=True, key="analizar_btn")
        
        if analizar:
            if not client_id or not client_secret:
                st.error("❌ Se requieren Client ID y Client Secret de Sentinel Hub")
            else:
                with st.spinner("🛰️ Conectando con Sentinel Hub..."):
                    try:
                        # Inicializar analizador Sentinel
                        analizador = SentinelAnalizador(client_id, client_secret)
                        
                        # Obtener BBox del polígono
                        bbox = obtener_bbox_desde_geojson(st.session_state.geojson_data)
                        if bbox is None:
                            st.error("❌ No se pudo obtener el área de análisis")
                            return
                        
                        # Obtener imagen Sentinel-2 L2A
                        fecha_inicio_str = fecha_inicio.strftime("%Y-%m-%d")
                        fecha_fin_str = fecha_fin.strftime("%Y-%m-%d")
                        
                        st.info(f"📡 Solicitando imágenes del {fecha_inicio_str} al {fecha_fin_str}")
                        
                        imagen = analizador.obtener_imagen_sentinel2(bbox, fecha_inicio_str, fecha_fin_str)
                        
                        if imagen is None:
                            st.error("❌ No se pudo obtener imagen Sentinel-2")
                            return
                        
                        st.success("✅ Imagen Sentinel-2 L2A obtenida")
                        
                        # Calcular índices
                        indices = analizador.calcular_indices(imagen)
                        if indices is None:
                            st.error("❌ Error calculando índices de vegetación")
                            return
                        
                        # Analizar salud del cultivo
                        st.session_state.resultados = analizador.analizar_salud_cultivo(indices, cultivo)
                        st.session_state.map_key += 1
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"❌ Error en el análisis: {str(e)}")
    
    # Contenido principal
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("🗺️ Mapa del Área")
        
        # Mostrar información del área
        if (st.session_state.geojson_data and 
            'features' in st.session_state.geojson_data and 
            len(st.session_state.geojson_data['features']) > 0 and
            'properties' in st.session_state.geojson_data['features'][0]):
            
            propiedades = st.session_state.geojson_data['features'][0]['properties']
            nombre_campo = propiedades.get('name', 'Polígono sin nombre')
            area_ha = propiedades.get('area_ha', 'N/A')
            st.info(f"📍 **Área:** {nombre_campo} | **Superficie:** {area_ha} ha")
        else:
            st.info("📍 **Área:** Polígono cargado")
        
        # Crear y mostrar mapa
        mapa = crear_mapa_interactivo(
            st.session_state.geojson_data, 
            st.session_state.resultados, 
            cultivo,
            key_suffix=str(st.session_state.map_key)
        )
        
        map_data = st_folium(
            mapa, 
            width=400, 
            height=500,
            key=f"map_{st.session_state.map_key}"
        )
    
    with col2:
        st.subheader("📊 Panel de Análisis Sentinel-2")
        
        if st.session_state.resultados:
            resultados = st.session_state.resultados
            
            st.success("✅ Análisis con Sentinel-2 L2A completado")
            
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
                    delta=f"±{resultados['ndvi_stats']['std']:.3f}"
                )
            
            with col_met3:
                st.metric(
                    label="💧 NDWI Medio", 
                    value=f"{resultados['ndwi_stats']['media']:.3f}",
                    delta=f"±{resultados['ndwi_stats']['std']:.3f}"
                )
            
            # Información técnica
            st.subheader("🔬 Información Técnica")
            col_tech1, col_tech2 = st.columns(2)
            
            with col_tech1:
                st.write("**NDVI Detallado**")
                st.write(f"• Rango: {resultados['ndvi_stats']['min']:.3f} - {resultados['ndvi_stats']['max']:.3f}")
                st.write(f"• Percentil 25: {resultados['ndvi_stats']['percentil_25']:.3f}")
                st.write(f"• Percentil 75: {resultados['ndvi_stats']['percentil_75']:.3f}")
                st.write(f"• En rango óptimo: {resultados['ndvi_en_rango']:.1f}%")
            
            with col_tech2:
                st.write("**Estadísticas**")
                st.write(f"• Píxeles analizados: {resultados['pixeles_analizados']:,}")
                st.write(f"• NDWI en rango: {resultados['ndwi_en_rango']:.1f}%")
                st.write(f"• Fecha análisis: {resultados['fecha_analisis'][:19]}")
            
            # Problemas detectados
            if resultados.get('problemas'):
                st.subheader("⚠️ Alertas Detectadas")
                for problema in resultados['problemas']:
                    st.warning(problema)
            
            # Recomendaciones
            st.subheader("💡 Recomendaciones")
            salud = resultados['salud_general']
            
            if salud >= 80:
                st.success("""
                **✅ Excelente Estado**
                - El cultivo muestra vigor vegetativo óptimo
                - Continuar con prácticas actuales de manejo
                - Monitoreo satelital rutinario recomendado
                """)
            elif salud >= 60:
                st.warning("""
                **🟡 Buen Estado**
                - Desarrollo vegetativo adecuado
                - Mantener programa de fertilización
                - Verificar humedad del suelo
                """)
            elif salud >= 40:
                st.warning("""
                **🟠 Estado Regular**
                - Posible estrés hídrico o nutricional
                - Evaluar programa de riego
                - Considerar análisis de suelo
                """)
            else:
                st.error("""
                **🔴 Estado Crítico**
                - Revisión urgente de manejo agronómico
                - Consulta técnica recomendada
                - Evaluar resiembra o cambio de estrategia
                """)
        
        else:
            st.info("""
            ## 🛰️ Analizador con Sentinel-2 L2A
            
            **Características:**
            - 🌱 Análisis multi-cultivo con imágenes reales
            - 🛰️ **Sentinel-2 L2A** (10m, corrección atmosférica)
            - 📊 Índices NDVI y NDWI en tiempo real
            - 🔬 Detección de problemas automática
            - 💡 Recomendaciones basadas en datos satelitales
            
            **Para comenzar:**
            1. Configura tus credenciales de Sentinel Hub
            2. Selecciona el cultivo a analizar
            3. Carga tu polígono o usa el ejemplo
            4. Define el período de análisis
            5. Haz clic en **"Ejecutar Análisis con Sentinel-2"**
            """)
    
    # Footer
    st.markdown("---")
    st.markdown(
        """
        <div style='text-align: center; color: gray;'>
        🌱 Analizador Multi-Cultivo | 🛰️ Sentinel-2 L2A | 📍 Streamlit Cloud
        </div>
        """,
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()
