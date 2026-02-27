import streamlit as st
import sqlite3
import pandas as pd
import hashlib
import secrets
import time
from datetime import datetime
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse
from pathlib import Path
import streamlit.components.v1 as components

# =========================
# 1. Configuración Inicial
# =========================
APP_TITLE = "Generador de IDs - Unicomer"
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = str(BASE_DIR / "links.db")

st.set_page_config(page_title=APP_TITLE, layout="wide")

# Inicialización de sesión (Esto DEBE ir antes de cualquier validación de rol)
if "auth" not in st.session_state:
    st.session_state.auth = {"is_logged": False, "username": None, "role": None}

UNICOMER_LOGO = "https://grupounicomer.com/wp-content/uploads/2022/12/logo-sol-gris.png"
UNICOMER_BLUE = "#002d5a"
UNICOMER_YELLOW = "#fdbb2d"

st.markdown(f"""
<style>
    [data-testid="stSidebar"] {{ background-color: {UNICOMER_BLUE} !important; }}
    [data-testid="stSidebar"] * {{ color: white !important; }}
    div.stButton > button {{
        background-color: {UNICOMER_YELLOW} !important;
        color: {UNICOMER_BLUE} !important;
        font-weight: bold; border: none; border-radius: 8px; width: 100%; height: 45px;
    }}
</style>
""", unsafe_allow_html=True)

# =========================
# 2. Funciones de Base de Datos
# =========================
def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)

def exec_sql(sql, params=()):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(sql, params)
        conn.commit()

def df_query(sql, params=()):
    with get_conn() as conn:
        return pd.read_sql_query(sql, conn, params=params)

def _hash_password(password: str, salt_hex: str) -> str:
    return hashlib.sha256((salt_hex + password).encode("utf-8")).hexdigest()

def make_password_record(password: str):
    salt = secrets.token_hex(16)
    return salt, _hash_password(password, salt)

def verify_password(password, salt, pwd_hash):
    return _hash_password(password, salt) == pwd_hash

def init_db():
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, role TEXT, salt TEXT, pwd_hash TEXT, created_at TEXT);")
        cur.execute("CREATE TABLE IF NOT EXISTS categories (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, prefix TEXT);")
        cur.execute("CREATE TABLE IF NOT EXISTS types (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, code TEXT);")
        cur.execute("CREATE TABLE IF NOT EXISTS type_orders (id INTEGER PRIMARY KEY AUTOINCREMENT, type_id INTEGER, order_no INTEGER);")
        cur.execute("CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT, base_url TEXT, final_url TEXT, country TEXT, type_code TEXT, order_value TEXT, hid_value TEXT);")
        
        # Configuración de usuarios requerida
        users_to_setup = [
            ("admin", "admin", "admin123"),
            ("leslie_mejia", "admin", "unicomer1234"),
            ("ula_corp_design", "user", "Dcorp$26")
        ]
        
        for u, r, p in users_to_setup:
            cur.execute("SELECT id FROM users WHERE username=?", (u,))
            if not cur.fetchone():
                s, ph = make_password_record(p)
                cur.execute("INSERT INTO users(username, role, salt, pwd_hash, created_at) VALUES (?,?,?,?,?)", 
                           (u, r, s, ph, datetime.now().isoformat()))
            else:
                cur.execute("UPDATE users SET role=? WHERE username=?", (r, u))
        conn.commit()

init_db()

# =========================
# 3. Login
# =========================
if not st.session_state.auth["is_logged"]:
    _, center, _ = st.columns([1, 2, 1])
    with center:
        st.image(UNICOMER_LOGO, width=200)
        u_in = st.text_input("Usuario")
        p_in = st.text_input("Contraseña", type="password")
        if st.button("ENTRAR", key="login_btn"):
            res = df_query("SELECT username, role, salt, pwd_hash FROM users WHERE username=?", (u_in,))
            if not res.empty and verify_password(p_in, res.iloc[0]['salt'], res.iloc[0]['pwd_hash']):
                st.session_state.auth = {"is_logged": True, "username": res.iloc[0]['username'], "role": res.iloc[0]['role']}
                st.rerun()
            else: st.error("Credenciales incorrectas")
    st.stop()

# =========================
# 4. Interfaz Principal
# =========================
with st.sidebar:
    st.image(UNICOMER_LOGO, width=150)
    st.write(f"👤 Sesión: **{st.session_state.auth['username']}**")
    st.write(f"🔑 Rol: **{st.session_state.auth['role'].upper()}**")
    if st.button("Cerrar Sesión"):
        st.session_state.auth = {"is_logged": False}
        st.rerun()

# Definición de pestañas
if st.session_state.auth["role"] == "admin":
    tabs = st.tabs(["✅ Generador", "🕒 Historial", "⚙️ Administración"])
else:
    tabs = st.tabs(["✅ Generador", "🕒 Historial"])

# --- TAB GENERADOR ---
with tabs[0]:
    st.title("Generador de IDs")
    url_base = st.text_input("URL base", placeholder="https://ejemplo.unicomer.com...")
    c1, c2, c3 = st.columns(3)
    pais = c1.selectbox("País", ["SV", "GT", "CR", "HN", "NI", "PA", "DO", "JM", "TT"])
    
    cats = df_query("SELECT name, prefix FROM categories")
    cat_sel = c2.selectbox("Categoría", [f"{r.name} ({r.prefix})" for r in cats.itertuples()] if not cats.empty else ["N/A"])
    
    typs = df_query("SELECT id, name, code FROM types")
    type_sel = c3.selectbox("Tipo", [f"{r.name} ({r.code})" for r in typs.itertuples()] if not typs.empty else ["N/A"])
    
    if "(" in type_sel and "(" in cat_sel:
        t_code = type_sel.split("(")[1].replace(")", "")
        t_id = typs[typs['code'] == t_code]['id'].values[0]
        pos_df = df_query("SELECT order_no FROM type_orders WHERE type_id=? ORDER BY order_no", (int(t_id),))
        pos = st.selectbox("Posición", pos_df['order_no'].tolist() if not pos_df.empty else [1])
        
        if st.button("GENERAR ID Y LINK", key="gen_main"):
            pref = cat_sel.split("(")[1].replace(")", "")
            hid = f"{pref}_{t_code}_{pos}"
            p_url = urlparse(url_base.strip())
            qs = dict(parse_qsl(p_url.query)); qs['hid'] = hid
            f_url = urlunparse(p_url._replace(query=urlencode(qs)))
            
            exec_sql("INSERT INTO history (created_at, base_url, final_url, country, type_code, order_value, hid_value) VALUES (?,?,?,?,?,?,?)",
                    (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), url_base, f_url, pais, t_code, str(pos), hid))
            
            st.success(f"ID Generado: {hid}")
            st.code(f_url)
            components.html(f"<button onclick=\"navigator.clipboard.writeText('{f_url}'); alert('Link copiado')\" style=\"width:100%; background:{UNICOMER_YELLOW}; border:none; height:45px; border-radius:8px; font-weight:bold; cursor:pointer;\">📋 COPIAR LINK</button>", height=50)

# --- TAB ADMINISTRACIÓN ---
if st.session_state.auth["role"] == "admin":
    with tabs[2]:
        st.subheader("⚙️ Mantenimiento de Catálogos")
        col_cat, col_typ = st.columns(2)
        
        with col_cat:
            st.write("**Categorías**")
            with st.expander("➕ Añadir"):
                cn = st.text_input("Nombre", key="new_cat_n")
                cp = st.text_input("Prefijo", key="new_cat_p")
                if st.button("Guardar Categoría", key="save_c"):
                    exec_sql("INSERT INTO categories(name, prefix) VALUES (?,?)", (cn, cp))
                    st.rerun()
            
            cats_adm = df_query("SELECT * FROM categories")
            if not cats_adm.empty:
                c_del = st.selectbox("Gestionar Categoría", cats_adm['name'].tolist(), key="sel_c_adm")
                c_row = cats_adm[cats_adm['name'] == c_del].iloc[0]
                if st.button(f"🗑️ Eliminar {c_del}", key="del_c_btn"):
                    exec_sql("DELETE FROM categories WHERE id=?", (int(c_row['id']),))
                    st.rerun()

        with col_typ:
            st.write("**Tipos y Componentes**")
            with st.expander("➕ Añadir"):
                tn = st.text_input("Nombre", key="new_t_n")
                tc = st.text_input("Código", key="new_t_c")
                tp = st.number_input("Posiciones", 1, 50, 5, key="new_t_p")
                if st.button("Crear Tipo", key="save_t"):
                    exec_sql("INSERT INTO types(name, code) VALUES (?,?)", (tn, tc))
                    tid = df_query("SELECT id FROM types WHERE code=?", (tc,)).iloc[0]['id']
                    for i in range(1, int(tp)+1): exec_sql("INSERT INTO type_orders(type_id, order_no) VALUES (?,?)", (tid, i))
                    st.rerun()

            typs_adm = df_query("SELECT * FROM types")
            if not typs_adm.empty:
                t_manage = st.selectbox("Gestionar Tipo", typs_adm['name'].tolist(), key="sel_t_adm")
                t_row = typs_adm[typs_adm['name'] == t_manage].iloc[0]
                tid = int(t_row['id'])
                
                # OPCIÓN DE BORRAR TIPOS REINCORPORADA
                st.info(f"Código actual: {t_row['code']}")
                if st.button(f"🗑️ Eliminar Tipo: {t_manage}", key="del_t_btn"):
                    exec_sql("DELETE FROM type_orders WHERE type_id=?", (tid,))
                    exec_sql("DELETE FROM types WHERE id=?", (tid,))
                    st.success(f"Tipo {t_manage} eliminado")
                    time.sleep(1)
                    st.rerun()
