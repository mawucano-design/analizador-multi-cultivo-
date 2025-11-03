# 🌱 Analizador Multi-Cultivo con Sentinel-2

Aplicación web interactiva para análisis de cultivos utilizando Streamlit y simulaciones de datos Sentinel-2.

## 🚀 Despliegue Rápido en Streamlit Cloud

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://analizador-multi-cultivo.streamlit.app/)

### Características Principales

- **Interfaz Web Moderna** con Streamlit
- **Análisis Multi-Cultivo** (Trigo, Maíz, Soja, Sorgo, Girasol)
- **Mapas Interactivos** con Folium y capas ESRI
- **Métricas de Salud** de cultivos (NDVI, NDWI)
- **Recomendaciones Automáticas** basadas en análisis
- **Modo Demo** con datos simulados

## 📋 Uso Rápido

1. **Accede a la aplicación** en Streamlit Cloud
2. **Selecciona un cultivo** en el panel izquierdo
3. **Configura el análisis** (usa el polígono de ejemplo o sube tu GeoJSON)
4. **Haz clic en "Ejecutar Análisis"**
5. **Visualiza los resultados** en el mapa y paneles

## 🛠️ Ejecución Local

```bash
# Clonar el repositorio
git clone https://github.com/mawucano-design/analizador-multi-cultivo-.git
cd analizador-multi-cultivo-

# Instalar dependencias
pip install -r requirements.txt

# Ejecutar la aplicación
streamlit run app.py
