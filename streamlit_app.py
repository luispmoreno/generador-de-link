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

# --- FUNCIONES DE BASE DE DATOS ---
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

# --- MIGRACIÓN Y PRE-CARGA DE DATOS ---
def provision_db():
    exec_sql("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT UNIQUE, role TEXT, salt TEXT, pwd_hash TEXT, created_at TEXT)")
    exec_sql("CREATE TABLE IF NOT EXISTS categories (id INTEGER PRIMARY KEY, name TEXT UNIQUE, prefix TEXT)")
    exec_sql("CREATE TABLE IF NOT EXISTS types (id INTEGER PRIMARY KEY, name TEXT UNIQUE, code TEXT)")
    exec_sql("CREATE TABLE IF NOT EXISTS type_orders (id INTEGER PRIMARY KEY, type_id INTEGER, order_no INTEGER)")
    exec_sql("CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY, created_at TEXT, country TEXT, hid_value TEXT, final_url TEXT, username TEXT)")
    
    # REPARACIÓN: Columna username
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("PRAGMA table_info(history)")
            if 'username' not in [col[1] for col in c.fetchall()]:
                c.execute("ALTER TABLE history ADD COLUMN username TEXT")
                conn.commit()
    except: pass

    # 1. Usuarios Maestros (image_122fb9.png)
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

    # 2. Categoría inicial si no hay
    if df_query("SELECT id FROM categories").empty:
        exec_sql("INSERT INTO categories(name, prefix) VALUES ('Home', 'hm')")

    # 3. Nuevos Tipos Requeridos (image_78995e.png)
    new_types_list = [
        ("BannerCarrito", "bcarrito", 1),
        ("BannerCredito", "bcredi", 1),
        ("BannerCheckout", "bcco", 1),
        ("PopupCategoria", "popupcat", 7),
        ("MenuHorizontal", "mhc", 10),
        ("MarcasDestacadas", "mdt", 10),
        ("CategoriasDestacadas", "dtd", 14)
    ]
    for t_name, t_code, t_pos in new_types_list:
        if df_query("SELECT id FROM types WHERE code=?", (t_code,)).empty:
            ok, _ = exec_sql("INSERT INTO types(name, code) VALUES (?,?)", (t_name, t_code))
            if ok:
                tid = df_query("SELECT id FROM types WHERE code=?", (t_code,)).iloc[0]['id']
                for i in range(1, t_pos + 1):
                    exec_sql("INSERT INTO type_orders(type_id, order_no) VALUES (?,?)", (tid, i))

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
            st.error("Credenciales no válidas.")
    st.stop()

# =========================
# 3. INTERFAZ PRINCIPAL
# =========================
with st.sidebar:
    st.markdown(f'<img src="{UNICOMER_LOGO_URL}" class="white-logo">', unsafe_allow_html=True)
    st.write(f"Sesión: **{st.session_state.auth['username']}**")
    if st.button("Cerrar Sesión"):
        st.session_state.auth = {"is_logged": False}
        st.rerun()

tabs = st.tabs(["✅ Generador", "🕒 Historial", "⚙️ Administración"])

# --- TAB 1: GENERADOR ---
with tabs[0]:
    st.markdown('<div class="figma-box"><h4>🎨 Figma Oficial</h4><a href="https://www.figma.com/design/ihSTaMfAmyN99BN5Z6sNps/Home-ULA?node-id=0-1" target="_blank" class="figma-button">IR A FIGMA</a></div>', unsafe_allow_html=True)
    url_base = st.text_input("URL base", placeholder="https://...")
    c1, c2, c3 = st.columns(3)
    p_sel = c1.selectbox("País", ["SV", "GT", "CR", "HN", "NI", "PA", "EC", "DO"])
    
    cats_df = df_query("SELECT id, name, prefix FROM categories")
    cat_sel = c2.selectbox("Categoría", [f"{r.name} ({r.prefix})" for r in cats_df.itertuples()] if not cats_df.empty else ["N/A"])
    
    typs_df = df_query("SELECT id, name, code FROM types")
    type_sel = c3.selectbox("Tipo", [f"{r.name} ({r.code})" for r in typs_df.itertuples()] if not typs_df.empty else ["N/A"])
    
    if "(" in type_sel and "(" in cat_sel:
        t_code_active = type_sel.split("(")[1].replace(")", "")
        t_id_active = typs_df[typs_df['code'] == t_code_active]['id'].values[0]
        pos_options = df_query("SELECT order_no FROM type_orders WHERE type_id=? ORDER BY order_no", (int(t_id_active),))
        pos_val = st.selectbox("Posición", pos_options['order_no'].tolist() if not pos_options.empty else [1])
        
        if st.button("GENERAR ID Y LINK"):
            if url_base.strip():
                c_pref = cat_sel.split("(")[1].replace(")", "")
                hid_final = f"{c_pref}_{t_code_active}_{pos_val}"
                up = urlparse(url_base.strip()); qs = dict(parse_qsl(up.query))
                qs['hid'] = hid_final
                f_link = urlunparse(up._replace(query=urlencode(qs)))
                
                exec_sql("INSERT INTO history (created_at, country, hid_value, final_url, username) VALUES (?,?,?,?,?)",
                        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), p_sel, hid_final, f_link, st.session_state.auth["username"]))
                st.success(f"ID: {hid_final}"); st.code(f_link); time.sleep(2)

# --- TAB 2: HISTORIAL ---
with tabs[1]:
    st.subheader("🕒 Registros Generados")
    if st.session_state.auth["role"] == "admin":
        h_df = df_query("SELECT created_at as Fecha, username as Usuario, country as Pais, hid_value as ID, final_url as URL FROM history ORDER BY id DESC")
    else:
        h_df = df_query("SELECT created_at as Fecha, country as Pais, hid_value as ID, final_url as URL FROM history WHERE username=? ORDER BY id DESC", (st.session_state.auth["username"],))
    st.dataframe(h_df, use_container_width=True)

# --- TAB 3: ADMINISTRACIÓN ---
with tabs[2]:
    st.title("⚙️ Administración")
    st.subheader("📊 Resumen de Tipos")
    resumen = df_query("""SELECT t.name as Nombre, t.code as Código, COUNT(o.id) as Posiciones 
                         FROM types t LEFT JOIN type_orders o ON t.id = o.type_id GROUP BY t.id""")
    if not resumen.empty:
        st.dataframe(resumen, use_container_width=True)

    if st.session_state.auth["role"] == "admin":
        st.divider()
        col_a, col_b = st.columns(2)
        
        with col_a:
            with st.expander("📁 Categorías"):
                c_n = st.text_input("Nombre Cat"); c_p = st.text_input("Prefijo Cat")
                if st.button("Guardar Categoría"):
                    exec_sql("INSERT INTO categories(name, prefix) VALUES (?,?)", (c_n, c_p))
                    st.success("Guardado"); time.sleep(2); st.rerun()
            
            with st.expander("📝 Editar Tipo Existente"):
                if not typs_df.empty:
                    t_edit_name = st.selectbox("Seleccionar tipo", typs_df['name'].tolist())
                    t_row = typs_df[typs_df['name'] == t_edit_name].iloc[0]
                    new_t_name = st.text_input("Nuevo Nombre", value=t_row['name'])
                    new_t_code = st.text_input("Nuevo Código", value=t_row['code'])
                    if st.button("Actualizar Parámetros"):
                        exec_sql("UPDATE types SET name=?, code=? WHERE id=?", (new_t_name, new_t_code, int(t_row['id'])))
                        st.success("Actualizado"); time.sleep(2); st.rerun()

        with col_b:
            with st.expander("➕ Registrar Nuevo Tipo"):
                reg_name = st.text_input("Nombre del Componente")
                reg_code = st.text_input("Código Corto")
                reg_pos = st.number_input("Posiciones", 1, 100, 5)
                if st.button("Registrar Ahora"):
                    # Reparación del botón: nombres de variables únicos
                    ok_reg, _ = exec_sql("INSERT INTO types(name, code) VALUES (?,?)", (reg_name, reg_code))
                    if ok_reg:
                        tid_reg = df_query("SELECT id FROM types WHERE code=?", (reg_code,)).iloc[0]['id']
                        for i in range(1, int(reg_pos)+1):
                            exec_sql("INSERT INTO type_orders(type_id, order_no) VALUES (?,?)", (tid_reg, i))
                        st.success("Tipo registrado correctamente"); time.sleep(2); st.rerun()

        st.divider()
        st.subheader("👤 Seguridad de Usuarios")
        udf = df_query("SELECT username, role FROM users")
        st.dataframe(udf, use_container_width=True)
        with st.expander("🔑 Cambiar Contraseña"):
            u_target = st.selectbox("Usuario", udf['username'].tolist() if not udf.empty else [])
            p_new_val = st.text_input("Nueva Clave", type="password")
            if st.button("Actualizar Password"):
                s_new = secrets.token_hex(16); h_new = hashlib.sha256((s_new+p_new_val).encode()).hexdigest()
                exec_sql("UPDATE users SET salt=?, pwd_hash=? WHERE username=?", (s_new, h_new, u_target))
                st.success("Hecho"); time.sleep(2); st.rerun()
