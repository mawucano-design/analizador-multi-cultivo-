import streamlit as st
import pandas as pd
import numpy as np
import tempfile
import os
import zipfile
import json
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.colors import LinearSegmentedColormap
import io
from PIL import Image
import warnings
warnings.filterwarnings('ignore')

st.set_page_config(page_title="🌱 Analizador Multi-Cultivo", layout="wide")
st.title("🌱 ANALIZADOR MULTI-CULTIVO - METODOLOGÍA GEE")
st.markdown("---")

# PARÁMETROS GEE POR CULTIVO
PARAMETROS_CULTIVOS = {
    'TRIGO': {
        'NITROGENO': {'min': 120, 'max': 180},
        'FOSFORO': {'min': 40, 'max': 60},
        'POTASIO': {'min': 80, 'max': 120},
        'MATERIA_ORGANICA_OPTIMA': 3.5,
        'HUMEDAD_OPTIMA': 0.25,
        'NDVI_OPTIMO': 0.7,
        'NDRE_OPTIMO': 0.4
    },
    'MAÍZ': {
        'NITROGENO': {'min': 150, 'max': 220},
        'FOSFORO': {'min': 50, 'max': 70},
        'POTASIO': {'min': 100, 'max': 140},
        'MATERIA_ORGANICA_OPTIMA': 4.0,
        'HUMEDAD_OPTIMA': 0.3,
        'NDVI_OPTIMO': 0.75,
        'NDRE_OPTIMO': 0.45
    },
    'SOJA': {
        'NITROGENO': {'min': 80, 'max': 120},
        'FOSFORO': {'min': 35, 'max': 50},
        'POTASIO': {'min': 90, 'max': 130},
        'MATERIA_ORGANICA_OPTIMA': 3.8,
        'HUMEDAD_OPTIMA': 0.28,
        'NDVI_OPTIMO': 0.65,
        'NDRE_OPTIMO': 0.35
    },
    'SORGO': {
        'NITROGENO': {'min': 100, 'max': 150},
        'FOSFORO': {'min': 30, 'max': 45},
        'POTASIO': {'min': 70, 'max': 100},
        'MATERIA_ORGANICA_OPTIMA': 3.0,
        'HUMEDAD_OPTIMA': 0.22,
        'NDVI_OPTIMO': 0.6,
        'NDRE_OPTIMO': 0.3
    },
    'GIRASOL': {
        'NITROGENO': {'min': 90, 'max': 130},
        'FOSFORO': {'min': 25, 'max': 40},
        'POTASIO': {'min': 80, 'max': 110},
        'MATERIA_ORGANICA_OPTIMA': 3.2,
        'HUMEDAD_OPTIMA': 0.26,
        'NDVI_OPTIMO': 0.55,
        'NDRE_OPTIMO': 0.25
    }
}

# ICONOS POR CULTIVO
ICONOS_CULTIVOS = {
    'TRIGO': '🌾',
    'MAÍZ': '🌽', 
    'SOJA': '🫘',
    'SORGO': '🌾',
    'GIRASOL': '🌻'
}

# PALETAS GEE
PALETAS_GEE = {
    'FERTILIDAD': ['#d73027', '#f46d43', '#fdae61', '#fee08b', '#d9ef8b', '#a6d96a', '#66bd63', '#1a9850'],
    'NITROGENO': ['#00ff00', '#80ff00', '#ffff00', '#ff8000', '#ff0000'],
    'FOSFORO': ['#0000ff', '#4040ff', '#8080ff', '#c0c0ff', '#ffffff'],
    'POTASIO': ['#4B0082', '#6A0DAD', '#8A2BE2', '#9370DB', '#D8BFD8']
}

# Sidebar
with st.sidebar:
    st.header("⚙️ Configuración")
    
    cultivo = st.selectbox("Cultivo:", ["TRIGO", "MAÍZ", "SOJA", "SORGO", "GIRASOL"])
    
    analisis_tipo = st.selectbox("Tipo de Análisis:", ["FERTILIDAD ACTUAL", "RECOMENDACIONES NPK"])
    
    nutriente = st.selectbox("Nutriente:", ["NITRÓGENO", "FÓSFORO", "POTASIO"])
    
    st.subheader("🛰️ Datos Satelitales")
    usar_sentinel = st.checkbox("Simular datos Sentinel-2", value=True)
    
    st.subheader("🎯 Configuración de Parcela")
    n_zonas = st.slider("Número de zonas:", min_value=16, max_value=48, value=32)
    area_total = st.number_input("Área total (hectáreas):", min_value=1.0, max_value=1000.0, value=50.0)
    
    st.subheader("📊 Datos de Entrada")
    tipo_parcela = st.selectbox("Tipo de parcela:", ["Rectangular", "Cuadrada", "Irregular"])
    calidad_suelo = st.select_slider("Calidad general del suelo:", 
                                   options=["Muy Baja", "Baja", "Media", "Buena", "Excelente"],
                                   value="Media")

# SIMULACIÓN DE GEOMETRÍAS SIMPLES
def generar_zonas_parcela(n_zonas, tipo_parcela, area_total):
    """Genera datos simulados de zonas de parcela"""
    zonas = []
    
    # Calcular área por zona
    area_por_zona = area_total / n_zonas
    
    for i in range(n_zonas):
        # Simular variación espacial
        x_pos = (i % int(np.sqrt(n_zonas))) / np.sqrt(n_zonas)
        y_pos = (i // int(np.sqrt(n_zonas))) / np.sqrt(n_zonas)
        
        # Base de calidad según posición
        calidad_base = 0.5 + (x_pos * 0.3) + (y_pos * 0.2)
        
        # Ajustar según tipo de parcela
        if tipo_parcela == "Rectangular":
            variacion = 0.1
        elif tipo_parcela == "Cuadrada":
            variacion = 0.05
        else:  # Irregular
            variacion = 0.15
        
        # Ajustar según calidad del suelo
        calidad_map = {"Muy Baja": 0.2, "Baja": 0.4, "Media": 0.6, "Buena": 0.8, "Excelente": 1.0}
        factor_calidad = calidad_map[calidad_suelo]
        
        zonas.append({
            'id_zona': i + 1,
            'area_ha': area_por_zona * (0.8 + np.random.random() * 0.4),  # Variación del 80-120%
            'x_pos': x_pos,
            'y_pos': y_pos,
            'calidad_base': calidad_base,
            'factor_calidad': factor_calidad,
            'variacion': variacion
        })
    
    return zonas

# SIMULACIÓN DE DATOS SENTINEL-2
def simular_datos_sentinel2(zona, cultivo, usar_sentinel=True):
    """Simula datos de Sentinel-2 Harmonizados"""
    params = PARAMETROS_CULTIVOS[cultivo]
    
    if usar_sentinel:
        # Simulación más realista con Sentinel-2
        base_ndvi = params['NDVI_OPTIMO'] * 0.7
        variacion_ndvi = zona['calidad_base'] * zona['factor_calidad'] * 0.3
        ruido = np.random.normal(0, zona['variacion'] * 0.1)
        
        ndvi = base_ndvi + variacion_ndvi + ruido
        ndvi = max(0.1, min(0.9, ndvi))
        
        ndre = ndvi * 0.8 + np.random.normal(0, 0.05)
        ndre = max(0.05, min(0.7, ndre))
        
        fuente = "Sentinel-2 Simulado"
    else:
        # Simulación tradicional
        ndvi = 0.5 + (zona['calidad_base'] - 0.5) * 0.4
        ndre = ndvi * 0.7
        fuente = "Tradicional"
    
    # Calcular otros parámetros basados en NDVI y calidad
    materia_organica = params['MATERIA_ORGANICA_OPTIMA'] * (0.6 + ndvi * 0.3 + zona['factor_calidad'] * 0.1)
    materia_organica = max(0.5, min(8.0, materia_organica))
    
    humedad_suelo = params['HUMEDAD_OPTIMA'] * (0.7 + ndvi * 0.2 + zona['factor_calidad'] * 0.1)
    humedad_suelo = max(0.1, min(0.8, humedad_suelo))
    
    # Índice NPK actual
    npk_actual = (ndvi * 0.4) + (ndre * 0.3) + ((materia_organica / 8) * 0.2) + (humedad_suelo * 0.1)
    npk_actual = max(0, min(1, npk_actual))
    
    return {
        'ndvi': round(ndvi, 3),
        'ndre': round(ndre, 3),
        'materia_organica': round(materia_organica, 2),
        'humedad_suelo': round(humedad_suelo, 3),
        'npk_actual': round(npk_actual, 3),
        'fuente_datos': fuente
    }

# CÁLCULO DE RECOMENDACIONES NPK
def calcular_recomendaciones_npk(indices, nutriente, cultivo):
    recomendaciones = []
    params = PARAMETROS_CULTIVOS[cultivo]
    
    for idx in indices:
        ndre = idx['ndre']
        materia_organica = idx['materia_organica']
        humedad_suelo = idx['humedad_suelo']
        ndvi = idx['ndvi']
        
        if nutriente == "NITRÓGENO":
            factor_n = ((1 - ndre) * 0.6 + (1 - ndvi) * 0.4)
            n_recomendado = (factor_n * 
                           (params['NITROGENO']['max'] - params['NITROGENO']['min']) + 
                           params['NITROGENO']['min'])
            n_recomendado = max(params['NITROGENO']['min'] * 0.8, 
                              min(params['NITROGENO']['max'] * 1.2, n_recomendado))
            recomendaciones.append(round(n_recomendado, 1))
            
        elif nutriente == "FÓSFORO":
            factor_p = ((1 - (materia_organica / 8)) * 0.7 + (1 - humedad_suelo) * 0.3)
            p_recomendado = (factor_p * 
                           (params['FOSFORO']['max'] - params['FOSFORO']['min']) + 
                           params['FOSFORO']['min'])
            p_recomendado = max(params['FOSFORO']['min'] * 0.8, 
                              min(params['FOSFORO']['max'] * 1.2, p_recomendado))
            recomendaciones.append(round(p_recomendado, 1))
            
        else:  # POTASIO
            factor_k = ((1 - ndre) * 0.4 + (1 - humedad_suelo) * 0.4 + (1 - (materia_organica / 8)) * 0.2)
            k_recomendado = (factor_k * 
                           (params['POTASIO']['max'] - params['POTASIO']['min']) + 
                           params['POTASIO']['min'])
            k_recomendado = max(params['POTASIO']['min'] * 0.8, 
                              min(params['POTASIO']['max'] * 1.2, k_recomendado))
            recomendaciones.append(round(k_recomendado, 1))
    
    return recomendaciones

# CREAR MAPA VISUAL
def crear_mapa_visual(zonas_con_datos, nutriente, analisis_tipo, cultivo):
    try:
        fig, ax = plt.subplots(1, 1, figsize=(12, 8))
        
        # Determinar valores y colores
        if analisis_tipo == "FERTILIDAD ACTUAL":
            valores = [z['npk_actual'] for z in zonas_con_datos]
            cmap = LinearSegmentedColormap.from_list('fertilidad_gee', PALETAS_GEE['FERTILIDAD'])
            vmin, vmax = 0, 1
            titulo = 'Índice NPK Actual (0-1)'
        else:
            valores = [z['valor_recomendado'] for z in zonas_con_datos]
            if nutriente == "NITRÓGENO":
                cmap = LinearSegmentedColormap.from_list('nitrogeno_gee', PALETAS_GEE['NITROGENO'])
                params = PARAMETROS_CULTIVOS[cultivo]
                vmin, vmax = params['NITROGENO']['min'] * 0.8, params['NITROGENO']['max'] * 1.2
                titulo = f'Recomendación {nutriente} (kg/ha)'
            elif nutriente == "FÓSFORO":
                cmap = LinearSegmentedColormap.from_list('fosforo_gee', PALETAS_GEE['FOSFORO'])
                params = PARAMETROS_CULTIVOS[cultivo]
                vmin, vmax = params['FOSFORO']['min'] * 0.8, params['FOSFORO']['max'] * 1.2
                titulo = f'Recomendación {nutriente} (kg/ha)'
            else:
                cmap = LinearSegmentedColormap.from_list('potasio_gee', PALETAS_GEE['POTASIO'])
                params = PARAMETROS_CULTIVOS[cultivo]
                vmin, vmax = params['POTASIO']['min'] * 0.8, params['POTASIO']['max'] * 1.2
                titulo = f'Recomendación {nutriente} (kg/ha)'
        
        # Crear visualización de cuadrícula
        n_cols = int(np.sqrt(len(zonas_con_datos)))
        n_rows = int(np.ceil(len(zonas_con_datos) / n_cols))
        
        for i, zona in enumerate(zonas_con_datos):
            row = i // n_cols
            col = i % n_cols
            
            valor = valores[i]
            valor_norm = (valor - vmin) / (vmax - vmin)
            valor_norm = max(0, min(1, valor_norm))
            color = cmap(valor_norm)
            
            # Dibujar rectángulo para la zona
            rect = plt.Rectangle((col, row), 0.8, 0.8, facecolor=color, edgecolor='black', linewidth=1)
            ax.add_patch(rect)
            
            # Etiqueta con valor
            ax.text(col + 0.4, row + 0.4, f"Z{zona['id_zona']}\n{valor:.1f}", 
                   ha='center', va='center', fontsize=8, weight='bold',
                   bbox=dict(boxstyle="round,pad=0.2", facecolor='white', alpha=0.8))
        
        ax.set_xlim(0, n_cols)
        ax.set_ylim(0, n_rows)
        ax.set_aspect('equal')
        ax.set_title(f'{ICONOS_CULTIVOS[cultivo]} ANÁLISIS GEE - {cultivo}\n{analisis_tipo}', 
                    fontsize=14, fontweight='bold', pad=15)
        ax.set_xlabel('Columnas')
        ax.set_ylabel('Filas')
        ax.grid(True, alpha=0.3)
        
        # Barra de colores
        sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(vmin=vmin, vmax=vmax))
        sm.set_array([])
        cbar = plt.colorbar(sm, ax=ax, shrink=0.8)
        cbar.set_label(titulo, fontsize=10, fontweight='bold')
        
        plt.tight_layout()
        
        # Convertir a imagen
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=120, bbox_inches='tight')
        buf.seek(0)
        plt.close()
        
        return buf
        
    except Exception as e:
        st.error(f"❌ Error creando mapa: {str(e)}")
        return None

# CATEGORIZACIÓN
def categorizar_valor(valor, nutriente, analisis_tipo, cultivo):
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

# FUNCIÓN PRINCIPAL DE ANÁLISIS
def ejecutar_analisis(cultivo, analisis_tipo, nutriente, n_zonas, area_total, tipo_parcela, calidad_suelo, usar_sentinel):
    try:
        st.header(f"{ICONOS_CULTIVOS[cultivo]} ANÁLISIS {cultivo} - METODOLOGÍA GEE")
        
        if usar_sentinel:
            st.success("🛰️ Usando simulación de datos Sentinel-2 Harmonizados")
        else:
            st.info("📊 Usando datos simulados tradicionales")
        
        # GENERAR ZONAS
        st.subheader("📐 GENERANDO ZONAS DE MANEJO")
        with st.spinner("Generando zonas..."):
            zonas = generar_zonas_parcela(n_zonas, tipo_parcela, area_total)
        
        st.success(f"✅ {len(zonas)} zonas generadas")
        
        # CALCULAR ÍNDICES
        st.subheader("🛰️ CALCULANDO ÍNDICES SATELITALES")
        with st.spinner("Calculando índices..."):
            zonas_con_indices = []
            for zona in zonas:
                indices = simular_datos_sentinel2(zona, cultivo, usar_sentinel)
                zona.update(indices)
                zonas_con_indices.append(zona)
        
        # CALCULAR RECOMENDACIONES
        if analisis_tipo == "RECOMENDACIONES NPK":
            with st.spinner("Calculando recomendaciones NPK..."):
                indices_para_recomendacion = [{
                    'ndre': z['ndre'],
                    'materia_organica': z['materia_organica'],
                    'humedad_suelo': z['humedad_suelo'],
                    'ndvi': z['ndvi']
                } for z in zonas_con_indices]
                
                recomendaciones = calcular_recomendaciones_npk(indices_para_recomendacion, nutriente, cultivo)
                
                for i, zona in enumerate(zonas_con_indices):
                    zona['valor_recomendado'] = recomendaciones[i]
                    columna_valor = 'valor_recomendado'
        else:
            columna_valor = 'npk_actual'
        
        # CATEGORIZAR
        for zona in zonas_con_indices:
            valor = zona[columna_valor]
            zona['categoria'] = categorizar_valor(valor, nutriente, analisis_tipo, cultivo)
        
        # CALCULAR ESTADÍSTICAS
        area_total_real = sum(z['area_ha'] for z in zonas_con_indices)
        if analisis_tipo == "FERTILIDAD ACTUAL":
            valor_promedio = np.mean([z['npk_actual'] for z in zonas_con_indices])
        else:
            valor_promedio = np.mean([z['valor_recomendado'] for z in zonas_con_indices])
        
        # MOSTRAR RESULTADOS
        st.subheader("📊 RESULTADOS DEL ANÁLISIS")
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Zonas Analizadas", len(zonas_con_indices))
        with col2:
            st.metric("Área Total", f"{area_total_real:.1f} ha")
        with col3:
            if analisis_tipo == "FERTILIDAD ACTUAL":
                st.metric("Índice NPK Promedio", f"{valor_promedio:.3f}")
            else:
                st.metric(f"{nutriente} Promedio", f"{valor_promedio:.1f} kg/ha")
        with col4:
            valores = [z[columna_valor] for z in zonas_con_indices]
            coef_var = (np.std(valores) / np.mean(valores) * 100) if np.mean(valores) > 0 else 0
            st.metric("Coef. Variación", f"{coef_var:.1f}%")
        
        # MAPA VISUAL
        st.subheader("🗺️ MAPA DE RESULTADOS")
        mapa_buffer = crear_mapa_visual(zonas_con_indices, nutriente, analisis_tipo, cultivo)
        if mapa_buffer:
            st.image(mapa_buffer, use_container_width=True)
            
            st.download_button(
                "📥 Descargar Mapa",
                mapa_buffer,
                f"mapa_gee_{cultivo}_{analisis_tipo.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M')}.png",
                "image/png"
            )
        
        # TABLA DE RESULTADOS
        st.subheader("📋 DETALLES POR ZONA")
        
        # Crear DataFrame para mostrar
        datos_tabla = []
        for zona in zonas_con_indices:
            fila = {
                'Zona': zona['id_zona'],
                'Área (ha)': f"{zona['area_ha']:.2f}",
                'NDVI': zona['ndvi'],
                'NDRE': zona['ndre'],
                'Materia Org (%)': zona['materia_organica'],
                'Humedad': zona['humedad_suelo']
            }
            
            if analisis_tipo == "FERTILIDAD ACTUAL":
                fila['NPK Actual'] = zona['npk_actual']
            else:
                fila['Recomendación'] = zona['valor_recomendado']
            
            fila['Categoría'] = zona['categoria']
            datos_tabla.append(fila)
        
        df_resultados = pd.DataFrame(datos_tabla)
        st.dataframe(df_resultados, use_container_width=True)
        
        # RECOMENDACIONES POR CATEGORÍA
        st.subheader("💡 RECOMENDACIONES POR CATEGORÍA")
        
        categorias = list(set(z['categoria'] for z in zonas_con_indices))
        for cat in sorted(categorias):
            zonas_cat = [z for z in zonas_con_indices if z['categoria'] == cat]
            area_cat = sum(z['area_ha'] for z in zonas_cat)
            
            with st.expander(f"🎯 **{cat}** - {area_cat:.1f} ha ({(area_cat/area_total_real*100):.1f}% del área)"):
                
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
                    if cat in ["MUY BAJO", "BAJO"]:
                        st.markdown("**🚨 APLICACIÓN ALTA** - Dosis correctiva urgente")
                        if nutriente == "NITRÓGENO":
                            st.markdown("- **Fuentes:** Urea (46% N) o Nitrato de amonio")
                            st.markdown("- **Aplicación:** 2-3 dosis fraccionadas")
                        elif nutriente == "FÓSFORO":
                            st.markdown("- **Fuentes:** Superfosfato triple (46% P₂O₅)")
                            st.markdown("- **Aplicación:** Incorporar al suelo")
                        else:
                            st.markdown("- **Fuentes:** Cloruro de potasio (60% K₂O)")
                            st.markdown("- **Aplicación:** 2-3 aplicaciones")
                    
                    elif cat == "MEDIO":
                        st.markdown("**✅ APLICACIÓN MEDIA** - Mantenimiento balanceado")
                        st.markdown("- **Fuentes:** Fertilizante balanceado")
                        st.markdown("- **Aplicación:** Programa estándar")
                    
                    else:
                        st.markdown("**🌟 APLICACIÓN BAJA** - Reducción de dosis")
                        st.markdown("- **Fuentes:** Fertilizantes bajos en el nutriente")
                        st.markdown("- **Aplicación:** Solo mantenimiento")
        
        # DESCARGA
        st.subheader("📥 DESCARGAR RESULTADOS")
        
        csv = df_resultados.to_csv(index=False)
        st.download_button(
            "📋 Descargar CSV",
            csv,
            f"analisis_gee_{cultivo}_{analisis_tipo.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            "text/csv"
        )
        
        return True
        
    except Exception as e:
        st.error(f"❌ Error en análisis: {str(e)}")
        return False

# INTERFAZ PRINCIPAL
st.info("🚀 **ANALIZADOR MULTI-CULTIVO** - Sistema de recomendaciones de fertilización basado en metodología GEE")

if st.button("🎯 EJECUTAR ANÁLISIS COMPLETO", type="primary", use_container_width=True):
    with st.spinner("Ejecutando análisis GEE..."):
        ejecutar_analisis(
            cultivo=cultivo,
            analisis_tipo=analisis_tipo,
            nutriente=nutriente,
            n_zonas=n_zonas,
            area_total=area_total,
            tipo_parcela=tipo_parcela,
            calidad_suelo=calidad_suelo,
            usar_sentinel=usar_sentinel
        )

# INFORMACIÓN ADICIONAL
with st.expander("ℹ️ INFORMACIÓN SOBRE LA METODOLOGÍA"):
    st.markdown("""
    **🌱 SISTEMA DE ANÁLISIS MULTI-CULTIVO (GEE)**
    
    **📊 CULTIVOS SOPORTADOS:**
    - **🌾 TRIGO, 🌽 MAÍZ, 🫘 SOJA, 🌾 SORGO, 🌻 GIRASOL**
    
    **🚀 FUNCIONALIDADES:**
    - **🌱 Fertilidad Actual:** Estado NPK del suelo
    - **💊 Recomendaciones NPK:** Dosis específicas por cultivo
    - **🛰️ Datos Satelitales:** Simulación Sentinel-2 Harmonizados
    - **🎯 Agricultura Precisión:** Análisis por zonas de manejo
    
    **🔬 METODOLOGÍA CIENTÍFICA:**
    - Parámetros específicos para cada cultivo
    - Cálculo basado en índices de vegetación
    - Recomendaciones validadas científicamente
    - Enfoque en agricultura de precisión
    """)

with st.expander("🎯 CÓMO USAR EL SISTEMA"):
    st.markdown("""
    1. **Selecciona el cultivo** a analizar
    2. **Elige el tipo de análisis** (Fertilidad o Recomendaciones NPK)
    3. **Configura los parámetros** de tu parcela
    4. **Haz clic en EJECUTAR ANÁLISIS**
    5. **Revisa los resultados** y recomendaciones
    
    **📝 Nota:** Este sistema utiliza simulación de datos para demostrar la metodología GEE.
    En una implementación real, se conectaría con APIs de satélites como Sentinel Hub.
    """)
