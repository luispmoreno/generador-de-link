import streamlit as st
import sqlite3
import pandas as pd
import hashlib
import secrets
from datetime import datetime
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse
from pathlib import Path
import streamlit.components.v1 as components
import io

# =========================
# Configuración Básica
# =========================
APP_TITLE = "Generador de IDs - Unicomer"
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = str(BASE_DIR / "links.db")

# Recursos de Marca
UNICOMER_LOGO = "https://grupounicomer.com/wp-content/uploads/2022/12/logo-sol-gris.png"
UNICOMER_BLUE = "#002d5a"
UNICOMER_YELLOW = "#fdbb2d"
FIGMA_HOME_URL = "https://www.figma.com/design/ihSTaMfAmyN99BN5Z6sNps/Home-ULA?node-id=0-1&p=f"

# =========================
# Lógica de Datos y Seguridad
# =========================
def _hash_password(password: str, salt_hex: str) -> str:
    data = (salt_hex + password).encode("utf-8")
    return hashlib.sha256(data).hexdigest()

def verify_password(password: str, salt_hex: str, pwd_hash: str) -> bool:
    return _hash_password(password, salt_hex) == (pwd_hash or "")

def make_password_record(password: str) -> tuple[str, str]:
    salt_hex = secrets.token_hex(16)
    pwd_hash = _hash_password(password, salt_hex)
    return salt_hex, pwd_hash

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)

def df_query(sql, params=()):
    with get_conn() as conn:
        return pd.read_sql_query(sql, conn, params=params)

def exec_sql(sql, params=()):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(sql, params)
        conn.commit()

def init_db():
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, role TEXT, salt TEXT, pwd_hash TEXT, created_at TEXT);")
        cur.execute("CREATE TABLE IF NOT EXISTS categories (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, prefix TEXT);")
        cur.execute("CREATE TABLE IF NOT EXISTS types (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, code TEXT);")
        cur.execute("CREATE TABLE IF NOT EXISTS type_orders (id INTEGER PRIMARY KEY AUTOINCREMENT, type_id INTEGER, order_no INTEGER);")
        cur.execute("CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT, base_url TEXT, final_url TEXT, country TEXT, type_code TEXT, order_value TEXT, hid_value TEXT);")
        
        # Admin por defecto
        cur.execute("SELECT 1 FROM users WHERE username='admin'")
        if not cur.fetchone():
            s, p = make_password_record("admin123")
            cur.execute("INSERT INTO users(username, role, salt, pwd_hash, created_at) VALUES (?,?,?,?,?)", ("admin", "admin", s, p, datetime.now().isoformat()))
        
        # NUEVO ADMIN SOLICITADO (Con chequeo para evitar IntegrityError)
        cur.execute("SELECT 1 FROM users WHERE username='ula_corp_design'")
        if not cur.fetchone():
            s, p = make_password_record("Dcorp$26")
            cur.execute("INSERT INTO users(username, role, salt, pwd_hash, created_at) VALUES (?,?,?,?,?)", ("ula_corp_design", "admin", s, p, datetime.now().isoformat()))

        # Otros usuarios estándar
        usuarios_staff = [
            ("ula_sv_unicomer", "SvLink$6Mc"), ("ula_cr_unicomer", "CrTrackQSjs"),
            ("ula_ec_unicomer", "EcHome!Cbb"), ("ula_gt_unicomer", "GtData$5Cg"),
            ("ula_hn_unicomer", "HnFlow%8Slp"), ("ula_ni_unicomer", "NiCode&3Ngt")
        ]
        for user, pwd in usuarios_staff:
            cur.execute("SELECT 1 FROM users WHERE username=?", (user,))
            if not cur.fetchone():
                s, p = make_password_record(pwd)
                cur.execute("INSERT INTO users(username, role, salt, pwd_hash, created_at) VALUES (?,?,?,?,?)", (user, "user", s, p, datetime.now().isoformat()))

def get_user(username: str):
    u = username.strip().lower()
    res = df_query("SELECT id, username, role, salt, pwd_hash FROM users WHERE lower(username) = ?", (u,))
    return res.iloc[0].to_dict() if not res.empty else None

# =========================
# CSS Adaptativo (Dark/Light)
# =========================
st.set_page_config(page_title=APP_TITLE, layout="wide")

st.markdown(f"""
<style>
    /* El fondo y texto principal se adaptan solos con el tema de Streamlit */
    
    /* Sidebar siempre Unicomer Blue */
    [data-testid="stSidebar"] {{
        background-color: {UNICOMER_BLUE} !important;
    }}
    [data-testid="stSidebar"] * {{
        color: white !important;
    }}
    
    /* Botones Amarillos Unicomer */
    div.stButton > button {{
        background-color: {UNICOMER_YELLOW} !important;
        color: {UNICOMER_BLUE} !important;
        border: none !important;
        font-weight: bold;
        border-radius: 8px;
    }}

    /* Recuadro Adaptativo para el botón Figma */
    .figma-box {{
        padding: 20px;
        border-radius: 12px;
        border: 2px solid #ff4b4b;
        background-color: rgba(255, 75, 75, 0.05);
        text-align: center;
        margin-bottom: 25px;
    }}
    
    /* Logo adaptativo */
    .brand-logo {{
        filter: drop-shadow(0px 0px 2px rgba(255,255,255,0.3));
    }}
</style>
""", unsafe_allow_html=True)

init_db()

if "auth" not in st.session_state:
    st.session_state.auth = {"is_logged": False, "username": None, "role": None}

# --- LOGIN ---
if not st.session_state.auth["is_logged"]:
    _, center, _ = st.columns([1, 2, 1])
    with center:
        st.markdown(f"<div style='text-align:center; margin-top:50px;'><img src='{UNICOMER_LOGO}' width='200' class='brand-logo'></div>", unsafe_allow_html=True)
        st.markdown("<h2 style='text-align:center;'>Acceso Unicomer</h2>", unsafe_allow_html=True)
        u_input = st.text_input("Usuario")
        p_input = st.text_input("Contraseña", type="password")
        if st.button("ENTRAR"):
            user_data = get_user(u_input)
            if user_data and verify_password(p_input, user_data["salt"], user_data["pwd_hash"]):
                st.session_state.auth = {"is_logged": True, "username": user_data["username"], "role": user_data["role"]}
                st.rerun()
            else:
                st.error("Credenciales incorrectas")
    st.stop()

# --- SIDEBAR ---
with st.sidebar:
    st.image(UNICOMER_LOGO, width=120)
    st.divider()
    st.write(f"Sesión activa: **{st.session_state.auth['username']}**")
    if st.button("Cerrar Sesión"):
        st.session_state.auth = {"is_logged": False, "username": None, "role": None}
        st.rerun()

# Logo en cabecera principal
st.markdown(f"<div style='text-align:right;'><img src='{UNICOMER_LOGO}' width='150' class='brand-logo'></div>", unsafe_allow_html=True)

tabs = st.tabs(["✅ Generador", "🕒 Historial", "⚙️ Administración"])

# --- TAB GENERADOR ---
with tabs[0]:
    # Layout para el título y el botón de Figma
    col_title, col_figma = st.columns([2, 1])
    
    with col_title:
        st.title("🔗 Generador de Links")
        base_url = st.text_input("URL base del sitio", placeholder="https://...")

    with col_figma:
        # RECUADRO PARA FIGMA
        st.markdown(f"""
            <div class="figma-box">
                <p style="font-weight: bold; margin-bottom: 10px;">Guía de Versiones Home</p>
                <a href="{FIGMA_HOME_URL}" target="_blank" style="text-decoration: none;">
                    <button style="width: 100%; background-color: #A259FF; color: white; border: none; padding: 12px; border-radius: 8px; font-weight: bold; cursor: pointer;">
                        🎨 VER MAPA EN FIGMA
                    </button>
                </a>
                <p style="font-size: 0.85em; margin-top: 10px; opacity: 0.8;">Consulta bloques y posiciones disponibles aquí.</p>
            </div>
        """, unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    with c1:
        country = st.selectbox("País", ["SV", "GT", "CR", "HN", "NI", "PA", "DO", "JM", "TT"])
    with c2:
        cats_df = df_query("SELECT name, prefix FROM categories")
        cat_sel = st.selectbox("Categoría de Ubicación", [f"{r.name} ({r.prefix})" for r in cats_df.itertuples()]) if not cats_df.empty else "N/A"
    with c3:
        types_df = df_query("SELECT id, name, code FROM types")
        type_sel = st.selectbox("Tipo de Componente", [f"{r.name} ({r.code})" for r in types_df.itertuples()]) if not types_df.empty else "N/A"

    if "(" in str(type_sel):
        t_code = type_sel.split("(")[1].replace(")", "")
        t_id = int(types_df[types_df['code'] == t_code]['id'].values[0])
        orders = df_query("SELECT order_no FROM type_orders WHERE type_id=? ORDER BY order_no", (t_id,))
        pos_val = st.selectbox("Posición (Orden)", orders['order_no'].tolist() if not orders.empty else [1])

        if st.button("GENERAR ID Y LINK"):
            if base_url:
                c_pref = cat_sel.split("(")[1].replace(")", "")
                hid = f"{c_pref}_{t_code}_{pos_val}"
                parsed = urlparse(base_url.strip())
                qs = dict(parse_qsl(parsed.query))
                qs['hid'] = hid
                final_url = urlunparse(parsed._replace(query=urlencode(qs)))
                
                # Guardar en historial
                exec_sql("INSERT INTO history (created_at, base_url, final_url, country, type_code, order_value, hid_value) VALUES (?,?,?,?,?,?,?)",
                        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), base_url, final_url, country, t_code, str(pos_val), hid))
                
                st.success(f"**ID:** {hid}")
                st.code(final_url)
                components.html(f"<button onclick=\"navigator.clipboard.writeText('{final_url}'); alert('Copiado');\" style=\"width:100%; background:{UNICOMER_YELLOW}; border:none; padding:12px; border-radius:8px; font-weight:bold; cursor:pointer;\">📋 COPIAR LINK</button>", height=60)

# --- TAB HISTORIAL ---
with tabs[1]:
    st.subheader("Historial")
    hist_data = df_query("SELECT created_at as Fecha, country as Pais, hid_value as HID, final_url as URL FROM history ORDER BY id DESC")
    if not hist_data.empty:
        # Botón Excel seguro
        try:
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine='xlsxwriter') as wr:
                hist_data.to_excel(wr, index=False, sheet_name='Historial')
            st.download_button("📥 Descargar Excel", buf.getvalue(), f"reporte_{datetime.now().strftime('%Y%m%d')}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        except:
            st.warning("Habilita xlsxwriter en requirements.txt")
        st.dataframe(hist_data, use_container_width=True)

# --- TAB ADMIN ---
with tabs[2]:
    if st.session_state.auth["role"] != "admin":
        st.error("Acceso restringido a administradores.")
    else:
        st.header("⚙️ Configuración del Sistema")
        # Aquí van los CRUDs de usuarios, categorías y tipos solicitados anteriormente
        st.info(f"Bienvenido {st.session_state.auth['username']}. Aquí puedes gestionar el catálogo.")
