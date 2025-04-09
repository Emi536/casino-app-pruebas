
import streamlit as st
import pandas as pd

# 🔐 CONTRASEÑA SIMPLE

if "acceso_valido" not in st.session_state:
    st.session_state.acceso_valido = False

if not st.session_state.acceso_valido:
    password = st.text_input("🔑 Ingresá la contraseña para acceder:", type="password")
    if password == "casino123":
        st.session_state.acceso_valido = True
        st.experimental_rerun()
    else:
        st.warning("Esta app es privada. Ingresá la contraseña correcta para continuar.")
        st.stop()


# --- FUNCIÓN DE PROCESAMIENTO ---
def procesar_reporte(df):
    columnas_esperadas = [
        "ID", "Tipo", "Monto", "?1", "?2", "?3", "Saldo",
        "Fecha", "Hora", "UsuarioSistema", "Plataforma", "Admin", "Jugador", "Extra"
    ]

    if len(df.columns) != len(columnas_esperadas):
        st.error(f"❌ El archivo tiene {len(df.columns)} columnas pero se esperaban {len(columnas_esperadas)}.")
        st.info("Asegurate de estar subiendo un archivo con el formato correcto.")
        st.stop()

    df.columns = columnas_esperadas

    df_cargas = df[df["Tipo"] == "in"]

    top_cantidades = (
        df_cargas.groupby("Jugador")
        .agg(Cantidad_Cargas=("Jugador", "count"), Monto_Total_Cargado=("Monto", "sum"))
        .sort_values(by="Cantidad_Cargas", ascending=False)
        .head(10)
        .reset_index()
    )

    top_montos = (
        df_cargas.groupby("Jugador")
        .agg(Monto_Total_Cargado=("Monto", "sum"), Cantidad_Cargas=("Jugador", "count"))
        .sort_values(by="Monto_Total_Cargado", ascending=False)
        .head(10)
        .reset_index()
    )

    return top_cantidades, top_montos

# --- INTERFAZ PRINCIPAL ---
st.title("📊 Reporte de Cargas del Casino")

archivo = st.file_uploader("📁 Subí tu archivo de reporte (.xlsx, .xls o .csv):", type=["xlsx", "xls", "csv"])

if archivo is not None:
    try:
        if archivo.name.endswith(".csv"):
            df = pd.read_csv(archivo)
        else:
            df = pd.read_excel(archivo)
        st.success("Archivo cargado correctamente ✅")

        top_cant, top_monto = procesar_reporte(df)

        st.subheader("🔢 Top 10 por Cantidad de Cargas")
        st.dataframe(top_cant)

        st.subheader("💰 Top 10 por Monto Total Cargado")
        st.dataframe(top_monto)

        excel_writer = pd.ExcelWriter("reporte_casino_resultado.xlsx", engine="xlsxwriter")
        top_cant.to_excel(excel_writer, sheet_name="Top Cantidad", index=False)
        top_monto.to_excel(excel_writer, sheet_name="Top Monto", index=False)
        excel_writer.close()

        with open("reporte_casino_resultado.xlsx", "rb") as file:
            st.download_button("📥 Descargar Reporte en Excel", file, file_name="Top_Reporte_Casino.xlsx")

    except Exception as e:
        st.error(f"❌ Error al leer el archivo: {e}")
        st.stop()
