import streamlit as st
import pandas as pd
import datetime
import plotly.express as px

st.set_page_config(page_title="PlayerMetrics - Análisis de Cargas", layout="wide")
st.markdown("<h1 style='text-align: center; color:#F44336;'>Player Metrics</h1>", unsafe_allow_html=True)

# Agregar CSS para ocultar GitHub Icon
st.markdown("""
    <style>
    .stApp .header .stGitHub { display: none; }
    </style>
""", unsafe_allow_html=True)

seccion = st.sidebar.radio("Seleccioná una sección:", ["🔝 Métricas de jugadores", "📋 Registro de actividad de jugadores", "📆 Seguimiento de jugadores inactivos"])

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
            col3.metric("🧍 Jugadores Únicos", total_jugadores)

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

            st.subheader("🌡️ Carga de fichas por hora")
            graf_heatmap = px.density_heatmap(df_cargas, x="Hora", y="Fecha", nbinsx=24, nbinsy=len(df_cargas["Fecha"].dt.date.unique()), 
                                              title="Mapa de calor - Horario de cargas",
                                              labels={"Hora": "Hora del día", "Fecha": "Fecha"})
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
                    st.download_button(f"📥 Descargar Excel - Top {top_n} Cargas", f, file_name=f"Top{top_n}_Cargas.xlsx")
            except Exception as e:
                st.error(f"❌ Error al guardar el archivo: {e}")

        else:
            st.error("❌ El archivo no tiene el formato esperado.")



# SECCIÓN 2: JUGADORES INACTIVOS
elif seccion == "📉 Jugadores Inactivos":
    st.header("📉 Detección y Segmentación de Jugadores Inactivos")
    archivo_inactivos = st.file_uploader("📁 Subí tu archivo con historial amplio de cargas:", type=["xlsx", "xls", "csv"], key="inactivos")

    if archivo_inactivos:
        df2 = pd.read_excel(archivo_inactivos) if archivo_inactivos.name.endswith((".xlsx", ".xls")) else pd.read_csv(archivo_inactivos)
        df2 = preparar_dataframe(df2)

        if df2 is not None:
            df2["Fecha"] = pd.to_datetime(df2["Fecha"], errors="coerce")
            df2 = df2[df2["Tipo"] == "in"]

            hoy = pd.to_datetime(datetime.date.today())
            ultima_carga = df2.groupby("Jugador")["Fecha"].max().reset_index()
            ultima_carga["Dias_inactivo"] = (hoy - ultima_carga["Fecha"]).dt.days

            def campaña_y_mensaje(jugador, dias):
                if 6 <= dias <= 13:
                    return ("Inactivo reciente: Bono moderado (50%) + mensaje 'Te esperamos'", f"Hola {jugador}, hace {dias} días que no te vemos. ¡Te esperamos con un bono del 50% si volvés hoy! 🎁")
                elif 14 <= dias <= 22:
                    return ("Semi-perdido: Bono fuerte (150%) + mensaje directo", f"¡{jugador}, volvé a cargar y duplicamos tu saldo con un 150% extra! Hace {dias} días que te extrañamos. 🔥")
                elif 23 <= dias <= 30:
                    return ("Inactivo prolongado: Oferta irresistible + mensaje emocional", f"{jugador}, tu cuenta sigue activa y tenemos algo especial para vos. Hace {dias} días que no jugás, ¿te pasó algo? 💬 Tenés un regalo esperándote.")
                else:
                    return ("", "")

            ultima_carga[["Campaña sugerida", "Mensaje personalizado"]] = ultima_carga.apply(lambda row: pd.Series(campaña_y_mensaje(row["Jugador"], row["Dias_inactivo"])), axis=1)
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

            if enviados:
                df_enviados = pd.DataFrame(enviados)
                df_enviados.to_excel("seguimiento_reactivacion.xlsx", index=False)
                with open("seguimiento_reactivacion.xlsx", "rb") as f:
                    st.download_button("📥 Descargar seguimiento", f, file_name="seguimiento_reactivacion.xlsx")
        else:
            st.error("❌ El archivo no tiene el formato esperado.")

# SECCIÓN 3: REGISTRO
elif seccion == "📋 Registro":
    st.header("📋 Registro General de Jugadores")
    archivo = st.file_uploader("📁 Subí tu archivo de cargas:", type=["xlsx", "xls", "csv"], key="registro")
    dias_filtrado = st.number_input("📅 Filtrar jugadores inactivos hace al menos X días (opcional):", min_value=0, max_value=365, value=0)

    if archivo:
        df = pd.read_excel(archivo) if archivo.name.endswith((".xlsx", ".xls")) else pd.read_csv(archivo)
        df = preparar_dataframe(df)

        if df is not None:
            df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce")
            df["Monto"] = pd.to_numeric(df["Monto"], errors="coerce").fillna(0)
            df["Retiro"] = df["Retiro"].astype(str).str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
            df["Retiro"] = pd.to_numeric(df["Retiro"], errors="coerce").fillna(0)

            jugadores = df["Jugador"].dropna().unique()
            resumen = []

            for jugador in jugadores:
                historial = df[df["Jugador"] == jugador].sort_values("Fecha")
                cargas = historial[historial["Tipo"] == "in"]
                retiros = historial[historial["Tipo"] == "out"]

                if not cargas.empty:
                    fecha_ingreso = cargas["Fecha"].min()
                    ultima_carga = cargas["Fecha"].max()
                    veces_que_cargo = len(cargas)
                    suma_de_cargas = cargas["Monto"].sum()
                    cantidad_retiro = retiros["Retiro"].sum()
                    dias_inactivo = (pd.to_datetime(datetime.date.today()) - ultima_carga).days

                    resumen.append({
                        "Nombre de jugador": jugador,
                        "Fecha que ingresó": fecha_ingreso,
                        "Veces que cargó": veces_que_cargo,
                        "Suma de las cargas": suma_de_cargas,
                        "Última vez que cargó": ultima_carga,
                        "Días inactivo": dias_inactivo,
                        "Cantidad de retiro": cantidad_retiro
                    })

            df_registro = pd.DataFrame(resumen)

            if dias_filtrado > 0:
                df_registro = df_registro[df_registro["Días inactivo"] >= dias_filtrado]

            df_registro = df_registro.sort_values("Días inactivo", ascending=False)

            st.subheader("📄 Registro completo de jugadores")
            st.dataframe(df_registro)

            df_registro.to_excel("registro_jugadores.xlsx", index=False)
            with open("registro_jugadores.xlsx", "rb") as f:
                st.download_button("📥 Descargar Excel", f, file_name="registro_jugadores.xlsx")
        else:
            st.error("❌ El archivo no tiene el formato esperado.")


# SECCIÓN 4: INACTIVOS AGENDA
elif seccion == "📆 Inactivos Agenda":
    st.header("📆 Agenda de Jugadores Inactivos Detectados")

    archivo_agenda = st.file_uploader("📁 Subí tu archivo con dos hojas (Nombre y Reporte General):", type=["xlsx", "xls"], key="agenda")

    if archivo_agenda:
        try:
            df_hoja1 = pd.read_excel(archivo_agenda, sheet_name=0)
            df_hoja2 = pd.read_excel(archivo_agenda, sheet_name=1)

            df_hoja2 = df_hoja2.rename(columns={
                "operación": "Tipo",
                "Depositar": "Monto",
                "Fecha": "Fecha",
                "Al usuario": "Jugador"
            })

            df_hoja2["Jugador"] = df_hoja2["Jugador"].astype(str).str.strip().str.lower()
            df_hoja2["Fecha"] = pd.to_datetime(df_hoja2["Fecha"], errors="coerce")
            df_hoja2["Monto"] = pd.to_numeric(df_hoja2["Monto"], errors="coerce").fillna(0)

            nombres_hoja1 = df_hoja1["Nombre"].dropna().astype(str).str.strip().str.lower().unique()
            df_hoja2["Jugador"] = df_hoja2["Jugador"].astype(str).str.strip().str.lower()
            df_filtrado = df_hoja2[df_hoja2["Jugador"].isin(nombres_hoja1)]

            resumen = []
            hoy = pd.to_datetime(datetime.date.today())

            for jugador in df_filtrado["Jugador"].dropna().unique():
                historial = df_filtrado[df_filtrado["Jugador"] == jugador].sort_values("Fecha")
                cargas = historial[historial["Tipo"] == "in"]

                if not cargas.empty:
                    fecha_ingreso = cargas["Fecha"].min()
                    ultima_carga = cargas["Fecha"].max()
                    veces_que_cargo = len(cargas)
                    suma_de_cargas = cargas["Monto"].sum()
                    dias_inactivo = (hoy - ultima_carga).days

                    resumen.append({
                        "Nombre de Usuario": jugador,
                        "Fecha que ingresó": fecha_ingreso,
                        "Veces que cargó": veces_que_cargo,
                        "Suma de las cargas": suma_de_cargas,
                        "Última vez que cargó": ultima_carga,
                        "Días inactivos": dias_inactivo,
                        "Cantidad de retiro": historial[historial["Tipo"] == "out"]["Retirar"].sum()
                    })

            
            
            if resumen:
                df_resultado = pd.DataFrame(resumen).sort_values("Días inactivos", ascending=False)

                df_hoja1["Nombre_normalizado"] = df_hoja1["Nombre"].astype(str).str.strip().str.lower()
                df_hoja1 = df_hoja1[["Nombre_normalizado", "Sesiones"]]
                df_resultado["Nombre_normalizado"] = df_resultado["Nombre de Usuario"].astype(str).str.strip().str.lower()
                df_resultado = df_resultado.merge(df_hoja1, on="Nombre_normalizado", how="left")
                df_resultado.drop(columns=["Nombre_normalizado"], inplace=True)

                sesiones_disponibles = df_resultado["Sesiones"].dropna().unique()
                sesion_filtrada = st.selectbox("🎯 Filtrar por Sesión (opcional):", options=["Todas"] + sorted(sesiones_disponibles.tolist()))
                if sesion_filtrada != "Todas":
                    df_resultado = df_resultado[df_resultado["Sesiones"] == sesion_filtrada]

                st.subheader("📋 Resumen de Actividad de Jugadores Coincidentes")
                st.dataframe(df_resultado)

                df_resultado.to_excel("agenda_inactivos_resumen.xlsx", index=False)
                with open("agenda_inactivos_resumen.xlsx", "rb") as f:
                    st.download_button("📥 Descargar Excel", f, file_name="agenda_inactivos_resumen.xlsx")
            else:
                st.warning("No se encontraron coincidencias entre ambas hojas.")

        except Exception as e:
            st.error(f"❌ Error al procesar el archivo: {e}")
