
import streamlit as st
import geopandas as gpd
import pandas as pd
import numpy as np
import tempfile
import os
import zipfile
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.colors import LinearSegmentedColormap
import io
from shapely.geometry import Polygon
import math
import warnings
warnings.filterwarnings('ignore')

# Importar módulos personalizados
from src.data_processor import (
    PARAMETROS_CULTIVOS, ICONOS_CULTIVOS, PALETAS_GEE,
    calcular_superficie, dividir_parcela_en_zonas,
    calcular_indices_satelitales_gee_mejorado, calcular_recomendaciones_npk_gee,
    get_fuente_nitrogeno, get_fertilizante_balanceado
)
from src.map_utils import crear_mapa_interactivo_gee, MAPAS_BASE
from streamlit_folium import folium_static

st.set_page_config(page_title="🌱 Analizador Multi-Cultivo", layout="wide")
st.title("🌱 ANALIZADOR MULTI-CULTIVO - METODOLOGÍA GEE + SENTINEL-2")
st.markdown("---")

# Configurar para restaurar .shx automáticamente
os.environ['SHAPE_RESTORE_SHX'] = 'YES'

# Sidebar
with st.sidebar:
    st.header("⚙️ Configuración")
    
    cultivo = st.selectbox("Cultivo:", 
                          ["TRIGO", "MAÍZ", "SOJA", "SORGO", "GIRASOL"])
    
    analisis_tipo = st.selectbox("Tipo de Análisis:", 
                               ["FERTILIDAD ACTUAL", "RECOMENDACIONES NPK"])
    
    nutriente = st.selectbox("Nutriente:", ["NITRÓGENO", "FÓSFORO", "POTASIO"])
    
    st.subheader("🛰️ Datos Sentinel-2")
    usar_sentinel = st.checkbox("Usar datos Sentinel-2 Harmonizados", value=True)
    fecha_imagen = st.date_input(
        "Fecha de imagen:",
        value=datetime.now() - timedelta(days=30),
        max_value=datetime.now(),
        help="Selecciona la fecha para análisis satelital"
    )
    
    st.subheader("🗺️ Mapa Base")
    mapa_base = st.selectbox(
        "Seleccionar mapa base:",
        list(MAPAS_BASE.keys()),
        index=0
    )
    
    st.subheader("🎯 División de Parcela")
    n_divisiones = st.slider("Número de zonas de manejo:", min_value=16, max_value=48, value=32)
    
    st.subheader("📤 Subir Parcela")
    uploaded_zip = st.file_uploader("Subir ZIP con shapefile de tu parcela", type=['zip'])

# FUNCIÓN PARA CREAR MAPA GEE (Matplotlib - Original)
def crear_mapa_gee(gdf, nutriente, analisis_tipo, cultivo):
    """Crea mapa con la metodología y paletas de Google Earth Engine"""
    try:
        fig, ax = plt.subplots(1, 1, figsize=(14, 10))
        
        # Seleccionar paleta según el análisis
        if analisis_tipo == "FERTILIDAD ACTUAL":
            cmap = LinearSegmentedColormap.from_list('fertilidad_gee', PALETAS_GEE['FERTILIDAD'])
            vmin, vmax = 0, 1
            columna = 'npk_actual'
            titulo_sufijo = 'Índice NPK Actual (0-1)'
        else:
            if nutriente == "NITRÓGENO":
                cmap = LinearSegmentedColormap.from_list('nitrogeno_gee', PALETAS_GEE['NITROGENO'])
                vmin, vmax = (PARAMETROS_CULTIVOS[cultivo]['NITROGENO']['min'] * 0.8, 
                            PARAMETROS_CULTIVOS[cultivo]['NITROGENO']['max'] * 1.2)
            elif nutriente == "FÓSFORO":
                cmap = LinearSegmentedColormap.from_list('fosforo_gee', PALETAS_GEE['FOSFORO'])
                vmin, vmax = (PARAMETROS_CULTIVOS[cultivo]['FOSFORO']['min'] * 0.8, 
                            PARAMETROS_CULTIVOS[cultivo]['FOSFORO']['max'] * 1.2)
            else:
                cmap = LinearSegmentedColormap.from_list('potasio_gee', PALETAS_GEE['POTASIO'])
                vmin, vmax = (PARAMETROS_CULTIVOS[cultivo]['POTASIO']['min'] * 0.8, 
                            PARAMETROS_CULTIVOS[cultivo]['POTASIO']['max'] * 1.2)
            
            columna = 'valor_recomendado'
            titulo_sufijo = f'Recomendación {nutriente} (kg/ha)'
        
        # Plotear cada polígono
        for idx, row in gdf.iterrows():
            valor = row[columna]
            valor_norm = (valor - vmin) / (vmax - vmin)
            valor_norm = max(0, min(1, valor_norm))
            color = cmap(valor_norm)
            
            gdf.iloc[[idx]].plot(ax=ax, color=color, edgecolor='black', linewidth=1.5)
            
            # Etiqueta con valor
            centroid = row.geometry.centroid
            ax.annotate(f"Z{row['id_zona']}\n{valor:.1f}", (centroid.x, centroid.y), 
                       xytext=(5, 5), textcoords="offset points", 
                       fontsize=8, color='black', weight='bold',
                       bbox=dict(boxstyle="round,pad=0.3", facecolor='white', alpha=0.9))
        
        # Configuración del mapa
        ax.set_title(f'{ICONOS_CULTIVOS[cultivo]} ANÁLISIS GEE - {cultivo}\n'
                    f'{analisis_tipo} - {titulo_sufijo}\n'
                    f'Metodología Google Earth Engine', 
                    fontsize=16, fontweight='bold', pad=20)
        
        ax.set_xlabel('Longitud')
        ax.set_ylabel('Latitud')
        ax.grid(True, alpha=0.3)
        
        # Barra de colores
        sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(vmin=vmin, vmax=vmax))
        sm.set_array([])
        cbar = plt.colorbar(sm, ax=ax, shrink=0.8)
        cbar.set_label(titulo_sufijo, fontsize=12, fontweight='bold')
        
        plt.tight_layout()
        
        # Convertir a imagen
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        buf.seek(0)
        plt.close()
        
        return buf
        
    except Exception as e:
        st.error(f"❌ Error creando mapa GEE: {str(e)}")
        return None

# FUNCIÓN PRINCIPAL DE ANÁLISIS GEE MEJORADA
def analisis_gee_completo_mejorado(gdf, nutriente, analisis_tipo, n_divisiones, cultivo, usar_sentinel, fecha_imagen, mapa_base):
    try:
        st.header(f"{ICONOS_CULTIVOS[cultivo]} ANÁLISIS {cultivo} - METODOLOGÍA GEE + SENTINEL-2")
        
        # Información de fuentes de datos
        if usar_sentinel:
            st.success(f"🛰️ Usando datos Sentinel-2 Harmonizados (L2A - 10m) - Fecha: {fecha_imagen}")
        else:
            st.info("📊 Usando datos simulados")
        
        # PASO 1: DIVIDIR PARCELA
        st.subheader("📐 DIVIDIENDO PARCELA EN ZONAS DE MANEJO")
        with st.spinner("Dividiendo parcela..."):
            gdf_dividido = dividir_parcela_en_zonas(gdf, n_divisiones)
        
        st.success(f"✅ Parcela dividida en {len(gdf_dividido)} zonas")
        
        # Calcular áreas
        areas_ha = calcular_superficie(gdf_dividido)
        area_total = areas_ha.sum()
        
        # PASO 2: CALCULAR ÍNDICES GEE MEJORADOS CON SENTINEL-2
        st.subheader("🛰️ CALCULANDO ÍNDICES SATELITALES GEE + SENTINEL-2")
        with st.spinner(f"Ejecutando algoritmos GEE con Sentinel-2 para {cultivo}..."):
            indices_gee = calcular_indices_satelitales_gee_mejorado(
                gdf_dividido, cultivo, usar_sentinel, fecha_imagen
            )
        
        # Crear dataframe con resultados
        gdf_analizado = gdf_dividido.copy()
        gdf_analizado['area_ha'] = areas_ha
        
        # Añadir índices GEE
        for idx, indice in enumerate(indices_gee):
            for key, value in indice.items():
                gdf_analizado.loc[gdf_analizado.index[idx], key] = value
        
        # PASO 3: CALCULAR RECOMENDACIONES SI ES NECESARIO
        if analisis_tipo == "RECOMENDACIONES NPK":
            with st.spinner("Calculando recomendaciones NPK..."):
                recomendaciones = calcular_recomendaciones_npk_gee(indices_gee, nutriente, cultivo)
                gdf_analizado['valor_recomendado'] = recomendaciones
                columna_valor = 'valor_recomendado'
        else:
            columna_valor = 'npk_actual'
        
        # PASO 4: CATEGORIZAR PARA RECOMENDACIONES ESPECÍFICAS POR CULTIVO
        def categorizar_gee(valor, nutriente, analisis_tipo, cultivo):
            params = PARAMETROS_CULTIVOS[cultivo]
            
            if analisis_tipo == "FERTILIDAD ACTUAL":
                if valor < 0.3: return "MUY BAJA"
                elif valor < 0.5: return "BAJA"
                elif valor < 0.6: return "MEDIA"
                elif valor < 0.7: return "BUENA"
                else: return "ÓPTIMA"
            else:
                if nutriente == "NITRÓGENO":
                    rango = params['NITROGENO']['max'] - params['NITROGENO']['min']
                    if valor < params['NITROGENO']['min'] + 0.2 * rango: return "MUY BAJO"
                    elif valor < params['NITROGENO']['min'] + 0.4 * rango: return "BAJO"
                    elif valor < params['NITROGENO']['min'] + 0.6 * rango: return "MEDIO"
                    elif valor < params['NITROGENO']['min'] + 0.8 * rango: return "ALTO"
                    else: return "MUY ALTO"
                elif nutriente == "FÓSFORO":
                    rango = params['FOSFORO']['max'] - params['FOSFORO']['min']
                    if valor < params['FOSFORO']['min'] + 0.2 * rango: return "MUY BAJO"
                    elif valor < params['FOSFORO']['min'] + 0.4 * rango: return "BAJO"
                    elif valor < params['FOSFORO']['min'] + 0.6 * rango: return "MEDIO"
                    elif valor < params['FOSFORO']['min'] + 0.8 * rango: return "ALTO"
                    else: return "MUY ALTO"
                else:
                    rango = params['POTASIO']['max'] - params['POTASIO']['min']
                    if valor < params['POTASIO']['min'] + 0.2 * rango: return "MUY BAJO"
                    elif valor < params['POTASIO']['min'] + 0.4 * rango: return "BAJO"
                    elif valor < params['POTASIO']['min'] + 0.6 * rango: return "MEDIO"
                    elif valor < params['POTASIO']['min'] + 0.8 * rango: return "ALTO"
                    else: return "MUY ALTO"
        
        gdf_analizado['categoria'] = [
            categorizar_gee(row[columna_valor], nutriente, analisis_tipo, cultivo) 
            for idx, row in gdf_analizado.iterrows()
        ]
        
        # PASO 5: MOSTRAR RESULTADOS
        st.subheader("📊 RESULTADOS DEL ANÁLISIS GEE")
        
        # Estadísticas principales
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Zonas Analizadas", len(gdf_analizado))
        with col2:
            st.metric("Área Total", f"{area_total:.1f} ha")
        with col3:
            if analisis_tipo == "FERTILIDAD ACTUAL":
                valor_prom = gdf_analizado['npk_actual'].mean()
                st.metric("Índice NPK Promedio", f"{valor_prom:.3f}")
            else:
                valor_prom = gdf_analizado['valor_recomendado'].mean()
                st.metric(f"{nutriente} Promedio", f"{valor_prom:.1f} kg/ha")
        with col4:
            coef_var = (gdf_analizado[columna_valor].std() / gdf_analizado[columna_valor].mean() * 100)
            st.metric("Coef. Variación", f"{coef_var:.1f}%")
        
        # VISUALIZACIÓN CON PESTAÑAS
        st.subheader("🗺️ VISUALIZACIÓN DE RESULTADOS")
        
        # Crear pestañas para diferentes visualizaciones
        tab1, tab2, tab3 = st.tabs([
            "🗺️ Mapa Interactivo ESRI", 
            "📊 Mapa Tradicional", 
            "📋 Tabla de Resultados"
        ])
        
        with tab1:
            st.subheader("🗺️ MAPA INTERACTIVO CON ESRI")
            with st.spinner("Generando mapa interactivo..."):
                mapa_interactivo = crear_mapa_interactivo_gee(
                    gdf_analizado, nutriente, analisis_tipo, cultivo, mapa_base
                )
                folium_static(mapa_interactivo, width=900, height=600)
            
            st.info(f"**Fuente de datos:** {indices_gee[0]['fuente_datos']} | "
                   f"**Resolución:** {indices_gee[0]['resolucion']} | "
                   f"**Procesamiento:** {indices_gee[0]['procesamiento']}")
        
        with tab2:
            st.subheader("📊 MAPA TRADICIONAL GEE")
            mapa_buffer = crear_mapa_gee(gdf_analizado, nutriente, analisis_tipo, cultivo)
            if mapa_buffer:
                st.image(mapa_buffer, use_container_width=True)
                
                st.download_button(
                    "📥 Descargar Mapa GEE",
                    mapa_buffer,
                    f"mapa_gee_{cultivo}_{analisis_tipo.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M')}.png",
                    "image/png"
                )
        
        with tab3:
            st.subheader("📋 TABLA DE ÍNDICES GEE POR ZONA")
            
            columnas_indices = ['id_zona', 'npk_actual', 'materia_organica', 'ndvi', 'ndre', 'humedad_suelo', 'categoria']
            if analisis_tipo == "RECOMENDACIONES NPK":
                columnas_indices.insert(2, 'valor_recomendado')
            
            tabla_indices = gdf_analizado[columnas_indices].copy()
            tabla_indices.columns = ['Zona', 'NPK Actual'] + (['Recomendación'] if analisis_tipo == "RECOMENDACIONES NPK" else []) + [
                'Materia Org (%)', 'NDVI', 'NDRE', 'Humedad', 'Categoría'
            ]
            
            st.dataframe(tabla_indices, use_container_width=True)
        
        # RECOMENDACIONES ESPECÍFICAS POR CULTIVO
        st.subheader("💡 RECOMENDACIONES ESPECÍFICAS GEE")
        
        categorias = gdf_analizado['categoria'].unique()
        for cat in sorted(categorias):
            subset = gdf_analizado[gdf_analizado['categoria'] == cat]
            area_cat = subset['area_ha'].sum()
            
            with st.expander(f"🎯 **{cat}** - {area_cat:.1f} ha ({(area_cat/area_total*100):.1f}% del área)"):
                
                if analisis_tipo == "FERTILIDAD ACTUAL":
                    if cat in ["MUY BAJA", "BAJA"]:
                        st.markdown("**🚨 ESTRATEGIA: FERTILIZACIÓN CORRECTIVA**")
                        st.markdown("- Aplicar dosis completas de NPK")
                        st.markdown("- Incorporar materia orgánica")
                        st.markdown("- Monitorear cada 3 meses")
                    elif cat == "MEDIA":
                        st.markdown("**✅ ESTRATEGIA: MANTENIMIENTO BALANCEADO**")
                        st.markdown("- Seguir programa estándar de fertilización")
                        st.markdown("- Monitorear cada 6 meses")
                    else:
                        st.markdown("**🌟 ESTRATEGIA: MANTENIMIENTO CONSERVADOR**")
                        st.markdown("- Reducir dosis de fertilizantes")
                        st.markdown("- Enfoque en sostenibilidad")
                
                else:
                    # Recomendaciones NPK específicas por cultivo
                    if cat in ["MUY BAJO", "BAJO"]:
                        st.markdown("**🚨 APLICACIÓN ALTA** - Dosis correctiva urgente")
                        if nutriente == "NITRÓGENO":
                            st.markdown(f"- **Fuentes:** Urea (46% N) o {get_fuente_nitrogeno(cultivo)}")
                            st.markdown("- **Aplicación:** 2-3 dosis fraccionadas")
                        elif nutriente == "FÓSFORO":
                            st.markdown("- **Fuentes:** Superfosfato triple (46% P₂O₅) o Fosfato diamónico")
                            st.markdown("- **Aplicación:** Incorporar al suelo")
                        else:
                            st.markdown("- **Fuentes:** Cloruro de potasio (60% K₂O) o Sulfato de potasio")
                            st.markdown("- **Aplicación:** 2-3 aplicaciones")
                    
                    elif cat == "MEDIO":
                        st.markdown("**✅ APLICACIÓN MEDIA** - Mantenimiento balanceado")
                        st.markdown(f"- **Fuentes:** {get_fertilizante_balanceado(cultivo)}")
                        st.markdown("- **Aplicación:** Programa estándar")
                    
                    else:
                        st.markdown("**🌟 APLICACIÓN BAJA** - Reducción de dosis")
                        st.markdown("- **Fuentes:** Fertilizantes bajos en el nutriente")
                        st.markdown("- **Aplicación:** Solo mantenimiento")
                
                # Mostrar estadísticas de la categoría
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Zonas", len(subset))
                with col2:
                    if analisis_tipo == "FERTILIDAD ACTUAL":
                        st.metric("NPK Prom", f"{subset['npk_actual'].mean():.3f}")
                    else:
                        st.metric("Valor Prom", f"{subset['valor_recomendado'].mean():.1f}")
                with col3:
                    st.metric("Área", f"{area_cat:.1f} ha")
        
        # DESCARGA DE RESULTADOS
        st.subheader("📥 DESCARGAR RESULTADOS COMPLETOS")
        
        csv = gdf_analizado.to_csv(index=False)
        st.download_button(
            "📋 Descargar CSV con Análisis GEE",
            csv,
            f"analisis_gee_{cultivo}_{analisis_tipo.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            "text/csv"
        )
        
        # INFORMACIÓN TÉCNICA GEE
        with st.expander("🔍 VER METODOLOGÍA GEE DETALLADA"):
            st.markdown(f"""
            **🌐 METODOLOGÍA GOOGLE EARTH ENGINE + SENTINEL-2 - {cultivo}**
            
            **🎯 PARÁMETROS ÓPTIMOS {cultivo}:**
            - **Materia Orgánica:** {PARAMETROS_CULTIVOS[cultivo]['MATERIA_ORGANICA_OPTIMA']}%
            - **Humedad Suelo:** {PARAMETROS_CULTIVOS[cultivo]['HUMEDAD_OPTIMA']}
            - **NDVI Óptimo:** {PARAMETROS_CULTIVOS[cultivo]['NDVI_OPTIMO']}
            - **NDRE Óptimo:** {PARAMETROS_CULTIVOS[cultivo]['NDRE_OPTIMO']}
            
            **🎯 RANGOS NPK RECOMENDADOS:**
            - **Nitrógeno:** {PARAMETROS_CULTIVOS[cultivo]['NITROGENO']['min']}-{PARAMETROS_CULTIVOS[cultivo]['NITROGENO']['max']} kg/ha
            - **Fósforo:** {PARAMETROS_CULTIVOS[cultivo]['FOSFORO']['min']}-{PARAMETROS_CULTIVOS[cultivo]['FOSFORO']['max']} kg/ha  
            - **Potasio:** {PARAMETROS_CULTIVOS[cultivo]['POTASIO']['min']}-{PARAMETROS_CULTIVOS[cultivo]['POTASIO']['max']} kg/ha
            
            **🛰️ DATOS SENTINEL-2 HARMONIZADOS UTILIZADOS:**
            - **Resolución:** 10m
            - **Procesamiento:** L2A (Corrección Atmosférica)
            - **Bandas Utilizadas:** B2, B4, B5, B8, B11
            - **Índices Calculados:** NDVI, NDRE, Materia Orgánica, Humedad
            """)
        
        return True
        
    except Exception as e:
        st.error(f"❌ Error en análisis GEE: {str(e)}")
        import traceback
        st.error(f"Detalle: {traceback.format_exc()}")
        return False

# INTERFAZ PRINCIPAL
if uploaded_zip:
    with st.spinner("Cargando parcela..."):
        try:
            with tempfile.TemporaryDirectory() as tmp_dir:
                with zipfile.ZipFile(uploaded_zip, 'r') as zip_ref:
                    zip_ref.extractall(tmp_dir)
                
                shp_files = [f for f in os.listdir(tmp_dir) if f.endswith('.shp')]
                if shp_files:
                    shp_path = os.path.join(tmp_dir, shp_files[0])
                    gdf = gpd.read_file(shp_path)
                    
                    st.success(f"✅ **Parcela cargada:** {len(gdf)} polígono(s)")
                    
                    # Información de la parcela
                    area_total = calcular_superficie(gdf).sum()
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.write("**📊 INFORMACIÓN DE LA PARCELA:**")
                        st.write(f"- Polígonos: {len(gdf)}")
                        st.write(f"- Área total: {area_total:.1f} ha")
                        st.write(f"- CRS: {gdf.crs}")
                    
                    with col2:
                        st.write("**🎯 CONFIGURACIÓN GEE:**")
                        st.write(f"- Cultivo: {ICONOS_CULTIVOS[cultivo]} {cultivo}")
                        st.write(f"- Análisis: {analisis_tipo}")
                        st.write(f"- Nutriente: {nutriente}")
                        st.write(f"- Zonas: {n_divisiones}")
                    
                    with col3:
                        st.write("**🛰️ DATOS SATELITALES:**")
                        fuente = "Sentinel-2 Harmonized" if usar_sentinel else "Simulado"
                        st.write(f"- Fuente: {fuente}")
                        if usar_sentinel:
                            st.write(f"- Fecha: {fecha_imagen}")
                            st.write(f"- Resolución: 10m")
                    
                    # EJECUTAR ANÁLISIS GEE MEJORADO
                    if st.button("🚀 EJECUTAR ANÁLISIS GEE + SENTINEL-2", type="primary"):
                        analisis_gee_completo_mejorado(
                            gdf, nutriente, analisis_tipo, n_divisiones, cultivo, 
                            usar_sentinel, fecha_imagen, mapa_base
                        )
                        
        except Exception as e:
            st.error(f"Error cargando shapefile: {str(e)}")

else:
    st.info("📁 Sube el ZIP de tu parcela para comenzar el análisis")
    
    # INFORMACIÓN INICIAL MEJORADA
    with st.expander("ℹ️ INFORMACIÓN SOBRE LA METODOLOGÍA GEE + SENTINEL-2"):
        st.markdown("""
        **🌱 SISTEMA DE ANÁLISIS MULTI-CULTIVO (GEE + SENTINEL-2)**
        
        **🛰️ NUEVAS CARACTERÍSTICAS:**
        - **Sentinel-2 Harmonizado:** Datos reales de satélite
        - **Resolución 10m:** Alta precisión espacial
        - **Procesamiento L2A:** Corrección atmosférica incluida
        - **Mapas Base ESRI:** Visualización profesional
        - **Análisis en Tiempo Real:** Datos actualizados
        
        **📊 CULTIVOS SOPORTADOS:**
        - **🌾 TRIGO:** Cereal de clima templado
        - **🌽 MAÍZ:** Cereal de alta demanda nutricional  
        - **🫘 SOJA:** Leguminosa fijadora de nitrógeno
        - **🌾 SORGO:** Cereal resistente a sequía
        - **🌻 GIRASOL:** Oleaginosa de profundas raíces
        
        **🚀 FUNCIONALIDADES:**
        - **🌱 Fertilidad Actual:** Estado NPK del suelo usando índices satelitales
        - **💊 Recomendaciones NPK:** Dosis específicas por cultivo basadas en GEE
        - **🛰️ Metodología GEE:** Algoritmos científicos de Google Earth Engine
        - **🎯 Agricultura Precisión:** Mapas de prescripción por zonas
        
        **🔬 METODOLOGÍA CIENTÍFICA:**
        - Análisis basado en imágenes Sentinel-2 Harmonizadas
        - Parámetros específicos para cada cultivo
        - Cálculo de índices de vegetación y suelo
        - Recomendaciones validadas científicamente
        """)
