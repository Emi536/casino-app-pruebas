import streamlit as st
import pandas as pd
import datetime
import plotly.express as px
from io import StringIO

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


# SECCIÓN 2: REGISTRO

elif "Registro de actividad de jugadores" in seccion:
    st.header("📋 Registro general de jugadores")
    
    metodo_carga = st.radio("¿Cómo querés cargar el reporte?", ["📄 Subir archivo", "📋 Pegar reporte manualmente"])

    if metodo_carga == "📄 Subir archivo":
        archivo = st.file_uploader("📁 Subí tu archivo de cargas:", type=["xlsx", "xls", "csv"], key="registro")
        if archivo:
            df = pd.read_excel(archivo) if archivo.name.endswith((".xlsx", ".xls")) else pd.read_csv(archivo)
        else:
            df = None

    elif metodo_carga == "📋 Pegar reporte manualmente":
        df = None
        texto_pegar = st.text_area("📋 Pegá aquí el reporte copiado (incluí encabezados)", height=300)
        if texto_pegar:
            try:
                texto_pegar_preview = texto_pegar[:500]  # Analizamos primeros caracteres
    
                if "\t" in texto_pegar_preview:
                    sep_detectado = "\t"
                elif ";" in texto_pegar_preview:
                    sep_detectado = ";"
                else:
                    sep_detectado = ","
    
                archivo_simulado = StringIO(texto_pegar)
                df = pd.read_csv(archivo_simulado, sep=sep_detectado, decimal=",")  # 💥 Aca corregimos también el decimal
    
                st.success(f"✅ Datos cargados correctamente detectando separador '{sep_detectado}' y decimal ','.")

            except Exception as e:
                st.error(f"❌ Error al procesar los datos pegados: {e}")
                df = None

    else:
        df = None

    # Si logramos obtener un DataFrame
    if df is not None:
        try:
            # 🔥 Renombrar columnas
            df = df.rename(columns={
                "operación": "Tipo",
                "Depositar": "Monto",
                "Retirar": "Retiro",
                "Fecha": "Fecha",
                "Al usuario": "Jugador"
            })

            # Preparar columnas
            df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce")
            df["Monto"] = pd.to_numeric(df["Monto"], errors="coerce").fillna(0)
            df["Retiro"] = df["Retiro"].astype(str).str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
            df["Retiro"] = pd.to_numeric(df["Retiro"], errors="coerce").fillna(0)

            jugadores = df["Jugador"].dropna().unique()
            resumen = []

            for jugador in jugadores:
                historial = df[df["Jugador"] == jugador].sort_values("Fecha")
                cargas = historial[historial["Tipo"].str.lower() == "in"]
                retiros = historial[historial["Tipo"].str.lower() == "out"]

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
                        "Cantidad de retiro": cantidad_retiro,
                        "LTV (Lifetime Value)": suma_de_cargas,
                        "Duración activa (días)": (ultima_carga - fecha_ingreso).days
                    })

            df_registro = pd.DataFrame(resumen)
            df_registro = df_registro.sort_values("Días inactivo", ascending=False)

            st.subheader("📄 Registro completo de jugadores")
            st.dataframe(df_registro)

            # 📥 Botón para descargar
            df_registro.to_excel("registro_jugadores.xlsx", index=False)
            with open("registro_jugadores.xlsx", "rb") as f:
                st.download_button("📥 Descargar Excel", f, file_name="registro_jugadores.xlsx")

            # 📈 Análisis avanzado - BI

            # 1. Top 10 por monto cargado
            st.subheader("🏆 Top 10 jugadores por monto total cargado")
            top_monto = df_registro.sort_values("Suma de las cargas", ascending=False).head(10)
            fig_top_monto = px.bar(top_monto, x="Nombre de jugador", y="Suma de las cargas", title="Top 10 - Monto Total Cargado")
            st.plotly_chart(fig_top_monto, use_container_width=True)

            # 2. Top 10 por cantidad de cargas
            st.subheader("🏆 Top 10 jugadores por cantidad de cargas")
            top_cargas = df_registro.sort_values("Veces que cargó", ascending=False).head(10)
            fig_top_cargas = px.bar(top_cargas, x="Nombre de jugador", y="Veces que cargó", title="Top 10 - Cantidad de Cargas")
            st.plotly_chart(fig_top_cargas, use_container_width=True)

            # 3. Evolución diaria de cargas, retiros y neto
            st.subheader("📈 Evolución diaria de cargas y retiros")
            df_diario = df.groupby(df["Fecha"].dt.date).agg({
                "Monto": "sum",
                "Retiro": "sum",
                "Jugador": "count"
            }).reset_index().rename(columns={"Jugador": "Cantidad de operaciones"})

            df_diario["Neto diario"] = df_diario["Monto"] - df_diario["Retiro"]

            fig_evolucion = px.line(df_diario, x="Fecha", y=["Monto", "Retiro", "Neto diario"], title="Evolución de cargas, retiros y neto diario")
            st.plotly_chart(fig_evolucion, use_container_width=True)

            # 4. Actividad por hora
            st.subheader("🕐 Análisis de actividad por hora")
            df["Hora"] = df["Fecha"].dt.hour
            df_hora = df.groupby("Hora").size().reset_index(name="Cantidad de movimientos")

            fig_hora = px.bar(df_hora, x="Hora", y="Cantidad de movimientos", title="Movimientos por hora del día")
            st.plotly_chart(fig_hora, use_container_width=True)

            # 5. Detección de anomalías
            st.subheader("🚨 Detección de anomalías")
            promedio_cargas = df_diario["Monto"].mean()
            df_diario["Anomalía"] = df_diario["Monto"] < (promedio_cargas * 0.7)

            fig_anomalias = px.scatter(df_diario, x="Fecha", y="Monto", color="Anomalía", title="Anomalías en cargas diarias")
            st.plotly_chart(fig_anomalias, use_container_width=True)

            # 6. Lifetime Value (LTV)
            st.subheader("💵 Análisis del Lifetime Value (LTV) de jugadores")
            fig_ltv = px.scatter(df_registro, x="Duración activa (días)", y="LTV (Lifetime Value)", hover_data=["Nombre de jugador"], title="Relación entre Duración Activa y LTV")
            st.plotly_chart(fig_ltv, use_container_width=True)

        except Exception as e:
            st.error(f"❌ Error al procesar el reporte: {e}")
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
