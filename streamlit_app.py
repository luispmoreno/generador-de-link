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
        st.error("❌ El nombre o código ya existe en la base de datos.") # Corrigiendo error de la imagen image_c95bf8
        return False

def df_query(sql, params=()):
    with get_conn() as conn:
        return pd.read_sql_query(sql, conn, params=params)

# =========================
# 3. LOGIN
# =========================
if not st.session_state.auth["is_logged"]:
    _, center, _ = st.columns([1, 2, 1])
    with center:
        st.image(UNICOMER_LOGO_URL, width=200)
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
# 4. INTERFAZ
# =========================
with st.sidebar:
    st.markdown(f'<img src="{UNICOMER_LOGO_URL}" class="white-logo">', unsafe_allow_html=True) # Logo blanco
    st.write(f"👤 **{st.session_state.auth['username']}**")
    if st.button("Cerrar Sesión"):
        st.session_state.auth = {"is_logged": False}
        st.rerun()

tabs = st.tabs(["✅ Generador", "🕒 Historial", "⚙️ Administración"])

# --- TAB GENERADOR ---
with tabs[0]:
    st.markdown('<div class="figma-box"><h4>🎨 Guía de Posiciones</h4><p>Consulta el Figma oficial para validar los códigos.</p></div>', unsafe_allow_html=True)
    url_base = st.text_input("URL base", placeholder="https://...")
    
    c1, c2, c3 = st.columns(3)
    pais = c1.selectbox("País", ["SV", "GT", "CR", "HN", "NI", "PA", "DO", "JM", "TT"])
    cats = df_query("SELECT name, prefix FROM categories")
    cat_sel = c2.selectbox("Categoría", [f"{r.name} ({r.prefix})" for r in cats.itertuples()] if not cats.empty else ["N/A"])
    typs = df_query("SELECT id, name, code FROM types")
    type_sel = c3.selectbox("Tipo", [f"{r.name} ({r.code})" for r in typs.itertuples()] if not typs.empty else ["N/A"])
    
    if "(" in type_sel and "(" in cat_sel:
        t_code = type_sel.split("(")[1].replace(")", "")
        t_id = typs[typs['code'] == t_code]['id'].values[0]
        pos_df = df_query("SELECT order_no FROM type_orders WHERE type_id=? ORDER BY order_no", (int(t_id),))
        pos = st.selectbox("Posición (Orden)", pos_df['order_no'].tolist() if not pos_df.empty else [1])
        
        if st.button("GENERAR ID Y LINK"):
            pref = cat_sel.split("(")[1].replace(")", "")
            hid = f"{pref}_{t_code}_{pos}"
            p_url = urlparse(url_base.strip())
            qs = dict(parse_qsl(p_url.query))
            qs['hid'] = hid
            f_url = urlunparse(p_url._replace(query=urlencode(qs)))
            
            exec_sql("INSERT INTO history (created_at, base_url, final_url, country, type_code, order_value, hid_value) VALUES (?,?,?,?,?,?,?)",
                    (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), url_base, f_url, pais, t_code, str(pos), hid))
            st.success(f"ID Generado: {hid}")
            st.code(f_url)

# --- TAB HISTORIAL ---
with tabs[1]:
    st.subheader("🕒 Registros Generados")
    hist_df = df_query("SELECT created_at, country, hid_value, final_url FROM history ORDER BY id DESC")
    st.dataframe(hist_df, use_container_width=True)

# --- TAB ADMINISTRACIÓN ---
if st.session_state.auth["role"] == "admin":
    with tabs[2]:
        st.title("⚙️ Panel de Administración")
        
        # 1. Gestión de Usuarios
        st.subheader("👤 Usuarios Registrados")
        users_df = df_query("SELECT id, username, role, created_at FROM users")
        st.dataframe(users_df, use_container_width=True)
        
        # 2. Resumen de Tipos y Posiciones
        st.divider()
        st.subheader("📊 Resumen de Tipos y Posiciones")
        summary = df_query("""SELECT t.id, t.name as Nombre, t.code as Código, COUNT(o.id) as Posiciones 
                           FROM types t LEFT JOIN type_orders o ON t.id = o.type_id GROUP BY t.id""")
        st.dataframe(summary[["Nombre", "Código", "Posiciones"]], use_container_width=True)

        st.divider()
        st.subheader("🛠️ Mantenimiento de Catálogos y Componentes")
        col_cat, col_typ = st.columns(2)
        
        with col_cat:
            with st.expander("📁 Categorías"):
                cn = st.text_input("Nombre Categoría", key="add_cat_n")
                cp = st.text_input("Prefijo", key="add_cat_p")
                if st.button("Añadir Categoría"):
                    exec_sql("INSERT INTO categories(name, prefix) VALUES (?,?)", (cn, cp))
                    st.rerun()

        with col_typ:
            with st.expander("➕ Añadir Nuevo Tipo"):
                atn = st.text_input("Nombre Tipo", key="atn")
                atc = st.text_input("Código", key="atc")
                atp = st.number_input("Posiciones", 1, 50, 5, key="atp")
                if st.button("Crear Tipo"):
                    if exec_sql("INSERT INTO types(name, code) VALUES (?,?)", (atn, atc)):
                        tid = df_query("SELECT id FROM types WHERE code=?", (atc,)).iloc[0]['id']
                        for i in range(1, int(atp)+1): exec_sql("INSERT INTO type_orders(type_id, order_no) VALUES (?,?)", (tid, i))
                        st.rerun()

            # --- SECCIÓN DE EDICIÓN (SOLICITADA) ---
            if not summary.empty:
                st.write("**📝 Editar Seleccionado**")
                t_manage = st.selectbox("Seleccionar para Editar/Borrar", summary['Nombre'].tolist(), key="sel_to_edit")
                
                # CARGA AUTOMÁTICA DE DATOS
                t_row = summary[summary['Nombre'] == t_manage].iloc[0]
                t_id_real = int(t_row['id'])
                
                with st.expander("📝 Ver/Modificar Información"):
                    # Los campos 'value' ahora cargan la info de la base de datos automáticamente
                    en = st.text_input("Nuevo Nombre Tipo", value=t_row['Nombre'], key="edit_n")
                    ec = st.text_input("Nuevo Código", value=t_row['Código'], key="edit_c")
                    # Blindaje contra StreamlitValueBelowMinError
                    ep = st.number_input("Cantidad de Posiciones", 1, 50, value=max(1, int(t_row['Posiciones'])), key="edit_p")
                    
                    if st.button("Actualizar Tipo", key="upd_btn"):
                        exec_sql("UPDATE types SET name=?, code=? WHERE id=?", (en, ec, t_id_real))
                        curr_count = int(t_row['Posiciones'])
                        if ep > curr_count:
                            for i in range(curr_count + 1, int(ep) + 1):
                                exec_sql("INSERT INTO type_orders(type_id, order_no) VALUES (?,?)", (t_id_real, i))
                        elif ep < curr_count:
                            exec_sql("DELETE FROM type_orders WHERE type_id=? AND order_no > ?", (t_id_real, int(ep)))
                        st.success("¡Datos actualizados!"); time.sleep(0.5); st.rerun()
                
                if st.button(f"🗑️ Eliminar Tipo: {t_manage}", key="del_btn_t"):
                    exec_sql("DELETE FROM type_orders WHERE type_id=?", (t_id_real,))
                    exec_sql("DELETE FROM types WHERE id=?", (t_id_real,))
                    st.rerun()
