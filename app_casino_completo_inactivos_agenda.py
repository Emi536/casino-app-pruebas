
import streamlit as st
import pandas as pd
import datetime

st.set_page_config(page_title="App de Cargas - Casino", layout="wide")
st.title("🎰 App de Análisis de Cargas del Casino")

seccion = st.sidebar.radio("Seleccioná una sección:", ["🔝 Top 10 de Cargas", "📉 Jugadores Inactivos", "📋 Registro", "🗓️ Inactivos Agenda"])

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

# NUEVA SECCIÓN: INACTIVOS AGENDA
def inactivos_agenda():
    hoja1 = pd.read_excel('pruebainactivos.xlsx', sheet_name='Hoja 1')
    hoja2 = pd.read_excel('pruebainactivos.xlsx', sheet_name='Hoja 2')
    hoja1['Nombre'] = hoja1['Nombre'].str.strip()
    hoja2['Al usuario'] = hoja2['Al usuario'].str.strip()
    
    nombres_coincidentes = hoja1[hoja1['Nombre'].isin(hoja2['Al usuario'])]
    resumen = []
    hoy = pd.to_datetime(datetime.date.today())

    for index, row in nombres_coincidentes.iterrows():
        jugador = row['Nombre']
        historial = hoja2[hoja2["Al usuario"] == jugador].sort_values("Fecha")
        cargas = historial[historial["Tipo"] == "in"]
        retiros = historial[historial["Tipo"] == "out"]

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
                "Días inactivo": dias_inactivo
            })

    df_resultado = pd.DataFrame(resumen)
    return df_resultado

def inactivos_agenda_streamlit():
    st.header("📋 Inactivos Agenda")
    df_resultado = inactivos_agenda()

    if df_resultado.empty:
        st.write("No se encontraron jugadores con coincidencias.")
    else:
        st.dataframe(df_resultado)
        df_resultado.to_excel("inactivos_agenda_resultados.xlsx", index=False)
        with open("inactivos_agenda_resultados.xlsx", "rb") as f:
            st.download_button("📥 Descargar Resultados", f, file_name="inactivos_agenda_resultados.xlsx")

# LLAMADA A CADA SECCIÓN
if seccion == "🗓️ Inactivos Agenda":
    inactivos_agenda_streamlit()
