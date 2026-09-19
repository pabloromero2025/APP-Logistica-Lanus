import os
import re
import pandas as pd
import streamlit as st
import numpy as np
from PIL import Image
import easyocr

st.set_page_config(page_title="Lector de Etiquetas (OCR Local)", layout="wide")

st.title("📦 Extractor de Datos con OCR Local (Ilimitado)")
st.write("Procesa imágenes ilimitadas de forma local sin depender de APIs ni pagar cuotas.")

# Cargar motor OCR local en memoria (se ejecuta una sola vez)
@st.cache_resource
def cargar_lector_ocr():
    return easyocr.Reader(['es', 'en'], gpu=False)

reader = cargar_lector_ocr()

# Componente para subir archivos
uploaded_files = st.file_uploader(
    "1. Subir imágenes de etiquetas (JPG, PNG)", 
    type=["jpg", "jpeg", "png"], 
    accept_multiple_files=True
)

# Filtro de selección de imágenes
archivos_a_procesar = []

if uploaded_files:
    # Crear lista con los nombres de todos los archivos subidos
    nombres_archivos = [file.name for file in uploaded_files]
    
    # Selector múltiple con todas las fotos seleccionadas por defecto
    seleccionados = st.multiselect(
        "2. Selecciona qué fotos deseas procesar:",
        options=nombres_archivos,
        default=nombres_archivos
    )
    
    # Filtrar solo los archivos que el usuario eligió en el multiselect
    archivos_a_procesar = [file for file in uploaded_files if file.name in seleccionados]

def extraer_datos_local(image):
    img_array = np.array(image)
    
    # Extraer texto de la imagen
    lineas_texto = reader.readtext(img_array, detail=0)
    texto_completo = "\n".join(lineas_texto)
    
    # Expresiones regulares para buscar campos clave
    pack_match = re.search(r'(?:Pack ID|Pack|ID)[:\s]*(\d{10,18})', texto_completo, re.IGNORECASE)
    envio_match = re.search(r'(?:Envío|Envio)[:\s]*(\d{8,15})', texto_completo, re.IGNORECASE)
    cp_match = re.search(r'\bCP[:\s]*(\d{4})\b', texto_completo, re.IGNORECASE)
    
    servicio = "FLEX" if "FLEX" in texto_completo.upper() else ""
    
    return {
        "pack_id": pack_match.group(1) if pack_match else "",
        "envio_id": envio_match.group(1) if envio_match else "",
        "cp": cp_match.group(1) if cp_match else "",
        "servicio": servicio,
        "texto_extraido": texto_completo
    }

# Botón para iniciar el procesamiento
if archivos_a_procesar:
    if st.button(f"🚀 Procesar {len(archivos_a_procesar)} Imagen(es) Seleccionada(s)"):
        resultados = []
        progress_bar = st.progress(0)
        
        for index, file in enumerate(archivos_a_procesar):
            try:
                image = Image.open(file)
                datos = extraer_datos_local(image)
                datos['archivo'] = file.name
                resultados.append(datos)
            except Exception as e:
                st.error(f"Error procesando {file.name}: {e}")
            
            progress_bar.progress((index + 1) / len(archivos_a_procesar))
            
        if resultados:
            df = pd.DataFrame(resultados)
            
            st.success("¡Procesamiento local completado!")
            
            st.subheader("📊 Datos Extraídos")
            df_vista = df.drop(columns=['archivo'], errors='ignore')
            st.dataframe(df_vista, use_container_width=True)
            
            csv_data = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Descargar Tabla en CSV",
                data=csv_data,
                file_name="etiquetas_procesadas_local.csv",
                mime="text/csv"
            )
elif uploaded_files and not archivos_a_procesar:
    st.warning("Selecciona al menos una foto de la lista para poder procesar.")