# 🌱 Analizador Multi-Cultivo con Sentinel-2

Sistema de análisis de cultivos utilizando imágenes satelitales Sentinel-2 y Sentinel Hub.

## 🚀 Características

- **Análisis multi-cultivo** (Trigo, Maíz, Soja, Sorgo, Girasol)
- **Imágenes Sentinel-2** en tiempo casi real
- **Índices de vegetación** (NDVI, NDWI)
- **Mapas interactivos** con capas base ESRI
- **Evaluación de salud** de cultivos
- **Recomendaciones automáticas** basadas en análisis

## 📋 Prerrequisitos

### Credenciales Sentinel Hub
1. Regístrate en [Sentinel Hub](https://www.sentinel-hub.com/)
2. Crea una nueva instancia en [Dashboard](https://apps.sentinel-hub.com/dashboard/)
3. Obtén tu `Client ID` y `Client Secret`

### Configuración de credenciales

**Opción 1: Variables de entorno**
```bash
export SENTINELHUB_CLIENT_ID="tu_client_id"
export SENTINELHUB_CLIENT_SECRET="tu_client_secret"
