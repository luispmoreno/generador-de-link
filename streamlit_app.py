import streamlit as st
import os

# 1. Configuración de página
st.set_page_config(page_title="Generador de IDs", layout="wide")

# 2. CSS personalizado para estilo Unicomer y Responsive
st.markdown("""
    <style>
    .block-container { padding-top: 2rem; }
    /* Botón amarillo Unicomer */
    div.stButton > button:first-child {
        background-color: #FFC107;
        color: black;
        border: none;
        padding: 0.6rem 2.5rem;
        font-weight: bold;
        border-radius: 8px;
        width: 100%;
    }
    /* Estilo para el título */
    .main-title {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1E1E1E;
        margin-bottom: 0;
    }
    </style>
    """, unsafe_allow_html=True)

# 3. Lógica de Sesión (Para que al dar 'Entrar' cambie la pantalla)
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

# --- PANTALLA DE LOGIN ---
if not st.session_state['logged_in']:
    col1, col2, col3 = st.columns([1, 1.2, 1])

    with col2:
        # Logo de Unicomer (Enlace directo y estable)
        st.image("https://www.unicomer.com/wp-content/uploads/2020/02/Logo-Unicomer.png", width=180)
        
        st.markdown('<p class="main-title">Generador de IDs</p>', unsafe_allow_html=True)
        st.write("---")
        
        st.subheader("🔐 Acceso al Sistema")
        
        usuario = st.text_input("Usuario", placeholder="ej: luis_pena")
        contrasena = st.text_input("Contraseña", type="password")
        
        st.write("") # Espaciado
        
        if st.button("Entrar"):
            if usuario == "admin" and contrasena == "admin": # Cambia esto por tu lógica real
                st.session_state['logged_in'] = True
                st.rerun()
            elif usuario and contrasena:
                # Simulación de validación exitosa para que no se quede trabado
                st.success("¡Bienvenido!")
                st.session_state['logged_in'] = True
                st.rerun()
            else:
                st.error("Por favor, ingresa credenciales válidas")

# --- PANTALLA PRINCIPAL (Después de loguearse) ---
else:
    col1, col2, col3 = st.columns([0.5, 3, 0.5])
    with col2:
        st.image("https://www.unicomer.com/wp-content/uploads/2020/02/Logo-Unicomer.png", width=100)
        st.title("Generador de IDs")
        st.info("Sesión iniciada correctamente. Aquí puedes colocar tu lógica de generación de IDs.")
        
        if st.button("Cerrar Sesión"):
            st.session_state['logged_in'] = False
            st.rerun()
