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
import matplotlib.pyplot as plt
from io import BytesIO

# --- FALLBACKS ---
try:
    from sentinelhub import SHConfig, SentinelHubRequest, MimeType, CRS, BBox, DataCollection
    SH_AVAILABLE = True
except:
    SH_AVAILABLE = False
    st.warning("Sentinel Hub no disponible. Usando simulación realista.")

try:
    from fpdf import FPDF
    PDF_AVAILABLE = True
except:
    PDF_AVAILABLE = False

warnings.filterwarnings('ignore')
st.set_page_config(page_title="Multi-Cultivo", layout="wide")

st.title("ANALIZADOR MULTI-CULTIVO")
st.markdown("**Análisis NPK por zonas con Sentinel-2 L2A (10m)**")
st.markdown("---")

# --- CULTIVOS CON RECOMENDACIONES ---
CULTIVOS = {
    'TRIGO': {'N': (120, 180), 'P': (40, 60), 'K': (80, 120), 'NDVI': 0.7},
    'MAÍZ': {'N': (150, 220), 'P': (50, 70), 'K': (100, 140), 'NDVI': 0.75},
    'SOJA': {'N': (80, 120), 'P': (35, 50), 'K': (90, 130), 'NDVI': 0.65},
    'SORGO': {'N': (100, 150), 'P': (30, 45), 'K': (70, 100), 'NDVI': 0.6},
    'GIRASOL': {'N': (90, 130), 'P': (25, 40), 'K': (80, 110), 'NDVI': 0.55}
}

# --- CONFIG SH ---
@st.cache_resource
def get_sh_config():
    if not SH_AVAILABLE: return None
    config = SHConfig()
    if 'SH_CLIENT_ID' in st.secrets:
        config.sh_client_id = st.secrets['SH_CLIENT_ID']
        config.sh_client_secret = st.secrets['SH_CLIENT_SECRET']
    return config if config.sh_client_id else None

# --- EVALSCRIPT ---
EVALSCRIPT = """
//VERSION=3
function setup() {
  return {
    input: ["B04", "B08", "B05", "B11", "CLM"],
    output: { bands: 4, sampleType: "FLOAT32" }
  };
}
function evaluatePixel(s) {
  let ndvi = index(s.B08, s.B04);
  let ndre = index(s.B08, s.B05);
  let lai = ndvi > 0.1 ? Math.pow(ndvi, 2) * 5.5 : 0.1;
  let humedad = 1 - (s.B11 / 10000);
  return [ndvi, ndre, lai, humedad];
}
function index(a, b) { return a && b ? (a - b) / (a + b + 0.0001) : 0; }
"""

# --- PROCESADOR ---
class Processor:
    def __init__(self, config):
        self.config = config

    def get_indices(self, bbox, fecha):
        if self.config and SH_AVAILABLE:
            try:
                bbox_sh = BBox(bbox=bbox, crs=CRS.WGS84)
                request = SentinelHubRequest(
                    evalscript=EVALSCRIPT,
                    input_data=[SentinelHubRequest.input_data(
                        data_collection=DataCollection.SENTINEL2_L2A,
                        time_interval=(str(fecha), str(fecha + timedelta(days=1))),
                        other_args={"maxCloudCoverage": 20}
                    )],
                    responses=[SentinelHubRequest.output_response('default', MimeType.TIFF)],
                    bbox=bbox_sh,
                    size=(128, 128),
                    config=self.config
                )
                data = request.get_data()[0]
                return {
                    'ndvi': float(np.mean(data[:, :, 0])),
                    'ndre': float(np.mean(data[:, :, 1])),
                    'lai': float(np.mean(data[:, :, 2])),
                    'humedad': float(np.mean(data[:, :, 3])),
                    'fuente': 'Sentinel-2 L2A'
                }
            except Exception as e:
                st.warning(f"API error: {e}. Usando simulación.")
        # Simulación realista
        ndvi = np.clip(0.45 + np.random.normal(0, 0.12), 0.1, 0.9)
        return {
            'ndvi': ndvi,
            'ndre': max(0, ndvi - 0.15),
            'lai': ndvi * 5.5,
            'humedad': np.clip(0.3 + np.random.normal(0, 0.08), 0.1, 0.7),
            'fuente': 'Simulado'
        }

# --- DIVIDIR ZONAS ---
def dividir_zonas(gdf, n):
    geom = gdf.geometry.iloc[0]
    b = geom.bounds
    w = (b[2] - b[0]) / math.isqrt(n)
    h = (b[3] - b[1]) / math.isqrt(n)
    zonas = []
    for i in range(math.isqrt(n)):
        for j in range(math.isqrt(n)):
            if len(zonas) >= n: break
            poly = Polygon([(b[0]+j*w, b[1]+i*h), (b[0]+(j+1)*w, b[1]+i*h),
                           (b[0]+(j+1)*w, b[1]+(i+1)*h), (b[0]+j*w, b[1]+(i+1)*h)])
            inter = geom.intersection(poly)
            if not inter.is_empty:
                zonas.append(inter)
    return gpd.GeoDataFrame({'zona': range(1, len(zonas)+1), 'geometry': zonas}, crs=gdf.crs)

# --- ÁREA ---
def area_ha(gdf):
    return gdf.to_crs('EPSG:3857').area / 10000

# --- MAPA ---
def crear_mapa(gdf):
    center = [gdf.centroid.y.mean(), gdf.centroid.x.mean()]
    m = folium.Map(location=center, zoom_start=15, tiles=None)
    folium.TileLayer(
        "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri", name="ESRI"
    ).add_to(m)
    folium.GeoJson(gdf, style_function=lambda f: {
        'fillColor': 'green' if f['properties']['npk'] > 0.7 else 'yellow' if f['properties']['npk'] > 0.4 else 'red',
        'color': 'black', 'weight': 1, 'fillOpacity': 0.7
    }, tooltip=folium.GeoJsonTooltip(['zona', 'ndvi', 'npk', 'area_ha'])).add_to(m)
    return m

# --- PDF ---
def generar_pdf(gdf, cultivo):
    if not PDF_AVAILABLE: return None
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt=f"Reporte {cultivo} - {datetime.now().strftime('%Y-%m-%d')}", ln=1, align='C')
    pdf.cell(200, 10, txt=f"NDVI Promedio: {gdf['ndvi'].mean():.3f}", ln=1)
    pdf.cell(200, 10, txt=f"NPK Promedio: {gdf['npk'].mean():.3f}", ln=1)
    img = BytesIO()
    plt.figure(figsize=(6,4))
    plt.bar(gdf['zona'], gdf['npk'])
    plt.title("NPK por Zona")
    plt.savefig(img, format='png')
    plt.close()
    img.seek(0)
    pdf.image(img, w=180)
    return BytesIO(pdf.output(dest='S').encode('latin1'))

# --- SIDEBAR ---
with st.sidebar:
    st.header("Configuración")
    cultivo = st.selectbox("Cultivo", list(CULTIVOS.keys()))
    fecha = st.date_input("Fecha", value=datetime.now() - timedelta(days=15))
    zonas = st.slider("Zonas", 16, 48, 32, 4)
    zip_file = st.file_uploader("ZIP Shapefile", type=['zip'])

# --- MAIN ---
if zip_file:
    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(zip_file) as z:
            z.extractall(tmp)
        shp = next((f for f in os.listdir(tmp) if f.endswith('.shp')), None)
        if not shp:
            st.error("No se encontró .shp en el ZIP")
        else:
            gdf = gpd.read_file(os.path.join(tmp, shp))
            area_total = area_ha(gdf).sum()
            st.success(f"Parcela cargada: {area_total:.1f} ha")

            if st.button("EJECUTAR ANÁLISIS", type="primary"):
                gdf_z = dividir_zonas(gdf, zonas)
                proc = Processor(get_sh_config())
                bounds = gdf_z.total_bounds
                resultados = []
                for _ in gdf_z.iterrows():
                    idx = proc.get_indices(bounds, fecha)
                    resultados.append(idx)
                
                gdf_z['ndvi'] = [r['ndvi'] for r in resultados]
                gdf_z['ndre'] = [r['ndre'] for r in resultados]
                gdf_z['lai'] = [r['lai'] for r in resultados]
                gdf_z['humedad'] = [r['humedad'] for r in resultados]
                gdf_z['fuente'] = [r['fuente'] for r in resultados]
                gdf_z['npk'] = (gdf_z['ndvi']*0.5 + gdf_z['ndre']*0.3 + gdf_z['lai']/6*0.1 + gdf_z['humedad']*0.1).clip(0,1)
                gdf_z['area_ha'] = area_ha(gdf_z)

                # Métricas
                col1, col2, col3 = st.columns(3)
                with col1: st.metric("NDVI", f"{gdf_z['ndvi'].mean():.3f}")
                with col2: st.metric("NPK", f"{gdf_z['npk'].mean():.3f}")
                with col3: st.metric("Zonas", len(gdf_z))

                # Mapa
                st.subheader("Mapa Interactivo")
                folium_static(crear_mapa(gdf_z), width=700, height=500)

                # Tabla
                st.subheader("Resultados por Zona")
                tabla = gdf_z[['zona', 'area_ha', 'ndvi', 'npk']].round(3)
                st.dataframe(tabla)

                # Descargas
                st.subheader("Descargar")
                st.download_button("CSV", gdf_z.to_csv(index=False), "resultados.csv", "text/csv")
                st.download_button("GeoJSON", gdf_z.to_json(), "zonas.geojson", "application/json")
                if PDF_AVAILABLE:
                    pdf = generar_pdf(gdf_z, cultivo)
                    if pdf:
                        st.download_button("PDF Reporte", pdf, "reporte.pdf", "application/pdf")
else:
    st.info("Sube un ZIP con shapefile (.shp + .shx + .dbf)")

st.markdown("---")
st.markdown("**Funciona con o sin API**")
