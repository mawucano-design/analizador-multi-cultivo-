import folium
import streamlit as st
from streamlit_folium import folium_static

MAPAS_BASE = {
    "ESRI World Imagery": {
        "url": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        "attribution": "Esri, Maxar, Earthstar Geographics",
        "name": "ESRI Satellite"
    },
    "ESRI World Street Map": {
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

def crear_mapa_base(gdf, mapa_seleccionado="ESRI World Imagery", zoom_start=14):
    """Crea un mapa base con el estilo seleccionado"""
    bounds = gdf.total_bounds
    center_lat = (bounds[1] + bounds[3]) / 2
    center_lon = (bounds[0] + bounds[2]) / 2
    
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=zoom_start,
        tiles=None,
        control_scale=True,
        zoom_control=True
    )
    
    for nombre, config in MAPAS_BASE.items():
        folium.TileLayer(
            tiles=config["url"],
            attr=config["attribution"],
            name=config["name"],
            control=True,
            show=(nombre == mapa_seleccionado)
        ).add_to(m)
    
    return m

def crear_mapa_interactivo_gee(gdf, nutriente, analisis_tipo, cultivo, mapa_base="ESRI World Imagery"):
    """Crea mapa interactivo con datos GEE y base ESRI"""
    
    m = crear_mapa_base(gdf, mapa_base, zoom_start=14)
    
    # Determinar columna y valores según el tipo de análisis
    if analisis_tipo == "FERTILIDAD ACTUAL":
        columna = 'npk_actual'
        titulo_leyenda = '🌱 Índice NPK Actual'
        vmin, vmax = 0, 1
    else:
        columna = 'valor_recomendado'
        from src.data_processor import PARAMETROS_CULTIVOS
        params = PARAMETROS_CULTIVOS[cultivo]
        if nutriente == "NITRÓGENO":
            titulo_leyenda = '🎯 Recomendación Nitrógeno (kg/ha)'
            vmin, vmax = (params['NITROGENO']['min'] * 0.8, params['NITROGENO']['max'] * 1.2)
        elif nutriente == "FÓSFORO":
            titulo_leyenda = '🎯 Recomendación Fósforo (kg/ha)'
            vmin, vmax = (params['FOSFORO']['min'] * 0.8, params['FOSFORO']['max'] * 1.2)
        else:
            titulo_leyenda = '🎯 Recomendación Potasio (kg/ha)'
            vmin, vmax = (params['POTASIO']['min'] * 0.8, params['POTASIO']['max'] * 1.2)
    
    def estilo_poligono(feature):
        valor = feature['properties'].get(columna, 0)
        if valor is None:
            return {'fillColor': 'gray', 'color': 'black', 'weight': 1, 'fillOpacity': 0.3}
        
        valor_norm = (valor - vmin) / (vmax - vmin)
        valor_norm = max(0, min(1, valor_norm))
        
        if analisis_tipo == "FERTILIDAD ACTUAL":
            colores = ['#d73027', '#f46d43', '#fdae61', '#fee08b', '#d9ef8b', '#a6d96a', '#66bd63', '#1a9850']
        elif nutriente == "NITRÓGENO":
            colores = ['#00ff00', '#80ff00', '#ffff00', '#ff8000', '#ff0000']
        elif nutriente == "FÓSFORO":
            colores = ['#0000ff', '#4040ff', '#8080ff', '#c0c0ff', '#ffffff']
        else:
            colores = ['#4B0082', '#6A0DAD', '#8A2BE2', '#9370DB', '#D8BFD8']
        
        n_colores = len(colores)
        idx = int(valor_norm * (n_colores - 1))
        idx = min(idx, n_colores - 2)
        color = colores[idx]
        
        return {
            'fillColor': color,
            'color': 'black',
            'weight': 2,
            'fillOpacity': 0.7,
            'opacity': 0.8
        }
    
    folium.GeoJson(
        gdf.__geo_interface__,
        name=f'Análisis {cultivo}',
        style_function=estilo_poligono,
        tooltip=folium.GeoJsonTooltip(
            fields=['id_zona', columna, 'area_ha', 'ndvi', 'materia_organica'],
            aliases=['Zona:', f'{analisis_tipo}:', 'Área (ha):', 'NDVI:', 'Materia Org (%):'],
            localize=True,
            style="background-color: white; border: 1px solid black; border-radius: 3px; padding: 5px;"
        )
    ).add_to(m)
    
    folium.LayerControl().add_to(m)
    
    return m
