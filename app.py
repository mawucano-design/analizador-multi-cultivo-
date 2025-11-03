import streamlit as st
import geopandas as gpd
import folium
from streamlit_folium import folium_static
import tempfile
import os
import pandas as pd
import numpy as np
# Importa ee si usas GEE en el original: import ee

st.set_page_config(page_title="Analizador de Fertilidad con Mapa ESRI", layout="wide")

st.title("🧪 Analizador de Fertilidad - Trigo, Maíz, Soja, Sorgo, Girasol")
st.markdown("Carga un polígono SHP para analizar nutrientes (N, P, K) y ver resultados en mapa ESRI.")

# Sidebar para selección de cultivo
st.sidebar.header("Selecciona el cultivo")
cultivo = st.sidebar.selectbox("Cultivo:", ["Trigo", "Maíz", "Soja", "Sorgo", "Girasol"])

# Carga de archivos SHP (necesitas shp, shx, dbf)
st.header("📁 Carga el polígono SHP")
files = st.file_uploader("Sube los archivos SHP (shp, shx, dbf)", type=['shp', 'shx', 'dbf'], accept_multiple_files=True)

if len(files) >= 3:  # Asegura que se suban al menos los 3 principales
    with tempfile.TemporaryDirectory() as tmpdirname:
        file_paths = {}
        for file in files:
            file_path = os.path.join(tmpdirname, file.name)
            with open(file_path, "wb") as f:
                f.write(file.getbuffer())
            file_paths[file.name.lower()] = file_path

        # Lee el SHP
        shp_path = file_paths.get('*.shp', list(file_paths.values())[0])  # Toma el shp
        gdf = gpd.read_file(shp_path)
        
        if len(gdf) > 0:
            st.success("✅ Polígono cargado correctamente.")
            
            # Muestra info básica del polígono
            st.subheader("ℹ️ Información del polígono")
            st.write(f"CRS: {gdf.crs}")
            st.write(f"Área total: {gdf.geometry.area.sum():.2f} unidades")
            
            # ANÁLISIS SIMULADO (REEMPLAZA CON TU LÓGICA ORIGINAL DE GEE PARA N, P, K)
            st.header("🔬 Análisis de Nutrientes")
            with st.spinner("Analizando..."):
                # Simulación: valores aleatorios de N, P, K (0-100)
                np.random.seed(42)  # Para reproducibilidad
                N = np.random.uniform(20, 80)
                P = np.random.uniform(10, 60)
                K = np.random.uniform(30, 90)
                
                # Recomendaciones por cultivo (simplificadas; integra las tuyas del original)
                if cultivo == "Trigo":
                    rec_N = max(0, 100 - N)
                    rec_P = max(0, 50 - P)
                    rec_K = max(0, 70 - K)
                    st.metric("Recomendación N", f"{rec_N:.1f} kg/ha")
                    st.metric("Recomendación P", f"{rec_P:.1f} kg/ha")
                    st.metric("Recomendación K", f"{rec_K:.1f} kg/ha")
                elif cultivo == "Maíz":
                    rec_N = max(0, 150 - N)
                    rec_P = max(0, 60 - P)
                    rec_K = max(0, 80 - K)
                    st.metric("Recomendación N", f"{rec_N:.1f} kg/ha")
                    st.metric("Recomendación P", f"{rec_P:.1f} kg/ha")
                    st.metric("Recomendación K", f"{rec_K:.1f} kg/ha")
                # Agrega casos para Soja, Sorgo, Girasol similares...
                else:
                    st.info("Recomendaciones para otros cultivos en desarrollo.")
                
                # Resultados en tabla
                df_result = pd.DataFrame({
                    "Nutriente": ["N", "P", "K"],
                    "Valor Actual": [f"{N:.1f}", f"{P:.1f}", f"{K:.1f}"],
                    "Recomendación": [f"{rec_N:.1f}", f"{rec_P:.1f}", f"{rec_K:.1f}"]
                })
                st.table(df_result)
            
            # MAPA CON BASE ESRI
            st.header("🗺️ Visualización en Mapa ESRI")
            geom = gdf.geometry.iloc[0]  # Asume un solo polígono
            bounds = geom.bounds
            center_lat = (bounds[1] + bounds[3]) / 2
            center_lon = (bounds[0] + bounds[2]) / 2
            
            # Crea mapa Folium con base ESRI
            m = folium.Map(location=[center_lat, center_lon], zoom_start=12)
            
            # Capa base ESRI World Street Map
            esri_url = 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}'
            folium.TileLayer(esri_url, name='ESRI World Street Map', attr='ESRI').add_to(m)
            
            # Agrega el polígono
            folium.GeoJson(
                gdf,
                style_function=lambda x: {'fillColor': 'blue', 'color': 'black', 'weight': 2, 'fillOpacity': 0.3},
                popup=folium.GeoJsonTooltip(fields=['name'])  # Si hay campo 'name'
            ).add_to(m)
            
            # Overlay de resultados (ej. marcador con fertilidad promedio)
            fertilidad_prom = (N + P + K) / 3 / 100  # Normalizado 0-1
            color = 'green' if fertilidad_prom > 0.6 else 'yellow' if fertilidad_prom > 0.4 else 'red'
            folium.CircleMarker(
                location=[center_lat, center_lon],
                radius=15,
                popup=f"Fertilidad promedio: {fertilidad_prom:.2f}<br>Cultivo: {cultivo}",
                color=color,
                fill=True,
                fillColor=color
            ).add_to(m)
            
            # Control de capas
            folium.LayerControl().add_to(m)
            
            # Muestra el mapa en Streamlit
            folium_static(m, width=700, height=500)
            
        else:
            st.error("No se encontró geometría en el SHP.")
else:
    st.warning("⚠️ Sube al menos los archivos .shp, .shx y .dbf para continuar.")
    st.info("Nota: Si tu SHP tiene más archivos (ej. .prj), súbelos también.")

# Pie de página
st.markdown("---")
st.markdown("Desarrollado con ❤️ usando Streamlit y ESRI basemaps.")
