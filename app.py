import streamlit as st
import pandas as pd
import numpy as np

# Configuración MUY básica
st.set_page_config(
    page_title="Test App",
    layout="wide"
)

# Título simple
st.title("🚀 TEST - App Funcionando")
st.markdown("---")

# Sidebar mínimo
with st.sidebar:
    st.header("Configuración")
    opcion = st.selectbox("Selecciona:", ["Opción 1", "Opción 2", "Opción 3"])

# Contenido principal
st.success("✅ ¡SI VES ESTO, LA APP FUNCIONA!")
st.info(f"Seleccionaste: {opcion}")

# Botón de prueba
if st.button("🎯 Probar funcionalidad"):
    st.balloons()
    st.write("🎉 ¡Todo funciona perfectamente!")
    
    # Datos de ejemplo
    data = pd.DataFrame({
        'A': np.random.randn(5),
        'B': np.random.randn(5),
        'C': np.random.randn(5)
    })
    st.dataframe(data)

st.markdown("---")
st.caption("App de prueba - Streamlit")
