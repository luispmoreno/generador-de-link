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
# 1. CONFIGURACIÓN E INICIALIZACIÓN
# =========================
APP_TITLE = "Generador de IDs - Unicomer"
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = str(BASE_DIR / "links.db")

st.set_page_config(page_title=APP_TITLE, layout="wide")

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
    .figma-box {{
        background-color: #f0f2f6; padding: 20px; border-radius: 10px;
        border-left: 5px solid {UNICOMER_YELLOW}; margin-bottom: 25px;
    }}
</style>
""", unsafe_allow_html=True)

# =========================
# 2. FUNCIONES DE BASE DE DATOS
# =========================
def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)

def exec_sql(sql, params=()):
    try:
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute(sql, params)
            conn.commit()
            return True
    except sqlite3.IntegrityError:
        st.error("❌ Error: El código o nombre ya existe en la base de datos.")
        return False
    except Exception as e:
        st.error(f"❌ Error inesperado: {e}")
        return False

def df_query(sql, params=()):
    with get_conn() as conn:
        return pd.read_sql_query(sql, conn, params=params)

def verify_password(password, salt, pwd_hash):
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest() == pwd_hash

def init_db():
    exec_sql("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, role TEXT, salt TEXT, pwd_hash TEXT, created_at TEXT);")
    exec_sql("CREATE TABLE IF NOT EXISTS categories (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, prefix TEXT UNIQUE);")
    exec_sql("CREATE TABLE IF NOT EXISTS types (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, code TEXT UNIQUE);")
    exec_sql("CREATE TABLE IF NOT EXISTS type_orders (id INTEGER PRIMARY KEY AUTOINCREMENT, type_id INTEGER, order_no INTEGER);")
    exec_sql("CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT, base_url TEXT, final_url TEXT, country TEXT, type_code TEXT, order_value TEXT, hid_value TEXT);")

init_db()

# =========================
# 3. LOGIN
# =========================
if not st.session_state.auth["is_logged"]:
    _, center, _ = st.columns([1, 2, 1])
    with center:
        st.image(UNICOMER_LOGO, width=200)
        u_in = st.text_input("Usuario")
        p_in = st.text_input("Contraseña", type="password")
        if st.button("ENTRAR", key="lp_btn"):
            res = df_query("SELECT username, role, salt, pwd_hash FROM users WHERE username=?", (u_in,))
            if not res.empty and verify_password(p_in, res.iloc[0]['salt'], res.iloc[0]['pwd_hash']):
                st.session_state.auth = {"is_logged": True, "username": res.iloc[0]['username'], "role": res.iloc[0]['role']}
                st.rerun()
            else: st.error("Credenciales incorrectas")
    st.stop()

# =========================
# 4. INTERFAZ
# =========================
with st.sidebar:
    st.image(UNICOMER_LOGO, width=150)
    st.write(f"👤 **{st.session_state.auth['username']}**")
    if st.button("Cerrar Sesión"):
        st.session_state.auth = {"is_logged": False}
        st.rerun()

tabs = st.tabs(["✅ Generador", "🕒 Historial", "⚙️ Administración"]) if st.session_state.auth["role"] == "admin" else st.tabs(["✅ Generador", "🕒 Historial"])

# --- TAB GENERADOR ---
with tabs[0]:
    st.markdown('<div class="figma-box"><h4>🎨 Guía de Diseño</h4><p>Consulta las posiciones en <a href="#" target="_blank">Figma aquí</a>.</p></div>', unsafe_allow_html=True)
    
    url_base = st.text_input("URL base", placeholder="https://...")
    c1, c2, c3 = st.columns(3)
    pais = c1.selectbox("País", ["SV", "GT", "CR", "HN", "NI", "PA", "DO", "JM", "TT"])
    
    cats_f = df_query("SELECT name, prefix FROM categories")
    cat_sel = c2.selectbox("Categoría", [f"{r.name} ({r.prefix})" for r in cats_f.itertuples()] if not cats_f.empty else ["N/A"])
    
    typs_f = df_query("SELECT id, name, code FROM types")
    type_sel = c3.selectbox("Tipo", [f"{r.name} ({r.code})" for r in typs_f.itertuples()] if not typs_f.empty else ["N/A"])
    
    if "(" in type_sel and "(" in cat_sel:
        t_code = type_sel.split("(")[1].replace(")", "")
        t_id = typs_f[typs_f['code'] == t_code]['id'].values[0]
        pos_df = df_query("SELECT order_no FROM type_orders WHERE type_id=? ORDER BY order_no", (int(t_id),))
        pos = st.selectbox("Posición", pos_df['order_no'].tolist() if not pos_df.empty else [1])
        
        if st.button("GENERAR ID Y LINK"):
            pref = cat_sel.split("(")[1].replace(")", "")
            hid = f"{pref}_{t_code}_{pos}"
            st.success(f"ID: {hid}")
            # Lógica de URL... (abreviada por espacio)

# --- TAB ADMINISTRACIÓN ---
if st.session_state.auth["role"] == "admin":
    with tabs[2]:
        st.subheader("👤 Gestión de Usuarios")
        u_list = df_query("SELECT id, username, role FROM users")
        st.table(u_list) # Usamos table para evitar errores de interacción en el dataframe
        
        with st.expander("➕ / 🗑️ Acciones de Usuario"):
            u_manage = st.selectbox("Seleccionar usuario", u_list['username'].tolist() if not u_list.empty else [], key="u_manage_sel")
            if st.button("Eliminar Usuario Seleccionado", key="del_u_final"):
                if u_manage not in ['admin', 'leslie_mejia']:
                    exec_sql("DELETE FROM users WHERE username=?", (u_manage,))
                    st.rerun()

        st.divider()
        st.subheader("🛠️ Catálogos y Componentes")
        
        # TABLA DE TIPOS (PEDIDA)
        summary = df_query("""SELECT t.name as Nombre, t.code as Código, COUNT(o.id) as Posiciones 
                           FROM types t LEFT JOIN type_orders o ON t.id = o.type_id GROUP BY t.id""")
        st.dataframe(summary, use_container_width=True)

        col_cat, col_typ = st.columns(2)
        
        with col_cat:
            with st.expander("📁 Categorías"):
                new_cn = st.text_input("Nombre", key="ncn")
                new_cp = st.text_input("Prefijo", key="ncp")
                if st.button("Añadir Categoría"):
                    exec_sql("INSERT INTO categories(name, prefix) VALUES (?,?)", (new_cn, new_cp))
                    st.rerun()

        with col_typ:
            with st.expander("➕ Añadir Tipo"):
                atn = st.text_input("Nombre", key="atn_z")
                atc = st.text_input("Código", key="atc_z")
                atp = st.number_input("Posiciones", 1, 50, 5, key="atp_z")
                if st.button("Crear"):
                    if exec_sql("INSERT INTO types(name, code) VALUES (?,?)", (atn, atc)):
                        tid_res = df_query("SELECT id FROM types WHERE code=?", (atc,))
                        for i in range(1, int(atp)+1): exec_sql("INSERT INTO type_orders(type_id, order_no) VALUES (?,?)", (tid_res.iloc[0]['id'], i))
                        st.rerun()

            st.write("**📝 Editar/Borrar Tipo**")
            t_names = summary['Nombre'].tolist() if not summary.empty else []
            t_edit = st.selectbox("Seleccionar", t_names, key="t_ed_sel")
            if t_edit:
                t_dat = df_query("SELECT * FROM types WHERE name=?", (t_edit,)).iloc[0]
                curr_p = int(summary[summary['Nombre'] == t_edit]['Posiciones'].iloc[0])
                
                with st.expander("Editar"):
                    e_n = st.text_input("Nombre", value=t_dat['name'], key="en_z")
                    e_c = st.text_input("Código", value=t_dat['code'], key="ec_z")
                    e_p = st.number_input("Posiciones", 1, 50, value=max(1, curr_p), key="ep_z")
                    if st.button("Actualizar"):
                        exec_sql("UPDATE types SET name=?, code=? WHERE id=?", (e_n, e_c, int(t_dat['id'])))
                        # Sincronizar posiciones
                        if e_p > curr_p:
                            for i in range(curr_count + 1, int(e_p) + 1): exec_sql("INSERT INTO type_orders(type_id, order_no) VALUES (?,?)", (int(t_dat['id']), i))
                        elif e_p < curr_p:
                            exec_sql("DELETE FROM type_orders WHERE type_id=? AND order_no > ?", (int(t_dat['id']), int(e_p)))
                        st.rerun()
                
                if st.button("🗑️ Eliminar Tipo Completo", key="del_t_z"):
                    exec_sql("DELETE FROM type_orders WHERE type_id=?", (int(t_dat['id']),))
                    exec_sql("DELETE FROM types WHERE id=?", (int(t_dat['id']),))
                    st.rerun()
