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

# Credenciales automáticas de Sentinel Hub
SENTINEL_CLIENT_ID = "b296cf70-c9d2-4e69-91f4-f7be80b99ed1"
SENTINEL_CLIENT_SECRET = "358474d6-2326-4637-bf8e-30a709b2d6a6"

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
        try:
            self.config = SHConfig()
            self.config.sh_client_id = client_id
            self.config.sh_client_secret = client_secret
            self.config.save()
            st.success("✅ Credenciales de Sentinel Hub configuradas")
        except Exception as e:
            st.error(f"❌ Error configurando Sentinel Hub: {str(e)}")
    
    def obtener_imagen_sentinel2(self, bbox, fecha_inicio, fecha_fin, tamaño=(512, 512)):
        """Obtiene imagen Sentinel-2 L2A para el área y fecha especificadas"""
        
        evalscript = """
        //VERSION=3
        function setup() {
            return {
                input: [{
                    bands: ["B02", "B03", "B04", "B08"],
                    units: "REFLECTANCE"
                }],
                output: {
                    bands: 4,
                    sampleType: "FLOAT32"
                }
            };
        }

        function evaluatePixel(sample) {
            // Calcular NDVI
            let ndvi = (sample.B08 - sample.B04) / (sample.B08 + sample.B04);
            
            // Calcular NDWI
            let ndwi = (sample.B03 - sample.B08) / (sample.B03 + sample.B08);
            
            // Retornar RGB + índices
            return [sample.B04, sample.B03, sample.B02, ndvi];
        }
        """
        
        try:
            st.info("🛰️ Conectando con Sentinel Hub...")
            
            # Verificar que el bbox sea válido
            if not bbox:
                st.error("❌ BBox inválido")
                return None
            
            st.info(f"📍 Área: {bbox}")
            st.info(f"📅 Período: {fecha_inicio} a {fecha_fin}")
            
            request = SentinelHubRequest(
                evalscript=evalscript,
                input_data=[
                    SentinelHubRequest.input_data(
                        data_collection=DataCollection.SENTINEL2_L2A,
                        time_interval=(fecha_inicio, fecha_fin),
                        mosaicking_order=MosaickingOrder.LEAST_CC,
                    )
                ],
                responses=[SentinelHubRequest.output_response("default", MimeType.TIFF)],
                bbox=bbox,
                size=tamaño,
                config=self.config,
            )
            
            st.info("📡 Descargando imagen Sentinel-2...")
            datos = request.get_data()
            
            if datos and len(datos) > 0:
                st.success("✅ Imagen Sentinel-2 obtenida correctamente")
                return datos[0]
            else:
                st.error("❌ No se recibieron datos de Sentinel Hub")
                return None
                
        except Exception as e:
            st.error(f"❌ Error obteniendo imagen Sentinel-2: {str(e)}")
            return None
    
    def calcular_indices(self, imagen):
        """Calcula índices de vegetación"""
        if imagen is None:
            st.error("❌ No hay imagen para calcular índices")
            return None
            
        try:
            st.info("📊 Procesando índices de vegetación...")
            
            # Verificar dimensiones de la imagen
            st.info(f"📏 Dimensiones de imagen: {imagen.shape}")
            
            # La imagen tiene [R, G, B, NDVI]
            ndvi = imagen[:, :, 3]
            
            # Calcular NDWI
            verde = imagen[:, :, 1]
            nir = imagen[:, :, 3]
            
            with np.errstate(divide='ignore', invalid='ignore'):
                ndwi = (verde - nir) / (verde + nir)
                ndwi = np.nan_to_num(ndwi, nan=0.0, posinf=1.0, neginf=-1.0)
            
            # Estadísticas básicas para debug
            st.info(f"📈 NDVI - Media: {np.nanmean(ndvi):.3f}, Min: {np.nanmin(ndvi):.3f}, Max: {np.nanmax(ndvi):.3f}")
            st.info(f"💧 NDWI - Media: {np.nanmean(ndwi):.3f}, Min: {np.nanmin(ndwi):.3f}, Max: {np.nanmax(ndwi):.3f}")
            
            st.success("✅ Índices calculados correctamente")
            return {
                'ndvi': ndvi,
                'ndwi': ndwi,
                'rgb': imagen[:, :, :3]
            }
            
        except Exception as e:
            st.error(f"❌ Error calculando índices: {str(e)}")
            return None
    
    def analizar_salud_cultivo(self, indices, cultivo):
        """Analiza la salud del cultivo"""
        if indices is None:
            return None
            
        try:
            st.info("🔍 Analizando salud del cultivo...")
            
            ndvi = indices['ndvi']
            ndwi = indices['ndwi']
            
            # Filtrar píxeles válidos
            mascara_valida = (ndvi > -1) & (ndvi < 1) & (ndwi > -1) & (ndwi < 1)
            ndvi_filtrado = ndvi[mascara_valida]
            ndwi_filtrado = ndwi[mascara_valida]
            
            st.info(f"🔢 Píxeles válidos encontrados: {len(ndvi_filtrado)}")
            
            if len(ndvi_filtrado) == 0:
                st.warning("⚠️ No se encontraron píxeles válidos para análisis")
                return None
            
            # Estadísticas
            stats_ndvi = {
                'media': float(np.nanmean(ndvi_filtrado)),
                'max': float(np.nanmax(ndvi_filtrado)),
                'min': float(np.nanmin(ndvi_filtrado)),
                'std': float(np.nanstd(ndvi_filtrado))
            }
            
            stats_ndwi = {
                'media': float(np.nanmean(ndwi_filtrado)),
                'max': float(np.nanmax(ndwi_filtrado)),
                'min': float(np.nanmin(ndwi_filtrado)),
                'std': float(np.nanstd(ndwi_filtrado))
            }
            
            # Evaluar salud
            cultivo_info = CULTIVOS[cultivo]
            ndvi_optimo = cultivo_info['ndvi_optimo']
            ndwi_optimo = cultivo_info['ndwi_optimo']
            
            ndvi_en_rango = np.sum((ndvi_filtrado >= ndvi_optimo[0]) & (ndvi_filtrado <= ndvi_optimo[1])) / len(ndvi_filtrado)
            ndwi_en_rango = np.sum((ndwi_filtrado >= ndwi_optimo[0]) & (ndwi_filtrado <= ndwi_optimo[1])) / len(ndwi_filtrado)
            
            salud_general = (ndvi_en_rango * 0.7 + ndwi_en_rango * 0.3) * 100
            
            st.success("✅ Análisis de salud completado")
            return {
                'salud_general': salud_general,
                'ndvi_stats': stats_ndvi,
                'ndwi_stats': stats_ndwi,
                'ndvi_en_rango': ndvi_en_rango * 100,
                'ndwi_en_rango': ndwi_en_rango * 100,
                'pixeles_analizados': len(ndvi_filtrado),
                'fecha_analisis': datetime.now().isoformat()
            }
            
        except Exception as e:
            st.error(f"❌ Error analizando salud: {str(e)}")
            return None

def procesar_archivo_subido(archivo):
    """Procesa archivos geoespaciales"""
    try:
        st.info(f"📂 Procesando archivo: {archivo.name}")
        
        if archivo.name.lower().endswith(('.geojson', '.json')):
            archivo.seek(0)
            geojson_data = json.load(archivo)
            st.success(f"✅ GeoJSON cargado: {len(geojson_data.get('features', []))} features")
            return geojson_data
            
        elif archivo.name.lower().endswith('.zip'):
            return procesar_archivo_zip(archivo.read(), archivo.name)
        else:
            st.error("❌ Formato no soportado")
            return None
            
    except Exception as e:
        st.error(f"❌ Error procesando archivo: {str(e)}")
        return None

def procesar_archivo_zip(contenido_zip, nombre_archivo):
    """Procesa archivos ZIP"""
    try:
        with zipfile.ZipFile(io.BytesIO(contenido_zip), 'r') as zip_ref:
            archivos = zip_ref.namelist()
            st.info(f"📁 Archivos en ZIP: {', '.join(archivos)}")
            
            # Buscar Shapefile
            shp_files = [f for f in archivos if f.lower().endswith('.shp')]
            if shp_files:
                st.info("🔍 Procesando Shapefile...")
                with tempfile.TemporaryDirectory() as temp_dir:
                    # Extraer todos los archivos relacionados
                    for file in zip_ref.namelist():
                        base_name = os.path.splitext(shp_files[0])[0]
                        if file.startswith(base_name):
                            zip_ref.extract(file, temp_dir)
                    
                    shp_path = os.path.join(temp_dir, shp_files[0])
                    gdf = gpd.read_file(shp_path)
                    st.success(f"✅ Shapefile procesado: {len(gdf)} features")
                    return json.loads(gdf.to_json())
            
            # Buscar GeoJSON
            geojson_files = [f for f in archivos if f.lower().endswith(('.geojson', '.json'))]
            if geojson_files:
                st.info(f"🔍 Procesando {geojson_files[0]}...")
                with zip_ref.open(geojson_files[0]) as f:
                    geojson_data = json.load(f)
                    st.success(f"✅ GeoJSON procesado: {len(geojson_data.get('features', []))} features")
                    return geojson_data
            
            st.error("❌ No se encontraron archivos geoespaciales en el ZIP")
            return None
            
    except Exception as e:
        st.error(f"❌ Error procesando ZIP: {str(e)}")
        return None

def obtener_bbox_desde_geojson(geojson_data):
    """Obtiene el BBox desde GeoJSON"""
    try:
        if not geojson_data or 'features' not in geojson_data or not geojson_data['features']:
            st.error("❌ GeoJSON no contiene features")
            return None
            
        gdf = gpd.GeoDataFrame.from_features(geojson_data["features"])
        bounds = gdf.total_bounds
        
        # Verificar que las coordenadas sean válidas
        if (bounds[0] >= bounds[2]) or (bounds[1] >= bounds[3]):
            st.error("❌ Coordenadas del BBox inválidas")
            return None
            
        bbox = BBox(bbox=[bounds[0], bounds[1], bounds[2], bounds[3]], crs=CRS.WGS84)
        st.info(f"📍 Área de análisis: {bounds}")
        return bbox
        
    except Exception as e:
        st.error(f"❌ Error obteniendo BBox: {str(e)}")
        return None

def crear_mapa_simple(geojson_data, resultados=None):
    """Crea un mapa simple y robusto"""
    try:
        # Centro por defecto (Argentina)
        centro = [-34.6037, -58.3816]
        
        # Intentar calcular centro desde GeoJSON
        if geojson_data and 'features' in geojson_data and geojson_data['features']:
            try:
                feature = geojson_data['features'][0]
                if 'geometry' in feature and 'coordinates' in feature['geometry']:
                    coords = feature['geometry']['coordinates'][0]
                    lats = [coord[1] for coord in coords]
                    lons = [coord[0] for coord in coords]
                    centro = [np.mean(lats), np.mean(lons)]
            except Exception as e:
                st.warning(f"⚠️ Usando centro por defecto: {str(e)}")
        
        # Crear mapa base
        m = folium.Map(location=centro, zoom_start=12)
        
        # Agregar capas base
        folium.TileLayer(
            tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
            attr='Esri',
            name='Esri Satélite'
        ).add_to(m)
        
        folium.TileLayer(
            tiles='OpenStreetMap',
            name='OpenStreetMap'
        ).add_to(m)
        
        # Agregar polígono si existe
        if geojson_data and 'features' in geojson_data:
            # Determinar color según resultados
            color = 'blue'
            if resultados:
                salud = resultados.get('salud_general', 50)
                if salud >= 80: color = 'green'
                elif salud >= 60: color = 'yellow'
                elif salud >= 40: color = 'orange'
                else: color = 'red'
            
            folium.GeoJson(
                geojson_data,
                style_function=lambda x: {
                    'fillColor': color,
                    'color': color,
                    'weight': 3,
                    'fillOpacity': 0.6,
                }
            ).add_to(m)
        
        # Controles básicos
        plugins.Fullscreen().add_to(m)
        folium.LayerControl().add_to(m)
        
        return m
        
    except Exception as e:
        st.error(f"❌ Error creando mapa: {str(e)}")
        return folium.Map(location=[-34.6037, -58.3816], zoom_start=4)

def exportar_geojson(geojson_data, resultados, cultivo):
    """Exporta GeoJSON con resultados del análisis"""
    try:
        if not geojson_data or not resultados:
            return None
            
        # Crear copia del GeoJSON
        geojson_export = json.loads(json.dumps(geojson_data))
        
        # Agregar resultados a las propiedades
        for feature in geojson_export['features']:
            if 'properties' not in feature:
                feature['properties'] = {}
            
            feature['properties'].update({
                'cultivo_analizado': CULTIVOS[cultivo]['nombre'],
                'salud_general': round(resultados['salud_general'], 1),
                'ndvi_media': round(resultados['ndvi_stats']['media'], 3),
                'ndwi_media': round(resultados['ndwi_stats']['media'], 3),
                'ndvi_en_rango': round(resultados['ndvi_en_rango'], 1),
                'ndwi_en_rango': round(resultados['ndwi_en_rango'], 1),
                'pixeles_analizados': resultados['pixeles_analizados'],
                'fecha_analisis': resultados['fecha_analisis']
            })
        
        return geojson_export
        
    except Exception as e:
        st.error(f"❌ Error exportando GeoJSON: {str(e)}")
        return None

def main():
    # Header principal
    st.title("🌱 Analizador Multi-Cultivo con Sentinel-2")
    st.markdown("---")
    
    # Inicializar estado de sesión
    if 'geojson_data' not in st.session_state:
        st.session_state.geojson_data = None
    if 'resultados' not in st.session_state:
        st.session_state.resultados = None
    if 'map_key' not in st.session_state:
        st.session_state.map_key = 0
    if 'analisis_completado' not in st.session_state:
        st.session_state.analisis_completado = False

    # Sidebar
    with st.sidebar:
        st.header("⚙️ Configuración")
        
        # Credenciales automáticas
        st.success("✅ Credenciales Sentinel Hub configuradas")
        st.info(f"**Client ID:** {SENTINEL_CLIENT_ID[:8]}...")
        
        # Selección de cultivo
        cultivo = st.selectbox(
            "Selecciona el cultivo:",
            options=list(CULTIVOS.keys()),
            format_func=lambda x: CULTIVOS[x]['nombre'],
            key="cultivo_select"
        )
        
        cultivo_info = CULTIVOS[cultivo]
        st.info(f"""
        **Cultivo:** {cultivo_info['nombre']}
        **NDVI Óptimo:** {cultivo_info['ndvi_optimo'][0]} - {cultivo_info['ndvi_optimo'][1]}
        **NDWI Óptimo:** {cultivo_info['ndwi_optimo'][0]} - {cultivo_info['ndwi_optimo'][1]}
        """)
        
        # Datos de entrada
        st.subheader("📁 Cargar Polígono")
        
        archivo_subido = st.file_uploader(
            "Subir archivo geoespacial",
            type=['geojson', 'json', 'zip'],
            help="GeoJSON, JSON o ZIP con Shapefile"
        )
        
        if archivo_subido is not None:
            if st.session_state.geojson_data is None or st.button("🔄 Reprocesar archivo"):
                with st.spinner("🔍 Procesando archivo..."):
                    nuevo_geojson = procesar_archivo_subido(archivo_subido)
                    if nuevo_geojson is not None:
                        st.session_state.geojson_data = nuevo_geojson
                        st.session_state.map_key += 1
                        st.session_state.resultados = None
                        st.session_state.analisis_completado = False
                        st.rerun()
        
        # Período de análisis
        st.subheader("📅 Período de Análisis")
        col1, col2 = st.columns(2)
        with col1:
            fecha_inicio = st.date_input(
                "Fecha inicio",
                value=datetime.now() - timedelta(days=30)
            )
        with col2:
            fecha_fin = st.date_input("Fecha fin", value=datetime.now())
        
        # Botón de análisis
        analizar_disabled = st.session_state.geojson_data is None
        
        if st.button(
            "🚀 Ejecutar Análisis con Sentinel-2", 
            type="primary", 
            use_container_width=True,
            disabled=analizar_disabled,
            key="analizar_btn"
        ):
            if st.session_state.geojson_data is None:
                st.error("❌ Primero debes cargar un archivo geoespacial")
            else:
                # Crear contenedor para mensajes de progreso
                progress_container = st.empty()
                
                with progress_container.container():
                    st.info("🔄 Iniciando análisis...")
                    
                    try:
                        # Inicializar analizador
                        analizador = SentinelAnalizador(SENTINEL_CLIENT_ID, SENTINEL_CLIENT_SECRET)
                        
                        # Obtener BBox
                        bbox = obtener_bbox_desde_geojson(st.session_state.geojson_data)
                        if not bbox:
                            st.error("❌ Error en el área de análisis")
                            return
                        
                        # Obtener imagen
                        imagen = analizador.obtener_imagen_sentinel2(
                            bbox, 
                            fecha_inicio.strftime("%Y-%m-%d"), 
                            fecha_fin.strftime("%Y-%m-%d")
                        )
                        
                        if imagen is None:
                            st.error("❌ No se pudo obtener imagen Sentinel-2")
                            return
                        
                        # Calcular índices
                        indices = analizador.calcular_indices(imagen)
                        if indices is None:
                            st.error("❌ Error en el cálculo de índices")
                            return
                        
                        # Analizar salud
                        resultados = analizador.analizar_salud_cultivo(indices, cultivo)
                        if resultados is None:
                            st.error("❌ Error en el análisis de salud")
                            return
                        
                        # Guardar resultados
                        st.session_state.resultados = resultados
                        st.session_state.analisis_completado = True
                        st.session_state.map_key += 1
                        
                        st.success("🎉 ¡Análisis completado exitosamente!")
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"❌ Error durante el análisis: {str(e)}")

    # Contenido principal
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("🗺️ Mapa del Área")
        
        if st.session_state.geojson_data:
            # Información del área
            if st.session_state.geojson_data.get('features'):
                props = st.session_state.geojson_data['features'][0].get('properties', {})
                nombre = props.get('name', 'Polígono cargado')
                area_ha = props.get('area_ha', 'N/A')
                st.success(f"📍 **Área:** {nombre} | **Superficie:** {area_ha} ha")
            
            # Mostrar mapa
            mapa = crear_mapa_simple(st.session_state.geojson_data, st.session_state.resultados)
            st_folium(mapa, width=400, height=500, key=f"map_{st.session_state.map_key}")
            
            # Botón de exportación
            if st.session_state.analisis_completado and st.session_state.resultados:
                geojson_export = exportar_geojson(
                    st.session_state.geojson_data, 
                    st.session_state.resultados, 
                    cultivo
                )
                
                if geojson_export:
                    # Convertir a string para descarga
                    geojson_str = json.dumps(geojson_export, indent=2)
                    
                    st.download_button(
                        label="📥 Exportar GeoJSON con Resultados",
                        data=geojson_str,
                        file_name=f"analisis_{cultivo}_{datetime.now().strftime('%Y%m%d_%H%M')}.geojson",
                        mime="application/json",
                        type="primary",
                        use_container_width=True
                    )
        else:
            st.info("🗺️ **Carga un archivo para ver el mapa**")
    
    with col2:
        st.subheader("📊 Resultados del Análisis")
        
        if st.session_state.analisis_completado and st.session_state.resultados:
            resultados = st.session_state.resultados
            
            st.success("✅ Análisis completado con Sentinel-2 L2A")
            
            # Métricas principales
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("🌱 Salud General", f"{resultados['salud_general']:.1f}%")
            with col2:
                st.metric("📈 NDVI Medio", f"{resultados['ndvi_stats']['media']:.3f}")
            with col3:
                st.metric("💧 NDWI Medio", f"{resultados['ndwi_stats']['media']:.3f}")
            
            # Detalles
            st.subheader("🔍 Detalles del Análisis")
            st.write(f"**Píxeles analizados:** {resultados['pixeles_analizados']:,}")
            st.write(f"**NDVI en rango óptimo:** {resultados['ndvi_en_rango']:.1f}%")
            st.write(f"**NDWI en rango óptimo:** {resultados['ndwi_en_rango']:.1f}%")
            st.write(f"**Rango NDVI:** {resultados['ndvi_stats']['min']:.3f} - {resultados['ndvi_stats']['max']:.3f}")
            st.write(f"**Rango NDWI:** {resultados['ndwi_stats']['min']:.3f} - {resultados['ndwi_stats']['max']:.3f}")
            st.write(f"**Fecha de análisis:** {resultados['fecha_analisis'][:19]}")
            
            # Recomendaciones
            st.subheader("💡 Recomendaciones")
            salud = resultados['salud_general']
            if salud >= 80:
                st.success("**✅ EXCELENTE** - El cultivo está en condiciones óptimas")
            elif salud >= 60:
                st.warning("**🟡 BUENO** - Desarrollo adecuado, mantener monitoreo")
            elif salud >= 40:
                st.warning("**🟠 REGULAR** - Revisar riego y fertilización")
            else:
                st.error("**🔴 CRÍTICO** - Revisión urgente requerida")
                
        elif st.session_state.geojson_data and not st.session_state.analisis_completado:
            st.info("""
            ## ⏳ Listo para analizar
            
            **Archivo cargado correctamente.**
            
            Para ejecutar el análisis:
            1. Verifica el cultivo seleccionado
            2. Revisa el período de análisis  
            3. Haz clic en **"Ejecutar Análisis con Sentinel-2"**
            
            **El análisis puede tomar unos segundos.**
            """)
        else:
            st.info("""
            ## 🚀 Bienvenido al Analizador
            
            **Para comenzar:**
            1. **Selecciona el cultivo** en el panel izquierdo
            2. **Carga un archivo geoespacial** con tu polígono
            3. **Define el período** de análisis
            4. **Ejecuta el análisis** con Sentinel-2
            
            **Formatos soportados:**
            - 🔹 GeoJSON (.geojson, .json)
            - 🔹 Shapefile (.zip con .shp, .dbf, .shx)
            """)

    # Footer
    st.markdown("---")
    st.markdown(
        """
        <div style='text-align: center; color: gray;'>
        🌱 Analizador Multi-Cultivo | 🛰️ Sentinel-2 L2A | Credenciales automáticas
        </div>
        """,
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()
