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
# Configuración y Estilos
# =========================
APP_TITLE = "Generador de IDs - Unicomer"
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = str(BASE_DIR / "links.db")

UNICOMER_LOGO = "https://grupounicomer.com/wp-content/uploads/2022/12/logo-sol-gris.png"
UNICOMER_BLUE = "#002d5a"
UNICOMER_YELLOW = "#fdbb2d"
FIGMA_HOME_URL = "https://www.figma.com/design/ihSTaMfAmyN99BN5Z6sNps/Home-ULA?node-id=0-1&p=f"

st.set_page_config(page_title=APP_TITLE, layout="wide")

st.markdown(f"""
<style>
    [data-testid="stSidebar"] {{ background-color: {UNICOMER_BLUE} !important; }}
    [data-testid="stSidebar"] * {{ color: white !important; }}
    div.stButton > button {{
        background-color: {UNICOMER_YELLOW} !important;
        color: {UNICOMER_BLUE} !important;
        font-weight: bold; border: none; border-radius: 8px; width: 100%;
    }}
    .figma-box {{
        padding: 15px; border-radius: 12px; border: 2px solid #ff4b4b;
        background-color: rgba(255, 75, 75, 0.05); text-align: center; margin-bottom: 20px;
    }}
</style>
""", unsafe_allow_html=True)

# =========================
# Funciones de Seguridad
# =========================
def _hash_password(password: str, salt_hex: str) -> str:
    return hashlib.sha256((salt_hex + password).encode("utf-8")).hexdigest()

def make_password_record(password: str):
    salt = secrets.token_hex(16)
    return salt, _hash_password(password, salt)

def verify_password(password, salt, pwd_hash):
    return _hash_password(password, salt) == pwd_hash

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

def init_db():
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, role TEXT, salt TEXT, pwd_hash TEXT, created_at TEXT);")
        cur.execute("CREATE TABLE IF NOT EXISTS categories (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, prefix TEXT);")
        cur.execute("CREATE TABLE IF NOT EXISTS types (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, code TEXT);")
        cur.execute("CREATE TABLE IF NOT EXISTS type_orders (id INTEGER PRIMARY KEY AUTOINCREMENT, type_id INTEGER, order_no INTEGER);")
        cur.execute("CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT, base_url TEXT, final_url TEXT, country TEXT, type_code TEXT, order_value TEXT, hid_value TEXT);")
        
        # Inserción segura de usuarios iniciales
        users = [
            ("admin", "admin", "admin123"),
            ("ula_corp_design", "admin", "Dcorp$26"),
            ("luis_pena", "user", "Lpena$2026")
        ]
        for u, r, p in users:
            cur.execute("SELECT 1 FROM users WHERE username=?", (u,))
            if not cur.fetchone():
                s, ph = make_password_record(p)
                cur.execute("INSERT INTO users(username, role, salt, pwd_hash, created_at) VALUES (?,?,?,?,?)", (u, r, s, ph, datetime.now().isoformat()))

init_db()

# =========================
# Manejo de Sesión
# =========================
if "auth" not in st.session_state:
    st.session_state.auth = {"is_logged": False, "username": None, "role": None}

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
            else: st.error("Credenciales incorrectas")
    st.stop()

# --- BARRA LATERAL ---
with st.sidebar:
    st.image(UNICOMER_LOGO, width=150)
    st.write(f"Sesión: **{st.session_state.auth['username']}**")
    if st.button("Cerrar Sesión"):
        st.session_state.auth = {"is_logged": False}
        st.rerun()

tabs = st.tabs(["✅ Generador", "🕒 Historial", "⚙️ Administración"])

# =========================
# TAB GENERADOR
# =========================
with tabs[0]:
    col_l, col_r = st.columns([2, 1])
    with col_l:
        st.title("Generador de Links")
        url_base = st.text_input("URL base", placeholder="https://ejemplo.com")
    with col_r:
        st.markdown(f'<div class="figma-box"><p>Guía de Bloques</p><a href="{FIGMA_HOME_URL}" target="_blank"><button style="background:#A259FF; color:white; border:none; padding:8px; border-radius:5px; cursor:pointer; width:100%;">ABRIR FIGMA</button></a></div>', unsafe_allow_html=True)
    
    c1, c2, c3 = st.columns(3)
    pais = c1.selectbox("País", ["SV", "GT", "CR", "HN", "NI", "PA", "DO", "JM", "TT"])
    
    cats_df = df_query("SELECT name, prefix FROM categories")
    cat_list = [f"{r.name} ({r.prefix})" for r in cats_df.itertuples()] if not cats_df.empty else ["N/A"]
    cat_sel = c2.selectbox("Categoría", cat_list)
    
    types_df = df_query("SELECT id, name, code FROM types")
    type_list = [f"{r.name} ({r.code})" for r in types_df.itertuples()] if not types_df.empty else ["N/A"]
    type_sel = c3.selectbox("Tipo de Componente", type_list)
    
    if "(" in type_sel:
        t_code = type_sel.split("(")[1].replace(")", "")
        t_id = int(types_df[types_df['code'] == t_code]['id'].values[0])
        ord_df = df_query("SELECT order_no FROM type_orders WHERE type_id=? ORDER BY order_no", (t_id,))
        pos = st.selectbox("Posición (Orden)", ord_df['order_no'].tolist() if not ord_df.empty else [1])
        
        if st.button("GENERAR ID Y LINK"):
            pref = cat_sel.split("(")[1].replace(")", "")
            hid = f"{pref}_{t_code}_{pos}"
            p_url = urlparse(url_base.strip())
            qs = dict(parse_qsl(p_url.query)); qs['hid'] = hid
            final_url = urlunparse(p_url._replace(query=urlencode(qs)))
            exec_sql("INSERT INTO history (created_at, base_url, final_url, country, type_code, order_value, hid_value) VALUES (?,?,?,?,?,?,?)",
                    (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), url_base, final_url, pais, t_code, str(pos), hid))
            st.success(f"ID: {hid}")
            st.code(final_url)

# =========================
# TAB ADMINISTRACIÓN
# =========================
with tabs[2]:
    if st.session_state.auth["role"] != "admin":
        st.error("🔒 Acceso restringido. Solo administradores.")
    else:
        st.subheader("👤 Gestión de Usuarios")
        u_df = df_query("SELECT username, role FROM users")
        st.table(u_df)
        
        u_gest = st.selectbox("Seleccionar usuario para editar/eliminar", u_df['username'].tolist())
        
        col_u1, col_u2 = st.columns(2)
        
        with col_u1:
            # INTERRUPTOR DE PODER EXCLUSIVO PARA ADMIN SOBRE ULA_CORP_DESIGN
            if st.session_state.auth["username"] == "admin" and u_gest == "ula_corp_design":
                st.info("Control Maestro de ula_corp_design")
                actual_r = u_df[u_df['username'] == u_gest]['role'].iloc[0]
                nuevo_r = st.radio("Acceso a Administración:", ["Activado (admin)", "Desactivado (user)"], 
                                   index=0 if actual_r == "admin" else 1)
                if st.button("Aplicar Cambio de Permisos"):
                    r_val = "admin" if "Activado" in nuevo_r else "user"
                    exec_sql("UPDATE users SET role=? WHERE username=?", (r_val, u_gest))
                    st.success(f"Permisos actualizados. {u_gest} ahora es {r_val}")
                    st.rerun()
            
            # AGREGAR NUEVO USUARIO
            with st.expander("➕ Agregar Nuevo Usuario"):
                new_un = st.text_input("Nombre de Usuario")
                new_pw = st.text_input("Contraseña", type="password")
                if st.button("Guardar Usuario"):
                    if new_un and new_pw:
                        s, ph = make_password_record(new_pw)
                        exec_sql("INSERT INTO users(username, role, salt, pwd_hash) VALUES (?,?,?,?)", (new_un, "user", s, ph))
                        st.success("Usuario creado")
                        st.rerun()

        with col_u2:
            if st.button("🗑️ Eliminar Usuario seleccionado"):
                if u_gest in ["admin", "ula_corp_design", "luis_pena"]:
                    st.error("No puedes eliminar usuarios base del sistema.")
                else:
                    exec_sql("DELETE FROM users WHERE username=?", (u_gest,))
                    st.success("Usuario eliminado")
                    st.rerun()

        st.divider()
        st.subheader("📁 Mantenimiento de Catálogos")
        
        c_add, t_add = st.columns(2)
        
        # GESTIÓN DE CATEGORÍAS
        with c_add:
            st.write("**Categorías (ej. Home, Categoría)**")
            cat_n = st.text_input("Nombre Categoría")
            cat_p = st.text_input("Prefijo (ej. hm, ct)")
            if st.button("Añadir Categoría"):
                exec_sql("INSERT INTO categories(name, prefix) VALUES (?,?)", (cat_n, cat_p))
                st.success("Categoría añadida")
                st.rerun()
            
            st.write("---")
            if not cats_df.empty:
                c_del = st.selectbox("Eliminar Categoría", cats_df['name'].tolist())
                if st.button("Borrar Categoría"):
                    exec_sql("DELETE FROM categories WHERE name=?", (c_del,))
                    st.success("Eliminada")
                    st.rerun()

        # GESTIÓN DE TIPOS
        with t_add:
            st.write("**Tipos de Componentes (ej. Banner, Grid)**")
            tp_n = st.text_input("Nombre Tipo")
            tp_c = st.text_input("Código (ej. bn, gd)")
            tp_o = st.number_input("Cantidad de Posiciones", 1, 50, 5)
            if st.button("Crear Tipo"):
                exec_sql("INSERT INTO types(name, code) VALUES (?,?)", (tp_n, tp_c))
                new_id = df_query("SELECT id FROM types WHERE code=?", (tp_c,)).iloc[0]['id']
                for i in range(1, int(tp_o)+1):
                    exec_sql("INSERT INTO type_orders(type_id, order_no) VALUES (?,?)", (new_id, i))
                st.success("Tipo y posiciones creados")
                st.rerun()

            st.write("---")
            if not types_df.empty:
                t_del = st.selectbox("Eliminar Tipo", types_df['name'].tolist())
                if st.button("Borrar Tipo Completo"):
                    tid = int(types_df[types_df['name'] == t_del]['id'].values[0])
                    exec_sql("DELETE FROM type_orders WHERE type_id=?", (tid,))
                    exec_sql("DELETE FROM types WHERE id=?", (tid,))
                    st.success("Tipo eliminado")
                    st.rerun()
