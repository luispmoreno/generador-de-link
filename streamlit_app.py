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

# Estilos corporativos
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

# --- FUNCIONES DE BASE DE DATOS ---
def exec_sql(sql, params=()):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.cursor()
            cur.execute(sql, params)
            conn.commit()
            return True, "✅ Cambio aplicado"
    except Exception as e:
        return False, str(e)

def df_query(sql, params=()):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            return pd.read_sql_query(sql, conn, params=params)
    except:
        return pd.DataFrame()

# --- MIGRACIÓN Y CARGA DE BLOQUES REQUERIDOS ---
def provision_db():
    # Creación de tablas
    exec_sql("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT UNIQUE, role TEXT, salt TEXT, pwd_hash TEXT, created_at TEXT)")
    exec_sql("CREATE TABLE IF NOT EXISTS categories (id INTEGER PRIMARY KEY, name TEXT UNIQUE, prefix TEXT)")
    exec_sql("CREATE TABLE IF NOT EXISTS types (id INTEGER PRIMARY KEY, name TEXT UNIQUE, code TEXT)")
    exec_sql("CREATE TABLE IF NOT EXISTS type_orders (id INTEGER PRIMARY KEY, type_id INTEGER, order_no INTEGER)")
    exec_sql("CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY, created_at TEXT, country TEXT, hid_value TEXT, final_url TEXT, username TEXT)")
    
    # Reparar columna username si falta
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("PRAGMA table_info(history)")
            if 'username' not in [col[1] for col in c.fetchall()]:
                c.execute("ALTER TABLE history ADD COLUMN username TEXT")
    except: pass

    # Cargar Usuarios Maestros (image_122fb9.png)
    master_users = [
        ("ula_cr_unicomer", "CrTrackQSjs", "user"), ("ula_sv_unicomer", "SVTrackQScs", "user"),
        ("ula_ec_unicomer", "EcHome!Cbb", "user"), ("ula_gt_unicomer", "GtData$5Cg", "user"),
        ("ula_hn_unicomer", "HnFlow%8Slp", "user"), ("ula_corp_design", "Dcorp$26", "user"),
        ("leslie_mejia", "desing1234", "admin"), ("ula_ni_unicomer", "NiCo2026!", "user"),
        ("admin", "admin123", "admin"), ("luis_pena", "admin123", "admin")
    ]
    for uname, pword, urole in master_users:
        if df_query("SELECT id FROM users WHERE username=?", (uname,)).empty:
            s = secrets.token_hex(16); h = hashlib.sha256((s+pword).encode()).hexdigest()
            exec_sql("INSERT INTO users(username, role, salt, pwd_hash, created_at) VALUES (?,?,?,?,?)",
                     (uname, urole, s, h, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

    # CARGA FORZADA DE TIPOS Y POSICIONES (image_78995e.png)
    required_blocks = [
        ("BannerCarrito", "bcarrito", 1),
        ("BannerCredito", "bcredi", 1),
        ("BannerCheckout", "bcco", 1),
        ("PopupCategoria", "popupcat", 7),
        ("MenuHorizontal", "mhc", 10),
        ("MarcasDestacadas", "mdt", 10),
        ("CategoriasDestacadas", "dtd", 14)
    ]
    
    for b_name, b_code, b_pos in required_blocks:
        # Verificar si el tipo existe
        t_check = df_query("SELECT id FROM types WHERE code=?", (b_code,))
        if t_check.empty:
            exec_sql("INSERT INTO types(name, code) VALUES (?,?)", (b_name, b_code))
            t_id = df_query("SELECT id FROM types WHERE code=?", (b_code,)).iloc[0]['id']
        else:
            t_id = t_check.iloc[0]['id']
            # Actualizar nombre por si acaso
            exec_sql("UPDATE types SET name=? WHERE id=?", (b_name, int(t_id)))
        
        # Verificar y rellenar posiciones faltantes
        existing_pos = df_query("SELECT order_no FROM type_orders WHERE type_id=?", (int(t_id),))
        if len(existing_pos) < b_pos:
            # Limpiar posiciones viejas si están incompletas para evitar saltos
            exec_sql("DELETE FROM type_orders WHERE type_id=?", (int(t_id),))
            for i in range(1, b_pos + 1):
                exec_sql("INSERT INTO type_orders(type_id, order_no) VALUES (?,?)", (int(t_id), i))

    if df_query("SELECT id FROM categories").empty:
        exec_sql("INSERT INTO categories(name, prefix) VALUES ('Home', 'hm')")

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
                ihash = hashlib.sha256((res.iloc[0]['salt'] + p_in).encode()).hexdigest()
                if ihash == res.iloc[0]['pwd_hash']:
                    st.session_state.auth = {"is_logged": True, "username": res.iloc[0]['username'], "role": res.iloc[0]['role']}
                    st.rerun()
            st.error("Credenciales incorrectas")
    st.stop()

# =========================
# 3. APP PRINCIPAL
# =========================
with st.sidebar:
    st.markdown(f'<img src="{UNICOMER_LOGO_URL}" class="white-logo">', unsafe_allow_html=True)
    st.write(f"Usuario: **{st.session_state.auth['username']}**")
    if st.button("Cerrar Sesión"):
        st.session_state.auth = {"is_logged": False}
        st.rerun()

tab1, tab2, tab3 = st.tabs(["✅ Generador", "🕒 Historial", "⚙️ Administración"])

# --- GENERADOR ---
with tab1:
    st.markdown('<div class="figma-box"><h4>🎨 Guía de Posiciones</h4><p>Usa Figma para validar el componente antes de generar el ID.</p><a href="https://www.figma.com/design/ihSTaMfAmyN99BN5Z6sNps/Home-ULA?node-id=0-1" target="_blank" class="figma-button">IR A FIGMA</a></div>', unsafe_allow_html=True)
    
    url_base = st.text_input("URL base", placeholder="https://www.lacuracaonline.com/...")
    c1, c2, c3 = st.columns(3)
    p_sel = c1.selectbox("País", ["SV", "GT", "CR", "HN", "NI", "PA", "EC", "DO"])
    cats_df = df_query("SELECT id, name, prefix FROM categories")
    cat_sel = c2.selectbox("Categoría", [f"{r.name} ({r.prefix})" for r in cats_df.itertuples()] if not cats_df.empty else ["N/A"])
    typs_df = df_query("SELECT id, name, code FROM types")
    type_sel = c3.selectbox("Tipo", [f"{r.name} ({r.code})" for r in typs_df.itertuples()] if not typs_df.empty else ["N/A"])
    
    if "(" in type_sel and "(" in cat_sel:
        t_code = type_sel.split("(")[1].replace(")", "")
        t_id = typs_df[typs_df['code'] == t_code]['id'].values[0]
        pos_df = df_query("SELECT order_no FROM type_orders WHERE type_id=? ORDER BY order_no", (int(t_id),))
        p_val = st.selectbox("Posición", pos_df['order_no'].tolist() if not pos_df.empty else [1])
        
        if st.button("GENERAR ID Y LINK"):
            if url_base.strip():
                c_pref = cat_sel.split("(")[1].replace(")", "")
                hid = f"{c_pref}_{t_code}_{p_val}"
                up = urlparse(url_base.strip()); qs = dict(parse_qsl(up.query))
                qs['hid'] = hid
                final_url = urlunparse(up._replace(query=urlencode(qs)))
                
                exec_sql("INSERT INTO history (created_at, country, hid_value, final_url, username) VALUES (?,?,?,?,?)",
                        (datetime.now().strftime("%Y-%m-%dT%H:%M:%S"), p_sel, hid, final_url, st.session_state.auth["username"]))
                st.success(f"ID: {hid}"); st.code(final_url); time.sleep(2)

# --- HISTORIAL ---
with tab2:
    st.subheader("Registros Recientes")
    h_sql = "SELECT created_at as Fecha, country as Pais, hid_value as ID, final_url as URL FROM history"
    if st.session_state.auth["role"] != "admin":
        h_sql += " WHERE username = ?"
        h_data = df_query(h_sql + " ORDER BY id DESC", (st.session_state.auth["username"],))
    else:
        h_data = df_query(h_sql + " ORDER BY id DESC")
    st.dataframe(h_data, use_container_width=True)

# --- ADMINISTRACIÓN ---
with tab3:
    st.title("Administración del Sistema")
    resumen = df_query("""SELECT t.name as Nombre, t.code as Codigo, COUNT(o.id) as Posiciones 
                         FROM types t LEFT JOIN type_orders o ON t.id = o.type_id GROUP BY t.id""")
    st.dataframe(resumen, use_container_width=True)

    if st.session_state.auth["role"] == "admin":
        st.divider()
        col_m1, col_m2 = st.columns(2)
        
        with col_m1:
            with st.expander("📝 Editar Tipo"):
                if not typs_df.empty:
                    t_sel_edit = st.selectbox("Seleccionar", typs_df['name'].tolist())
                    t_info = typs_df[typs_df['name'] == t_sel_edit].iloc[0]
                    v_name = st.text_input("Nombre", value=t_info['name'])
                    v_code = st.text_input("Código", value=t_info['code'])
                    if st.button("Actualizar"):
                        exec_sql("UPDATE types SET name=?, code=? WHERE id=?", (v_name, v_code, int(t_info['id'])))
                        st.success("Guardado"); time.sleep(2); st.rerun()

        with col_m2:
            with st.expander("➕ Crear Nuevo Bloque"):
                n_name = st.text_input("Nombre Componente")
                n_code = st.text_input("Código Corto")
                n_pos = st.number_input("Total Posiciones", 1, 100, 5)
                if st.button("Registrar Bloque"):
                    ok, _ = exec_sql("INSERT INTO types(name, code) VALUES (?,?)", (n_name, n_code))
                    if ok:
                        tid = df_query("SELECT id FROM types WHERE code=?", (n_code,)).iloc[0]['id']
                        for i in range(1, int(n_pos)+1):
                            exec_sql("INSERT INTO type_orders(type_id, order_no) VALUES (?,?)", (tid, i))
                        st.success("Bloque Creado"); time.sleep(2); st.rerun()
