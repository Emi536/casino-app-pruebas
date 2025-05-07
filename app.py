import streamlit as st
st.set_page_config(page_title="PlayerMetrics - Análisis de Cargas", layout="wide")

import pandas as pd
import datetime
import plotly.express as px
from io import StringIO
import os
import gspread
from google.oauth2 import service_account
import pytz
import hashlib
import re

# --- Título principal ---
st.markdown("<h1 style='text-align: center; color:#F44336;'>Player Metrics</h1>", unsafe_allow_html=True)
import streamlit as st
import hashlib

# --- Cargar desde secrets ---
USER = st.secrets["auth"]["usuario"]
PASSWORD = st.secrets["auth"]["clave"]

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# --- Session state login persistente ---
if "logueado" not in st.session_state:
    st.session_state["logueado"] = False

# --- Pantalla de login ---
if not st.session_state["logueado"]:
    st.title("🔐 Iniciar sesión")
    usuario_input = st.text_input("Usuario")
    clave_input = st.text_input("Contraseña", type="password")

    login_btn = st.button("Iniciar sesión")
    
    if login_btn:
        if usuario_input == USER and hash_password(clave_input) == hash_password(PASSWORD):
            st.session_state["logueado"] = True
            st.rerun()  # ✅ Ahora seguro
        else:
            st.error("❌ Usuario o contraseña incorrectos")
    st.stop()

# --- CONTENIDO SEGURO DE LA APP ---
st.sidebar.success(f"Bienvenido, {USER}")
if st.sidebar.button("Cerrar sesión"):
    st.session_state.clear()
    st.rerun()


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

seccion = st.sidebar.radio("Seleccioná una sección:", ["🔝 Métricas de jugadores", "📋 Registro Fénix","📋 Registro Eros","📋 Registro Bet Argento", "📆 Seguimiento de jugadores inactivos"])

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


#SECCIÓN FÉNIX
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

    def limpiar_dataframe(df_temp):
        df_temp = df_temp.copy()
        if "Jugador" in df_temp.columns:
            df_temp["Jugador"] = df_temp["Jugador"].astype(str).apply(lambda x: x.strip().lower())
        if "Monto" in df_temp.columns:
            df_temp["Monto"] = pd.to_numeric(df_temp["Monto"], errors="coerce").fillna(0)
        if "Retiro" in df_temp.columns:
            df_temp["Retiro"] = pd.to_numeric(df_temp["Retiro"], errors="coerce").fillna(0)
        if "Fecha" in df_temp.columns:
            df_temp["Fecha"] = pd.to_datetime(df_temp["Fecha"], errors="coerce")
        return df_temp


    df_historial = limpiar_dataframe(df_historial)

    if "Fecha" in df_historial.columns:
        df_historial["Fecha"] = pd.to_datetime(df_historial["Fecha"], errors="coerce")
        df_historial = df_historial[df_historial["Fecha"].notna()]
        limite = fecha_actual_date - datetime.timedelta(days=9)
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
            df_nuevo = pd.read_csv(archivo_limpio, sep=sep_detectado, decimal=".", thousands=",", dtype=str)
            df_nuevo = df_nuevo.loc[:, ~df_nuevo.columns.str.contains("^Unnamed")]

            columnas_requeridas = ["operación", "Depositar", "Retirar", "Fecha", "Al usuario"]
            if not all(col in df_nuevo.columns for col in columnas_requeridas):
                st.error("❌ El reporte pegado no contiene los encabezados necesarios o está mal formateado.")
                st.stop()

            df_nuevo = df_nuevo.rename(columns={
                "operación": "Tipo",
                "Depositar": "Monto",
                "Retirar": "Retiro",
                "Fecha": "Fecha",
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
        df = df_historial.copy()

        try:
            valores_hl = ["hl_casinofenix"]
            valores_wagger = ["Fenix_Wagger100", "Fenix_Wagger40", "Fenix_Wagger30", "Fenix_Wagger50", "Fenix_Wagger150", "Fenix_Wagger200"]

            resumen = []
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

                if not cargas.empty:
                    resumen.append({
                        "Nombre de jugador": jugador,
                        "Fecha que ingresó": cargas["Fecha"].min(),
                        "Veces que cargó": len(cargas),
                        "Hl": hl,
                        "Wagger": wagger,
                        "Monto total": total_monto,
                        "Última vez que cargó": cargas["Fecha"].max(),
                        "Días inactivo": (pd.to_datetime(datetime.date.today()) - cargas["Fecha"].max()).days,
                        "Cantidad de retiro": retiros["Retiro"].sum(),
                        "LTV (Lifetime Value)": total_monto,
                        "Duración activa (días)": (cargas["Fecha"].max() - cargas["Fecha"].min()).days
                    })

            df_registro = pd.DataFrame(resumen).sort_values("Días inactivo", ascending=False)

            st.subheader("📄 Registro completo de jugadores")
            st.dataframe(df_registro)

            df_registro.to_excel("registro_jugadores.xlsx", index=False)
            with open("registro_jugadores.xlsx", "rb") as f:
                st.download_button("📅 Descargar Excel", f, file_name="registro_jugadores.xlsx")

        except Exception as e:
            st.error(f"❌ Error al generar el resumen: {e}")

    
    # 🔵 Tabla Bono Fénix
        try:
            hoja_bonos_fenix = sh.worksheet("Exclusivos + recurrentes fenix")
            datos_bonos = hoja_bonos_fenix.get_all_records()
            df_bonos_fenix = pd.DataFrame(datos_bonos)
        
            # Limpieza y transformación
            df_bonos_fenix["BONOS USADOS"] = pd.to_numeric(df_bonos_fenix["BONOS USADOS"], errors="coerce").fillna(0).astype(int)
            df_bonos_fenix["% DE CONVERSION"] = df_bonos_fenix["% DE CONVERSION"].astype(str).str.replace('%', '', regex=False)
            df_bonos_fenix["% DE CONVERSION"] = pd.to_numeric(df_bonos_fenix["% DE CONVERSION"], errors="coerce").fillna(0)
        
            df_bonos_fenix["CARGÓ CON BONO"] = df_bonos_fenix["% DE CONVERSION"].apply(lambda x: "Sí" if x > 0 else "No")
        
            df_bonos_fenix.rename(columns={
                "USUARIO": "Usuario",
                "FUNNEL": "Tipo de jugador",
                "BONOS USADOS": "Veces que aceptó",
                "% DE CONVERSION": "% Conversión",
                "FECHA ULT. MSJ": "Fecha último mensaje"
            }, inplace=True)
        
            tabla_bono_fenix = df_bonos_fenix[[
                "Usuario", "Tipo de jugador", "CARGÓ CON BONO",
                "% Conversión", "Veces que aceptó", "Fecha último mensaje"
            ]]
        
            st.subheader("🎁 Tabla Bono - Fénix")
            st.dataframe(tabla_bono_fenix)
        
        except Exception as e:
            st.error(f"❌ Error al cargar la tabla bono Fénix: {e}")


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
        valor = str(valor).strip()
        if "," in valor and "." in valor:
            valor = valor.replace(".", "").replace(",", ".")
        elif "," in valor:
            valor = valor.replace(",", ".")
        try:
            return float(valor)
        except:
            return 0.0

    def limpiar_dataframe(df_temp):
        df_temp = df_temp.copy()
        if "Jugador" in df_temp.columns:
            df_temp["Jugador"] = df_temp["Jugador"].astype(str).apply(lambda x: x.strip().lower())
        if "Monto" in df_temp.columns:
            df_temp["Monto"] = df_temp["Monto"].apply(convertir_monto)
        if "Retiro" in df_temp.columns:
            df_temp["Retiro"] = df_temp["Retiro"].apply(convertir_monto)
        if "Fecha" in df_temp.columns:
            df_temp["Fecha"] = pd.to_datetime(df_temp["Fecha"], errors="coerce")
        return df_temp

    df_historial = limpiar_dataframe(df_historial)

    if "Fecha" in df_historial.columns:
        df_historial["Fecha"] = pd.to_datetime(df_historial["Fecha"], errors="coerce")
        df_historial = df_historial[df_historial["Fecha"].notna()]
        limite = fecha_actual_date - datetime.timedelta(days=9)
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
            df_nuevo = pd.read_csv(archivo_limpio, sep=sep_detectado, decimal=",", dtype=str)
            df_nuevo = df_nuevo.loc[:, ~df_nuevo.columns.str.contains("^Unnamed")]

            columnas_requeridas = ["operación", "Depositar", "Retirar", "Fecha", "Al usuario"]
            if not all(col in df_nuevo.columns for col in columnas_requeridas):
                st.error("❌ El reporte pegado no contiene los encabezados necesarios o está mal formateado.")
                st.stop()

            df_nuevo = df_nuevo.rename(columns={
                "operación": "Tipo",
                "Depositar": "Monto",
                "Retirar": "Retiro",
                "Fecha": "Fecha",
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
        df = df_historial.copy()

        try:
            valores_hl = ["hl_Erosonline"]
            valores_wagger = ["Eros_wagger30%", "Eros_wagger40%", "Eros_wagger50%", "Eros_wagger100%", "Eros_wagger150%", "Eros_wagger200%"]

            resumen = []
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

                if not cargas.empty:
                    resumen.append({
                        "Nombre de jugador": jugador,
                        "Fecha que ingresó": cargas["Fecha"].min(),
                        "Veces que cargó": len(cargas),
                        "Hl": hl,
                        "Wagger": wagger,
                        "Monto total": total_monto,
                        "Última vez que cargó": cargas["Fecha"].max(),
                        "Días inactivo": (pd.to_datetime(datetime.date.today()) - cargas["Fecha"].max()).days,
                        "Cantidad de retiro": retiros["Retiro"].sum(),
                        "LTV (Lifetime Value)": total_monto,
                        "Duración activa (días)": (cargas["Fecha"].max() - cargas["Fecha"].min()).days
                    })

            df_registro = pd.DataFrame(resumen).sort_values("Días inactivo", ascending=False)

            st.subheader("📄 Registro completo de jugadores")
            st.dataframe(df_registro)

            df_registro.to_excel("registro_jugadores.xlsx", index=False)
            with open("registro_jugadores.xlsx", "rb") as f:
                st.download_button("📅 Descargar Excel", f, file_name="registro_jugadores.xlsx")

        except Exception as e:
            st.error(f"❌ Error al generar el resumen: {e}")

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
        hoja_argento = sh.worksheet("registro_betargento")
        data_argento = hoja_argento.get_all_records()
        df_historial = pd.DataFrame(data_argento)
    except:
        hoja_argento = sh.add_worksheet(title="registro_betargento", rows="1000", cols="20")
        df_historial = pd.DataFrame()

    def convertir_monto(valor):
        if pd.isna(valor): return 0.0
        valor = str(valor).strip()
        if "," in valor and "." in valor:
            valor = valor.replace(".", "").replace(",", ".")
        elif "," in valor:
            valor = valor.replace(",", ".")
        try:
            return float(valor)
        except:
            return 0.0

    def limpiar_dataframe(df_temp):
        df_temp = df_temp.copy()
        if "Jugador" in df_temp.columns:
            df_temp["Jugador"] = df_temp["Jugador"].astype(str).apply(lambda x: x.strip().lower())
        if "Monto" in df_temp.columns:
            df_temp["Monto"] = df_temp["Monto"].apply(convertir_monto)
        if "Retiro" in df_temp.columns:
            df_temp["Retiro"] = df_temp["Retiro"].apply(convertir_monto)
        if "Fecha" in df_temp.columns:
            df_temp["Fecha"] = pd.to_datetime(df_temp["Fecha"], errors="coerce")
        return df_temp

    df_historial = limpiar_dataframe(df_historial)

    if "Fecha" in df_historial.columns:
        df_historial["Fecha"] = pd.to_datetime(df_historial["Fecha"], errors="coerce")
        df_historial = df_historial[df_historial["Fecha"].notna()]
        limite = fecha_actual_date - datetime.timedelta(days=9)
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
            df_nuevo = pd.read_csv(archivo_limpio, sep=sep_detectado, decimal=",", dtype=str)
            df_nuevo = df_nuevo.loc[:, ~df_nuevo.columns.str.contains("^Unnamed")]

            columnas_requeridas = ["operación", "Depositar", "Retirar", "Fecha", "Al usuario"]
            if not all(col in df_nuevo.columns for col in columnas_requeridas):
                st.error("❌ El reporte pegado no contiene los encabezados necesarios o está mal formateado.")
                st.stop()

            df_nuevo = df_nuevo.rename(columns={
                "operación": "Tipo",
                "Depositar": "Monto",
                "Retirar": "Retiro",
                "Fecha": "Fecha",
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
        df = df_historial.copy()

        try:
            valores_hl = ["hl_betargento"]
            valores_wagger = ["Argento_Wager", "Argento_Wager30", "Argento_Wager40", "Argento_Wager50", "Argento_Wager100", "Argento_Wager150", "Argento_Wager200"]

            resumen = []
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

                if not cargas.empty:
                    resumen.append({
                        "Nombre de jugador": jugador,
                        "Fecha que ingresó": cargas["Fecha"].min(),
                        "Veces que cargó": len(cargas),
                        "Hl": hl,
                        "Wagger": wagger,
                        "Monto total": total_monto,
                        "Última vez que cargó": cargas["Fecha"].max(),
                        "Días inactivo": (pd.to_datetime(datetime.date.today()) - cargas["Fecha"].max()).days,
                        "Cantidad de retiro": retiros["Retiro"].sum(),
                        "LTV (Lifetime Value)": total_monto,
                        "Duración activa (días)": (cargas["Fecha"].max() - cargas["Fecha"].min()).days
                    })

            df_registro = pd.DataFrame(resumen).sort_values("Días inactivo", ascending=False)
            st.subheader("📄 Registro completo de jugadores")
            st.dataframe(df_registro)

            df_registro.to_excel("registro_jugadores.xlsx", index=False)
            with open("registro_jugadores.xlsx", "rb") as f:
                st.download_button("📅 Descargar Excel", f, file_name="registro_jugadores.xlsx")

        except Exception as e:
            st.error(f"❌ Error al generar el resumen: {e}")

elif seccion == "📆 Seguimiento de jugadores inactivos":
    st.header("📆 Seguimiento de Jugadores Inactivos Mejorado")
    archivo_agenda = st.file_uploader("📁 Subí tu archivo con dos hojas (Nombres y Reporte General):", type=["xlsx", "xls"], key="agenda")

    if archivo_agenda:
        try:
            df_hoja1 = pd.read_excel(archivo_agenda, sheet_name=0)
            df_hoja2 = pd.read_excel(archivo_agenda, sheet_name=1)

            df_hoja2 = df_hoja2.rename(columns={
                "operación": "Tipo",
                "Depositar": "Monto",
                "Fecha": "Fecha",
                "Al usuario": "Jugador",
                "Retirar": "Retirar"
            })

            df_hoja2["Jugador"] = df_hoja2["Jugador"].astype(str).str.strip().str.lower()
            df_hoja2["Fecha"] = pd.to_datetime(df_hoja2["Fecha"], errors="coerce")
            df_hoja2["Monto"] = pd.to_numeric(df_hoja2["Monto"], errors="coerce").fillna(0)
            df_hoja2["Retirar"] = pd.to_numeric(df_hoja2["Retirar"], errors="coerce").fillna(0)

            nombres_hoja1 = df_hoja1["Nombre"].dropna().astype(str).str.strip().str.lower().unique()
            df_filtrado = df_hoja2[df_hoja2["Jugador"].isin(nombres_hoja1)]

            resumen = []
            hoy = pd.to_datetime(datetime.date.today())

            for jugador in df_filtrado["Jugador"].dropna().unique():
                historial = df_filtrado[df_filtrado["Jugador"] == jugador].sort_values("Fecha")
                cargas = historial[historial["Tipo"].str.lower() == "in"]

                if not cargas.empty:
                    fecha_ingreso = cargas["Fecha"].min()
                    ultima_carga = cargas["Fecha"].max()
                    veces_que_cargo = len(cargas)
                    suma_de_cargas = cargas["Monto"].sum()
                    promedio_monto = cargas["Monto"].mean()
                    dias_inactivo = (hoy - ultima_carga).days
                    dias_activos = (ultima_carga - fecha_ingreso).days
                    cantidad_retiro = historial[historial["Tipo"].str.lower() == "out"]["Retirar"].sum()

                    ultimos_30 = cargas[cargas["Fecha"] >= hoy - pd.Timedelta(days=30)]
                    cargas_30 = len(ultimos_30)
                    monto_30 = ultimos_30["Monto"].mean() if not ultimos_30.empty else 0

                    riesgo = min(100, (dias_inactivo * 2.5) + (10 / (cargas_30 + 1)) + (3000 / (monto_30 + 1)))
                    riesgo = round(riesgo, 2)

                    if riesgo >= 70:
                        categoria = "🔥 Alto"
                        accion = "Bono urgente / Contacto inmediato"
                    elif 40 <= riesgo < 70:
                        categoria = "🔹 Medio"
                        accion = "Mantener contacto frecuente"
                    else:
                        categoria = "🔷 Bajo"
                        accion = "Sin acción inmediata"

                    resumen.append({
                        "Nombre de Usuario": jugador,
                        "Fecha que ingresó": fecha_ingreso,
                        "Última vez que cargó": ultima_carga,
                        "Veces que cargó": veces_que_cargo,
                        "Suma de las cargas": suma_de_cargas,
                        "Monto promedio": promedio_monto,
                        "Días inactivos": dias_inactivo,
                        "Tiempo activo antes de inactividad (días)": dias_activos,
                        "Cargas últimos 30d": cargas_30,
                        "Monto promedio 30d": monto_30,
                        "Cantidad de retiro": cantidad_retiro,
                        "Riesgo de inactividad (%)": riesgo,
                        "Nivel de riesgo": categoria,
                        "Acción sugerida": accion,
                        "Historial de contacto": "Sin contacto"
                    })

            if resumen:
                df_resultado = pd.DataFrame(resumen).sort_values("Riesgo de inactividad (%)", ascending=False)

                def color_alerta(dias):
                    if dias > 30:
                        return "🔴 Rojo"
                    elif dias >= 15:
                        return "🟡 Amarillo"
                    else:
                        return "🟢 Verde"

                df_resultado["Alerta de inactividad"] = df_resultado["Días inactivos"].apply(color_alerta)

                st.subheader("📊 Resumen de Inactividad y Riesgos")

                riesgo_filtrar = st.selectbox("Filtrar jugadores por nivel de riesgo:", ["Todos", "Alto", "Medio", "Bajo"])
                if riesgo_filtrar != "Todos":
                    df_resultado = df_resultado[df_resultado["Nivel de riesgo"].str.contains(riesgo_filtrar)]

                editable_cols = ["Historial de contacto"]
                st.data_editor(
                    df_resultado,
                    num_rows="dynamic",
                    use_container_width=True,
                    column_config={col: st.column_config.TextColumn() for col in editable_cols}
                )

                # 📈 Gráficos
                st.subheader("📉 Tendencia promedio de inactividad")
                dias_inactivos_media = df_resultado.groupby("Días inactivos").size().reset_index(name="Cantidad")
                fig_linea = px.line(dias_inactivos_media, x="Días inactivos", y="Cantidad", title="Días promedio de inactividad")
                st.plotly_chart(fig_linea, use_container_width=True)

                st.subheader("🧐 Probabilidad de reactivación")
                df_resultado["Probabilidad de reactivación (%)"] = 100 - df_resultado["Riesgo de inactividad (%)"]
                fig_reactivacion = px.bar(df_resultado, x="Nombre de Usuario", y="Probabilidad de reactivación (%)", color="Nivel de riesgo", title="Chance de que recarguen")
                st.plotly_chart(fig_reactivacion, use_container_width=True)

                st.subheader("⏳ Tiempo promedio de retención")
                tiempo_promedio_retencion = df_resultado["Tiempo activo antes de inactividad (días)"].mean()
                st.metric("Tiempo activo promedio", f"{tiempo_promedio_retencion:.1f} días")

                st.subheader("🔻 Funnel de abandono")
                funnel = {
                    "0-15 días": (df_resultado["Días inactivos"] <= 15).sum(),
                    "16-30 días": ((df_resultado["Días inactivos"] > 15) & (df_resultado["Días inactivos"] <= 30)).sum(),
                    "31-60 días": ((df_resultado["Días inactivos"] > 30) & (df_resultado["Días inactivos"] <= 60)).sum(),
                    "60+ días": (df_resultado["Días inactivos"] > 60).sum()
                }
                funnel_df = pd.DataFrame(list(funnel.items()), columns=["Periodo", "Cantidad"])
                fig_funnel = px.funnel(funnel_df, x="Cantidad", y="Periodo", title="Funnel de abandono")
                st.plotly_chart(fig_funnel, use_container_width=True)

                st.subheader("📈 Predicción de abandono futuro")
                cantidad_riesgo_alto = (df_resultado["Riesgo de inactividad (%)"] >= 60).sum()
                abandono_esperado = cantidad_riesgo_alto * 0.7
                if abandono_esperado > 0:
                    fig_prediccion = px.bar(
                        x=["Jugadores activos", "Posibles abandonos"],
                        y=[len(df_resultado) - abandono_esperado, abandono_esperado],
                        title="Proyección de abandono próximo",
                        labels={"x": "Estado", "y": "Cantidad"}
                    )
                    st.plotly_chart(fig_prediccion, use_container_width=True)
                else:
                    st.info("Actualmente no hay suficientes jugadores en riesgo medio-alto (60%+) para proyectar abandonos.")

        except Exception as e:
            st.error(f"❌ Error al procesar el archivo: {e}")
