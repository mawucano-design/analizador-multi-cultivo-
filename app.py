import streamlit as st
import geopandas as gpd
import folium
from streamlit_folium import folium_static
import tempfile
import os
import pandas as pd
import numpy as np

# Configuración de página
st.set_page_config(
    page_title="Analizador Fertilidad + Mapa ESRI",
    page_icon="🌾",
    layout="wide"
)

# Título principal
st.title("🌾 Analizador de Fertilidad con Mapa ESRI")
st.markdown("""
Carga un **polígono SHP** para analizar niveles de **N, P, K** y obtener recomendaciones por cultivo.
Los resultados se visualizan en un **mapa base de ESRI (World Street Map)**.
""")

# Sidebar: Selección de cultivo
st.sidebar.header("Configuración")
cultivo = st.sidebar.selectbox(
    "Selecciona el cultivo:",
    ["Trigo", "Maíz", "Soja", "Sorgo", "Girasol"]
)

# Carga de archivos SHP
st.header("Carga el polígono (SHP)")
uploaded_files = st.file_uploader(
    "Sube los archivos del SHP (.shp, .shx, .dbf, .prj, etc.)",
    type=['shp', 'shx', 'dbf', 'prj', 'cpg', 'qpj'],
    accept_multiple_files=True
)

if uploaded_files:
    # Verificar que haya al menos un .shp
    shp_file = None
    for file in uploaded_files:
        if file.name.lower().endswith('.shp'):
            shp_file = file
            break

    if not shp_file:
        st.error("Por favor, incluye el archivo `.shp`.")
        st.stop()

    # Crear directorio temporal y guardar archivos
    with tempfile.TemporaryDirectory() as tmpdir:
        file_paths = {}
        for file in uploaded_files:
            file_path = os.path.join(tmpdir, file.name)
            with open(file_path, "wb") as f:
                f.write(file.getbuffer())
            file_paths[file.name.lower()] = file_path

        shp_path = file_paths.get(shp_file.name.lower())

        try:
            # Leer el shapefile
            gdf = gpd.read_file(shp_path)
            if gdf.empty:
                st.error("El SHP está vacío o no contiene geometrías.")
                st.stop()

            st.success(f"Polígono cargado: {len(gdf)} feature(s)")

            # Mostrar información básica
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Número de polígonos", len(gdf))
            with col2:
                total_area = gdf.to_crs(epsg=3857).geometry.area.sum() / 10000  # ha
                st.metric("Área total", f"{total_area:,.2f} ha")

            # --- ANÁLISIS DE NUTRIENTES (SIMULADO) ---
            # REEMPLAZA ESTA SECCIÓN CON TU CÓDIGO GEE ORIGINAL
            st.header("Análisis de Nutrientes (N, P, K)")

            with st.spinner("Procesando análisis de suelo..."):
                # Simulación de valores (reemplazar con GEE)
                np.random.seed(42)
                N = np.random.uniform(20, 80)
                P = np.random.uniform(10, 60)
                K = np.random.uniform(30, 90)

                # Recomendaciones por cultivo (kg/ha)
                rec = {
                    "Trigo":  (max(0, 100 - N), max(0, 50 - P), max(0, 70 - K)),
                    "Maíz":   (max(0, 180 - N), max(0, 80 - P), max(0, 100 - K)),
                    "Soja":   (max(0, 40 - N),  max(0, 60 - P), max(0, 50 - K)),
                    "Sorgo":  (max(0, 120 - N), max(0, 60 - P), max(0, 80 - K)),
                    "Girasol":(max(0, 60 - N),  max(0, 70 - P), max(0, 60 - K)),
                }

                rec_N, rec_P, rec_K = rec[cultivo]

                # Mostrar métricas
                cols = st.columns(3)
                with cols[0]:
                    st.metric("Nitrógeno (N)", f"{N:.1f} ppm", f"+{rec_N:.0f} kg/ha")
                with cols[1]:
                    st.metric("Fósforo (P)", f"{P:.1f} ppm", f"+{rec_P:.0f} kg/ha")
                with cols[2]:
                    st.metric("Potasio (K)", f"{K:.1f} ppm", f"+{rec_K:.0f} kg/ha")

                # Tabla de resultados
                df_result = pd.DataFrame({
                    "Nutriente": ["N", "P", "K"],
                    "Valor Actual (ppm)": [f"{N:.1f}", f"{P:.1f}", f"{K:.1f}"],
                    "Recomendación (kg/ha)": [f"{rec_N:.0f}", f"{rec_P:.0f}", f"{rec_K:.0f}"]
                })
                st.table(df_result)

            # --- MAPA CON BASE ESRI ---
            st.header("Mapa Interactivo (ESRI World Street Map)")

            # Centro del polígono
            centroid = gdf.geometry.union_all().centroid
            center_lat, center_lon = centroid.y, centroid.x

            # Crear mapa Folium
            m = folium.Map(
                location=[center_lat, center_lon],
                zoom_start=14,
                tiles=None  # Sin tiles por defecto
            )

            # Capa base ESRI
            esri_street = folium.TileLayer(
                tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}',
                attr='Esri',
                name='ESRI World Street Map',
                overlay=False,
                control=True
            ).add_to(m)

            esri_sat = folium.TileLayer(
                tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
                attr='Esri',
                name='ESRI World Imagery',
                overlay=False,
                control=True
            ).add_to(m)

            # Polígono con estilo
            folium.GeoJson(
                gdf,
                name="Área de análisis",
                style_function=lambda x: {
                    'fillColor': '#3388ff',
                    'color': 'black',
                    'weight': 3,
                    'fillOpacity': 0.4
                },
                tooltip=folium.GeoJsonTooltip(
                    fields=list(gdf.columns.drop('geometry')),
                    aliases=[f"{col}:" for col in gdf.columns.drop('geometry')]
                )
            ).add_to(m)

            # Marcador central con info
            fertilidad_prom = (N + P + K) / 3
            color = 'green' if fertilidad_prom > 60 else 'orange' if fertilidad_prom > 40 else 'red'

            folium.CircleMarker(
                location=[center_lat, center_lon],
                radius=12,
                popup=folium.Popup(
                    f"<b>{cultivo}</b><br>"
                    f"N: {N:.1f} ppm<br>P: {P:.1f} ppm<br>K: {K:.1f} ppm<br>"
                    f"Área: {total_area:,.1f} ha",
                    max_width=300
                ),
                color='black',
                weight=2,
                fillColor=color,
                fillOpacity=0.8
            ).add_to(m)

            # Control de capas
            folium.LayerControl().add_to(m)

            # Mostrar mapa en Streamlit
            folium_static(m, width=800, height=500)

        except Exception as e:
            st.error(f"Error al procesar el SHP: {str(e)}")
            st.info("Asegúrate de subir todos los archivos necesarios del SHP.")
            st.stop()
else:
    st.info("Sube los archivos del polígono para comenzar.")
    st.markdown("""
    ### Instrucciones:
    1. Prepara tu polígono en formato **SHP**.
    2. Comprime todos los archivos (.shp, .shx, .dbf, .prj, etc.) en un ZIP **o súbelos uno por uno**.
    3. Selecciona el cultivo.
    4. ¡Listo! Verás análisis y mapa.
    """)

# Footer
st.markdown("---")
st.markdown(
    "<small>Desarrollado con ❤️ usando Streamlit, Folium y bases de ESRI | "
    "Basado en metodología GEE</small>",
    unsafe_allow_html=True
)
