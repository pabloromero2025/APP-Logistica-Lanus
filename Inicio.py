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
    nombres_archivos = [file.name for file in uploaded_files]
    
    seleccionados = st.multiselect(
        "2. Selecciona qué fotos deseas procesar:",
        options=nombres_archivos,
        default=nombres_archivos
    )
    
    archivos_a_procesar = [file for file in uploaded_files if file.name in seleccionados]

def extraer_datos_local(image):
    img_array = np.array(image)
    
    # Extraer texto de la imagen
    lineas_texto = reader.readtext(img_array, detail=0)
    texto_completo = "\n".join(lineas_texto)
    
    # Reemplazo de caracteres comúnmente confundidos por el OCR
    texto_normalizado = texto_completo.replace('ZOO', '200').replace('ZO0', '200').replace('Z00', '200')
    
    # Búsqueda de Pack ID (flexibilidad para capturar secuencias numéricas largas)
    pack_match = re.search(r'(?:Pack\s*ID|Pack)[:\s]*[A-Z0-9]*\s*(\d{10,18})', texto_normalizado, re.IGNORECASE)
    if not pack_match:
        pack_match = re.search(r'\b(20000\d{10,12}|150\d{7,12})\b', texto_normalizado)
        
    # Búsqueda de Envío ID / Tracking
    envio_match = re.search(r'(?:Env[íi]o|Tracking)[:\s]*([0-9\sV]+)', texto_normalizado, re.IGNORECASE)
    envio_id = ""
    if envio_match:
        envio_id = re.sub(r'\D', '', envio_match.group(1))
    if not envio_id or len(envio_id) < 5:
        alt_envio = re.search(r'\b(480\d{7,10}|48\s*\d{4,10})\b', texto_normalizado)
        if alt_envio:
            envio_id = re.sub(r'\D', '', alt_envio.group(1))
            
    # Búsqueda de Código Postal (CP)
    cp_match = re.search(r'\bCP[:\s]*(\d{4})\b', texto_completo, re.IGNORECASE)
    if not cp_match:
        cp_match = re.search(r'\b(\d{4})\b', texto_completo)
        
    # Extracción de campos adicionales de la etiqueta
    dir_match = re.search(r'Direcci[oó]n[:\s]*(.*)', texto_completo, re.IGNORECASE)
    dest_match = re.search(r'Destinatario[:\s]*(.*)', texto_completo, re.IGNORECASE)
    ref_match = re.search(r'Referencia[:\s]*(.*)', texto_completo, re.IGNORECASE)
    
    servicio = "FLEX" if "FLEX" in texto_completo.upper() else ""
    
    return {
        "pack_id": pack_match.group(1) if pack_match else "",
        "envio_id": envio_id,
        "destinatario": dest_match.group(1).strip() if dest_match else "",
        "direccion": dir_match.group(1).strip() if dir_match else "",
        "referencia": ref_match.group(1).strip() if ref_match else "",
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
                data=excel_data if 'excel_data' in locals() else csv_data,
                file_name="etiquetas_procesadas_local.csv",
                mime="text/csv"
            )
elif uploaded_files and not archivos_a_procesar:
    st.warning("Selecciona al menos una foto de la lista para poder procesar.")
