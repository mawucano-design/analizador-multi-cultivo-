"""
Configuración de la aplicación Analizador Multi-Cultivo
"""

# Configuración de cultivos
CULTIVOS_CONFIG = {
    "trigo": {
        "nombre": "Trigo",
        "ndvi_optimo": (0.6, 0.8),
        "color": "#FFD700",
        "ciclo": "invierno"
    },
    "maiz": {
        "nombre": "Maíz",
        "ndvi_optimo": (0.7, 0.9),
        "color": "#32CD32", 
        "ciclo": "verano"
    },
    "soja": {
        "nombre": "Soja",
        "ndvi_optimo": (0.6, 0.85),
        "color": "#90EE90",
        "ciclo": "verano"
    },
    "sorgo": {
        "nombre": "Sorgo", 
        "ndvi_optimo": (0.5, 0.75),
        "color": "#DAA520",
        "ciclo": "verano"
    },
    "girasol": {
        "nombre": "Girasol",
        "ndvi_optimo": (0.4, 0.7),
        "color": "#FF8C00",
        "ciclo": "verano"
    }
}

# Configuración de la aplicación
APP_CONFIG = {
    "title": "Analizador Multi-Cultivo",
    "description": "Sistema de análisis de cultivos con datos geoespaciales",
    "version": "1.0.0"
}
