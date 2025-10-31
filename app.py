import streamlit as st
import geopandas as gpd
import pandas as pd
import numpy as np
import tempfile
import os
import zipfile
from datetime import datetime, timedelta
import folium
from streamlit_folium import folium_static
from shapely.geometry import Polygon
import math
import warnings

# IMPORTS CONDICIONALES PARA SENTINEL HUB (ANTI-ERROR)
try:
    from sentinelhub import SHConfig, SentinelHubRequest, MimeType, CRS, BBox, DataCollection, Geometry
    SENTINELHUB_AVAILABLE = True
except ImportError:
    SENTINELHUB_AVAILABLE = False
    st.warning("⚠️ SentinelHub no disponible. Usando simulación de datos.")

try:
    from fpdf import FPDF
    FPDF_AVAILABLE = True
except ImportError:
    FPDF_AVAILABLE = False
    st.warning("⚠️ fpdf2 no disponible. PDF deshabilitado.")

try:
    import branca.colormap as cm
    BRANCA_AVAILABLE = True
except ImportError:
    BRANCA_AVAILABLE = False
    st.warning("⚠️ branca no disponible. Leyendas simples.")

warnings.filterwarnings('ignore')

st.set_page_config(page_title="Analizador Multi-Cultivo + Sentinel-2", layout="wide")
st.title("🌱 ANALIZADOR MULTI-CULTIVO - SENTINEL-2 + PDF + Leyendas")
st.markdown("**Agricultura de Precisión con IA + Satélite + Reportes PDF**")
st.markdown("---")

os.environ['SHAPE_RESTORE_SHX'] = 'YES'

# =============================================================================
# MAPAS BASE ESRI
# =============================================================================
MAPAS_BASE = {
    "ESRI World Imagery": {
        "url": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        "attribution": "Esri, Maxar, Earthstar Geographics",
        "name": "ESRI Satellite"
    },
    "ESRI World Street": {
        "url": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}",
        "attribution": "Esri, HERE, Garmin",
        "name": "ESRI Streets"
    },
    "OpenStreetMap": {
        "url": "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        "attribution": "OpenStreetMap contributors",
        "name": "OSM"
    }
}

# =============================================================================
# PARÁMETROS CULTIVOS
# =============================================================================
PARAMETROS_CULTIVOS = {
    'TRIGO':    {'NITRÓGENO': {'min': 120, 'max': 180}, 'FÓSFORO': {'min': 40, 'max': 60}, 'POTASIO': {'min': 80, 'max': 120}, 'NDVI_OPTIMO': 0.7, 'NDRE_OPTIMO': 0.4},
    'MAÍZ':     {'NITRÓGENO': {'min': 150, 'max': 220}, 'FÓSFORO': {'min': 50, 'max': 70}, 'POTASIO': {'min': 100, 'max': 140}, 'NDVI_OPTIMO': 0.75, 'NDRE_OPTIMO': 0.45},
    'SOJA':     {'NITRÓGENO': {'min': 80, 'max': 120},  'FÓSFORO': {'min': 35, 'max': 50}, 'POTASIO': {'min': 90, 'max': 130},  'NDVI_OPTIMO': 0.65, 'NDRE_OPTIMO': 0.35},
    'SORGO':    {'NITRÓGENO': {'min': 100, 'max': 150}, 'FÓSFORO': {'min': 30, 'max': 45}, 'POTASIO': {'min': 70, 'max': 100}, 'NDVI_OPTIMO': 0.6,  'NDRE_OPTIMO': 0.3},
    'GIRASOL':  {'NITRÓGENO': {'min': 90, 'max': 130},  'FÓSFORO': {'min': 25, 'max': 40}, 'POTASIO': {'min': 80, 'max': 110}, 'NDVI_OPTIMO': 0.55, 'NDRE_OPTIMO': 0.25}
}

ICONOS_CULTIVOS = {'TRIGO': '🌾', 'MAÍZ': '🌽', 'SOJA': '🫘', 'SORGO': '🌾', 'GIRASOL': '🌻'}

# =============================================================================
# SENTINEL HUB CONFIG (SOLO SI DISPONIBLE)
# =============================================================================
@st.cache_resource
def get_sh_config():
    if not SENTINELHUB_AVAILABLE:
        return None
    config = SHConfig()
    # Usa secrets o sidebar para credenciales
    if 'SH_CLIENT_ID' in st.secrets:
        config.sh_client_id = st.secrets['SH_CLIENT_ID']
        config.sh_client_secret = st.secrets['SH_CLIENT_SECRET']
    else:
        with st.sidebar.expander("🔑 Sentinel Hub Credenciales"):
            config.sh_client_id = st.text_input("Client ID", type="password")
            config.sh_client_secret = st.text_input("Client Secret", type="password")
            if st.button("💾 Guardar"):
                st.secrets['SH_CLIENT_ID'] = config.sh_client_id
                st.secrets['SH_CLIENT_SECRET'] = config.sh_client_secret
                st.success("Guardado. Recarga.")
    return config if config.sh_client_id and config.sh_client_secret else None

# Evalscript simplificado
EVALSCRIPT = """
//VERSION=3
function setup() {
  return {
    input: ["B04", "B05", "B08", "B11", "CLM"],
    output: { bands: 4, sampleType: "FLOAT32" }
  };
}
function evaluatePixel(sample) {
  let ndvi = (sample.B08 - sample.B04) / (sample.B08 + sample.B04);
  let ndre = (sample.B08 - sample.B05) / (sample.B08 + sample.B05);
  let humidity = 1 - (sample.B11 / 10000);
  return [ndvi, ndre, 0, humidity];
}
"""

class SentinelHubProcessor:
    def __init__(self, config):
        self.config = config

    def get_real_indices(self, bbox, fecha, resolution=10):
        if not self.config or not SENTINELHUB_AVAILABLE:
            return self._simulate_indices(bbox, fecha)
        try:
            bbox_sh = BBox(bbox=bbox, crs=CRS.WGS84)
            request = SentinelHubRequest(
                evalscript=EVALSCRIPT,
                input_data=[SentinelHubRequest.input_data(data_collection=DataCollection.SENTINEL2_L2A, time_interval=(fecha, fecha))],
                responses=[SentinelHubRequest.output_response('default', MimeType.TIFF)],
                bbox=bbox_sh,
                size=(512, 512),
                config=self.config
            )
            data = request.get_data()[0]
            ndvi_mean = np.mean(data[:, :, 0])
            ndre_mean = np.mean(data[:, :, 1])
            humidity_mean = np.mean(data[:, :, 3])
            lai = ndvi_mean * 5.5
            return {
                'ndvi': round(float(ndvi_mean), 3),
                'ndre': round(float(ndre_mean), 3),
                'lai': round(float(lai), 2),
                'humedad_suelo': round(float(humidity_mean), 3),
                'fuente': 'Sentinel Hub API Real'
            }
        except Exception as e:
            st.warning(f"API Error: {e}. Usando simulación.")
            return self._simulate_indices(bbox, fecha)

    def _simulate_indices(self, bbox, fecha):
        x_norm = (bbox[0] * 100) % 1
        y_norm = (bbox[1] * 100) % 1
        fecha_dt = datetime.combine(fecha, datetime.min.time())
        dias = (datetime.now() - fecha_dt).days
        ndvi = max(0.1, min(0.85, 0.45 + x_norm * 0.3 + y_norm * 0.2 + np.random.normal(0, 0.04)))
        ndre = max(0.05, min(0.75, 0.35 + x_norm * 0.25 - y_norm * 0.15 + np.random.normal(0, 0.035)))
        lai = max(0.5, min(6.0, ndvi * 5.5 + np.random.normal(0, 0.3)))
        humedad = max(0.08, min(0.75, 0.28 - (dias / 365 * 0.1) + np.random.normal(0, 0.045)))
        return {'ndvi': round(ndvi, 3), 'ndre': round(ndre, 3), 'lai': round(lai, 2), 'humedad_suelo': round(humedad, 3), 'fuente': 'Simulado'}

# =============================================================================
# MAPAS CON LEYENDAS SIMPLES (FALLBACK SI NO BRANCA)
# =============================================================================
def crear_mapa_base_esri(gdf, mapa_seleccionado="ESRI World Imagery"):
    bounds = gdf.total_bounds
    center_lat = (bounds[1] + bounds[3]) / 2
    center_lon = (bounds[0] + bounds[2]) / 2
    m = folium.Map(location=[center_lat, center_lon], zoom_start=16, tiles=None, control_scale=True)
    for nombre, config in MAPAS_BASE.items():
        folium.TileLayer(tiles=config["url"], attr=config["attribution"], name=config["name"], control=True, show=(nombre == mapa_seleccionado)).add_to(m)
    return m

def crear_leyenda_npk_simple():
    # Leyenda HTML simple con rangos numéricos
    return '''
    <div style="position: fixed; bottom: 50px; left: 50px; width: 200px; height: 180px; background-color: white; 
                border:2px solid grey; z-index:9999; font-size:12px; padding: 10px; border-radius: 5px;
                box-shadow: 0 0 10px rgba(0,0,0,0.2);">
        <div style="font-weight: bold; margin-bottom: 8px; text-align: center; font-size: 14px;">
            📊 ÍNDICE NPK (0-1)
        </div>
        <div style="display: flex; flex-direction: column; gap: 4px;">
            <div style="display: flex; align-items: center; justify-content: space-between;">
                <div style="width: 20px; height: 15px; background: #d73027; border: 1px solid #000; margin-right: 10px;"></div>
                <span>0.0-0.3: MUY BAJA</span>
            </div>
            <div style="display: flex; align-items: center; justify-content: space-between;">
                <div style="width: 20px; height: 15px; background: #fdae61; border: 1px solid #000; margin-right: 10px;"></div>
                <span>0.3-0.5: BAJA</span>
            </div>
            <div style="display: flex; align-items: center; justify-content: space-between;">
                <div style="width: 20px; height: 15px; background: #a6d96a; border: 1px solid #000; margin-right: 10px;"></div>
                <span>0.5-0.7: BUENA</span>
            </div>
            <div style="display: flex; align-items: center; justify-content: space-between;">
                <div style="width: 20px; height: 15px; background: #006837; border: 1px solid #000; margin-right: 10px;"></div>
                <span>0.7-1.0: ÓPTIMA</span>
            </div>
        </div>
    </div>
    '''

def crear_mapa_interactivo(gdf_analizado, mapa_base):
    m = crear_mapa_base_esri(gdf_analizado, mapa_base)

    def estilo_zona(feature):
        npk = feature['properties'].get('npk_actual', 0.5)
        if npk < 0.3:
            color = '#d73027'
        elif npk < 0.5:
            color = '#fdae61'
        elif npk < 0.7:
            color = '#a6d96a'
        else:
            color = '#006837'
        return {'fillColor': color, 'color': 'white', 'weight': 2, 'fillOpacity': 0.75}

    folium.GeoJson(
        gdf_analizado.__geo_interface__,
        name='Zonas NPK',
        style_function=estilo_zona,
        tooltip=folium.GeoJsonTooltip(
            fields=['id_zona', 'npk_actual', 'ndvi', 'area_ha', 'categoria'],
            aliases=['Zona:', 'NPK (0-1):', 'NDVI (0-1):', 'Área (ha):', 'Estado:'],
            localize=True,
            style="background: #2E7D32; color: white; border-radius: 8px; padding: 8px;"
        )
    ).add_to(m)

    # Leyenda simple con rangos
    m.get_root().html.add_child(folium.Element(crear_leyenda_npk_simple()))
    folium.LayerControl().add_to(m)
    return m

# =============================================================================
# PDF SIMPLE (FALLBACK SI NO FPDF)
# =============================================================================
def generar_pdf_reporte(gdf_res, config):
    if not FPDF_AVAILABLE:
        st.warning("PDF no disponible. Usa CSV/GeoJSON.")
        return None
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=16)
    pdf.cell(200, 10, txt=f"Reporte {config['cultivo']} - {datetime.now().strftime('%d/%m/%Y')}", ln=1, align='C')
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt=f"Área: {gdf_res['area_ha'].sum():.1f} ha | NPK: {gdf_res['npk_actual'].mean():.3f}", ln=1)
    # Gráfico simple
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(gdf_res['id_zona'], gdf_res['npk_actual'], color='green', alpha=0.7)
    ax.set_title('NPK por Zona')
    ax.set_xlabel('Zona')
    ax.set_ylabel('Índice NPK')
    buf = io.BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight')
    buf.seek(0)
    pdf.image(buf, x=10, y=30, w=190)
    plt.close()
    # Tabla resumen
    pdf.ln(80)
    pdf.cell(200, 10, txt="Resumen por Categoría:", ln=1)
    for cat, count in gdf_res['categoria'].value_counts().items():
        pdf.cell(200, 10, txt=f"{cat}: {count} zonas ({count*100/len(gdf_res):.1f}%)", ln=1)
    buf_pdf = io.BytesIO()
    buf_pdf.write(pdf.output(dest='S').encode('latin1'))
    buf_pdf.seek(0)
    return buf_pdf

# =============================================================================
# FUNCIONES BÁSICAS
# =============================================================================
def calcular_superficie(gdf):
    try:
        if gdf.crs and gdf.crs.is_geographic:
            return gdf.to_crs('EPSG:3857').geometry.area / 10000
        else:
            return gdf.geometry.area / 10000
    except:
        return gdf.geometry.area / 10000

def dividir_parcela_en_zonas(gdf, n_zonas):
    if len(gdf) == 0:
        return gdf
    parcela = gdf.iloc[0].geometry
    bounds = parcela.bounds
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
            cell = Polygon([(minx + j*width, miny + i*height), (minx + (j+1)*width, miny + i*height),
                            (minx + (j+1)*width, miny + (i+1)*height), (minx + j*width, miny + (i+1)*height)])
            inter = parcela.intersection(cell)
            if not inter.is_empty and inter.area > 0:
                sub_poligonos.append(inter)
    if sub_poligonos:
        return gpd.GeoDataFrame({'id_zona': range(1, len(sub_poligonos)+1), 'geometry': sub_poligonos}, crs=gdf.crs)
    return gdf

def calcular_indices_sentinel2(gdf_dividido, cultivo, fecha_imagen):
    config_sh = get_sh_config()
    processor = SentinelHubProcessor(config_sh)
    resultados = []
    bounds = gdf_dividido.total_bounds
    bbox = [bounds[0], bounds[1], bounds[2], bounds[3]]
    for idx, row in gdf_dividido.iterrows():
        s2 = processor.get_real_indices(bbox, fecha_imagen)
        npk = (s2['ndvi'] * 0.4 + s2['ndre'] * 0.3 + (s2['lai']/6.0)*0.2 + s2['humedad_suelo']*0.1)
        npk = max(0, min(1, npk))
        resultados.append({**s2, 'npk_actual': round(npk, 3)})
    return resultados

# =============================================================================
# SIDEBAR
# =============================================================================
with st.sidebar:
    st.header("⚙️ Configuración")
    cultivo = st.selectbox("🌱 Cultivo:", list(PARAMETROS_CULTIVOS.keys()))
    fecha_sentinel = st.date_input("📅 Fecha Imagen:", value=datetime.now() - timedelta(days=15), max_value=datetime.now())
    mapa_base = st.selectbox("🗺️ Mapa Base:", list(MAPAS_BASE.keys()), index=0)
    n_divisiones = st.slider("🎯 Número de Zonas:", 16, 48, 32, step=4)
    uploaded_zip = st.file_uploader("📤 ZIP Shapefile:", type=['zip'])

# =============================================================================
# ANÁLISIS PRINCIPAL
# =============================================================================
def analisis_multicultivo_sentinel2(gdf, config):
    st.header(f"{ICONOS_CULTIVOS[config['cultivo']]} {config['cultivo']}")
    st.markdown("**🛰️ Sentinel-2 Datos + ESRI**")

    with st.spinner("📐 Dividiendo en zonas..."):
        gdf_zonas = dividir_parcela_en_zonas(gdf, config['n_divisiones'])
    st.success(f"✅ {len(gdf_zonas)} zonas creadas")

    with st.spinner("🛰️ Procesando datos..."):
        indices = calcular_indices_sentinel2(gdf_zonas, config['cultivo'], config['fecha_sentinel'])

    areas = calcular_superficie(gdf_zonas)
    gdf_res = gdf_zonas.copy()
    gdf_res['area_ha'] = areas
    for idx, ind in enumerate(indices):
        for k, v in ind.items():
            gdf_res.loc[idx, k] = v
    gdf_res['categoria'] = gdf_res['npk_actual'].apply(lambda x: "🚨 MUY BAJA" if x < 0.3 else "⚠️ BAJA" if x < 0.5 else "✅ BUENA" if x < 0.7 else "🌟 ÓPTIMA")

    # Métricas
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("🗺️ Zonas", len(gdf_res))
    with col2:
        st.metric("📏 Área Total", f"{gdf_res['area_ha'].sum():.1f} ha")
    with col3:
        st.metric("📊 NPK Promedio", f"{gdf_res['npk_actual'].mean():.3f}")
    with col4:
        st.metric("🌿 NDVI Promedio", f"{gdf_res['ndvi'].mean():.3f}")

    # Mapa con leyenda numérica
    st.subheader("🗺️ Mapa Interactivo")
    mapa = crear_mapa_interactivo(gdf_res, config['mapa_base'])
    folium_static(mapa, width="100%", height=600)

    # Tabla
    st.subheader("📋 Detalles por Zona")
    tabla = gdf_res[['id_zona', 'area_ha', 'npk_actual', 'ndvi', 'ndre', 'humedad_suelo', 'categoria']].round(3)
    tabla.columns = ['Zona', 'Área (ha)', 'Índice NPK', 'NDVI', 'NDRE', 'Humedad Suelo', 'Estado']
    st.dataframe(tabla, use_container_width=True)

    # Descargas
    st.subheader("💾 Exportar")
    col_dl1, col_dl2, col_dl3 = st.columns(3)
    with col_dl1:
        csv_data = gdf_res.to_csv(index=False).encode('utf-8')
        st.download_button("📥 CSV", csv_data, f"analisis_{config['cultivo']}.csv", "text/csv")
    with col_dl2:
        geojson_data = gdf_res.to_json()
        st.download_button("🗺️ GeoJSON", geojson_data, f"zonas_{config['cultivo']}.geojson", "application/json")
    with col_dl3:
        if FPDF_AVAILABLE:
            pdf_buffer = generar_pdf_reporte(gdf_res, config)
            if pdf_buffer:
                st.download_button("📄 PDF Reporte", pdf_buffer.getvalue(), f"reporte_{config['cultivo']}.pdf", "application/pdf")
        else:
            st.info("📄 PDF: Instala fpdf2 para habilitar.")

# =============================================================================
# MAIN
# =============================================================================
if uploaded_zip is not None:
    with st.spinner("📁 Cargando..."):
        try:
            with tempfile.TemporaryDirectory() as tmp_dir:
                with zipfile.ZipFile(uploaded_zip, 'r') as zip_ref:
                    zip_ref.extractall(tmp_dir)
                shp_files = [f for f in os.listdir(tmp_dir) if f.endswith('.shp')]
                if not shp_files:
                    st.error("❌ No .shp en ZIP.")
                else:
                    shp_path = os.path.join(tmp_dir, shp_files[0])
                    gdf = gpd.read_file(shp_path)
                    if gdf.empty:
                        st.error("❌ Shapefile vacío.")
                    else:
                        area_total = calcular_superficie(gdf).sum()
                        st.success(f"✅ Cargado: {area_total:.1f} ha")
                        if st.button("🚀 ANALIZAR", type="primary"):
                            config = {'cultivo': cultivo, 'fecha_sentinel': fecha_sentinel, 'mapa_base': mapa_base, 'n_divisiones': n_divisiones}
                            analisis_multicultivo_sentinel2(gdf, config)
        except Exception as e:
            st.error(f"❌ Error: {str(e)}")
else:
    st.info("👆 Sube ZIP con shapefile.")
    with st.expander("ℹ️ Info"):
        st.markdown("""
        - **🛰️ Sentinel-2:** API real o simulación.
        - **📄 PDF:** Reporte con gráficos y mapa.
        - **🎨 Leyendas:** Rangos numéricos (0.0-1.0).
        """)

st.markdown("---")
st.markdown("*Powered by xAI + Sentinel Hub*")
