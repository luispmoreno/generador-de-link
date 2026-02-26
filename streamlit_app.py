import streamlit as st

# 1. Configuración de página para que use todo el ancho disponible
st.set_page_config(page_title="Link Builder", layout="wide")

# 2. CSS para mejorar la estética y el centrado
st.markdown("""
    <style>
    /* Ajustar el padding superior */
    .block-container {
        padding-top: 2rem;
    }
    /* Estilo para el botón 'Entrar' (Amarillo Unicomer) */
    div.stButton > button:first-child {
        background-color: #FFC107;
        color: black;
        border: none;
        padding: 0.5rem 2rem;
        font-weight: bold;
        border-radius: 5px;
    }
    /* Asegurar que la imagen no se desborde en móvil */
    img {
        max-width: 100%;
    }
    </style>
    """, unsafe_allow_html=True)

# 3. Estructura de columnas para centrar el contenido en Desktop
# El ratio [1, 1.2, 1] asegura que el centro no sea demasiado ancho en pantallas grandes
col1, col2, col3 = st.columns([1, 1.2, 1])

with col2:
    # Encabezado con Logo de Unicomer desde URL para evitar errores de archivo
    logo_url = "https://upload.wikimedia.org/wikipedia/commons/thumb/6/63/Grupo_Unicomer_Logo.png/640px-Grupo_Unicomer_Logo.png"
    
    # Usamos columnas internas para alinear logo y título horizontalmente
    inner_col1, inner_col2 = st.columns([1, 4])
    with inner_col1:
        st.image(logo_url, width=80)
    with inner_col2:
        st.title("Link Builder")
    
    st.write("---")
    
    # Sección de Acceso
    st.subheader("🔐 Acceso")
    
    with st.container():
        usuario = st.text_input("Usuario", placeholder="Ingresa tu usuario")
        contrasena = st.text_input("Contraseña", type="password", placeholder="••••••••")
        
        # Espacio estético
        st.write("")
        
        if st.button("Entrar"):
            if usuario and contrasena:
                st.success("Validando credenciales...")
            else:
                st.error("Por favor, completa todos los campos.")
