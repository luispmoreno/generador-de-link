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
        
        # Usuarios Base
        base_users = [
            ("admin", "admin", "admin123"),
            ("ula_corp_design", "admin", "Dcorp$26"),
            ("luis_pena", "user", "Lpena$2026")
        ]
        for user, role, pwd in base_users:
            cur.execute("SELECT 1 FROM users WHERE username=?", (user,))
            if not cur.fetchone():
                s, p = make_password_record(pwd)
                cur.execute("INSERT INTO users(username, role, salt, pwd_hash, created_at) VALUES (?,?,?,?,?)", (user, role, s, p, datetime.now().isoformat()))

def get_user(username: str):
    u = username.strip().lower()
    res = df_query("SELECT id, username, role, salt, pwd_hash FROM users WHERE lower(username) = ?", (u,))
    return res.iloc[0].to_dict() if not res.empty else None

# =========================
# Interfaz
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
            st.success("¡Link generado!")

# --- TAB HISTORIAL ---
with tabs[1]:
    st.subheader("Historial")
    hist = df_query("SELECT created_at as Fecha, country as Pais, hid_value as HID, final_url as URL FROM history ORDER BY id DESC")
    st.dataframe(hist, use_container_width=True)

# --- TAB ADMINISTRACIÓN (CORREGIDA) ---
with tabs[2]:
    if st.session_state.auth["role"] != "admin":
        st.error("🔒 Acceso restringido. Contacta al administrador principal.")
    else:
        st.title("⚙️ Panel de Seguridad")
        
        # 1. GESTIÓN DE USUARIOS
        st.subheader("👤 Usuarios")
        u_df = df_query("SELECT id, username, role FROM users")
        st.dataframe(u_df, use_container_width=True)
        
        u_sel = st.selectbox("Seleccionar Usuario para Gestionar", u_df['username'].tolist())
        
        # REGLAS DE ORO DE SEGURIDAD
        # Estos usuarios NO se pueden eliminar bajo ninguna circunstancia por nadie
        PROTECTED_USERS = ["admin", "ula_corp_design", "luis_pena"]
        
        col_sec1, col_sec2 = st.columns(2)
        
        with col_sec1:
            # SOLO EL ADMIN MAESTRO VE ESTA OPCIÓN
            if st.session_state.auth["username"] == "admin" and u_sel == "ula_corp_design":
                st.info(f"**Control de Acceso para {u_sel}**")
                current_role = u_df[u_df['username']==u_sel]['role'].iloc[0]
                new_role_val = st.radio("Permisos de Administración:", ["Habilitado (admin)", "Restringido (user)"], 
                                        index=0 if current_role == "admin" else 1)
                
                if st.button("✅ Aplicar Cambio de Rango"):
                    role_to_set = "admin" if "Habilitado" in new_role_val else "user"
                    exec_sql("UPDATE users SET role=? WHERE username=?", (role_to_set, u_sel))
                    st.success(f"Permisos de {u_sel} actualizados a {role_to_set}.")
                    st.rerun()
            else:
                st.write("Selecciona un usuario para ver opciones disponibles.")

        with col_sec2:
            if st.button("🗑️ Eliminar Registro"):
                if u_sel in PROTECTED_USERS:
                    st.error(f"🚫 PROHIBIDO: El usuario '{u_sel}' es una cuenta protegida del sistema.")
                else:
                    st.session_state.confirm_user_del = True

            if st.session_state.get('confirm_user_del'):
                st.warning(f"¿Confirmas que deseas eliminar a {u_sel} permanentemente?")
                if st.button("SÍ, ELIMINAR AHORA"):
                    exec_sql("DELETE FROM users WHERE username=?", (u_sel,))
                    st.success("Usuario eliminado.")
                    st.session_state.confirm_user_del = False
                    st.rerun()
                if st.button("CANCELAR"):
                    st.session_state.confirm_user_del = False
                    st.rerun()

        # 2. GESTIÓN DE CATÁLOGOS (CATEGORÍAS Y TIPOS)
        st.divider()
        st.subheader("📁 Mantenimiento de Catálogos")
        # (Aquí continúa el código de Categorías y Tipos con sus mensajes de éxito y confirmación...)
        c_col, t_col = st.columns(2)
        with c_col:
            st.write("**Nueva Categoría**")
            n_c = st.text_input("Nombre", key="nc")
            n_p = st.text_input("Prefijo", key="np")
            if st.button("Guardar"):
                exec_sql("INSERT INTO categories(name, prefix) VALUES (?,?)", (n_c, n_p))
                st.success("Guardado con éxito")
                st.rerun()
        with t_col:
            st.write("**Nuevo Tipo**")
            n_t = st.text_input("Nombre", key="nt")
            n_co = st.text_input("Código", key="ntc")
            n_pos = st.number_input("Posiciones", 1, 50, 5)
            if st.button("Crear"):
                exec_sql("INSERT INTO types(name, code) VALUES (?,?)", (n_t, n_co))
                tid = df_query("SELECT id FROM types WHERE code=?", (n_co,)).iloc[0]['id']
                for i in range(1, n_pos+1): exec_sql("INSERT INTO type_orders(type_id, order_no) VALUES (?,?)", (tid, i))
                st.success("Tipo creado exitosamente")
                st.rerun()
