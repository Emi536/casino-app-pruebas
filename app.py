import streamlit as st
st.set_page_config(page_title="Strike IQ - Análisis de Cargas", layout="wide")
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

from sqlalchemy import create_engine, text
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
        "admin": ["🏢 Oficina VIP", "📋 Registro Fénix/Eros", "📋 Registro BetArgento/Atlantis","📋 Registro Spirita","📋 Registro Mi Jugada","📋 Registro Atenea","📋 Registro Padrino Latino/Tiger","📋 Registro Fortuna/Gana 24","🗒️ Registro de Contactos","📊 Análisis Temporal"],
        "fenix_eros": ["📋 Registro Fénix/Eros"],
        "bet": ["📋 Registro BetArgento/Atlantis/Mi Jugada"],
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

    def limpiar_registro(df: pd.DataFrame, casino_actual: str) -> pd.DataFrame:
        df.columns = df.columns.str.strip()
        map_cols = {
            "FECHA": "fecha", "Fecha": "fecha",
            "USUARIO": "usuario", "Usuario": "usuario",
            "TIPO DE BONO": "tipo_bono", "Tipo de bono": "tipo_bono",
            "CATEGORIA DE BONO": "categoria_bono", "Categoría de Bono": "categoria_bono",
            "USADO": "usado", "Usado": "usado",
            "MONTO": "monto", "Monto": "monto",
            "RESPONDIÓ": "respondio", "Respondió": "respondio",
            "ID": "ext_id", "Id": "ext_id"
        }
        rename_dict = {c: map_cols[c] for c in df.columns if c in map_cols}
        df = df.rename(columns=rename_dict)
    
        for c in ["fecha", "usuario"]:
            if c not in df.columns:
                df[c] = None
    
        if "fecha" in df.columns:
            df["fecha"] = parse_datetime_flexible_series(df["fecha"])
        if "usuario" in df.columns:
            df["usuario"] = df["usuario"].astype(str).str.strip()
            df["usuario_norm"] = norm_user_series(df["usuario"])
        if "usado" in df.columns:
            df["usado"] = parse_bool_series(df["usado"])
        if "respondio" in df.columns:
            df["respondio"] = parse_bool_series(df["respondio"])
        if "monto" in df.columns:
            df["monto"] = parse_monto_lat_series(df["monto"])
    
        for c in ["tipo_bono", "categoria_bono", "ext_id"]:
            if c not in df.columns:
                df[c] = None
    
        df["casino"] = casino_actual
        df = df.dropna(subset=["usuario_norm", "fecha"])
    
        cols_finales = ["fecha", "usuario", "usuario_norm", "casino",
                        "tipo_bono", "categoria_bono", "usado", "monto", "respondio", "ext_id"]
        df = df[[c for c in cols_finales if c in df.columns]]
    
        if "ext_id" in df.columns:
            df = df.drop_duplicates(subset=["ext_id"], keep="last")
        else:
            df = df.drop_duplicates(subset=["usuario_norm", "fecha", "casino"], keep="last")
    
        return df
    
    AR_TZ = "America/Argentina/Buenos_Aires"

    def norm_user_series(s: pd.Series) -> pd.Series:
        return (s.astype(str).str.strip().str.lower()
                .str.replace(" ", "", regex=False)
                .str.replace("_", "", regex=False))
    
    def parse_bool_series(s: pd.Series) -> pd.Series:
        return (s.astype(str).str.strip().str.lower()
                  .replace({"true": True, "false": False, "": None, "nan": None}))
    
    def parse_monto_lat_series(s: pd.Series) -> pd.Series:
        s = s.astype(str).str.strip().replace({"": None, "nan": None})
        s = s.str.replace("$", "", regex=False).str.replace(" ", "", regex=False)
        s = s.str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
        return pd.to_numeric(s, errors="coerce")
    
    def parse_datetime_flexible_series(s: pd.Series) -> pd.Series:
        dt = pd.to_datetime(s, errors="coerce", dayfirst=True)
        try:
            # si ya viene tz-aware, convertimos a AR; si no, la asignamos
            if getattr(dt.dt, "tz", None) is not None:
                return dt.dt.tz_convert(AR_TZ)
            return dt.dt.tz_localize(AR_TZ, nonexistent="shift_forward", ambiguous="NaT")
        except Exception:
            return pd.to_datetime(None)
    
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

    UPSERT_EXT = text("""
    INSERT INTO registro (fecha, usuario, casino, tipo_bono, categoria_bono, usado, monto, respondio, ext_id)
    VALUES (:fecha, :usuario, :casino, :tipo_bono, :categoria_bono, :usado, :monto, :respondio, :ext_id)
    ON CONFLICT (ext_id) DO UPDATE
    SET fecha = EXCLUDED.fecha,
        usuario = EXCLUDED.usuario,
        casino = EXCLUDED.casino,
        tipo_bono = EXCLUDED.tipo_bono,
        categoria_bono = EXCLUDED.categoria_bono,
        usado = EXCLUDED.usado,
        monto = EXCLUDED.monto,
        respondio = EXCLUDED.respondio;
    """)
        
    def _py(v):
        """Convierte tipos pandas/numpy a nativos para el driver."""
        if isinstance(v, (np.floating,)):
            return None if np.isnan(v) else float(v)
        if isinstance(v, (np.integer,)):
            return int(v)
        if pd.isna(v):
            return None
        if isinstance(v, pd.Timestamp):
            return v.to_pydatetime()
        return v
    
    def upsert_registro(df_reg: pd.DataFrame, engine, generar_hash_si_falta: bool = True):
        """
        Carga df_reg a `registro_stage` y hace UN SOLO merge a `registro`.
        Mucho más rápido que upserts por lotes.
        """
        if df_reg.empty:
            st.warning("⚠️ El archivo de registro no tiene filas válidas.")
            return
    
        # 1) Garantizar columna ext_id
        if "ext_id" not in df_reg.columns:
            df_reg["ext_id"] = None
    
        # 2) Generar ext_id si falta (hash estable usuario_norm|fecha|casino)
        if generar_hash_si_falta:
            mask = df_reg["ext_id"].isna()
            if mask.any():
                gen = (df_reg.loc[mask, "usuario_norm"].astype(str) + "|" +
                       df_reg.loc[mask, "fecha"].astype(str) + "|" +
                       df_reg.loc[mask, "casino"].astype(str))
                df_reg.loc[mask, "ext_id"] = gen.apply(lambda s: hashlib.sha256(s.encode()).hexdigest())
        else:
            faltantes = df_reg["ext_id"].isna().sum()
            if faltantes > 0:
                st.info(f"ℹ️ {faltantes} filas sin ext_id fueron descartadas.")
                df_reg = df_reg[~df_reg["ext_id"].isna()]
    
        if df_reg.empty:
            st.warning("⚠️ Tras validar ext_id, no quedaron filas para subir.")
            return
    
        # 3) Preparar dataframe para staging (sin usuario_norm, que es GENERATED en destino)
        cols_stage = ["fecha","usuario","casino","tipo_bono","categoria_bono","usado","monto","respondio","ext_id"]
        df_stage = df_reg.drop(columns=["usuario_norm"], errors="ignore")
        df_stage = df_stage[[c for c in cols_stage if c in df_stage.columns]]
    
        total = len(df_stage)
        prog = st.progress(0)
    
        try:
            with engine.begin() as conn:
                # TZ literal y staging limpio
                conn.execute(text("SET TIME ZONE 'America/Argentina/Buenos_Aires'"))
                conn.execute(text("TRUNCATE registro_stage"))
    
                # Carga masiva a stage (rápida)
                df_stage.to_sql(
                    "registro_stage",
                    con=conn.connection,      # conexión DBAPI
                    if_exists="append",
                    index=False,
                    method="multi",
                    chunksize=5000
                )
                prog.progress(0.6)
    
                # Un solo upsert/merge a destino
                conn.execute(text("""
                    INSERT INTO registro (fecha, usuario, casino, tipo_bono, categoria_bono, usado, monto, respondio, ext_id)
                    SELECT fecha, usuario, casino, tipo_bono, categoria_bono, usado, monto, respondio, ext_id
                    FROM registro_stage
                    ON CONFLICT (ext_id) DO UPDATE
                    SET fecha = EXCLUDED.fecha,
                        usuario = EXCLUDED.usuario,
                        casino = EXCLUDED.casino,
                        tipo_bono = EXCLUDED.tipo_bono,
                        categoria_bono = EXCLUDED.categoria_bono,
                        usado = EXCLUDED.usado,
                        monto = EXCLUDED.monto,
                        respondio = EXCLUDED.respondio;
                """))
                prog.progress(1.0)
    
            st.success(f"✅ {total} registros procesados vía staging (merge a `registro`).")
    
        except Exception as e:
            st.error(f"❌ Error en carga staging/merge: {e}")
        
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

    def corregir_bonos_na_con_vips(df_resumen, casino_actual, engine):
        try:
            query = "SELECT LOWER(TRIM(nombre)) AS nombre, LOWER(TRIM(sesion)) AS sesion FROM names_vips"
            df_vips = pd.read_sql(query, engine)
    
            # Preparamos el dataframe para coincidir sin espacios/guiones
            df_resumen["__nombre_match"] = df_resumen["Nombre de jugador"].str.lower().str.replace(" ", "").str.replace("_", "")
            df_vips["__nombre_match"] = df_vips["nombre"].str.replace(" ", "").str.replace("_", "")
    
            # Definimos qué prefijo de sesión buscar según el casino
            if casino_actual.lower() == "fénix":
                filtro_sesion = "fenix"
            elif casino_actual.lower() == "eros":
                filtro_sesion = "eros"
            elif casino_actual.lower() == "bet argento":
                filtro_sesion = "betarg"
            elif casino_actual.lower() == "atlantis":
                filtro_sesion = "atlantis"
            else:
                return df_resumen
    
            # Filtramos solo los VIPs del casino actual
            df_vips_casino = df_vips[df_vips["sesion"].str.startswith(filtro_sesion)]
    
            # Creamos set de usuarios vips válidos para este casino
            set_vips = set(df_vips_casino["__nombre_match"])
    
            # Corregimos los "N/A" si el usuario aparece como VIP
            mask_vip_na = df_resumen["Tipo de bono"].str.upper() == "N/A"
            mask_usuario_vip = df_resumen["__nombre_match"].isin(set_vips)
            df_resumen.loc[mask_vip_na & mask_usuario_vip, "Tipo de bono"] = "VIP"
    
            df_resumen.drop(columns=["__nombre_match"], inplace=True)
            return df_resumen
    
        except Exception as e:
            print(f"⚠️ Error en corrección de N/A con VIPs: {e}")
            return df_resumen

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
    
        nombre_funcion = "resumen_fenix_dinamico" if casino_actual == "Fénix" else "resumen_eros_dinamico"
        
        # 🗓️ NUEVO filtro de rango dinámico — antes de abrir conexión
        st.markdown("### 📅 Seleccioná el rango de fechas")
        col1, col2 = st.columns(2)
        
        with col1:
            filtro_desde = st.date_input(
                "📆 Desde",
                value=pd.to_datetime("2023-01-01").date(),
                key="desde_fecha_fenix_eros"
            )
        with col2:
            filtro_hasta = st.date_input(
                "📆 Hasta",
                value=datetime.date.today(),
                key="hasta_fecha_fenix_eros"
            )

    
        try:
            engine = create_engine(st.secrets["DB_URL"])
            with engine.connect() as conn:
                query = f"""
                SELECT * FROM {nombre_funcion}(
                  '{filtro_desde.strftime('%Y-%m-%d')}',
                  '{filtro_hasta.strftime('%Y-%m-%d')}'
                )
                ORDER BY "Ganacias casino" DESC
                """
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
                df_resumen = corregir_bonos_na_con_vips(df_resumen, casino_actual, engine)
    
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
            
            df_resumen["Tipo de bono"] = df_resumen["Tipo de bono"].fillna("N/A")
            col_filtro, _ = st.columns(2)
            tipos_disponibles = sorted(df_resumen["Tipo de bono"].unique().tolist())
            
            seleccion_tipos = col_filtro.multiselect(
                "🎯 Filtrar por tipo de bono:",
                options=tipos_disponibles,
                default=[]
            )
            
            if seleccion_tipos:
                df_resumen = df_resumen[df_resumen["Tipo de bono"].isin(seleccion_tipos)]

    
            if not df_resumen.empty:
                st.dataframe(df_resumen, use_container_width=True)
    
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
                    df_resumen.to_excel(writer, index=False, sheet_name=casino_actual)
    
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
    
        nombre_funcion = "resumen_betargento_dinamico" if casino_actual == "Bet Argento" else "resumen_atlantis_dinamico"

        st.markdown("### 📅 Filtrar jugadores por fecha")
        col1, col2 = st.columns(2)
        
        with col1:
            filtro_desde = st.date_input(
                "📆 Desde",
                value=pd.to_datetime("2023-01-01").date(),
                key="desde_fecha_bet_atlantis"
            )
        with col2:
            filtro_hasta = st.date_input(
                "📆 Hasta",
                value=datetime.date.today(),
                key="hasta_fecha_bet_atlantis"
            )

        try:
            engine = create_engine(st.secrets["DB_URL"])
            with engine.connect() as conn:
                query = f"""
                SELECT * FROM {nombre_funcion}(
                  '{filtro_desde.strftime('%Y-%m-%d')}',
                  '{filtro_hasta.strftime('%Y-%m-%d')}'
                )
                ORDER BY "Ganacias casino" DESC
                """
                df_resumen = pd.read_sql(query, conn)
    
            df_bonos = cargar_tabla_bonos(clave_casino, sh)
    
            df_resumen["__user_key"] = df_resumen["Nombre de jugador"].astype(str).str.lower().str.replace(" ", "").str.replace("_", "")
            df_bonos["__user_key"] = df_bonos["Usuario"].astype(str).str.lower().str.replace(" ", "").str.replace("_", "")
    
            dict_tipo_bono = dict(zip(df_bonos["__user_key"], df_bonos["Tipo de Bono"]))
            dict_contacto = dict(zip(df_bonos["__user_key"], df_bonos["Últ. vez contactado"]))
    
            if "Tipo de bono" in df_resumen.columns:
                df_resumen["Tipo de bono"] = df_resumen["__user_key"].map(dict_tipo_bono).combine_first(df_resumen["Tipo de bono"])
                df_resumen["Tipo de bono"] = df_resumen["Tipo de bono"].replace("", pd.NA).fillna("N/A")
                df_resumen = corregir_bonos_na_con_vips(df_resumen, casino_actual, engine)
    
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
    
            df_resumen["Tipo de bono"] = df_resumen["Tipo de bono"].fillna("N/A")
            col_filtro, _ = st.columns(2)
            tipos_disponibles = sorted(df_resumen["Tipo de bono"].unique().tolist())
    
            seleccion_tipos = col_filtro.multiselect(
                "🎯 Filtrar por tipo de bono:",
                options=tipos_disponibles,
                default=[]  # ← esto evita que se filtre por defecto
            )
            
            if seleccion_tipos:
                df_resumen = df_resumen[df_resumen["Tipo de bono"].isin(seleccion_tipos)]
    
            if not df_resumen.empty:
                st.dataframe(df_resumen, use_container_width=True)
    
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
                    df_resumen.to_excel(writer, index=False, sheet_name=casino_actual)
    
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


        st.markdown("### 📅 Filtrar jugadores por fecha de última carga")
        col1, col2 = st.columns(2)
        
        with col1:
            filtro_desde = st.date_input(
                "📆 Desde",
                value=pd.to_datetime("2023-01-01").date(),
                key="desde_spirita"
            )
        with col2:
            filtro_hasta = st.date_input(
                "📆 Hasta",
                value=datetime.date.today(),
                key="hasta_spirita"
            )

        try:
            engine = create_engine(st.secrets["DB_URL"])
            with engine.connect() as conn:
                query = f"""
                SELECT * FROM resumen_spirita_dinamico(
                  '{filtro_desde.strftime('%Y-%m-%d')}',
                  '{filtro_hasta.strftime('%Y-%m-%d')}'
                )
                ORDER BY "Ganacias casino" DESC
                """
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
    
            df_resumen["Tipo de bono"] = df_resumen["Tipo de bono"].fillna("N/A")
            col_filtro, _ = st.columns(2)
            tipos_disponibles = sorted(df_resumen["Tipo de bono"].unique().tolist())
    
            seleccion_tipos = col_filtro.multiselect(
                "🎯 Filtrar por tipo de bono:",
                options=tipos_disponibles,
                default=tipos_disponibles
            )
    
            if seleccion_tipos:
                df_resumen = df_resumen[df_resumen["Tipo de bono"].isin(seleccion_tipos)]
    
            if not df_resumen.empty:
                st.dataframe(df_resumen, use_container_width=True)
    
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
                    df_resumen.to_excel(writer, index=False, sheet_name="Spirita")
    
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

    # SECCIÓN MI JUGADA
    elif "📋 Registro Mi Jugada" in seccion:
        st.header("📋 Registro general de jugadores - Mi Jugada")
    
        archivo = st.file_uploader("📁 Subí el archivo del reporte (.xlsx)", type=["xlsx"], key="reporte_mijugada")
    
        if archivo and not st.session_state.get("archivo_procesado_mijugada"):
            try:
                df = pd.read_excel(archivo)
                df = limpiar_transacciones(df)
                df = agregar_columna_casino(df, "Mi Jugada")
    
                engine = create_engine(st.secrets["DB_URL"])
                subir_a_supabase(df, "reportes_jugadores", engine)
    
                st.session_state["archivo_procesado_mijugada"] = True
                st.success("✅ Archivo subido y procesado correctamente.")
            except Exception as e:
                st.error(f"❌ Error al procesar o subir el archivo: {e}")
    
        elif st.session_state.get("archivo_procesado_mijugada"):
            st.success("✅ El archivo ya fue procesado. Recargá la página si querés subir uno nuevo.")
    
        st.markdown("---")
        st.subheader("🔍 Vista resumen de jugadores - Mi Jugada")
    
        st.markdown("### 📅 Filtrar jugadores por fecha de última carga")
        col1, col2 = st.columns(2)
    
        with col1:
            filtro_desde = st.date_input(
                "📆 Desde",
                value=pd.to_datetime("2023-01-01").date(),
                key="desde_mijugada"
            )
        with col2:
            filtro_hasta = st.date_input(
                "📆 Hasta",
                value=datetime.date.today(),
                key="hasta_mijugada"
            )
    
        try:
            engine = create_engine(st.secrets["DB_URL"])
            with engine.connect() as conn:
                query = f"""
                SELECT * FROM resumen_mijugada_dinamico(
                  '{filtro_desde.strftime('%Y-%m-%d')}',
                  '{filtro_hasta.strftime('%Y-%m-%d')}'
                )
                ORDER BY "Ganacias casino" DESC
                """
                df_resumen = pd.read_sql(query, conn)
    
            df_bonos = cargar_tabla_bonos("mijugada", sh)
    
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
    
            df_resumen = asignar_princi(df_resumen, sh, "mijugada")
    
            cols = df_resumen.columns.tolist()
            if "Tipo de bono" in cols and "PRINCI" in cols:
                cols.remove("PRINCI")
                idx = cols.index("Tipo de bono") + 1
                cols.insert(idx, "PRINCI")
                df_resumen = df_resumen[cols]
    
            df_resumen["Tipo de bono"] = df_resumen["Tipo de bono"].fillna("N/A")
            col_filtro, _ = st.columns(2)
            tipos_disponibles = sorted(df_resumen["Tipo de bono"].unique().tolist())
    
            seleccion_tipos = col_filtro.multiselect(
                "🎯 Filtrar por tipo de bono:",
                options=tipos_disponibles,
                default=tipos_disponibles
            )
    
            if seleccion_tipos:
                df_resumen = df_resumen[df_resumen["Tipo de bono"].isin(seleccion_tipos)]
    
            if not df_resumen.empty:
                st.dataframe(df_resumen, use_container_width=True)
    
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
                    df_resumen.to_excel(writer, index=False, sheet_name="Mi Jugada")
    
                st.download_button(
                    "⬇️ Descargar Excel",
                    data=output.getvalue(),
                    file_name="mijugada_resumen.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.info("ℹ️ No hay jugadores que coincidan con los filtros.")
    
        except Exception as e:
            st.error(f"❌ Error al consultar la vista resumen de Mi Jugada: {e}")
    
        st.markdown("----")
        st.subheader("🎁 Tabla de Bonos - Mi Jugada")
    
        try:
            df_bonos = cargar_tabla_bonos("mijugada", sh)
    
            if not df_bonos.empty:
                st.dataframe(df_bonos, use_container_width=True)
    
                output_bonos = io.BytesIO()
                with pd.ExcelWriter(output_bonos, engine="xlsxwriter") as writer:
                    df_bonos.to_excel(writer, index=False, sheet_name="Bonos_Mi_Jugada")
    
                st.download_button(
                    "⬇️ Descargar Tabla de Bonos",
                    data=output_bonos.getvalue(),
                    file_name="mijugada_bonos.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.info("ℹ️ No hay datos en la tabla de bonos de Mi Jugada.")
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

        st.markdown("### 📅 Filtrar jugadores por fecha")
        col1, col2 = st.columns(2)
        
        with col1:
            filtro_desde = st.date_input(
                "📆 Desde",
                value=pd.to_datetime("2023-01-01").date(),
                key="desde_atenea"
            )
        with col2:
            filtro_hasta = st.date_input(
                "📆 Hasta",
                value=datetime.date.today(),
                key="hasta_atenea"
            )
    
        try:
            engine = create_engine(st.secrets["DB_URL"])
            with engine.connect() as conn:
                query = f"""
                SELECT * FROM resumen_atenea_dinamico(
                    '{filtro_desde.strftime('%Y-%m-%d')}',
                    '{filtro_hasta.strftime('%Y-%m-%d')}'
                )
                ORDER BY "Ganacias casino" DESC
                """
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
    
            df_resumen["Tipo de bono"] = df_resumen["Tipo de bono"].fillna("N/A")
            col_filtro, _ = st.columns(2)
            tipos_disponibles = sorted(df_resumen["Tipo de bono"].unique().tolist())
    
            seleccion_tipos = col_filtro.multiselect(
                "🎯 Filtrar por tipo de bono:",
                options=tipos_disponibles,
                default=tipos_disponibles
            )
    
            if seleccion_tipos:
                df_resumen = df_resumen[df_resumen["Tipo de bono"].isin(seleccion_tipos)]
    
            if not df_resumen.empty:
                st.dataframe(df_resumen, use_container_width=True)
    
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
                    df_resumen.to_excel(writer, index=False, sheet_name="Atenea")
    
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

        nombre_funcion = "resumen_padrino_latino_dinamico" if casino_actual == "Padrino Latino" else "resumen_tiger_dinamico"
        st.markdown("### 📅 Filtrar jugadores por fecha")

        col1, col2 = st.columns(2)
        
        with col1:
            filtro_desde = st.date_input(
                "📆 Desde",
                value=pd.to_datetime("2023-01-01").date(),
                key="desde_fecha_padrino_tiger"
            )
        with col2:
            filtro_hasta = st.date_input(
                "📆 Hasta",
               value=datetime.date.today(),
                key="hasta_fecha_padrino_tiger"
            )

        try:
            engine = create_engine(st.secrets["DB_URL"])
            with engine.connect() as conn:
                query = f"""
                SELECT * FROM {nombre_funcion}(
                  '{filtro_desde.strftime('%Y-%m-%d')}',
                  '{filtro_hasta.strftime('%Y-%m-%d')}'
                )
                ORDER BY "Ganacias casino" DESC
                """
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
        
            # 🎯 Filtro por tipo de bono
            df_resumen["Tipo de bono"] = df_resumen["Tipo de bono"].fillna("N/A")
            col_filtro, col_orden = st.columns(2)
            tipos_disponibles = sorted(df_resumen["Tipo de bono"].unique().tolist())
        
            seleccion_tipos = col_filtro.multiselect(
                "🎯 Filtrar por tipo de bono:",
                options=tipos_disponibles,
                default=[]  # ← esto evita que se filtre por defecto
            )
            
            if seleccion_tipos:
                df_resumen = df_resumen[df_resumen["Tipo de bono"].isin(seleccion_tipos)]
        
            # ✅ Mostrar y exportar
            if not df_resumen.empty:
                st.dataframe(df_resumen, use_container_width=True)
        
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
                    df_resumen.to_excel(writer, index=False, sheet_name=casino_actual)
        
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

        nombre_funcion = "resumen_fortuna_dinamico" if casino_actual == "Fortuna" else "resumen_gana24_dinamico"
        st.markdown("### 📅 Filtrar jugadores por fecha")
        col1, col2 = st.columns(2)
        
        with col1:
            filtro_desde = st.date_input(
                "📆 Desde",
                value=pd.to_datetime("2023-01-01").date(),
                key="desde_fecha_fortuna_gana24"
            )
        with col2:
            filtro_hasta = st.date_input(
                "📆 Hasta",
                value=datetime.date.today(),
                key="hasta_fecha_fortuna_gana24"
            )

        try:
            engine = create_engine(st.secrets["DB_URL"])
            with engine.connect() as conn:
                query = f"""
                SELECT * FROM {nombre_funcion}(
                  '{filtro_desde.strftime('%Y-%m-%d')}',
                  '{filtro_hasta.strftime('%Y-%m-%d')}'
                )
                ORDER BY "Ganacias casino" DESC
                """
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

            df_resumen["Tipo de bono"] = df_resumen["Tipo de bono"].fillna("N/A")
            col_filtro, _ = st.columns(2)
            tipos_disponibles = sorted(df_resumen["Tipo de bono"].unique().tolist())

            seleccion_tipos = col_filtro.multiselect(
                "🎯 Filtrar por tipo de bono:",
                options=tipos_disponibles,
                default=[]
            )

            if seleccion_tipos:
                df_resumen = df_resumen[df_resumen["Tipo de bono"].isin(seleccion_tipos)]

            if not df_resumen.empty:
                st.dataframe(df_resumen, use_container_width=True)

                output = io.BytesIO()
                with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
                    df_resumen.to_excel(writer, index=False, sheet_name=casino_actual)

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

    elif "🗒️ Registro de Contactos" in seccion:
        st.header("🗒️ Registro de Contactos")
    
        casino_actual = st.selectbox("🎰 Casino del archivo", [
            "Fénix", "Eros", "Bet Argento", "Atlantis", "Spirita", "Atenea", "Mi jugada"
        ], key="casino_selector_registro")
    
        archivo_reg = st.file_uploader("📁 Subí el archivo de REGISTRO (.xlsx o .csv)", type=["xlsx","csv"], key="uploader_registro")
    
        if archivo_reg:
            try:
                # leer archivo
                if archivo_reg.name.lower().endswith(".xlsx"):
                    df_raw = pd.read_excel(archivo_reg)
                else:
                    df_raw = pd.read_csv(archivo_reg, encoding="utf-8", sep=",")  # ajustá ';' si tu CSV lo usa
    
                # limpiar y normalizar
                df_reg = limpiar_registro(df_raw, casino_actual)
    
                if df_reg.empty:
                    st.warning("⚠️ No se detectaron filas válidas tras la limpieza.")
                else:
                    # mini QC opcional
                    col_a, col_b, col_c = st.columns(3)
                    with col_a: st.metric("Filas limpias", len(df_reg))
                    with col_b: st.metric("ext_id faltantes", int(df_reg["ext_id"].isna().sum()))
                    with col_c: st.metric("Usuarios únicos", df_reg["usuario_norm"].nunique())
    
                    st.write("Vista previa (primeras 50 filas):")
                    st.dataframe(df_reg.head(50), use_container_width=True)
    
                    engine = create_engine(st.secrets["DB_URL"])  # mantenemos tu estilo
    
                    generar = st.checkbox("Generar ext_id si falta (hash usuario|fecha|casino)", value=False)
                    if st.button("🚀 Guardar en tabla `registro`"):
                        upsert_registro(df_reg, engine, use_ext_id=True, generar_hash_si_falta=generar)
    
            except Exception as e:
                st.error(f"❌ Error al procesar archivo de registro: {e}")

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

                query_resumen = "SELECT * FROM resumen_vip"
                try:
                    resumen_vip = pd.read_sql(query_resumen, conn)
                except Exception as e:
                    st.error(f"❌ Error al consultar la vista resumen_vip: {e}")
                    resumen_vip = pd.DataFrame()
                
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

                            # === RESUMEN VIP ADICIONAL (por jugador, casino, etc) ===
                            st.markdown("### 🧾 Resumen VIP")
                            st.dataframe(resumen_vip, use_container_width=True)    
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
                        # Consulta específica a resumen_vip con las columnas seleccionadas
                        query_resumen_vip = """
                            SELECT jugador, casino, princi, clasificacion, monto_total, total_retirado, 
                                   ultima_vez_que_cargo, racha_activa_dias, fin_racha_activa, dias_desde_ultima_carga
                            FROM resumen_vip
                        """
                        
                        # Leer datos desde Supabase
                        df_resumen_vip = pd.read_sql(query_resumen_vip, conn)
                        
                        # Agregamos el filtro de casino
                        st.markdown("### 🔍 Filtro de Casino")
                        
                        # Obtenemos los casinos únicos desde el df_resumen_vip
                        casinos_disponibles = ["Todos"] + list(df_resumen_vip["casino"].unique())
                        casino_filtro = st.selectbox("🏢 Casino", casinos_disponibles)
                        
                        if casino_filtro != "Todos":
                            df_resumen_vip = df_resumen_vip[df_resumen_vip["casino"] == casino_filtro]
                        
                        # --- Nuevo filtro por clasificación ---
                        if "clasificacion" in df_resumen_vip.columns:
                            # Normalizamos para evitar problemas de mayúsculas/espacios
                            opciones_norm = (
                                df_resumen_vip["clasificacion"]
                                .dropna()
                                .astype(str)
                                .str.strip()
                                .str.lower()
                                .unique()
                            )
                            # Armamos opciones visibles (capitalizadas)
                            opciones_visibles = ["Todos"] + [opt.capitalize() for opt in sorted(opciones_norm)]
                            
                            # Preseleccionar "Oro" si existe; si no, "Todos"
                            index_default = opciones_visibles.index("Oro") if "oro" in opciones_norm else 0
                            clasificacion_filtro = st.selectbox("🏷 Clasificación", opciones_visibles, index=index_default)
                        
                            if clasificacion_filtro != "Todos":
                                df_resumen_vip = df_resumen_vip[
                                    df_resumen_vip["clasificacion"].astype(str).str.strip().str.lower() == clasificacion_filtro.lower()
                                ]
                        
                        # Mostramos la tabla resumida ya filtrada
                        st.markdown("### 📊 Resumen Operativo Actual de VIPs")
                        st.dataframe(df_resumen_vip, use_container_width=True)

                        
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
                        ["Fenix", "Eros", "Bet Argento", "Atlantis","Spirita"],
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








        
