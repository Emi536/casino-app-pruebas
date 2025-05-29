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

from sqlalchemy import create_engine
import psycopg2


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
        "admin": ["🏢 Oficina VIP", "📋 Registro Fénix", "📋 Registro Eros", "📋 Registro Bet Argento","📋 Registro Spirita","📆 Agenda Fénix","📆 Agenda Eros","📆 Agenda BetArgento","📊 Análisis Temporal","🔝 Métricas de jugadores"],
        "fenix_eros": ["🔝 Métricas de jugadores", "📋 Registro Fénix", "📋 Registro Eros"],
        "bet": ["🔝 Métricas de jugadores","📋 Registro Bet Argento"],
        "spirita":["🔝 Métricas de jugadores","📋 Registro Spirita"]
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
    
    

    # SECCIÓN FÉNIX
    elif "📋 Registro Fénix" in seccion:
        st.header("📋 Registro general de jugadores - Fénix")
    
        argentina = pytz.timezone("America/Argentina/Buenos_Aires")
        ahora = datetime.datetime.now(argentina)
        fecha_actual = ahora.strftime("%d/%m/%Y - %H:%M hs")
        fecha_actual_date = ahora.date()
        st.info(f"⏰ Última actualización: {fecha_actual}")
    
        responsable = st.text_input("👤 Ingresá tu nombre para registrar quién sube el reporte", value="Anónimo")
    
        texto_pegar = st.text_area("📋 Pegá aquí el reporte copiado (incluí encabezados)", height=300, key="texto_pegar")
        df_historial = pd.DataFrame()
    
        try:
            hoja_fenix = sh.worksheet("registro_fenix")
            data_fenix = hoja_fenix.get_all_records()
            df_historial = pd.DataFrame(data_fenix)
        except:
            hoja_fenix = sh.add_worksheet(title="registro_fenix", rows="1000", cols="20")
            df_historial = pd.DataFrame()
    
        def convertir_monto(valor):
            if pd.isna(valor): return 0.0
            valor = str(valor)
            valor = valor.replace("\u202f", "").replace("\xa0", "").replace(" ", "").replace(",", "")
            try:
                return float(valor)
            except:
                return 0.0
    
        def limpiar_dataframe(df_temp):
            df_temp = df_temp.copy()
            if "Jugador" in df_temp.columns:
                df_temp["Jugador"] = df_temp["Jugador"].astype(str).str.strip().str.lower()
            for col in ["Monto", "Retiro", "Balance antes de operación", "Wager"]:
                if col in df_temp.columns:
                    df_temp[col] = df_temp[col].apply(convertir_monto)
            if "Fecha" in df_temp.columns:
                df_temp["Fecha"] = pd.to_datetime(df_temp["Fecha"], errors="coerce")
            return df_temp
    
        def procesar_retiros_validos(df, iniciadores_validos):
            df["FechaHora"] = pd.to_datetime(df["Fecha"].astype(str) + " " + df["Hora"].astype(str), errors="coerce")
            df_retiros_validos = df[
                (df["Tipo"].str.lower() == "out") & df["Iniciador"].isin(iniciadores_validos)
            ].copy()
            df_cargas = df[df["Tipo"].str.lower() == "in"].copy()
            df_retiros_validos["Clave"] = df_retiros_validos["Jugador"] + df_retiros_validos["Retiro"].astype(str)
            df_cargas["Clave"] = df_cargas["Jugador"] + df_cargas["Monto"].astype(str)
            df_cargas["FechaHora"] = pd.to_datetime(df_cargas["Fecha"].astype(str) + " " + df_cargas["Hora"].astype(str), errors="coerce")
            claves_cargas = df_cargas.set_index("Clave")["FechaHora"].to_dict()
            indices_a_excluir = []
            for i, row in df_retiros_validos.iterrows():
                clave = row["Clave"]
                if clave in claves_cargas:
                    delta = row["FechaHora"] - claves_cargas[clave]
                    if pd.notnull(delta) and delta.total_seconds() <= 300:
                        indices_a_excluir.append(i)
            df_retiros_validos = df_retiros_validos.drop(index=indices_a_excluir)
            return df_retiros_validos
    
        df_historial = limpiar_dataframe(df_historial)
    
        if "Fecha" in df_historial.columns:
            df_historial["Fecha"] = pd.to_datetime(df_historial["Fecha"], errors="coerce")
            df_historial = df_historial[df_historial["Fecha"].notna()]
            limite = fecha_actual_date - datetime.timedelta(days=30)
            df_historial = df_historial[df_historial["Fecha"].dt.date >= limite]
    
        if texto_pegar:
            try:
                sep_detectado = "\t" if "\t" in texto_pegar else ";" if ";" in texto_pegar else ","
                lineas = texto_pegar.strip().splitlines()
                encabezados = lineas[0].split(sep_detectado)
                cantidad_columnas = len(encabezados)
    
                contenido_limpio = [sep_detectado.join(encabezados)]
                for fila in lineas[1:]:
                    columnas = fila.split(sep_detectado)
                    if len(columnas) < cantidad_columnas:
                        columnas += [""] * (cantidad_columnas - len(columnas))
                    elif len(columnas) > cantidad_columnas:
                        columnas = columnas[:cantidad_columnas]
                    contenido_limpio.append(sep_detectado.join(columnas))
    
                archivo_limpio = StringIO("\n".join(contenido_limpio))
                df_nuevo = pd.read_csv(archivo_limpio, sep=sep_detectado, dtype=str, encoding="utf-8")
                df_nuevo = df_nuevo.loc[:, ~df_nuevo.columns.str.contains("^Unnamed")]
    
                # 🔁 Limpiar montos ANTES de renombrar
                for col in ["Depositar", "Retirar", "Wager", "Balance antes de operación"]:
                    if col in df_nuevo.columns:
                        df_nuevo[col] = (
                            df_nuevo[col]
                            .astype(str)
                            .str.replace(",", "", regex=False)
                            .str.replace(" ", "", regex=False)
                        )
                        df_nuevo[col] = pd.to_numeric(df_nuevo[col], errors="coerce").fillna(0.0)
    
                columnas_requeridas = ["operación", "Depositar", "Retirar", "Fecha", "Al usuario"]
                if not all(col in df_nuevo.columns for col in columnas_requeridas):
                    st.error("❌ El reporte pegado no contiene los encabezados necesarios o está mal formateado.")
                    st.stop()
    
                df_nuevo = df_nuevo.rename(columns={
                    "operación": "Tipo",
                    "Depositar": "Monto",
                    "Retirar": "Retiro",
                    "Fecha": "Fecha",
                    "Tiempo": "Hora",
                    "Al usuario": "Jugador"
                })
    
                df_nuevo["Responsable"] = responsable
                df_nuevo["Fecha_Subida"] = fecha_actual
    
                valores_fenix = [
                    "hl_casinofenix",
                    "Fenix_Wagger100", "Fenix_Wagger40", "Fenix_Wagger30",
                    "Fenix_Wagger50", "Fenix_Wagger150", "Fenix_Wagger200"
                ]
                if "Del usuario" in df_nuevo.columns:
                    df_nuevo["Del usuario"] = df_nuevo["Del usuario"].astype(str).str.strip()
                    df_nuevo = df_nuevo[df_nuevo["Del usuario"].isin(valores_fenix)]
    
                df_nuevo = limpiar_dataframe(df_nuevo)
    
                if "ID" in df_nuevo.columns and "ID" in df_historial.columns:
                    ids_existentes = df_historial["ID"].astype(str).tolist()
                    df_nuevo = df_nuevo[~df_nuevo["ID"].astype(str).isin(ids_existentes)]
    
                if df_nuevo.empty:
                    st.warning("⚠️ Todos los registros pegados ya existían en el historial (mismo ID). No se agregó nada.")
                    st.stop()
    
                df_historial = pd.concat([df_historial, df_nuevo], ignore_index=True)
                df_historial.drop_duplicates(subset=["ID"], inplace=True)
    
                hoja_fenix.clear()
                hoja_fenix.update([df_historial.columns.tolist()] + df_historial.astype(str).values.tolist())
    
                st.success(f"✅ Registros de Fénix actualizados correctamente. Total acumulado: {len(df_historial)}")
    
            except Exception as e:
                st.error(f"❌ Error al procesar los datos pegados: {e}")

        if not df_historial.empty:
            st.info(f"📊 Total de registros acumulados: {len(df_historial)}")

            # 🗓️ Filtro por fecha de los registros individuales
            st.markdown("### 📅 Filtrar registros por fecha de actividad")
            col1, col2 = st.columns(2)
            with col1:
                filtro_desde = st.date_input("📆 Desde", value=df_historial["Fecha"].min().date(), key="desde_historial_filtro")
            with col2:
                filtro_hasta = st.date_input("📆 Hasta", value=df_historial["Fecha"].max().date(), key="hasta_historial_filtro")
        
            df_historial_filtrado = df_historial[
                (df_historial["Fecha"].dt.date >= filtro_desde) &
                (df_historial["Fecha"].dt.date <= filtro_hasta)
            ].copy()

            df = df_historial_filtrado.copy()
            if "Tiempo" in df.columns and "Hora" not in df.columns:
                df = df.rename(columns={"Tiempo": "Hora"})
        
            def hash_dataframe(df):
                return hashlib.md5(pd.util.hash_pandas_object(df, index=True).values).hexdigest()
        
            df_hash = hash_dataframe(df)
            actualizar = st.button("🔄 Recalcular resumen de jugadores")
        
            resumen_path = "resumen_fenix_cache.pkl"
            hash_path = "resumen_fenix_hash.txt"
        
            resumen = []
            resumen_actualizado = False
        
            if os.path.exists(resumen_path) and os.path.exists(hash_path):
                with open(hash_path, "r") as f:
                    hash_guardado = f.read().strip()
                if hash_guardado == df_hash and not actualizar:
                    with open(resumen_path, "rb") as f:
                        resumen = pickle.load(f)
                    st.info("⚡️ Resumen cargado desde caché local.")
                else:
                    resumen_actualizado = True
            else:
                resumen_actualizado = True
        
            if resumen_actualizado:
                from collections import Counter
                valores_hl = ["hl_casinofenix"]
                valores_wagger = [
                    "Fenix_Wagger100", "Fenix_Wagger40", "Fenix_Wagger30",
                    "Fenix_Wagger50", "Fenix_Wagger150", "Fenix_Wagger200"
                ]
                jugadores = df["Jugador"].dropna().unique()
        
                for jugador in jugadores:
                    historial = df[df["Jugador"] == jugador].sort_values("Fecha")
                    cargas = historial[historial["Tipo"].str.lower() == "in"]
                    retiros = procesar_retiros_validos(historial, ["DemonGOD", "DaniGOD", "NahueGOD", "CajeroJuancho", "JuanpiCajero", "FlorGOD", "SebaGOD"])
        
                    cargas_hl = cargas[cargas["Del usuario"].isin(valores_hl)]
                    cargas_wagger = cargas[cargas["Del usuario"].isin(valores_wagger)]
        
                    hl = cargas_hl["Monto"].sum()
                    wagger = cargas_wagger["Monto"].sum()
                    total_monto = hl + wagger
                    total_retiro = retiros["Retiro"].sum()
                    ganancias_casino = total_monto - total_retiro
        
                    rango = "Sin datos"
                    if not cargas.empty and "Hora" in cargas.columns:
                        try:
                            cargas["Hora"] = pd.to_datetime(cargas["Hora"], format="%H:%M:%S", errors="coerce")
                            cargas["Día"] = cargas["Fecha"].dt.date
                            cargas["Hora_hora"] = cargas["Hora"].dt.hour
                            hora_por_dia = cargas.groupby("Día")["Hora_hora"].agg(lambda x: int(x.median()))
                            conteo = Counter(hora_por_dia)
                            if conteo:
                                hora_patron, repeticiones = conteo.most_common(1)[0]
                                if repeticiones >= 2:
                                    if 6 <= hora_patron < 12:
                                        franja = "Mañana"
                                    elif 12 <= hora_patron < 18:
                                        franja = "Tarde"
                                    elif 18 <= hora_patron < 24:
                                        franja = "Noche"
                                    else:
                                        franja = "Madrugada"
                                    rango = f"{franja} ({hora_patron:02d}:00 hs) – patrón en {repeticiones} días"
                                else:
                                    rango = "Actividad dispersa"
                        except:
                            rango = "Sin datos"
        
                    if not cargas.empty:
                        ultima_fecha = cargas["Fecha"].max()
                        resumen.append({
                            "Nombre de jugador": jugador,
                            "Tipo de bono": "",
                            "Fecha que ingresó": cargas["Fecha"].min(),
                            "Veces que cargó": len(cargas),
                            "Hl": hl,
                            "Wagger": wagger,
                            "Monto total": total_monto,
                            "Cantidad de retiro": total_retiro,
                            "Ganacias casino": ganancias_casino,
                            "Rango horario de juego": rango,
                            "Última vez que cargó": ultima_fecha,
                            "Días inactivo": (pd.to_datetime(datetime.date.today()) - ultima_fecha).days,
                            "Racha Activa (Días)": (ultima_fecha - cargas["Fecha"].min()).days,
                            "Última vez que se lo contacto": ""
                        })
        
                with open(resumen_path, "wb") as f:
                    pickle.dump(resumen, f)
                with open(hash_path, "w") as f:
                    f.write(df_hash)
                st.success("✅ Resumen recalculado y cacheado.")
        
            df_registro = pd.DataFrame(resumen).sort_values("Última vez que cargó", ascending=False)

            try:
                hoja_princi_fenix = sh.worksheet("princi_fenix")
                data_princi_fenix = hoja_princi_fenix.get_all_values()
                df_princi_fenix = pd.DataFrame(data_princi_fenix[1:], columns=data_princi_fenix[0])
            
                # Normalizar nombres: remover espacios, convertir a minúscula
                def normalizar(nombre):
                    return str(nombre).strip().lower().replace(" ", "").replace("_", "")
            
                # Crear un diccionario: nombre_normalizado ➝ princi
                mapping_princi_fenix = {}
                for col in df_princi_fenix.columns:
                    for nombre in df_princi_fenix[col]:
                        if nombre.strip():
                            nombre_norm = normalizar(nombre)
                            mapping_princi_fenix[nombre_norm] = col.strip().upper()
            
                # Asignar el princi al dataframe df_registro
                df_registro["Jugador_NORM"] = df_registro["Nombre de jugador"].apply(normalizar)
                df_registro["PRINCI"] = df_registro["Jugador_NORM"].map(mapping_princi_fenix).fillna("N/A")
                df_registro = df_registro.drop(columns=["Jugador_NORM"])
            
            except Exception as e:
                st.warning(f"⚠️ No se pudo asignar los PRINCI a los jugadores (Fénix): {e}")

            try:
                # 🧩 COMPLETAR TIPO DE BONO desde hoja 'registro_bono_fenix'
                hoja_users = sh.worksheet("registro_bono_fenix")
                raw_data_users = hoja_users.get_all_values()
                headers_users = raw_data_users[0]
                rows_users = raw_data_users[1:]
                df_users = pd.DataFrame(rows_users, columns=headers_users)
            
                # Normalizar nombres de usuario
                def normalizar_usuario(nombre):
                    return str(nombre).strip().lower().replace(" ", "").replace("_", "")
            
                df_users["USUARIO_NORM"] = df_users["USUARIO"].apply(normalizar_usuario)
            
                # ✅ Eliminar duplicados conservando la última aparición del usuario
                df_users = df_users.drop_duplicates(subset=["USUARIO_NORM"], keep="last")
            
                # Normalizar también en el DataFrame del resumen
                df_registro["JUGADOR_NORM"] = df_registro["Nombre de jugador"].apply(normalizar_usuario)
            
                # Merge para obtener el tipo de bono (FUNNEL)
                df_registro = df_registro.merge(
                    df_users[["USUARIO_NORM", "FUNNEL"]],
                    left_on="JUGADOR_NORM",
                    right_on="USUARIO_NORM",
                    how="left"
                ).drop(columns=["USUARIO_NORM", "JUGADOR_NORM"])
            
                # Asignar tipo de bono (rellenar con "N/A" si no hay match)
                df_registro["Tipo de bono"] = df_registro["FUNNEL"].fillna("N/A")
                df_registro = df_registro.drop(columns=["FUNNEL"])
                cols = df_registro.columns.tolist()
                if "Tipo de bono" in cols and "PRINCI" in cols:
                    cols.remove("PRINCI")
                    idx = cols.index("Tipo de bono") + 1
                    cols.insert(idx, "PRINCI")
                    df_registro = df_registro[cols]
            
            except Exception as e:
                st.warning(f"⚠️ No se pudo cargar el tipo de bono desde registro_bono_fenix: {e}")

            # ✅ Mostrar siempre la tabla y botón de descarga (fuera del try/except)
            st.subheader("📄 Registro completo de jugadores")

            col_filtro, col_orden = st.columns(2)
            
            # ✅ Filtro múltiple por tipo de bono
            tipos_disponibles = df_registro["Tipo de bono"].dropna().unique().tolist()
            tipos_disponibles.sort()
            seleccion_tipos = col_filtro.multiselect(
                "🎯 Filtrar por tipo de bono:",
                options=tipos_disponibles,
                default=["N/A"]  # Podés dejarlo vacío si querés que no filtre por defecto
            )
            
            # ✅ Selector de orden
            criterio_orden = col_orden.selectbox("📊 Ordenar por:", ["Sin ordenar", "Veces que cargó", "Monto total", "Racha Activa (Días)"])
            
            # ✅ Aplicar filtros
            if seleccion_tipos:
                df_registro = df_registro[df_registro["Tipo de bono"].isin(seleccion_tipos)]
            
            if criterio_orden != "Sin ordenar":
                columna_orden = {
                    "Veces que cargó": "Veces que cargó",
                    "Monto total": "Monto total",
                    "Racha Activa (Días)": "Racha Activa (Días)"
                }[criterio_orden]
                df_registro = df_registro.sort_values(by=columna_orden, ascending=False)

            try:
                hoja_bonos_fenix = sh.worksheet("bonos_ofrecidos_fenix")
                raw_data_bonos = hoja_bonos_fenix.get_all_values()
                df_bonos_fenix = pd.DataFrame(raw_data_bonos[1:], columns=raw_data_bonos[0])
            
                def normalizar(nombre):
                    return str(nombre).strip().lower().replace(" ", "").replace("_", "")
            
                # ✅ Limpiar y preparar bonos ofrecidos
                df_bonos_fenix = df_bonos_fenix[df_bonos_fenix["USUARIO"].notna()]
                df_bonos_fenix["FECHA"] = pd.to_datetime(df_bonos_fenix["FECHA"], errors="coerce")
                df_bonos_fenix = df_bonos_fenix[df_bonos_fenix["FECHA"].notna()]
                df_bonos_fenix["USUARIO_NORM"] = df_bonos_fenix["USUARIO"].apply(normalizar)
            
                # 📆 Últimos 3 días
                zona_ar = pytz.timezone("America/Argentina/Buenos_Aires")
                hoy = datetime.datetime.now(zona_ar).date()
                limite = hoy - datetime.timedelta(days=3)
            
                # 🎯 Usuarios con bono reciente
                usuarios_bono = df_bonos_fenix[df_bonos_fenix["FECHA"].dt.date >= limite]["USUARIO_NORM"].unique().tolist()
            
                # 🧹 Limpiar íconos anteriores y normalizar
                df_registro["Nombre limpio"] = df_registro["Nombre de jugador"].str.replace("🔴", "", regex=False)
                df_registro["JUGADOR_NORM"] = df_registro["Nombre limpio"].apply(normalizar)
            
                # 🔴 Marcar visualmente si recibió bono
                df_registro["Nombre de jugador"] = df_registro.apply(
                    lambda row: f"🔴 {row['Nombre limpio']}" if row["JUGADOR_NORM"] in usuarios_bono else row["Nombre limpio"],
                    axis=1
                )
            
                df_registro.drop(columns=["JUGADOR_NORM", "Nombre limpio"], inplace=True)
            
            except Exception as e:
                st.warning(f"⚠️ No se pudo marcar los usuarios con bono reciente: {e}")

            st.dataframe(df_registro)
            
            df_registro.to_excel("registro_jugadores_fenix.xlsx", index=False)
            with open("registro_jugadores_fenix.xlsx", "rb") as f:
                st.download_button("🗓️ Descargar Excel", f, file_name="registro_jugadores_fenix.xlsx")

    
            # 🔵 Tabla Bono Fénix desde hojas "registro_users" y "bonos_ofrecidos"
            try:
                # Leer hoja principal ignorando posibles conflictos de encabezado
                hoja_registro = sh.worksheet("registro_bono_fenix")
                raw_data = hoja_registro.get_all_values()
                headers = raw_data[0]
            
                # Manejar encabezados duplicados
                seen = set()
                unique_headers = []
                for header in headers:
                    if header in seen:
                        counter = 1
                        while f"{header}_{counter}" in seen:
                            counter += 1
                        header = f"{header}_{counter}"
                    seen.add(header)
                    unique_headers.append(header)
            
                rows = raw_data[1:]
                df_registro_users = pd.DataFrame(rows, columns=unique_headers)
            
                # 🟡 NORMALIZAR y ELIMINAR DUPLICADOS
                df_registro_users["USUARIO"] = df_registro_users["USUARIO"].astype(str).str.strip().str.lower()
                df_registro_users["USUARIO_NORM"] = df_registro_users["USUARIO"].apply(lambda x: x.replace(" ", "").replace("_", ""))
                df_registro_users = df_registro_users.drop_duplicates(subset=["USUARIO_NORM"], keep="last")
                df_registro_users = df_registro_users.drop(columns=["USUARIO_NORM"])
            
                # Leer hoja con categorías de bonos
                hoja_bonos = sh.worksheet("bonos_ofrecidos_fenix")
                raw_data_bonos = hoja_bonos.get_all_values()
                headers_bonos = raw_data_bonos[0]
            
                # Manejar encabezados duplicados en bonos
                seen_bonos = set()
                unique_headers_bonos = []
                for header in headers_bonos:
                    if header in seen_bonos:
                        counter = 1
                        while f"{header}_{counter}" in seen_bonos:
                            counter += 1
                        header = f"{header}_{counter}"
                    seen_bonos.add(header)
                    unique_headers_bonos.append(header)
            
                rows_bonos = raw_data_bonos[1:]
                df_bonos = pd.DataFrame(rows_bonos, columns=unique_headers_bonos)
            
                # Limpiar nombre de usuario
                df_bonos["USUARIO"] = df_bonos["USUARIO"].astype(str).str.strip().str.lower()
            
                # Obtener la última categoría de bono por usuario
                df_categorias = df_bonos.dropna(subset=["CATEGORIA DE BONO"]).sort_values("FECHA")
                df_categorias = df_categorias.groupby("USUARIO")["CATEGORIA DE BONO"].last().reset_index()
            
                # Unir con el registro principal
                df_bono = df_registro_users.merge(df_categorias, on="USUARIO", how="left")
            
                # Renombrar columnas al formato final
                df_bono = df_bono.rename(columns={
                    "USUARIO": "Usuario",
                    "FUNNEL": "Tipo de Bono",
                    "BONOS OFRECIDOS": "Cuántas veces se le ofreció el bono",
                    "BONOS USADOS": "Cuántas veces cargó con bono",
                    "MONTO TOTAL CARGADO": "Monto total",
                    "% DE CONVERSION": "Conversión",
                    "ULT. ACTUALIZACION": "Fecha del último mensaje",
                    "CATEGORIA DE BONO": "Categoría de Bono"
                })
            
                # Limpiar campos
                df_bono["Conversión"] = df_bono["Conversión"].astype(str).str.replace("%", "", regex=False)
                df_bono["Conversión"] = pd.to_numeric(df_bono["Conversión"], errors="coerce").fillna(0)
                df_bono["Fecha del último mensaje"] = df_bono["Fecha del último mensaje"].replace(["30/12/1899", "1899-12-30"], "Sin registros")
            
                # Seleccionar columnas finales
                columnas_finales = [
                    "Usuario", "Tipo de Bono",
                    "Cuántas veces se le ofreció el bono", "Cuántas veces cargó con bono",
                    "Monto total", "Conversión",
                    "Fecha del último mensaje", "Categoría de Bono"
                ]
                df_bono = df_bono[columnas_finales]
            
                # Mostrar en la app
                st.subheader("🎁 Tabla Bono - Fénix")
                st.dataframe(df_bono)
            
            except Exception as e:
                st.error(f"❌ Error al generar la Tabla Bono Fénix: {e}")
    
    #SECCIÓN EROS
    elif "📋 Registro Eros" in seccion:
        st.header("📋 Registro general de jugadores - Eros")
    
        argentina = pytz.timezone("America/Argentina/Buenos_Aires")
        ahora = datetime.datetime.now(argentina)
        fecha_actual = ahora.strftime("%d/%m/%Y - %H:%M hs")
        fecha_actual_date = ahora.date()
        st.info(f"⏰ Última actualización: {fecha_actual}")
    
        responsable = st.text_input("👤 Ingresá tu nombre para registrar quién sube el reporte", value="Anónimo")
    
        texto_pegar = st.text_area("📋 Pegá aquí el reporte copiado (incluí encabezados)", height=300, key="texto_pegar")
        df_historial = pd.DataFrame()
    
        try:
            hoja_eros = sh.worksheet("registro_eros")
            data_eros = hoja_eros.get_all_records()
            df_historial = pd.DataFrame(data_eros)
        except:
            hoja_eros = sh.add_worksheet(title="registro_eros", rows="1000", cols="20")
            df_historial = pd.DataFrame()
    
        def convertir_monto(valor):
            if pd.isna(valor): return 0.0
            valor = str(valor)
            valor = valor.replace("\u202f", "").replace("\xa0", "").replace(" ", "").replace(",", "")
            try:
                return float(valor)
            except:
                return 0.0
    
        def limpiar_dataframe(df_temp):
            df_temp = df_temp.copy()
            if "Jugador" in df_temp.columns:
                df_temp["Jugador"] = df_temp["Jugador"].astype(str).str.strip().str.lower()
            for col in ["Monto", "Retiro", "Balance antes de operación", "Wager"]:
                if col in df_temp.columns:
                    df_temp[col] = df_temp[col].apply(convertir_monto)
            if "Fecha" in df_temp.columns:
                df_temp["Fecha"] = pd.to_datetime(df_temp["Fecha"], errors="coerce")
            return df_temp
    
        def procesar_retiros_validos(df, iniciadores_validos):
            df["FechaHora"] = pd.to_datetime(df["Fecha"].astype(str) + " " + df["Hora"].astype(str), errors="coerce")
            df_retiros_validos = df[
                (df["Tipo"].str.lower() == "out") & df["Iniciador"].isin(iniciadores_validos)
            ].copy()
            df_cargas = df[df["Tipo"].str.lower() == "in"].copy()
            df_retiros_validos["Clave"] = df_retiros_validos["Jugador"] + df_retiros_validos["Retiro"].astype(str)
            df_cargas["Clave"] = df_cargas["Jugador"] + df_cargas["Monto"].astype(str)
            df_cargas["FechaHora"] = pd.to_datetime(df_cargas["Fecha"].astype(str) + " " + df_cargas["Hora"].astype(str), errors="coerce")
            claves_cargas = df_cargas.set_index("Clave")["FechaHora"].to_dict()
            indices_a_excluir = []
            for i, row in df_retiros_validos.iterrows():
                clave = row["Clave"]
                if clave in claves_cargas:
                    delta = row["FechaHora"] - claves_cargas[clave]
                    if pd.notnull(delta) and delta.total_seconds() <= 300:
                        indices_a_excluir.append(i)
            df_retiros_validos = df_retiros_validos.drop(index=indices_a_excluir)
            return df_retiros_validos
    
        df_historial = limpiar_dataframe(df_historial)
    
        if "Fecha" in df_historial.columns:
            df_historial["Fecha"] = pd.to_datetime(df_historial["Fecha"], errors="coerce")
            df_historial = df_historial[df_historial["Fecha"].notna()]
            limite = fecha_actual_date - datetime.timedelta(days=30)
            df_historial = df_historial[df_historial["Fecha"].dt.date >= limite]

        if texto_pegar:
            try:
                sep_detectado = "\t" if "\t" in texto_pegar else ";" if ";" in texto_pegar else ","
                lineas = texto_pegar.strip().splitlines()
                encabezados = lineas[0].split(sep_detectado)
                cantidad_columnas = len(encabezados)
    
                contenido_limpio = [sep_detectado.join(encabezados)]
                for fila in lineas[1:]:
                    columnas = fila.split(sep_detectado)
                    if len(columnas) < cantidad_columnas:
                        columnas += [""] * (cantidad_columnas - len(columnas))
                    elif len(columnas) > cantidad_columnas:
                        columnas = columnas[:cantidad_columnas]
                    contenido_limpio.append(sep_detectado.join(columnas))
    
                archivo_limpio = StringIO("\n".join(contenido_limpio))
                df_nuevo = pd.read_csv(archivo_limpio, sep=sep_detectado, dtype=str, encoding="utf-8")
                df_nuevo = df_nuevo.loc[:, ~df_nuevo.columns.str.contains("^Unnamed")]
    
                # 🔁 Limpiar montos ANTES de renombrar
                for col in ["Depositar", "Retirar", "Wager", "Balance antes de operación"]:
                    if col in df_nuevo.columns:
                        df_nuevo[col] = (
                            df_nuevo[col]
                            .astype(str)
                            .str.replace(",", "", regex=False)
                            .str.replace(" ", "", regex=False)
                        )
                        df_nuevo[col] = pd.to_numeric(df_nuevo[col], errors="coerce").fillna(0.0)
    
                columnas_requeridas = ["operación", "Depositar", "Retirar", "Fecha", "Al usuario"]
                if not all(col in df_nuevo.columns for col in columnas_requeridas):
                    st.error("❌ El reporte pegado no contiene los encabezados necesarios o está mal formateado.")
                    st.stop()
    
                df_nuevo = df_nuevo.rename(columns={
                    "operación": "Tipo",
                    "Depositar": "Monto",
                    "Retirar": "Retiro",
                    "Fecha": "Fecha",
                    "Tiempo": "Hora",
                    "Al usuario": "Jugador"
                })
    
                df_nuevo["Responsable"] = responsable
                df_nuevo["Fecha_Subida"] = fecha_actual
    
                valores_eros = [
                    "hl_Erosonline",
                    "Eros_wagger30%", "Eros_wagger40%", "Eros_wagger50%",
                    "Eros_wagger100%", "Eros_wagger150%", "Eros_wagger200%"
                ]
                if "Del usuario" in df_nuevo.columns:
                    df_nuevo["Del usuario"] = df_nuevo["Del usuario"].astype(str).str.strip()
                    df_nuevo = df_nuevo[df_nuevo["Del usuario"].isin(valores_eros)]
    
                df_nuevo = limpiar_dataframe(df_nuevo)
    
                if "ID" in df_nuevo.columns and "ID" in df_historial.columns:
                    ids_existentes = df_historial["ID"].astype(str).tolist()
                    df_nuevo = df_nuevo[~df_nuevo["ID"].astype(str).isin(ids_existentes)]
    
                if df_nuevo.empty:
                    st.warning("⚠️ Todos los registros pegados ya existían en el historial (mismo ID). No se agregó nada.")
                    st.stop()
    
                df_historial = pd.concat([df_historial, df_nuevo], ignore_index=True)
                df_historial.drop_duplicates(subset=["ID"], inplace=True)
    
                hoja_eros.clear()
                hoja_eros.update([df_historial.columns.tolist()] + df_historial.astype(str).values.tolist())
    
                st.success(f"✅ Registros de Eros actualizados correctamente. Total acumulado: {len(df_historial)}")
    
            except Exception as e:
                st.error(f"❌ Error al procesar los datos pegados: {e}")
    
        if not df_historial.empty:
            st.info(f"📊 Total de registros acumulados: {len(df_historial)}")
            # 🗓️ Filtro por fecha de los registros individuales
            st.markdown("### 📅 Filtrar registros por fecha de actividad")
            col1, col2 = st.columns(2)
            with col1:
                filtro_desde = st.date_input("📆 Desde", value=df_historial["Fecha"].min().date(), key="desde_historial_eros")
            with col2:
                filtro_hasta = st.date_input("📆 Hasta", value=df_historial["Fecha"].max().date(), key="hasta_historial_eros")
        
            df_historial_filtrado = df_historial[
                (df_historial["Fecha"].dt.date >= filtro_desde) &
                (df_historial["Fecha"].dt.date <= filtro_hasta)
            ].copy()
        
            # ⚠️ Este df se usará para calcular el resumen
            df = df_historial_filtrado.copy()
            if "Tiempo" in df.columns and "Hora" not in df.columns:
                df = df.rename(columns={"Tiempo": "Hora"})
        
            def hash_dataframe(df):
                return hashlib.md5(pd.util.hash_pandas_object(df, index=True).values).hexdigest()
        
            df_hash = hash_dataframe(df)
            actualizar = st.button("🔄 Recalcular resumen de jugadores")
        
            resumen_path = "resumen_eros_cache.pkl"
            hash_path = "resumen_eros_hash.txt"
        
            resumen = []
            resumen_actualizado = False
        
            if os.path.exists(resumen_path) and os.path.exists(hash_path):
                with open(hash_path, "r") as f:
                    hash_guardado = f.read().strip()
                if hash_guardado == df_hash and not actualizar:
                    with open(resumen_path, "rb") as f:
                        resumen = pickle.load(f)
                    st.info("⚡️ Resumen cargado desde caché local.")
                else:
                    resumen_actualizado = True
            else:
                resumen_actualizado = True
        
            if resumen_actualizado:
                from collections import Counter
                valores_hl = ["hl_Erosonline"]
                valores_wagger = [
                    "Eros_wagger30%", "Eros_wagger40%", "Eros_wagger50%",
                    "Eros_wagger100%", "Eros_wagger150%", "Eros_wagger200%"
                ]
                jugadores = df["Jugador"].dropna().unique()
        
                for jugador in jugadores:
                    historial = df[df["Jugador"] == jugador].sort_values("Fecha")
                    cargas = historial[historial["Tipo"].str.lower() == "in"]
                    retiros = procesar_retiros_validos(historial, ["DemonGOD", "DaniGOD", "NahueGOD", "CajeroJuancho", "JuanpiCajero", "FlorGOD", "SebaGOD"])
        
                    cargas_hl = cargas[cargas["Del usuario"].isin(valores_hl)]
                    cargas_wagger = cargas[cargas["Del usuario"].isin(valores_wagger)]
        
                    hl = cargas_hl["Monto"].sum()
                    wagger = cargas_wagger["Monto"].sum()
                    total_monto = hl + wagger
                    total_retiro = retiros["Retiro"].sum()
                    ganancias_casino = total_monto - total_retiro
        
                    rango = "Sin datos"
                    if not cargas.empty and "Hora" in cargas.columns:
                        try:
                            cargas["Hora"] = pd.to_datetime(cargas["Hora"], format="%H:%M:%S", errors="coerce")
                            cargas["Día"] = cargas["Fecha"].dt.date
                            cargas["Hora_hora"] = cargas["Hora"].dt.hour
                            hora_por_dia = cargas.groupby("Día")["Hora_hora"].agg(lambda x: int(x.median()))
                            conteo = Counter(hora_por_dia)
                            if conteo:
                                hora_patron, repeticiones = conteo.most_common(1)[0]
                                if repeticiones >= 2:
                                    if 6 <= hora_patron < 12:
                                        franja = "Mañana"
                                    elif 12 <= hora_patron < 18:
                                        franja = "Tarde"
                                    elif 18 <= hora_patron < 24:
                                        franja = "Noche"
                                    else:
                                        franja = "Madrugada"
                                    rango = f"{franja} ({hora_patron:02d}:00 hs) – patrón en {repeticiones} días"
                                else:
                                    rango = "Actividad dispersa"
                        except:
                            rango = "Sin datos"
        
                    if not cargas.empty:
                        ultima_fecha = cargas["Fecha"].max()
                        resumen.append({
                            "Nombre de jugador": jugador,
                            "Tipo de bono": "",
                            "Fecha que ingresó": cargas["Fecha"].min(),
                            "Veces que cargó": len(cargas),
                            "Hl": hl,
                            "Wagger": wagger,
                            "Monto total": total_monto,
                            "Cantidad de retiro": total_retiro,
                            "Ganacias casino": ganancias_casino,
                            "Rango horario de juego": rango,
                            "Última vez que cargó": ultima_fecha,
                            "Días inactivo": (pd.to_datetime(datetime.date.today()) - ultima_fecha).days,
                            "Racha Activa (Días)": (ultima_fecha - cargas["Fecha"].min()).days,
                            "Última vez que se lo contacto": ""
                        })
        
                with open(resumen_path, "wb") as f:
                    pickle.dump(resumen, f)
                with open(hash_path, "w") as f:
                    f.write(df_hash)
                st.success("✅ Resumen recalculado y cacheado.")
        
            df_registro = pd.DataFrame(resumen).sort_values("Última vez que cargó", ascending=False)


            try:
                hoja_princi = sh.worksheet("princi_eros")
                data_princi = hoja_princi.get_all_values()
                df_princi = pd.DataFrame(data_princi[1:], columns=data_princi[0])
            
                # Normalizar nombres: remover espacios, convertir a minúscula
                def normalizar(nombre):
                    return str(nombre).strip().lower().replace(" ", "").replace("_", "")
            
                # Crear un diccionario: nombre_normalizado ➝ princi
                mapping_princi = {}
                for col in df_princi.columns:
                    for nombre in df_princi[col]:
                        if nombre.strip():
                            nombre_norm = normalizar(nombre)
                            mapping_princi[nombre_norm] = col.strip().upper()
            
                # Asignar el princi al dataframe df_registro
                df_registro["Jugador_NORM"] = df_registro["Nombre de jugador"].apply(normalizar)
                df_registro["PRINCI"] = df_registro["Jugador_NORM"].map(mapping_princi).fillna("N/A")
                df_registro = df_registro.drop(columns=["Jugador_NORM"])
            
            except Exception as e:
                st.warning(f"⚠️ No se pudo asignar los PRINCI a los jugadores: {e}")


            try:
                # 🧩 COMPLETAR TIPO DE BONO desde hoja 'registro_bono_eros'
                hoja_users = sh.worksheet("registro_bono_eros")
                raw_data_users = hoja_users.get_all_values()
                headers_users = raw_data_users[0]
                rows_users = raw_data_users[1:]
                df_users = pd.DataFrame(rows_users, columns=headers_users)
            
                # Normalizar nombres de usuario
                def normalizar_usuario(nombre):
                    return str(nombre).strip().lower().replace(" ", "").replace("_", "")
            
                df_users["USUARIO_NORM"] = df_users["USUARIO"].apply(normalizar_usuario)
            
                # ✅ Eliminar duplicados conservando la última aparición del usuario
                df_users = df_users.drop_duplicates(subset=["USUARIO_NORM"], keep="last")
            
                # Normalizar también en el DataFrame de registro
                df_registro["JUGADOR_NORM"] = df_registro["Nombre de jugador"].apply(normalizar_usuario)
            
                # Merge para obtener el tipo de bono (FUNNEL)
                df_registro = df_registro.merge(
                    df_users[["USUARIO_NORM", "FUNNEL"]],
                    left_on="JUGADOR_NORM",
                    right_on="USUARIO_NORM",
                    how="left"
                ).drop(columns=["USUARIO_NORM", "JUGADOR_NORM"])
            
                # Asignar tipo de bono
                df_registro["Tipo de bono"] = df_registro["FUNNEL"].fillna("N/A")
                df_registro = df_registro.drop(columns=["FUNNEL"])
                cols = df_registro.columns.tolist()
                if "Tipo de bono" in cols and "PRINCI" in cols:
                    cols.remove("PRINCI")
                    idx = cols.index("Tipo de bono") + 1
                    cols.insert(idx, "PRINCI")
                    df_registro = df_registro[cols]
            
            except Exception as e:
                st.warning(f"⚠️ No se pudo cargar el tipo de bono desde registro_bono_eros: {e}")

            # Mostrar en app
            st.subheader("📄 Registro completo de jugadores")

            col_filtro, col_orden = st.columns(2)
            
            # ✅ Filtro múltiple por tipo de bono
            tipos_disponibles = df_registro["Tipo de bono"].dropna().unique().tolist()
            tipos_disponibles.sort()
            seleccion_tipos = col_filtro.multiselect(
                "🎯 Filtrar por tipo de bono:",
                options=tipos_disponibles,
                default=["N/A"]  # Podés dejarlo vacío si querés que no filtre por defecto
            )
            
            # ✅ Selector de orden
            criterio_orden = col_orden.selectbox("📊 Ordenar por:", ["Sin ordenar", "Veces que cargó", "Monto total", "Racha Activa (Días)"])
            
            # ✅ Aplicar filtros
            if seleccion_tipos:
                df_registro = df_registro[df_registro["Tipo de bono"].isin(seleccion_tipos)]
            
            if criterio_orden != "Sin ordenar":
                columna_orden = {
                    "Veces que cargó": "Veces que cargó",
                    "Monto total": "Monto total",
                    "Racha Activa (Días)": "Racha Activa (Días)"
                }[criterio_orden]
                df_registro = df_registro.sort_values(by=columna_orden, ascending=False)

            st.dataframe(df_registro)

            # Exportar a Excel
            df_registro.to_excel("registro_jugadores.xlsx", index=False)
            with open("registro_jugadores.xlsx", "rb") as f:
                st.download_button("📅 Descargar Excel", f, file_name="registro_jugadores.xlsx")


        # 🔵 Tabla Bono Eros desde hojas "registro_users" y "bonos_ofrecidos"
        try:
            # Leer hoja principal ignorando posibles conflictos de encabezado
            hoja_registro = sh.worksheet("registro_bono_eros")
            raw_data = hoja_registro.get_all_values()
            headers = raw_data[0]
        
            # Manejar encabezados duplicados
            seen = set()
            unique_headers = []
            for header in headers:
                if header in seen:
                    counter = 1
                    while f"{header}_{counter}" in seen:
                        counter += 1
                    header = f"{header}_{counter}"
                seen.add(header)
                unique_headers.append(header)
        
            rows = raw_data[1:]
            df_registro_users = pd.DataFrame(rows, columns=unique_headers)
        
            # Normalizar y eliminar duplicados (🟡 NUEVO)
            df_registro_users["USUARIO"] = df_registro_users["USUARIO"].astype(str).str.strip().str.lower()
            df_registro_users["USUARIO_NORM"] = df_registro_users["USUARIO"].apply(lambda x: x.replace(" ", "").replace("_", ""))
            df_registro_users = df_registro_users.drop_duplicates(subset=["USUARIO_NORM"], keep="last")
            df_registro_users = df_registro_users.drop(columns=["USUARIO_NORM"])
        
            # Leer hoja con categorías de bonos
            hoja_bonos = sh.worksheet("bonos_ofrecidos_eros")
            raw_data_bonos = hoja_bonos.get_all_values()
            headers_bonos = raw_data_bonos[0]
        
            # Manejar encabezados duplicados en bonos
            seen_bonos = set()
            unique_headers_bonos = []
            for header in headers_bonos:
                if header in seen_bonos:
                    counter = 1
                    while f"{header}_{counter}" in seen_bonos:
                        counter += 1
                    header = f"{header}_{counter}"
                seen_bonos.add(header)
                unique_headers_bonos.append(header)
        
            rows_bonos = raw_data_bonos[1:]
            df_bonos = pd.DataFrame(rows_bonos, columns=unique_headers_bonos)
        
            # Limpiar nombre de usuario
            df_bonos["USUARIO"] = df_bonos["USUARIO"].astype(str).str.strip().str.lower()
        
            # Obtener la última categoría de bono por usuario
            df_categorias = df_bonos.dropna(subset=["CATEGORIA DE BONO"]).sort_values("FECHA")
            df_categorias = df_categorias.groupby("USUARIO")["CATEGORIA DE BONO"].last().reset_index()
        
            # Unir con el registro principal
            df_bono = df_registro_users.merge(df_categorias, on="USUARIO", how="left")
        
            # Renombrar columnas al formato final
            df_bono = df_bono.rename(columns={
                "USUARIO": "Usuario",
                "FUNNEL": "Tipo de Bono",
                "BONOS OFRECIDOS": "Cuántas veces se le ofreció el bono",
                "BONOS USADOS": "Cuántas veces cargó con bono",
                "MONTO TOTAL CARGADO": "Monto total",
                "% DE CONVERSION": "Conversión",
                "ULT. ACTUALIZACION": "Fecha del último mensaje",
                "CATEGORIA DE BONO": "Categoría de Bono"
            })
        
            # Limpiar campos
            df_bono["Conversión"] = df_bono["Conversión"].astype(str).str.replace("%", "", regex=False)
            df_bono["Conversión"] = pd.to_numeric(df_bono["Conversión"], errors="coerce").fillna(0)
            df_bono["Fecha del último mensaje"] = df_bono["Fecha del último mensaje"].replace(
                ["30/12/1899", "1899-12-30"], "Sin registros"
            )
        
            # Seleccionar columnas finales
            columnas_finales = [
                "Usuario", "Tipo de Bono",
                "Cuántas veces se le ofreció el bono", "Cuántas veces cargó con bono",
                "Monto total", "Conversión",
                "Fecha del último mensaje", "Categoría de Bono"
            ]
            df_bono = df_bono[columnas_finales]
        
            # Mostrar en la app
            st.subheader("🎁 Tabla Bono - Eros")
            st.dataframe(df_bono)
        
        except Exception as e:
            st.error(f"❌ Error al generar la Tabla Bono Eros: {e}")


    # SECCIÓN BET ARGENTO
    elif "📋 Registro Bet Argento" in seccion:
        st.header("📋 Registro general de jugadores - Bet Argento")
    
        argentina = pytz.timezone("America/Argentina/Buenos_Aires")
        ahora = datetime.datetime.now(argentina)
        fecha_actual = ahora.strftime("%d/%m/%Y - %H:%M hs")
        fecha_actual_date = ahora.date()
        st.info(f"⏰ Última actualización: {fecha_actual}")
    
        responsable = st.text_input("👤 Ingresá tu nombre para registrar quién sube el reporte", value="Anónimo")
    
        texto_pegar = st.text_area("📋 Pegá aquí el reporte copiado (incluí encabezados)", height=300, key="texto_pegar")
        df_historial = pd.DataFrame()
    
        try:
            # Intentar obtener la hoja existente
            try:
                hoja_argento = sh.worksheet("registro_betargento")
                # Obtener todos los valores y manejar encabezados duplicados
                raw_data = hoja_argento.get_all_values()
                if raw_data:
                    headers = raw_data[0]
                    # Manejar encabezados duplicados
                    seen = set()
                    unique_headers = []
                    for header in headers:
                        if header in seen:
                            # Agregar un sufijo numérico al encabezado duplicado
                            counter = 1
                            while f"{header}_{counter}" in seen:
                                counter += 1
                            header = f"{header}_{counter}"
                        seen.add(header)
                        unique_headers.append(header)
                    
                    # Crear DataFrame con encabezados únicos
                    df_historial = pd.DataFrame(raw_data[1:], columns=unique_headers)
                else:
                    df_historial = pd.DataFrame()
            except gspread.exceptions.WorksheetNotFound:
                # Si la hoja no existe, intentar crearla
                try:
                    hoja_argento = sh.add_worksheet(title="registro_betargento", rows="1000", cols="20")
                    df_historial = pd.DataFrame()
                except gspread.exceptions.APIError as e:
                    st.error("❌ Error al crear la hoja de Bet Argento. Por favor, verifica los permisos de la hoja de cálculo.")
                    st.stop()
        except Exception as e:
            st.error(f"❌ Error al acceder a la hoja de cálculo: {str(e)}")
            st.stop()
    
        def convertir_monto(valor):
            if pd.isna(valor): return 0.0
            valor = str(valor)
            # Eliminar caracteres invisibles y separadores ambiguos
            valor = valor.replace("\u202f", "")  # Narrow no-break space
            valor = valor.replace("\xa0", "")    # Non-breaking space
            valor = valor.replace(" ", "")       # Espacios normales
            valor = valor.replace(",", "")       # Comas (separador de miles)
            try:
                return float(valor)
            except:
                return 0.0
    
    
        def limpiar_dataframe(df_temp):
            df_temp = df_temp.copy()
            if "Jugador" in df_temp.columns:
                df_temp["Jugador"] = df_temp["Jugador"].astype(str).str.strip().str.lower()
    
            for col in ["Monto", "Retiro", "Balance antes de operación", "Wager"]:
                if col in df_temp.columns:
                    df_temp[col] = df_temp[col].apply(convertir_monto)
    
            if "Fecha" in df_temp.columns:
                df_temp["Fecha"] = pd.to_datetime(df_temp["Fecha"], errors="coerce")
    
            return df_temp

        def procesar_retiros_validos(df, iniciadores_validos):
            df["FechaHora"] = pd.to_datetime(df["Fecha"].astype(str) + " " + df["Hora"].astype(str), errors="coerce")
        
            df_retiros_validos = df[
                (df["Tipo"].str.lower() == "out") & df["Iniciador"].isin(iniciadores_validos)
            ].copy()
        
            df_cargas = df[df["Tipo"].str.lower() == "in"].copy()
            df_cargas["FechaHora"] = pd.to_datetime(df_cargas["Fecha"].astype(str) + " " + df_cargas["Hora"].astype(str), errors="coerce")
        
            df_retiros_validos["Clave"] = df_retiros_validos["Jugador"] + df_retiros_validos["Retiro"].astype(str)
            df_cargas["Clave"] = df_cargas["Jugador"] + df_cargas["Monto"].astype(str)
        
            claves_cargas = df_cargas.set_index("Clave")["FechaHora"].to_dict()
        
            indices_a_excluir = []
            for i, row in df_retiros_validos.iterrows():
                clave = row["Clave"]
                if clave in claves_cargas:
                    delta = row["FechaHora"] - claves_cargas[clave]
                    if pd.notnull(delta) and delta.total_seconds() <= 300:
                        indices_a_excluir.append(i)
        
            df_retiros_validos = df_retiros_validos.drop(index=indices_a_excluir)
            return df_retiros_validos
    
        df_historial = limpiar_dataframe(df_historial)

    
        if "Fecha" in df_historial.columns:
            df_historial["Fecha"] = pd.to_datetime(df_historial["Fecha"], errors="coerce")
            df_historial = df_historial[df_historial["Fecha"].notna()]
            limite = fecha_actual_date - datetime.timedelta(days=30)
            df_historial = df_historial[df_historial["Fecha"].dt.date >= limite]
    
        if texto_pegar:
            try:
                sep_detectado = "\t" if "\t" in texto_pegar else ";" if ";" in texto_pegar else ","
                lineas = texto_pegar.strip().splitlines()
                encabezados = lineas[0].split(sep_detectado)
                cantidad_columnas = len(encabezados)
    
                contenido_limpio = [sep_detectado.join(encabezados)]
                for fila in lineas[1:]:
                    columnas = fila.split(sep_detectado)
                    if len(columnas) < cantidad_columnas:
                        columnas += [""] * (cantidad_columnas - len(columnas))
                    elif len(columnas) > cantidad_columnas:
                        columnas = columnas[:cantidad_columnas]
                    contenido_limpio.append(sep_detectado.join(columnas))
    
                archivo_limpio = StringIO("\n".join(contenido_limpio))
                df_nuevo = pd.read_csv(archivo_limpio, sep=sep_detectado, dtype=str, encoding="utf-8")
                df_nuevo = df_nuevo.loc[:, ~df_nuevo.columns.str.contains("^Unnamed")]
    
                # 🔁 Limpiar montos ANTES de renombrar
                for col in ["Depositar", "Retirar", "Wager", "Balance antes de operación"]:
                    if col in df_nuevo.columns:
                        df_nuevo[col] = (
                            df_nuevo[col]
                            .astype(str)
                            .str.replace(",", "", regex=False)
                            .str.replace(" ", "", regex=False)
                        )
                        df_nuevo[col] = pd.to_numeric(df_nuevo[col], errors="coerce").fillna(0.0)
    
                columnas_requeridas = ["operación", "Depositar", "Retirar", "Fecha", "Al usuario"]
                if not all(col in df_nuevo.columns for col in columnas_requeridas):
                    st.error("❌ El reporte pegado no contiene los encabezados necesarios o está mal formateado.")
                    st.stop()
    
                df_nuevo = df_nuevo.rename(columns={
                    "operación": "Tipo",
                    "Depositar": "Monto",
                    "Retirar": "Retiro",
                    "Fecha": "Fecha",
                    "Tiempo": "Hora",
                    "Al usuario": "Jugador"
                })
    
                df_nuevo["Responsable"] = responsable
                df_nuevo["Fecha_Subida"] = fecha_actual
    
                valores_argento = [
                    "hl_betargento",
                    "Argento_Wager", "Argento_Wager30", "Argento_Wager40",
                    "Argento_Wager50", "Argento_Wager100", "Argento_Wager150", "Argento_Wager200"
                ]
                if "Del usuario" in df_nuevo.columns:
                    df_nuevo["Del usuario"] = df_nuevo["Del usuario"].astype(str).str.strip()
                    df_nuevo = df_nuevo[df_nuevo["Del usuario"].isin(valores_argento)]
    
                df_nuevo = limpiar_dataframe(df_nuevo)
    
                if "ID" in df_nuevo.columns and "ID" in df_historial.columns:
                    ids_existentes = df_historial["ID"].astype(str).tolist()
                    df_nuevo = df_nuevo[~df_nuevo["ID"].astype(str).isin(ids_existentes)]
    
                if df_nuevo.empty:
                    st.warning("⚠️ Todos los registros pegados ya existían en el historial (mismo ID). No se agregó nada.")
                    st.stop()
    
                df_historial = pd.concat([df_historial, df_nuevo], ignore_index=True)
                df_historial.drop_duplicates(subset=["ID"], inplace=True)
    
                hoja_argento.clear()
                hoja_argento.update([df_historial.columns.tolist()] + df_historial.astype(str).values.tolist())
    
                st.success(f"✅ Registros de Bet Argento actualizados correctamente. Total acumulado: {len(df_historial)}")
    
            except Exception as e:
                st.error(f"❌ Error al procesar los datos pegados: {e}")
    
        if not df_historial.empty:
            st.info(f"📊 Total de registros acumulados: {len(df_historial)}")
            # 🗓️ Filtro por fecha de los registros individuales
            st.markdown("### 📅 Filtrar registros por fecha de actividad")
            col1, col2 = st.columns(2)
            with col1:
                filtro_desde = st.date_input("📆 Desde", value=df_historial["Fecha"].min().date(), key="desde_historial_bet")
            with col2:
                filtro_hasta = st.date_input("📆 Hasta", value=df_historial["Fecha"].max().date(), key="hasta_historial_bet")
        
            df_historial_filtrado = df_historial[
                (df_historial["Fecha"].dt.date >= filtro_desde) &
                (df_historial["Fecha"].dt.date <= filtro_hasta)
            ].copy()
        
            # ⚠️ Este df se usará para calcular el resumen
            df = df_historial_filtrado.copy()
            if "Tiempo" in df.columns and "Hora" not in df.columns:
                df = df.rename(columns={"Tiempo": "Hora"})
        
            def hash_dataframe(df):
                return hashlib.md5(pd.util.hash_pandas_object(df, index=True).values).hexdigest()
        
            df_hash = hash_dataframe(df)
            actualizar = st.button("🔄 Recalcular resumen de jugadores")
        
            resumen_path = "resumen_betargento_cache.pkl"
            hash_path = "resumen_betargento_hash.txt"
        
            resumen = []
            resumen_actualizado = False
        
            if os.path.exists(resumen_path) and os.path.exists(hash_path):
                with open(hash_path, "r") as f:
                    hash_guardado = f.read().strip()
                if hash_guardado == df_hash and not actualizar:
                    with open(resumen_path, "rb") as f:
                        resumen = pickle.load(f)
                    st.info("⚡️ Resumen cargado desde caché local.")
                else:
                    resumen_actualizado = True
            else:
                resumen_actualizado = True
        
            if resumen_actualizado:
                from collections import Counter
                valores_hl = ["hl_betargento"]
                valores_wagger = [
                    "Argento_Wager", "Argento_Wagger30", "Argento_Wagger40",
                    "Argento_Wagger50", "Argento_Wagger100",
                    "Argento_Wagger150", "Argento_Wagger200"
                ]
                jugadores = df["Jugador"].dropna().unique()
        
                for jugador in jugadores:
                    historial = df[df["Jugador"] == jugador].sort_values("Fecha")
                    cargas = historial[historial["Tipo"].str.lower() == "in"]
                    retiros = procesar_retiros_validos(historial, ["subagente01", "subagente03", "sub_agent06", "sub_agent11", "sub_agent012"])
        
                    cargas_hl = cargas[cargas["Del usuario"].isin(valores_hl)]
                    cargas_wagger = cargas[cargas["Del usuario"].isin(valores_wagger)]
        
                    hl = cargas_hl["Monto"].sum()
                    wagger = cargas_wagger["Monto"].sum()
                    total_monto = hl + wagger
                    total_retiro = retiros["Retiro"].sum()
                    ganancias_casino = total_monto - total_retiro
        
                    rango = "Sin datos"
                    if not cargas.empty and "Hora" in cargas.columns:
                        try:
                            cargas["Hora"] = pd.to_datetime(cargas["Hora"], format="%H:%M:%S", errors="coerce")
                            cargas["Día"] = cargas["Fecha"].dt.date
                            cargas["Hora_hora"] = cargas["Hora"].dt.hour
                            hora_por_dia = cargas.groupby("Día")["Hora_hora"].agg(lambda x: int(x.median()))
                            conteo = Counter(hora_por_dia)
                            if conteo:
                                hora_patron, repeticiones = conteo.most_common(1)[0]
                                if repeticiones >= 2:
                                    if 6 <= hora_patron < 12:
                                        franja = "Mañana"
                                    elif 12 <= hora_patron < 18:
                                        franja = "Tarde"
                                    elif 18 <= hora_patron < 24:
                                        franja = "Noche"
                                    else:
                                        franja = "Madrugada"
                                    rango = f"{franja} ({hora_patron:02d}:00 hs) – patrón en {repeticiones} días"
                                else:
                                    rango = "Actividad dispersa"
                        except:
                            rango = "Sin datos"
        
                    if not cargas.empty:
                        ultima_fecha = cargas["Fecha"].max()
                        resumen.append({
                            "Nombre de jugador": jugador,
                            "Tipo de bono": "",
                            "Fecha que ingresó": cargas["Fecha"].min(),
                            "Veces que cargó": len(cargas),
                            "Hl": hl,
                            "Wagger": wagger,
                            "Monto total": total_monto,
                            "Cantidad de retiro": total_retiro,
                            "Ganacias casino": ganancias_casino,
                            "Rango horario de juego": rango,
                            "Última vez que cargó": ultima_fecha,
                            "Días inactivo": (pd.to_datetime(datetime.date.today()) - ultima_fecha).days,
                            "Racha Activa (Días)": (ultima_fecha - cargas["Fecha"].min()).days,
                            "Última vez que se lo contacto": ""
                        })
        
                with open(resumen_path, "wb") as f:
                    pickle.dump(resumen, f)
                with open(hash_path, "w") as f:
                    f.write(df_hash)
                st.success("✅ Resumen recalculado y cacheado.")
        
            df_registro = pd.DataFrame(resumen).sort_values("Última vez que cargó", ascending=False)

            try:
                hoja_princi = sh.worksheet("princi_betargento")
                data_princi = hoja_princi.get_all_values()
                df_princi = pd.DataFrame(data_princi[1:], columns=data_princi[0])
            
                def normalizar(nombre):
                    return str(nombre).strip().lower().replace(" ", "").replace("_", "")
            
                mapping_princi = {}
                for col in df_princi.columns:
                    for nombre in df_princi[col]:
                        if nombre.strip():
                            nombre_norm = normalizar(nombre)
                            mapping_princi[nombre_norm] = col.strip().upper()
            
                df_registro["Jugador_NORM"] = df_registro["Nombre de jugador"].apply(normalizar)
                df_registro["PRINCI"] = df_registro["Jugador_NORM"].map(mapping_princi).fillna("N/A")
                df_registro = df_registro.drop(columns=["Jugador_NORM"])
            
            except Exception as e:
                st.warning(f"⚠️ No se pudo asignar los PRINCI a los jugadores de Bet Argento: {e}")


            try:
                hoja_users = sh.worksheet("registro_bono_bet")
                raw_data_users = hoja_users.get_all_values()
                headers_users = raw_data_users[0]
                rows_users = raw_data_users[1:]
                df_users = pd.DataFrame(rows_users, columns=headers_users)

                def normalizar_usuario(nombre):
                    return str(nombre).strip().lower().replace(" ", "").replace("_", "")

                df_users["USUARIO_NORM"] = df_users["USUARIO"].apply(normalizar_usuario)
                df_users = df_users.drop_duplicates(subset=["USUARIO_NORM"], keep="last")

                df_registro["JUGADOR_NORM"] = df_registro["Nombre de jugador"].apply(normalizar_usuario)

                df_registro = df_registro.merge(
                    df_users[["USUARIO_NORM", "FUNNEL"]],
                    left_on="JUGADOR_NORM",
                    right_on="USUARIO_NORM",
                    how="left"
                ).drop(columns=["USUARIO_NORM", "JUGADOR_NORM"])

                df_registro["Tipo de bono"] = df_registro["FUNNEL"].fillna("N/A")
                df_registro = df_registro.drop(columns=["FUNNEL"])
                cols = df_registro.columns.tolist()
                if "Tipo de bono" in cols and "PRINCI" in cols:
                    cols.remove("PRINCI")
                    idx = cols.index("Tipo de bono") + 1
                    cols.insert(idx, "PRINCI")
                    df_registro = df_registro[cols]

            except Exception as e:
                st.warning(f"⚠️ No se pudo cargar el tipo de bono desde registro_bono_bet: {e}")

            st.subheader("📄 Registro completo de jugadores")

            col_filtro, col_orden = st.columns(2)
            
            # ✅ Filtro múltiple por tipo de bono
            tipos_disponibles = df_registro["Tipo de bono"].dropna().unique().tolist()
            tipos_disponibles.sort()
            seleccion_tipos = col_filtro.multiselect(
                "🎯 Filtrar por tipo de bono:",
                options=tipos_disponibles,
                default=["N/A"]  # Podés dejarlo vacío si querés que no filtre por defecto
            )
            
            # ✅ Selector de orden
            criterio_orden = col_orden.selectbox("📊 Ordenar por:", ["Sin ordenar", "Veces que cargó", "Monto total", "Racha Activa (Días)"])
            
            # ✅ Aplicar filtros
            if seleccion_tipos:
                df_registro = df_registro[df_registro["Tipo de bono"].isin(seleccion_tipos)]
            
            if criterio_orden != "Sin ordenar":
                columna_orden = {
                    "Veces que cargó": "Veces que cargó",
                    "Monto total": "Monto total",
                    "Racha Activa (Días)": "Racha Activa (Días)"
                }[criterio_orden]
                df_registro = df_registro.sort_values(by=columna_orden, ascending=False)
            st.dataframe(df_registro)

            df_registro.to_excel("registro_jugadores_betargento.xlsx", index=False)
            with open("registro_jugadores_betargento.xlsx", "rb") as f:
                st.download_button("📅 Descargar Excel", f, file_name="registro_jugadores_betargento.xlsx")


            try:
                hoja_registro = sh.worksheet("registro_bono_bet")
                raw_data = hoja_registro.get_all_values()
                headers = raw_data[0]

                seen = set()
                unique_headers = []
                for header in headers:
                    if header in seen:
                        counter = 1
                        while f"{header}_{counter}" in seen:
                            counter += 1
                        header = f"{header}_{counter}"
                    seen.add(header)
                    unique_headers.append(header)

                rows = raw_data[1:]
                df_registro_users = pd.DataFrame(rows, columns=unique_headers)

                df_registro_users["USUARIO"] = df_registro_users["USUARIO"].astype(str).str.strip().str.lower()
                df_registro_users["USUARIO_NORM"] = df_registro_users["USUARIO"].apply(lambda x: x.replace(" ", "").replace("_", ""))
                df_registro_users = df_registro_users.drop_duplicates(subset=["USUARIO_NORM"], keep="last")
                df_registro_users = df_registro_users.drop(columns=["USUARIO_NORM"])

                hoja_bonos = sh.worksheet("bonos_ofrecidos_bet")
                raw_data_bonos = hoja_bonos.get_all_values()
                headers_bonos = raw_data_bonos[0]

                seen_bonos = set()
                unique_headers_bonos = []
                for header in headers_bonos:
                    if header in seen_bonos:
                        counter = 1
                        while f"{header}_{counter}" in seen_bonos:
                            counter += 1
                        header = f"{header}_{counter}"
                    seen_bonos.add(header)
                    unique_headers_bonos.append(header)

                rows_bonos = raw_data_bonos[1:]
                df_bonos = pd.DataFrame(rows_bonos, columns=unique_headers_bonos)

                df_bonos["USUARIO"] = df_bonos["USUARIO"].astype(str).str.strip().str.lower()

                df_categorias = df_bonos.dropna(subset=["CATEGORIA DE BONO"]).sort_values("FECHA")
                df_categorias = df_categorias.groupby("USUARIO")["CATEGORIA DE BONO"].last().reset_index()

                df_bono = df_registro_users.merge(df_categorias, on="USUARIO", how="left")

                df_bono = df_bono.rename(columns={
                    "USUARIO": "Usuario",
                    "FUNNEL": "Tipo de Bono",
                    "BONOS OFRECIDOS": "Cuántas veces se le ofreció el bono",
                    "BONOS USADOS": "Cuántas veces cargó con bono",
                    "MONTO TOTAL CARGADO": "Monto total",
                    "% DE CONVERSION": "Conversión",
                    "ULT. ACTUALIZACION": "Fecha del último mensaje",
                    "CATEGORIA DE BONO": "Categoría de Bono"
                })

                df_bono["Conversión"] = df_bono["Conversión"].astype(str).str.replace("%", "", regex=False)
                df_bono["Conversión"] = pd.to_numeric(df_bono["Conversión"], errors="coerce").fillna(0)
                df_bono["Fecha del último mensaje"] = df_bono["Fecha del último mensaje"].replace(["30/12/1899", "1899-12-30"], "Sin registros")

                columnas_finales = [
                    "Usuario", "Tipo de Bono",
                    "Cuántas veces se le ofreció el bono", "Cuántas veces cargó con bono",
                    "Monto total", "Conversión",
                    "Fecha del último mensaje", "Categoría de Bono"
                ]
                df_bono = df_bono[columnas_finales]

                st.subheader("🎁 Tabla Bono - Bet Argento")
                st.dataframe(df_bono)

            except Exception as e:
                st.error(f"❌ Error al generar la Tabla Bono Bet Argento: {e}")

    #SECCIÓN SPIRITA
    elif "📋 Registro Spirita" in seccion:
        st.header("📋 Registro general de jugadores - Spirita")
    
        argentina = pytz.timezone("America/Argentina/Buenos_Aires")
        ahora = datetime.datetime.now(argentina)
        fecha_actual = ahora.strftime("%d/%m/%Y - %H:%M hs")
        fecha_actual_date = ahora.date()
        st.info(f"⏰ Última actualización: {fecha_actual}")
    
        responsable = st.text_input("👤 Ingresá tu nombre para registrar quién sube el reporte", value="Anónimo")
    
        texto_pegar = st.text_area("📋 Pegá aquí el reporte copiado (incluí encabezados)", height=300, key="texto_pegar")
        df_historial = pd.DataFrame()
    
        try:
            hoja_spirita = sh.worksheet("registro_spirita")
            data_spirita = hoja_spirita.get_all_records()
            df_historial = pd.DataFrame(data_spirita)
        except:
            hoja_spirita = sh.add_worksheet(title="registro_spirita", rows="1000", cols="20")
            df_historial = pd.DataFrame()
    
        def convertir_monto(valor):
            if pd.isna(valor): return 0.0
            valor = str(valor)
            # Eliminar caracteres invisibles y separadores ambiguos
            valor = valor.replace("\u202f", "")  # Narrow no-break space
            valor = valor.replace("\xa0", "")    # Non-breaking space
            valor = valor.replace(" ", "")       # Espacios normales
            valor = valor.replace(",", "")       # Comas (separador de miles)
            try:
                return float(valor)
            except:
                return 0.0
    
    
        def limpiar_dataframe(df_temp):
            df_temp = df_temp.copy()
            if "Jugador" in df_temp.columns:
                df_temp["Jugador"] = df_temp["Jugador"].astype(str).str.strip().str.lower()
    
            for col in ["Monto", "Retiro", "Balance antes de operación", "Wager"]:
                if col in df_temp.columns:
                    df_temp[col] = df_temp[col].apply(convertir_monto)
    
            if "Fecha" in df_temp.columns:
                df_temp["Fecha"] = pd.to_datetime(df_temp["Fecha"], errors="coerce")
    
            return df_temp
    
        df_historial = limpiar_dataframe(df_historial)
    
        if "Fecha" in df_historial.columns:
            df_historial["Fecha"] = pd.to_datetime(df_historial["Fecha"], errors="coerce")
            df_historial = df_historial[df_historial["Fecha"].notna()]
            limite = fecha_actual_date - datetime.timedelta(days=30)
            df_historial = df_historial[df_historial["Fecha"].dt.date >= limite]

        if texto_pegar:
            try:
                sep_detectado = "\t" if "\t" in texto_pegar else ";" if ";" in texto_pegar else ","
                lineas = texto_pegar.strip().splitlines()
                encabezados = lineas[0].split(sep_detectado)
                cantidad_columnas = len(encabezados)
    
                contenido_limpio = [sep_detectado.join(encabezados)]
                for fila in lineas[1:]:
                    columnas = fila.split(sep_detectado)
                    if len(columnas) < cantidad_columnas:
                        columnas += [""] * (cantidad_columnas - len(columnas))
                    elif len(columnas) > cantidad_columnas:
                        columnas = columnas[:cantidad_columnas]
                    contenido_limpio.append(sep_detectado.join(columnas))
    
                archivo_limpio = StringIO("\n".join(contenido_limpio))
                df_nuevo = pd.read_csv(archivo_limpio, sep=sep_detectado, dtype=str, encoding="utf-8")
                df_nuevo = df_nuevo.loc[:, ~df_nuevo.columns.str.contains("^Unnamed")]
    
                # 🔁 Limpiar montos ANTES de renombrar
                for col in ["Depositar", "Retirar", "Wager", "Balance antes de operación"]:
                    if col in df_nuevo.columns:
                        df_nuevo[col] = (
                            df_nuevo[col]
                            .astype(str)
                            .str.replace(",", "", regex=False)
                            .str.replace(" ", "", regex=False)
                        )
                        df_nuevo[col] = pd.to_numeric(df_nuevo[col], errors="coerce").fillna(0.0)
    
                columnas_requeridas = ["operación", "Depositar", "Retirar", "Fecha", "Al usuario"]
                if not all(col in df_nuevo.columns for col in columnas_requeridas):
                    st.error("❌ El reporte pegado no contiene los encabezados necesarios o está mal formateado.")
                    st.stop()
    
                df_nuevo = df_nuevo.rename(columns={
                    "operación": "Tipo",
                    "Depositar": "Monto",
                    "Retirar": "Retiro",
                    "Fecha": "Fecha",
                    "Tiempo": "Hora",
                    "Al usuario": "Jugador"
                })
    
                df_nuevo["Responsable"] = responsable
                df_nuevo["Fecha_Subida"] = fecha_actual
    
                valores_spirita = [
                    "hall_atenea"
                ]
                if "Del usuario" in df_nuevo.columns:
                    df_nuevo["Del usuario"] = df_nuevo["Del usuario"].astype(str).str.strip()
                    df_nuevo = df_nuevo[df_nuevo["Del usuario"].isin(valores_spirita)]
    
                df_nuevo = limpiar_dataframe(df_nuevo)
    
                if "ID" in df_nuevo.columns and "ID" in df_historial.columns:
                    ids_existentes = df_historial["ID"].astype(str).tolist()
                    df_nuevo = df_nuevo[~df_nuevo["ID"].astype(str).isin(ids_existentes)]
    
                if df_nuevo.empty:
                    st.warning("⚠️ Todos los registros pegados ya existían en el historial (mismo ID). No se agregó nada.")
                    st.stop()
    
                df_historial = pd.concat([df_historial, df_nuevo], ignore_index=True)
                df_historial.drop_duplicates(subset=["ID"], inplace=True)
    
                hoja_spirita.clear()
                hoja_spirita.update([df_historial.columns.tolist()] + df_historial.astype(str).values.tolist())
    
                st.success(f"✅ Registros de spirita actualizados correctamente. Total acumulado: {len(df_historial)}")
    
            except Exception as e:
                st.error(f"❌ Error al procesar los datos pegados: {e}")
    
        if not df_historial.empty:
            st.info(f"📊 Total de registros acumulados: {len(df_historial)}")
            # 🗓️ Filtro por fecha de los registros individuales
            st.markdown("### 📅 Filtrar registros por fecha de actividad")
            col1, col2 = st.columns(2)
            with col1:
                filtro_desde = st.date_input("📆 Desde", value=df_historial["Fecha"].min().date(), key="desde_historial_spirita")
            with col2:
                filtro_hasta = st.date_input("📆 Hasta", value=df_historial["Fecha"].max().date(), key="hasta_historial_spirita")
        
            df_historial_filtrado = df_historial[
                (df_historial["Fecha"].dt.date >= filtro_desde) &
                (df_historial["Fecha"].dt.date <= filtro_hasta)
            ].copy()
        
            # ⚠️ Este df se usará para calcular el resumen
            df = df_historial_filtrado.copy()
            if "Tiempo" in df.columns and "Hora" not in df.columns:
                df = df.rename(columns={"Tiempo": "Hora"})
        
            def hash_dataframe(df):
                return hashlib.md5(pd.util.hash_pandas_object(df, index=True).values).hexdigest()
        
            df_hash = hash_dataframe(df)
            actualizar = st.button("🔄 Recalcular resumen de jugadores")
        
            resumen_path = "resumen_spirita_cache.pkl"
            hash_path = "resumen_spirita_hash.txt"
        
            resumen = []
            resumen_actualizado = False
        
            if os.path.exists(resumen_path) and os.path.exists(hash_path):
                with open(hash_path, "r") as f:
                    hash_guardado = f.read().strip()
                if hash_guardado == df_hash and not actualizar:
                    with open(resumen_path, "rb") as f:
                        resumen = pickle.load(f)
                    st.info("⚡️ Resumen cargado desde caché local.")
                else:
                    resumen_actualizado = True
            else:
                resumen_actualizado = True
        
            if resumen_actualizado:
                from collections import Counter
                valores_hl = ["hall_atenea"]
                valores_wagger = [
                    "spirita_wagger30%", "spirita_wagger40%", "spirita_wagger50%",
                    "spirita_wagger100%", "spirita_wagger150%", "spirita_wagger200%"
                ]
                jugadores = df["Jugador"].dropna().unique()
        
                for jugador in jugadores:
                    historial = df[df["Jugador"] == jugador].sort_values("Fecha")
                    cargas = historial[historial["Tipo"].str.lower() == "in"]
                    retiros = historial[historial["Tipo"].str.lower() == "out"]
        
                    cargas_hl = cargas[cargas["Del usuario"].isin(valores_hl)]
                    cargas_wagger = cargas[cargas["Del usuario"].isin(valores_wagger)]
        
                    hl = cargas_hl["Monto"].sum()
                    wagger = cargas_wagger["Monto"].sum()
                    total_monto = hl + wagger
                    total_retiro = retiros["Retiro"].sum()
                    ganancias_casino = total_monto - total_retiro
        
                    rango = "Sin datos"
                    if not cargas.empty and "Hora" in cargas.columns:
                        try:
                            cargas["Hora"] = pd.to_datetime(cargas["Hora"], format="%H:%M:%S", errors="coerce")
                            cargas["Día"] = cargas["Fecha"].dt.date
                            cargas["Hora_hora"] = cargas["Hora"].dt.hour
                            hora_por_dia = cargas.groupby("Día")["Hora_hora"].agg(lambda x: int(x.median()))
                            conteo = Counter(hora_por_dia)
                            if conteo:
                                hora_patron, repeticiones = conteo.most_common(1)[0]
                                if repeticiones >= 2:
                                    if 6 <= hora_patron < 12:
                                        franja = "Mañana"
                                    elif 12 <= hora_patron < 18:
                                        franja = "Tarde"
                                    elif 18 <= hora_patron < 24:
                                        franja = "Noche"
                                    else:
                                        franja = "Madrugada"
                                    rango = f"{franja} ({hora_patron:02d}:00 hs) – patrón en {repeticiones} días"
                                else:
                                    rango = "Actividad dispersa"
                        except:
                            rango = "Sin datos"
        
                    if not cargas.empty:
                        ultima_fecha = cargas["Fecha"].max()
                        resumen.append({
                            "Nombre de jugador": jugador,
                            "Tipo de bono": "",
                            "Fecha que ingresó": cargas["Fecha"].min(),
                            "Veces que cargó": len(cargas),
                            "Hl": hl,
                            "Wagger": wagger,
                            "Monto total": total_monto,
                            "Cantidad de retiro": total_retiro,
                            "Ganacias casino": ganancias_casino,
                            "Rango horario de juego": rango,
                            "Última vez que cargó": ultima_fecha,
                            "Días inactivo": (pd.to_datetime(datetime.date.today()) - ultima_fecha).days,
                            "Racha Activa (Días)": (ultima_fecha - cargas["Fecha"].min()).days,
                            "Última vez que se lo contacto": ""
                        })
        
                with open(resumen_path, "wb") as f:
                    pickle.dump(resumen, f)
                with open(hash_path, "w") as f:
                    f.write(df_hash)
                st.success("✅ Resumen recalculado y cacheado.")
        
            df_registro = pd.DataFrame(resumen).sort_values("Última vez que cargó", ascending=False)


            try:
                hoja_princi = sh.worksheet("princi_spirita")
                data_princi = hoja_princi.get_all_values()
                df_princi = pd.DataFrame(data_princi[1:], columns=data_princi[0])
            
                # Normalizar nombres: remover espacios, convertir a minúscula
                def normalizar(nombre):
                    return str(nombre).strip().lower().replace(" ", "").replace("_", "")
            
                # Crear un diccionario: nombre_normalizado ➝ princi
                mapping_princi = {}
                for col in df_princi.columns:
                    for nombre in df_princi[col]:
                        if nombre.strip():
                            nombre_norm = normalizar(nombre)
                            mapping_princi[nombre_norm] = col.strip().upper()
            
                # Asignar el princi al dataframe df_registro
                df_registro["Jugador_NORM"] = df_registro["Nombre de jugador"].apply(normalizar)
                df_registro["PRINCI"] = df_registro["Jugador_NORM"].map(mapping_princi).fillna("N/A")
                df_registro = df_registro.drop(columns=["Jugador_NORM"])
            
            except Exception as e:
                st.warning(f"⚠️ No se pudo asignar los PRINCI a los jugadores: {e}")


            try:
                # 🧩 COMPLETAR TIPO DE BONO desde hoja 'registro_bono_spirita'
                hoja_users = sh.worksheet("registro_bono_spirita")
                raw_data_users = hoja_users.get_all_values()
                headers_users = raw_data_users[0]
                rows_users = raw_data_users[1:]
                df_users = pd.DataFrame(rows_users, columns=headers_users)
            
                # Normalizar nombres de usuario
                def normalizar_usuario(nombre):
                    return str(nombre).strip().lower().replace(" ", "").replace("_", "")
            
                df_users["USUARIO_NORM"] = df_users["USUARIO"].apply(normalizar_usuario)
            
                # ✅ Eliminar duplicados conservando la última aparición del usuario
                df_users = df_users.drop_duplicates(subset=["USUARIO_NORM"], keep="last")
            
                # Normalizar también en el DataFrame de registro
                df_registro["JUGADOR_NORM"] = df_registro["Nombre de jugador"].apply(normalizar_usuario)
            
                # Merge para obtener el tipo de bono (FUNNEL)
                df_registro = df_registro.merge(
                    df_users[["USUARIO_NORM", "FUNNEL"]],
                    left_on="JUGADOR_NORM",
                    right_on="USUARIO_NORM",
                    how="left"
                ).drop(columns=["USUARIO_NORM", "JUGADOR_NORM"])
            
                # Asignar tipo de bono
                df_registro["Tipo de bono"] = df_registro["FUNNEL"].fillna("N/A")
                df_registro = df_registro.drop(columns=["FUNNEL"])
                cols = df_registro.columns.tolist()
                if "Tipo de bono" in cols and "PRINCI" in cols:
                    cols.remove("PRINCI")
                    idx = cols.index("Tipo de bono") + 1
                    cols.insert(idx, "PRINCI")
                    df_registro = df_registro[cols]
            
            except Exception as e:
                st.warning(f"⚠️ No se pudo cargar el tipo de bono desde registro_bono_spirita: {e}")

            # Mostrar en app
            st.subheader("📄 Registro completo de jugadores")

            col_filtro, col_orden = st.columns(2)
            
            # ✅ Filtro múltiple por tipo de bono
            tipos_disponibles = df_registro["Tipo de bono"].dropna().unique().tolist()
            tipos_disponibles.sort()
            seleccion_tipos = col_filtro.multiselect(
                "🎯 Filtrar por tipo de bono:",
                options=tipos_disponibles,
                default=["N/A"]  # Podés dejarlo vacío si querés que no filtre por defecto
            )
            
            # ✅ Selector de orden
            criterio_orden = col_orden.selectbox("📊 Ordenar por:", ["Sin ordenar", "Veces que cargó", "Monto total", "Racha Activa (Días)"])
            
            # ✅ Aplicar filtros
            if seleccion_tipos:
                df_registro = df_registro[df_registro["Tipo de bono"].isin(seleccion_tipos)]
            
            if criterio_orden != "Sin ordenar":
                columna_orden = {
                    "Veces que cargó": "Veces que cargó",
                    "Monto total": "Monto total",
                    "Racha Activa (Días)": "Racha Activa (Días)"
                }[criterio_orden]
                df_registro = df_registro.sort_values(by=columna_orden, ascending=False)

            st.dataframe(df_registro)

            # Exportar a Excel
            df_registro.to_excel("registro_jugadores.xlsx", index=False)
            with open("registro_jugadores.xlsx", "rb") as f:
                st.download_button("📅 Descargar Excel", f, file_name="registro_jugadores.xlsx")


        # 🔵 Tabla Bono Spirita desde hojas "registro_users" y "bonos_ofrecidos"
        try:
            # Leer hoja principal ignorando posibles conflictos de encabezado
            hoja_registro = sh.worksheet("registro_bono_spirita")
            raw_data = hoja_registro.get_all_values()
            headers = raw_data[0]
        
            # Manejar encabezados duplicados
            seen = set()
            unique_headers = []
            for header in headers:
                if header in seen:
                    counter = 1
                    while f"{header}_{counter}" in seen:
                        counter += 1
                    header = f"{header}_{counter}"
                seen.add(header)
                unique_headers.append(header)
        
            rows = raw_data[1:]
            df_registro_users = pd.DataFrame(rows, columns=unique_headers)
        
            # Normalizar y eliminar duplicados (🟡 NUEVO)
            df_registro_users["USUARIO"] = df_registro_users["USUARIO"].astype(str).str.strip().str.lower()
            df_registro_users["USUARIO_NORM"] = df_registro_users["USUARIO"].apply(lambda x: x.replace(" ", "").replace("_", ""))
            df_registro_users = df_registro_users.drop_duplicates(subset=["USUARIO_NORM"], keep="last")
            df_registro_users = df_registro_users.drop(columns=["USUARIO_NORM"])
        
            # Leer hoja con categorías de bonos
            hoja_bonos = sh.worksheet("bonos_ofrecidos_spirita")
            raw_data_bonos = hoja_bonos.get_all_values()
            headers_bonos = raw_data_bonos[0]
        
            # Manejar encabezados duplicados en bonos
            seen_bonos = set()
            unique_headers_bonos = []
            for header in headers_bonos:
                if header in seen_bonos:
                    counter = 1
                    while f"{header}_{counter}" in seen_bonos:
                        counter += 1
                    header = f"{header}_{counter}"
                seen_bonos.add(header)
                unique_headers_bonos.append(header)
        
            rows_bonos = raw_data_bonos[1:]
            df_bonos = pd.DataFrame(rows_bonos, columns=unique_headers_bonos)
        
            # Limpiar nombre de usuario
            df_bonos["USUARIO"] = df_bonos["USUARIO"].astype(str).str.strip().str.lower()
        
            # Obtener la última categoría de bono por usuario
            df_categorias = df_bonos.dropna(subset=["CATEGORIA DE BONO"]).sort_values("FECHA")
            df_categorias = df_categorias.groupby("USUARIO")["CATEGORIA DE BONO"].last().reset_index()
        
            # Unir con el registro principal
            df_bono = df_registro_users.merge(df_categorias, on="USUARIO", how="left")
        
            # Renombrar columnas al formato final
            df_bono = df_bono.rename(columns={
                "USUARIO": "Usuario",
                "FUNNEL": "Tipo de Bono",
                "BONOS OFRECIDOS": "Cuántas veces se le ofreció el bono",
                "BONOS USADOS": "Cuántas veces cargó con bono",
                "MONTO TOTAL CARGADO": "Monto total",
                "% DE CONVERSION": "Conversión",
                "ULT. ACTUALIZACION": "Fecha del último mensaje",
                "CATEGORIA DE BONO": "Categoría de Bono"
            })
        
            # Limpiar campos
            df_bono["Conversión"] = df_bono["Conversión"].astype(str).str.replace("%", "", regex=False)
            df_bono["Conversión"] = pd.to_numeric(df_bono["Conversión"], errors="coerce").fillna(0)
            df_bono["Fecha del último mensaje"] = df_bono["Fecha del último mensaje"].replace(
                ["30/12/1899", "1899-12-30"], "Sin registros"
            )
        
            # Seleccionar columnas finales
            columnas_finales = [
                "Usuario", "Tipo de Bono",
                "Cuántas veces se le ofreció el bono", "Cuántas veces cargó con bono",
                "Monto total", "Conversión",
                "Fecha del último mensaje", "Categoría de Bono"
            ]
            df_bono = df_bono[columnas_finales]
        
            # Mostrar en la app
            st.subheader("🎁 Tabla Bono - Spirita")
            st.dataframe(df_bono)
        
        except Exception as e:
            st.error(f"❌ Error al generar la Tabla Bono Spirita: {e}")

    
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
            "📦 Unificar múltiples reportes de jugadores",
            "📊 Jugadores VIP"
        ])

        if tarea == "📈 Analizar Lifetime Value (LTV)":
            archivo_temporal = st.file_uploader("📥 Pegá o subí aquí tus reportes", type=["csv", "xlsx", "xls"])
        
            if archivo_temporal and tipo_analisis == "Lifetime Value":
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

        elif tarea == "📊 Jugadores VIP":
            st.title("📊 Gestión de jugadores VIP y carga de reportes")
        
            # Conexión a Supabase
            try:
                engine = create_engine(st.secrets["DB_URL"])
                with engine.connect() as conn:
                    st.success("✅ Conectado a Supabase correctamente")
                    df = pd.read_sql("SELECT * FROM jugadores_vip LIMIT 5", conn)
                    st.dataframe(df)
            except Exception as e:
                st.error(f"❌ Error de conexión: {e}")
        
            st.divider()
            st.subheader("📥 Subir archivo Excel o ZIP para almacenar en la base")
        
            archivo = st.file_uploader("📁 Seleccioná un archivo .xlsx o .zip", type=["xlsx", "zip"])
        
            if archivo:
                if archivo.name.endswith(".xlsx"):
                    procesar_y_subir_excel(archivo, engine)
                elif archivo.name.endswith(".zip"):
                    procesar_y_subir_zip(archivo, engine)


    
    # === SECCIÓN: 🏢 Oficina VIP Grilla ===
    elif "🏢 Oficina VIP" in seccion:
        st.header("🏢 Oficina VIP")
    
        st.markdown("Esta sección permite individualizar a los jugadores según su comportamiento y actividad reciente.")
    
        archivo = st.file_uploader("📂 Subí el historial de actividad unificado (formato .xlsx)", type=["xlsx"], key="vip_uploader")
    
        if archivo:
            try:
                import pandas as pd
                from datetime import datetime, timedelta
                from io import BytesIO
    
                df = pd.read_excel(archivo)
    
                df["Apuesta"] = pd.to_numeric(df["Apuesta"], errors="coerce").fillna(0)
                df["Ganancias"] = pd.to_numeric(df["Ganancias"], errors="coerce").fillna(0)
                df["Hora de apertura"] = pd.to_datetime(df["Hora de apertura"], errors="coerce")
                df["Hora de ultima actividad"] = pd.to_datetime(df["Hora de ultima actividad"], errors="coerce")
                df["Fecha"] = df["Hora de apertura"].dt.date
                df["Hora"] = df["Hora de apertura"].dt.hour
    
                juego_frecuente = (
                    df.groupby(["Jugador", "Nombre del juego"])
                    .size()
                    .reset_index(name="Frecuencia")
                    .sort_values(["Jugador", "Frecuencia"], ascending=[True, False])
                    .drop_duplicates("Jugador")
                    .rename(columns={"Nombre del juego": "Juego más jugado"})
                )
    
                juego_frecuente = juego_frecuente.merge(
                    df[["Nombre del juego", "Categoría", "Sello"]].drop_duplicates(),
                    left_on="Juego más jugado",
                    right_on="Nombre del juego",
                    how="left"
                ).drop(columns=["Nombre del juego"])
    
                juego_frecuente = juego_frecuente.rename(columns={
                    "Categoría": "Tipo de juego",
                    "Sello": "Proveedor"
                })
    
                fecha_maxima = df["Fecha"].max()
    
                resumen = df.groupby("Jugador").agg({
                    "Apuesta": "sum",
                    "Ganancias": "sum",
                    "Fecha": pd.Series.nunique,
                    "Hora de ultima actividad": "max"
                }).reset_index()
    
                resumen = resumen.rename(columns={
                    "Apuesta": "Monto total apostado",
                    "Ganancias": "Monto total ganado",
                    "Fecha": "Días activos",
                    "Hora de ultima actividad": "Última actividad"
                })
    
                resumen["Días inactivos"] = (
                    pd.to_datetime(fecha_maxima).normalize() - resumen["Última actividad"].dt.normalize()
                ).dt.days
    
                resumen["Monto perdido"] = resumen["Monto total apostado"] - resumen["Monto total ganado"]
    
                def clasificar_estado(dias):
                    if dias <= 15:
                        return "🟢 Activo"
                    elif dias <= 45:
                        return "🟡 Inactivo (15-45 días)"
                    else:
                        return "🔴 Inactivo (+45 días)"
    
                resumen["Estado"] = resumen["Días inactivos"].apply(clasificar_estado)
    
                hora_frecuente_raw = df.groupby(["Jugador", "Hora"]).size().reset_index(name="Frecuencia")
                max_frecuencia = hora_frecuente_raw.groupby("Jugador")["Frecuencia"].transform("max")
                hora_frecuente_filtrada = hora_frecuente_raw[hora_frecuente_raw["Frecuencia"] == max_frecuencia]
                hora_frecuente_final = hora_frecuente_filtrada.groupby("Jugador")["Hora"].apply(
                    lambda x: ", ".join(str(h) for h in sorted(x))
                ).reset_index().rename(columns={"Hora": "Hora(s) más frecuente(s)"})
    
                def detectar_franja(hora_str):
                    horas = [int(h) for h in hora_str.split(",")]
                    franjas = set()
                    for h in horas:
                        if 0 <= h < 6:
                            franjas.add("Madrugada")
                        elif 6 <= h < 12:
                            franjas.add("Mañana")
                        elif 12 <= h < 18:
                            franjas.add("Tarde")
                        else:
                            franjas.add("Noche")
                    return ", ".join(sorted(franjas))
    
                hora_frecuente_final["Franja horaria predominante"] = hora_frecuente_final["Hora(s) más frecuente(s)"].apply(detectar_franja)
    
                def calcular_racha_maxima(fechas):
                    fechas_ordenadas = sorted(set(fechas))
                    racha = max_racha = 1
                    for i in range(1, len(fechas_ordenadas)):
                        if fechas_ordenadas[i] == fechas_ordenadas[i - 1] + timedelta(days=1):
                            racha += 1
                            max_racha = max(max_racha, racha)
                        else:
                            racha = 1
                    return max_racha
    
                racha_df = df.groupby("Jugador")["Fecha"].apply(calcular_racha_maxima).reset_index()
                racha_df = racha_df.rename(columns={"Fecha": "Racha máxima de días consecutivos"})
    
                df_final = resumen.merge(juego_frecuente, on="Jugador", how="left")
                df_final = df_final.merge(hora_frecuente_final, on="Jugador", how="left")
                df_final = df_final.merge(racha_df, on="Jugador", how="left")
    
                df_final = df_final[[
                    "Jugador", "Monto total apostado", "Monto total ganado", "Monto perdido",
                    "Juego más jugado", "Tipo de juego", "Proveedor",
                    "Días activos", "Días inactivos", "Estado",
                    "Hora(s) más frecuente(s)", "Franja horaria predominante",
                    "Racha máxima de días consecutivos"
                ]].sort_values(by="Monto total apostado", ascending=False)
    
                st.subheader("🔢 Tabla de jugadores individualizados")
                st.dataframe(df_final, use_container_width=True)
    
                jugador_seleccionado = st.selectbox("Seleccioná un jugador para ver su perfil individual:", df_final["Jugador"].unique())
    
                if jugador_seleccionado:
                    perfil = df_final[df_final["Jugador"] == jugador_seleccionado].iloc[0]
                    st.markdown("""
                    ### 📈 Perfil del jugador seleccionado
                    - **Monto total apostado:** ${:,.2f}
                    - **Monto total ganado:** ${:,.2f}
                    - **Monto perdido:** ${:,.2f}
                    - **Juego más jugado:** {}
                    - **Proveedor:** {}
                    - **Tipo de juego:** {}
                    - **Días activos:** {}
                    - **Días inactivos:** {}
                    - **Estado:** {}
                    - **Hora(s) más frecuente(s):** {}
                    - **Franja horaria predominante:** {}
                    - **Racha máxima de días consecutivos activos:** {}
                    - **Racha de depósitos:** Sin información
                    - **Patrón de juego:** En desarrollo
                    """.format(
                        perfil["Monto total apostado"],
                        perfil["Monto total ganado"],
                        perfil["Monto perdido"],
                        perfil["Juego más jugado"],
                        perfil["Proveedor"],
                        perfil["Tipo de juego"],
                        perfil["Días activos"],
                        perfil["Días inactivos"],
                        perfil["Estado"],
                        perfil["Hora(s) más frecuente(s)"],
                        perfil["Franja horaria predominante"],
                        perfil["Racha máxima de días consecutivos"]
                    ))
    
                output = BytesIO()
                with pd.ExcelWriter(output, engine="openpyxl") as writer:
                    df_final.to_excel(writer, index=False, sheet_name="Oficina VIP")
                output.seek(0)
    
                st.download_button(
                    "📅 Descargar Excel",
                    data=output,
                    file_name="oficina_vip_individualizada.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
    
            except Exception as e:
                st.error(f"❌ Error al procesar el archivo: {e}")







        

