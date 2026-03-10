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
            return True, "✅ Operación exitosa"
    except sqlite3.IntegrityError:
        return False, "❌ Error: Registro duplicado."
    except Exception as e:
        return False, f"❌ Error: {str(e)}"

def df_query(sql, params=()):
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql_query(sql, conn, params=params)

# --- MIGRACIÓN Y PERSISTENCIA ---
# Eliminamos initial_cleanup para que los usuarios no se borren.
# Aseguramos que la tabla history tenga la columna 'username'.
def ensure_db_structure():
    # Intenta agregar la columna username si no existe (Migración silenciosa)
    try:
        exec_sql("ALTER TABLE history ADD COLUMN username TEXT")
    except:
        pass # La columna ya existe

ensure_db_structure()

# =========================
# 2. LOGIN
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
# 3. INTERFAZ
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
    st.markdown(f'''
    <div class="figma-box">
        <h4>🎨 Guía de Posiciones</h4>
        <p>Valida los códigos en el Figma oficial antes de generar.</p>
        <a href="https://www.figma.com/design/ihSTaMfAmyN99BN5Z6sNps/Home-ULA?node-id=0-1&p=f&t=QoYAbgJju2kuyRIF-0" target="_blank" class="figma-button">IR A FIGMA</a>
    </div>
    ''', unsafe_allow_html=True)
    
    url_base = st.text_input("URL base", placeholder="https://...")
    
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
                
                # Guardamos incluyendo el nombre de usuario para el historial
                exec_sql("INSERT INTO history (created_at, country, hid_value, final_url, username) VALUES (?,?,?,?,?)",
                        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), pais, hid, f_url, st.session_state.auth["username"]))
                
                st.success(f"ID Generado: {hid}")
                st.code(f_url)
                time.sleep(2) # Confirmación visible por 2 segundos

# --- TAB 2: HISTORIAL ---
with tabs[1]:
    st.subheader("🕒 Registros Generados")
    
    # Lógica de filtrado: Admin ve todo, User ve solo lo suyo
    if st.session_state.auth["role"] == "admin":
        historial = df_query("SELECT created_at as Fecha, username as Usuario, country as Pais, hid_value as ID, final_url as URL FROM history ORDER BY id DESC")
    else:
        historial = df_query("SELECT created_at as Fecha, country as Pais, hid_value as ID, final_url as URL FROM history WHERE username=? ORDER BY id DESC", 
                             (st.session_state.auth["username"],))
        
    st.dataframe(historial, use_container_width=True)

# --- TAB 3: ADMINISTRACIÓN ---
with tabs[2]:
    st.title("⚙️ Panel de Administración")
    
    if st.session_state.auth["role"] == "admin":
        st.subheader("👤 Usuarios Registrados")
        users_df = df_query("SELECT id, username, role, created_at FROM users")
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
                    ok, msg = exec_sql("INSERT INTO users(username, role, salt, pwd_hash, created_at) VALUES (?,?,?,?,?)", 
                                      (new_u, new_r, salt, ph, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                    if ok: 
                        st.success("Registrado")
                        time.sleep(2)
                        st.rerun()
                    else: st.error(msg)
        
        with u_col2:
            if not users_df.empty:
                with st.expander("🗑️ Eliminar Usuario"):
                    sel_u = st.selectbox("Usuario a borrar", users_df['username'].tolist())
                    if st.button("Eliminar"):
                        if sel_u not in ['admin', 'luis_pena']:
                            exec_sql("DELETE FROM users WHERE username=?", (sel_u,))
                            st.warning(f"Usuario {sel_u} eliminado")
                            time.sleep(2)
                            st.rerun()

    # Resumen de Tipos (Visible para todos)
    st.divider()
    st.subheader("📊 Resumen de Tipos")
    sum_df = df_query("""SELECT t.id, t.name as Nombre, t.code as Código, COUNT(o.id) as Posiciones 
                         FROM types t LEFT JOIN type_orders o ON t.id = o.type_id GROUP BY t.id""")
    st.dataframe(sum_df[["Nombre", "Código", "Posiciones"]], use_container_width=True)

    # Mantenimiento (Solo Admin)
    if st.session_state.auth["role"] == "admin":
        st.divider()
        st.subheader("🛠️ Mantenimiento de Catálogos")
        col_cat, col_typ = st.columns(2)
        
        with col_cat:
            with st.expander("📁 Categorías"):
                cn = st.text_input("Nombre")
                cp = st.text_input("Prefijo")
                if st.button("Guardar Cat"):
                    exec_sql("INSERT INTO categories(name, prefix) VALUES (?,?)", (cn, cp))
                    st.success("Categoría guardada")
                    time.sleep(2)
                    st.rerun()

        with col_typ:
            with st.expander("➕ Añadir Nuevo Tipo"):
                tn = st.text_input("Nombre Componente")
                tc = st.text_input("Código")
                tp = st.number_input("Posiciones iniciales", 1, 100, 5) 
                if st.button("Crear"):
                    ok, msg = exec_sql("INSERT INTO types(name, code) VALUES (?,?)", (tn, tc))
                    if ok:
                        tid = df_query("SELECT id FROM types WHERE code=?", (tc,)).iloc[0]['id']
                        for i in range(1, int(tp)+1): 
                            exec_sql("INSERT INTO type_orders(type_id, order_no) VALUES (?,?)", (tid, i))
                        st.success("Tipo creado correctamente")
                        time.sleep(2)
                        st.rerun()

            if not sum_df.empty:
                with st.expander("📝 Editar / Borrar Tipo"):
                    sel_t = st.selectbox("Seleccionar Tipo", sum_df['Nombre'].tolist())
                    t_dat = sum_df[sum_df['Nombre'] == sel_t].iloc[0]
                    val_pos = max(1, int(t_dat['Posiciones']))
                    
                    en = st.text_input("Nuevo Nombre", value=t_dat['Nombre'])
                    ec = st.text_input("Nuevo Código", value=t_dat['Código'])
                    ep = st.number_input("Editar Posiciones", 1, 100, value=val_pos)
                    
                    c_upd, c_del = st.columns(2)
                    with c_upd:
                        if st.button("Actualizar"):
                            exec_sql("UPDATE types SET name=?, code=? WHERE id=?", (en, ec, int(t_dat['id'])))
                            old_p = int(t_dat['Posiciones'])
                            if ep > old_p:
                                for i in range(old_p + 1, int(ep) + 1): 
                                    exec_sql("INSERT INTO type_orders(type_id, order_no) VALUES (?,?)", (int(t_dat['id']), i))
                            elif ep < old_p:
                                exec_sql("DELETE FROM type_orders WHERE type_id=? AND order_no > ?", (int(t_dat['id']), int(ep)))
                            st.success("Cambios aplicados")
                            time.sleep(2)
                            st.rerun()
                    
                    with c_del:
                        if st.button(f"🗑️ Eliminar {sel_t}"):
                            tid = int(t_dat['id'])
                            exec_sql("DELETE FROM type_orders WHERE type_id=?", (tid,))
                            exec_sql("DELETE FROM types WHERE id=?", (tid,))
                            st.warning(f"Tipo '{sel_t}' eliminado")
                            time.sleep(2)
                            st.rerun()
