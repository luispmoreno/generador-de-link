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
# Config
# =========================
APP_TITLE = "Generador de IDs"
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = str(BASE_DIR / "links.db")

UNICOMER_LOGO = "https://grupounicomer.com/wp-content/uploads/2022/12/logo-sol-gris.png"
UNICOMER_BLUE = "#002d5a"
UNICOMER_YELLOW = "#fdbb2d"
FIGMA_URL = "https://www.figma.com/design/ihSTaMfAmyN99BN5Z6sNps/Home-ULA?node-id=0-1&t=0q58oIwyTto6wv3R-1"

# =========================
# Lógica de Datos
# =========================
HOME_TYPES = [("BannerRotativo", "rtv"), ("MejoresOfertas", "topd"), ("CategoriasDestacadas", "dtd"), ("BloqueFomo", "bcr"), ("MoreDeals", "dls"), ("Carrusel1Ofertas", "bts"), ("BannerMultiuso1", "bmuno"), ("Carrusel2Ofertas", "npd"), ("BannerMultiuso2", "bmdos"), ("Carrusel3Ofertas", "cdp"), ("Carousel4Ofertas", "cci"), ("CarouselconImagen", "imb"), ("MarcasDestacadas", "mdt"), ("BloqueDeBeneficios", "icb"), ("CintilloBajoRotativo", "cbr"), ("BannerMultiuso3", "bmtres"), ("MoreDealsRotativo", "mdr"), ("CarruselConPortada", "ccp"), ("MoreDealsCarrusel", "mdc"), ("BannerMoreDealsCarrusel", "bmdc"), ("BannerDeCategoria", "bdct"), ("DobleBannerMultiuso", "dbm"), ("BannerLateral", "bnl"), ("MoreDealsde4", "mddc"), ("MoreDealsVersion2", "mdvd"), ("BannerMulticarruselCP", "bpm"), ("CategoriasDestacadasDos", "dtddos"), ("CategoriasDestacadasTres", "cdtres"), ("ProductTop", "pdtop"), ("TopCategories", "tcat"), ("FomoAdviento", "fad"), ("PopUp", "popup"), ("BannerMultiusoCP", "bmcp"), ("PopUp2", "popdos"), ("BotonLateral", "btl")]
ORDER_MAX_BY_CODE = {"rtv": 6, "topd": 1, "dtd": 1, "bcr": 4, "dls": 6, "bts": 1, "bmuno": 1, "npd": 1, "bmdos": 1, "cdp": 1, "cci": 1, "imb": 1, "mdt": 1, "icb": 1, "cbr": 1, "bmtres": 1, "mdr": 6, "ccp": 1, "mdc": 6, "bmdc": 1, "bdct": 10, "dbm": 2, "bnl": 1, "mddc": 4, "mdvd": 9, "bpm": 11, "dtddos": 3, "cdtres": 14, "pdtop": 6, "tcat": 6, "fad": 6, "popup": 1, "bmcp": 3, "popdos": 1, "btl": 1}
DEFAULT_ORDER_RANGE = list(range(1, 21))

# Funciones de Soporte
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

def _table_exists(cur, name: str) -> bool:
    cur.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,))
    return cur.fetchone() is not None

def _get_cols(cur, table: str) -> list[str]:
    cur.execute(f"PRAGMA table_info({table})")
    return [r[1] for r in cur.fetchall()]

def _ensure_users_schema(cur):
    if not _table_exists(cur, "users"):
        cur.execute("""CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL UNIQUE, role TEXT NOT NULL DEFAULT 'user', salt TEXT, pwd_hash TEXT, created_at TEXT NOT NULL);""")
        return
    cols = set(_get_cols(cur, "users"))
    if "role" not in cols: cur.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user'")
    if "salt" not in cols: cur.execute("ALTER TABLE users ADD COLUMN salt TEXT")
    if "pwd_hash" not in cols: cur.execute("ALTER TABLE users ADD COLUMN pwd_hash TEXT")
    if "created_at" not in cols: cur.execute("ALTER TABLE users ADD COLUMN created_at TEXT NOT NULL DEFAULT ''")

def _ensure_tables(conn):
    cur = conn.cursor()
    _ensure_users_schema(cur)
    cur.execute("CREATE TABLE IF NOT EXISTS categories (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, prefix TEXT NOT NULL);")
    cur.execute("CREATE TABLE IF NOT EXISTS types (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, code TEXT NOT NULL);")
    cur.execute("CREATE TABLE IF NOT EXISTS type_orders (id INTEGER PRIMARY KEY AUTOINCREMENT, type_id INTEGER NOT NULL, order_no INTEGER NOT NULL, UNIQUE(type_id, order_no));")
    cur.execute("CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL, base_url TEXT NOT NULL, final_url TEXT NOT NULL, country TEXT, category_id INTEGER, category_name TEXT, type_id INTEGER, type_name TEXT, type_code TEXT, order_value TEXT, hid_value TEXT);")
    cols_hist = set(_get_cols(cur, "history"))
    if "country" not in cols_hist: cur.execute("ALTER TABLE history ADD COLUMN country TEXT")
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_categories_name ON categories(name)")
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_types_code ON types(code)")
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_users_username ON users(username)")
    conn.commit()

def _upsert_category(conn, name: str, prefix: str):
    cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO categories(name, prefix) VALUES (?,?)", (name, prefix))

def _upsert_type(conn, name: str, code: str):
    cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO types(name, code) VALUES (?,?)", (name, code))

def _ensure_orders_for_code(conn, code: str):
    cur = conn.cursor()
    cur.execute("SELECT id FROM types WHERE code=?", (code,))
    row = cur.fetchone()
    if not row: return
    tid = row[0]
    cur.execute("SELECT COUNT(*) FROM type_orders WHERE type_id=?", (tid,))
    if cur.fetchone()[0] > 0: return
    max_n = ORDER_MAX_BY_CODE.get(code, 20)
    for n in range(1, max_n + 1):
        cur.execute("INSERT OR IGNORE INTO type_orders(type_id, order_no) VALUES (?,?)", (tid, n))

def init_db():
    conn = get_conn()
    _ensure_tables(conn)
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM users WHERE lower(trim(username))='admin'")
    if not cur.fetchone():
        salt, pwd_hash = make_password_record("admin123")
        cur.execute("INSERT INTO users(username, role, salt, pwd_hash, created_at) VALUES (?,?,?,?,?)", ("admin", "admin", salt, pwd_hash, datetime.now().isoformat(timespec="seconds")))
    if df_query("SELECT COUNT(*) as c FROM categories").iloc[0]['c'] == 0:
        for n, p in [("Home", "hm"), ("PLP", "plp"), ("PDP", "pdp"), ("CLP", "clp")]: _upsert_category(conn, n, p)
    if df_query("SELECT COUNT(*) as c FROM types").iloc[0]['c'] == 0:
        for name, code in HOME_TYPES:
            _upsert_type(conn, name, code)
            _ensure_orders_for_code(conn, code)
    conn.commit()
    conn.close()

def get_user(username: str):
    u = (username or "").strip().lower()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT username, role, salt, pwd_hash FROM users WHERE lower(trim(username)) = ?", (u,))
    row = cur.fetchone()
    conn.close()
    return {"username": row[0], "role": row[1], "salt": row[2], "pwd_hash": row[3]} if row else None

def build_url_with_params(base_url: str, new_params: dict) -> str:
    parsed = urlparse(base_url.strip())
    existing = dict(parse_qsl(parsed.query, keep_blank_values=True))
    merged = {**existing, **{k: v for k, v in new_params.items() if v and str(v).strip() != ""}}
    query = urlencode(merged, doseq=True)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, query, parsed.fragment))

def make_hid(prefix: str, type_code: str, order_value: str) -> str:
    return "_".join([prefix, type_code, str(order_value).strip()])

# =========================
# CSS Styles (CORREGIDO COLOR DE TEXTO)
# =========================
def apply_custom_styles():
    st.markdown(f"""
    <style>
        /* Sidebar General */
        [data-testid="stSidebar"] {{ 
            background-color: {UNICOMER_BLUE}; 
        }}
        
        /* Asegurar visibilidad de etiquetas y textos en Sidebar */
        [data-testid="stSidebar"] label, 
        [data-testid="stSidebar"] p, 
        [data-testid="stSidebar"] h3 {{ 
            color: white !important; 
        }}

        /* CORRECCIÓN: Forzar color de texto oscuro en todos los inputs */
        .stTextInput input, .stSelectbox select, textarea {{
            color: #31333F !important; /* Gris oscuro/Negro */
            background-color: white !important; /* Fondo blanco */
            border-radius: 8px !important;
        }}

        /* Botones en Sidebar */
        [data-testid="stSidebar"] .stButton button {{
            background-color: {UNICOMER_YELLOW} !important;
            color: {UNICOMER_BLUE} !important;
            font-weight: bold;
        }}
        
        /* Ajuste de márgenes */
        .block-container {{ padding-top: 2rem; padding-bottom: 2rem; }}
        
        /* Fuentes */
        @import url('https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;600&display=swap');
        html, body, [class*="css"] {{ font-family: 'Open Sans', sans-serif; }}
        h1, h2, h3 {{ color: {UNICOMER_BLUE}; font-weight: 700; }}

        /* Botón Primario Unicomer (Main Content) */
        div.stButton > button[kind="primary"] {{
            background-color: {UNICOMER_YELLOW} !important;
            color: {UNICOMER_BLUE} !important;
            border: none !important;
            width: 100%;
            font-weight: bold;
            height: 3em;
        }}
    </style>
    """, unsafe_allow_html=True)

# =========================
# APP MAIN
# =========================
st.set_page_config(page_title=APP_TITLE, layout="wide")
apply_custom_styles()
init_db()

# SIDEBAR
with st.sidebar:
    st.markdown(f"<div style='filter: brightness(0) invert(1); text-align:center;'><img src='{UNICOMER_LOGO}' width='150'></div>", unsafe_allow_html=True)
    st.divider()
    
    if "auth" not in st.session_state:
        st.session_state.auth = {"is_logged": False, "username": None, "role": None}
    
    auth = st.session_state.auth
    if not auth["is_logged"]:
        st.subheader("🔐 Login")
        user = st.text_input("Usuario")
        pwd = st.text_input("Contraseña", type="password")
        if st.button("Entrar", type="primary"):
            u = get_user(user)
            if u and verify_password(pwd, u["salt"], u["pwd_hash"]):
                st.session_state.auth = {"is_logged": True, "username": u["username"], "role": u["role"]}
                st.rerun()
            else:
                st.error("Credenciales incorrectas")
    else:
        st.write(f"Bienvenido, **{auth['username']}**")
        if st.button("Cerrar sesión"):
            st.session_state.auth = {"is_logged": False, "username": None, "role": None}
            st.rerun()

# CONTENIDO PRINCIPAL
if not st.session_state.auth["is_logged"]:
    st.title(APP_TITLE)
    st.info("👈 Por favor, inicia sesión en el panel lateral para continuar.")
    st.stop()

# Layout Responsivo
col_left, col_main, col_right = st.columns([1, 2, 1])

with col_main:
    st.title(f"🔗 {APP_TITLE}")
    
    st.markdown(f"""
    <div style="padding:15px; border-radius:10px; border:1px solid #ddd; background:#f9f9f9; margin-bottom:20px;">
        <small>MOCKUPS FIGMA:</small><br>
        <a href="{FIGMA_URL}" target="_blank" style="color:{UNICOMER_BLUE}; word-break: break-all;">{FIGMA_URL}</a>
    </div>
    """, unsafe_allow_html=True)

    is_admin = st.session_state.auth["role"] == "admin"
    tabs = st.tabs(["✅ Generar", "🕒 Historial"] + (["⚙️ Admin"] if is_admin else []))

    # --- TAB GENERAR ---
    with tabs[0]:
        base_url = st.text_input("URL base", placeholder="https://www.tienda.com/producto")
        
        c1, c2 = st.columns(2)
        with c1:
            country = st.selectbox("País", ["SV", "GT", "CR", "HN", "NI", "PA", "DO", "JM", "TT", "Otro"])
            categories_df = df_query("SELECT id, name, prefix FROM categories")
            cat_options = [f"{r.name} ({r.prefix})" for r in categories_df.itertuples()]
            cat_sel = st.selectbox("Categoría", cat_options)
        
        with c2:
            types_df = df_query("SELECT id, name, code FROM types")
            type_options = [f"{r.name} ({r.code})" for r in types_df.itertuples()]
            type_sel = st.selectbox("Tipo", type_options)
            
            t_code = type_sel.split("(")[1].replace(")", "")
            t_id = types_df[types_df['code'] == t_code]['id'].values[0]
            orders = df_query("SELECT order_no FROM type_orders WHERE type_id=? ORDER BY order_no", (int(t_id),))
            order_list = orders['order_no'].tolist() if not orders.empty else DEFAULT_ORDER_RANGE
            order_val = st.selectbox("Order", order_list)

        if st.button("🔗 GENERAR LINK", type="primary"):
            if not base_url:
                st.error("Debes ingresar una URL")
            else:
                c_prefix = cat_sel.split("(")[1].replace(")", "")
                hid = make_hid(c_prefix, t_code, order_val)
                final_url = build_url_with_params(base_url, {"hid": hid})
                
                st.success("¡Link generado!")
                st.code(final_url)
                
                exec_sql("""INSERT INTO history (created_at, base_url, final_url, country, type_code, order_value, hid_value) 
                            VALUES (?,?,?,?,?,?,?)""", 
                         (datetime.now().isoformat(), base_url, final_url, country, t_code, str(order_val), hid))
                
                components.html(f"""
                    <button onclick="navigator.clipboard.writeText('{final_url}'); alert('Copiado');" 
                    style="width:100%; background:{UNICOMER_YELLOW}; border:none; padding:10px; border-radius:5px; font-weight:bold; cursor:pointer; color:{UNICOMER_BLUE};">
                    📋 COPIAR AL PORTAPAPELES
                    </button>
                """, height=50)

    # --- TAB HISTORIAL ---
    with tabs[1]:
        hist = df_query("SELECT created_at, country, final_url, hid_value FROM history ORDER BY id DESC LIMIT 20")
        st.dataframe(hist, use_container_width=True)

    # --- TAB ADMIN ---
    if is_admin:
        with tabs[2]:
            st.subheader("Gestión de Usuarios")
            u_data = df_query("SELECT id, username, role FROM users")
            st.table(u_data)
