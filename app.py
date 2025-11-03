"""
Módulo para generación de mapas interactivos con ESRI
"""

import folium
import json
import os
from folium import plugins
from folium.features import GeoJsonTooltip

class MapaAnalizador:
    def __init__(self):
        # Capas base de ESRI
        self.esri_layers = {
            "Imagen Satelital": "Esri.WorldImagery",
            "Calles": "Esri.WorldStreetMap", 
            "Topográfico": "Esri.WorldTopoMap",
            "Oscuro": "Esri.WorldDarkGray",
            "Terreno": "Esri.WorldTerrain"
        }
        
    def crear_mapa_base(self, centro=[-34.6037, -58.3816], zoom=6):
        """Crea un mapa base con capas de ESRI"""
        
        mapa = folium.Map(
            location=centro,
            zoom_start=zoom,
            tiles=self.esri_layers["Imagen Satelital"],
            attr='Esri'
        )
        
        # Agregar control de capas base
        for nombre, capa in self.esri_layers.items():
            if nombre != "Imagen Satelital":  # Ya está como base
                folium.TileLayer(
                    capa,
                    name=nombre,
                    attr='Esri'
                ).add_to(mapa)
        
        folium.LayerControl().add_to(mapa)
        
        # Agregar plugins útiles
        plugins.Fullscreen().add_to(mapa)
        plugins.MeasureControl().add_to(mapa)
        plugins.LocateControl().add_to(mapa)
        
        return mapa
    
    def agregar_poligono(self, mapa, geojson_data, nombre="Polígono de Análisis"):
        """Agrega un polígono GeoJSON al mapa"""
        
        # Si es un archivo, cargarlo
        if isinstance(geojson_data, str):
            with open(geojson_data, 'r', encoding='utf-8') as f:
                geojson = json.load(f)
        else:
            geojson = geojson_data
            
        # Crear estilo para el polígono
        estilo_poligono = {
            'fillColor': '#3388ff',
            'color': '#3388ff',
            'weight': 3,
            'fillOpacity': 0.2,
            'dashArray': '5, 5'
        }
        
        # Agregar el polígono al mapa
        folium.GeoJson(
            geojson,
            name=nombre,
            style_function=lambda x: estilo_poligono,
            tooltip=folium.GeoJsonTooltip(
                fields=['name', 'area_ha', 'cultivo'],
                aliases=['Nombre:', 'Área (ha):', 'Cultivo:'],
                localize=True
            )
        ).add_to(mapa)
        
        # Ajustar vista al polígono
        mapa.fit_bounds(folium.GeoJson(geojson).get_bounds())
        
        return mapa
    
    def agregar_resultados(self, mapa, resultados_geojson, cultivo):
        """Agrega los resultados del análisis al mapa"""
        
        # Definir colores según el nivel de fertilidad
        def estilo_fertilidad(feature):
            fertilidad = feature['properties'].get('fertilidad', 0)
            
            if fertilidad >= 80:
                color = '#00ff00'  # Verde - Alta
            elif fertilidad >= 60:
                color = '#ffff00'  # Amarillo - Media
            elif fertilidad >= 40:
                color = '#ffa500'  # Naranja - Baja
            else:
                color = '#ff0000'  # Rojo - Muy baja
                
            return {
                'fillColor': color,
                'color': color,
                'weight': 2,
                'fillOpacity': 0.6
            }
        
        # Crear tooltip con información
        tooltip = folium.GeoJsonTooltip(
            fields=['fertilidad', 'nitrogeno', 'fosforo', 'potasio', 'ph', 'materia_organica'],
            aliases=[
                'Fertilidad (%):',
                'Nitrógeno (%):',
                'Fósforo (%):',
                'Potasio (%):', 
                'pH:',
                'Materia Orgánica (%):'
            ],
            localize=True,
            style=("background-color: white; color: #333333; font-family: arial; font-size: 12px; padding: 10px;")
        )
        
        folium.GeoJson(
            resultados_geojson,
            name=f"Resultados {cultivo}",
            style_function=estilo_fertilidad,
            tooltip=tooltip
        ).add_to(mapa)
        
        # Agregar leyenda
        self.agregar_leyenda(mapa, cultivo)
        
        return mapa
    
    def agregar_leyenda(self, mapa, cultivo):
        """Agrega una leyenda al mapa"""
        
        leyenda_html = f'''
        <div style="position: fixed; 
                    bottom: 50px; left: 50px; width: 220px; height: 180px; 
                    background-color: white; border:2px solid grey; z-index:9999; 
                    font-size:12px; padding: 10px; border-radius: 5px;
                    box-shadow: 0 0 10px rgba(0,0,0,0.2);">
            <p style="margin:0 0 8px 0; font-weight:bold; text-align:center;">
                🌱 {cultivo} - Niveles de Fertilidad
            </p>
            <p style="margin:2px 0;"><i style="background:#00ff00; width:12px; height:12px; display:inline-block; margin-right:5px;"></i> Alta (80-100%)</p>
            <p style="margin:2px 0;"><i style="background:#ffff00; width:12px; height:12px; display:inline-block; margin-right:5px;"></i> Media (60-79%)</p>
            <p style="margin:2px 0;"><i style="background:#ffa500; width:12px; height:12px; display:inline-block; margin-right:5px;"></i> Baja (40-59%)</p>
            <p style="margin:2px 0;"><i style="background:#ff0000; width:12px; height:12px; display:inline-block; margin-right:5px;"></i> Muy baja (<40%)</p>
            <hr style="margin:8px 0;">
            <p style="margin:4px 0; font-size:10px; color:#666;">🗺️ Capas ESRI disponibles</p>
        </div>
        '''
        
        mapa.get_root().html.add_child(folium.Element(leyenda_html))
    
    def guardar_mapa(self, mapa, nombre_archivo="analisis_fertilidad.html"):
        """Guarda el mapa como archivo HTML"""
        # Asegurar directorio de resultados
        os.makedirs('resultados', exist_ok=True)
        
        ruta_completa = os.path.join('resultados', nombre_archivo)
        mapa.save(ruta_completa)
        return ruta_completa

def convertir_resultados_a_geojson(resultados, poligono_path):
    """Convierte los resultados del análisis a formato GeoJSON"""
    
    # Cargar el polígono original
    with open(poligono_path, 'r', encoding='utf-8') as f:
        poligono_geojson = json.load(f)
    
    # Agregar propiedades de resultados al GeoJSON
    for feature in poligono_geojson['features']:
        feature['properties'].update(resultados)
    
    return poligono_geojson

def integrar_con_analizador(poligono_path, resultados, cultivo, centro_mapa=None):
    """
    Función principal para integrar con el analizador existente
    
    Args:
        poligono_path (str): Ruta al archivo GeoJSON del polígono
        resultados (dict): Resultados del análisis de fertilidad
        cultivo (str): Tipo de cultivo analizado
        centro_mapa (list): Coordenadas [lat, lon] para centrar el mapa
    """
    
    # Crear instancia del mapa
    analizador_mapa = MapaAnalizador()
    
    # Determinar centro del mapa
    if centro_mapa is None:
        centro_mapa = [-34.6037, -58.3816]  # Buenos Aires por defecto
    
    # Crear mapa base
    mapa = analizador_mapa.crear_mapa_base(centro=centro_mapa)
    
    # Agregar polígono de análisis
    mapa = analizador_mapa.agregar_poligono(mapa, poligono_path)
    
    # Convertir resultados a GeoJSON
    resultados_geojson = convertir_resultados_a_geojson(resultados, poligono_path)
    
    # Agregar resultados al mapa
    mapa = analizador_mapa.agregar_resultados(mapa, resultados_geojson, cultivo)
    
    # Generar nombre de archivo
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nombre_archivo = f"fertilidad_{cultivo.lower()}_{timestamp}.html"
    
    # Guardar mapa
    archivo_html = analizador_mapa.guardar_mapa(mapa, nombre_archivo)
    
    return archivo_html

if __name__ == "__main__":
    print("🌍 Módulo de Mapas ESRI para Analizador de Fertilidad")
    print("💡 Usa: from mapa_analizador import integrar_con_analizador")
