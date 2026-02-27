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

UNICOMER_BLUE = "#002d5a"
UNICOMER_YELLOW = "#fdbb2d"

# LOGO EN SVG (PARA QUE NO SE CAIGA NUNCA)
LOGO_SVG = """
<svg viewBox="0 0 500 150" xmlns="http://www.w3.org/2000/svg">
    <path fill="white" d="M45.2,85.1c-12.7,0-21.5-8.5-21.5-21.2c0-12.8,8.8-21.2,21.5-21.2c12.7,0,21.5,8.4,21.5,21.2 C66.7,76.6,57.9,85.1,45.2,85.1z M45.2,50.8c-7.6,0-12.6,5.3-12.6,13.1c0,7.7,5,13.1,12.6,13.1c7.5,0,12.6-5.3,12.6-13.1 C57.8,56.1,52.7,50.8,45.2,50.8z"/>
    <text x="80" y="95" font-family="Arial, Helvetica, sans-serif" font-weight="bold" font-size="80" fill="white">unicomer</text>
</svg>
"""

st.markdown(f"""
<style>
    [data-testid="stSidebar"] {{ background-color: {UNICOMER_BLUE} !important; }}
    [data-testid="stSidebar"] * {{ color: white !important; }}
    .sidebar-logo {{ width: 180px; margin-bottom: 20px; filter: drop-shadow(0px 0px 2px rgba(255,255,255,0.5)); }}
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
        st.error("❌ Error de Integridad: El nombre o código ya existe.")
        return False

def df_query(sql, params=()):
    with get_conn() as conn:
        return pd.read_sql_query(sql, conn, params=params)

def make_password_record(password: str):
    salt = secrets.token_hex(16)
    pwd_hash = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
    return salt, pwd_hash

# =========================
# 3. LOGIN
# =========================
if not st.session_state.auth["is_logged"]:
    _, center, _ = st.columns([1, 2, 1])
    with center:
        st.markdown(f'<div style="width:200px; margin:auto; filter: invert(15%) sepia(95%) saturate(693%) hue-rotate(185deg) brightness(91%) contrast(101%);">{LOGO_SVG}</div>', unsafe_allow_html=True)
        u_in = st.text_input("Usuario")
        p_in = st.text_input("Contraseña", type="password")
        if st.button("ENTRAR", key="main_login_btn"):
            res = df_query("SELECT username, role, salt, pwd_hash FROM users WHERE username=?", (u_in,))
            if not res.empty:
                input_hash = hashlib.sha256((res.iloc[0]['salt'] + p_in).encode("utf-8")).hexdigest()
                if input_hash == res.iloc[0]['pwd_hash']:
                    st.session_state.auth = {"is_logged": True, "username": res.iloc[0]['username'], "role": res.iloc[0]['role']}
                    st.rerun()
            st.error("Credenciales incorrectas")
    st.stop()

# =========================
# 4. INTERFAZ PRINCIPAL
# =========================
with st.sidebar:
    st.markdown(f'<div class="sidebar-logo">{LOGO_SVG}</div>', unsafe_allow_html=True)
    st.write(f"👤 Sesión: **{st.session_state.auth['username']}**")
    st.write(f"🔑 Rol: **{st.session_state.auth['role'].upper()}**")
    if st.button("Cerrar Sesión", key="logout_btn"):
        st.session_state.auth = {"is_logged": False}
        st.rerun()

tabs = st.tabs(["✅ Generador", "🕒 Historial", "⚙️ Administración"])

# --- TAB ADMINISTRACIÓN ---
if st.session_state.auth["role"] == "admin":
    with tabs[2]:
        st.title("⚙️ Panel de Administración")
        
        # --- SECCIÓN USUARIOS ---
        st.subheader("👤 Gestión de Usuarios")
        users_df = df_query("SELECT id, username, role, created_at FROM users")
        st.dataframe(users_df, use_container_width=True)
        
        u_col1, u_col2 = st.columns(2)
        with u_col1:
            with st.expander("➕ Agregar Nuevo Usuario"):
                new_un = st.text_input("Username", key="add_u_name")
                new_pw = st.text_input("Password", type="password", key="add_u_pass")
                new_rl = st.selectbox("Rol", ["admin", "user"], key="add_u_role")
                if st.button("Registrar Usuario", key="btn_reg_u"):
                    s, ph = make_password_record(new_pw)
                    if exec_sql("INSERT INTO users(username, role, salt, pwd_hash, created_at) VALUES (?,?,?,?,?)", 
                                (new_un, new_rl, s, ph, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))):
                        st.success("Usuario creado"); time.sleep(0.5); st.rerun()
        
        with u_col2:
            if not users_df.empty:
                with st.expander("📝 Editar / Eliminar Usuario"):
                    u_to_edit = st.selectbox("Seleccionar usuario", users_df['username'].tolist(), key="sel_u_edit")
                    new_u_role = st.selectbox("Cambiar Rol", ["admin", "user"], key="edit_u_role_val")
                    
                    eb1, eb2 = st.columns(2)
                    if eb1.button("Actualizar Rol", key="btn_upd_u"):
                        exec_sql("UPDATE users SET role=? WHERE username=?", (new_u_role, u_to_edit))
                        st.rerun()
                    if eb2.button("🗑️ Eliminar Usuario", key="btn_del_u"):
                        if u_to_edit not in ["admin", "leslie_mejia"]:
                            exec_sql("DELETE FROM users WHERE username=?", (u_to_edit,))
                            st.rerun()
                        else: st.error("No puedes eliminar cuentas maestras.")

        st.divider()

        # --- SECCIÓN CATÁLOGOS Y TIPOS ---
        st.subheader("📊 Mantenimiento de Catálogos y Tipos")
        summary = df_query("""SELECT t.id, t.name as Nombre, t.code as Código, COUNT(o.id) as Posiciones 
                           FROM types t LEFT JOIN type_orders o ON t.id = o.type_id GROUP BY t.id""")
        
        c_col1, c_col2 = st.columns(2)
        with c_col1:
            with st.expander("📁 Gestionar Categorías"):
                cat_n = st.text_input("Nombre de Categoría", key="cat_name_in")
                cat_p = st.text_input("Prefijo (ej: home)", key="cat_pref_in")
                if st.button("Añadir Categoría", key="btn_add_cat"):
                    exec_sql("INSERT INTO categories(name, prefix) VALUES (?,?)", (cat_n, cat_p))
                    st.rerun()
                
                cats_list = df_query("SELECT name FROM categories")
                if not cats_list.empty:
                    cat_del = st.selectbox("Eliminar Categoría", cats_list['name'].tolist(), key="sel_cat_del")
                    if st.button(f"Borrar {cat_del}", key="btn_del_cat"):
                        exec_sql("DELETE FROM categories WHERE name=?", (cat_del,))
                        st.rerun()

        with c_col2:
            with st.expander("➕ Añadir Nuevo Tipo"):
                tn = st.text_input("Nombre (ej: Banner)", key="tn_final")
                tc = st.text_input("Código (ej: bn)", key="tc_final")
                tp = st.number_input("Posiciones iniciales", 1, 100, 5, key="tp_final")
                if st.button("Crear Tipo", key="btn_create_t"):
                    if exec_sql("INSERT INTO types(name, code) VALUES (?,?)", (tn, tc)):
                        tid = df_query("SELECT id FROM types WHERE code=?", (tc,)).iloc[0]['id']
                        for i in range(1, int(tp)+1): exec_sql("INSERT INTO type_orders(type_id, order_no) VALUES (?,?)", (tid, i))
                        st.rerun()

        if not summary.empty:
            st.write("**📝 Editar o Borrar Componente**")
            t_sel = st.selectbox("Seleccionar Componente", summary['Nombre'].tolist(), key="sel_t_manage")
            t_data = summary[summary['Nombre'] == t_sel].iloc[0]
            
            with st.expander(f"Editar: {t_sel}"):
                en = st.text_input("Nuevo Nombre", value=t_data['Nombre'], key="en_f")
                ec = st.text_input("Nuevo Código", value=t_data['Código'], key="ec_f")
                # BLINDAJE: max(1, ...) evita el error ValueBelowMinError
                ep = st.number_input("Cantidad de Posiciones", 1, 100, value=max(1, int(t_data['Posiciones'])), key="ep_f")
                
                if st.button("Actualizar Componente", key="btn_upd_t"):
                    exec_sql("UPDATE types SET name=?, code=? WHERE id=?", (en, ec, int(t_data['id'])))
                    curr_p = int(t_data['Posiciones'])
                    if ep > curr_p:
                        for i in range(curr_p + 1, int(ep) + 1): exec_sql("INSERT INTO type_orders(type_id, order_no) VALUES (?,?)", (int(t_data['id']), i))
                    elif ep < curr_p:
                        exec_sql("DELETE FROM type_orders WHERE type_id=? AND order_no > ?", (int(t_data['id']), int(ep)))
                    st.rerun()
            
            if st.button(f"❌ ELIMINAR TIPO: {t_sel}", key="btn_del_t_total"):
                exec_sql("DELETE FROM type_orders WHERE type_id=?", (int(t_data['id']),))
                exec_sql("DELETE FROM types WHERE id=?", (int(t_data['id']),))
                st.rerun()
