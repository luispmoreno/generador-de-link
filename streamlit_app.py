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

# --- FUNCIONES DB ---
def exec_sql(sql, params=()):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.cursor()
            cur.execute(sql, params)
            conn.commit()
            return True, "✅ Acción realizada con éxito"
    except sqlite3.IntegrityError:
        return False, "❌ Error: Ese registro ya existe"
    except Exception as e:
        return False, f"❌ Error: {str(e)}"

def df_query(sql, params=()):
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql_query(sql, conn, params=params)

# =========================
# 2. LIMPIEZA DE USUARIOS (SOLO ADMIN Y LUIS_PENA)
# =========================
# Esta función asegura que solo existan los usuarios base para evitar errores de duplicados al crear nuevos.
def reset_user_table():
    exec_sql("DELETE FROM users WHERE username NOT IN ('admin', 'luis_pena')")

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
    st.markdown(f'<img src="{UNICOMER_LOGO_URL}" class="white-logo">', unsafe_allow_html=True)
    st.write(f"👤 **{st.session_state.auth['username']}**")
    if st.button("Cerrar Sesión"):
        st.session_state.auth = {"is_logged": False}
        st.rerun()

tabs = st.tabs(["✅ Generador", "🕒 Historial", "⚙️ Administración"])

# --- TAB 1: GENERADOR ---
with tabs[0]:
    # Guía con botón clickeable para Figma
    st.markdown(f'''
    <div class="figma-box">
        <h4>🎨 Guía de Posiciones</h4>
        <p>Valida los códigos en el Figma oficial antes de generar.</p>
        <a href="https://www.figma.com/proto/..." target="_blank" class="figma-button">IR A FIGMA</a>
    </div>
    ''', unsafe_allow_html=True)
    
    url_base = st.text_input("URL base", placeholder="https://www.lacuracaonline.com/...")
    
    # ... (Resto de la lógica de generación se mantiene igual)
    c1, c2, c3 = st.columns(3)
    pais = c1.selectbox("País", ["SV", "GT", "CR", "HN", "NI", "PA", "DO", "JM", "TT"])
    cats_df = df_query("SELECT id, name, prefix FROM categories")
    cat_sel = c2.selectbox("Categoría", [f"{r.name} ({r.prefix})" for r in cats_df.itertuples()] if not cats_df.empty else ["N/A"])
    typs_df = df_query("SELECT id, name, code FROM types")
    type_sel = c3.selectbox("Tipo", [f"{r.name} ({r.code})" for r in typs_df.itertuples()] if not typs_df.empty else ["N/A"])
    
    if "(" in type_sel and "(" in cat_sel:
        t_code = type_sel.split("(")[1].replace(")", "")
        t_id = typs_df[typs_df['code'] == t_code]['id'].values[0]
        pos_df = df_query("SELECT order_no FROM type_orders WHERE type_id=? ORDER BY order_no", (int(t_id),))
        pos = st.selectbox("Posición (Orden)", pos_df['order_no'].tolist() if not pos_df.empty else [1])
        
        if st.button("GENERAR ID Y LINK"):
            if url_base.strip():
                pref = cat_sel.split("(")[1].replace(")", "")
                hid = f"{pref}_{t_code}_{pos}"
                p_url = urlparse(url_base.strip())
                qs = dict(parse_qsl(p_url.query))
                qs['hid'] = hid
                f_url = urlunparse(p_url._replace(query=urlencode(qs)))
                
                exec_sql("INSERT INTO history (created_at, country, hid_value, final_url) VALUES (?,?,?,?)",
                        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), pais, hid, f_url))
                st.success(f"ID Generado: {hid}")
                st.code(f_url)

# --- TAB 2: HISTORIAL ---
with tabs[1]:
    st.subheader("🕒 Registros Generados")
    historial = df_query("SELECT created_at as Fecha, country as Pais, hid_value as ID, final_url as URL FROM history ORDER BY id DESC")
    st.dataframe(historial, use_container_width=True)

# --- TAB 3: ADMINISTRACIÓN ---
if st.session_state.auth["role"] == "admin":
    with tabs[2]:
        st.title("⚙️ Panel de Administración")
        
        # 1. GESTIÓN DE USUARIOS (RESTAURADO Y PROTEGIDO)
        st.subheader("👤 Gestión de Usuarios")
        
        # Botón para limpiar usuarios adicionales y evitar errores de "ya existe"
        if st.button("🧹 Limpiar Usuarios Adicionales (Mantener solo Admin y Luis)"):
            reset_user_table()
            st.success("Tabla de usuarios limpiada exitosamente.")
            time.sleep(1)
            st.rerun()

        users_df = df_query("SELECT id, username, role FROM users")
        st.dataframe(users_df, use_container_width=True)
        
        u_col1, u_col2 = st.columns(2)
        with u_col1:
            with st.expander("➕ Crear Nuevo Usuario"):
                new_u = st.text_input("Nombre de Usuario", key="n_u")
                new_p = st.text_input("Contraseña", type="password", key="n_p")
                new_r = st.selectbox("Rol", ["admin", "user"], key="n_r")
                if st.button("Registrar Usuario"):
                    salt = secrets.token_hex(16)
                    ph = hashlib.sha256((salt + new_p).encode("utf-8")).hexdigest()
                    ok, msg = exec_sql("INSERT INTO users(username, role, salt, pwd_hash) VALUES (?,?,?,?)", (new_u, new_r, salt, ph))
                    if ok: st.success(msg); time.sleep(1); st.rerun()
                    else: st.error(msg)
        
        with u_col2:
            if not users_df.empty:
                with st.expander("📝 Editar / Eliminar Usuario"):
                    sel_user = st.selectbox("Seleccionar usuario para editar", users_df['username'].tolist(), key="s_u_edit")
                    u_info = users_df[users_df['username'] == sel_user].iloc[0]
                    
                    # Auto-relleno de rol actual
                    new_role = st.selectbox("Cambiar Rol", ["admin", "user"], index=0 if u_info['role'] == 'admin' else 1)
                    new_pass = st.text_input("Cambiar Contraseña (dejar vacío para mantener)", type="password")
                    
                    if st.button("Actualizar Datos"):
                        if new_pass:
                            salt = secrets.token_hex(16)
                            ph = hashlib.sha256((salt + new_pass).encode("utf-8")).hexdigest()
                            exec_sql("UPDATE users SET role=?, salt=?, pwd_hash=? WHERE username=?", (new_role, salt, ph, sel_user))
                        else:
                            exec_sql("UPDATE users SET role=? WHERE username=?", (new_role, sel_user))
                        st.success("✅ Usuario actualizado correctamente"); time.sleep(1); st.rerun()
                    
                    if st.button("🗑️ Eliminar Usuario"):
                        if sel_user not in ['admin', 'luis_pena']:
                            ok, msg = exec_sql("DELETE FROM users WHERE username=?", (sel_user,))
                            if ok: st.success(msg); time.sleep(1); st.rerun()
                        else: st.error("No se pueden eliminar administradores base.")

        # ... (Siguientes secciones de Catálogos y Tipos con auto-relleno se mantienen intactas)
        st.divider()
        st.subheader("🛠️ Mantenimiento de Catálogos")
        # (Lógica de Categorías y Tipos continúa aquí...)
