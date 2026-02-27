import streamlit as st
import sqlite3
import pandas as pd
import hashlib
import secrets
from datetime import datetime
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse
from pathlib import Path
import streamlit.components.v1 as components

# =========================
# Configuración Básica
# =========================
APP_TITLE = "Generador de IDs - Unicomer"
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = str(BASE_DIR / "links.db")

UNICOMER_LOGO = "https://grupounicomer.com/wp-content/uploads/2022/12/logo-sol-gris.png"
UNICOMER_BLUE = "#002d5a"
UNICOMER_YELLOW = "#fdbb2d"
FIGMA_URL = "https://www.figma.com/design/ihSTaMfAmyN99BN5Z6sNps/Home-ULA?node-id=0-1&t=0q58oIwyTto6wv3R-1"

# =========================
# Lógica de Datos y DB
# =========================
HOME_TYPES_INIT = [("BannerRotativo", "rtv"), ("MejoresOfertas", "topd"), ("CategoriasDestacadas", "dtd"), ("BloqueFomo", "bcr"), ("MoreDeals", "dls"), ("Carrusel1Ofertas", "bts"), ("BannerMultiuso1", "bmuno"), ("Carrusel2Ofertas", "npd"), ("BannerMultiuso2", "bmdos"), ("Carrusel3Ofertas", "cdp"), ("Carousel4Ofertas", "cci"), ("CarouselconImagen", "imb"), ("MarcasDestacadas", "mdt"), ("BloqueDeBeneficios", "icb"), ("CintilloBajoRotativo", "cbr"), ("BannerMultiuso3", "bmtres"), ("MoreDealsRotativo", "mdr"), ("CarruselConPortada", "ccp"), ("MoreDealsCarrusel", "mdc"), ("BannerMoreDealsCarrusel", "bmdc"), ("BannerDeCategoria", "bdct"), ("DobleBannerMultiuso", "dbm"), ("BannerLateral", "bnl"), ("MoreDealsde4", "mddc"), ("MoreDealsVersion2", "mdvd"), ("BannerMulticarruselCP", "bpm"), ("CategoriasDestacadasDos", "dtddos"), ("CategoriasDestacadasTres", "cdtres"), ("ProductTop", "pdtop"), ("TopCategories", "tcat"), ("FomoAdviento", "fad"), ("PopUp", "popup"), ("BannerMultiusoCP", "bmcp"), ("PopUp2", "popdos"), ("BotonLateral", "btl")]
ORDER_MAX_BY_CODE = {"rtv": 6, "topd": 1, "dtd": 1, "bcr": 4, "dls": 6, "bts": 1, "bmuno": 1, "npd": 1, "bmdos": 1, "cdp": 1, "cci": 1, "imb": 1, "mdt": 1, "icb": 1, "cbr": 1, "bmtres": 1, "mdr": 6, "ccp": 1, "mdc": 6, "bmdc": 1, "bdct": 10, "dbm": 2, "bnl": 1, "mddc": 4, "mdvd": 9, "bpm": 11, "dtddos": 3, "cdtres": 14, "pdtop": 6, "tcat": 6, "fad": 6, "popup": 1, "bmcp": 3, "popdos": 1, "btl": 1}

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
        
        cur.execute("SELECT 1 FROM users WHERE username='admin'")
        if not cur.fetchone():
            s, p = make_password_record("admin123")
            cur.execute("INSERT INTO users(username, role, salt, pwd_hash, created_at) VALUES (?,?,?,?,?)", ("admin", "admin", s, p, datetime.now().isoformat()))
        
        cur.execute("SELECT COUNT(*) FROM categories")
        if cur.fetchone()[0] == 0:
            for n, p in [("Home", "hm"), ("PLP", "plp"), ("PDP", "pdp"), ("CLP", "clp")]:
                cur.execute("INSERT INTO categories(name, prefix) VALUES (?,?)", (n, p))
        
        cur.execute("SELECT COUNT(*) FROM types")
        if cur.fetchone()[0] == 0:
            for name, code in HOME_TYPES_INIT:
                cur.execute("INSERT INTO types(name, code) VALUES (?,?)", (name, code))
                tid = cur.lastrowid
                max_n = ORDER_MAX_BY_CODE.get(code, 20)
                for n in range(1, max_n + 1):
                    cur.execute("INSERT INTO type_orders(type_id, order_no) VALUES (?,?)", (tid, n))

def get_user(username: str):
    u = username.strip().lower()
    res = df_query("SELECT id, username, role, salt, pwd_hash FROM users WHERE lower(username) = ?", (u,))
    return res.iloc[0].to_dict() if not res.empty else None

# =========================
# CSS Personalizado
# =========================
def apply_custom_styles():
    st.markdown(f"""
    <style>
        .stApp {{ background-color: #f4f7f9; }}
        .stTextInput input, .stSelectbox [data-baseweb="select"], .stSelectbox select {{
            color: #31333F !important;
            background-color: white !important;
            border-radius: 8px !important;
        }}
        div[data-baseweb="popover"], div[data-baseweb="menu"] {{
            max-height: 350px !important;
            overflow-y: auto !important;
            -webkit-overflow-scrolling: touch !important;
        }}
        [data-testid="stSidebar"] {{ background-color: {UNICOMER_BLUE}; }}
        [data-testid="stSidebar"] * {{ color: white !important; }}
        div.stButton > button {{
            background-color: {UNICOMER_YELLOW} !important;
            color: {UNICOMER_BLUE} !important;
            border: none !important;
            font-weight: bold;
            width: 100%;
            border-radius: 8px;
            height: 3em;
        }}
    </style>
    """, unsafe_allow_html=True)

# =========================
# Lógica Principal
# =========================
st.set_page_config(page_title=APP_TITLE, layout="wide")
apply_custom_styles()
init_db()

if "auth" not in st.session_state:
    st.session_state.auth = {"is_logged": False, "username": None, "role": None}

# --- LOGIN CENTRAL ---
if not st.session_state.auth["is_logged"]:
    _, center, _ = st.columns([1, 2, 1])
    with center:
        st.markdown(f"<div style='text-align:center; margin-top:50px;'><img src='{UNICOMER_LOGO}' width='200'></div>", unsafe_allow_html=True)
        st.markdown("<h2 style='text-align:center; color:#002d5a;'>Generador de IDs</h2>", unsafe_allow_html=True)
        u_input = st.text_input("Usuario", key="login_user")
        p_input = st.text_input("Contraseña", type="password", key="login_pwd")
        if st.button("ENTRAR"):
            user_data = get_user(u_input)
            if user_data and verify_password(p_input, user_data["salt"], user_data["pwd_hash"]):
                st.session_state.auth = {"is_logged": True, "username": user_data["username"], "role": user_data["role"]}
                st.rerun()
            else:
                st.error("Credenciales incorrectas")
    st.stop()

# --- APP ---
with st.sidebar:
    st.markdown(f"<div style='filter: brightness(0) invert(1); text-align:center;'><img src='{UNICOMER_LOGO}' width='120'></div>", unsafe_allow_html=True)
    st.divider()
    st.write(f"Usuario: **{st.session_state.auth['username']}**")
    if st.button("Cerrar Sesión"):
        st.session_state.auth = {"is_logged": False, "username": None, "role": None}
        st.rerun()

tabs = st.tabs(["✅ Generar Link", "🕒 Historial", "⚙️ Administración"])

# --- TAB GENERAR ---
with tabs[0]:
    _, col_main, _ = st.columns([0.05, 0.9, 0.05])
    with col_main:
        st.title(f"🔗 {APP_TITLE}")
        st.info("Ingresa la URL base y selecciona los parámetros.")
        base_url = st.text_input("URL base", placeholder="https://...")
        c1, c2, c3 = st.columns(3)
        with c1:
            country = st.selectbox("País", ["SV", "GT", "CR", "HN", "NI", "PA", "DO", "JM", "TT"])
        with c2:
            cats_df = df_query("SELECT name, prefix FROM categories")
            cat_options = [f"{r.name} ({r.prefix})" for r in cats_df.itertuples()]
            cat_sel = st.selectbox("Categoría", cat_options) if not cats_df.empty else st.selectbox("Categoría", ["N/A"])
        with c3:
            types_df = df_query("SELECT id, name, code FROM types")
            type_options = [f"{r.name} ({r.code})" for r in types_df.itertuples()]
            type_sel = st.selectbox("Tipo", type_options) if not types_df.empty else st.selectbox("Tipo", ["N/A"])

        if not types_df.empty and "(" in type_sel:
            t_code = type_sel.split("(")[1].replace(")", "")
            t_id = int(types_df[types_df['code'] == t_code]['id'].values[0])
            orders = df_query("SELECT order_no FROM type_orders WHERE type_id=? ORDER BY order_no", (t_id,))
            order_list = orders['order_no'].tolist() if not orders.empty else list(range(1, 21))
            order_val = st.selectbox("Posición", order_list)

            if st.button("GENERAR"):
                if base_url:
                    c_prefix = cat_sel.split("(")[1].replace(")", "")
                    hid = f"{c_prefix}_{t_code}_{order_val}"
                    parsed = urlparse(base_url.strip())
                    qs = dict(parse_qsl(parsed.query))
                    qs['hid'] = hid
                    final_url = urlunparse(parsed._replace(query=urlencode(qs)))
                    exec_sql("INSERT INTO history (created_at, base_url, final_url, country, type_code, order_value, hid_value) VALUES (?,?,?,?,?,?,?)",
                            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), base_url, final_url, country, t_code, str(order_val), hid))
                    st.success(f"**HID:** {hid}")
                    st.code(final_url)
                    components.html(f"<button onclick=\"navigator.clipboard.writeText('{final_url}'); alert('¡Copiado!');\" style=\"width:100%; background:{UNICOMER_YELLOW}; border:none; padding:12px; border-radius:8px; font-weight:bold; cursor:pointer;\">📋 COPIAR</button>", height=60)

# --- TAB HISTORIAL ---
with tabs[1]:
    hist = df_query("SELECT created_at as Fecha, country as Pais, hid_value as HID, final_url as URL FROM history ORDER BY id DESC LIMIT 50")
    st.dataframe(hist, use_container_width=True)

# --- TAB ADMIN (CRUD COMPLETO) ---
with tabs[2]:
    if st.session_state.auth["role"] != "admin":
        st.error("Acceso restringido.")
    else:
        st.subheader("🛠️ Panel de Control")
        
        # --- GESTIÓN DE USUARIOS ---
        with st.expander("👤 Usuarios"):
            u_list = df_query("SELECT id, username, role FROM users")
            st.table(u_list)
            with st.form("new_user"):
                new_u = st.text_input("Nuevo Usuario")
                new_p = st.text_input("Contraseña", type="password")
                new_r = st.selectbox("Rol", ["user", "admin"])
                if st.form_submit_button("Añadir Usuario"):
                    s, p = make_password_record(new_p)
                    exec_sql("INSERT INTO users(username, role, salt, pwd_hash, created_at) VALUES (?,?,?,?,?)",
                            (new_u, new_r, s, p, datetime.now().isoformat()))
                    st.success("Usuario creado.")
                    st.rerun()

        # --- GESTIÓN DE CATEGORÍAS ---
        with st.expander("📁 Categorías (Home, PLP, etc.)"):
            c_list = df_query("SELECT * FROM categories")
            st.dataframe(c_list, use_container_width=True)
            with st.form("new_cat"):
                cn = st.text_input("Nombre (ej: Checkout)")
                cp = st.text_input("Prefijo (ej: chk)")
                if st.form_submit_button("Añadir Categoría"):
                    exec_sql("INSERT INTO categories(name, prefix) VALUES (?,?)", (cn, cp))
                    st.rerun()
            del_cat = st.selectbox("Eliminar Categoría", c_list['name'].tolist() if not c_list.empty else [])
            if st.button("Eliminar Seleccionada"):
                exec_sql("DELETE FROM categories WHERE name=?", (del_cat,))
                st.rerun()

        # --- GESTIÓN DE TIPOS ---
        with st.expander("🧩 Tipos de Componentes"):
            t_list = df_query("SELECT * FROM types")
            st.dataframe(t_list, use_container_width=True)
            with st.form("new_type"):
                tn = st.text_input("Nombre Componente")
                tc = st.text_input("Código (ej: bnr)")
                tm = st.number_input("Máximo de posiciones", min_value=1, value=10)
                if st.form_submit_button("Añadir Tipo"):
                    exec_sql("INSERT INTO types(name, code) VALUES (?,?)", (tn, tc))
                    res = df_query("SELECT id FROM types WHERE code=?", (tc,))
                    new_id = int(res.iloc[0]['id'])
                    for i in range(1, tm + 1):
                        exec_sql("INSERT INTO type_orders(type_id, order_no) VALUES (?,?)", (new_id, i))
                    st.rerun()
