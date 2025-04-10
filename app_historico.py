
import streamlit as st
import pandas as pd
import datetime
import os

st.set_page_config(page_title="Reporte Casino Histórico", page_icon="🎰")
st.title("📊 Análisis de Reportes del Casino")

password = st.text_input("🔐 Ingresá la contraseña para acceder:", type="password")
if password != "casino123":
    st.warning("Contraseña incorrecta.")
    st.stop()

archivo = st.file_uploader("📁 Subí tu archivo de reporte (.xlsx, .xls, .csv):", type=["xlsx", "xls", "csv"])

if archivo:
    try:
        if archivo.name.endswith(".csv"):
            df = pd.read_csv(archivo)
        else:
            df = pd.read_excel(archivo)

        st.success("✅ Archivo cargado correctamente.")
        df.columns = [
            "ID", "Tipo", "Monto", "?1", "?2", "?3", "Saldo",
            "Fecha", "Hora", "UsuarioSistema", "Plataforma", "Admin", "Jugador", "Extra"
        ]
        df["Fecha"] = pd.to_datetime(df["Fecha"])

        # FILTROS
        st.subheader("📆 Filtro por rango de fechas")
        col1, col2 = st.columns(2)
        fecha_inicio = col1.date_input("Desde", df["Fecha"].min().date())
        fecha_fin = col2.date_input("Hasta", df["Fecha"].max().date())
        df = df[(df["Fecha"].dt.date >= fecha_inicio) & (df["Fecha"].dt.date <= fecha_fin)]

        # TOP JUGADORES
        df_cargas = df[df["Tipo"] == "in"]
        top = (
            df_cargas.groupby("Jugador")
            .agg(Cargas_Totales=("Jugador", "count"), Monto_Total=("Monto", "sum"))
            .sort_values(by="Monto_Total", ascending=False)
            .head(10)
            .reset_index()
        )

        st.subheader("🏆 Top 10 jugadores por monto")
        st.dataframe(top)

        # GRÁFICO HISTÓRICO
        st.subheader("📈 Evolución diaria de cargas")
        resumen_diario = df_cargas.groupby(df_cargas["Fecha"].dt.date)["Monto"].sum()
        st.line_chart(resumen_diario)

        # CHECK DE CONTACTO
        st.subheader("✅ Seguimiento de jugadores (¿Ya fueron contactados?)")
        for i, row in top.iterrows():
            jugador = row["Jugador"]
            col1, col2 = st.columns([3, 1])
            col1.markdown(f"**{jugador}** - 💰 ${row['Monto_Total']:,.2f}")
            if col2.checkbox("Contactado", key=jugador):
                st.success(f"{jugador} fue marcado como contactado.")

    except Exception as e:
        st.error(f"❌ Error al procesar el archivo: {e}")
else:
    st.info("Subí un archivo para comenzar.")
