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
    [data-testid="stSidebar"] img {{ filter: brightness(0) invert(1); }} 
    
    div.stButton > button {{
        background-color: {UNICOMER_YELLOW} !important;
        color: {UNICOMER_BLUE} !important;
        font-weight: bold; border: none; border-radius: 8px; width: 100%;
        height: 45px;
    }}
</style>
""", unsafe_allow_html=True)

# =========================
# Lógica de Datos
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
        
        master_users = [
            ("admin", "admin", "admin123"),
            ("ula_corp_design", "admin", "Dcorp$26")
        ]
        for u, r, p in master_users:
            s, ph = make_password_record(p)
            cur.execute("INSERT OR IGNORE INTO users(username, role, salt, pwd_hash, created_at) VALUES (?,?,?,?,?)", 
                       (u, r, s, ph, datetime.now().isoformat()))

init_db()

# =========================
# Auth y Sesión
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
            else: st.error("Acceso denegado")
    st.stop()

with st.sidebar:
    st.image(UNICOMER_LOGO, width=150)
    st.write(f"👤 Sesión: **{st.session_state.auth['username']}**")
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
        url_base = st.text_input("URL base", placeholder="https://unicomer.com...")
    
    c1, c2, c3 = st.columns(3)
    pais = c1.selectbox("País", ["SV", "GT", "CR", "HN", "NI", "PA", "DO", "JM", "TT"])
    cats_df = df_query("SELECT id, name, prefix FROM categories")
    cat_options = [f"{r.name} ({r.prefix})" for r in cats_df.itertuples()] if not cats_df.empty else ["N/A"]
    cat_sel = c2.selectbox("Categoría", cat_options)
    
    types_df = df_query("SELECT id, name, code FROM types")
    type_options = [f"{r.name} ({r.code})" for r in types_df.itertuples()] if not types_df.empty else ["N/A"]
    type_sel = c3.selectbox("Tipo", type_options)
    
    if "(" in type_sel and "(" in cat_sel:
        t_code = type_sel.split("(")[1].replace(")", "")
        t_id_row = types_df[types_df['code'] == t_code]
        if not t_id_row.empty:
            t_id = int(t_id_row['id'].values[0])
            ord_df = df_query("SELECT order_no FROM type_orders WHERE type_id=? ORDER BY order_no", (t_id,))
            pos = st.selectbox("Posición", ord_df['order_no'].tolist() if not ord_df.empty else [1])
            
            if st.button("GENERAR ID Y LINK"):
                pref = cat_sel.split("(")[1].replace(")", "")
                hid = f"{pref}_{t_code}_{pos}"
                p_url = urlparse(url_base.strip())
                qs = dict(parse_qsl(p_url.query)); qs['hid'] = hid
                final_url = urlunparse(p_url._replace(query=urlencode(qs)))
                exec_sql("INSERT INTO history (created_at, base_url, final_url, country, type_code, order_value, hid_value) VALUES (?,?,?,?,?,?,?)",
                        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), url_base, final_url, pais, t_code, str(pos), hid))
                
                st.success(f"¡Link generado con éxito! ID: {hid}")
                st.code(final_url)
                components.html(f"""
                    <button onclick="navigator.clipboard.writeText('{final_url}'); this.innerText='¡COPIADO!'; setTimeout(()=>{{this.innerText='📋 COPIAR LINK'}}, 2000)" 
                    style="width:100%; background:{UNICOMER_YELLOW}; border:none; height:45px; border-radius:8px; font-weight:bold; cursor:pointer; color:{UNICOMER_BLUE}; font-family:sans-serif;">
                    📋 COPIAR LINK
                    </button>
                """, height=50)

# =========================
# TAB ADMINISTRACIÓN
# =========================
with tabs[2]:
    if st.session_state.auth["role"] != "admin":
        st.error("🔒 Acceso Restringido.")
    else:
        st.subheader("👤 Usuarios y Seguridad")
        u_df = df_query("SELECT username, role FROM users")
        st.dataframe(u_df, use_container_width=True)
        
        u_sel = st.selectbox("Usuario a gestionar", u_df['username'].tolist())
        actual_role = u_df[u_df['username'] == u_sel]['role'].iloc[0]
        
        col_u1, col_u2 = st.columns(2)
        with col_u1:
            with st.expander("➕ Registrar Nuevo"):
                n_u = st.text_input("Username", key="reg_u")
                n_p = st.text_input("Password", type="password", key="reg_p")
                if st.button("Crear Usuario"):
                    if n_u and n_p:
                        s, ph = make_password_record(n_p)
                        exec_sql("INSERT OR IGNORE INTO users(username, role, salt, pwd_hash, created_at) VALUES (?,?,?,?,?)", (n_u, "user", s, ph, datetime.now().isoformat()))
                        st.toast(f"✅ Usuario {n_u} creado correctamente")
                        time.sleep(1); st.rerun()
            
            st.write("---")
            is_adm = st.toggle("Permitir edición (Admin)", value=(actual_role == "admin"), key="tgl_adm")
            if st.button("Aplicar Rango"):
                exec_sql("UPDATE users SET role=? WHERE username=?", ("admin" if is_adm else "user", u_sel))
                st.toast(f"✅ Rango de {u_sel} actualizado")
                time.sleep(1); st.rerun()

        with col_u2:
            with st.expander("🔑 Cambiar Contraseña"):
                new_pw_val = st.text_input("Nueva contraseña", type="password")
                if st.button("Actualizar Password"):
                    if new_pw_val:
                        s, ph = make_password_record(new_pw_val)
                        exec_sql("UPDATE users SET salt=?, pwd_hash=? WHERE username=?", (s, ph, u_sel))
                        st.toast("✅ Contraseña actualizada")

            if st.button("🗑️ Eliminar Usuario"):
                if u_sel in ["admin", "ula_corp_design"]: st.error("No puedes eliminar esta cuenta")
                else:
                    exec_sql("DELETE FROM users WHERE username=?", (u_sel,))
                    st.toast("🗑️ Usuario eliminado")
                    time.sleep(1); st.rerun()

        st.divider()

        # --- SECCIÓN CATÁLOGOS ---
        st.subheader("📁 Mantenimiento de Catálogos")
        c_left, c_right = st.columns(2)
        
        with c_left:
            st.write("**Categorías**")
            with st.expander("➕ Añadir"):
                cat_n = st.text_input("Nombre", key="add_cn")
                cat_p = st.text_input("Prefijo", key="add_cp")
                if st.button("Guardar Categoría"):
                    exec_sql("INSERT INTO categories(name, prefix) VALUES (?,?)", (cat_n, cat_p))
                    st.toast("✅ Categoría guardada")
                    time.sleep(1); st.rerun()
            
            if not cats_df.empty:
                st.write("---")
                c_sel_ed = st.selectbox("Editar/Borrar", cats_df['name'].tolist(), key="sb_cat")
                row_c = cats_df[cats_df['name'] == c_sel_ed].iloc[0]
                with st.expander("📝 Editar Seleccionada"):
                    ed_cn = st.text_input("Nuevo Nombre", value=row_c['name'], key="e_cn")
                    ed_cp = st.text_input("Nuevo Prefijo", value=row_c['prefix'], key="e_cp")
                    if st.button("Actualizar"):
                        exec_sql("UPDATE categories SET name=?, prefix=? WHERE id=?", (ed_cn, ed_cp, int(row_c['id'])))
                        st.toast("✅ Categoría actualizada")
                        time.sleep(1); st.rerun()
                if st.button("❌ Borrar Categoría"):
                    exec_sql("DELETE FROM categories WHERE id=?", (int(row_c['id']),))
                    st.rerun()

        with c_right:
            st.write("**Tipos**")
            with st.expander("➕ Añadir"):
                tp_n = st.text_input("Nombre", key="add_tn")
                tp_c = st.text_input("Código", key="add_tc")
                tp_o = st.number_input("Posiciones", 1, 50, 5)
                if st.button("Crear Tipo"):
                    exec_sql("INSERT INTO types(name, code) VALUES (?,?)", (tp_n, tp_c))
                    new_id = df_query("SELECT id FROM types WHERE code=?", (tp_c,)).iloc[0]['id']
                    for i in range(1, int(tp_o)+1): exec_sql("INSERT INTO type_orders(type_id, order_no) VALUES (?,?)", (new_id, i))
                    st.toast(f"✅ Tipo {tp_n} creado")
                    time.sleep(1); st.rerun()

            if not types_df.empty:
                st.write("---")
                t_sel_ed = st.selectbox("Editar/Borrar", types_df['name'].tolist(), key="sb_tp")
                row_t = types_df[types_df['name'] == t_sel_ed].iloc[0]
                tid = int(row_t['id'])
                
                # CORRECCIÓN DEL ERROR: Validamos que el conteo no sea 0
                current_count = len(df_query("SELECT id FROM type_orders WHERE type_id=?", (tid,)))
                safe_val = max(1, current_count) 
                
                with st.expander("📝 Editar Seleccionado"):
                    ed_tn = st.text_input("Nuevo Nombre", value=row_t['name'], key="e_tn")
                    ed_tc = st.text_input("Nuevo Código", value=row_t['code'], key="e_tc")
                    ed_to = st.number_input("Posiciones", 1, 50, value=safe_val, key="e_to")
                    if st.button("Actualizar Tipo"):
                        exec_sql("UPDATE types SET name=?, code=? WHERE id=?", (ed_tn, ed_tc, tid))
                        if ed_to > current_count:
                            for i in range(current_count + 1, int(ed_to) + 1):
                                exec_sql("INSERT INTO type_orders(type_id, order_no) VALUES (?,?)", (tid, i))
                        elif ed_to < current_count:
                            exec_sql("DELETE FROM type_orders WHERE type_id=? AND order_no > ?", (tid, int(ed_to)))
                        st.toast("✅ Tipo y Posiciones actualizados")
                        time.sleep(1); st.rerun()
                if st.button("❌ Borrar Tipo"):
                    exec_sql("DELETE FROM type_orders WHERE type_id=?", (tid,))
                    exec_sql("DELETE FROM types WHERE id=?", (tid,))
                    st.rerun()
