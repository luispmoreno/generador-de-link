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

# CSS: Estilos corporativos y logo blanco
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
    .figma-box {{
        background-color: #f0f2f6; padding: 20px; border-radius: 10px;
        border-left: 5px solid {UNICOMER_YELLOW}; margin-bottom: 25px;
    }}
    .figma-button {{
        background-color: {UNICOMER_BLUE} !important; color: white !important;
        padding: 10px 20px; border-radius: 5px; text-decoration: none; font-weight: bold; display: inline-block; margin-top: 10px;
    }}
</style>
""", unsafe_allow_html=True)

# --- FUNCIONES DE BASE DE DATOS ROBUSTAS ---
def exec_sql(sql, params=()):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.cursor()
            cur.execute(sql, params)
            conn.commit()
            return True, "✅ Hecho"
    except Exception as e:
        return False, str(e)

def df_query(sql, params=()):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            return pd.read_sql_query(sql, conn, params=params)
    except:
        return pd.DataFrame()

# --- MIGRACIÓN Y LIMPIEZA ---
def provision_db():
    # Creación de tablas base
    exec_sql("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT UNIQUE, role TEXT, salt TEXT, pwd_hash TEXT, created_at TEXT)")
    exec_sql("CREATE TABLE IF NOT EXISTS categories (id INTEGER PRIMARY KEY, name TEXT UNIQUE, prefix TEXT)")
    exec_sql("CREATE TABLE IF NOT EXISTS types (id INTEGER PRIMARY KEY, name TEXT UNIQUE, code TEXT)")
    exec_sql("CREATE TABLE IF NOT EXISTS type_orders (id INTEGER PRIMARY KEY, type_id INTEGER, order_no INTEGER)")
    exec_sql("CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY, created_at TEXT, country TEXT, hid_value TEXT, final_url TEXT, username TEXT)")
    
    # REPARACIÓN: Agregar columna username si falta (Corrige DatabaseError)
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("PRAGMA table_info(history)")
            cols = [col[1] for col in c.fetchall()]
            if 'username' not in cols:
                c.execute("ALTER TABLE history ADD COLUMN username TEXT")
                conn.commit()
    except: pass

    # Inserción de usuarios maestros
    master_users = [
        ("ula_cr_unicomer", "CrTrackQSjs", "user"),
        ("ula_sv_unicomer", "SVTrackQScs", "user"),
        ("ula_ec_unicomer", "EcHome!Cbb", "user"),
        ("ula_gt_unicomer", "GtData$5Cg", "user"),
        ("ula_hn_unicomer", "HnFlow%8Slp", "user"),
        ("ula_corp_design", "Dcorp$26", "user"),
        ("leslie_mejia", "desing1234", "admin"),
        ("ula_ni_unicomer", "NiCo2026!", "user"),
        ("admin", "admin123", "admin"),
        ("luis_pena", "admin123", "admin")
    ]
    for uname, pword, urole in master_users:
        if df_query("SELECT id FROM users WHERE username=?", (uname,)).empty:
            s = secrets.token_hex(16); h = hashlib.sha256((s+pword).encode()).hexdigest()
            exec_sql("INSERT INTO users(username, role, salt, pwd_hash, created_at) VALUES (?,?,?,?,?)",
                     (uname, urole, s, h, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

provision_db()

# =========================
# 2. LOGIN
# =========================
if not st.session_state.auth["is_logged"]:
    _, center, _ = st.columns([1, 2, 1])
    with center:
        st.image(UNICOMER_LOGO_URL, width=200)
        u_in = st.text_input("Usuario")
        p_in = st.text_input("Contraseña", type="password")
        if st.button("ACCEDER"):
            res = df_query("SELECT username, role, salt, pwd_hash FROM users WHERE username=?", (u_in,))
            if not res.empty:
                input_hash = hashlib.sha256((res.iloc[0]['salt'] + p_in).encode("utf-8")).hexdigest()
                if input_hash == res.iloc[0]['pwd_hash']:
                    st.session_state.auth = {"is_logged": True, "username": res.iloc[0]['username'], "role": res.iloc[0]['role']}
                    st.rerun()
            st.error("Acceso denegado.")
    st.stop()

# =========================
# 3. INTERFAZ
# =========================
with st.sidebar:
    st.markdown(f'<img src="{UNICOMER_LOGO_URL}" class="white-logo">', unsafe_allow_html=True)
    st.write(f"Conectado como: **{st.session_state.auth['username']}**")
    if st.button("Cerrar Sesión"):
        st.session_state.auth = {"is_logged": False}
        st.rerun()

tabs = st.tabs(["✅ Generador", "🕒 Historial", "⚙️ Administración"])

# --- TAB 1: GENERADOR ---
with tabs[0]:
    st.markdown('<div class="figma-box"><h4>🎨 Guía de Posiciones</h4><p>Valida los códigos en el Figma oficial antes de generar.</p><a href="https://www.figma.com/design/ihSTaMfAmyN99BN5Z6sNps/Home-ULA?node-id=0-1" target="_blank" class="figma-button">IR A FIGMA</a></div>', unsafe_allow_html=True)
    url_base = st.text_input("URL base", placeholder="https://www.lacuracaonline.com/...")
    c1, c2, c3 = st.columns(3)
    p_sel = c1.selectbox("País", ["SV", "GT", "CR", "HN", "NI", "PA", "EC", "DO"])
    
    cats_df = df_query("SELECT id, name, prefix FROM categories")
    cat_sel = c2.selectbox("Categoría", [f"{r.name} ({r.prefix})" for r in cats_df.itertuples()] if not cats_df.empty else ["Sin categorías"])
    
    typs_df = df_query("SELECT id, name, code FROM types")
    type_sel = c3.selectbox("Tipo", [f"{r.name} ({r.code})" for r in typs_df.itertuples()] if not typs_df.empty else ["Sin tipos"])
    
    if "(" in type_sel and "(" in cat_sel:
        t_code = type_sel.split("(")[1].replace(")", "")
        t_id = typs_df[typs_df['code'] == t_code]['id'].values[0]
        pos_df = df_query("SELECT order_no FROM type_orders WHERE type_id=? ORDER BY order_no", (int(t_id),))
        p_val = st.selectbox("Posición", pos_df['order_no'].tolist() if not pos_df.empty else [1])
        
        if st.button("GENERAR ID Y LINK"):
            if url_base.strip():
                c_pref = cat_sel.split("(")[1].replace(")", "")
                hid_gen = f"{c_pref}_{t_code}_{p_val}"
                parsed = urlparse(url_base.strip()); query = dict(parse_qsl(parsed.query))
                query['hid'] = hid_gen
                f_link = urlunparse(parsed._replace(query=urlencode(query)))
                
                exec_sql("INSERT INTO history (created_at, country, hid_value, final_url, username) VALUES (?,?,?,?,?)",
                        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), p_sel, hid_gen, f_link, st.session_state.auth["username"]))
                st.success(f"Generado: {hid_gen}"); st.code(f_link); time.sleep(2)

# --- TAB 2: HISTORIAL ---
with tabs[1]:
    st.subheader("🕒 Registros Generados")
    if st.session_state.auth["role"] == "admin":
        h_data = df_query("SELECT created_at as Fecha, username as Usuario, country as Pais, hid_value as ID, final_url as URL FROM history ORDER BY id DESC")
    else:
        h_data = df_query("SELECT created_at as Fecha, country as Pais, hid_value as ID, final_url as URL FROM history WHERE username=? ORDER BY id DESC", (st.session_state.auth["username"],))
    st.dataframe(h_data, use_container_width=True)

# --- TAB 3: ADMINISTRACIÓN (Reparado) ---
with tabs[2]:
    st.title("⚙️ Configuración")
    st.subheader("📊 Tipos Registrados")
    resumen_df = df_query("""SELECT t.name as Nombre, t.code as Código, COUNT(o.id) as Posiciones 
                            FROM types t LEFT JOIN type_orders o ON t.id = o.type_id GROUP BY t.id""")
    if not resumen_df.empty:
        st.dataframe(resumen_df, use_container_width=True)

    if st.session_state.auth["role"] == "admin":
        st.divider()
        col_m1, col_m2 = st.columns(2)
        
        with col_m1:
            with st.expander("📁 Categorías"):
                c_name = st.text_input("Nombre Categoría")
                c_pref = st.text_input("Prefijo")
                if st.button("Crear"):
                    exec_sql("INSERT INTO categories(name, prefix) VALUES (?,?)", (c_name, c_pref))
                    st.success("Guardado"); time.sleep(2); st.rerun()
            
            with st.expander("📝 Editar Tipo"):
                if not typs_df.empty:
                    t_sel_edit = st.selectbox("Seleccionar para modificar", typs_df['name'].tolist())
                    t_row = typs_df[typs_df['name'] == t_sel_edit].iloc[0]
                    # Variables con nombres únicos para evitar NameError
                    upd_name = st.text_input("Nuevo Nombre", value=t_row['name'])
                    upd_code = st.text_input("Nuevo Código", value=t_row['code'])
                    if st.button("Actualizar"):
                        exec_sql("UPDATE types SET name=?, code=? WHERE id=?", (upd_name, upd_code, int(t_row['id'])))
                        st.success("Hecho"); time.sleep(2); st.rerun()

        with col_m2:
            with st.expander("➕ Nuevo Tipo"):
                n_t_name = st.text_input("Nombre Componente")
                n_t_code = st.text_input("Código Corto")
                n_t_pos = st.number_input("Cantidad Posiciones", 1, 100, 5)
                if st.button("Registrar"):
                    ok, _ = exec_sql("INSERT INTO types(name, code) VALUES (?,?)", (n_t_name, n_t_code))
                    if ok:
                        tid = df_query("SELECT id FROM types WHERE code=?", (n_t_code,)).iloc[0]['id']
                        for i in range(1, int(n_t_pos)+1): exec_sql("INSERT INTO type_orders(type_id, order_no) VALUES (?,?)", (tid, i))
                        st.success("Creado"); time.sleep(2); st.rerun()

        st.divider()
        st.subheader("👤 Gestión de Usuarios")
        u_table = df_query("SELECT username, role FROM users")
        st.dataframe(u_table, use_container_width=True)
        with st.expander("🔑 Reset Password"):
            target_u = st.selectbox("Usuario", u_table['username'].tolist() if not u_table.empty else [])
            new_p_val = st.text_input("Nueva Clave", type="password") # Cambiado de 'new' a 'new_p_val'
            if st.button("Cambiar Clave"):
                s_val = secrets.token_hex(16); h_val = hashlib.sha256((s_val+new_p_val).encode()).hexdigest()
                exec_sql("UPDATE users SET salt=?, pwd_hash=? WHERE username=?", (s_val, h_val, target_u))
                st.success("Password actualizado"); time.sleep(2); st.rerun()
