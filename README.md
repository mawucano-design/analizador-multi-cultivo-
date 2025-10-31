# Analizador Multi-Cultivo - Sentinel-2 + ESRI

Análisis de fertilidad NPK por zonas usando imágenes reales **Sentinel-2 (10m)** y mapas base **ESRI World Imagery**.

## Características

* **API Real Sentinel Hub** (NDVI, NDRE)
* **Mapas ESRI 50cm/píxel**
* 5 cultivos: Trigo, Maíz, Soja, Sorgo, Girasol
* Zonas de manejo: 16 a 48
* Descarga: CSV + GeoJSON + PDF
* **Funciona en Streamlit Cloud**

## Deploy

[https://analizador-multi-cultivo-.streamlit.app](https://analizador-multi-cultivo-.streamlit.app)

## Uso

1. Sube un ZIP con shapefile
2. Selecciona cultivo y fecha
3. ¡Obtén análisis por zonas!

## Requisitos

```bash
pip install -r requirements.txt
