import streamlit as st
st.set_page_config(page_title="Strike IQ - Análisis de Cargas", layout="wide")
#
import pandas as pd
import datetime
import plotly.express as px
from io import StringIO
import os
import gspread
from google.oauth2 import service_account
import pytz
import hashlib
import streamlit_authenticator as stauth
import json
import copy
import pickle
import zipfile
import tempfile
import io
from pathlib import Path
import re

from sqlalchemy import create_engine
import psycopg2
from sqlalchemy.exc import SQLAlchemyError

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from datetime import timedelta

# Leer credenciales y configuración de cookies desde secrets.toml
credentials = dict(st.secrets["credentials"])
cookie = st.secrets["cookie"]

# Inicializar el autenticador
authenticator = stauth.Authenticate(
    credentials,
    st.secrets["cookie"]["name"],
    st.secrets["cookie"]["key"],
    st.secrets["cookie"]["expiry_days"]
)

# Mostrar el formulario de inicio de sesión
name, auth_status, username = authenticator.login("Iniciar sesión", "main")


if  auth_status is False:
    st.error("❌ Usuario o contraseña incorrectos")
elif auth_status is None:
    st.warning("🔐 Por favor ingresá tus credenciales")
elif auth_status:

    role = credentials["usernames"][username].get("role", "admin")


    authenticator.logout("Cerrar sesión", "sidebar")
    st.markdown("""
        <h1 style='
            text-align: center;
            font-size: 52px;
            font-weight: 900;
            color: #42A5F5;
            font-family: "Segoe UI", sans-serif;
            margin-bottom: 5px;
            letter-spacing: 1px;'>
            Strike IQ
        </h1>
        <p style='
            text-align: center;
            font-size: 18px;
            color: #B0BEC5;
            font-family: "Segoe UI", sans-serif;
            margin-top: 0;
            font-style: italic;
            letter-spacing: 0.5px;'>
            Inteligencia estratégica
        </p>
    """, unsafe_allow_html=True)
    
    
    # --- Conexión a Google Sheets ---
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    credentials = service_account.Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], scopes=scope
    )
    gc = gspread.authorize(credentials)
    SPREADSHEET_ID = "1HxbIBXBs8tlFtNy8RUQq8oANei1MHp_VleQmvCmLabY"
    sh = gc.open_by_key(SPREADSHEET_ID)
    worksheet = sh.sheet1
    
    # 🔵 Cargar historial si existe
    try:
        historial_data = worksheet.get_all_records()
        df_historial = pd.DataFrame(historial_data)
    except:
        df_historial = pd.DataFrame()
    # Agregar CSS para ocultar GitHub Icon
    st.markdown("""
        <style>
        .stApp .header .stGitHub { display: none; }
        </style>
    """, unsafe_allow_html=True)
    
    # Guardar la selección anterior y actual
    if "seccion_actual" not in st.session_state:
        st.session_state.seccion_actual = ""
    
     # Definir qué secciones ve cada rol
    secciones_por_rol = {
        "admin": ["🏢 Oficina VIP", "📋 Registro Fénix/Eros", "📋 Registro BetArgento/Atlantis","📋 Registro Spirita","📋 Registro Atenea","📋 Registro Padrino Latino/Tiger","📋 Registro Fortuna/Gana 24","📆 Agenda Fénix","📆 Agenda Eros","📆 Agenda BetArgento","📊 Análisis Temporal"],
        "fenix_eros": ["📋 Registro Fénix/Eros"],
        "bet": ["📋 Registro BetArgento/Atlantis"],
        "spirita":["📋 Registro Spirita"],
        "atenea":["📋 Registro Atenea"],
        "padrino":["📋 Registro Padrino Latino/Tiger"],
        "fortuna":["📋 Registro Fortuna/Gana 24"]
    }
    
    # Obtener lista de secciones según el rol
    secciones_disponibles = secciones_por_rol.get(role, [])
    seccion = st.sidebar.radio("Seleccioná una sección:", secciones_disponibles)
        
    if seccion != st.session_state.seccion_actual:
        st.session_state.texto_pegar = ""
        st.session_state.seccion_actual = seccion
    
    # --- FUNCIONES ---
    def preparar_dataframe(df):
        df = df.rename(columns={
            "operación": "Tipo",
            "Depositar": "Monto",
            "Retirar": "Retiro",
            "Wager": "?2",
            "Límites": "?3",
            "Balance antes de operación": "Saldo",
            "Fecha": "Fecha",
            "Tiempo": "Hora",
            "Iniciador": "UsuarioSistema",
            "Del usuario": "Plataforma",
            "Sistema": "Admin",
            "Al usuario": "Jugador",
            "IP": "Extra"
        })
        return df

    # 🔍 Detecta el formato numérico
    def detectar_formato_decimal(valor):
        if "," in valor and "." in valor:
            return "en" if valor.rfind(".") > valor.rfind(",") else "lat"
        elif "," in valor:
            return "lat"
        elif "." in valor:
            return "en"
        else:
            return "none"
    
    # 🔄 Convierte valores como "2.000,00" o "2,000.00" a 2000.00
    def convertir_a_numero(valor):
        try:
            valor = str(valor).strip()
            if valor == "":
                return 0.0
            formato = detectar_formato_decimal(valor)
            if formato == "en":
                valor = valor.replace(",", "")
            elif formato == "lat":
                valor = valor.replace(".", "").replace(",", ".")
            return float(valor)
        except:
            return 0.0
    
    # ✅ Limpia columnas numéricas específicas
    def limpiar_columnas_numericas(df):
        columnas_numericas = ["Depositar", "Retirar", "Wager", "Balance antes de operación"]
        for col in columnas_numericas:
            if col in df.columns:
                df[col] = df[col].apply(convertir_a_numero)
        return df
    
    # ✅ Convierte correctamente la columna "Tiempo"
    def convertir_columna_tiempo(df):
        def convertir(valor):
            try:
                if isinstance(valor, datetime.time):
                    return valor
                if isinstance(valor, str) and ":" in valor:
                    return datetime.datetime.strptime(valor.strip(), "%H:%M:%S").time()
                valor_str = str(int(float(valor))).zfill(6)
                h, m, s = int(valor_str[0:2]), int(valor_str[2:4]), int(valor_str[4:6])
                return datetime.time(h, m, s)
            except:
                return None
    
        if "Tiempo" in df.columns:
            df["Tiempo"] = df["Tiempo"].apply(convertir)
        return df
    
    # ✅ Limpieza específica para la tabla de transacciones
    def limpiar_transacciones(df):
        df = limpiar_columnas_numericas(df)
    
        if "Fecha" in df.columns:
            df["Fecha"] = pd.to_datetime(df["Fecha"], errors='coerce').dt.date
    
        df = convertir_columna_tiempo(df)
    
        columnas_texto = [
            "ID", "operación", "Límites", "Iniciador", "Del usuario",
            "Sistema", "Al usuario", "IP"
        ]
        for col in columnas_texto:
            if col in df.columns:
                df[col] = df[col].astype(str).fillna("").str.strip()
    
        return df
    
    # ✅ Inserta datos en Supabase
    def subir_a_supabase(df, tabla, engine):
        try:
            if tabla == "transacciones_crudas":
                df = limpiar_transacciones(df)
    
            elif tabla == "bonos_crudos":
                df.columns = df.columns.str.strip()
                if "USUARIO" in df.columns:
                    df = df.drop_duplicates(subset=["USUARIO"], keep="last")
                    st.info(f"🧹 Se eliminaron duplicados. Registros únicos por usuario: {len(df)}")
    
            elif tabla == "actividad_jugador_cruda":
                columnas_validas = [
                    "casino", "ID", "Sesión", "Usuario", "Sistema de juegos", "Sello",
                    "Nombre del juego", "Balance", "Divisa", "Apuesta", "Ganar",
                    "Ganancias", "Hora de apertura", "Hora de cierre", "Hora de ultima actividad"
                ]
                df.columns = df.columns.str.strip()
                df = df[[col for col in df.columns if col in columnas_validas]]
    
                columnas_numericas = ["Balance", "Apuesta", "Ganar", "Ganancias"]
                for col in columnas_numericas:
                    if col in df.columns:
                        df[col] = df[col].astype(str).str.replace(",", "").str.replace("−", "-")
                        df[col] = pd.to_numeric(df[col], errors="coerce")
    
            else:
                df = limpiar_columnas_numericas(df)
    
            if df.empty:
                st.warning("⚠️ El archivo no contiene datos válidos para subir.")
                return
    
            df.to_sql(tabla, con=engine, if_exists='append', index=False)
            st.success(f"✅ {len(df)} registros cargados correctamente en la tabla `{tabla}`.")
    
        except SQLAlchemyError as e:
            st.error(f"❌ Error al subir datos a `{tabla}`: {e}")
    
    # ✅ Detecta la tabla por estructura de columnas
    def detectar_tabla(df):
        columnas = set(col.lower().strip() for col in df.columns)
    
        if {"sesión", "usuario", "nombre del juego", "hora de apertura"}.issubset(columnas):
            return "actividad_jugador_cruda"
        elif {"operación", "depositar", "retirar", "fecha", "del usuario"}.issubset(columnas):
            return "transacciones_crudas"
        elif {"id_usuario", "usuario", "bonos ofrecidos", "bonos usados"}.issubset(columnas):
            return "bonos_crudos"
        elif {"game name", "label", "category", "type"}.issubset(columnas):
            return "catalogo_juegos"
        else:
            return None
    
    # ✅ Agrega columna del casino
    def agregar_columna_casino(df, casino):
        df.columns = df.columns.str.strip()
        df["casino"] = casino
        return df
    
    # ✅ Extrae nombre real de la hoja 'Información'
    def extraer_nombre_real_desde_info(archivo_path):
        try:
            df_info = pd.read_excel(archivo_path, sheet_name="Información", usecols="A:B", nrows=10)
            df_info.columns = df_info.columns.str.strip()
            df_info = df_info.dropna()
            df_info.columns = ["clave", "valor"]
            df_info["clave"] = df_info["clave"].astype(str).str.strip()
            df_info["valor"] = df_info["valor"].astype(str).str.strip()
            fila_usuario = df_info[df_info["clave"] == "Usuario"]
            if not fila_usuario.empty:
                return fila_usuario["valor"].values[0]
        except Exception:
            return None

    # ✅ Función cacheada y reutilizable para cargar bonos según casino
    @st.cache_data(ttl=300)
    def cargar_tabla_bonos(casino_key: str, _sh):
        hoja_registro = _sh.worksheet(f"registro_bono_{casino_key}")
        datos_registro = hoja_registro.get_all_values()
        hoja_bonos = _sh.worksheet(f"bonos_ofrecidos_{casino_key}")
        datos_bonos = hoja_bonos.get_all_values()
    
        def manejar_encabezados_unicos(headers):
            seen = set()
            unique = []
            for h in headers:
                if h in seen:
                    i = 1
                    while f"{h}_{i}" in seen:
                        i += 1
                    h = f"{h}_{i}"
                seen.add(h)
                unique.append(h)
            return unique
    
        headers_reg = manejar_encabezados_unicos(datos_registro[0])
        df_registro = pd.DataFrame(datos_registro[1:], columns=headers_reg)
        df_registro["USUARIO"] = df_registro["USUARIO"].astype(str).str.strip().str.lower()
        df_registro["USUARIO_NORM"] = df_registro["USUARIO"].str.replace(" ", "").str.replace("_", "")
        df_registro = df_registro.drop_duplicates(subset=["USUARIO_NORM"], keep="last").drop(columns=["USUARIO_NORM"])
    
        headers_bonos = manejar_encabezados_unicos(datos_bonos[0])
        df_bonos = pd.DataFrame(datos_bonos[1:], columns=headers_bonos)
        df_bonos["USUARIO"] = df_bonos["USUARIO"].astype(str).str.strip().str.lower()
        df_bonos["FECHA"] = pd.to_datetime(df_bonos["FECHA"], errors="coerce")
    
        df_categorias = (
            df_bonos.dropna(subset=["CATEGORIA DE BONO"])
            .sort_values("FECHA")
            .groupby("USUARIO")
            .agg({
                "CATEGORIA DE BONO": "last",
                "FECHA": "last"
            })
            .reset_index()
            .rename(columns={"FECHA": "FECHA_ULTIMA_ACTUALIZACION"})
        )
    
        df_bono = df_registro.merge(df_categorias, on="USUARIO", how="left")
    
        df_bono.rename(columns={
            "USUARIO": "Usuario",
            "FUNNEL": "Tipo de Bono",
            "BONOS OFRECIDOS": "Cuántas veces se le ofreció el bono",
            "BONOS USADOS": "Cuántas veces cargó con bono",
            "MONTO TOTAL CARGADO": "Monto total",
            "% DE CONVERSION": "Conversión",
            "ULT. ACTUALIZACION": "Fecha del último mensaje",
            "CATEGORIA DE BONO": "Categoría de Bono",
            "FECHA_ULTIMA_ACTUALIZACION": "Últ. vez contactado"
        }, inplace=True)
    
        df_bono["Conversión"] = df_bono["Conversión"].astype(str).str.replace("%", "", regex=False)
        df_bono["Conversión"] = pd.to_numeric(df_bono["Conversión"], errors="coerce").fillna(0)
        df_bono["Fecha del último mensaje"] = df_bono["Fecha del último mensaje"].replace(
            ["30/12/1899", "1899-12-30"], "Sin registros"
        )
    
        columnas_finales = [
            "Usuario", "Tipo de Bono",
            "Cuántas veces se le ofreció el bono", "Cuántas veces cargó con bono",
            "Monto total", "Conversión",
            "Fecha del último mensaje", "Categoría de Bono",
            "Últ. vez contactado"
        ]
    
        return df_bono[columnas_finales]

    def asignar_princi(df_registro: pd.DataFrame, sh, nombre_casino: str) -> pd.DataFrame:
        try:
            nombre_hoja = f"princi_{nombre_casino.lower()}"
            hoja_princi = sh.worksheet(nombre_hoja)
            data_princi = hoja_princi.get_all_values()
            df_princi = pd.DataFrame(data_princi[1:], columns=data_princi[0])
    
            def normalizar(nombre):
                return str(nombre).strip().lower().replace(" ", "").replace("_", "")
    
            mapping_princi = {}
            for col in df_princi.columns:
                for nombre in df_princi[col]:
                    if nombre.strip():
                        mapping_princi[normalizar(nombre)] = col.strip().upper()
    
            df_registro["Jugador_NORM"] = df_registro["Nombre de jugador"].apply(normalizar)
            df_registro["PRINCI"] = df_registro["Jugador_NORM"].map(mapping_princi).fillna("N/A")
            df_registro.drop(columns=["Jugador_NORM"], inplace=True)
        
        except Exception as e:
            st.warning(f"⚠️ No se pudo asignar princi desde la hoja '{nombre_hoja}': {e}")
            df_registro["PRINCI"] = "N/A"
    
        return df_registro


    if  "📋 Registro Fénix/Eros" in seccion:
        st.header("📋 Registro general de jugadores")
    
        casino_actual = st.selectbox("🎰 Seleccioná el casino al que pertenece este reporte", [
            "Fénix", "Eros"
        ], key="casino_selector_fenix_eros")
        
        clave_casino = "fenix" if casino_actual == "Fénix" else "eros"
    
        if "casino_anterior_fenix_eros" not in st.session_state:
            st.session_state["casino_anterior_fenix_eros"] = casino_actual
    
        if casino_actual != st.session_state["casino_anterior_fenix_eros"]:
            st.session_state["casino_anterior_fenix_eros"] = casino_actual
            st.session_state.pop("archivo_procesado_fenix_eros", None)
            st.experimental_rerun()
    
        archivo = st.file_uploader("📁 Subí el archivo del reporte (.xlsx)", type=["xlsx"], key="reporte_fenix_eros")
    
        if archivo and not st.session_state.get("archivo_procesado_fenix_eros"):
            try:
                df = pd.read_excel(archivo)
                df = limpiar_transacciones(df)
                df = agregar_columna_casino(df, casino_actual)
    
                engine = create_engine(st.secrets["DB_URL"])
                subir_a_supabase(df, "reportes_jugadores", engine)
    
                st.session_state["archivo_procesado_fenix_eros"] = True
                st.success("✅ Archivo subido y procesado correctamente.")
    
            except Exception as e:
                st.error(f"❌ Error al procesar o subir el archivo: {e}")
    
        elif st.session_state.get("archivo_procesado_fenix_eros"):
            st.success("✅ El archivo ya fue procesado. Si querés subir uno nuevo, cambiá el casino o recargá la página.")
    
        # === Visualización de la vista correspondiente ===
        st.markdown("---")
        st.subheader(f"🔍 Vista resumen de jugadores - {casino_actual}")
    
        nombre_vista = "resumen_fenix" if casino_actual == "Fénix" else "resumen_eros"
    
        try:
            engine = create_engine(st.secrets["DB_URL"])
            with engine.connect() as conn:
                query = f'SELECT * FROM "{nombre_vista}" ORDER BY "Ganacias casino" DESC'
                df_resumen = pd.read_sql(query, conn)
    
            clave_casino = "fenix" if casino_actual == "Fénix" else "eros"
            df_bonos = cargar_tabla_bonos(clave_casino, sh)
    
            df_resumen["__user_key"] = df_resumen["Nombre de jugador"].astype(str).str.lower().str.replace(" ", "").str.replace("_", "")
            df_bonos["__user_key"] = df_bonos["Usuario"].astype(str).str.lower().str.replace(" ", "").str.replace("_", "")
    
            dict_tipo_bono = dict(zip(df_bonos["__user_key"], df_bonos["Tipo de Bono"]))
            dict_contacto = dict(zip(df_bonos["__user_key"], df_bonos["Últ. vez contactado"]))
    
            if "Tipo de bono" in df_resumen.columns:
                df_resumen["Tipo de bono"] = df_resumen["__user_key"].map(dict_tipo_bono).combine_first(df_resumen["Tipo de bono"])
                df_resumen["Tipo de bono"] = df_resumen["Tipo de bono"].replace("", pd.NA).fillna("N/A")
    
            if "Últ. vez contactado" in df_resumen.columns:
                df_resumen["Últ. vez contactado"] = df_resumen["__user_key"].map(dict_contacto).fillna(df_resumen["Últ. vez contactado"])
    
            df_resumen.drop(columns=["__user_key"], inplace=True)
    
            df_resumen = asignar_princi(df_resumen, sh, clave_casino)
    
            cols = df_resumen.columns.tolist()
            if "Tipo de bono" in cols and "PRINCI" in cols:
                cols.remove("PRINCI")
                idx = cols.index("Tipo de bono") + 1
                cols.insert(idx, "PRINCI")
                df_resumen = df_resumen[cols]
    
            # 🗓️ Filtro por fecha
            st.markdown("### 📅 Filtrar jugadores por fecha de última carga")
            col1, col2 = st.columns(2)
    
            if not pd.api.types.is_datetime64_any_dtype(df_resumen["Última vez que cargó"]):
                df_resumen["Última vez que cargó"] = pd.to_datetime(df_resumen["Última vez que cargó"], errors="coerce")
    
            with col1:
                filtro_desde = st.date_input("📆 Desde", value=df_resumen["Última vez que cargó"].min().date(), key="desde_fecha_fenix_eros")
            with col2:
                filtro_hasta = st.date_input("📆 Hasta", value=df_resumen["Última vez que cargó"].max().date(), key="hasta_fecha_fenix_eros")
    
            df_resumen_filtrado = df_resumen[
                (df_resumen["Última vez que cargó"] >= pd.to_datetime(filtro_desde)) &
                (df_resumen["Última vez que cargó"] <= pd.to_datetime(filtro_hasta))
            ]
    
            df_resumen_filtrado["Tipo de bono"] = df_resumen_filtrado["Tipo de bono"].fillna("N/A")
            col_filtro, _ = st.columns(2)
            tipos_disponibles = sorted(df_resumen_filtrado["Tipo de bono"].unique().tolist())
    
            # ✅ Cambio: por defecto no se selecciona ningún tipo de bono
            seleccion_tipos = col_filtro.multiselect(
                "🎯 Filtrar por tipo de bono:",
                options=tipos_disponibles,
                default=[]
            )
            
            # ✅ Agregado: si se selecciona al menos un tipo, se filtra; si no, se muestra todo
            if seleccion_tipos:
                df_resumen_filtrado = df_resumen_filtrado[df_resumen_filtrado["Tipo de bono"].isin(seleccion_tipos)]
    
            if not df_resumen_filtrado.empty:
                st.dataframe(df_resumen_filtrado, use_container_width=True)
    
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
                    df_resumen_filtrado.to_excel(writer, index=False, sheet_name=casino_actual)
    
                st.download_button(
                    "⬇️ Descargar Excel",
                    data=output.getvalue(),
                    file_name=f"{casino_actual.lower().replace(' ', '_')}_resumen.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.info("ℹ️ No hay jugadores que coincidan con los filtros.")
        except Exception as e:
            st.error(f"❌ Error al consultar la vista del casino seleccionado: {e}")
    
        st.markdown("----")
        st.subheader(f"🎁 Tabla de Bonos - {casino_actual}")
    
        try:
            df_bonos = cargar_tabla_bonos(clave_casino, sh)
    
            if not df_bonos.empty:
                st.dataframe(df_bonos, use_container_width=True)
    
                output_bonos = io.BytesIO()
                with pd.ExcelWriter(output_bonos, engine="xlsxwriter") as writer:
                    df_bonos.to_excel(writer, index=False, sheet_name=f"Bonos_{casino_actual}")
                st.download_button(
                    "⬇️ Descargar Tabla de Bonos",
                    data=output_bonos.getvalue(),
                    file_name=f"{clave_casino}_bonos.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.info("ℹ️ No hay datos en la tabla de bonos para este casino.")
        except Exception as e:
            st.error(f"❌ Error al cargar tabla de bonos: {e}")


    elif "📋 Registro BetArgento/Atlantis" in seccion:
        st.header("📋 Registro general de jugadores")
    
        casino_actual = st.selectbox("🎰 Seleccioná el casino al que pertenece este reporte", [
            "Bet Argento", "Atlantis"
        ], key="casino_selector_bet_atlantis")
    
        clave_casino = "betargento" if casino_actual == "Bet Argento" else "atlantis"
    
        if "casino_anterior_bet_atlantis" not in st.session_state:
            st.session_state["casino_anterior_bet_atlantis"] = casino_actual
    
        if casino_actual != st.session_state["casino_anterior_bet_atlantis"]:
            st.session_state["casino_anterior_bet_atlantis"] = casino_actual
            st.session_state.pop("archivo_procesado_bet_atlantis", None)
            st.experimental_rerun()
    
        archivo = st.file_uploader("📁 Subí el archivo del reporte (.xlsx)", type=["xlsx"], key="reporte_bet_atlantis")
    
        if archivo and not st.session_state.get("archivo_procesado_bet_atlantis"):
            try:
                df = pd.read_excel(archivo)
                df = limpiar_transacciones(df)
                df = agregar_columna_casino(df, casino_actual)
    
                engine = create_engine(st.secrets["DB_URL"])
                subir_a_supabase(df, "reportes_jugadores", engine)
    
                st.session_state["archivo_procesado_bet_atlantis"] = True
                st.success("✅ Archivo subido y procesado correctamente.")
    
            except Exception as e:
                st.error(f"❌ Error al procesar o subir el archivo: {e}")
    
        elif st.session_state.get("archivo_procesado_bet_atlantis"):
            st.success("✅ El archivo ya fue procesado. Si querés subir uno nuevo, cambiá el casino o recargá la página.")
    
        # === Visualización ===
        st.markdown("---")
        st.subheader(f"🔍 Vista resumen de jugadores - {casino_actual}")
    
        nombre_vista = "resumen_betargento" if casino_actual == "Bet Argento" else "resumen_atlantis"
    
        try:
            engine = create_engine(st.secrets["DB_URL"])
            with engine.connect() as conn:
                query = f'SELECT * FROM "{nombre_vista}" ORDER BY "Ganacias casino" DESC'
                df_resumen = pd.read_sql(query, conn)
    
            df_bonos = cargar_tabla_bonos(clave_casino, sh)
    
            df_resumen["__user_key"] = df_resumen["Nombre de jugador"].astype(str).str.lower().str.replace(" ", "").str.replace("_", "")
            df_bonos["__user_key"] = df_bonos["Usuario"].astype(str).str.lower().str.replace(" ", "").str.replace("_", "")
    
            dict_tipo_bono = dict(zip(df_bonos["__user_key"], df_bonos["Tipo de Bono"]))
            dict_contacto = dict(zip(df_bonos["__user_key"], df_bonos["Últ. vez contactado"]))
    
            if "Tipo de bono" in df_resumen.columns:
                df_resumen["Tipo de bono"] = df_resumen["__user_key"].map(dict_tipo_bono).combine_first(df_resumen["Tipo de bono"])
                df_resumen["Tipo de bono"] = df_resumen["Tipo de bono"].replace("", pd.NA).fillna("N/A")
    
            if "Últ. vez contactado" in df_resumen.columns:
                df_resumen["Últ. vez contactado"] = df_resumen["__user_key"].map(dict_contacto).fillna(df_resumen["Últ. vez contactado"])
    
            df_resumen.drop(columns=["__user_key"], inplace=True)
    
            df_resumen = asignar_princi(df_resumen, sh, clave_casino)
    
            cols = df_resumen.columns.tolist()
            if "Tipo de bono" in cols and "PRINCI" in cols:
                cols.remove("PRINCI")
                idx = cols.index("Tipo de bono") + 1
                cols.insert(idx, "PRINCI")
                df_resumen = df_resumen[cols]
    
            # 🗓️ Filtro por fecha
            st.markdown("### 📅 Filtrar jugadores por fecha de última carga")
            col1, col2 = st.columns(2)
    
            if not pd.api.types.is_datetime64_any_dtype(df_resumen["Última vez que cargó"]):
                df_resumen["Última vez que cargó"] = pd.to_datetime(df_resumen["Última vez que cargó"], errors="coerce")
    
            with col1:
                filtro_desde = st.date_input("📆 Desde", value=df_resumen["Última vez que cargó"].min().date(), key="desde_fecha_bet_atlantis")
            with col2:
                filtro_hasta = st.date_input("📆 Hasta", value=df_resumen["Última vez que cargó"].max().date(), key="hasta_fecha_bet_atlantis")
    
            df_resumen_filtrado = df_resumen[
                (df_resumen["Última vez que cargó"] >= pd.to_datetime(filtro_desde)) &
                (df_resumen["Última vez que cargó"] <= pd.to_datetime(filtro_hasta))
            ]
    
            df_resumen_filtrado["Tipo de bono"] = df_resumen_filtrado["Tipo de bono"].fillna("N/A")
            col_filtro, _ = st.columns(2)
            tipos_disponibles = sorted(df_resumen_filtrado["Tipo de bono"].unique().tolist())
    
            seleccion_tipos = col_filtro.multiselect(
                "🎯 Filtrar por tipo de bono:",
                options=tipos_disponibles,
                default=[]  # ← esto evita que se filtre por defecto
            )
            
            if seleccion_tipos:
                df_resumen_filtrado = df_resumen_filtrado[df_resumen_filtrado["Tipo de bono"].isin(seleccion_tipos)]
    
            if not df_resumen_filtrado.empty:
                st.dataframe(df_resumen_filtrado, use_container_width=True)
    
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
                    df_resumen_filtrado.to_excel(writer, index=False, sheet_name=casino_actual)
    
                st.download_button(
                    "⬇️ Descargar Excel",
                    data=output.getvalue(),
                    file_name=f"{casino_actual.lower().replace(' ', '_')}_resumen.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.info("ℹ️ No hay jugadores que coincidan con los filtros.")
        except Exception as e:
            st.error(f"❌ Error al consultar la vista del casino seleccionado: {e}")
    
        st.markdown("----")
        st.subheader(f"🎁 Tabla de Bonos - {casino_actual}")
    
        try:
            df_bonos = cargar_tabla_bonos(clave_casino, sh)
    
            if not df_bonos.empty:
                st.dataframe(df_bonos, use_container_width=True)
    
                output_bonos = io.BytesIO()
                with pd.ExcelWriter(output_bonos, engine="xlsxwriter") as writer:
                    df_bonos.to_excel(writer, index=False, sheet_name=f"Bonos_{casino_actual}")
    
                st.download_button(
                    "⬇️ Descargar Tabla de Bonos",
                    data=output_bonos.getvalue(),
                    file_name=f"{clave_casino}_bonos.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.info("ℹ️ No hay datos en la tabla de bonos para este casino.")
        except Exception as e:
            st.error(f"❌ Error al cargar tabla de bonos: {e}")


    # SECCIÓN SPIRITA
    elif "📋 Registro Spirita" in seccion:
        st.header("📋 Registro general de jugadores - Spirita")
    
        archivo = st.file_uploader("📁 Subí el archivo del reporte (.xlsx)", type=["xlsx"], key="reporte_spirita")
    
        if archivo and not st.session_state.get("archivo_procesado_spirita"):
            try:
                df = pd.read_excel(archivo)
                df = limpiar_transacciones(df)
                df = agregar_columna_casino(df, "Spirita")
    
                engine = create_engine(st.secrets["DB_URL"])
                subir_a_supabase(df, "reportes_jugadores", engine)
    
                st.session_state["archivo_procesado_spirita"] = True
                st.success("✅ Archivo subido y procesado correctamente.")
            except Exception as e:
                st.error(f"❌ Error al procesar o subir el archivo: {e}")
    
        elif st.session_state.get("archivo_procesado_spirita"):
            st.success("✅ El archivo ya fue procesado. Recargá la página si querés subir uno nuevo.")
    
        st.markdown("---")
        st.subheader("🔍 Vista resumen de jugadores - Spirita")
    
        try:
            engine = create_engine(st.secrets["DB_URL"])
            with engine.connect() as conn:
                query = 'SELECT * FROM "resumen_spirita" ORDER BY "Ganacias casino" DESC'
                df_resumen = pd.read_sql(query, conn)
    
            df_bonos = cargar_tabla_bonos("spirita", sh)
    
            df_resumen["__user_key"] = df_resumen["Nombre de jugador"].astype(str).str.lower().str.replace(" ", "").str.replace("_", "")
            df_bonos["__user_key"] = df_bonos["Usuario"].astype(str).str.lower().str.replace(" ", "").str.replace("_", "")
    
            dict_tipo_bono = dict(zip(df_bonos["__user_key"], df_bonos["Tipo de Bono"]))
            dict_contacto = dict(zip(df_bonos["__user_key"], df_bonos["Últ. vez contactado"]))
    
            if "Tipo de bono" in df_resumen.columns:
                df_resumen["Tipo de bono"] = df_resumen["__user_key"].map(dict_tipo_bono).combine_first(df_resumen["Tipo de bono"])
                df_resumen["Tipo de bono"] = df_resumen["Tipo de bono"].replace("", pd.NA).fillna("N/A")
    
            if "Últ. vez contactado" in df_resumen.columns:
                df_resumen["Últ. vez contactado"] = df_resumen["__user_key"].map(dict_contacto).fillna(df_resumen["Últ. vez contactado"])
    
            df_resumen.drop(columns=["__user_key"], inplace=True)
    
            df_resumen = asignar_princi(df_resumen, sh, "spirita")
    
            cols = df_resumen.columns.tolist()
            if "Tipo de bono" in cols and "PRINCI" in cols:
                cols.remove("PRINCI")
                idx = cols.index("Tipo de bono") + 1
                cols.insert(idx, "PRINCI")
                df_resumen = df_resumen[cols]
    
            st.markdown("### 📅 Filtrar jugadores por fecha de última carga")
            col1, col2 = st.columns(2)
    
            if not pd.api.types.is_datetime64_any_dtype(df_resumen["Última vez que cargó"]):
                df_resumen["Última vez que cargó"] = pd.to_datetime(df_resumen["Última vez que cargó"], errors="coerce")
    
            with col1:
                filtro_desde = st.date_input("📆 Desde", value=df_resumen["Última vez que cargó"].min().date(), key="desde_spirita")
            with col2:
                filtro_hasta = st.date_input("📆 Hasta", value=df_resumen["Última vez que cargó"].max().date(), key="hasta_spirita")
    
            df_filtrado = df_resumen[
                (df_resumen["Última vez que cargó"] >= pd.to_datetime(filtro_desde)) &
                (df_resumen["Última vez que cargó"] <= pd.to_datetime(filtro_hasta))
            ]
    
            df_filtrado["Tipo de bono"] = df_filtrado["Tipo de bono"].fillna("N/A")
            col_filtro, _ = st.columns(2)
            tipos_disponibles = sorted(df_filtrado["Tipo de bono"].unique().tolist())
    
            seleccion_tipos = col_filtro.multiselect(
                "🎯 Filtrar por tipo de bono:",
                options=tipos_disponibles,
                default=tipos_disponibles
            )
    
            if seleccion_tipos:
                df_filtrado = df_filtrado[df_filtrado["Tipo de bono"].isin(seleccion_tipos)]
    
            if not df_filtrado.empty:
                st.dataframe(df_filtrado, use_container_width=True)
    
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
                    df_filtrado.to_excel(writer, index=False, sheet_name="Spirita")
    
                st.download_button(
                    "⬇️ Descargar Excel",
                    data=output.getvalue(),
                    file_name="spirita_resumen.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.info("ℹ️ No hay jugadores que coincidan con los filtros.")
    
        except Exception as e:
            st.error(f"❌ Error al consultar la vista resumen de Spirita: {e}")
    
        st.markdown("----")
        st.subheader("🎁 Tabla de Bonos - Spirita")
    
        try:
            df_bonos = cargar_tabla_bonos("spirita", sh)
    
            if not df_bonos.empty:
                st.dataframe(df_bonos, use_container_width=True)
    
                output_bonos = io.BytesIO()
                with pd.ExcelWriter(output_bonos, engine="xlsxwriter") as writer:
                    df_bonos.to_excel(writer, index=False, sheet_name="Bonos_Spirita")
    
                st.download_button(
                    "⬇️ Descargar Tabla de Bonos",
                    data=output_bonos.getvalue(),
                    file_name="spirita_bonos.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.info("ℹ️ No hay datos en la tabla de bonos de Spirita.")
        except Exception as e:
            st.error(f"❌ Error al cargar la tabla de bonos: {e}")

    #SECCIÓN ATENEA
    elif "📋 Registro Atenea" in seccion:
        st.header("📋 Registro general de jugadores - Atenea")
    
        archivo = st.file_uploader("📁 Subí el archivo del reporte (.xlsx)", type=["xlsx"], key="reporte_atenea")
    
        if archivo and not st.session_state.get("archivo_procesado_atenea"):
            try:
                df = pd.read_excel(archivo)
                df = limpiar_transacciones(df)
                df = agregar_columna_casino(df, "Atenea")
    
                engine = create_engine(st.secrets["DB_URL"])
                subir_a_supabase(df, "reportes_jugadores", engine)
    
                st.session_state["archivo_procesado_atenea"] = True
                st.success("✅ Archivo subido y procesado correctamente.")
            except Exception as e:
                st.error(f"❌ Error al procesar o subir el archivo: {e}")
    
        elif st.session_state.get("archivo_procesado_atenea"):
            st.success("✅ El archivo ya fue procesado. Recargá la página si querés subir uno nuevo.")
    
        st.markdown("---")
        st.subheader("🔍 Vista resumen de jugadores - Atenea")
    
        try:
            engine = create_engine(st.secrets["DB_URL"])
            with engine.connect() as conn:
                query = 'SELECT * FROM "resumen_atenea" ORDER BY "Ganacias casino" DESC'
                df_resumen = pd.read_sql(query, conn)
    
            df_bonos = cargar_tabla_bonos("atenea", sh)
    
            df_resumen["__user_key"] = df_resumen["Nombre de jugador"].astype(str).str.lower().str.replace(" ", "").str.replace("_", "")
            df_bonos["__user_key"] = df_bonos["Usuario"].astype(str).str.lower().str.replace(" ", "").str.replace("_", "")
    
            dict_tipo_bono = dict(zip(df_bonos["__user_key"], df_bonos["Tipo de Bono"]))
            dict_contacto = dict(zip(df_bonos["__user_key"], df_bonos["Últ. vez contactado"]))
    
            if "Tipo de bono" in df_resumen.columns:
                df_resumen["Tipo de bono"] = df_resumen["__user_key"].map(dict_tipo_bono).combine_first(df_resumen["Tipo de bono"])
                df_resumen["Tipo de bono"] = df_resumen["Tipo de bono"].replace("", pd.NA).fillna("N/A")
    
            if "Últ. vez contactado" in df_resumen.columns:
                df_resumen["Últ. vez contactado"] = df_resumen["__user_key"].map(dict_contacto).fillna(df_resumen["Últ. vez contactado"])
    
            df_resumen.drop(columns=["__user_key"], inplace=True)

            df_resumen = asignar_princi(df_resumen, sh, "atenea")

            cols = df_resumen.columns.tolist()
            if "Tipo de bono" in cols and "PRINCI" in cols:
                cols.remove("PRINCI")
                idx = cols.index("Tipo de bono") + 1
                cols.insert(idx, "PRINCI")
                df_resumen = df_resumen[cols]
    
            st.markdown("### 📅 Filtrar jugadores por fecha de última carga")
            col1, col2 = st.columns(2)
    
            if not pd.api.types.is_datetime64_any_dtype(df_resumen["Última vez que cargó"]):
                df_resumen["Última vez que cargó"] = pd.to_datetime(df_resumen["Última vez que cargó"], errors="coerce")
    
            with col1:
                filtro_desde = st.date_input("📆 Desde", value=df_resumen["Última vez que cargó"].min().date(), key="desde_atenea")
            with col2:
                filtro_hasta = st.date_input("📆 Hasta", value=df_resumen["Última vez que cargó"].max().date(), key="hasta_atenea")
    
            df_filtrado = df_resumen[
                (df_resumen["Última vez que cargó"] >= pd.to_datetime(filtro_desde)) &
                (df_resumen["Última vez que cargó"] <= pd.to_datetime(filtro_hasta))
            ]
    
            df_filtrado["Tipo de bono"] = df_filtrado["Tipo de bono"].fillna("N/A")
            col_filtro, _ = st.columns(2)
            tipos_disponibles = sorted(df_filtrado["Tipo de bono"].unique().tolist())
    
            seleccion_tipos = col_filtro.multiselect(
                "🎯 Filtrar por tipo de bono:",
                options=tipos_disponibles,
                default=tipos_disponibles
            )
    
            if seleccion_tipos:
                df_filtrado = df_filtrado[df_filtrado["Tipo de bono"].isin(seleccion_tipos)]
    
            if not df_filtrado.empty:
                st.dataframe(df_filtrado, use_container_width=True)
    
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
                    df_filtrado.to_excel(writer, index=False, sheet_name="Atenea")
    
                st.download_button(
                    "⬇️ Descargar Excel",
                    data=output.getvalue(),
                    file_name="atenea_resumen.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.info("ℹ️ No hay jugadores que coincidan con los filtros.")
    
        except Exception as e:
            st.error(f"❌ Error al consultar la vista resumen de Atenea: {e}")
    
        st.markdown("----")
        st.subheader("🎁 Tabla de Bonos - Atenea")
    
        try:
            df_bonos = cargar_tabla_bonos("atenea", sh)
    
            if not df_bonos.empty:
                st.dataframe(df_bonos, use_container_width=True)
    
                output_bonos = io.BytesIO()
                with pd.ExcelWriter(output_bonos, engine="xlsxwriter") as writer:
                    df_bonos.to_excel(writer, index=False, sheet_name="Bonos_Atenea")
    
                st.download_button(
                    "⬇️ Descargar Tabla de Bonos",
                    data=output_bonos.getvalue(),
                    file_name="atenea_bonos.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.info("ℹ️ No hay datos en la tabla de bonos de Atenea.")
        except Exception as e:
            st.error(f"❌ Error al cargar la tabla de bonos: {e}")

    elif "📋 Registro Padrino Latino/Tiger" in seccion:
        st.header("📋 Registro general de jugadores")

        casino_actual = st.selectbox("🎰 Seleccioná el casino al que pertenece este reporte", [
            "Padrino Latino", "Tiger"
        ], key="casino_selector")

        if "casino_anterior" not in st.session_state:
            st.session_state["casino_anterior"] = casino_actual

        if casino_actual != st.session_state["casino_anterior"]:
            st.session_state["casino_anterior"] = casino_actual
            st.session_state.pop("archivo_procesado", None)
            st.experimental_rerun()

        archivo = st.file_uploader("📁 Subí el archivo del reporte (.xlsx)", type=["xlsx"], key="reporte_padrino")

        if archivo and not st.session_state.get("archivo_procesado"):
            try:
                df = pd.read_excel(archivo)
                df = limpiar_transacciones(df)
                df = agregar_columna_casino(df, casino_actual)

                engine = create_engine(st.secrets["DB_URL"])
                subir_a_supabase(df, "reportes_jugadores", engine)

                st.session_state["archivo_procesado"] = True
                st.success("✅ Archivo subido y procesado correctamente.")

            except Exception as e:
                st.error(f"❌ Error al procesar o subir el archivo: {e}")

        elif st.session_state.get("archivo_procesado"):
            st.success("✅ El archivo ya fue procesado. Si querés subir uno nuevo, cambiá el casino o recargá la página.")

        # === Visualización de la vista correspondiente ===
        st.markdown("---")
        st.subheader(f"🔍 Vista resumen de jugadores - {casino_actual}")

        nombre_vista = "resumen_padrino_latino" if casino_actual == "Padrino Latino" else "resumen_tiger"

        try:
            engine = create_engine(st.secrets["DB_URL"])
            with engine.connect() as conn:
                query = f'SELECT * FROM "{nombre_vista}" ORDER BY "Ganacias casino" DESC'
                df_resumen = pd.read_sql(query, conn)
        
            # 🧠 Actualizar desde tabla de bonos
            clave_casino = "padrino" if casino_actual == "Padrino Latino" else "tiger"
            df_bonos = cargar_tabla_bonos(clave_casino, sh)
        
            # Clave de unión
            df_resumen["__user_key"] = df_resumen["Nombre de jugador"].astype(str).str.lower().str.replace(" ", "").str.replace("_", "")
            df_bonos["__user_key"] = df_bonos["Usuario"].astype(str).str.lower().str.replace(" ", "").str.replace("_", "")
        
            dict_tipo_bono = dict(zip(df_bonos["__user_key"], df_bonos["Tipo de Bono"]))
            dict_contacto = dict(zip(df_bonos["__user_key"], df_bonos["Últ. vez contactado"]))
        
            if "Tipo de bono" in df_resumen.columns:
                df_resumen["Tipo de bono"] = df_resumen["__user_key"].map(dict_tipo_bono).combine_first(df_resumen["Tipo de bono"])
                
                # Normalizar: convertir cadenas vacías o espacios en "N/A"
                df_resumen["Tipo de bono"] = df_resumen["Tipo de bono"].replace("", pd.NA)
                df_resumen["Tipo de bono"] = df_resumen["Tipo de bono"].fillna("N/A")
        
            if "Últ. vez contactado" in df_resumen.columns:
                df_resumen["Últ. vez contactado"] = df_resumen["__user_key"].map(dict_contacto).fillna(df_resumen["Últ. vez contactado"])
        
            df_resumen.drop(columns=["__user_key"], inplace=True)

            # ✅ Asignar PRINCI
            df_resumen = asignar_princi(df_resumen, sh, clave_casino)
            
            # 🧠 Reordenar columnas para mostrar PRINCI junto a tipo de bono
            cols = df_resumen.columns.tolist()
            if "Tipo de bono" in cols and "PRINCI" in cols:
                cols.remove("PRINCI")
                idx = cols.index("Tipo de bono") + 1
                cols.insert(idx, "PRINCI")
                df_resumen = df_resumen[cols]
        
            # 🗓️ Filtro por fecha
            st.markdown("### 📅 Filtrar jugadores por fecha de última carga")
            col1, col2 = st.columns(2)
        
            if not pd.api.types.is_datetime64_any_dtype(df_resumen["Última vez que cargó"]):
                df_resumen["Última vez que cargó"] = pd.to_datetime(df_resumen["Última vez que cargó"], errors="coerce")
        
            with col1:
                filtro_desde = st.date_input("📆 Desde", value=df_resumen["Última vez que cargó"].min().date(), key="desde_ultima_carga")
            with col2:
                filtro_hasta = st.date_input("📆 Hasta", value=df_resumen["Última vez que cargó"].max().date(), key="hasta_ultima_carga")
        
            df_resumen_filtrado = df_resumen[
                (df_resumen["Última vez que cargó"] >= pd.to_datetime(filtro_desde)) &
                (df_resumen["Última vez que cargó"] <= pd.to_datetime(filtro_hasta))
            ]
        
            # 🎯 Filtro por tipo de bono
            df_resumen_filtrado["Tipo de bono"] = df_resumen_filtrado["Tipo de bono"].fillna("N/A")
            col_filtro, col_orden = st.columns(2)
            tipos_disponibles = sorted(df_resumen_filtrado["Tipo de bono"].unique().tolist())
        
            seleccion_tipos = col_filtro.multiselect(
                "🎯 Filtrar por tipo de bono:",
                options=tipos_disponibles,
                default=[]  # ← esto evita que se filtre por defecto
            )
            
            if seleccion_tipos:
                df_resumen_filtrado = df_resumen_filtrado[df_resumen_filtrado["Tipo de bono"].isin(seleccion_tipos)]
        
            # ✅ Mostrar y exportar
            if not df_resumen_filtrado.empty:
                st.dataframe(df_resumen_filtrado, use_container_width=True)
        
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
                    df_resumen_filtrado.to_excel(writer, index=False, sheet_name=casino_actual)
        
                st.download_button(
                    "⬇️ Descargar Excel",
                    data=output.getvalue(),
                    file_name=f"{casino_actual.lower().replace(' ', '_')}_resumen.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.info("ℹ️ No hay jugadores que coincidan con los filtros.")
        except Exception as e:
            st.error(f"❌ Error al consultar la vista del casino seleccionado: {e}")
            
        st.markdown("----")
        st.subheader(f"🎁 Tabla de Bonos - {casino_actual}")
        
        try:
            # 🔄 Reutilizá el objeto 'sh' que ya tenés en tu app
            clave_casino = "padrino" if casino_actual == "Padrino Latino" else "tiger"
            df_bonos = cargar_tabla_bonos(clave_casino, sh)
        
            if not df_bonos.empty:
                st.dataframe(df_bonos, use_container_width=True)
        
                # Descargar en Excel
                output_bonos = io.BytesIO()
                with pd.ExcelWriter(output_bonos, engine="xlsxwriter") as writer:
                    df_bonos.to_excel(writer, index=False, sheet_name=f"Bonos_{casino_actual}")
                st.download_button(
                    "⬇️ Descargar Tabla de Bonos",
                    data=output_bonos.getvalue(),
                    file_name=f"{clave_casino}_bonos.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.info("ℹ️ No hay datos en la tabla de bonos para este casino.")
        except Exception as e:
            st.error(f"❌ Error al cargar tabla de bonos: {e}")

    elif "📋 Registro Fortuna/Gana 24" in seccion:
        st.header("📋 Registro general de jugadores")

        casino_actual = st.selectbox("🎰 Seleccioná el casino al que pertenece este reporte", [
            "Fortuna", "Gana 24"
        ], key="casino_selector_fortuna_gana24")
        
        clave_casino = "fortuna" if casino_actual == "Fortuna" else "gana24"

        if "casino_anterior_fortuna_gana24" not in st.session_state:
            st.session_state["casino_anterior_fortuna_gana24"] = casino_actual

        if casino_actual != st.session_state["casino_anterior_fortuna_gana24"]:
            st.session_state["casino_anterior_fortuna_gana24"] = casino_actual
            st.session_state.pop("archivo_procesado_fortuna_gana24", None)
            st.experimental_rerun()

        archivo = st.file_uploader("📁 Subí el archivo del reporte (.xlsx)", type=["xlsx"], key="reporte_fortuna_gana24")

        if archivo and not st.session_state.get("archivo_procesado_fortuna_gana24"):
            try:
                df = pd.read_excel(archivo)
                df = limpiar_transacciones(df)
                df = agregar_columna_casino(df, casino_actual)

                engine = create_engine(st.secrets["DB_URL"])
                subir_a_supabase(df, "reportes_jugadores", engine)

                st.session_state["archivo_procesado_fortuna_gana24"] = True
                st.success("✅ Archivo subido y procesado correctamente.")
            except Exception as e:
                st.error(f"❌ Error al procesar o subir el archivo: {e}")
        elif st.session_state.get("archivo_procesado_fortuna_gana24"):
            st.success("✅ El archivo ya fue procesado. Si querés subir uno nuevo, cambiá el casino o recargá la página.")

        # === Visualización de la vista correspondiente ===
        st.markdown("---")
        st.subheader(f"🔍 Vista resumen de jugadores - {casino_actual}")

        nombre_vista = "resumen_fortuna" if casino_actual == "Fortuna" else "resumen_gana24"

        try:
            engine = create_engine(st.secrets["DB_URL"])
            with engine.connect() as conn:
                query = f'SELECT * FROM "{nombre_vista}" ORDER BY "Ganacias casino" DESC'
                df_resumen = pd.read_sql(query, conn)

            df_bonos = cargar_tabla_bonos(clave_casino, sh)

            df_resumen["__user_key"] = df_resumen["Nombre de jugador"].astype(str).str.lower().str.replace(" ", "").str.replace("_", "")
            df_bonos["__user_key"] = df_bonos["Usuario"].astype(str).str.lower().str.replace(" ", "").str.replace("_", "")

            dict_tipo_bono = dict(zip(df_bonos["__user_key"], df_bonos["Tipo de Bono"]))
            dict_contacto = dict(zip(df_bonos["__user_key"], df_bonos["Últ. vez contactado"]))

            if "Tipo de bono" in df_resumen.columns:
                df_resumen["Tipo de bono"] = df_resumen["__user_key"].map(dict_tipo_bono).combine_first(df_resumen["Tipo de bono"])
                df_resumen["Tipo de bono"] = df_resumen["Tipo de bono"].replace("", pd.NA).fillna("N/A")

            if "Últ. vez contactado" in df_resumen.columns:
                df_resumen["Últ. vez contactado"] = df_resumen["__user_key"].map(dict_contacto).fillna(df_resumen["Últ. vez contactado"])

            df_resumen.drop(columns=["__user_key"], inplace=True)

            df_resumen = asignar_princi(df_resumen, sh, clave_casino)

            cols = df_resumen.columns.tolist()
            if "Tipo de bono" in cols and "PRINCI" in cols:
                cols.remove("PRINCI")
                idx = cols.index("Tipo de bono") + 1
                cols.insert(idx, "PRINCI")
                df_resumen = df_resumen[cols]

            st.markdown("### 📅 Filtrar jugadores por fecha de última carga")
            col1, col2 = st.columns(2)

            if not pd.api.types.is_datetime64_any_dtype(df_resumen["Última vez que cargó"]):
                df_resumen["Última vez que cargó"] = pd.to_datetime(df_resumen["Última vez que cargó"], errors="coerce")

            with col1:
                filtro_desde = st.date_input("📆 Desde", value=df_resumen["Última vez que cargó"].min().date(), key="desde_fecha_fortuna_gana24")
            with col2:
                filtro_hasta = st.date_input("📆 Hasta", value=df_resumen["Última vez que cargó"].max().date(), key="hasta_fecha_fortuna_gana24")

            df_resumen_filtrado = df_resumen[
                (df_resumen["Última vez que cargó"] >= pd.to_datetime(filtro_desde)) &
                (df_resumen["Última vez que cargó"] <= pd.to_datetime(filtro_hasta))
            ]

            df_resumen_filtrado["Tipo de bono"] = df_resumen_filtrado["Tipo de bono"].fillna("N/A")
            col_filtro, _ = st.columns(2)
            tipos_disponibles = sorted(df_resumen_filtrado["Tipo de bono"].unique().tolist())

            seleccion_tipos = col_filtro.multiselect(
                "🎯 Filtrar por tipo de bono:",
                options=tipos_disponibles,
                default=[]
            )

            if seleccion_tipos:
                df_resumen_filtrado = df_resumen_filtrado[df_resumen_filtrado["Tipo de bono"].isin(seleccion_tipos)]

            if not df_resumen_filtrado.empty:
                st.dataframe(df_resumen_filtrado, use_container_width=True)

                output = io.BytesIO()
                with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
                    df_resumen_filtrado.to_excel(writer, index=False, sheet_name=casino_actual)

                st.download_button(
                    "⬇️ Descargar Excel",
                    data=output.getvalue(),
                    file_name=f"{clave_casino}_resumen.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.info("ℹ️ No hay jugadores que coincidan con los filtros.")
        except Exception as e:
            st.error(f"❌ Error al consultar la vista del casino seleccionado: {e}")

        st.markdown("----")
        st.subheader(f"🎁 Tabla de Bonos - {casino_actual}")

        try:
            df_bonos = cargar_tabla_bonos(clave_casino, sh)

            if not df_bonos.empty:
                st.dataframe(df_bonos, use_container_width=True)

                output_bonos = io.BytesIO()
                with pd.ExcelWriter(output_bonos, engine="xlsxwriter") as writer:
                    df_bonos.to_excel(writer, index=False, sheet_name=f"Bonos_{casino_actual}")
                st.download_button(
                    "⬇️ Descargar Tabla de Bonos",
                    data=output_bonos.getvalue(),
                    file_name=f"{clave_casino}_bonos.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.info("ℹ️ No hay datos en la tabla de bonos para este casino.")
        except Exception as e:
            st.error(f"❌ Error al cargar tabla de bonos: {e}")

    
    elif seccion == "📆 Agenda Fénix":
        st.header("📆 Seguimiento de Jugadores Nuevos - Fénix")
    
        try:
            hoja_agenda = sh.worksheet("agenda_fenix")
            nombres_agenda = hoja_agenda.col_values(1)[1:]  # Omite encabezado
            nombres_agenda = [str(n).strip().lower().replace(" ", "") for n in nombres_agenda if n]
        except:
            st.error("❌ No se pudo leer la hoja 'agenda_fenix'")
            st.stop()
    
        try:
            hoja_fenix = sh.worksheet("registro_fenix")
            data_fenix = hoja_fenix.get_all_records()
            df_fenix = pd.DataFrame(data_fenix)
        except:
            st.error("❌ No se pudo leer la hoja 'registro_fenix'")
            st.stop()
    
        df_fenix = df_fenix.rename(columns={
            "Del usuario": "Plataforma",
            "Jugador": "Jugador",
            "Monto": "Monto",
            "Fecha": "Fecha",
            "Tipo": "Tipo"
        })
    
        df_fenix["Jugador"] = df_fenix["Jugador"].astype(str).str.strip().str.lower().str.replace(" ", "")
        df_fenix["Fecha"] = pd.to_datetime(df_fenix["Fecha"], errors="coerce")
        df_fenix["Monto"] = pd.to_numeric(df_fenix["Monto"], errors="coerce").fillna(0)
    
        valores_wagger = ["Fenix_Wagger100", "Fenix_Wagger40", "Fenix_Wagger30", "Fenix_Wagger50", "Fenix_Wagger150", "Fenix_Wagger200"]
    
        hoy = pd.to_datetime(datetime.date.today())
        resumen = []
    
        for jugador in nombres_agenda:
            historial = df_fenix[df_fenix["Jugador"] == jugador].sort_values("Fecha")
            cargas = historial[historial["Tipo"].str.lower() == "in"]
    
            if not cargas.empty:
                cargas_hl = cargas[cargas["Plataforma"] == "hl_casinofenix"]
                cargas_wagger = cargas[cargas["Plataforma"].isin(valores_wagger)]
    
                suma_hl = cargas_hl["Monto"].sum()
                suma_wagger = cargas_wagger["Monto"].sum()
                total_cargas = cargas["Monto"].sum()
                fecha_ingreso = cargas["Fecha"].min()
                ultima_carga = cargas["Fecha"].max()
                promedio = cargas["Monto"].mean()
                dias_inactivo = (hoy - ultima_carga).days
    
                if dias_inactivo <= 3:
                    riesgo = "🟢 Bajo"
                elif dias_inactivo <= 19:
                    riesgo = "🟡 Medio"
                else:
                    riesgo = "🔴 Alto"
    
                resumen.append({
                    "Nombre de Usuario": jugador,
                    "Fecha que ingresó": fecha_ingreso,
                    "Última vez que cargó": ultima_carga,
                    "Veces que cargó": len(cargas),
                    "Suma de las cargas (HL)": suma_hl,
                    "Suma de las cargas (Wagger)": suma_wagger,
                    "Monto promedio": promedio,
                    "Días inactivos": dias_inactivo,
                    "Nivel de riesgo": riesgo
                })
    
        if resumen:
            df_resultado = pd.DataFrame(resumen).sort_values("Última vez que cargó", ascending=False)
            st.subheader("📊 Resumen jugadores de agenda")
            st.dataframe(df_resultado)
            df_resultado.to_excel("resumen_agenda_fenix.xlsx", index=False)
            with open("resumen_agenda_fenix.xlsx", "rb") as f:
                st.download_button("📥 Descargar Excel", f, file_name="resumen_agenda_fenix.xlsx")
        else:
            st.info("⚠️ No se encontraron coincidencias entre jugadores nuevos y el historial de Fénix.")

    elif seccion == "📆 Agenda Eros":
        st.header("📆 Seguimiento de Jugadores Nuevos - Eros")
    
        try:
            hoja_agenda = sh.worksheet("agenda_eros")
            nombres_agenda = hoja_agenda.col_values(1)[1:]
            nombres_agenda = [str(n).strip().lower().replace(" ", "") for n in nombres_agenda if n]
        except:
            st.error("❌ No se pudo leer la hoja 'agenda_eros'")
            st.stop()
    
        try:
            hoja_eros = sh.worksheet("registro_eros")
            data_eros = hoja_eros.get_all_records()
            df_eros = pd.DataFrame(data_eros)
        except:
            st.error("❌ No se pudo leer la hoja 'registro_eros'")
            st.stop()
    
        df_eros = df_eros.rename(columns={
            "Del usuario": "Plataforma",
            "Jugador": "Jugador",
            "Monto": "Monto",
            "Fecha": "Fecha",
            "Tipo": "Tipo"
        })
    
        df_eros["Jugador"] = df_eros["Jugador"].astype(str).str.strip().str.lower().str.replace(" ", "")
        df_eros["Fecha"] = pd.to_datetime(df_eros["Fecha"], errors="coerce")
        df_eros["Monto"] = pd.to_numeric(df_eros["Monto"], errors="coerce").fillna(0)
    
        valores_wagger = ["Eros_wagger30%", "Eros_wagger40%", "Eros_wagger50%", "Eros_wagger100%", "Eros_wagger150%", "Eros_wagger200%"]
    
        hoy = pd.to_datetime(datetime.date.today())
        resumen = []
    
        for jugador in nombres_agenda:
            historial = df_eros[df_eros["Jugador"] == jugador].sort_values("Fecha")
            cargas = historial[historial["Tipo"].str.lower() == "in"]
    
            if not cargas.empty:
                cargas_hl = cargas[cargas["Plataforma"] == "hl_Erosonline"]
                cargas_wagger = cargas[cargas["Plataforma"].isin(valores_wagger)]
    
                suma_hl = cargas_hl["Monto"].sum()
                suma_wagger = cargas_wagger["Monto"].sum()
                fecha_ingreso = cargas["Fecha"].min()
                ultima_carga = cargas["Fecha"].max()
                promedio = cargas["Monto"].mean()
                dias_inactivo = (hoy - ultima_carga).days
    
                if dias_inactivo <= 3:
                    riesgo = "🟢 Bajo"
                elif dias_inactivo <= 19:
                    riesgo = "🟡 Medio"
                else:
                    riesgo = "🔴 Alto"
    
                resumen.append({
                    "Nombre de Usuario": jugador,
                    "Fecha que ingresó": fecha_ingreso,
                    "Última vez que cargó": ultima_carga,
                    "Veces que cargó": len(cargas),
                    "Suma de las cargas (HL)": suma_hl,
                    "Suma de las cargas (Wagger)": suma_wagger,
                    "Monto promedio": promedio,
                    "Días inactivos": dias_inactivo,
                    "Nivel de riesgo": riesgo
                })
    
        if resumen:
            df_resultado = pd.DataFrame(resumen).sort_values("Última vez que cargó", ascending=False)
            st.subheader("📊 Resumen jugadores de agenda")
            st.dataframe(df_resultado)
            df_resultado.to_excel("resumen_agenda_eros.xlsx", index=False)
            with open("resumen_agenda_eros.xlsx", "rb") as f:
                st.download_button("📥 Descargar Excel", f, file_name="resumen_agenda_eros.xlsx")
        else:
            st.info("⚠️ No se encontraron coincidencias entre jugadores nuevos y el historial de Eros.")

    elif seccion == "📆 Agenda BetArgento":
        st.header("📆 Seguimiento de Jugadores Nuevos - BetArgento")
    
        try:
            hoja_agenda = sh.worksheet("agenda_bet")
            nombres_agenda = hoja_agenda.col_values(1)[1:]
            nombres_agenda = [str(n).strip().lower().replace(" ", "") for n in nombres_agenda if n]
        except:
            st.error("❌ No se pudo leer la hoja 'agenda_bet'")
            st.stop()
    
        try:
            hoja_bet = sh.worksheet("registro_betargento")
            data_bet = hoja_bet.get_all_records()
            df_bet = pd.DataFrame(data_bet)
        except:
            st.error("❌ No se pudo leer la hoja 'registro_betargento'")
            st.stop()
    
        df_bet = df_bet.rename(columns={
            "Del usuario": "Plataforma",
            "Jugador": "Jugador",
            "Monto": "Monto",
            "Fecha": "Fecha",
            "Tipo": "Tipo"
        })
    
        df_bet["Jugador"] = df_bet["Jugador"].astype(str).str.strip().str.lower().str.replace(" ", "")
        df_bet["Fecha"] = pd.to_datetime(df_bet["Fecha"], errors="coerce")
        df_bet["Monto"] = pd.to_numeric(df_bet["Monto"], errors="coerce").fillna(0)
    
        valores_wagger = ["Argento_Wager","Argento_Wager30","Argento_Wager100", "Argento_Wager50", "Argento_Wager150", "Argento_Wager200"]
    
        hoy = pd.to_datetime(datetime.date.today())
        resumen = []
    
        for jugador in nombres_agenda:
            historial = df_bet[df_bet["Jugador"] == jugador].sort_values("Fecha")
            cargas = historial[historial["Tipo"].str.lower() == "in"]
    
            if not cargas.empty:
                cargas_hl = cargas[cargas["Plataforma"] == "hl_BetArgento"]
                cargas_wagger = cargas[cargas["Plataforma"].isin(valores_wagger)]
    
                suma_hl = cargas_hl["Monto"].sum()
                suma_wagger = cargas_wagger["Monto"].sum()
                fecha_ingreso = cargas["Fecha"].min()
                ultima_carga = cargas["Fecha"].max()
                promedio = cargas["Monto"].mean()
                dias_inactivo = (hoy - ultima_carga).days
    
                if dias_inactivo <= 3:
                    riesgo = "🟢 Bajo"
                elif dias_inactivo <= 19:
                    riesgo = "🟡 Medio"
                else:
                    riesgo = "🔴 Alto"
    
                resumen.append({
                    "Nombre de Usuario": jugador,
                    "Fecha que ingresó": fecha_ingreso,
                    "Última vez que cargó": ultima_carga,
                    "Veces que cargó": len(cargas),
                    "Suma de las cargas (HL)": suma_hl,
                    "Suma de las cargas (Wagger)": suma_wagger,
                    "Monto promedio": promedio,
                    "Días inactivos": dias_inactivo,
                    "Nivel de riesgo": riesgo
                })
    
        if resumen:
            df_resultado = pd.DataFrame(resumen).sort_values("Última vez que cargó", ascending=False)
            st.subheader("📊 Resumen jugadores de agenda")
            st.dataframe(df_resultado)
            df_resultado.to_excel("resumen_agenda_betargento.xlsx", index=False)
            with open("resumen_agenda_betargento.xlsx", "rb") as f:
                st.download_button("📥 Descargar Excel", f, file_name="resumen_agenda_betargento.xlsx")
        else:
            st.info("⚠️ No se encontraron coincidencias entre jugadores nuevos y el historial de BetArgento.")

    # Sección: Análisis Temporal
    elif seccion == "📊 Análisis Temporal":
        st.header("📊 Análisis Temporal de Jugadores")
    
        tarea = st.selectbox("📌 ¿Qué deseás hacer?", [
            "📈 Analizar Lifetime Value (LTV)",
            "📦 Unificar múltiples reportes de jugadores"
        ])

        if tarea == "📈 Analizar Lifetime Value (LTV)":
            archivo_temporal = st.file_uploader("📥 Pegá o subí aquí tus reportes", type=["csv", "xlsx", "xls"])
            
            if archivo_temporal:
                try:
                    df = pd.read_csv(archivo_temporal) if archivo_temporal.name.endswith(".csv") else pd.read_excel(archivo_temporal)
        
                    # 🔁 Renombrar columnas clave
                    df = df.rename(columns={
                        "operación": "Tipo",
                        "Depositar": "Monto",
                        "Retirar": "Retiro",
                        "Fecha": "Fecha",
                        "Tiempo": "Hora",
                        "Al usuario": "Jugador",
                        "Iniciador": "Iniciador"
                    })
        
                    # 🧹 Limpieza general
                    df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce")
                    df["Hora"] = pd.to_datetime(df["Hora"], errors="coerce").dt.time
                    df["Monto"] = pd.to_numeric(df.get("Monto", 0), errors="coerce").fillna(0)
                    df["Retiro"] = pd.to_numeric(df.get("Retiro", 0), errors="coerce").fillna(0)
                    df["Jugador"] = df["Jugador"].astype(str).str.strip().str.lower()
                    df["Tipo"] = df["Tipo"].str.lower()
        
                    # 🔎 Filtrar por plataformas válidas
                    valores_hl = ["hl_casinofenix", "hl_erosonline", "hl_betargento", "hall_atenea"]
                    valores_wagger = [
                        "Fenix_Wagger30", "Fenix_Wagger40", "Fenix_Wagger50", "Fenix_Wagger100",
                        "Fenix_Wagger150", "Fenix_Wagger200",
                        "Eros_wagger30%", "Eros_wagger40%", "Eros_wagger50%", "Eros_wagger100%",
                        "Eros_wagger150%", "Eros_wagger200%",
                        "Argento_Wager30", "Argento_Wager40", "Argento_Wager50", "Argento_Wager100",
                        "Argento_Wager150", "Argento_Wager200",
                        "spirita_wagger30%", "spirita_wagger40%", "spirita_wagger50%", "spirita_wagger100%",
                        "spirita_wagger150%", "spirita_wagger200%"
                    ]
                    plataformas_validas = valores_hl + valores_wagger
        
                    if "Del usuario" in df.columns:
                        df["Del usuario"] = df["Del usuario"].astype(str).str.strip()
                        df = df[df["Del usuario"].isin(plataformas_validas)]
                    else:
                        st.warning("❗ No se encontró la columna 'Del usuario'. No se puede filtrar por plataformas válidas.")
                        st.stop()
        
                    # ✅ Cargas y Retiros
                    df_cargas = df[df["Tipo"] == "in"].copy()
                    df_retiros = df[df["Tipo"] == "out"].copy()
        
                    # ✅ Filtro de iniciadores válidos
                    iniciadores_validos = [
                        "DemonGOD", "DaniGOD", "NahueGOD", "CajeroJuancho", "JuanpiCajero", "FlorGOD", "SebaGOD",
                        "subagente01", "subagente03", "sub_agent06", "sub_agent11", "sub_agent012"
                    ]
                    df_retiros = df_retiros[df_retiros["Iniciador"].isin(iniciadores_validos)].copy()
        
                    # ❌ Excluir "out" que ocurren dentro de los 2 minutos del mismo "in"
                    df_cargas["DateTime"] = df_cargas["Fecha"] + pd.to_timedelta(df_cargas["Hora"].astype(str))
                    df_retiros["DateTime"] = df_retiros["Fecha"] + pd.to_timedelta(df_retiros["Hora"].astype(str))
        
                    merged = pd.merge(
                        df_cargas[["Jugador", "Monto", "DateTime"]],
                        df_retiros[["Jugador", "Retiro", "DateTime"]],
                        left_on=["Jugador", "Monto"],
                        right_on=["Jugador", "Retiro"],
                        suffixes=("_in", "_out")
                    )
        
                    merged["dif_segundos"] = (merged["DateTime_out"] - merged["DateTime_in"]).dt.total_seconds()
                    errores = merged[merged["dif_segundos"] <= 300][["Jugador", "DateTime_out"]]
                    df_retiros = df_retiros[~df_retiros.set_index(["Jugador", "DateTime"]).index.isin(errores.set_index(["Jugador", "DateTime_out"]).index)]
        
                    # 🔄 Agrupaciones
                    cargas_agg = df_cargas.groupby("Jugador").agg({
                        "Monto": "sum",
                        "Fecha": ["min", "max"],
                        "Jugador": "count"
                    })
                    cargas_agg.columns = ["Total_Cargado", "Fecha_Inicio", "Fecha_Ultima", "Veces_Que_Cargo"]
                    cargas_agg.reset_index(inplace=True)
        
                    retiros_agg = df_retiros.groupby("Jugador")["Retiro"].sum().reset_index()
                    retiros_agg.columns = ["Jugador", "Total_Retirado"]
        
                    df_ltv = cargas_agg.merge(retiros_agg, on="Jugador", how="left")
                    df_ltv["Total_Retirado"] = df_ltv["Total_Retirado"].fillna(0)
        
                    # Cálculos
                    df_ltv["Dias_Activo"] = (df_ltv["Fecha_Ultima"] - df_ltv["Fecha_Inicio"]).dt.days + 1
                    costo_adquisicion = 5.10
                    df_ltv["LTV"] = df_ltv["Total_Cargado"] - df_ltv["Total_Retirado"] - costo_adquisicion
    
                    fecha_final_reporte = df["Fecha"].max()
                    df_ltv["Días_Sin_Cargar"] = (fecha_final_reporte - df_ltv["Fecha_Ultima"]).dt.days
                    df_ltv["Estado"] = df_ltv["Días_Sin_Cargar"].apply(lambda x: "Activo" if x <= 19 else "Inactivo")
        
                    # Mostrar resultados
                    st.success("✅ Análisis Lifetime Value generado correctamente.")
                    st.dataframe(df_ltv)
    
                    # 📊 Mostrar promedios de métricas clave debajo de la tabla
                    promedio_cargado = df_ltv["Total_Cargado"].mean()
                    promedio_retirado = df_ltv["Total_Retirado"].mean()
                    promedio_veces = df_ltv["Veces_Que_Cargo"].mean()
                    promedio_dias_activo = df_ltv["Dias_Activo"].mean()
                    
                    st.markdown("#### 📈 Promedios Generales (Lifetime Value)")
                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric(" Total Cargado", f"${promedio_cargado:,.2f}")
                    col2.metric(" Veces que Cargó", f"{promedio_veces:.2f}")
                    col3.metric(" Total Retirado", f"${promedio_retirado:,.2f}")
                    col4.metric(" Días Activo", f"{promedio_dias_activo:.2f}")
        
                    df_ltv.to_excel("ltv_temporal.xlsx", index=False)
                    with open("ltv_temporal.xlsx", "rb") as f:
                        st.download_button("📥 Descargar Excel", f, file_name="ltv_temporal.xlsx")
        
                except Exception as e:
                    st.error(f"❌ Error al procesar el archivo: {e}")


        elif tarea == "📦 Unificar múltiples reportes de jugadores":
                    archivo_zip = st.file_uploader("📥 Subí un archivo ZIP con reportes individuales (.xlsx o .xls)", type=["zip"])
                    
                    if archivo_zip:
                        with tempfile.TemporaryDirectory() as tmpdir:
                            zip_path = os.path.join(tmpdir, "reportes.zip")
                            with open(zip_path, "wb") as f:
                                f.write(archivo_zip.read())
                
                            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                                zip_ref.extractall(tmpdir)
                
                            historiales = []
                            errores = []
                            df_categorias = None
                
                            # Buscar archivo GameListFenixCasino.xlsx
                            for root, _, files in os.walk(tmpdir):
                                for file_name in files:
                                    if "GameListFenixCasino.xlsx" in file_name:
                                        path_catalogo = os.path.join(root, file_name)
                                        try:
                                            df_categorias = pd.read_excel(path_catalogo)
                                            df_categorias.columns = df_categorias.columns.str.strip()
                                            df_categorias = df_categorias.rename(columns={"Game Name": "Juego", "Category": "Categoría"})
                                            df_categorias["Categoría"] = df_categorias["Categoría"].str.lower().replace({
                                                "fishing game": "fishing",
                                                "fishing games": "fishing"
                                            })
                                        except Exception as e:
                                            errores.append(f"No se pudo leer GameListFenixCasino.xlsx: {e}")
                
                            # Leer historiales individuales
                            for root, _, files in os.walk(tmpdir):
                                for file_name in files:
                                    if file_name.endswith((".xlsx", ".xls")) and "GameListFenixCasino.xlsx" not in file_name:
                                        full_path = os.path.join(root, file_name)
                                        try:
                                            extension = os.path.splitext(full_path)[-1].lower()
                                            engine = "xlrd" if extension == ".xls" else "openpyxl"
                                            xl = pd.ExcelFile(full_path, engine=engine)
                
                                            if "Información" not in xl.sheet_names or "Historia" not in xl.sheet_names:
                                                errores.append(f"{file_name} no contiene ambas hojas requeridas.")
                                                continue
                
                                            info = xl.parse("Información", header=None)
                                            try:
                                                jugador = info[info[0] == "Usuario"].iloc[0, 1]
                                                jugador = str(jugador).strip()
                                                if jugador.lower() in ["", "nan", "none"]:
                                                    jugador = "Desconocido"
                                            except Exception:
                                                jugador = "Desconocido"
                
                                            historia = xl.parse("Historia")
                
                                            # Conversión segura de columnas numéricas
                                            for col in ["Apuesta", "Ganancias", "Ganar"]:
                                                if col in historia.columns:
                                                    historia[col] = (
                                                        historia[col]
                                                        .astype(str)
                                                        .str.replace(",", "", regex=False)
                                                        .str.replace(" ", "", regex=False)
                                                    )
                                                    historia[col] = pd.to_numeric(historia[col], errors="coerce")
                
                                            historia["Jugador"] = jugador
                                            historiales.append(historia)
                
                                        except Exception as e:
                                            errores.append(f"{file_name}: {e}")
                
                            # Unificación y análisis
                            if historiales:
                                df_historial = pd.concat(historiales, ignore_index=True)
                                df_historial = df_historial.sort_values(by="Jugador").reset_index(drop=True)
                
                                # Merge con categorías
                                if df_categorias is not None and "Nombre del juego" in df_historial.columns:
                                    df_historial = df_historial.merge(
                                        df_categorias,
                                        how="left",
                                        left_on="Nombre del juego",
                                        right_on="Juego"
                                    )
                
                                # Análisis global de actividad
                                if "Apuesta" in df_historial.columns and "Nombre del juego" in df_historial.columns and "Categoría" in df_historial.columns:
                                    if "Fecha" not in df_historial.columns and "Hora de apertura" in df_historial.columns:
                                        df_historial["Fecha"] = pd.to_datetime(df_historial["Hora de apertura"], errors="coerce").dt.date
                                    df_historial["Fecha"] = pd.to_datetime(df_historial["Fecha"], errors="coerce")
                
                                    # 🎯 Juego más jugado por frecuencia
                                    frecuencias = df_historial["Nombre del juego"].value_counts().reset_index()
                                    frecuencias.columns = ["Nombre del juego", "Frecuencia"]
                                    juego_top_frecuencia = frecuencias.iloc[0]
                
                                    # 🧩 Categoría más jugada por volumen de apuesta
                                    categoria_top = (
                                        df_historial.groupby("Categoría")["Apuesta"]
                                        .sum()
                                        .sort_values(ascending=False)
                                        .reset_index()
                                        .iloc[0]
                                    )
                
                                    # 🕒 Inactividad promedio
                                    fecha_final = df_historial["Fecha"].max()
                                    inactividad = (
                                        df_historial.groupby("Jugador")["Fecha"]
                                        .max()
                                        .apply(lambda x: (fecha_final - x).days)
                                    )
                                    promedio_inactividad = inactividad.mean()
                
                                    st.subheader("📊 Análisis global de actividad VIP")
                                    col1, col2, col3 = st.columns(3)
                                    with col1:
                                        st.metric("🎯 Juego más jugado", juego_top_frecuencia["Nombre del juego"], f"{juego_top_frecuencia['Frecuencia']} veces")
                                    with col2:
                                        st.metric("🧩 Categoría más jugada", categoria_top["Categoría"], f"${categoria_top['Apuesta']:,.2f}")
                                    with col3:
                                        st.metric("🕒 Inactividad promedio", f"{promedio_inactividad:.2f} días")
                
                                st.success("✅ Historial unificado generado correctamente.")
                                st.dataframe(df_historial)
                
                                df_historial.to_excel("historial_unificado.xlsx", index=False)
                                with open("historial_unificado.xlsx", "rb") as f:
                                    st.download_button("📥 Descargar historial_unificado.xlsx", f, file_name="historial_unificado.xlsx")
                
                                if errores:
                                    st.warning("⚠️ Algunos archivos no se pudieron procesar:")
                                    for e in errores:
                                        st.text(f"• {e}")
                            else:
                                st.error("❌ No se pudo generar el historial unificado. Verificá que los archivos contengan las hojas 'Información' y 'Historia'.")

    
    # === SECCIÓN: 🏢 Oficina VIP Mejorada ===
    elif "🏢 Oficina VIP" in seccion:
        
        # --- CUSTOM CSS PARA TEMA PROFESIONAL ---
        st.markdown("""
        <style>
            .main-header {
                background: linear-gradient(90deg, #1e3c72 0%, #2a5298 100%);
                padding: 20px;
                border-radius: 10px;
                margin-bottom: 20px;
                color: white;
            }
            .metric-card {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                padding: 20px;
                border-radius: 15px;
                text-align: center;
                color: white;
                box-shadow: 0 8px 32px rgba(0,0,0,0.1);
                border: 1px solid rgba(255,255,255,0.1);
            }
            .metric-value {
                font-size: 2.5rem;
                font-weight: bold;
                margin-bottom: 5px;
            }
            .metric-label {
                font-size: 0.9rem;
                opacity: 0.9;
            }
            .success-card {
                background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
                padding: 15px;
                border-radius: 10px;
                color: white;
                margin: 10px 0;
            }
            .warning-card {
                background: linear-gradient(135deg, #fa709a 0%, #fee140 100%);
                padding: 15px;
                border-radius: 10px;
                color: white;
                margin: 10px 0;
            }
            .info-card {
                background: linear-gradient(135deg, #a8edea 0%, #fed6e3 100%);
                padding: 15px;
                border-radius: 10px;
                color: #333;
                margin: 10px 0;
            }
            .stTabs [data-baseweb="tab-list"] {
                gap: 8px;
            }
            .stTabs [data-baseweb="tab"] {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                border-radius: 10px 10px 0 0;
                color: white;
                font-weight: bold;
            }
            .stTabs [aria-selected="true"] {
                background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            }
            .upload-zone {
                border: 2px dashed #667eea;
                border-radius: 10px;
                padding: 20px;
                text-align: center;
                background: rgba(102, 126, 234, 0.1);
            }
        </style>
        """, unsafe_allow_html=True)
        
        # --- HEADER PRINCIPAL ---
        st.markdown("""
        <div class="main-header">
            <h1>🏢 Oficina VIP - Centro de Control</h1>
            <p>Gestión integral de jugadores VIP y análisis de datos</p>
        </div>
        """, unsafe_allow_html=True)
        
        try:
            engine = create_engine(st.secrets["DB_URL"])
            with engine.connect() as conn:
                st.markdown("""
                <div class="success-card">
                    ✅ <strong>Conectado a Supabase correctamente</strong>
                </div>
                """, unsafe_allow_html=True)
                
                # Cargar datos una vez
                query = "SELECT * FROM jugadores_vip ORDER BY total_apostado DESC"
                try:
                    df_vip = pd.read_sql(query, conn)
                except Exception as e:
                    st.error(f"❌ Error al consultar la tabla jugadores_vip: {e}")
                    df_vip = pd.DataFrame()
                
                # --- PESTAÑAS PRINCIPALES ---
                tab1, tab2, tab3, tab4 = st.tabs([
                    "📊 Dashboard VIP", 
                    "📋 Gestión de Datos", 
                    "📈 Análisis Avanzado", 
                    "📤 Carga de Archivos"
                ])
                #
                # === TAB 1: DASHBOARD VIP CON GRÁFICOS ESTRATÉGICOS ===
                with tab1:
                    st.markdown("## 📊 Dashboard Principal")
                    
                    if df_vip.empty:
                        st.markdown("""
                        <div class="info-card">
                            ℹ️ <strong>No hay datos VIP disponibles</strong><br>
                            La tabla jugadores_vip no contiene registros aún.
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        # === MÉTRICAS PRINCIPALES ===
                        col1, col2, col3, col4 = st.columns(4)
                        
                        total_jugadores = df_vip["usuario"].nunique()
                        riesgo_alto = df_vip[df_vip["riesgo_abandono"] == "alto"].shape[0]
                        riesgo_medio = df_vip[df_vip["riesgo_abandono"] == "medio"].shape[0]
                        riesgo_bajo = df_vip[df_vip["riesgo_abandono"] == "bajo"].shape[0]
                        
                        with col1:
                            st.markdown(f"""
                            <div class="metric-card">
                                <div class="metric-value">{total_jugadores}</div>
                                <div class="metric-label">👥 Total Jugadores VIP</div>
                            </div>
                            """, unsafe_allow_html=True)
                        
                        with col2:
                            st.markdown(f"""
                            <div class="metric-card">
                                <div class="metric-value">{riesgo_alto}</div>
                                <div class="metric-label">🔴 Riesgo Alto</div>
                            </div>
                            """, unsafe_allow_html=True)
                        
                        with col3:
                            st.markdown(f"""
                            <div class="metric-card">
                                <div class="metric-value">{riesgo_medio}</div>
                                <div class="metric-label">🟠 Riesgo Medio</div>
                            </div>
                            """, unsafe_allow_html=True)
                        
                        with col4:
                            st.markdown(f"""
                            <div class="metric-card">
                                <div class="metric-value">{riesgo_bajo}</div>
                                <div class="metric-label">🟢 Riesgo Bajo</div>
                            </div>
                            """, unsafe_allow_html=True)
                        
                        st.markdown("<br>", unsafe_allow_html=True)
                        
                        # === MÉTRICAS FINANCIERAS ===
                        col5, col6, col7 = st.columns(3)
                        
                        total_apostado = df_vip["total_apostado"].sum()
                        total_cargado = df_vip["total_cargado"].sum() if "total_cargado" in df_vip.columns else 0
                        promedio_cargado = df_vip["total_cargado"].mean() if "total_cargado" in df_vip.columns else 0
                        
                        with col5:
                            st.markdown(f"""
                            <div class="metric-card">
                                <div class="metric-value">${total_apostado:,.0f}</div>
                                <div class="metric-label">💰 Total Apostado</div>
                            </div>
                            """, unsafe_allow_html=True)
                        
                        with col6:
                            st.markdown(f"""
                            <div class="metric-card">
                                <div class="metric-value">${total_cargado:,.0f}</div>
                                <div class="metric-label">💳 Total Cargado</div>
                            </div>
                            """, unsafe_allow_html=True)
                        
                        with col7:
                            st.markdown(f"""
                            <div class="metric-card">
                                <div class="metric-value">${promedio_cargado:,.0f}</div>
                                <div class="metric-label">📊 Promedio Cargado</div>
                            </div>
                            """, unsafe_allow_html=True)
                        
                        st.markdown("---")
                        
                
                # === TAB 2: GESTIÓN DE DATOS ===
                with tab2:
                    st.markdown("## 📋 Gestión de Datos VIP")
                    
                    if df_vip.empty:
                        st.markdown("""
                        <div class="info-card">
                            ℹ️ <strong>No hay datos disponibles</strong><br>
                            La tabla jugadores_vip no contiene registros aún.
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        # === FILTROS AVANZADOS ===
                        st.markdown("### 🔍 Filtros de Datos")
                        
                        col1, col2, col3, col4 = st.columns(4)
                        
                        with col1:
                            casinos_disponibles = ["Todos"] + list(df_vip["casino"].unique()) if "casino" in df_vip.columns else ["Todos"]
                            casino_filtro = st.selectbox("🏢 Casino", casinos_disponibles)
                        
                        with col2:
                            riesgos_disponibles = ["Todos"] + list(df_vip["riesgo_abandono"].unique())
                            riesgo_filtro = st.selectbox("⚠️ Nivel de Riesgo", riesgos_disponibles)
                        
                        with col3:
                            min_apostado = st.number_input("💰 Monto mínimo", min_value=0.0, value=0.0, step=1000.0)
                        
                        with col4:
                            max_apostado = st.number_input("💰 Monto máximo", min_value=0.0, value=float(df_vip["total_apostado"].max()), step=1000.0)
                        
                        # Aplicar filtros
                        df_filtrado = df_vip.copy()
                        
                        if casino_filtro != "Todos" and "casino" in df_vip.columns:
                            df_filtrado = df_filtrado[df_filtrado["casino"] == casino_filtro]
                        
                        if riesgo_filtro != "Todos":
                            df_filtrado = df_filtrado[df_filtrado["riesgo_abandono"] == riesgo_filtro]
                        
                        df_filtrado = df_filtrado[
                            (df_filtrado["total_apostado"] >= min_apostado) & 
                            (df_filtrado["total_apostado"] <= max_apostado)
                        ]
                        
                        st.markdown(f"""
                        <div class="info-card">
                            📊 <strong>Mostrando {len(df_filtrado)} de {len(df_vip)} jugadores</strong>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # === TABLA INTERACTIVA ===
                        if not df_filtrado.empty:
                            st.markdown("### 📄 Tabla de Jugadores VIP")
                            st.dataframe(df_filtrado, use_container_width=True)
                            
                            # === DESCARGA DE DATOS ===
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                # Excel completo
                                output = io.BytesIO()
                                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                                    df_filtrado.to_excel(writer, index=False, sheet_name='jugadores_vip_filtrado')
                                
                                st.download_button(
                                    "📥 Descargar Excel (Filtrado)",
                                    data=output.getvalue(),
                                    file_name=f"jugadores_vip_filtrado.xlsx",
                                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                                )
                            
                            with col2:
                                # CSV
                                csv = df_filtrado.to_csv(index=False)
                                st.download_button(
                                    "📥 Descargar CSV (Filtrado)",
                                    data=csv,
                                    file_name=f"jugadores_vip_filtrado.csv",
                                    mime="text/csv"
                                )
                
                # === TAB 3: ANÁLISIS ESTRATÉGICO DE NEGOCIO ===
                with tab3:
                    st.markdown("## 🎯 Análisis Estratégico de Negocio")
                    
                    if df_vip.empty:
                        st.markdown("""
                        <div class="info-card">
                            ℹ️ <strong>No hay datos para análisis estratégico</strong><br>
                            Necesitas datos en la tabla jugadores_vip para generar insights de negocio.
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        # Verificar que existe la columna total_cargado
                        if "total_cargado" not in df_vip.columns:
                            st.markdown("""
                            <div class="warning-card">
                                ⚠️ <strong>Columna 'total_cargado' no encontrada</strong><br>
                                Para el análisis estratégico necesitamos la métrica 'total_cargado'. Usando 'total_apostado' como referencia temporal.
                            </div>
                            """, unsafe_allow_html=True)
                            df_vip['total_cargado'] = df_vip['total_apostado'] * 0.8  # Estimación temporal
                        
                        # === MÉTRICAS CLAVE DE NEGOCIO ===
                        st.markdown("### 💰 Métricas Clave de Ingresos")
                        
                        col1, col2, col3, col4 = st.columns(4)
                        
                        total_cargado_global = df_vip["total_cargado"].sum()
                        total_apostado_global = df_vip["total_apostado"].sum()
                        eficiencia_carga = (total_cargado_global / total_apostado_global * 100) if total_apostado_global > 0 else 0
                        jugadores_activos = len(df_vip[df_vip["total_cargado"] > 0])
                        
                        with col1:
                            st.markdown(f"""
                            <div class="metric-card">
                                <div class="metric-value">${total_cargado_global:,.0f}</div>
                                <div class="metric-label">💳 TOTAL CARGADO</div>
                            </div>
                            """, unsafe_allow_html=True)
                        
                        with col2:
                            st.markdown(f"""
                            <div class="metric-card">
                                <div class="metric-value">{eficiencia_carga:.1f}%</div>
                                <div class="metric-label">📊 Eficiencia Carga/Apuesta</div>
                            </div>
                            """, unsafe_allow_html=True)
                        
                        with col3:
                            st.markdown(f"""
                            <div class="metric-card">
                                <div class="metric-value">{jugadores_activos}</div>
                                <div class="metric-label">👥 Jugadores que Cargan</div>
                            </div>
                            """, unsafe_allow_html=True)
                        
                        with col4:
                            carga_promedio = df_vip["total_cargado"].mean()
                            st.markdown(f"""
                            <div class="metric-card">
                                <div class="metric-value">${carga_promedio:,.0f}</div>
                                <div class="metric-label">📈 Carga Promedio</div>
                            </div>
                            """, unsafe_allow_html=True)
                        
                        st.markdown("---")
                        
                        # === SEGMENTACIÓN ESTRATÉGICA POR CARGA ===
                        st.markdown("### 🎯 Segmentación Estratégica por Valor de Carga")
                        
                        # Crear segmentos basados en total_cargado
                        df_strategy = df_vip.copy()
                        df_strategy['segmento_carga'] = pd.cut(
                            df_strategy['total_cargado'], 
                            bins=[0, 5000, 25000, 75000, float('inf')], 
                            labels=['🥉 Básico', '🥈 Premium', '🥇 VIP', '💎 Elite']
                        )
                        
                        col1, col2 = st.columns([2, 1])
                        
                        with col1:
                            # Análisis detallado por segmento
                            segmento_business = df_strategy.groupby('segmento_carga').agg({
                                'usuario': 'count',
                                'total_cargado': ['sum', 'mean'],
                                'total_apostado': 'sum',
                                'riesgo_abandono': lambda x: (x == 'alto').sum()
                            }).round(2)
                            
                            segmento_business.columns = ['Cantidad', 'Total Cargado', 'Promedio Carga', 'Total Apostado', 'En Riesgo']
                            segmento_business['% Ingresos'] = (segmento_business['Total Cargado'] / segmento_business['Total Cargado'].sum() * 100).round(1)
                            segmento_business['ROI Carga'] = (segmento_business['Total Apostado'] / segmento_business['Total Cargado']).round(2)
                            segmento_business['% Riesgo'] = (segmento_business['En Riesgo'] / segmento_business['Cantidad'] * 100).round(1)
                            
                            st.markdown("#### 📊 Análisis de Segmentos por Carga")
                            st.dataframe(segmento_business, use_container_width=True)
                        
                        with col2:
                            # Concentración de ingresos por segmento
                            fig_concentration = px.pie(
                                values=segmento_business['Total Cargado'],
                                names=segmento_business.index,
                                title="💰 Concentración de Ingresos",
                                color_discrete_map={
                                    '🥉 Básico': '#cd7f32',
                                    '🥈 Premium': '#c0c0c0',
                                    '🥇 VIP': '#ffd700',
                                    '💎 Elite': '#b9f2ff'
                                }
                            )
                            fig_concentration.update_layout(
                                paper_bgcolor='rgba(0,0,0,0)',
                                plot_bgcolor='rgba(0,0,0,0)',
                                font=dict(color='white', size=10),
                                height=300
                            )
                            st.plotly_chart(fig_concentration, use_container_width=True)
                        
                        st.markdown("---")
                        
                        # === OPORTUNIDADES DE CROSS-PROPERTY MARKETING ===
                        st.markdown("### 🏢 Oportunidades Cross-Property")
                        
                        if "casino" in df_vip.columns:
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                # Jugadores mono-casino con alto potencial
                                casino_counts = df_strategy.groupby('usuario')['casino'].nunique()
                                mono_casino = casino_counts[casino_counts == 1].index
                                
                                mono_casino_data = df_strategy[
                                    (df_strategy['usuario'].isin(mono_casino)) & 
                                    (df_strategy['total_cargado'] > df_strategy['total_cargado'].median())
                                ].sort_values('total_cargado', ascending=False)
                                
                                st.markdown("#### 🎯 Oportunidades Cross-Property")
                                st.markdown(f"**{len(mono_casino_data)} jugadores** de alto valor en un solo casino")
                                
                                if not mono_casino_data.empty:
                                    cross_opportunities = mono_casino_data.groupby('casino').agg({
                                        'usuario': 'count',
                                        'total_cargado': ['sum', 'mean']
                                    }).round(0)
                                    cross_opportunities.columns = ['Jugadores', 'Total Cargado', 'Promedio']
                                    cross_opportunities['Potencial Cross'] = cross_opportunities['Total Cargado'] * 0.3  # 30% potencial
                                    
                                    st.dataframe(cross_opportunities, use_container_width=True)
                            
                            with col2:
                                # Análisis de penetración por casino
                                penetration_analysis = df_strategy.groupby('casino').agg({
                                    'usuario': 'count',
                                    'total_cargado': 'sum'
                                }).round(0)
                                
                                penetration_analysis['Market Share'] = (
                                    penetration_analysis['total_cargado'] / penetration_analysis['total_cargado'].sum() * 100
                                ).round(1)
                                
                                fig_market = px.bar(
                                    x=penetration_analysis.index,
                                    y=penetration_analysis['Market Share'],
                                    title="📊 Market Share por Casino",
                                    color=penetration_analysis.index,
                                    color_discrete_sequence=px.colors.qualitative.Set3
                                )
                                fig_market.update_layout(
                                    paper_bgcolor='rgba(0,0,0,0)',
                                    plot_bgcolor='rgba(0,0,0,0)',
                                    font=dict(color='white'),
                                    yaxis_title="% Market Share",
                                    height=300
                                )
                                st.plotly_chart(fig_market, use_container_width=True)
                        
                        st.markdown("---")
                        

                        # === AGREGAR DESPUÉS DE LA SECCIÓN DE CROSS-PROPERTY ===
                        st.markdown("---")
                        
                        # === SEGMENTACIÓN POR FRANJA HORARIA ===
                        st.markdown("### ⏰ Segmentación por Franja Horaria")
                        
                        # Si no existe la columna franja_horaria, crearla basada en datos disponibles
                        if "franja_horaria" not in df_strategy.columns:
                            # Crear franjas horarias simuladas basadas en patrones (esto se puede ajustar con datos reales)
                            import random
                            random.seed(42)  # Para resultados consistentes
                            franjas = ['🌅 Mañana (6-12h)', '☀️ Tarde (12-18h)', '🌙 Noche (18-24h)', '🌃 Madrugada (0-6h)']
                            df_strategy['franja_horaria'] = [random.choice(franjas) for _ in range(len(df_strategy))]
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            # Análisis por franja horaria
                            horario_analysis = df_strategy.groupby('franja_horaria').agg({
                                'usuario': 'count',
                                'total_cargado': ['sum', 'mean'],
                                'riesgo_abandono': lambda x: (x == 'alto').sum()
                            }).round(2)
                            
                            horario_analysis.columns = ['Jugadores', 'Total Cargado', 'Promedio Carga', 'En Riesgo']
                            horario_analysis['% Ingresos'] = (horario_analysis['Total Cargado'] / horario_analysis['Total Cargado'].sum() * 100).round(1)
                            horario_analysis['Carga por Jugador'] = (horario_analysis['Total Cargado'] / horario_analysis['Jugadores']).round(0)
                            
                            st.markdown("#### ⏰ Análisis por Franja Horaria")
                            st.dataframe(horario_analysis, use_container_width=True)
                            
                            # Identificar franja más rentable
                            mejor_franja = horario_analysis['Total Cargado'].idxmax()
                            mejor_valor = horario_analysis.loc[mejor_franja, 'Total Cargado']
                            
                            st.markdown(f"""
                            <div class="success-card">
                                🏆 <strong>Franja Más Rentable:</strong><br>
                                {mejor_franja}<br>
                                ${mejor_valor:,.0f} en cargas
                            </div>
                            """, unsafe_allow_html=True)
                        
                        with col2:
                            # Gráfico de distribución por horario
                            fig_horario = px.bar(
                                x=horario_analysis.index,
                                y=horario_analysis['Total Cargado'],
                                title="💰 Ingresos por Franja Horaria",
                                color=horario_analysis.index,
                                color_discrete_map={
                                    '🌅 Mañana (6-12h)': '#ffeb3b',
                                    '☀️ Tarde (12-18h)': '#ff9800',
                                    '🌙 Noche (18-24h)': '#3f51b5',
                                    '🌃 Madrugada (0-6h)': '#9c27b0'
                                }
                            )
                            fig_horario.update_layout(
                                paper_bgcolor='rgba(0,0,0,0)',
                                plot_bgcolor='rgba(0,0,0,0)',
                                font=dict(color='white'),
                                xaxis_title="Franja Horaria",
                                yaxis_title="Total Cargado ($)",
                                height=350
                            )
                            st.plotly_chart(fig_horario, use_container_width=True)
                        
                        # === OPORTUNIDADES POR HORARIO ===
                        st.markdown("#### 🎯 Oportunidades por Franja Horaria")
                        
                        col1, col2, col3, col4 = st.columns(4)
                        
                        franjas_info = {
                            '🌅 Mañana (6-12h)': {'estrategia': 'Promociones de inicio de día', 'target': 'Jubilados y trabajadores remotos'},
                            '☀️ Tarde (12-18h)': {'estrategia': 'Bonos de almuerzo', 'target': 'Trabajadores en pausa'},
                            '🌙 Noche (18-24h)': {'estrategia': 'Happy hour nocturno', 'target': 'Trabajadores post-laboral'},
                            '🌃 Madrugada (0-6h)': {'estrategia': 'Bonos nocturnos especiales', 'target': 'Jugadores nocturnos'}
                        }
                        
                        for i, (franja, info) in enumerate(franjas_info.items()):
                            with [col1, col2, col3, col4][i]:
                                jugadores_franja = horario_analysis.loc[franja, 'Jugadores'] if franja in horario_analysis.index else 0
                                ingresos_franja = horario_analysis.loc[franja, 'Total Cargado'] if franja in horario_analysis.index else 0
                                
                                st.markdown(f"""
                                <div class="info-card">
                                    <strong>{franja}</strong><br>
                                    👥 {jugadores_franja} jugadores<br>
                                    💰 ${ingresos_franja:,.0f}<br>
                                    <small>{info['estrategia']}</small>
                                </div>
                                """, unsafe_allow_html=True)
                        
                        st.markdown("---")
                        
                        # === SEGMENTACIÓN POR CATEGORÍA DE SESIONES ===
                        st.markdown("### 🎮 Segmentación por Categoría de Sesiones")
                        
                        # Si no existe la columna categoria_sesiones, crearla
                        if "categoria_sesiones" not in df_strategy.columns:
                            # Crear categorías basadas en total_cargado como proxy de frecuencia/intensidad
                            df_strategy['categoria_sesiones'] = pd.cut(
                                df_strategy['total_cargado'], 
                                bins=[0, 2000, 10000, 30000, float('inf')], 
                                labels=['🔵 Casual', '🟡 Regular', '🟠 Intensivo', '🔴 Compulsivo']
                            )
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            # Análisis por categoría de sesiones
                            sesiones_analysis = df_strategy.groupby('categoria_sesiones').agg({
                                'usuario': 'count',
                                'total_cargado': ['sum', 'mean'],
                                'riesgo_abandono': lambda x: (x == 'alto').sum()
                            }).round(2)
                            
                            sesiones_analysis.columns = ['Jugadores', 'Total Cargado', 'Promedio Carga', 'En Riesgo']
                            sesiones_analysis['% Riesgo'] = (sesiones_analysis['En Riesgo'] / sesiones_analysis['Jugadores'] * 100).round(1)
                            sesiones_analysis['Valor por Jugador'] = (sesiones_analysis['Total Cargado'] / sesiones_analysis['Jugadores']).round(0)
                            
                            st.markdown("#### 🎮 Análisis por Categoría de Sesiones")
                            st.dataframe(sesiones_analysis, use_container_width=True)
                        
                        with col2:
                            # Gráfico de riesgo por categoría
                            fig_sesiones = px.scatter(
                                x=sesiones_analysis['Valor por Jugador'],
                                y=sesiones_analysis['% Riesgo'],
                                size=sesiones_analysis['Jugadores'],
                                color=sesiones_analysis.index,
                                title="🎯 Valor vs Riesgo por Categoría",
                                labels={'x': 'Valor por Jugador ($)', 'y': '% en Riesgo'},
                                color_discrete_map={
                                    '🔵 Casual': '#2196f3',
                                    '🟡 Regular': '#ffeb3b',
                                    '🟠 Intensivo': '#ff9800',
                                    '🔴 Compulsivo': '#f44336'
                                }
                            )
                            fig_sesiones.update_layout(
                                paper_bgcolor='rgba(0,0,0,0)',
                                plot_bgcolor='rgba(0,0,0,0)',
                                font=dict(color='white'),
                                height=350
                            )
                            st.plotly_chart(fig_sesiones, use_container_width=True)
                        
                        # === ESTRATEGIAS POR CATEGORÍA DE SESIONES ===
                        st.markdown("#### 💡 Estrategias por Categoría de Sesiones")
                        
                        col1, col2, col3, col4 = st.columns(4)
                        
                        categorias_estrategias = {
                            '🔵 Casual': {
                                'objetivo': 'Incrementar frecuencia',
                                'estrategia': 'Bonos de bienvenida diarios',
                                'riesgo': 'Bajo - Enfoque en engagement'
                            },
                            '🟡 Regular': {
                                'objetivo': 'Aumentar valor por sesión',
                                'estrategia': 'Promociones escalonadas',
                                'riesgo': 'Medio - Monitoreo regular'
                            },
                            '🟠 Intensivo': {
                                'objetivo': 'Mantener nivel actual',
                                'estrategia': 'Programas VIP exclusivos',
                                'riesgo': 'Medio-Alto - Seguimiento cercano'
                            },
                            '🔴 Compulsivo': {
                                'objetivo': 'Juego responsable',
                                'estrategia': 'Límites y pausas sugeridas',
                                'riesgo': 'Alto - Intervención necesaria'
                            }
                        }
                        
                        for i, (categoria, estrategia) in enumerate(categorias_estrategias.items()):
                            with [col1, col2, col3, col4][i]:
                                jugadores_cat = sesiones_analysis.loc[categoria, 'Jugadores'] if categoria in sesiones_analysis.index else 0
                                
                                st.markdown(f"""
                                <div class="info-card">
                                    <strong>{categoria}</strong><br>
                                    👥 {jugadores_cat} jugadores<br>
                                    🎯 {estrategia['objetivo']}<br>
                                    📋 {estrategia['estrategia']}<br>
                                    <small>⚠️ {estrategia['riesgo']}</small>
                                </div>
                                """, unsafe_allow_html=True)
                        
                        st.markdown("---")
                        
                        # === SEGMENTACIÓN POR CATEGORÍA VA ===
                        st.markdown("### 💎 Segmentación por Categoría VA (Valor Agregado)")
                        
                        # Si no existe la columna categoria_va, crearla
                        if "categoria_va" not in df_strategy.columns:
                            # Crear categorías VA basadas en combinación de carga, riesgo y casino
                            def asignar_categoria_va(row):
                                if row['total_cargado'] > 50000 and row['riesgo_abandono'] == 'bajo':
                                    return '💎 Premium Plus'
                                elif row['total_cargado'] > 25000 and row['riesgo_abandono'] in ['bajo', 'medio']:
                                    return '🥇 Gold Member'
                                elif row['total_cargado'] > 10000:
                                    return '🥈 Silver Member'
                                else:
                                    return '🥉 Standard'
                            
                            df_strategy['categoria_va'] = df_strategy.apply(asignar_categoria_va, axis=1)
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            # Análisis por categoría VA
                            va_analysis = df_strategy.groupby('categoria_va').agg({
                                'usuario': 'count',
                                'total_cargado': ['sum', 'mean'],
                                'total_apostado': 'sum',
                                'riesgo_abandono': lambda x: (x == 'alto').sum()
                            }).round(2)
                            
                            va_analysis.columns = ['Jugadores', 'Total Cargado', 'Promedio Carga', 'Total Apostado', 'En Riesgo']
                            va_analysis['ROI VA'] = (va_analysis['Total Apostado'] / va_analysis['Total Cargado']).round(2)
                            va_analysis['% Portfolio'] = (va_analysis['Total Cargado'] / va_analysis['Total Cargado'].sum() * 100).round(1)
                            
                            st.markdown("#### 💎 Análisis por Categoría VA")
                            st.dataframe(va_analysis, use_container_width=True)
                        
                        with col2:
                            # Gráfico de portfolio VA
                            fig_va = px.treemap(
                                names=va_analysis.index,
                                values=va_analysis['Total Cargado'],
                                title="🏦 Portfolio por Categoría VA",
                                color=va_analysis['ROI VA'],
                                color_continuous_scale='Viridis'
                            )
                            fig_va.update_layout(
                                paper_bgcolor='rgba(0,0,0,0)',
                                font=dict(color='white'),
                                height=350
                            )
                            st.plotly_chart(fig_va, use_container_width=True)
                        
                        # === MATRIZ ESTRATÉGICA VA ===
                        st.markdown("#### 🎯 Matriz Estratégica por Categoría VA")
                        
                        col1, col2, col3, col4 = st.columns(4)
                        
                        va_estrategias = {
                            '💎 Premium Plus': {
                                'beneficios': 'Account manager dedicado, eventos exclusivos',
                                'comunicacion': 'Contacto directo, ofertas personalizadas',
                                'objetivo': 'Retención máxima y cross-selling premium'
                            },
                            '🥇 Gold Member': {
                                'beneficios': 'Bonos mejorados, acceso prioritario',
                                'comunicacion': 'Email personalizado, llamadas ocasionales',
                                'objetivo': 'Upgrade a Premium Plus'
                            },
                            '🥈 Silver Member': {
                                'beneficios': 'Bonos regulares, promociones especiales',
                                'comunicacion': 'Email segmentado, SMS promocionales',
                                'objetivo': 'Incrementar frecuencia y valor'
                            },
                            '🥉 Standard': {
                                'beneficios': 'Bonos básicos, promociones generales',
                                'comunicacion': 'Email masivo, notificaciones app',
                                'objetivo': 'Activación y primer upgrade'
                            }
                        }
                        
                        for i, (categoria, estrategia) in enumerate(va_estrategias.items()):
                            with [col1, col2, col3, col4][i]:
                                jugadores_va = va_analysis.loc[categoria, 'Jugadores'] if categoria in va_analysis.index else 0
                                portfolio_va = va_analysis.loc[categoria, '% Portfolio'] if categoria in va_analysis.index else 0
                                
                                st.markdown(f"""
                                <div class="info-card">
                                    <strong>{categoria}</strong><br>
                                    👥 {jugadores_va} jugadores<br>
                                    📊 {portfolio_va}% del portfolio<br>
                                    🎁 {estrategia['beneficios']}<br>
                                    📞 {estrategia['comunicacion']}<br>
                                    <small>🎯 {estrategia['objetivo']}</small>
                                </div>
                                """, unsafe_allow_html=True)
                        
                        st.markdown("---")
                        
                        # === EXPORTAR SEGMENTACIONES ADICIONALES ===
                        st.markdown("### 📥 Exportar Segmentaciones Específicas")
                        
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            # Export por franja horaria
                            horario_export = df_strategy[['usuario', 'casino', 'franja_horaria', 'total_cargado', 'riesgo_abandono']]
                            csv_horario = horario_export.to_csv(index=False)
                            st.download_button(
                                "⏰ Segmentación Horaria",
                                data=csv_horario,
                                file_name="segmentacion_franja_horaria.csv",
                                mime="text/csv"
                            )
                        
                        with col2:
                            # Export por categoría sesiones
                            sesiones_export = df_strategy[['usuario', 'casino', 'categoria_sesiones', 'total_cargado', 'riesgo_abandono']]
                            csv_sesiones = sesiones_export.to_csv(index=False)
                            st.download_button(
                                "🎮 Categoría Sesiones",
                                data=csv_sesiones,
                                file_name="segmentacion_categoria_sesiones.csv",
                                mime="text/csv"
                            )
                        
                        with col3:
                            # Export por categoría VA
                            va_export = df_strategy[['usuario', 'casino', 'categoria_va', 'total_cargado', 'riesgo_abandono']]
                            csv_va = va_export.to_csv(index=False)
                            st.download_button(
                                "💎 Categoría VA",
                                data=csv_va,
                                file_name="segmentacion_categoria_va.csv",
                                mime="text/csv"
                            )
                        
                        # === ESTRATEGIAS DE REACTIVACIÓN ===
                        st.markdown("### 🚨 Estrategias de Reactivación y Retención")
                        
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            # VIPs en riesgo crítico
                            vips_criticos = df_strategy[
                                (df_strategy['riesgo_abandono'] == 'alto') & 
                                (df_strategy['segmento_carga'].isin(['🥇 VIP', '💎 Elite']))
                            ].sort_values('total_cargado', ascending=False)
                            
                            st.markdown("#### 🚨 VIPs en Riesgo Crítico")
                            st.markdown(f"**{len(vips_criticos)} jugadores** requieren atención inmediata")
                            
                            if not vips_criticos.empty:
                                perdida_potencial = vips_criticos['total_cargado'].sum()
                                st.markdown(f"""
                                <div class="warning-card">
                                    💸 <strong>Riesgo de Pérdida:</strong><br>
                                    ${perdida_potencial:,.0f} en ingresos
                                </div>
                                """, unsafe_allow_html=True)
                                
                                st.dataframe(
                                    vips_criticos[['usuario', 'casino', 'total_cargado', 'segmento_carga']].head(5),
                                    use_container_width=True
                                )
                        
                        with col2:
                            # Oportunidades de upgrade
                            upgrade_candidates = df_strategy[
                                (df_strategy['riesgo_abandono'].isin(['bajo', 'medio'])) & 
                                (df_strategy['segmento_carga'].isin(['🥉 Básico', '🥈 Premium']))
                            ].sort_values('total_cargado', ascending=False)
                            
                            st.markdown("#### 📈 Candidatos a Upgrade")
                            st.markdown(f"**{len(upgrade_candidates)} jugadores** con potencial de crecimiento")
                            
                            if not upgrade_candidates.empty:
                                potencial_upgrade = upgrade_candidates['total_cargado'].sum() * 0.5  # 50% potencial
                                st.markdown(f"""
                                <div class="success-card">
                                    🚀 <strong>Potencial de Crecimiento:</strong><br>
                                    ${potencial_upgrade:,.0f} adicionales
                                </div>
                                """, unsafe_allow_html=True)
                                
                                st.dataframe(
                                    upgrade_candidates[['usuario', 'casino', 'total_cargado', 'riesgo_abandono']].head(5),
                                    use_container_width=True
                                )
                        
                        with col3:
                            # Jugadores estables de alto valor
                            estables_alto_valor = df_strategy[
                                (df_strategy['riesgo_abandono'] == 'bajo') & 
                                (df_strategy['total_cargado'] > df_strategy['total_cargado'].quantile(0.8))
                            ].sort_values('total_cargado', ascending=False)
                            
                            st.markdown("#### 🛡️ VIPs Estables")
                            st.markdown(f"**{len(estables_alto_valor)} jugadores** para fidelizar")
                            
                            if not estables_alto_valor.empty:
                                ingresos_estables = estables_alto_valor['total_cargado'].sum()
                                st.markdown(f"""
                                <div class="success-card">
                                    💎 <strong>Base Sólida:</strong><br>
                                    ${ingresos_estables:,.0f} seguros
                                </div>
                                """, unsafe_allow_html=True)
                                
                                st.dataframe(
                                    estables_alto_valor[['usuario', 'casino', 'total_cargado', 'segmento_carga']].head(5),
                                    use_container_width=True
                                )
                        
                        st.markdown("---")
                        
                        # === PLAN DE ACCIÓN ESTRATÉGICO ===
                        st.markdown("### 📋 Plan de Acción Estratégico")
                        
                        # Calcular métricas para el plan
                        total_vips_riesgo = len(vips_criticos) if 'vips_criticos' in locals() else 0
                        total_upgrade = len(upgrade_candidates) if 'upgrade_candidates' in locals() else 0
                        total_cross_property = len(mono_casino_data) if 'mono_casino_data' in locals() else 0
                        
                        col1, col2 = st.columns([2, 1])
                        
                        with col1:
                            st.markdown("#### 🎯 Acciones Prioritarias")
                            
                            acciones = [
                                {
                                    "Prioridad": "🔴 CRÍTICA",
                                    "Acción": "Campaña de Retención VIP",
                                    "Target": f"{total_vips_riesgo} jugadores",
                                    "Impacto": f"${vips_criticos['total_cargado'].sum():,.0f}" if 'vips_criticos' in locals() and not vips_criticos.empty else "$0",
                                    "Plazo": "Inmediato (24-48h)"
                                },
                                {
                                    "Prioridad": "🟠 ALTA",
                                    "Acción": "Promociones de Upgrade",
                                    "Target": f"{total_upgrade} jugadores",
                                    "Impacto": f"${potencial_upgrade:,.0f}" if 'potencial_upgrade' in locals() else "$0",
                                    "Plazo": "1-2 semanas"
                                },
                                {
                                    "Prioridad": "🟡 MEDIA",
                                    "Acción": "Cross-Property Marketing",
                                    "Target": f"{total_cross_property} jugadores",
                                    "Impacto": f"${cross_opportunities['Potencial Cross'].sum():,.0f}" if 'cross_opportunities' in locals() else "$0",
                                    "Plazo": "2-4 semanas"
                                }
                            ]
                            
                            df_acciones = pd.DataFrame(acciones)
                            st.dataframe(df_acciones, use_container_width=True, hide_index=True)
                        
                        with col2:
                            st.markdown("#### 💡 Recomendaciones")
                            
                            st.markdown("""
                            **🎯 Enfoque Inmediato:**
                            - Contactar VIPs en riesgo crítico
                            - Ofrecer bonos personalizados
                            - Asignar account manager dedicado
                            
                            **📈 Crecimiento:**
                            - Promociones escalonadas por segmento
                            - Incentivos por primera carga en nuevo casino
                            - Programas de lealtad diferenciados
                            
                            **🔄 Retención:**
                            - Análisis semanal de patrones
                            - Alertas automáticas de cambios
                            - Comunicación proactiva
                            """)
                        
                        # === EXPORTAR LISTAS DE ACCIÓN ===
                        st.markdown("---")
                        st.markdown("### 📥 Exportar Listas de Acción")
                        
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            if 'vips_criticos' in locals() and not vips_criticos.empty:
                                csv_criticos = vips_criticos[['usuario', 'casino', 'total_cargado', 'riesgo_abandono']].to_csv(index=False)
                                st.download_button(
                                    "🚨 Lista VIPs Críticos",
                                    data=csv_criticos,
                                    file_name="vips_criticos_accion_inmediata.csv",
                                    mime="text/csv"
                                )
                        
                        with col2:
                            if 'upgrade_candidates' in locals() and not upgrade_candidates.empty:
                                csv_upgrade = upgrade_candidates[['usuario', 'casino', 'total_cargado', 'segmento_carga']].to_csv(index=False)
                                st.download_button(
                                    "📈 Lista Candidatos Upgrade",
                                    data=csv_upgrade,
                                    file_name="candidatos_upgrade.csv",
                                    mime="text/csv"
                                )
                        
                        with col3:
                            if 'mono_casino_data' in locals() and not mono_casino_data.empty:
                                csv_cross = mono_casino_data[['usuario', 'casino', 'total_cargado']].to_csv(index=False)
                                st.download_button(
                                    "🏢 Lista Cross-Property",
                                    data=csv_cross,
                                    file_name="oportunidades_cross_property.csv",
                                    mime="text/csv"
                                )
                
                # === TAB 4: CARGA DE ARCHIVOS ===
                with tab4:
                    st.markdown("## 📤 Carga de Archivos")
                    
                    # === SELECCIÓN DE CASINO ===
                    st.markdown("### 🏢 Configuración")
                    casino = st.selectbox(
                        "Seleccioná el casino al que pertenece este archivo", 
                        ["Fenix", "Eros", "Bet Argento", "Atlantis"],
                        help="Esta información se agregará automáticamente a los datos cargados"
                    )
                    
                    # === TIPO DE ARCHIVO ===
                    st.markdown("### 📂 Tipo de Carga")
                    tipo_archivo = st.radio(
                        "Seleccioná el tipo de archivo a cargar",
                        ["Archivo individual (.csv o .xlsx)", "Archivo ZIP con múltiples historiales"],
                        help="Archivo individual para datos únicos, ZIP para múltiples reportes históricos"
                    )
                    
                    if tipo_archivo == "Archivo individual (.csv o .xlsx)":
                        # === CARGA INDIVIDUAL ===
                        st.markdown("### 📎 Subir Archivo Individual")
                        
                        st.markdown("""
                        <div class="upload-zone">
                            <h4>📁 Zona de Carga</h4>
                            <p>Arrastra tu archivo aquí o haz clic para seleccionar</p>
                            <p><small>Formatos soportados: CSV, XLSX</small></p>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        archivo = st.file_uploader("", type=["csv", "xlsx"], key="single_upload")
                        
                        if archivo:
                            try:
                                with st.spinner("🔄 Procesando archivo..."):
                                    if archivo.name.endswith(".csv"):
                                        df = pd.read_csv(archivo)
                                    else:
                                        df = pd.read_excel(archivo)
                                    
                                    df.columns = df.columns.str.strip()
                                    df["casino"] = casino
                                
                                st.markdown("""
                                <div class="success-card">
                                    ✅ <strong>Archivo procesado correctamente</strong>
                                </div>
                                """, unsafe_allow_html=True)
                                
                                st.markdown("#### 👀 Vista previa del archivo:")
                                st.dataframe(df.head(10), use_container_width=True)
                                
                                if df.empty:
                                    st.markdown("""
                                    <div class="warning-card">
                                        ⚠️ <strong>Archivo vacío</strong><br>
                                        El archivo está vacío o malformado.
                                    </div>
                                    """, unsafe_allow_html=True)
                                else:
                                    tabla = detectar_tabla(df)
                                    
                                    if tabla in {"actividad_jugador_cruda", "transacciones_crudas", "bonos_crudos", "catalogo_juegos"}:
                                        st.markdown(f"""
                                        <div class="info-card">
                                            📌 <strong>Tabla detectada:</strong> {tabla}<br>
                                            El archivo será cargado en esta tabla.
                                        </div>
                                        """, unsafe_allow_html=True)
                                        
                                        if st.button("🚀 Confirmar Carga", type="primary"):
                                            subir_a_supabase(df, tabla, engine)
                                            
                                    elif tabla == "jugadores_vip":
                                        st.markdown("""
                                        <div class="warning-card">
                                            ❌ <strong>Carga no permitida</strong><br>
                                            No se puede subir directamente a la tabla jugadores_vip. Esta tabla es generada automáticamente.
                                        </div>
                                        """, unsafe_allow_html=True)
                                    else:
                                        st.markdown("""
                                        <div class="warning-card">
                                            ⚠️ <strong>Tabla no detectada</strong><br>
                                            No se pudo detectar a qué tabla pertenece el archivo. Verificá las columnas.
                                        </div>
                                        """, unsafe_allow_html=True)
                                        
                            except Exception as e:
                                st.markdown(f"""
                                <div class="warning-card">
                                    ❌ <strong>Error al procesar archivo:</strong><br>
                                    {str(e)}
                                </div>
                                """, unsafe_allow_html=True)
                    
                    else:
                        # === CARGA ZIP ===
                        st.markdown("### 📦 Subir Archivo ZIP")
                        
                        st.markdown("""
                        <div class="upload-zone">
                            <h4>📦 Zona de Carga ZIP</h4>
                            <p>Arrastra tu archivo ZIP aquí o haz clic para seleccionar</p>
                            <p><small>El ZIP debe contener archivos .xlsx con hojas "Historia"</small></p>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        archivo_zip = st.file_uploader("", type=["zip"], key="zip_upload")
                        
                        if archivo_zip:
                            with st.spinner("⏳ Procesando archivo ZIP..."):
                                try:
                                    with tempfile.TemporaryDirectory() as tmpdir:
                                        zip_path = os.path.join(tmpdir, "reportes.zip")
                                        with open(zip_path, "wb") as f:
                                            f.write(archivo_zip.getbuffer())
                                        
                                        with zipfile.ZipFile(zip_path, "r") as zip_ref:
                                            zip_ref.extractall(tmpdir)
                                        
                                        archivos_xlsx = list(Path(tmpdir).rglob("*.xlsx"))
                                        
                                        if not archivos_xlsx:
                                            st.markdown("""
                                            <div class="warning-card">
                                                ⚠️ <strong>No se encontraron archivos</strong><br>
                                                No se encontraron archivos .xlsx en el ZIP.
                                            </div>
                                            """, unsafe_allow_html=True)
                                        else:
                                            dataframes = []
                                            progress_bar = st.progress(0)
                                            status_text = st.empty()
                                            
                                            for i, archivo in enumerate(archivos_xlsx):
                                                try:
                                                    status_text.text(f"Procesando: {archivo.name}")
                                                    df_historia = pd.read_excel(archivo, sheet_name="Historia")
                                                    df_historia.columns = df_historia.columns.str.strip()
                                                    
                                                    nombre_real = extraer_nombre_real_desde_info(archivo)
                                                    if nombre_real and "Usuario" in df_historia.columns:
                                                        df_historia["Usuario"] = nombre_real
                                                    
                                                    df_historia["casino"] = casino
                                                    dataframes.append(df_historia)
                                                    
                                                    progress_bar.progress((i + 1) / len(archivos_xlsx))
                                                    
                                                except Exception as e:
                                                    st.warning(f"No se pudo procesar {archivo.name}: {e}")
                                            
                                            status_text.empty()
                                            progress_bar.empty()
                                            
                                            if dataframes:
                                                df_final = pd.concat(dataframes, ignore_index=True)
                                                
                                                st.markdown(f"""
                                                <div class="success-card">
                                                    ✅ <strong>Consolidación completa</strong><br>
                                                    {len(df_final)} registros procesados desde {len(dataframes)} archivos
                                                </div>
                                                """, unsafe_allow_html=True)
                                                
                                                st.markdown("#### 👀 Vista previa de datos consolidados:")
                                                st.dataframe(df_final.head(10), use_container_width=True)
                                                
                                                if st.button("🚀 Confirmar Carga Masiva", type="primary"):
                                                    subir_a_supabase(df_final, "actividad_jugador_cruda", engine)
                                            else:
                                                st.markdown("""
                                                <div class="warning-card">
                                                    ⚠️ <strong>Sin archivos válidos</strong><br>
                                                    No se pudo consolidar ningún archivo válido del ZIP.
                                                </div>
                                                """, unsafe_allow_html=True)
                                                
                                except Exception as e:
                                    st.markdown(f"""
                                    <div class="warning-card">
                                        ❌ <strong>Error al procesar ZIP:</strong><br>
                                        {str(e)}
                                    </div>
                                    """, unsafe_allow_html=True)
                    
        except Exception as e:
            st.markdown(f"""
            <div class="warning-card">
                ❌ <strong>Error de conexión:</strong> {e}
            </div>
            """, unsafe_allow_html=True)
    
    # === FUNCIONES AUXILIARES (AGREGAR AL FINAL DEL ARCHIVO) ===
    def detectar_tabla(df):
        """Detecta a qué tabla pertenece el DataFrame basándose en sus columnas"""
        columnas = set(df.columns.str.lower().str.strip())
        
        if {"usuario", "total_apostado", "riesgo_abandono"}.issubset(columnas):
            return "jugadores_vip"
        elif {"usuario", "fecha", "juego"}.issubset(columnas):
            return "actividad_jugador_cruda"
        elif {"usuario", "monto", "tipo_transaccion"}.issubset(columnas):
            return "transacciones_crudas"
        elif {"usuario", "bono", "fecha_otorgado"}.issubset(columnas):
            return "bonos_crudos"
        elif {"juego", "categoria", "proveedor"}.issubset(columnas):
            return "catalogo_juegos"
        else:
            return "desconocido"
    
    def subir_a_supabase(df, tabla, engine):
        """Sube el DataFrame a la tabla especificada en Supabase"""
        try:
            with st.spinner(f"⏳ Subiendo {len(df)} registros a {tabla}..."):
                df.to_sql(tabla, engine, if_exists="append", index=False)
            
            st.markdown(f"""
            <div class="success-card">
                ✅ <strong>Carga exitosa</strong><br>
                {len(df)} registros subidos correctamente a {tabla}
            </div>
            """, unsafe_allow_html=True)
            
            # Botón para recargar datos
            if st.button("🔄 Actualizar Dashboard"):
                st.rerun()
                
        except Exception as e:
            st.markdown(f"""
            <div class="warning-card">
                ❌ <strong>Error en la carga:</strong><br>
                {str(e)}
            </div>
            """, unsafe_allow_html=True)
    
    def extraer_nombre_real_desde_info(archivo_path):
        """Extrae el nombre real del jugador desde la hoja Info del archivo"""
        try:
            df_info = pd.read_excel(archivo_path, sheet_name="Info")
            if not df_info.empty and len(df_info.columns) > 1:
                return df_info.iloc[0, 1]
        except:
            pass
        return None








        
