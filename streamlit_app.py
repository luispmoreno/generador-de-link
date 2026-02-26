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
HOME_TYPES = [("BannerRotativo", "rtv"), ("MejoresOfertas", "topd"), ("CategoriasDestacadas", "dtd"), ("BloqueFomo", "bcr"), ("MoreDeals", "dls"), ("Carrusel1Ofertas", "bts"), ("BannerMultiuso1", "bmuno"), ("Carrusel2Ofertas", "npd"), ("BannerMultiuso2", "bmdos"), ("Carrusel3Ofertas", "cdp"), ("Carousel4Ofertas", "cci"), ("CarouselconImagen", "imb"), ("MarcasDestacadas", "mdt"), ("BloqueDeBeneficios", "icb"), ("CintilloBajoRotativo", "cbr"), ("BannerMultiuso3", "bmtres"), ("MoreDealsRotativo", "mdr"), ("CarruselConPortada", "ccp"), ("MoreDealsCarrusel", "mdc"), ("BannerMoreDealsCarrusel", "bmdc"), ("BannerDeCategoria", "bdct"), ("DobleBannerMultiuso", "dbm"), ("BannerLateral", "bnl"), ("MoreDealsde4", "mddc"), ("MoreDealsVersion2", "mdvd"), ("BannerMulticarruselCP", "bpm"), ("CategoriasDestacadasDos", "dtddos"), ("CategoriasDestacadasTres", "cdtres"), ("ProductTop", "pdtop"), ("TopCategories", "tcat"), ("FomoAdviento", "fad"), ("PopUp", "popup"), ("BannerMultiusoCP", "bmcp"), ("PopUp2", "popdos"), ("BotonLateral", "btl")]
ORDER_MAX_BY_CODE = {"rtv": 6, "topd": 1, "dtd": 1, "bcr": 4, "dls": 6, "bts": 1, "bmuno": 1, "npd": 1, "bmdos": 1, "cdp": 1, "cci": 1, "imb": 1, "mdt": 1, "icb": 1, "cbr": 1, "bmtres": 1, "mdr": 6, "ccp": 1, "mdc": 6, "bmdc": 1, "bdct": 10, "dbm": 2, "bnl": 1, "mddc": 4, "mdvd": 9, "bpm": 11, "dtddos": 3, "cdtres": 14, "pdtop": 6, "tcat": 6, "fad": 6, "popup": 1, "bmcp": 3, "popdos": 1, "btl": 1}
DEFAULT_ORDER_RANGE = list(range(1, 21))

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
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
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
    conn = get_conn()
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
        for name, code in HOME_TYPES:
            cur.execute("INSERT INTO types(name, code) VALUES (?,?)", (name, code))
            tid = cur.lastrowid
            max_n = ORDER_MAX_BY_CODE.get(code, 20)
            for n in range(1, max_n + 1):
                cur.execute("INSERT INTO type_orders(type_id, order_no) VALUES (?,?)", (tid, n))
    conn.commit()
    conn.close()

def get_user(username: str):
    u = username.strip().lower()
    res = df_query("SELECT username, role, salt, pwd_hash FROM users WHERE lower(username) = ?", (u,))
    return res.iloc[0].to_dict() if not res.empty else None

# =========================
# CSS Personalizado
# =========================
def apply_custom_styles():
    st.markdown(f"""
    <style>
        /* Fondo General */
        .stApp {{ background-color: #f4f7f9; }}

        /* Estilos de inputs para visibilidad de texto */
        .stTextInput input, .stSelectbox [data-baseweb="select"], .stSelectbox select {{
            color: #31333F !important;
            background-color: white !important;
            border-radius: 8px !important;
        }}

        /* MEJORA MOBILE: Scroll táctil en selectores */
        div[data-baseweb="popover"], div[data-baseweb="menu"] {{
            max-height: 350px !important;
            overflow-y: auto !important;
            -webkit-overflow-scrolling: touch !important;
        }}

        /* Sidebar Unicomer */
        [data-testid="stSidebar"] {{ background-color: {UNICOMER_BLUE}; }}
        [data-testid="stSidebar"] * {{ color: white !important; }}

        /* Botón Login y Generar */
        div.stButton > button {{
            background-color: {UNICOMER_YELLOW} !important;
            color: {UNICOMER_BLUE} !important;
            border: none !important;
            font-weight: bold;
            width: 100%;
            border-radius: 8px;
