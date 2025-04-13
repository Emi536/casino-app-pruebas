import streamlit as st
import pandas as pd
import datetime

st.set_page_config(page_title="App de Cargas - Casino", layout="wide")
st.title("🎰 App de Análisis de Cargas del Casino")

seccion = st.sidebar.radio("Seleccioná una sección:", ["🔝 Top 10 de Cargas", "📉 Jugadores Inactivos", "📋 Registro", "📅 Inactivos Agenda"])

# FUNCIONES AUXILIARES
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

# SECCIÓN 1: TOP 10 DE CARGAS
if seccion == "🔝 Top 10 de Cargas":
    st.header("🔝 Top 10 por Monto y Cantidad de Cargas")
    archivo = st.file_uploader("📁 Subí tu archivo de cargas recientes:", type=["xlsx", "xls", "csv"], key="top10")

    if archivo:
        df = pd.read_excel(archivo) if archivo.name.endswith((".xlsx", ".xls")) else pd.read_csv(archivo)
        df = preparar_dataframe(df)

        if df is not None:
            df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce")
            df["Monto"] = pd.to_numeric(df["Monto"], errors="coerce").fillna(0)
            df_cargas = df[df["Tipo"] == "in"]

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


# SECCIÓN 4: INACTIVOS AGENDA
elif seccion == "📅 Inactivos Agenda":
    st.header("📅 Inactivos Agenda - Comparación de Jugadores")

    # Filtrar los nombres de la Hoja 2 que coinciden con los de la Hoja 1
    nombres_hoja_1 = set(hoja_1['Nombre'])
    nombres_hoja_2 = set(hoja_2['Al usuario'])

    # Encontrar los nombres comunes
    nombres_comunes = nombres_hoja_1.intersection(nombres_hoja_2)

    # Crear la lista para la tabla final
    tabla_resultados = []

    # Iterar sobre los nombres comunes y recolectar la información
    for nombre in nombres_comunes:
        # Obtener la información de la Hoja 1
        jugador_hoja_1 = hoja_1[hoja_1['Nombre'] == nombre].iloc[0]
        fecha_ingreso = jugador_hoja_1['Fecha que ingresó']

        # Obtener la información de la Hoja 2
        jugador_hoja_2 = hoja_2[hoja_2['Al usuario'] == nombre]
        cargas = jugador_hoja_2[jugador_hoja_2['Tipo'] == 'in']
        retiros = jugador_hoja_2[jugador_hoja_2['Tipo'] == 'out']

        # Calcular la cantidad de cargas y la suma de las cargas
        veces_que_cargo = len(cargas)
        suma_de_cargas = cargas['Monto'].sum()

        # Última vez que cargó
        ultima_vez_cargo = cargas['Fecha'].max() if not cargas.empty else None

        # Calcular los días inactivos
        dias_inactivo = (datetime.datetime.now() - ultima_vez_cargo).days if ultima_vez_cargo else None

        # Agregar la información a la tabla de resultados
        tabla_resultados.append({
            'Nombre de Usuario': nombre,
            'Fecha que ingresó': fecha_ingreso,
            'Veces que cargó': veces_que_cargo,
            'Suma de las cargas': suma_de_cargas,
            'Última vez que cargó': ultima_vez_cargo,
            'Días inactivos': dias_inactivo
        })

    # Convertir la tabla a un DataFrame y mostrarla
    df_resultado = pd.DataFrame(tabla_resultados)

    # Mostrar la tabla en Streamlit
    st.dataframe(df_resultado)

    # Si quieres exportar a Excel
    df_resultado.to_excel('resultado_comparacion_inactivos.xlsx', index=False)
    with open("resultado_comparacion_inactivos.xlsx", "rb") as f:
        st.download_button("📥 Descargar Excel", f, file_name="resultado_comparacion_inactivos.xlsx")
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
