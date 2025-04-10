
import streamlit as st
import pandas as pd
import datetime

st.set_page_config(page_title="📢 Reactivación Personalizada", layout="wide")

st.title("📉 Jugadores Inactivos con Mensajes de Reactivación")

archivo = st.file_uploader("📁 Subí tu archivo de historial de cargas (Excel o CSV):", type=["xlsx", "xls", "csv"])

hoy = pd.to_datetime(datetime.date.today())

if archivo:
    if archivo.name.endswith(".csv"):
        df = pd.read_csv(archivo)
    else:
        df = pd.read_excel(archivo)

    # Renombrar columnas
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

    df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce")
    df = df[df["Tipo"] == "in"]

    # Obtener última carga por jugador
    ultima_carga = df.groupby("Jugador")["Fecha"].max().reset_index()
    ultima_carga["Dias_inactivo"] = (hoy - ultima_carga["Fecha"]).dt.days

    # Campaña y mensaje personalizado
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

    resultado = ultima_carga.copy()
    resultado[["Campaña sugerida", "Mensaje personalizado"]] = resultado.apply(
        lambda row: pd.Series(campaña_y_mensaje(row["Jugador"], row["Dias_inactivo"])), axis=1
    )

    resultado = resultado[resultado["Campaña sugerida"] != ""].sort_values(by="Dias_inactivo", ascending=False)

    st.subheader("📋 Jugadores segmentados + mensajes personalizados")
    st.dataframe(resultado)

    resultado.to_excel("jugadores_mensajes_reactivacion.xlsx", index=False)
    with open("jugadores_mensajes_reactivacion.xlsx", "rb") as f:
        st.download_button("📥 Descargar Excel con mensajes", f, file_name="jugadores_mensajes_reactivacion.xlsx")
