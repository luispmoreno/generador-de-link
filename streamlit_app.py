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

# Inicialización de sesión inmediata para evitar NameError
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
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 10px;
        border-left: 5px solid {UNICOMER_YELLOW};
        margin-bottom: 25px;
    }}
</style>
""", unsafe_allow_html=True)

# =========================
# 2. FUNCIONES DE BASE DE DATOS
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
        
        # Usuarios Maestros
        for u, r, p in [("admin", "admin", "admin123"), ("leslie_mejia", "admin", "unicomer1234"), ("ula_corp_design", "admin", "Dcorp$26")]:
            cur.execute("SELECT id FROM users WHERE username=?", (u,))
            if not cur.fetchone():
                s, ph = make_password_record(p)
                cur.execute("INSERT INTO users(username, role, salt, pwd_hash, created_at) VALUES (?,?,?,?,?)", (u, r, s, ph, datetime.now().isoformat()))
        conn.commit()

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
        if st.button("ENTRAR"):
            res = df_query("SELECT username, role, salt, pwd_hash FROM users WHERE username=?", (u_in,))
            if not res.empty and verify_password(p_in, res.iloc[0]['salt'], res.iloc[0]['pwd_hash']):
                st.session_state.auth = {"is_logged": True, "username": res.iloc[0]['username'], "role": res.iloc[0]['role']}
                st.rerun()
            else: st.error("Acceso denegado")
    st.stop()

# =========================
# 4. INTERFAZ PRINCIPAL
# =========================
with st.sidebar:
    st.image(UNICOMER_LOGO, width=150)
    st.write(f"👤 **{st.session_state.auth['username']}**")
    st.write(f"🔑 Rol: **{st.session_state.auth['role'].upper()}**")
    if st.button("Cerrar Sesión"):
        st.session_state.auth = {"is_logged": False}
        st.rerun()

tabs = st.tabs(["✅ Generador", "🕒 Historial", "⚙️ Administración"]) if st.session_state.auth["role"] == "admin" else st.tabs(["✅ Generador", "🕒 Historial"])

# --- TAB GENERADOR ---
with tabs[0]:
    # RECUADRO DE FIGMA (RESTABLECIDO)
    st.markdown(f"""
    <div class="figma-box">
        <h4 style="margin-top:0;">🎨 Guía de Diseño y Posiciones</h4>
        <p>Para revisar el orden correcto de los componentes y las posiciones del Home, consulta el diseño oficial en Figma:</p>
        <a href="https://www.figma.com/design/tu-link-de-figma-aqui" target="_blank" style="color:{UNICOMER_BLUE}; font-weight:bold; text-decoration:none;">
            🚀 ABRIR DISEÑO EN FIGMA
        </a>
    </div>
    """, unsafe_allow_html=True)

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
        pos = st.selectbox("Posición (Orden)", pos_df['order_no'].tolist() if not pos_df.empty else [1])
        
        if st.button("GENERAR ID Y LINK"):
            pref = cat_sel.split("(")[1].replace(")", "")
            hid = f"{pref}_{t_code}_{pos}"
            p_url = urlparse(url_base.strip())
            qs = dict(parse_qsl(p_url.query)); qs['hid'] = hid
            f_url = urlunparse(p_url._replace(query=urlencode(qs)))
            
            exec_sql("INSERT INTO history (created_at, base_url, final_url, country, type_code, order_value, hid_value) VALUES (?,?,?,?,?,?,?)",
                    (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), url_base, f_url, pais, t_code, str(pos), hid))
            
            st.success(f"ID Generado: {hid}")
            st.code(f_url)
            components.html(f"<button onclick=\"navigator.clipboard.writeText('{f_url}'); alert('Link copiado')\" style=\"width:100%; background:{UNICOMER_YELLOW}; border:none; height:45px; border-radius:8px; font-weight:bold; cursor:pointer; color:{UNICOMER_BLUE}\">📋 COPIAR LINK</button>", height=50)

# --- TAB ADMINISTRACIÓN ---
if st.session_state.auth["role"] == "admin":
    with tabs[2]:
        st.header("⚙️ Panel de Administración")
        
        # TABLA DE USUARIOS (RESTABLECIDA)
        st.subheader("👤 Usuarios Registrados")
        st.dataframe(df_query("SELECT id, username, role, created_at FROM users"), use_container_width=True)
        
        # TABLA DE TIPOS (RESTABLECIDA)
        st.subheader("📊 Resumen de Tipos y Posiciones")
        summary_df = df_query("""
            SELECT t.name as Nombre, t.code as Código, COUNT(o.id) as 'Total Posiciones'
            FROM types t LEFT JOIN type_orders o ON t.id = o.type_id
            GROUP BY t.id
        """)
        st.dataframe(summary_df, use_container_width=True)

        st.divider()

        col_left, col_right = st.columns(2)
        
        with col_left:
            st.write("**📂 Mantenimiento de Categorías**")
            with st.expander("Añadir / Borrar Categoría"):
                c_n = st.text_input("Nombre", key="cat_n_new")
                c_p = st.text_input("Prefijo", key="cat_p_new")
                if st.button("Guardar", key="save_c"):
                    exec_sql("INSERT INTO categories(name, prefix) VALUES (?,?)", (c_n, c_p))
                    st.rerun()
                
                if not cats.empty:
                    c_del = st.selectbox("Eliminar Categoría", cats['name'].tolist(), key="del_cat_sel")
                    if st.button(f"🗑️ Borrar {c_del}"):
                        exec_sql("DELETE FROM categories WHERE name=?", (c_del,))
                        st.rerun()

        with col_right:
            st.write("**🛠️ Mantenimiento de Tipos**")
            with st.expander("➕ Añadir Nuevo Tipo"):
                tn = st.text_input("Nombre", key="add_tn")
                tc = st.text_input("Código", key="add_tc")
                tp = st.number_input("Posiciones iniciales", 1, 50, 5, key="add_tp")
                if st.button("Crear Tipo"):
                    exec_sql("INSERT INTO types(name, code) VALUES (?,?)", (tn, tc))
                    tid = df_query("SELECT id FROM types WHERE code=?", (tc,)).iloc[0]['id']
                    for i in range(1, int(tp)+1): exec_sql("INSERT INTO type_orders(type_id, order_no) VALUES (?,?)", (tid, i))
                    st.rerun()

            if not typs.empty:
                st.write("**📝 Editar o Eliminar Tipo**")
                t_manage = st.selectbox("Seleccionar", typs['name'].tolist(), key="edit_t_sel")
                t_row = typs[typs['name'] == t_manage].iloc[0]
                tid = int(t_row['id'])
                
                # Blindaje contra StreamlitValueBelowMinError
                count_res = df_query("SELECT COUNT(*) as c FROM type_orders WHERE type_id=?", (tid,))
                curr_count = max(1, int(count_res['c'].iloc[0]))

                with st.expander("Modificar Seleccionado"):
                    new_tn = st.text_input("Nombre", value=t_row['name'], key="ed_tn_act")
                    new_tc = st.text_input("Código", value=t_row['code'], key="ed_tc_act")
                    new_tp = st.number_input("Cantidad de Posiciones", 1, 50, value=curr_count, key="ed_tp_act")
                    
                    if st.button("Actualizar Tipo"):
                        exec_sql("UPDATE types SET name=?, code=? WHERE id=?", (new_tn, new_tc, tid))
                        if new_tp > curr_count:
                            for i in range(curr_count + 1, int(new_tp) + 1):
                                exec_sql("INSERT INTO type_orders(type_id, order_no) VALUES (?,?)", (tid, i))
                        elif new_tp < curr_count:
                            exec_sql("DELETE FROM type_orders WHERE type_id=? AND order_no > ?", (tid, int(new_tp)))
                        st.rerun()
                
                if st.button(f"❌ ELIMINAR TIPO: {t_manage}", key="del_t_btn"):
                    exec_sql("DELETE FROM type_orders WHERE type_id=?", (tid,))
                    exec_sql("DELETE FROM types WHERE id=?", (tid,))
                    st.rerun()
