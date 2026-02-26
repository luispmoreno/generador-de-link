import streamlit as st

# 1. Configuración de página (Opcional: puedes usar "centered" o "wide")
st.set_page_config(page_title="Link Builder", layout="wide")

# 2. CSS para mejorar la estética en ambos dispositivos
st.markdown("""
    <style>
    /* Eliminar espacio superior innecesario */
    .block-container {
        padding-top: 2rem;
    }
    /* Estilo para el botón 'Entrar' */
    div.stButton > button:first-child {
        background-color: #FFC107;
        color: black;
        border: none;
        padding: 0.5rem 2rem;
        font-weight: bold;
    }
    </style>
    """, unsafe_allow_html=True)

# 3. CREAR COLUMNAS PARA EL RESPONSIVE
# En Desktop: Crea 3 columnas. La del centro (ratio 2) contiene el app.
# En Mobile: Streamlit apila las columnas, pero podemos forzar que se vea bien.
col1, col2, col3 = st.columns([1, 2, 1])

with col2:
    # Encabezado con Logo y Título
    st.image("tu_logo.png", width=100) # Cambia por tu ruta de imagen
    st.title("Link Builder")
    
    st.write("---")
    
    # Sección de Acceso
    st.subheader("🔐 Acceso")
    
    with st.container():
        usuario = st.text_input("Usuario")
        contrasena = st.text_input("Contraseña", type="password")
        
        # El botón se ajustará al ancho de la columna
        if st.button("Entrar"):
            st.success("Validando credenciales...")
