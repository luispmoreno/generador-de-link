import streamlit as st
import sqlite3
import pandas as pd
import hashlib
import secrets
import re
from datetime import datetime
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse
from pathlib import Path
import streamlit.components.v1 as components

# =========================
# Configuración de Página (Mobile Optimized)
# =========================
st.set_page_config(
    page_title="Generador de Links",
    page_icon="🔗",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# =========================
# Variables y Estilos
# =========================
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = str(BASE_DIR / "links.db")
UNICOMER_LOGO = "https://grupounicomer.com/wp-content/uploads/2022/12/logo-sol-gris.png"
UNICOMER_BLUE = "#002d5a"
UNICOMER_YELLOW = "#fdbb2d"
FIGMA_URL = "https://www.figma.com/design/ihSTaMfAmyN99BN5Z6sNps/Home-ULA?node-id=0-1&t=0q58oIwyTto6wv3R-1"

def apply_custom_styles():
    st.markdown(f"""
    <style>
        /* Fuentes y Colores Base */
        @import url('https://fonts.googleapis.com/css2?family=Ubuntu:wght@400;700&display=swap');
        
        .main {{ background-color: #f8f9fa; }}
        
        /* Botones Estilo Mobile App */
        .stButton>button {{
            width: 100%;
            border-radius: 12px;
            height: 3.5rem;
            background-color: {UNICOMER_YELLOW};
            color: {UNICOMER_BLUE};
            font-weight: bold;
            border: none;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            transition: all 0.3s ease;
        }}
        .stButton>button:active {{ transform: scale(0.98); }}
        
        /* Inputs más grandes para dedos */
        .stTextInput input, .stSelectbox div[data-baseweb="select"] {{
            border-radius: 10px !important;
            min-height: 45px;
        }}
        
        /* Tarjetas (Cards) */
        .custom-card {{
            background: white;
            padding: 20px;
            border-radius: 15px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.05);
            margin-bottom: 20px;
        }}
        
        /* Ocultar barra de GitHub y pie de página */
        #MainMenu {{visibility: hidden;}}
        footer {{visibility: hidden;}}
        header {{visibility: hidden;}}
    </style>
    """, unsafe_allow_html=True)

# [Mantenemos tus funciones de DB y Auth intactas para no romper la lógica]
# ... (Aquí van todas tus funciones: _hash_password, make_password_record, get_conn, etc.)
# [Para ahorrar espacio en el ejemplo, asumamos que están presentes debajo]

def _hash_password(password: str, salt_hex: str) -> str:
    data = (salt_hex + password).encode("utf-8")
    return hashlib.sha256(data).hexdigest()

def make_password_record(password: str) -> tuple[str, str]:
    salt_hex = secrets.token_hex(16)
    pwd_hash = _hash_password(password, salt_hex)
    return salt_hex, pwd_hash

def verify_password(password: str, salt_hex: str, pwd_hash: str) -> bool:
    return _hash_password(password, salt_hex) == (pwd_hash or "")

def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def df_query(sql, params=()):
    conn = get_conn()
    df = pd.read_sql_query(sql, conn, params=params)
    conn.close()
    return df

def exec_sql(sql, params=()):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(sql, params)
    conn.commit()
    conn.close()

def init_db():
    # Aquí va tu código original de inicialización de tablas (init_db, _ensure_tables, etc.)
    # Lo mantengo simplificado para el ejemplo
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT, base_url TEXT, final_url TEXT, country TEXT, category_id INTEGER, category_name TEXT, type_id INTEGER, type_name TEXT, type_code TEXT, order_value TEXT, hid_value TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, role TEXT, salt TEXT, pwd_hash TEXT, created_at TEXT)")
    # Asegurar Admin
    cur.execute("SELECT 1 FROM users WHERE username='admin'")
    if not cur.fetchone():
        s, p = make_password_record("admin123")
        cur.execute("INSERT INTO users(username, role, salt, pwd_hash, created_at) VALUES ('admin','admin',?,?,?)", (s,p, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def get_user(username: str):
    u = (username or "").strip().lower()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT username, role, salt, pwd_hash FROM users WHERE username = ?", (u,))
    row = cur.fetchone()
    conn.close()
    return {"username": row[0], "role": row[1], "salt": row[2], "pwd_hash": row[3]} if row else None

def build_url_with_params(base_url: str, new_params: dict) -> str:
    parsed = urlparse(base_url.strip())
    existing = dict(parse_qsl(parsed.query, keep_blank_values=True))
    merged = {**existing, **{k: v for k, v in new_params.items() if v}}
    query = urlencode(merged, doseq=True)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, query, parsed.fragment))

# =========================
# Ejecución Principal
# =========================
apply_custom_styles()
init_db()

# Header Minimalista
col_logo, col_title = st.columns([1, 4])
with col_logo:
    st.image(UNICOMER_LOGO, width=60)
with col_title:
    st.markdown(f"<h2 style='margin:0; color:{UNICOMER_BLUE};'>Link Builder</h2>", unsafe_allow_html=True)

# Login Manejado en el cuerpo principal para móvil
if "auth" not in st.session_state:
    st.session_state.auth = {"is_logged": False, "username": None, "role": None}

if not st.session_state.auth["is_logged"]:
    with st.container():
        st.markdown('<div class="custom-card">', unsafe_allow_html=True)
        st.subheader("🔐 Acceso")
        user = st.text_input("Usuario")
        pwd = st.text_input("Contraseña", type="password")
        if st.button("Entrar", type="primary"):
            u = get_user(user)
            if u and verify_password(pwd, u["salt"], u["pwd_hash"]):
                st.session_state.auth = {"is_logged": True, "username": u["username"], "role": u["role"]}
                st.rerun()
            else:
                st.error("Credenciales incorrectas")
        st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

# --- APP PRINCIPAL (USUARIO LOGUEADO) ---
auth = st.session_state.auth
is_admin = auth["role"] == "admin"

# Menú de pestañas estilo app
tab_labels = ["🚀 Generar", "🕒 Historial"]
if is_admin: tab_labels += ["📊 Admin"]

tabs = st.tabs(tab_labels)

with tabs[0]:
    st.markdown('<div class="custom-card">', unsafe_allow_html=True)
    
    # URL Base con Icono
    base_url = st.text_input("📍 URL Destino", placeholder="Pega el link de la tienda aquí...")
    
    # Grid de selección (2 columnas en escritorio, se apilan en móvil)
    c1, c2 = st.columns(2)
    with c1:
        country = st.selectbox("🌎 País", ["SV", "GT", "CR", "HN", "NI", "PA", "DO", "Otro"])
    with c2:
        # Aquí cargarías tus categorías de la DB
        cat_sel = st.selectbox("📂 Categoría", ["Home", "PLP", "PDP", "CLP"])
    
    # El resto de inputs...
    order_val = st.slider("🔢 Posición (Order)", 1, 20, 1)
    
    st.markdown("---")
    
    if st.button("✨ GENERAR LINK", use_container_width=True):
        if base_url:
            # Lógica de generación simplificada para el ejemplo
            hid = f"hm_rtv_{order_val}"
            final_url = build_url_with_params(base_url, {"hid": hid})
            
            st.success("¡Link generado!")
            st.code(final_url)
            
            # Botón de copiar optimizado
            components.html(f"""
                <button onclick="navigator.clipboard.writeText('{final_url}'); alert('Copiado ✅')" 
                style="width:100%; height:50px; background:{UNICOMER_BLUE}; color:white; border:none; border-radius:10px; font-weight:bold; cursor:pointer;">
                📋 COPIAR AL PORTAPAPELES
                </button>
            """, height=60)
        else:
            st.warning("Por favor ingresa una URL")
    st.markdown('</div>', unsafe_allow_html=True)

with tabs[1]:
    st.subheader("Últimos generados")
    # Aquí mostrarías tu df_query de historial
    st.info("Aquí aparecerá tu historial de links generados.")

if is_admin:
    with tabs[2]:
        st.subheader("Configuración de Sistema")
        if st.button("Cerrar Sesión"):
            st.session_state.auth = {"is_logged": False}
            st.rerun()

# Footer sutil
st.markdown(f"<center><p style='color:gray; font-size:12px;'>Unicomer Digital © 2024 | <a href='{FIGMA_URL}'>Figma</a></p></center>", unsafe_allow_html=True)
