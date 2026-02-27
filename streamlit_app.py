import streamlit as st
import sqlite3
import pandas as pd
import hashlib
import secrets
import time
from datetime import datetime
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse
from pathlib import Path

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
UNICOMER_LOGO_URL = "https://grupounicomer.com/wp-content/uploads/2022/12/logo-sol-gris.png"

st.markdown(f"""
<style>
    [data-testid="stSidebar"] {{ background-color: {UNICOMER_BLUE} !important; }}
    [data-testid="stSidebar"] * {{ color: white !important; }}
    .white-logo {{ filter: brightness(0) invert(1); width: 180px; margin-bottom: 20px; }}
    div.stButton > button {{
        background-color: {UNICOMER_YELLOW} !important;
        color: {UNICOMER_BLUE} !important;
        font-weight: bold; border: none; border-radius: 8px; width: 100%; height: 45px;
    }}
</style>
""", unsafe_allow_html=True)

def exec_sql(sql, params=()):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.cursor()
            cur.execute(sql, params)
            conn.commit()
            return True, "✅ Cambio aplicado exitosamente"
    except sqlite3.IntegrityError:
        return False, "❌ Error: El nombre o código ya existe"
    except Exception as e:
        return False, f"❌ Error: {str(e)}"

def df_query(sql, params=()):
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql_query(sql, conn, params=params)

# --- LOGIN --- (Omitido por brevedad, se mantiene igual)
if not st.session_state.auth["is_logged"]:
    # ... (Lógica de login anterior)
    st.stop()

# =========================
# 4. INTERFAZ
# =========================
with st.sidebar:
    st.markdown(f'<img src="{UNICOMER_LOGO_URL}" class="white-logo">', unsafe_allow_html=True)
    st.write(f"👤 **{st.session_state.auth['username']}**")
    if st.button("Cerrar Sesión"):
        st.session_state.auth = {"is_logged": False}
        st.rerun()

tabs = st.tabs(["✅ Generador", "🕒 Historial", "⚙️ Administración"])

# --- TAB ADMINISTRACIÓN ---
if st.session_state.auth["role"] == "admin":
    with tabs[2]:
        st.title("⚙️ Panel de Administración")
        
        # 1. USUARIOS
        st.subheader("👤 Gestión de Usuarios")
        users_df = df_query("SELECT id, username, role FROM users")
        st.dataframe(users_df, use_container_width=True)
        
        u_col1, u_col2 = st.columns(2)
        with u_col1:
            with st.expander("➕ Crear Nuevo Usuario"):
                new_u = st.text_input("Username", key="add_u")
                new_p = st.text_input("Password", type="password", key="add_p")
                if st.button("Registrar Usuario"):
                    salt = secrets.token_hex(16)
                    ph = hashlib.sha256((salt + new_p).encode("utf-8")).hexdigest()
                    ok, msg = exec_sql("INSERT INTO users(username, role, salt, pwd_hash) VALUES (?,?,?,?)", (new_u, 'user', salt, ph))
                    if ok: st.success(msg); time.sleep(1); st.rerun()
                    else: st.error(msg)

        with u_col2:
            if not users_df.empty:
                with st.expander("📝 Editar / Eliminar Usuario"):
                    sel_user = st.selectbox("Seleccionar usuario", users_df['username'].tolist(), key="s_u")
                    # AUTO-RELLENO DE ROL
                    curr_role = users_df[users_df['username'] == sel_user]['role'].iloc[0]
                    new_role = st.selectbox("Cambiar Rol", ["admin", "user"], index=0 if curr_role == 'admin' else 1)
                    
                    if st.button("Actualizar Rol"):
                        ok, msg = exec_sql("UPDATE users SET role=? WHERE username=?", (new_role, sel_user))
                        if ok: st.success(msg); time.sleep(1); st.rerun()
                        else: st.error(msg)
                    
                    if st.button("🗑️ Eliminar Usuario"):
                        if sel_user not in ['admin', 'leslie_mejia']:
                            ok, msg = exec_sql("DELETE FROM users WHERE username=?", (sel_user,))
                            if ok: st.success(msg); time.sleep(1); st.rerun()
                        else: st.error("No puedes eliminar administradores maestros")

        st.divider()
        
        # 2. TABLA RESUMEN DE TIPOS
        st.subheader("📊 Resumen de Tipos y Posiciones")
        summary = df_query("""SELECT t.id, t.name as Nombre, t.code as Código, COUNT(o.id) as Posiciones 
                           FROM types t LEFT JOIN type_orders o ON t.id = o.type_id GROUP BY t.id""")
        st.dataframe(summary[["Nombre", "Código", "Posiciones"]], use_container_width=True)

        st.divider()

        # 3. MANTENIMIENTO
        st.subheader("🛠️ Mantenimiento de Catálogos")
        col_cat, col_typ = st.columns(2)
        
        with col_cat:
            with st.expander("📁 Categorías (Editar/Borrar)"):
                cats_df = df_query("SELECT * FROM categories")
                if not cats_df.empty:
                    sel_cat = st.selectbox("Seleccionar Categoría", cats_df['name'].tolist())
                    cat_data = cats_df[cats_df['name'] == sel_cat].iloc[0]
                    
                    # AUTO-RELLENO DE CATEGORÍA
                    edit_cat_n = st.text_input("Editar Nombre", value=cat_data['name'])
                    edit_cat_p = st.text_input("Editar Prefijo", value=cat_data['prefix'])
                    
                    if st.button("Actualizar Categoría"):
                        ok, msg = exec_sql("UPDATE categories SET name=?, prefix=? WHERE id=?", (edit_cat_n, edit_cat_p, int(cat_data['id'])))
                        if ok: st.success(msg); time.sleep(1); st.rerun()
                        else: st.error(msg)
                    
                    if st.button("🗑️ Borrar Categoría"):
                        ok, msg = exec_sql("DELETE FROM categories WHERE id=?", (int(cat_data['id']),))
                        if ok: st.success(msg); time.sleep(1); st.rerun()

        with col_typ:
            if not summary.empty:
                with st.expander("📝 Editar / Borrar Tipo"):
                    sel_type = st.selectbox("Seleccionar Tipo", summary['Nombre'].tolist(), key="sel_t_edit")
                    t_data = summary[summary['Nombre'] == sel_type].iloc[0]
                    
                    # AUTO-RELLENO DE TIPO
                    new_tn = st.text_input("Nuevo Nombre Tipo", value=t_data['Nombre'], key="edit_tn")
                    new_tc = st.text_input("Nuevo Código", value=t_data['Código'], key="edit_tc")
                    # Blindaje contra ValueBelowMinError
                    new_tp = st.number_input("Cantidad de Posiciones", 1, 100, value=max(1, int(t_data['Posiciones'])), key="edit_tp")
                    
                    if st.button("Actualizar Tipo"):
                        ok, msg = exec_sql("UPDATE types SET name=?, code=? WHERE id=?", (new_tn, new_tc, int(t_data['id'])))
                        if ok:
                            # Sincronizar posiciones
                            curr = int(t_data['Posiciones'])
                            if new_tp > curr:
                                for i in range(curr + 1, int(new_tp) + 1):
                                    exec_sql("INSERT INTO type_orders(type_id, order_no) VALUES (?,?)", (int(t_data['id']), i))
                            elif new_tp < curr:
                                exec_sql("DELETE FROM type_orders WHERE type_id=? AND order_no > ?", (int(t_data['id']), int(new_tp)))
                            st.success(msg); time.sleep(1); st.rerun()
                        else: st.error(msg)

                    if st.button(f"🗑️ Eliminar Tipo: {sel_type}"):
                        exec_sql("DELETE FROM type_orders WHERE type_id=?", (int(t_data['id']),))
                        ok, msg = exec_sql("DELETE FROM types WHERE id=?", (int(t_data['id']),))
                        if ok: st.success(msg); time.sleep(1); st.rerun()

# --- TAB GENERADOR Y HISTORIAL --- (Se mantienen con la lógica recuperada anteriormente)
# ...
