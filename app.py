
import streamlit as st

# Estado inicial
if "acceso_valido" not in st.session_state:
    st.session_state.acceso_valido = False

# Solo mostrar el input si no tiene acceso
if not st.session_state.acceso_valido:
    password = st.text_input("🔑 Ingresá la contraseña para acceder:", type="password")
    if password == "casino123":
        st.session_state.acceso_valido = True
        st.success("✅ Acceso concedido")
    else:
        if password != "":
            st.warning("❌ Contraseña incorrecta")
        st.stop()

# Contenido principal
st.title("🎰 Reporte del Casino")
st.write("Bienvenido, accediste correctamente.")
