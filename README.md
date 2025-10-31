# 🌱 Analizador Multi-Cultivo - GEE + Sentinel-2

Sistema de análisis agrícola que combina la metodología Google Earth Engine con datos Sentinel-2 Harmonizados para recomendaciones de fertilización específicas por cultivo.

## 🚀 Características

- **🛰️ Datos Sentinel-2 Harmonizados**: Resolución 10m con corrección atmosférica L2A
- **🌱 Multi-Cultivo**: Soporte para trigo, maíz, soja, sorgo y girasol
- **🎯 Recomendaciones NPK**: Dosis específicas por cultivo y zona
- **🗺️ Mapas Interactivos**: Visualización con mapas base ESRI
- **📊 Análisis de Precisión**: División en zonas de manejo

## 🛠️ Instalación

```bash
git clone https://github.com/tu-usuario/analizador-multi-cultivo.git
cd analizador-multi-cultivo
pip install -r requirements.txt
streamlit run app.py
