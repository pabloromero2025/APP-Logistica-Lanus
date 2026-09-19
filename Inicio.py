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
    lineas_texto = reader.readtext(img_array, detail=0)
    texto_completo = "\n".join(lineas_texto)
    
    # 1. CP de entrega (busca prioritariamente 'CP:' seguido de 4 dígitos hacia el final de la etiqueta)
    cp_match = re.search(r'CP[:\s\n]*(\d{4})\b(?=[\s\n]*[A-Z\s]+(?:SUR|NORTE|ESTE|OESTE|RESIDENCIAL))', texto_completo, re.IGNORECASE)
    if not cp_match:
        cp_matches = re.findall(r'\bCP[:\s\n]*(\d{4})\b', texto_completo, re.IGNORECASE)
        cp_val = cp_matches[-1] if cp_matches else "" # Toma el último CP (destinatario)
    else:
        cp_val = cp_match.group(1)

    # 2. Pack ID (Pack ID suele empezar con 20000 o 150)
    pack_match = re.search(r'(?:20000\d{10,12}|150\d{8,12})', texto_completo)
    
    # 3. Envío ID (Tracking de Mercado Envíos suele empezar por 48 o 49 y tener 11 dígitos)
    envio_match = re.search(r'(?:48\d{9}|49\d{9})', texto_completo.replace(" ", ""))
    
    # 4. Dirección
    dir_match = re.search(r'Direcci[oó]n[:\s]*(.*)', texto_completo, re.IGNORECASE)
    
    # 5. Destinatario
    dest_match = re.search(r'Destina[tT]ar[iıo]+[:\s]*(.*)', texto_completo, re.IGNORECASE)
    
    # 6. Referencia
    ref_match = re.search(r'Referenc[iı]a[:\s]*(.*)', texto_completo, re.IGNORECASE)
    
    servicio = "FLEX" if "FLEX" in texto_completo.upper() else ""
    
    return {
        "pack_id": pack_match.group(0) if pack_match else "",
        "envio_id": envio_match.group(0) if envio_match else "",
        "destinatario": dest_match.group(1).strip() if dest_match else "",
        "direccion": dir_match.group(1).strip() if dir_match else "",
        "referencia": ref_match.group(1).strip() if ref_match else "",
        "cp": cp_val,
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
