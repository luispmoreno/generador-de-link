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

# URLs de marca
UNICOMER_LOGO = "https://grupounicomer.com/wp-content/uploads/2022/12/logo-sol-gris.png"
UNICOMER_BLUE = "#002d5a"
UNICOMER_YELLOW = "#fdbb2d"

# =========================
# Lógica de Datos y DB
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
        
        # Admin por defecto
        cur.execute("SELECT 1 FROM users WHERE username='admin'")
        if not cur.fetchone():
            s, p = make_password_record("admin123")
            cur.execute("INSERT INTO users(username, role, salt, pwd_hash, created_at) VALUES (?,?,?,?,?)", ("admin", "admin", s, p, datetime.now().isoformat()))
        
        # Carga de usuarios solicitados
        nuevos_usuarios = [
            ("ula_sv_unicomer", "SvLink$6Mc"),
            ("ula_cr_unicomer", "CrTrackQSjs"),
            ("ula_ec_unicomer", "EcHome!Cbb"),
            ("ula_gt_unicomer", "GtData$5Cg"),
            ("ula_hn_unicomer", "HnFlow%8Slp"),
            ("ula_ni_unicomer", "NiCode&3Ngt"),
            ("ula_corp_design", "D$corp_26")
        ]
        for user, pwd in nuevos_usuarios:
            cur.execute("SELECT 1 FROM users WHERE username=?", (user,))
            if not cur.fetchone():
                s, p = make_password_record(pwd)
                cur.execute("INSERT INTO users(username, role, salt, pwd_hash, created_at) VALUES (?,?,?,?,?)", (user, "user", s, p, datetime.now().isoformat()))

def get_user(username: str):
    u = username.strip().lower()
    res = df_query("SELECT id, username, role, salt, pwd_hash FROM users WHERE lower(username) = ?", (u,))
    return res.iloc[0].to_dict() if not res.empty else None

# =========================
# CSS Personalizado
# =========================
def apply_custom_styles():
    st.markdown(f"""
    <style>
        .stApp {{ background-color: #f4f7f9; }}
        [data-testid="stSidebar"] {{ background-color: {UNICOMER_BLUE}; }}
        [data-testid="stSidebar"] * {{ color: white !important; }}
        div.stButton > button {{
            background-color: {UNICOMER_YELLOW} !important;
            color: {UNICOMER_BLUE} !important;
            border: none !important;
            font-weight: bold;
            border-radius: 8px;
        }}
    </style>
    """, unsafe_allow_html=True)

# =========================
# Lógica Principal
# =========================
st.set_page_config(page_title=APP_TITLE, layout="wide")
apply_custom_styles()
init_db()

if "auth" not in st.session_state:
    st.session_state.auth = {"is_logged": False, "username": None, "role": None}

# --- LOGIN CENTRAL ---
if not st.session_state.auth["is_logged"]:
    _, center, _ = st.columns([1, 2, 1])
    with center:
        st.markdown(f"<div style='text-align:center; margin-top:50px;'><img src='{UNICOMER_LOGO}' width='200'></div>", unsafe_allow_html=True)
        st.markdown("<h2 style='text-align:center; color:#002d5a;'>Acceso Unicomer</h2>", unsafe_allow_html=True)
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
    st.markdown(f"<div style='filter: brightness(0) invert(1); text-align:center;'><img src='{UNICOMER_LOGO}' width='120'></div>", unsafe_allow_html=True)
    st.divider()
    st.write(f"Sesión: **{st.session_state.auth['username']}**")
    if st.button("Cerrar Sesión"):
        st.session_state.auth = {"is_logged": False, "username": None, "role": None}
        st.rerun()

# --- LOGO SUPERIOR ---
st.markdown(f"<div style='text-align:right;'><img src='{UNICOMER_LOGO}' width='150'></div>", unsafe_allow_html=True)

tabs = st.tabs(["✅ Generador", "🕒 Historial", "⚙️ Administración"])

# --- TAB GENERADOR ---
with tabs[0]:
    st.title(f"🔗 {APP_TITLE}")
    base_url = st.text_input("URL base del sitio", placeholder="https://...")
    c1, c2, c3 = st.columns(3)
    with c1:
        country = st.selectbox("País", ["SV", "GT", "CR", "HN", "NI", "PA", "DO", "JM", "TT"])
    with c2:
        cats_df = df_query("SELECT name, prefix FROM categories")
        cat_options = [f"{r.name} ({r.prefix})" for r in cats_df.itertuples()]
        cat_sel = st.selectbox("Categoría de Ubicación", cat_options) if not cats_df.empty else st.selectbox("Categoría", ["N/A"])
    with c3:
        types_df = df_query("SELECT id, name, code FROM types")
        type_options = [f"{r.name} ({r.code})" for r in types_df.itertuples()]
        type_sel = st.selectbox("Tipo de Componente", type_options) if not types_df.empty else st.selectbox("Tipo", ["N/A"])

    if not types_df.empty and "(" in type_sel:
        t_code = type_sel.split("(")[1].replace(")", "")
        t_id = int(types_df[types_df['code'] == t_code]['id'].values[0])
        orders = df_query("SELECT order_no FROM type_orders WHERE type_id=? ORDER BY order_no", (t_id,))
        order_list = orders['order_no'].tolist() if not orders.empty else list(range(1, 11))
        order_val = st.selectbox("Posición (Orden)", order_list)

        if st.button("GENERAR ID Y LINK"):
            if base_url:
                c_prefix = cat_sel.split("(")[1].replace(")", "")
                hid = f"{c_prefix}_{t_code}_{order_val}"
                parsed = urlparse(base_url.strip())
                qs = dict(parse_qsl(parsed.query))
                qs['hid'] = hid
                final_url = urlunparse(parsed._replace(query=urlencode(qs)))
                exec_sql("INSERT INTO history (created_at, base_url, final_url, country, type_code, order_value, hid_value) VALUES (?,?,?,?,?,?,?)",
                        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), base_url, final_url, country, t_code, str(order_val), hid))
                st.success(f"**ID Generado:** {hid}")
                st.code(final_url)
                components.html(f"<button onclick=\"navigator.clipboard.writeText('{final_url}'); alert('URL Copiada');\" style=\"width:100%; background:{UNICOMER_YELLOW}; border:none; padding:12px; border-radius:8px; font-weight:bold; cursor:pointer;\">📋 COPIAR LINK</button>", height=60)

# --- TAB HISTORIAL ---
with tabs[1]:
    st.subheader("Historial de Generaciones")
    hist = df_query("SELECT created_at as Fecha, country as Pais, hid_value as HID, final_url as URL FROM history ORDER BY id DESC")
    
    if not hist.empty:
        # Generar Excel de forma segura
        try:
            buffer = io.BytesIO()
            # Usamos engine='xlsxwriter' si está instalado, de lo contrario un fallback
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                hist.to_excel(writer, index=False, sheet_name='Historial')
            
            st.download_button(
                label="📥 Descargar Reporte en Excel",
                data=buffer.getvalue(),
                file_name=f"historial_unicomer_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        except Exception as e:
            st.warning("El botón de Excel se activará en breve. (Asegúrate de haber actualizado requirements.txt)")
            
        st.dataframe(hist, use_container_width=True)
    else:
        st.info("No hay registros.")

# --- TAB ADMIN ---
with tabs[2]:
    if st.session_state.auth["role"] != "admin":
        st.error("Acceso restringido.")
    else:
        st.header("👤 Usuarios")
        u_list = df_query("SELECT id, username, role FROM users")
        st.dataframe(u_list, use_container_width=True)
        
        with st.expander("📝 Gestionar Usuarios"):
            user_mod = st.selectbox("Seleccionar Usuario", u_list['username'].tolist())
            new_p = st.text_input("Nueva Contraseña (vacío = no cambiar)", type="password")
            if st.button("Actualizar Usuario"):
                if new_p:
                    s, p = make_password_record(new_p)
                    exec_sql("UPDATE users SET salt=?, pwd_hash=? WHERE username=?", (s, p, user_mod))
                    st.success("Cambios aplicados")
            if st.button("❌ Eliminar Usuario"):
                if user_mod != "admin":
                    exec_sql("DELETE FROM users WHERE username=?", (user_mod,))
                    st.rerun()

        st.divider()
        st.header("🧩 Componentes")
        # Mostrar visibilidad de posiciones
        t_list = df_query("""
            SELECT t.id, t.name as Nombre, t.code as Código, COUNT(o.order_no) as Posiciones
            FROM types t
            LEFT JOIN type_orders o ON t.id = o.type_id
            GROUP BY t.id
        """)
        st.dataframe(t_list, use_container_width=True)

        with st.expander("🛠️ Administrar Tipos"):
            with st.form("add_type"):
                tn = st.text_input("Nombre Componente")
                tc = st.text_input("Código")
                tp = st.number_input("Posiciones", min_value=1, value=5)
                if st.form_submit_button("Crear"):
                    exec_sql("INSERT INTO types(name, code) VALUES (?,?)", (tn, tc))
                    tid = df_query("SELECT id FROM types WHERE code=?", (tc,)).iloc[0]['id']
                    for i in range(1, int(tp)+1):
                        exec_sql("INSERT INTO type_orders(type_id, order_no) VALUES (?,?)", (tid, i))
                    st.rerun()
            
            type_del = st.selectbox("Borrar Tipo", t_list['Nombre'].tolist() if not t_list.empty else [])
            if st.button("Eliminar Tipo Seleccionado"):
                exec_sql("DELETE FROM type_orders WHERE type_id IN (SELECT id FROM types WHERE name=?)", (type_del,))
                exec_sql("DELETE FROM types WHERE name=?", (type_del,))
                st.rerun()
