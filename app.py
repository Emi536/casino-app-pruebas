
import streamlit as st

# Login con contraseña
if "acceso_valido" not in st.session_state:
    st.session_state.acceso_valido = False

if not st.session_state.acceso_valido:
    password = st.text_input("🔑 Ingresá la contraseña para acceder:", type="password")
    if password == "casino123":
        st.session_state.acceso_valido = True
        st.experimental_rerun()
    elif password != "":
        st.warning("❌ Contraseña incorrecta")
    st.stop()

# Contenido principal
st.title("🎰 Reporte del Casino")
st.write("Bienvenido, accediste correctamente.")
