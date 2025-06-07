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

from sqlalchemy import create_engine
import psycopg2
from sqlalchemy.exc import SQLAlchemyError

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
        "admin": ["🏢 Oficina VIP", "📋 Registro Fénix/Eros", "📋 Registro BetArgento/Atlantis","📋 Registro Spirita","📋 Registro Atenea","📋 Registro Padrino Latino/Tiger","📆 Agenda Fénix","📆 Agenda Eros","📆 Agenda BetArgento","📊 Análisis Temporal","🔝 Métricas de jugadores"],
        "fenix_eros": ["🔝 Métricas de jugadores", "📋 Registro Fénix/Eros"],
        "bet": ["🔝 Métricas de jugadores","📋 Registro BetArgento/Atlantis"],
        "spirita":["🔝 Métricas de jugadores","📋 Registro Spirita"],
        "atenea":["🔝 Métricas de jugadores","📋 Registro Atenea"],
        "padrino":["🔝 Métricas de jugadores","📋 Registro Padrino Latino/Tiger"]
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


    # --- SECCION 1: METRICAS DE JUGADORES ---
    if seccion == "🔝 Métricas de jugadores":
        st.header("📊 Métricas de Jugadores - Análisis de Cargas")
    
        top_n = st.selectbox("Selecciona el número de jugadores a mostrar:", [30, 50, 100, 150, 200], index=0)
        archivo = st.file_uploader("📁 Subí tu archivo de cargas recientes:", type=["xlsx", "xls", "csv"], key="top10")
    
        if archivo:
            df = pd.read_excel(archivo) if archivo.name.endswith((".xlsx", ".xls")) else pd.read_csv(archivo)
            df = preparar_dataframe(df)
    
            if df is not None:
                df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce")
                df["Hora"] = pd.to_datetime(df["Hora"], format="%H:%M:%S", errors="coerce").dt.hour
                df["Monto"] = pd.to_numeric(df["Monto"], errors="coerce").fillna(0)
                df_cargas = df[df["Tipo"] == "in"]
    
                # --- KPIs ---
                total_cargado = df_cargas["Monto"].sum()
                promedio_carga = df_cargas["Monto"].mean()
                total_jugadores = df_cargas["Jugador"].nunique()
    
                col1, col2, col3 = st.columns(3)
                col1.metric("💰 Total Cargado", f"${total_cargado:,.0f}")
                col2.metric("🎯 Promedio por Carga", f"${promedio_carga:,.0f}")
                col3.metric("🧑 Jugadores Únicos", total_jugadores)
    
                st.markdown("---")
    
                # --- TOP MONTO Y CANTIDAD ---
                top_monto = (
                    df_cargas.groupby("Jugador")
                    .agg(Monto_Total_Cargado=("Monto", "sum"), Cantidad_Cargas=("Jugador", "count"))
                    .sort_values(by="Monto_Total_Cargado", ascending=False)
                    .head(top_n)
                    .reset_index()
                )
                top_monto['Última vez que cargó'] = top_monto['Jugador'].apply(lambda x: df_cargas[df_cargas['Jugador'] == x]['Fecha'].max())
    
                top_cant = (
                    df_cargas.groupby("Jugador")
                    .agg(Cantidad_Cargas=("Jugador", "count"), Monto_Total_Cargado=("Monto", "sum"))
                    .sort_values(by="Cantidad_Cargas", ascending=False)
                    .head(top_n)
                    .reset_index()
                )
                top_cant['Última vez que cargó'] = top_cant['Jugador'].apply(lambda x: df_cargas[df_cargas['Jugador'] == x]['Fecha'].max())
    
                # --- VISUALIZACIONES ---
                st.subheader("📈 Evolución diaria de cargas")
                cargas_diarias = df_cargas.groupby(df_cargas["Fecha"].dt.date)["Monto"].sum().reset_index()
                graf_linea = px.line(cargas_diarias, x="Fecha", y="Monto", title="Cargas por día", markers=True, labels={"Monto": "Monto Total ($)"})
                st.plotly_chart(graf_linea, use_container_width=True)
    
                st.subheader("📊 Distribución de montos de carga")
                graf_hist = px.histogram(df_cargas, x="Monto", nbins=20, title="Distribución de Montos de Carga", labels={"Monto": "Monto Cargado ($)"})
                st.plotly_chart(graf_hist, use_container_width=True)
    
                st.subheader("🌡️ Mapa de Calor de Actividad Horaria")
                heatmap_data = df_cargas.copy()
                heatmap_data["Día"] = heatmap_data["Fecha"].dt.strftime("%Y-%m-%d")
                graf_heatmap = px.density_heatmap(
                    heatmap_data,
                    x="Hora",
                    y="Día",
                    nbinsx=24,
                    color_continuous_scale="Blues",
                    title="Actividad de cargas por hora y día",
                    labels={"Hora": "Hora del día", "Día": "Fecha"}
                )
                st.plotly_chart(graf_heatmap, use_container_width=True)
    
                st.markdown("---")
    
                # --- TABLAS ---
                st.subheader(f"💵 Top {top_n} por Monto Total Cargado")
                st.dataframe(top_monto)
    
                st.subheader(f"📈 Top {top_n} por Cantidad de Cargas")
                st.dataframe(top_cant)
    
                # --- EXPORTAR ---
                try:
                    with pd.ExcelWriter(f"Top{top_n}_Cargas.xlsx", engine="openpyxl") as writer:
                        top_monto.to_excel(writer, sheet_name="Top Monto", index=False)
                        top_cant.to_excel(writer, sheet_name="Top Cantidad", index=False)
                    with open(f"Top{top_n}_Cargas.xlsx", "rb") as f:
                        st.download_button(f"📅 Descargar Excel - Top {top_n} Cargas", f, file_name=f"Top{top_n}_Cargas.xlsx")
                except Exception as e:
                    st.error(f"❌ Error al guardar el archivo: {e}")
    
            else:
                st.error("❌ El archivo no tiene el formato esperado.")
    
    

    elif "📋 Registro Fénix/Eros" in seccion:
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
                default=tipos_disponibles
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

    
    # === SECCIÓN: 🏢 Oficina VIP Grilla ===
    elif "🏢 Oficina VIP" in seccion:
            st.title("📊 Visualización y análisis de jugadores VIP")
        
            try:
                engine = create_engine(st.secrets["DB_URL"])
                with engine.connect() as conn:
                    st.success("✅ Conectado a Supabase correctamente")
        
                    st.subheader("👀 Vista de tabla jugadores_vip")
                    
                    # 🔘 Selector de vista
                    opcion_vista = st.radio(
                        "🔎 ¿Qué datos querés mostrar?",
                        ["Top 10 por total apostado", "Todos los jugadores"]
                    )
                    
                    # 📥 Consulta según opción elegida
                    if opcion_vista == "Top 10 por total apostado":
                        query = "SELECT * FROM jugadores_vip ORDER BY total_apostado DESC LIMIT 10"
                    else:
                        query = "SELECT * FROM jugadores_vip ORDER BY total_apostado DESC"
                    
                    # 📊 Leer tabla
                    try:
                        df_vip = pd.read_sql(query, conn)
                    
                        if not df_vip.empty:
                            # 🔢 KPIs rápidas
                            total = df_vip["usuario"].nunique()
                            riesgo_alto = df_vip[df_vip["riesgo_abandono"] == "alto"].shape[0]
                            riesgo_medio = df_vip[df_vip["riesgo_abandono"] == "medio"].shape[0]
                            riesgo_bajo = df_vip[df_vip["riesgo_abandono"] == "bajo"].shape[0]
                            total_apostado = df_vip["total_apostado"].sum()
                            total_cargado = df_vip["total_cargado"].sum()
                    
                            col1, col2, col3 = st.columns(3)
                            col1.metric("🔴 Riesgo Alto", riesgo_alto)
                            col2.metric("🟠 Riesgo Medio", riesgo_medio)
                            col3.metric("🟢 Riesgo Bajo", riesgo_bajo)
                    
                            # 📄 Mostrar tabla
                            st.dataframe(df_vip, use_container_width=True)
                    
                            # 💾 Descargar como Excel
                            output = io.BytesIO()
                            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                                df_vip.to_excel(writer, index=False, sheet_name='jugadores_vip')
                            st.download_button(
                                "⬇️ Descargar Excel",
                                data=output.getvalue(),
                                file_name="jugadores_vip.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                            )
                        else:
                            st.info("ℹ️ La tabla jugadores_vip no contiene registros aún.")
                    
                    except Exception as e:
                        st.error(f"❌ Error al consultar la tabla jugadores_vip: {e}")
        
                    st.markdown("---")
                    casino = st.selectbox("🏷️ Seleccioná el casino al que pertenece este archivo", ["Fenix", "Eros", "Bet Argento", "Atlantis"])
        
                    tipo_archivo = st.radio("📂 Tipo de carga", ["Archivo individual (.csv o .xlsx)", "Archivo ZIP con múltiples historiales"])
        
                    if tipo_archivo == "Archivo individual (.csv o .xlsx)":
                        archivo = st.file_uploader("📎 Subí tu archivo", type=["csv", "xlsx"])
                        if archivo:
                            try:
                                if archivo.name.endswith(".csv"):
                                    df = pd.read_csv(archivo)
                                else:
                                    df = pd.read_excel(archivo)
        
                                df.columns = df.columns.str.strip()
                                df["casino"] = casino
        
                                st.write("📄 Vista previa del archivo cargado:")
                                st.dataframe(df.head())
        
                                if df.empty:
                                    st.warning("⚠️ El archivo está vacío o malformado.")
                                else:
                                    tabla = detectar_tabla(df)
        
                                    if tabla in {"actividad_jugador_cruda", "transacciones_crudas", "bonos_crudos", "catalogo_juegos"}:
                                        st.info(f"📌 El archivo será cargado en la tabla {tabla}.")
                                        subir_a_supabase(df, tabla, engine)
                                    elif tabla == "jugadores_vip":
                                        st.error("❌ No se puede subir directamente a la tabla jugadores_vip. Esta tabla es generada automáticamente.")
                                    else:
                                        st.warning("⚠️ No se pudo detectar a qué tabla pertenece el archivo. Verificá las columnas.")
                            except Exception as e:
                                st.error(f"❌ Error al procesar el archivo: {e}")
        
                    elif tipo_archivo == "Archivo ZIP con múltiples historiales":
                        archivo_zip = st.file_uploader("📦 Subí el archivo ZIP", type=["zip"])
        
                        if archivo_zip:
                            with st.spinner("⏳ Procesando ZIP..."):
                                try:
                                    with tempfile.TemporaryDirectory() as tmpdir:
                                        zip_path = os.path.join(tmpdir, "reportes.zip")
                                        with open(zip_path, "wb") as f:
                                            f.write(archivo_zip.getbuffer())
        
                                        with zipfile.ZipFile(zip_path, "r") as zip_ref:
                                            zip_ref.extractall(tmpdir)
        
                                        archivos_xlsx = list(Path(tmpdir).rglob("*.xlsx"))
                                        if not archivos_xlsx:
                                            st.warning("⚠️ No se encontraron archivos .xlsx en el ZIP.")
                                        else:
                                            dataframes = []
                                            for archivo in archivos_xlsx:
                                                try:
                                                    df_historia = pd.read_excel(archivo, sheet_name="Historia")
                                                    df_historia.columns = df_historia.columns.str.strip()
        
                                                    nombre_real = extraer_nombre_real_desde_info(archivo)
                                                    if nombre_real and "Usuario" in df_historia.columns:
                                                        df_historia["Usuario"] = nombre_real
        
                                                    df_historia["casino"] = casino
                                                    dataframes.append(df_historia)
                                                except Exception as e:
                                                    st.warning(f"No se pudo procesar {archivo.name}: {e}")
        
                                            if dataframes:
                                                df_final = pd.concat(dataframes, ignore_index=True)
                                                st.success(f"✅ Consolidación completa: {len(df_final)} registros")
                                                st.dataframe(df_final.head())
                                                subir_a_supabase(df_final, "actividad_jugador_cruda", engine)
                                            else:
                                                st.warning("⚠️ No se pudo consolidar ningún archivo válido.")
                                except Exception as e:
                                    st.error(f"❌ Error al procesar el ZIP: {e}")
            except Exception as e:
                st.error(f"❌ Error de conexión: {e}")








        
