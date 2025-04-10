
import streamlit as st
import pandas as pd
import datetime

st.set_page_config(page_title="App de Cargas - Casino", layout="wide")

st.title("🎰 App de Análisis de Cargas del Casino")

seccion = st.sidebar.radio("Seleccioná una sección:", ["🔝 Top 10 de Cargas", "📉 Jugadores Inactivos"])

# FUNCIONES AUXILIARES
def preparar_dataframe(df):
    df = df.rename(columns={
        "operación": "Tipo",
        "Depositar": "Monto",
        "Retirar": "?1",
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
    columnas_esperadas = [
        "ID", "Tipo", "Monto", "?1", "?2", "?3", "Saldo",
        "Fecha", "Hora", "UsuarioSistema", "Plataforma", "Admin", "Jugador", "Extra"
    ]
    if len(df.columns) == len(columnas_esperadas):
        df.columns = columnas_esperadas
        return df
    else:
        return None

# SECCIÓN 1: TOP 10 DE CARGAS
if seccion == "🔝 Top 10 de Cargas":
    st.header("🔝 Top 10 por Monto y Cantidad de Cargas")
    archivo = st.file_uploader("📁 Subí tu archivo de cargas recientes:", type=["xlsx", "xls", "csv"], key="top10")

    if archivo:
        if archivo.name.endswith(".csv"):
            df = pd.read_csv(archivo)
        else:
            df = pd.read_excel(archivo)

        df = preparar_dataframe(df)

        if df is not None:
            df_cargas = df[df["Tipo"] == "in"]
            df_cargas["Fecha"] = pd.to_datetime(df_cargas["Fecha"])

            top_monto = (
                df_cargas.groupby("Jugador")
                .agg(Monto_Total_Cargado=("Monto", "sum"), Cantidad_Cargas=("Jugador", "count"))
                .sort_values(by="Monto_Total_Cargado", ascending=False)
                .head(10)
                .reset_index()
            )

            top_cant = (
                df_cargas.groupby("Jugador")
                .agg(Cantidad_Cargas=("Jugador", "count"), Monto_Total_Cargado=("Monto", "sum"))
                .sort_values(by="Cantidad_Cargas", ascending=False)
                .head(10)
                .reset_index()
            )

            st.subheader("💰 Top 10 por Monto Total Cargado")
            st.dataframe(top_monto)

            st.subheader("🔢 Top 10 por Cantidad de Cargas")
            st.dataframe(top_cant)

            writer = pd.ExcelWriter("Top10_Cargas.xlsx", engine="xlsxwriter")
            top_monto.to_excel(writer, sheet_name="Top Monto", index=False)
            top_cant.to_excel(writer, sheet_name="Top Cantidad", index=False)
            writer.close()

            with open("Top10_Cargas.xlsx", "rb") as f:
                st.download_button("📥 Descargar Excel", f, file_name="Top10_Cargas.xlsx")
        else:
            st.error("❌ El archivo no tiene el formato esperado.")

# SECCIÓN 2: JUGADORES INACTIVOS + MENSAJE + SEGUIMIENTO
elif seccion == "📉 Jugadores Inactivos":
    st.header("📉 Detección y Segmentación de Jugadores Inactivos")
    archivo_inactivos = st.file_uploader("📁 Subí tu archivo con historial amplio de cargas:", type=["xlsx", "xls", "csv"], key="inactivos")

    if archivo_inactivos:
        if archivo_inactivos.name.endswith(".csv"):
            df2 = pd.read_csv(archivo_inactivos)
        else:
            df2 = pd.read_excel(archivo_inactivos)

        df2 = preparar_dataframe(df2)

        if df2 is not None:
            df2["Fecha"] = pd.to_datetime(df2["Fecha"])
            df2 = df2[df2["Tipo"] == "in"]

            hoy = pd.to_datetime(datetime.date.today())
            ultima_carga = df2.groupby("Jugador")["Fecha"].max().reset_index()
            ultima_carga["Dias_inactivo"] = (hoy - ultima_carga["Fecha"]).dt.days

            def campaña_y_mensaje(jugador, dias):
                if 6 <= dias <= 13:
                    return (
                        "Inactivo reciente: Bono moderado (50%) + mensaje 'Te esperamos'",
                        f"Hola {jugador}, hace {dias} días que no te vemos. ¡Te esperamos con un bono del 50% si volvés hoy! 🎁"
                    )
                elif 14 <= dias <= 22:
                    return (
                        "Semi-perdido: Bono fuerte (150%) + mensaje directo",
                        f"¡{jugador}, volvé a cargar y duplicamos tu saldo con un 150% extra! Hace {dias} días que te extrañamos. 🔥"
                    )
                elif 23 <= dias <= 30:
                    return (
                        "Inactivo prolongado: Oferta irresistible + mensaje emocional",
                        f"{jugador}, tu cuenta sigue activa y tenemos algo especial para vos. Hace {dias} días que no jugás, ¿te pasó algo? 💬 Tenés un regalo esperándote."
                    )
                else:
                    return ("", "")

            ultima_carga[["Campaña sugerida", "Mensaje personalizado"]] = ultima_carga.apply(
                lambda row: pd.Series(campaña_y_mensaje(row["Jugador"], row["Dias_inactivo"])), axis=1
            )

            resultado = ultima_carga[ultima_carga["Campaña sugerida"] != ""].sort_values(by="Dias_inactivo", ascending=False)

            st.subheader("📋 Jugadores inactivos segmentados con mensajes")

            enviados = []

            for _, row in resultado.iterrows():
                with st.expander(f"{row['Jugador']} ({row['Dias_inactivo']} días inactivo)"):
                    st.markdown(f"**Campaña sugerida:** {row['Campaña sugerida']}")
                    st.text_area("📨 Mensaje personalizado", value=row["Mensaje personalizado"], key=row["Jugador"])
                    enviado = st.checkbox("✅ Mensaje enviado", key=f"check_{row['Jugador']}")
                    enviados.append({
                        "Jugador": row["Jugador"],
                        "Días inactivo": row["Dias_inactivo"],
                        "Mensaje personalizado": row["Mensaje personalizado"],
                        "Enviado": enviado
                    })

            # Descargar tabla de seguimiento
            if enviados:
                df_enviados = pd.DataFrame(enviados)
                df_enviados.to_excel("seguimiento_reactivacion.xlsx", index=False)
                with open("seguimiento_reactivacion.xlsx", "rb") as f:
                    st.download_button("📥 Descargar seguimiento", f, file_name="seguimiento_reactivacion.xlsx")
        else:
            st.error("❌ El archivo no tiene el formato esperado.")
