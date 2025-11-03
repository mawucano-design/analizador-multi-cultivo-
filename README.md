# 🧪 Analizador de Fertilidad con Mapa ESRI

Visualización de polígonos SHP reales para análisis de nutrientes (N, P, K) en 5 cultivos: Trigo, Maíz, Soja, Sorgo, Girasol. Incluye recomendaciones de fertilización y mapas interactivos con base ESRI.

## ✨ Funcionalidades
- Carga de archivos SHP para definir el área de análisis.
- Análisis de nutrientes usando metodología GEE (integra tu código original).
- Recomendaciones específicas por cultivo.
- **Nuevo:** Visualización del polígono y resultados en mapa base ESRI (World Street Map) con Folium.

## 🚀 Cómo usar
1. Despliega en [Streamlit Cloud](https://share.streamlit.io/) conectando este repo.
2. Sube archivos SHP (.shp, .shx, .dbf).
3. Selecciona el cultivo en la sidebar.
4. Ve los resultados y el mapa interactivo.

## 📦 Requisitos
Ver `requirements.txt`. Instala con `pip install -r requirements.txt`.

## 🔧 Desarrollo
- Basado en [repo original](https://github.com/mawucano-design/Analizador-de-Fertilidad.-Trigo---Ma-z---Soja---Sorgo---Girasol).
- Para GEE: Configura autenticación en Google Earth Engine.
- Mapa ESRI: Usa tiles gratuitos de ArcGIS Online (ver términos de uso).

## 📝 Licencia
MIT License.

¡Contribuciones bienvenidas! 🌾
