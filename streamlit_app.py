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

# LOGO EN BLANCO PARA FONDO AZUL
UNICOMER_LOGO_WHITE = "https://grupounicomer.com/wp-content/uploads/2022/12/logo-sol-blanco.png"
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
        st.error("❌ Error: Ese nombre o código ya existe.")
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
        st.image("https://grupounicomer.com/wp-content/uploads/2022/12/logo-sol-gris.png", width=200)
        u_in = st.text_input("Usuario")
        p_in = st.text_input("Contraseña", type="password")
        if st.button("ENTRAR"):
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
    st.image(UNICOMER_LOGO_WHITE, width=150) # Logo blanco aplicado
    st.write(f"👤 **{st.session_state.auth['username']}**")
    if st.button("Cerrar Sesión"):
        st.session_state.auth = {"is_logged": False}
        st.rerun()

tabs = st.tabs(["✅ Generador", "🕒 Historial", "⚙️ Administración"])

# --- TAB ADMINISTRACIÓN ---
if st.session_state.auth["role"] == "admin":
    with tabs[2]:
        st.header("⚙️ Panel de Control Maestro")
        
        # 1. GESTIÓN DE USUARIOS (NUEVO)
        st.subheader("👤 Gestión de Usuarios")
        users_df = df_query("SELECT id, username, role, created_at FROM users")
        st.dataframe(users_df, use_container_width=True)
        
        u_col1, u_col2 = st.columns(2)
        with u_col1:
            with st.expander("➕ Crear Nuevo Usuario"):
                new_un = st.text_input("Username", key="add_un")
                new_pw = st.text_input("Password", type="password", key="add_pw")
                new_rl = st.selectbox("Rol", ["admin", "user"], key="add_rl")
                if st.button("Registrar Usuario"):
                    s, ph = make_password_record(new_pw)
                    exec_sql("INSERT INTO users(username, role, salt, pwd_hash, created_at) VALUES (?,?,?,?,?)", 
                             (new_un, new_rl, s, ph, datetime.now().isoformat()))
                    st.rerun()
        
        with u_col2:
            if not users_df.empty:
                with st.expander("📝 Editar / Eliminar Usuario"):
                    sel_u = st.selectbox("Seleccionar usuario", users_df['username'].tolist(), key="sel_u_manage")
                    u_data = users_df[users_df['username'] == sel_u].iloc[0]
                    
                    new_role = st.selectbox("Cambiar Rol", ["admin", "user"], index=0 if u_data['role'] == 'admin' else 1, key="edit_u_role")
                    
                    c_u1, c_u2 = st.columns(2)
                    if c_u1.button("Actualizar Rol"):
                        exec_sql("UPDATE users SET role=? WHERE username=?", (new_role, sel_u))
                        st.rerun()
                    if c_u2.button("🗑️ Eliminar Usuario"):
                        if sel_u not in ["admin", "leslie_mejia"]:
                            exec_sql("DELETE FROM users WHERE username=?", (sel_u,))
                            st.rerun()
                        else: st.error("No puedes eliminar administradores maestros")

        st.divider()

        # 2. GESTIÓN DE TIPOS Y CATÁLOGOS
        st.subheader("📊 Mantenimiento de Catálogos")
        summary = df_query("""SELECT t.id, t.name as Nombre, t.code as Código, COUNT(o.id) as Posiciones 
                           FROM types t LEFT JOIN type_orders o ON t.id = o.type_id GROUP BY t.id""")
        st.dataframe(summary[["Nombre", "Código", "Posiciones"]], use_container_width=True)

        col_left, col_right = st.columns(2)
        with col_left:
            with st.expander("📁 Categorías"):
                cat_n = st.text_input("Nombre Catálogo")
                cat_p = st.text_input("Prefijo")
                if st.button("Guardar Catálogo"):
                    exec_sql("INSERT INTO categories(name, prefix) VALUES (?,?)", (cat_n, cat_p))
                    st.rerun()

        with col_right:
            with st.expander("➕ Añadir Nuevo Tipo"):
                tn = st.text_input("Nombre Tipo", key="tn_new")
                tc = st.text_input("Código", key="tc_new")
                tp = st.number_input("Posiciones", 1, 50, 5, key="tp_new")
                if st.button("Crear"):
                    if exec_sql("INSERT INTO types(name, code) VALUES (?,?)", (tn, tc)):
                        tid = df_query("SELECT id FROM types WHERE code=?", (tc,)).iloc[0]['id']
                        for i in range(1, int(tp)+1): exec_sql("INSERT INTO type_orders(type_id, order_no) VALUES (?,?)", (tid, i))
                        st.rerun()

            if not summary.empty:
                st.write("**📝 Modificar / Eliminar Tipo**")
                t_sel = st.selectbox("Seleccionar Tipo", summary['Nombre'].tolist(), key="edit_t_list")
                t_row = summary[summary['Nombre'] == t_sel].iloc[0]
                
                with st.expander(f"Editar {t_sel}"):
                    en = st.text_input("Nuevo Nombre", value=t_row['Nombre'], key="en_val")
                    ec = st.text_input("Nuevo Código", value=t_row['Código'], key="ec_val")
                    # Proteccion contra ValueBelowMinError
                    ep = st.number_input("Cant. Posiciones", 1, 50, value=max(1, int(t_row['Posiciones'])), key="ep_val")
                    
                    if st.button("Aplicar Cambios"):
                        exec_sql("UPDATE types SET name=?, code=? WHERE id=?", (en, ec, int(t_row['id'])))
                        # Sincronización de posiciones
                        curr_p = int(t_row['Posiciones'])
                        if ep > curr_p:
                            for i in range(curr_p + 1, int(ep) + 1): exec_sql("INSERT INTO type_orders(type_id, order_no) VALUES (?,?)", (int(t_row['id']), i))
                        elif ep < curr_p:
                            exec_sql("DELETE FROM type_orders WHERE type_id=? AND order_no > ?", (int(t_row['id']), int(ep)))
                        st.rerun()
                
                if st.button(f"🗑️ Eliminar Tipo: {t_sel}", key="del_t_final"):
                    exec_sql("DELETE FROM type_orders WHERE type_id=?", (int(t_row['id']),))
                    exec_sql("DELETE FROM types WHERE id=?", (int(t_row['id']),))
                    st.rerun()
