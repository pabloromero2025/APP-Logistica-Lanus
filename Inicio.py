import os
import re
import pandas as pd
import streamlit as st
import numpy as np
from PIL import Image
import easyocr
import cv2
st.set_page_config(page_title="Lector de Etiquetas (OCR Local)", layout="wide")

st.title("📦 Extractor de Datos con OCR Local (Ilimitado)")
st.write("Procesa imágenes ilimitadas de forma local sin depender de APIs ni pagar cuotas.")

# Cargar motor OCR local en memoria
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




def preprocesar_imagen(pil_image):
  # Convertir a escala de grises y aumentar contraste para etiquetas térmicas
  img_cv = np.array(pil_image.convert('RGB'))
  gray = cv2.cvtColor(img_cv, cv2.COLOR_RGB2GRAY)
  # Aumentar contraste
  gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
  return gray


def extraer_datos_local(image):
  # 1. Preprocesar imagen antes de pasar a EasyOCR
  img_procesada = preprocesar_imagen(image)
  lineas_texto = reader.readtext(img_procesada, detail=0)

  texto_completo = "\n".join(lineas_texto)
  # Unificar saltos de línea para búsquedas multilínea
  texto_unificado = " ".join(lineas_texto)
  texto_norm = (
      texto_unificado.replace("ZOO", "200")
      .replace("ZO0", "200")
      .replace("Z00", "200")
  )

  # 1. Pack ID (15 a 17 dígitos, buscando patrón 20000...)
  pack_id = ""
  pack_match = re.search(
      r"(?:Pack\s*ID|PackID|PeckID)[:\s]*(\d[\d\s]{10,20})",
      texto_norm,
      re.IGNORECASE,
  )
  if pack_match:
    pack_id = re.sub(r"\D", "", pack_match.group(1))
  if not pack_id or len(pack_id) < 12:
    alt_pack = re.search(r"\b(20000\d{10,12})\b", re.sub(r"\s+", "", texto_norm))
    if alt_pack:
      pack_id = alt_pack.group(1)

  # 2. Envío ID / Tracking (11 dígitos que suelen empezar por 48 o 49)
  envio_id = ""
  envio_match = re.search(
      r"(?:Env[íiao]o|Tracking)[:\s]*([0-9\s]{8,15})", texto_norm, re.IGNORECASE
  )
  if envio_match:
    envio_id = re.sub(r"\D", "", envio_match.group(1))
  if not envio_id or len(envio_id) < 9:
    alt_envio = re.search(
        r"\b(4[89]\d{9})\b", re.sub(r"\s+", "", texto_norm)
    )
    if alt_envio:
      envio_id = alt_envio.group(1)

  # 3. Código Postal Destino (CP: 1XXX)
  cp_val = ""
  cp_match = re.search(r"CP[:\s]*(\d{4})", texto_norm, re.IGNORECASE)
  if cp_match:
    cp_val = cp_match.group(1)
  else:
    # Buscar el CP que no sea el de Lanús (1824) si hay varios
    cps = re.findall(r"\b(1\d{3})\b", texto_completo)
    cps_filtrados = [c for c in cps if c != "1824"]
    cp_val = cps_filtrados[-1] if cps_filtrados else (cps[-1] if cps else "")

  # 4. Dirección (captura multilínea hasta Barrio/Referencia/Destinatario)
  dir_match = re.search(
      r"Direccion[:\s]*(.*?)(?=Barrio|Referencia|Destinatario|$)",
      texto_unificado,
      re.IGNORECASE,
  )
  direccion = dir_match.group(1).strip() if dir_match else ""

  # 5. Referencia
  ref_match = re.search(
      r"Referencia[:\s]*(.*?)(?=Destinatario|$)", texto_unificado, re.IGNORECASE
  )
  referencia = ref_match.group(1).strip() if ref_match else ""

  # 6. Destinatario
  dest_match = re.search(
      r"Destinatario[:\s]*(.*?)(?=\([A-Z0-9]+\)|$)",
      texto_unificado,
      re.IGNORECASE,
  )
  destinatario = dest_match.group(1).strip() if dest_match else ""

  servicio = "FLEX" if "FLEX" in texto_completo.upper() else ""

  return {
      "pack_id": pack_id,
      "envio_id": envio_id,
      "destinatario": destinatario,
      "direccion": direccion,
      "referencia": referencia,
      "cp": cp_val,
      "servicio": servicio,
      "texto_extraido": texto_completo,
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
            
            # Ordenar columnas para la vista
            columnas_orden = [
                'pack_id', 'envio_id', 'destinatario', 'direccion', 
                'referencia', 'cp', 'servicio', 'texto_extraido', 'archivo'
            ]
            df = df.reindex(columns=[col for col in columnas_orden if col in df.columns])
            
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
