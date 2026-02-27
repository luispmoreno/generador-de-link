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

# Inicialización crítica del estado de sesión
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
    .stDataFrame {{ background-color: white; border-radius: 10px; }}
</style>
""", unsafe_allow_html=True)

# =========================
# 2. FUNCIONES DE DATOS
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
        
        # Usuarios por defecto
        default_users = [
            ("admin", "admin", "admin123"),
            ("leslie_mejia", "admin", "unicomer1234"),
            ("ula_corp_design", "admin", "Dcorp$26")
        ]
        for u, r, p in default_users:
            cur.execute("SELECT id FROM users WHERE username=?", (u,))
            if not cur.fetchone():
                s, ph = make_password_record(p)
                cur.execute("INSERT INTO users(username, role, salt, pwd_hash, created_at) VALUES (?,?,?,?,?)", 
                           (u, r, s, ph, datetime.now().isoformat()))
        conn.commit()

init_db()

# =========================
# 3. SISTEMA DE ACCESO
# =========================
if not st.session_state.auth["is_logged"]:
    _, center, _ = st.columns([1, 2, 1])
    with center:
        st.image(UNICOMER_LOGO, width=200)
        u_in = st.text_input("Usuario")
        p_in = st.text_input("Contraseña", type="password")
        if st.button("ENTRAR", key="login_main"):
            res = df_query("SELECT username, role, salt, pwd_hash FROM users WHERE username=?", (u_in,))
            if not res.empty and verify_password(p_in, res.iloc[0]['salt'], res.iloc[0]['pwd_hash']):
                st.session_state.auth = {"is_logged": True, "username": res.iloc[0]['username'], "role": res.iloc[0]['role']}
                st.rerun()
            else: st.error("Credenciales incorrectas")
    st.stop()

# =========================
# 4. INTERFAZ PRINCIPAL
# =========================
with st.sidebar:
    st.image(UNICOMER_LOGO, width=150)
    st.write(f"👤 Usuario: **{st.session_state.auth['username']}**")
    if st.button("Cerrar Sesión"):
        st.session_state.auth = {"is_logged": False}
        st.rerun()

# Definición de pestañas según rol
tabs = st.tabs(["✅ Generador", "🕒 Historial", "⚙️ Administración"]) if st.session_state.auth["role"] == "admin" else st.tabs(["✅ Generador", "🕒 Historial"])

# --- TAB GENERADOR ---
with tabs[0]:
    st.title("Generador de IDs")
    url_base = st.text_input("URL base", placeholder="https://ejemplo.unicomer.com...")
    c1, c2, c3 = st.columns(3)
    pais = c1.selectbox("País", ["SV", "GT", "CR", "HN", "NI", "PA", "DO", "JM", "TT"])
    
    cats_df = df_query("SELECT name, prefix FROM categories")
    cat_sel = c2.selectbox("Categoría", [f"{r.name} ({r.prefix})" for r in cats_df.itertuples()] if not cats_df.empty else ["N/A"])
    
    typs_df = df_query("SELECT id, name, code FROM types")
    type_sel = c3.selectbox("Tipo", [f"{r.name} ({r.code})" for r in typs_df.itertuples()] if not typs_df.empty else ["N/A"])
    
    if "(" in type_sel and "(" in cat_sel:
        t_code = type_sel.split("(")[1].replace(")", "")
        t_id = typs_df[typs_df['code'] == t_code]['id'].values[0]
        pos_df = df_query("SELECT order_no FROM type_orders WHERE type_id=? ORDER BY order_no", (int(t_id),))
        pos = st.selectbox("Posición", pos_df['order_no'].tolist() if not pos_df.empty else [1])
        
        if st.button("GENERAR ID Y LINK", key="btn_generate"):
            pref = cat_sel.split("(")[1].replace(")", "")
            hid = f"{pref}_{t_code}_{pos}"
            p_url = urlparse(url_base.strip())
            qs = dict(parse_qsl(p_url.query)); qs['hid'] = hid
            f_url = urlunparse(p_url._replace(query=urlencode(qs)))
            exec_sql("INSERT INTO history (created_at, base_url, final_url, country, type_code, order_value, hid_value) VALUES (?,?,?,?,?,?,?)",
                    (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), url_base, f_url, pais, t_code, str(pos), hid))
            st.success(f"ID: {hid}")
            st.code(f_url)

# --- TAB ADMINISTRACIÓN ---
if st.session_state.auth["role"] == "admin":
    with tabs[2]:
        st.header("⚙️ Panel de Control")
        
        # 1. VISUALIZACIÓN DE USUARIOS
        st.subheader("👤 Usuarios Registrados")
        users_table = df_query("SELECT id, username, role, created_at FROM users")
        st.dataframe(users_table, use_container_width=True)
        
        with st.expander("➕ Gestionar Usuarios (Crear/Eliminar)"):
            u_col1, u_col2 = st.columns(2)
            with u_col1:
                st.write("**Nuevo Usuario**")
                new_u = st.text_input("Username", key="adm_new_u")
                new_p = st.text_input("Password", type="password", key="adm_new_p")
                new_r = st.selectbox("Rol", ["admin", "user"], key="adm_new_r")
                if st.button("Registrar Usuario", key="btn_reg_u"):
                    s, ph = make_password_record(new_p)
                    exec_sql("INSERT INTO users(username, role, salt, pwd_hash, created_at) VALUES (?,?,?,?,?)", (new_u, new_r, s, ph, datetime.now().isoformat()))
                    st.toast("Usuario creado"); time.sleep(1); st.rerun()
            with u_col2:
                st.write("**Eliminar Usuario**")
                u_to_del = st.selectbox("Seleccionar", users_table['username'].tolist(), key="sel_u_del")
                if st.button("Eliminar Seleccionado", key="btn_del_u"):
                    if u_to_del not in ["admin", "leslie_mejia"]:
                        exec_sql("DELETE FROM users WHERE username=?", (u_to_del,))
                        st.toast("Usuario eliminado"); time.sleep(1); st.rerun()
                    else: st.error("No puedes eliminar administradores maestros")

        st.divider()

        # 2. VISUALIZACIÓN DE TIPOS Y CATÁLOGOS
        st.subheader("📁 Mantenimiento de Catálogos")
        
        # Tabla resumen de Tipos y Posiciones
        st.write("**Resumen de Tipos y Posiciones Disponibles**")
        summary_df = df_query("""
            SELECT t.name as Nombre, t.code as Código, COUNT(o.id) as 'Total Posiciones'
            FROM types t LEFT JOIN type_orders o ON t.id = o.type_id
            GROUP BY t.id
        """)
        st.dataframe(summary_df, use_container_width=True)

        # GESTIÓN DE CATEGORÍAS
        st.write("---")
        c_m1, c_m2 = st.columns(2)
        with c_m1:
            with st.expander("📂 Gestionar Categorías"):
                cat_name = st.text_input("Nombre Categoría", key="add_c_n")
                cat_pref = st.text_input("Prefijo (ej: hm)", key="add_c_p")
                if st.button("Guardar Categoría", key="btn_c_save"):
                    exec_sql("INSERT INTO categories(name, prefix) VALUES (?,?)", (cat_name, cat_pref))
                    st.rerun()
                
                if not cats_df.empty:
                    c_edit_sel = st.selectbox("Editar/Eliminar Categoría", cats_df['name'].tolist(), key="sel_c_manage")
                    c_data = df_query("SELECT id, name, prefix FROM categories WHERE name=?", (c_edit_sel,)).iloc[0]
                    new_cn = st.text_input("Nuevo Nombre", value=c_data['name'], key="ed_c_n")
                    new_cp = st.text_input("Nuevo Prefijo", value=c_data['prefix'], key="ed_c_p")
                    
                    eb1, eb2 = st.columns(2)
                    if eb1.button("Actualizar", key="btn_c_upd"):
                        exec_sql("UPDATE categories SET name=?, prefix=? WHERE id=?", (new_cn, new_cp, int(c_data['id'])))
                        st.rerun()
                    if eb2.button("Eliminar", key="btn_c_del"):
                        exec_sql("DELETE FROM categories WHERE id=?", (int(c_data['id']),))
                        st.rerun()

        # GESTIÓN DE TIPOS (EL MÁS COMPLETO)
        with c_m2:
            with st.expander("🛠️ Gestionar Tipos de Componentes"):
                st.write("**Añadir Nuevo**")
                t_n = st.text_input("Nombre Tipo", key="at_n")
                t_c = st.text_input("Código (ej: rtv)", key="at_c")
                t_p = st.number_input("Posiciones Iniciales", 1, 50, 5, key="at_p")
                if st.button("Crear Tipo", key="btn_t_save"):
                    exec_sql("INSERT INTO types(name, code) VALUES (?,?)", (t_n, t_c))
                    tid = df_query("SELECT id FROM types WHERE code=?", (t_c,)).iloc[0]['id']
                    for i in range(1, int(t_p)+1): exec_sql("INSERT INTO type_orders(type_id, order_no) VALUES (?,?)", (tid, i))
                    st.rerun()
                
                st.divider()
                st.write("**Modificar Existente**")
                if not typs_df.empty:
                    t_edit_sel = st.selectbox("Seleccionar Tipo", typs_df['name'].tolist(), key="sel_t_manage")
                    t_data = df_query("SELECT * FROM types WHERE name=?", (t_edit_sel,)).iloc[0]
                    tid_edit = int(t_data['id'])
                    
                    curr_pos_count = len(df_query("SELECT id FROM type_orders WHERE type_id=?", (tid_edit,)))
                    
                    new_tn = st.text_input("Editar Nombre", value=t_data['name'], key="ed_t_n")
                    new_tc = st.text_input("Editar Código", value=t_data['code'], key="ed_t_c")
                    new_tp = st.number_input("Cantidad de Posiciones", 1, 50, value=curr_pos_count, key="ed_t_p")
                    
                    tb1, tb2 = st.columns(2)
                    if tb1.button("Aplicar Cambios", key="btn_t_upd"):
                        # Actualizar nombre/código
                        exec_sql("UPDATE types SET name=?, code=? WHERE id=?", (new_tn, new_tc, tid_edit))
                        # Sincronizar posiciones
                        if new_tp > curr_pos_count:
                            for i in range(curr_pos_count + 1, int(new_tp) + 1):
                                exec_sql("INSERT INTO type_orders(type_id, order_no) VALUES (?,?)", (tid_edit, i))
                        elif new_tp < curr_pos_count:
                            exec_sql("DELETE FROM type_orders WHERE type_id=? AND order_no > ?", (tid_edit, int(new_tp)))
                        st.toast("Tipo actualizado"); time.sleep(1); st.rerun()
                        
                    if tb2.button("Eliminar Tipo", key="btn_t_del"):
                        exec_sql("DELETE FROM type_orders WHERE type_id=?", (tid_edit,))
                        exec_sql("DELETE FROM types WHERE id=?", (tid_edit,))
                        st.rerun()
