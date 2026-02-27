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
# Configuración Básica
# =========================
APP_TITLE = "Generador de IDs - Unicomer"
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = str(BASE_DIR / "links.db")

UNICOMER_LOGO = "https://grupounicomer.com/wp-content/uploads/2022/12/logo-sol-gris.png"
UNICOMER_BLUE = "#002d5a"
UNICOMER_YELLOW = "#fdbb2d"
FIGMA_HOME_URL = "https://www.figma.com/design/ihSTaMfAmyN99BN5Z6sNps/Home-ULA?node-id=0-1&p=f"

# =========================
# Lógica de Datos y Seguridad
# =========================
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
    return sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)

def df_query(sql, params=()):
    with get_conn() as conn:
        return pd.read_sql_query(sql, conn, params=params)

def exec_sql(sql, params=()):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(sql, params)
        conn.commit()

def init_db():
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, role TEXT, salt TEXT, pwd_hash TEXT, created_at TEXT);")
        cur.execute("CREATE TABLE IF NOT EXISTS categories (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, prefix TEXT);")
        cur.execute("CREATE TABLE IF NOT EXISTS types (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, code TEXT);")
        cur.execute("CREATE TABLE IF NOT EXISTS type_orders (id INTEGER PRIMARY KEY AUTOINCREMENT, type_id INTEGER, order_no INTEGER);")
        cur.execute("CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT, base_url TEXT, final_url TEXT, country TEXT, type_code TEXT, order_value TEXT, hid_value TEXT);")
        
        # Admin Maestro
        cur.execute("SELECT 1 FROM users WHERE username='admin'")
        if not cur.fetchone():
            s, p = make_password_record("admin123")
            cur.execute("INSERT INTO users(username, role, salt, pwd_hash, created_at) VALUES (?,?,?,?,?)", ("admin", "admin", s, p, datetime.now().isoformat()))
        
        # Admin Design Corp
        cur.execute("SELECT 1 FROM users WHERE username='ula_corp_design'")
        if not cur.fetchone():
            s, p = make_password_record("Dcorp$26")
            cur.execute("INSERT INTO users(username, role, salt, pwd_hash, created_at) VALUES (?,?,?,?,?)", ("ula_corp_design", "admin", s, p, datetime.now().isoformat()))

def get_user(username: str):
    u = username.strip().lower()
    res = df_query("SELECT id, username, role, salt, pwd_hash FROM users WHERE lower(username) = ?", (u,))
    return res.iloc[0].to_dict() if not res.empty else None

# =========================
# Interfaz Adaptativa
# =========================
st.set_page_config(page_title=APP_TITLE, layout="wide")

st.markdown(f"""
<style>
    [data-testid="stSidebar"] {{ background-color: {UNICOMER_BLUE} !important; }}
    [data-testid="stSidebar"] * {{ color: white !important; }}
    div.stButton > button {{
        background-color: {UNICOMER_YELLOW} !important;
        color: {UNICOMER_BLUE} !important;
        font-weight: bold; border: none; border-radius: 8px;
    }}
    .figma-box {{
        padding: 15px; border-radius: 12px; border: 2px solid #ff4b4b;
        background-color: rgba(255, 75, 75, 0.05); text-align: center; margin-bottom: 20px;
    }}
</style>
""", unsafe_allow_html=True)

init_db()

if "auth" not in st.session_state:
    st.session_state.auth = {"is_logged": False, "username": None, "role": None}

# --- LOGIN ---
if not st.session_state.auth["is_logged"]:
    _, center, _ = st.columns([1, 2, 1])
    with center:
        st.markdown(f"<div style='text-align:center; margin-top:50px;'><img src='{UNICOMER_LOGO}' width='200'></div>", unsafe_allow_html=True)
        u_input = st.text_input("Usuario")
        p_input = st.text_input("Contraseña", type="password")
        if st.button("ENTRAR"):
            user_data = get_user(u_input)
            if user_data and verify_password(p_input, user_data["salt"], user_data["pwd_hash"]):
                st.session_state.auth = {"is_logged": True, "username": user_data["username"], "role": user_data["role"]}
                st.rerun()
            else: st.error("Acceso denegado")
    st.stop()

# --- SIDEBAR ---
with st.sidebar:
    st.image(UNICOMER_LOGO, width=120)
    st.write(f"👤 **{st.session_state.auth['username']}**")
    if st.button("Cerrar Sesión"):
        st.session_state.auth = {"is_logged": False, "username": None, "role": None}
        st.rerun()

tabs = st.tabs(["✅ Generador", "🕒 Historial", "⚙️ Administración"])

# --- TAB GENERADOR ---
with tabs[0]:
    col_main, col_figma = st.columns([2, 1])
    with col_main:
        st.title("🔗 Generador de Links")
        base_url = st.text_input("URL base del sitio", placeholder="https://...")
    with col_figma:
        st.markdown(f"""<div class="figma-box"><p style="font-weight:bold;">Mapa Visual Home</p>
            <a href="{FIGMA_HOME_URL}" target="_blank"><button style="width:100%;background:#A259FF;color:white;border:none;padding:10px;border-radius:8px;cursor:pointer;font-weight:bold;">🎨 FIGMA: VER BLOQUES</button></a>
            </div>""", unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    with c1: country = st.selectbox("País", ["SV", "GT", "CR", "HN", "NI", "PA", "DO", "JM", "TT"])
    with c2:
        cats = df_query("SELECT name, prefix FROM categories")
        cat_sel = st.selectbox("Categoría", [f"{r.name} ({r.prefix})" for r in cats.itertuples()]) if not cats.empty else "N/A"
    with c3:
        types = df_query("SELECT id, name, code FROM types")
        type_sel = st.selectbox("Tipo", [f"{r.name} ({r.code})" for r in types.itertuples()]) if not types.empty else "N/A"

    if "(" in str(type_sel):
        t_code = type_sel.split("(")[1].replace(")", "")
        t_id = int(types[types['code'] == t_code]['id'].values[0])
        orders = df_query("SELECT order_no FROM type_orders WHERE type_id=? ORDER BY order_no", (t_id,))
        pos = st.selectbox("Posición", orders['order_no'].tolist() if not orders.empty else [1])
        if st.button("GENERAR ID"):
            pref = cat_sel.split("(")[1].replace(")", "")
            hid = f"{pref}_{t_code}_{pos}"
            parsed = urlparse(base_url.strip())
            qs = dict(parse_qsl(parsed.query)); qs['hid'] = hid
            final_url = urlunparse(parsed._replace(query=urlencode(qs)))
            exec_sql("INSERT INTO history (created_at, base_url, final_url, country, type_code, order_value, hid_value) VALUES (?,?,?,?,?,?,?)",
                    (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), base_url, final_url, country, t_code, str(pos), hid))
            st.code(final_url)
            st.success("¡Link generado con éxito!")
            components.html(f"<button onclick=\"navigator.clipboard.writeText('{final_url}'); alert('Copiado');\" style=\"width:100%; background:{UNICOMER_YELLOW}; border:none; padding:12px; border-radius:8px; font-weight:bold; cursor:pointer;\">📋 COPIAR LINK</button>", height=60)

# --- TAB HISTORIAL ---
with tabs[1]:
    st.subheader("Historial")
    hist = df_query("SELECT created_at as Fecha, country as Pais, hid_value as HID, final_url as URL FROM history ORDER BY id DESC")
    st.dataframe(hist, use_container_width=True)

# --- TAB ADMINISTRACIÓN ---
with tabs[2]:
    if st.session_state.auth["role"] != "admin":
        st.error("🔒 Acceso restringido")
    else:
        st.title("⚙️ Panel de Control")
        
        # --- SECCIÓN USUARIOS ---
        st.subheader("👤 Usuarios y Permisos")
        u_df = df_query("SELECT id, username, role FROM users")
        st.dataframe(u_df, use_container_width=True)
        
        u_sel = st.selectbox("Seleccionar Usuario", u_df['username'].tolist())
        is_protected = u_sel in ["admin", "ula_corp_design"]
        
        col_u1, col_u2 = st.columns(2)
        with col_u1:
            if u_sel == "ula_corp_design" and st.session_state.auth["username"] == "admin":
                status = "Activo" if u_df[u_df['username']=="ula_corp_design"]['role'].iloc[0] == "admin" else "Inactivo"
                st.write(f"Estado Admin de {u_sel}: **{status}**")
                if st.button("🔄 Alternar Permisos Admin"):
                    new_r = "user" if status == "Activo" else "admin"
                    exec_sql("UPDATE users SET role=? WHERE username=?", (new_r, u_sel))
                    st.success(f"Cambio aplicado: {u_sel} ahora es {new_r}")
                    st.rerun()
        
        with col_u2:
            if st.button("🗑️ Eliminar Usuario"):
                if is_protected:
                    st.error("⚠️ Error: Este usuario es del sistema y no puede eliminarse.")
                else:
                    st.session_state.confirm_del_user = True

            if st.session_state.get('confirm_del_user'):
                st.warning(f"¿Seguro que deseas eliminar a {u_sel}?")
                c_del1, c_del2 = st.columns(2)
                if c_del1.button("SÍ, ELIMINAR"):
                    exec_sql("DELETE FROM users WHERE username=?", (u_sel,))
                    st.success("Usuario eliminado correctamente.")
                    st.session_state.confirm_del_user = False
                    st.rerun()
                if c_del2.button("CANCELAR"):
                    st.session_state.confirm_del_user = False
                    st.rerun()

        # --- SECCIÓN CATÁLOGOS ---
        st.divider()
        st.subheader("📁 Categorías y Tipos")
        c_col, t_col = st.columns(2)
        
        with c_col:
            st.write("**Nueva Categoría**")
            n_c = st.text_input("Nombre (ej: Home)", key="nc")
            n_p = st.text_input("Prefijo (ej: hm)", key="np")
            if st.button("Guardar Categoría"):
                if n_c and n_p:
                    exec_sql("INSERT INTO categories(name, prefix) VALUES (?,?)", (n_c, n_p))
                    st.success(f"Categoría '{n_c}' guardada con éxito.")
                    st.rerun()
                else: st.warning("Completa ambos campos.")

        with t_col:
            st.write("**Nuevo Tipo de Componente**")
            n_t = st.text_input("Nombre (ej: Banner)", key="nt")
            n_co = st.text_input("Código (ej: bn)", key="ntc")
            n_pos = st.number_input("Posiciones iniciales", 1, 50, 5)
            if st.button("Guardar Tipo"):
                if n_t and n_co:
                    exec_sql("INSERT INTO types(name, code) VALUES (?,?)", (n_t, n_co))
                    tid = df_query("SELECT id FROM types WHERE code=?", (n_co,)).iloc[0]['id']
                    for i in range(1, n_pos+1): exec_sql("INSERT INTO type_orders(type_id, order_no) VALUES (?,?)", (tid, i))
                    st.success(f"Tipo '{n_t}' y sus {n_pos} posiciones guardados.")
                    st.rerun()
                else: st.warning("Completa los campos.")

        # --- EDICIÓN / ELIMINACIÓN DE CATÁLOGOS ---
        st.divider()
        st.write("**Gestión de registros existentes**")
        edit_col1, edit_col2 = st.columns(2)
        
        with edit_col1:
            if not cats.empty:
                c_to_del = st.selectbox("Borrar Categoría", cats['name'].tolist())
                if st.button("🗑️ Borrar Seleccionada"):
                    st.session_state.confirm_del_cat = True
                
                if st.session_state.get('confirm_del_cat'):
                    st.error(f"¿Borrar la categoría '{c_to_del}'?")
                    if st.button("CONFIRMAR BORRADO"):
                        exec_sql("DELETE FROM categories WHERE name=?", (c_to_del,))
                        st.success("Categoría eliminada.")
                        st.session_state.confirm_del_cat = False
                        st.rerun()

        with edit_col2:
            if not types.empty:
                t_to_del = st.selectbox("Borrar Tipo", types['name'].tolist())
                if st.button("🗑️ Borrar Tipo Seleccionado"):
                    st.session_state.confirm_del_type = True
                
                if st.session_state.get('confirm_del_type'):
                    st.error(f"¿Borrar el tipo '{t_to_del}' y todas sus posiciones?")
                    if st.button("CONFIRMAR BORRADO TIPO"):
                        tid_del = int(types[types['name'] == t_to_del]['id'].values[0])
                        exec_sql("DELETE FROM type_orders WHERE type_id=?", (tid_del,))
                        exec_sql("DELETE FROM types WHERE id=?", (tid_del,))
                        st.success("Tipo eliminado por completo.")
                        st.session_state.confirm_del_type = False
                        st.rerun()
