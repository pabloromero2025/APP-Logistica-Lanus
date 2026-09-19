import json
import os
import re
import cv2
import easyocr
import numpy as np
import pandas as pd
from PIL import Image
import streamlit as st

st.set_page_config(
    page_title="Lector de Etiquetas (OCR Local Mejorado)", layout="wide"
)

st.title("📦 Extractor de Datos con OCR Local (Optimizado)")
st.write(
    "Procesa imágenes de etiquetas aplicando filtros de contraste y limpieza de"
    " ruido."
)


# Cargar motor OCR local en memoria
@st.cache_resource
def cargar_lector_ocr():
  return easyocr.Reader(["es", "en"], gpu=False)


reader = cargar_lector_ocr()


def limpiar_y_preprocesar_imagen(pil_image):
  """Aplica conversión a escala de grises y umbralizado para eliminar brillos de bolsas plasticas y sombras."""
  img_array = np.array(pil_image.convert("RGB"))
  gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)

  # Reescalar si la foto es pequeña
  h, w = gray.shape
  if w < 1000:
    gray = cv2.resize(gray, (w * 2, h * 2), interpolation=cv2.INTER_CUBIC)

  # Contraste y binarización
  gray = cv2.adaptiveThreshold(
      gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 21, 10
  )
  return gray


def extraer_datos_robusto(image):
  # 1. Preprocesar imagen para mejorar la lectura de EasyOCR
  img_cv = limpiar_y_preprocesar_imagen(image)

  # 2. Extraer bloques de texto de la imagen original y de la limpia
  lineas_texto = reader.readtext(img_cv, detail=0)
  if not lineas_texto:
    # Intento de respaldo con la imagen en formato PIL directo
    lineas_texto = reader.readtext(np.array(image), detail=0)

  texto_bruto = "\n".join(lineas_texto)
  texto_unificado = " ".join(lineas_texto)

  # 3. Limpieza de ruido OCR: Convertir caracteres confusos a dígitos
  traduccion_numeros = str.maketrans({
      "O": "0",
      "o": "0",
      "S": "5",
      "s": "5",
      "Z": "2",
      "z": "2",
      "I": "1",
      "l": "1",
      "|": "1",
      "!": "1",
      "i": "1",
      "+": "1",
      "B": "8",
      "b": "6",
  })
  texto_digitos = texto_unificado.translate(traduccion_numeros)
  solo_numeros = re.sub(r"\D", "", texto_digitos)

  # 4. Extracción de Pack ID (11 o 16 dígitos)
  pack_id = ""
  p_direct = re.findall(r"(20000\d{10,12}|150\d{8,11})", solo_numeros)
  if p_direct:
    pack_id = p_direct[0][:16]

  # 5. Extracción de Envío ID (11 dígitos comenzando en 48, 49, 42)
  envio_id = ""
  e_direct = re.findall(r"(480\d{8}|490\d{8}|48\d{9}|420\d{8})", solo_numeros)
  if e_direct:
    envio_id = e_direct[0][:11]

  # 6. Extracción de CP (priorizando el CP de destino que suele estar abajo)
  cps = re.findall(r"\b(1\d{3})\b", texto_bruto)
  cp_val = cps[-1] if cps else ""

  # 7. Captura de Dirección, Destinatario y Referencia
  dir_m = re.search(
      r"(?:Direcci[oó]n|Dhreccion|Direcron|Dieesios|DIRECCIÓN|Drecoon)[:\s\n]*(.*?)(?=Barrio|Borno|Bartio|Baqnos|Referencia|Betorencta|Peferendia|Destinatario|Distinario|Destinetorlo|Destinatani|$)",
      texto_unificado,
      re.IGNORECASE,
  )
  direccion = dir_m.group(1).strip() if dir_m else ""
  direccion = re.sub(r"^[;\s\:]+", "", direccion)

  dest_m = re.search(
      r"(?:Destina[tT]ar[iıo]+|Distinario|Destinetorlo|Destinatani|Dertinataria|NOMBRE)[:\s\n]*(.*?)(?=\(|CELULAR|CÓDIGO|CSUER|$)",
      texto_unificado,
      re.IGNORECASE,
  )
  destinatario = dest_m.group(1).strip() if dest_m else ""

  ref_m = re.search(
      r"(?:Referenc[iı]a|Betorencta|Peferendia|Bercnor)[:\s\n]*(.*?)(?=Destinatario|Distinario|Destinetorlo|Destinatani|Dertinataria|Entre:|$)",
      texto_unificado,
      re.IGNORECASE,
  )
  referencia = ref_m.group(1).strip() if ref_m else ""

  servicio = "FLEX" if "FLEX" in texto_unificado.upper() else "ESTÁNDAR"

  return {
      "pack_id": pack_id,
      "envio_id": envio_id,
      "destinatario": destinatario,
      "direccion": direccion,
      "referencia": referencia,
      "cp": cp_val,
      "servicio": servicio,
      "texto_extraido": texto_bruto,
  }


# --- INTERFAZ WEB STREAMLIT ---
uploaded_files = st.file_uploader(
    "1. Subir imágenes de etiquetas (JPG, PNG)",
    type=["jpg", "jpeg", "png"],
    accept_multiple_files=True,
)

archivos_a_procesar = []

if uploaded_files:
  nombres_archivos = [file.name for file in uploaded_files]
  seleccionados = st.multiselect(
      "2. Selecciona qué fotos deseas procesar:",
      options=nombres_archivos,
      default=nombres_archivos,
  )
  archivos_a_procesar = [
      file for file in uploaded_files if file.name in seleccionados
  ]

if archivos_a_procesar:
  if st.button(
      f"🚀 Procesar {len(archivos_a_procesar)} Imagen(es) Seleccionada(s)"
  ):
    resultados = []
    progress_bar = st.progress(0)

    for index, file in enumerate(archivos_a_procesar):
      try:
        image = Image.open(file)
        datos = extraer_datos_robusto(image)
        datos["archivo"] = file.name
        resultados.append(datos)
      except Exception as e:
        st.error(f"Error procesando {file.name}: {e}")

      progress_bar.progress((index + 1) / len(archivos_a_procesar))

    if resultados:
      df = pd.DataFrame(resultados)
      columnas_orden = [
          "pack_id",
          "envio_id",
          "destinatario",
          "direccion",
          "referencia",
          "cp",
          "servicio",
          "texto_extraido",
          "archivo",
      ]
      df = df.reindex(
          columns=[col for col in columnas_orden if col in df.columns]
      )

      st.success("¡Procesamiento local completado!")

      st.subheader("📊 Datos Extraídos")
      df_vista = df.drop(columns=["archivo"], errors="ignore")
      st.dataframe(df_vista, use_container_width=True)

      csv_data = df.to_csv(index=False).encode("utf-8")
      st.download_button(
          label="📥 Descargar Tabla en CSV",
          data=csv_data,
          file_name="etiquetas_procesadas_local.csv",
          mime="text/csv",
      )
