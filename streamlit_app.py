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
        
        # Admin Corp Design (Se crea como admin por defecto)
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
    .brand-logo {{ filter: drop-shadow(0px 0px 2px rgba(255,255,255,0.3)); }}
</style>
""", unsafe_allow_html=True)

init_db()

if "auth" not in st.session_state:
    st.session_state.auth = {"is_logged": False, "username": None, "role": None}

# --- LOGIN ---
if not st.session_state.auth["is_logged"]:
    _, center, _ = st.columns([1, 2, 1])
    with center:
        st.markdown(f"<div style='text-align:center; margin-top:50px;'><img src='{UNICOMER_LOGO}' width='200' class='brand-logo'></div>", unsafe_allow_html=True)
        u_input = st.text_input("Usuario")
        p_input = st.text_input("Contraseña", type="password")
        if st.button("ENTRAR"):
            user_data = get_user(u_input)
            if user_data and verify_password(p_input, user_data["salt"], user_data["pwd_hash"]):
                st.session_state.auth = {"is_logged": True, "username": user_data["username"], "role": user_data["role"]}
                st.rerun()
            else:
                st.error("Credenciales incorrectas")
    st.stop()

# --- SIDEBAR ---
with st.sidebar:
    st.image(UNICOMER_LOGO, width=120)
    st.divider()
    st.write(f"👤 Usuario: **{st.session_state.auth['username']}**")
    st.write(f"🔑 Rol: **{st.session_state.auth['role'].upper()}**")
    if st.button("Cerrar Sesión"):
        st.session_state.auth = {"is_logged": False, "username": None, "role": None}
        st.rerun()

st.markdown(f"<div style='text-align:right;'><img src='{UNICOMER_LOGO}' width='150' class='brand-logo'></div>", unsafe_allow_html=True)
tabs = st.tabs(["✅ Generador", "🕒 Historial", "⚙️ Administración"])

# --- TAB GENERADOR ---
with tabs[0]:
    col_t, col_f = st.columns([2, 1])
    with col_t:
        st.title("🔗 Generador de Links")
        base_url = st.text_input("URL base del sitio", placeholder="https://...")
    with col_f:
        st.markdown(f"""<div class="figma-box"><p style="font-weight:bold;margin-bottom:10px;">Guía Visual Home</p>
            <a href="{FIGMA_HOME_URL}" target="_blank"><button style="width:100%;background:#A259FF;color:white;border:none;padding:10px;border-radius:8px;cursor:pointer;font-weight:bold;">🎨 ABRIR FIGMA</button></a>
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
        if st.button("GENERAR"):
            pref = cat_sel.split("(")[1].replace(")", "")
            hid = f"{pref}_{t_code}_{pos}"
            parsed = urlparse(base_url.strip())
            qs = dict(parse_qsl(parsed.query)); qs['hid'] = hid
            final_url = urlunparse(parsed._replace(query=urlencode(qs)))
            exec_sql("INSERT INTO history (created_at, base_url, final_url, country, type_code, order_value, hid_value) VALUES (?,?,?,?,?,?,?)",
                    (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), base_url, final_url, country, t_code, str(pos), hid))
            st.success(f"ID: {hid}")
            st.code(final_url)
            components.html(f"<button onclick=\"navigator.clipboard.writeText('{final_url}'); alert('Copiado');\" style=\"width:100%; background:{UNICOMER_YELLOW}; color:{UNICOMER_BLUE}; border:none; padding:12px; border-radius:8px; font-weight:bold; cursor:pointer;\">📋 COPIAR LINK</button>", height=60)

# --- TAB HISTORIAL ---
with tabs[1]:
    st.subheader("Historial de Generaciones")
    hist = df_query("SELECT created_at as Fecha, country as Pais, hid_value as HID, final_url as URL FROM history ORDER BY id DESC")
    if not hist.empty:
        buf = io.BytesIO()
        try:
            with pd.ExcelWriter(buf, engine='xlsxwriter') as wr: hist.to_excel(wr, index=False)
            st.download_button("📥 Descargar Reporte Excel", buf.getvalue(), "historial.xlsx")
        except: st.warning("Instale 'xlsxwriter' para habilitar descargas.")
        st.dataframe(hist, use_container_width=True)

# --- TAB ADMINISTRACIÓN ---
with tabs[2]:
    if st.session_state.auth["role"] != "admin":
        st.error("🔒 Acceso restringido a administradores.")
    else:
        st.title("⚙️ Gestión del Sistema")
        
        # 1. GESTIÓN DE USUARIOS
        st.subheader("👤 Usuarios")
        u_df = df_query("SELECT id, username, role FROM users")
        st.dataframe(u_df, use_container_width=True)
        
        with st.expander("➕ / 📝 Editar Usuarios"):
            col1, col2 = st.columns(2)
            with col1:
                st.write("**Nuevo Usuario**")
                nu = st.text_input("Username", key="nu")
                np = st.text_input("Password", type="password", key="np")
                if st.button("Guardar Nuevo"):
                    s, p = make_password_record(np)
                    exec_sql("INSERT INTO users(username, role, salt, pwd_hash) VALUES (?,?,?,?)", (nu, "user", s, p))
                    st.rerun()
            with col2:
                st.write("**Editar/Eliminar**")
                u_sel = st.selectbox("Usuario", u_df['username'].tolist())
                
                # Bloqueo de eliminación para admins críticos
                is_protected = u_sel in ["admin", "ula_corp_design"]
                
                # Control de Rango (Solo disponible para el admin principal sobre ula_corp_design)
                if u_sel == "ula_corp_design" and st.session_state.auth["username"] == "admin":
                    new_role = st.radio("Herramientas Admin:", ["Activado (admin)", "Desactivado (user)"], index=0 if u_df[u_df['username']=="ula_corp_design"]['role'].iloc[0] == "admin" else 1)
                    if st.button("Cambiar Permisos"):
                        role_val = "admin" if "Activado" in new_role else "user"
                        exec_sql("UPDATE users SET role=? WHERE username=?", (role_val, u_sel))
                        st.success(f"Permisos de {u_sel} actualizados.")
                        st.rerun()

                new_un = st.text_input("Nuevo nombre", value=u_sel)
                new_up = st.text_input("Nueva pass (vacío = sin cambios)", type="password")
                
                ca, cb = st.columns(2)
                if ca.button("Actualizar Datos"):
                    if new_up:
                        s, p = make_password_record(new_up)
                        exec_sql("UPDATE users SET username=?, salt=?, pwd_hash=? WHERE username=?", (new_un, s, p, u_sel))
                    else: exec_sql("UPDATE users SET username=? WHERE username=?", (new_un, u_sel))
                    st.rerun()
                
                if cb.button("🗑️ Eliminar"):
                    if is_protected:
                        st.error("Este usuario es crítico y no puede eliminarse.")
                    else:
                        exec_sql("DELETE FROM users WHERE username=?", (u_sel,))
                        st.rerun()

        # 2. CATÁLOGO (CATEGORÍAS)
        st.divider()
        st.subheader("📁 Catálogo (Categorías)")
        c_df = df_query("SELECT * FROM categories")
        st.dataframe(c_df, use_container_width=True)
        with st.expander("📝 Gestionar Categorías"):
            col1, col2 = st.columns(2)
            with col1:
                st.write("**Añadir**")
                acn = st.text_input("Nombre Cat"); acp = st.text_input("Prefijo Cat")
                if st.button("Añadir Categoría"):
                    exec_sql("INSERT INTO categories(name, prefix) VALUES (?,?)", (acn, acp)); st.rerun()
            with col2:
                st.write("**Editar**")
                c_sel_cat = st.selectbox("Seleccionar Cat", c_df['name'].tolist() if not c_df.empty else [])
                ecn = st.text_input("Nuevo Nombre")
                ecp = st.text_input("Nuevo Prefijo")
                if st.button("Modificar Cat"):
                    exec_sql("UPDATE categories SET name=?, prefix=? WHERE name=?", (ecn, ecp, c_sel_cat)); st.rerun()
                if st.button("🗑️ Borrar Cat"):
                    exec_sql("DELETE FROM categories WHERE name=?", (c_sel_cat,)); st.rerun()

        # 3. TIPOS Y POSICIONES
        st.divider()
        st.subheader("🧩 Tipos de Componentes")
        t_df = df_query("SELECT t.id, t.name, t.code, COUNT(o.order_no) as posiciones FROM types t LEFT JOIN type_orders o ON t.id = o.type_id GROUP BY t.id")
        st.dataframe(t_df, use_container_width=True)
        with st.expander("📝 Gestionar Tipos"):
            col1, col2 = st.columns(2)
            with col1:
                st.write("**Nuevo Tipo**")
                with st.form("nt"):
                    tn = st.text_input("Nombre"); tc = st.text_input("Código"); tp = st.number_input("Posiciones", 1, 50, 5)
                    if st.form_submit_button("Crear"):
                        exec_sql("INSERT INTO types(name, code) VALUES (?,?)", (tn, tc))
                        tid = df_query("SELECT id FROM types WHERE code=?", (tc,)).iloc[0]['id']
                        for i in range(1, int(tp)+1): exec_sql("INSERT INTO type_orders(type_id, order_no) VALUES (?,?)", (tid, i))
                        st.rerun()
            with col2:
                st.write("**Modificar Tipo**")
                t_sel_edit = st.selectbox("Tipo", t_df['name'].tolist() if not t_df.empty else [])
                etn = st.text_input("Editar Nombre T"); etc = st.text_input("Editar Código T"); etp = st.number_input("Nuevas Posiciones", 1, 50, 5)
                ta, tb = st.columns(2)
                if ta.button("Actualizar Todo"):
                    tid = int(t_df[t_df['name'] == t_sel_edit]['id'].values[0])
                    exec_sql("UPDATE types SET name=?, code=? WHERE id=?", (etn, etc, tid))
                    exec_sql("DELETE FROM type_orders WHERE type_id=?", (tid,))
                    for i in range(1, int(etp)+1): exec_sql("INSERT INTO type_orders(type_id, order_no) VALUES (?,?)", (tid, i))
                    st.rerun()
                if tb.button("🗑️ Eliminar Tipo"):
                    tid = int(t_df[t_df['name'] == t_sel_edit]['id'].values[0])
                    exec_sql("DELETE FROM type_orders WHERE type_id=?", (tid,))
                    exec_sql("DELETE FROM types WHERE id=?", (tid,)); st.rerun()
