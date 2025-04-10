
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import os
import json
import datetime

st.set_page_config(page_title="Reporte Casino", layout="wide")

# 🔐 CONTRASEÑA SIMPLE
password = st.text_input("🔑 Ingresá la contraseña para acceder:", type="password")
if password != "casino123":
    st.warning("Esta app es privada. Ingresá la contraseña correcta para continuar.")
    st.stop()

def aplicar_filtros(df, fecha_inicio, fecha_fin, hora_inicio, hora_fin):
    df["Fecha"] = pd.to_datetime(df["Fecha"])
    df["Hora"] = pd.to_datetime(df["Hora"], format="%H:%M:%S").dt.time
    fecha_inicio = pd.to_datetime(fecha_inicio)
    fecha_fin = pd.to_datetime(fecha_fin)
    df = df[(df["Fecha"] >= fecha_inicio) & (df["Fecha"] <= fecha_fin)]
    df = df[df["Hora"].between(hora_inicio, hora_fin)]
    return df

def procesar_reporte(df):
    columnas_esperadas = [
        "ID", "Tipo", "Monto", "?1", "?2", "?3", "Saldo",
        "Fecha", "Hora", "UsuarioSistema", "Plataforma", "Admin", "Jugador", "Extra"
    ]
    if len(df.columns) == len(columnas_esperadas):
        df.columns = columnas_esperadas
    else:
        st.error(f"❌ El archivo tiene {len(df.columns)} columnas pero se esperaban {len(columnas_esperadas)}.")
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
    return df_cargas, top_cantidades, top_montos

def guardar_comentario(jugador, comentario):
    if not os.path.exists("comentarios.json"):
        comentarios = {}
    else:
        with open("comentarios.json", "r") as f:
            comentarios = json.load(f)
    comentarios.setdefault(jugador, []).append({
        "comentario": comentario,
        "fecha": str(datetime.date.today())
    })
    with open("comentarios.json", "w") as f:
        json.dump(comentarios, f, indent=2)

def cargar_comentarios(jugador):
    if os.path.exists("comentarios.json"):
        with open("comentarios.json", "r") as f:
            comentarios = json.load(f)
        return comentarios.get(jugador, [])
    return []

def guardar_historial(top_cantidades, top_montos):
    hoy = str(datetime.date.today())
    os.makedirs("historial", exist_ok=True)
    top_cantidades.to_csv(f"historial/top_cant_{hoy}.csv", index=False)
    top_montos.to_csv(f"historial/top_monto_{hoy}.csv", index=False)

st.title("🎰 Reporte de Cargas del Casino")

archivo = st.file_uploader("📁 Subí tu archivo de reporte (.xlsx, .xls o .csv):", type=["xlsx", "xls", "csv"])

if archivo:
    columnas_esperadas = [
        "ID", "Tipo", "Monto", "?1", "?2", "?3", "Saldo",
        "Fecha", "Hora", "UsuarioSistema", "Plataforma", "Admin", "Jugador", "Extra"
    ]
    if archivo.name.endswith(".csv"):
        df = pd.read_csv(archivo)
    else:
        df = pd.read_excel(archivo)

    st.sidebar.header("📅 Filtros de Tiempo")
    fecha_inicio = st.sidebar.date_input("Desde", datetime.date.today())
    fecha_fin = st.sidebar.date_input("Hasta", datetime.date.today())
    hora_inicio = st.sidebar.time_input("Hora desde", datetime.time(6, 0))
    hora_fin = st.sidebar.time_input("Hora hasta", datetime.time(10, 0))

    df_filtrado = aplicar_filtros(df, fecha_inicio, fecha_fin, hora_inicio, hora_fin)
    df_cargas, top_cant, top_monto = procesar_reporte(df_filtrado)

    st.subheader("🔢 Top 10 por Cantidad de Cargas")
    st.dataframe(top_cant)

    st.subheader("💰 Top 10 por Monto Total Cargado")
    st.dataframe(top_monto)

    st.subheader("📊 Gráficos")
    col1, col2 = st.columns(2)
    with col1:
        fig1, ax1 = plt.subplots()
        ax1.bar(top_cant["Jugador"], top_cant["Cantidad_Cargas"])
        plt.xticks(rotation=45)
        st.pyplot(fig1)
    with col2:
        fig2, ax2 = plt.subplots()
        ax2.bar(top_monto["Jugador"], top_monto["Monto_Total_Cargado"])
        plt.xticks(rotation=45)
        st.pyplot(fig2)

    st.subheader("📈 Evolución diaria de cargas")
    df_cargas["Fecha"] = pd.to_datetime(df_cargas["Fecha"])
    carga_por_dia = df_cargas.groupby(df_cargas["Fecha"].dt.date)["Monto"].sum()
    fig3, ax3 = plt.subplots()
    ax3.plot(carga_por_dia.index, carga_por_dia.values)
    st.pyplot(fig3)

    st.subheader("🕒 Distribución por Hora")
    df_cargas["Hora"] = pd.to_datetime(df_cargas["Hora"].astype(str)).dt.hour
    carga_por_hora = df_cargas.groupby("Hora")["Monto"].sum()
    fig4, ax4 = plt.subplots()
    ax4.bar(carga_por_hora.index, carga_por_hora.values)
    st.pyplot(fig4)

    st.subheader("📝 Notas Internas por Jugador")
    jugador = st.selectbox("Seleccioná un jugador para ver o agregar comentarios:", df_cargas["Jugador"].unique())
    comentario = st.text_area("Agregar comentario")
    if st.button("Guardar comentario"):
        guardar_comentario(jugador, comentario)
        st.success("Comentario guardado.")

    comentarios_previos = cargar_comentarios(jugador)
    if comentarios_previos:
        st.write("📜 Comentarios anteriores:")
        for c in comentarios_previos:
            st.markdown(f"- *{c['fecha']}*: {c['comentario']}")

    guardar_historial(top_cant, top_monto)
    st.success("Historial diario guardado automáticamente.")
