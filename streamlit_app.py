import streamlit as st
import sqlite3
import pandas as pd
import hashlib
import secrets
import re
from datetime import datetime
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse
from pathlib import Path
import streamlit.components.v1 as components

# =========================
# Config
# =========================
APP_TITLE = "Generador de Links"
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = str(BASE_DIR / "links.db")  # ruta absoluta

UNICOMER_LOGO = "https://grupounicomer.com/wp-content/uploads/2022/12/logo-sol-gris.png"
UNICOMER_BLUE = "#002d5a"
UNICOMER_YELLOW = "#fdbb2d"


FIGMA_URL = "https://www.figma.com/design/ihSTaMfAmyN99BN5Z6sNps/Home-ULA?node-id=0-1&t=0q58oIwyTto6wv3R-1"

# =========================
# Seed: Tipos Home + Códigos
# =========================
HOME_TYPES = [
    ("BannerRotativo", "rtv"),
    ("MejoresOfertas", "topd"),
    ("CategoriasDestacadas", "dtd"),
    ("BloqueFomo", "bcr"),
    ("MoreDeals", "dls"),
    ("Carrusel1Ofertas", "bts"),
    ("BannerMultiuso1", "bmuno"),
    ("Carrusel2Ofertas", "npd"),
    ("BannerMultiuso2", "bmdos"),
    ("Carrusel3Ofertas", "cdp"),
    ("Carousel4Ofertas", "cci"),
    ("CarouselconImagen", "imb"),
    ("MarcasDestacadas", "mdt"),
    ("BloqueDeBeneficios", "icb"),
    ("CintilloBajoRotativo", "cbr"),
    ("BannerMultiuso3", "bmtres"),

    # extras Home
    ("MoreDealsRotativo", "mdr"),
    ("CarruselConPortada", "ccp"),
    ("MoreDealsCarrusel", "mdc"),
    ("BannerMoreDealsCarrusel", "bmdc"),
    ("BannerDeCategoria", "bdct"),
    ("DobleBannerMultiuso", "dbm"),
    ("BannerLateral", "bnl"),
    ("MoreDealsde4", "mddc"),
    ("MoreDealsVersion2", "mdvd"),
    ("BannerMulticarruselCP", "bpm"),
    ("CategoriasDestacadasDos", "dtddos"),
    ("CategoriasDestacadasTres", "cdtres"),
    ("ProductTop", "pdtop"),
    ("TopCategories", "tcat"),
    ("FomoAdviento", "fad"),
    ("PopUp", "popup"),
    ("BannerMultiusoCP", "bmcp"),
    ("PopUp2", "popdos"),
    ("BotonLateral", "btl"),
]

# =========================
# Orders por código (máximo) según tu Excel
# Si no está aquí => 1..20 por defecto
# =========================
ORDER_MAX_BY_CODE = {
    # “clásicos” (según capturas)
    "rtv": 6,
    "topd": 1,
    "dtd": 1,
    "bcr": 4,
    "dls": 6,
    "bts": 1,
    "bmuno": 1,
    "npd": 1,
    "bmdos": 1,
    "cdp": 1,
    "cci": 1,
    "imb": 1,
    "mdt": 1,
    "icb": 1,
    "cbr": 1,
    "bmtres": 1,

    # extras Home
    "mdr": 6,
    "ccp": 1,
    "mdc": 6,
    "bmdc": 1,
    "bdct": 10,
    "dbm": 2,
    "bnl": 1,
    "mddc": 4,
    "mdvd": 9,
    "bpm": 11,
    "dtddos": 3,
    "cdtres": 14,
    "pdtop": 6,
    "tcat": 6,
    "fad": 6,
    "popup": 1,
    "bmcp": 3,
    "popdos": 1,
    "btl": 1,
}

DEFAULT_ORDER_RANGE = list(range(1, 21))

# =========================
# Auth helpers
# =========================
def _hash_password(password: str, salt_hex: str) -> str:
    data = (salt_hex + password).encode("utf-8")
    return hashlib.sha256(data).hexdigest()

def make_password_record(password: str) -> tuple[str, str]:
    salt_hex = secrets.token_hex(16)
    pwd_hash = _hash_password(password, salt_hex)
    return salt_hex, pwd_hash

def verify_password(password: str, salt_hex: str, pwd_hash: str) -> bool:
    return _hash_password(password, salt_hex) == (pwd_hash or "")

# =========================
# DB helpers
# =========================
def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def df_query(sql, params=()):
    conn = get_conn()
    df = pd.read_sql_query(sql, conn, params=params)
    conn.close()
    return df

def exec_sql(sql, params=()):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(sql, params)
    conn.commit()
    conn.close()

def _table_exists(cur, name: str) -> bool:
    cur.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,))
    return cur.fetchone() is not None

def _get_cols(cur, table: str) -> list[str]:
    cur.execute(f"PRAGMA table_info({table})")
    return [r[1] for r in cur.fetchall()]

# =========================
# Schema / init
# =========================
def _ensure_users_schema(cur):
    if not _table_exists(cur, "users"):
        cur.execute("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            role TEXT NOT NULL DEFAULT 'user',
            salt TEXT,
            pwd_hash TEXT,
            created_at TEXT NOT NULL
        );
        """)
        return

    cols = set(_get_cols(cur, "users"))
    if "role" not in cols:
        cur.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user'")
    if "salt" not in cols:
        cur.execute("ALTER TABLE users ADD COLUMN salt TEXT")
    if "pwd_hash" not in cols:
        cur.execute("ALTER TABLE users ADD COLUMN pwd_hash TEXT")
    if "created_at" not in cols:
        cur.execute("ALTER TABLE users ADD COLUMN created_at TEXT NOT NULL DEFAULT ''")

    if "password_hash" in cols and "pwd_hash" in cols:
        cur.execute("""
            UPDATE users
            SET password_hash = pwd_hash
            WHERE (password_hash IS NULL OR password_hash = '')
              AND (pwd_hash IS NOT NULL AND pwd_hash <> '')
        """)

    cur.execute("UPDATE users SET created_at=? WHERE created_at IS NULL OR created_at=''",
                (datetime.now().isoformat(timespec="seconds"),))

def _ensure_tables(conn):
    cur = conn.cursor()
    _ensure_users_schema(cur)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        prefix TEXT NOT NULL
    );
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS types (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        code TEXT NOT NULL
    );
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS type_orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type_id INTEGER NOT NULL,
        order_no INTEGER NOT NULL,
        UNIQUE(type_id, order_no)
    );
    """)

    # History con country
    cur.execute("""
    CREATE TABLE IF NOT EXISTS history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        base_url TEXT NOT NULL,
        final_url TEXT NOT NULL,
        country TEXT,
        category_id INTEGER,
        category_name TEXT,
        type_id INTEGER,
        type_name TEXT,
        type_code TEXT,
        order_value TEXT,
        hid_value TEXT
    );
    """)

    # Migración: agregar country si la tabla ya existía sin esa columna
    cols_hist = set(_get_cols(cur, "history"))
    if "country" not in cols_hist:
        cur.execute("ALTER TABLE history ADD COLUMN country TEXT")

    # índices únicos
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_categories_name ON categories(name)")
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_types_code ON types(code)")
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_users_username ON users(username)")

    conn.commit()

def _upsert_category(conn, name: str, prefix: str):
    cur = conn.cursor()
    cur.execute("UPDATE categories SET prefix=? WHERE name=?", (prefix, name))
    if cur.rowcount == 0:
        try:
            cur.execute("INSERT INTO categories(name, prefix) VALUES (?,?)", (name, prefix))
        except sqlite3.IntegrityError:
            cur.execute("UPDATE categories SET prefix=? WHERE name=?", (prefix, name))

def _upsert_type(conn, name: str, code: str):
    cur = conn.cursor()
    cur.execute("UPDATE types SET name=? WHERE code=?", (name, code))
    if cur.rowcount == 0:
        try:
            cur.execute("INSERT INTO types(name, code) VALUES (?,?)", (name, code))
        except sqlite3.IntegrityError:
            cur.execute("UPDATE types SET name=? WHERE code=?", (name, code))

def _ensure_orders_for_code(conn, code: str):
    cur = conn.cursor()
    cur.execute("SELECT id FROM types WHERE code=?", (code,))
    row = cur.fetchone()
    if not row:
        return
    tid = row[0]

    cur.execute("SELECT COUNT(*) FROM type_orders WHERE type_id=?", (tid,))
    has = cur.fetchone()[0]
    if has > 0:
        return

    max_n = ORDER_MAX_BY_CODE.get(code, 20)
    for n in range(1, max_n + 1):
        cur.execute(
            "INSERT OR IGNORE INTO type_orders(type_id, order_no) VALUES (?,?)",
            (tid, n),
        )

def init_db():
    conn = get_conn()
    _ensure_tables(conn)
    cur = conn.cursor()

    # Seed admin
    cur.execute("SELECT 1 FROM users WHERE lower(trim(username))='admin'")
    if not cur.fetchone():
        salt, pwd_hash = make_password_record("admin123")
        cur.execute(
            "INSERT INTO users(username, role, salt, pwd_hash, created_at) VALUES (?,?,?,?,?)",
            ("admin", "admin", salt, pwd_hash, datetime.now().isoformat(timespec="seconds")),
        )
    else:
        cur.execute("UPDATE users SET role='admin' WHERE lower(trim(username))='admin'")

    # Seed categories (solo si está vacía)
    cur.execute("SELECT COUNT(*) FROM categories")
    if cur.fetchone()[0] == 0:
        for n, p in [("Home", "hm"), ("PLP", "plp"), ("PDP", "pdp"), ("CLP", "clp")]:
            _upsert_category(conn, n, p)

    # Seed tipos Home (solo si está vacía)
    cur.execute("SELECT COUNT(*) FROM types")
    if cur.fetchone()[0] == 0:
        for name, code in HOME_TYPES:
            _upsert_type(conn, name, code)
        
        # Seed orders por tipo (solo al inicio)
        for _, code in HOME_TYPES:
            _ensure_orders_for_code(conn, code)

    conn.commit()
    conn.close()

def get_user(username: str):
    u = (username or "").strip().lower()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT username, role, salt, pwd_hash FROM users WHERE lower(trim(username)) = ?", (u,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return {"username": row[0], "role": row[1] or "user", "salt": row[2] or "", "pwd_hash": row[3] or ""}

# =========================
# URL helpers
# =========================
def build_url_with_params(base_url: str, new_params: dict) -> str:
    parsed = urlparse(base_url.strip())
    existing = dict(parse_qsl(parsed.query, keep_blank_values=True))
    merged = {**existing, **{k: v for k, v in new_params.items() if v is not None and str(v).strip() != ""}}
    query = urlencode(merged, doseq=True)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, query, parsed.fragment))

def make_hid(prefix: str, type_code: str, order_value: str) -> str:
    return "_".join([prefix, type_code, str(order_value).strip()])

# =========================
# CSS Styles (Unicomer)
# =========================
def apply_custom_styles():
    st.markdown(f"""
    <style>
        /* Sidebar background */
        [data-testid="stSidebar"] {{
            background-color: {UNICOMER_BLUE};
            color: white;
        }}
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {{
            color: white;
        }}
        [data-testid="stSidebar"] .stTextInput label {{
            color: white !important;
        }}
        [data-testid="stSidebar"] .stButton button {{
            background-color: {UNICOMER_YELLOW};
            color: {UNICOMER_BLUE};
            border: none;
            font-weight: bold;
        }}
        
        /* Fonts */
        @import url('https://fonts.googleapis.com/css2?family=Ubuntu:wght@400;700&family=Open+Sans:wght@400;600&display=swap');
        
        html, body, [class*="css"]  {{
            font-family: 'Open Sans', sans-serif;
        }}
        h1, h2, h3, h4, h5, h6 {{
            font-family: 'Ubuntu', sans-serif;
            color: {UNICOMER_BLUE};
        }}
        
        /* General buttons matching Unicomer yellow */
        .stButton>button {{
            border-radius: 4px;
        }}
    </style>
    """, unsafe_allow_html=True)


# =========================
# Login UI
# =========================
def require_login():
    if "auth" not in st.session_state:
        st.session_state.auth = {"is_logged": False, "username": None, "role": None}

    auth = st.session_state.auth
    with st.sidebar:
        st.markdown("## 🔐 Inicio de sesión")

        if auth["is_logged"]:
            st.success(f"Sesión: **{auth['username']}**")
            st.caption(f"Rol: **{auth['role']}**")
            if st.button("Cerrar sesión"):
                st.session_state.auth = {"is_logged": False, "username": None, "role": None}
                st.rerun()
            st.divider()
            return

        user = st.text_input("Usuario", key="login_user")
        pwd = st.text_input("Contraseña", type="password", key="login_pwd")
        if st.button("Entrar", type="primary"):
            u = get_user(user)
            if not u or not verify_password(pwd, u["salt"], u["pwd_hash"]):
                st.error("Usuario o contraseña incorrectos.")
                st.stop()
            st.session_state.auth = {"is_logged": True, "username": u["username"], "role": u["role"]}
            st.rerun()

# =========================
# APP
# =========================
st.set_page_config(page_title=APP_TITLE, layout="wide")
apply_custom_styles()
init_db()

with st.sidebar:
    st.markdown(f"<div style='filter: brightness(0) invert(1);'><img src='{UNICOMER_LOGO}' width='200'></div>", unsafe_allow_html=True)
    st.divider()

st.title(APP_TITLE)

# Link grande Figma
st.markdown(
    f"""
<div style="padding:14px 16px; border-radius:14px; border:1px solid #e6e6e6; background:#fafafa;">
  <div style="font-size:18px; font-weight:700; margin-bottom:6px;">MOCKUPS DE LA APLICACIÓN</div>
  <div style="font-size:16px;">
    <a href="{FIGMA_URL}" target="_blank">{FIGMA_URL}</a>
  </div>
</div>
""",
    unsafe_allow_html=True,
)

require_login()
auth = st.session_state.auth
if not auth["is_logged"]:
    st.info("Iniciá sesión en el panel izquierdo.")
    st.stop()

is_admin = auth["role"] == "admin"

categories = df_query("SELECT id, name, prefix FROM categories ORDER BY id ASC")
types_df = df_query("SELECT id, name, code FROM types ORDER BY id ASC")

if is_admin:
    tabs = st.tabs(["✅ Generar link", "📚 Catálogos", "🧩 Orders por Tipo", "🕒 Historial", "👤 Usuarios"])
else:
    tabs = st.tabs(["✅ Generar link"])

# =========================
# TAB 0: Generar link
# =========================
with tabs[0]:
    colA, colB = st.columns([2, 1], gap="large")

    with colA:
        base_url = st.text_input("URL base", placeholder="https://www.gollo.com/c/muebles/camas-y-colchones")

        # País (nuevo)
        country_options = ["SV", "GT", "CR", "HN", "NI", "PA", "DO", "JM", "TT", "Otro"]
        c_sel = st.selectbox("País", options=country_options, index=0)
        if c_sel == "Otro":
            country = st.text_input("Escribí el país (ej: SV)", value="").strip().upper()
        else:
            country = c_sel.strip().upper()

        cat_options = [f"{row.id} — {row.name} ({row.prefix})" for row in categories.itertuples(index=False)]
        type_options = [f"{row.id} — {row.name} ({row.code})" for row in types_df.itertuples(index=False)]

        cat_sel = st.selectbox("Categoría (prefijo)", options=cat_options)
        type_sel = st.selectbox("Tipo (código)", options=type_options)

        category_id = int(cat_sel.split("—")[0].strip())
        type_id = int(type_sel.split("—")[0].strip())

        orders_df = df_query("SELECT order_no FROM type_orders WHERE type_id=? ORDER BY order_no ASC", (type_id,))
        orders_for_type = orders_df["order_no"].tolist() or DEFAULT_ORDER_RANGE
        order_value = st.selectbox("Order (según Tipo)", options=orders_for_type, index=0)

    with colB:
        if "last_final_url" not in st.session_state:
            st.session_state.last_final_url = ""
            st.session_state.last_hid = ""

        can_generate = bool(base_url.strip()) and bool(country.strip())

        if st.button("🔗 Generar link", type="primary", disabled=not can_generate):
            cat = categories[categories["id"] == category_id].iloc[0]
            tp = types_df[types_df["id"] == type_id].iloc[0]

            hid_value = make_hid(cat["prefix"], tp["code"], str(order_value))
            final_url = build_url_with_params(base_url, {"hid": hid_value})

            st.session_state.last_final_url = final_url
            st.session_state.last_hid = hid_value

            # Guardar historial (incluye country)
            conn = get_conn()
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO history(
                    created_at, base_url, final_url, country,
                    category_id, category_name, type_id, type_name, type_code,
                    order_value, hid_value
                )
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """, (
                datetime.now().isoformat(timespec="seconds"),
                base_url,
                final_url,
                country,
                int(cat["id"]),
                str(cat["name"]),
                int(tp["id"]),
                str(tp["name"]),
                str(tp["code"]),
                str(order_value),
                hid_value,
            ))
            conn.commit()
            conn.close()

        if st.session_state.last_final_url:
            st.code(st.session_state.last_final_url, language="text")
            st.write("**hid:**", st.session_state.last_hid)
            
            # Botón Copiar con componentes oficiales para máxima compatibilidad
            copy_html = f"""
            <html>
                <body style="margin: 0; padding: 0;">
                    <button id="btn-copiar" style="background-color: {UNICOMER_YELLOW}; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; font-weight: bold; color: {UNICOMER_BLUE}; font-family: sans-serif; display: flex; align-items: center; gap: 8px;">
                        📋 Copiar link
                    </button>
                    <script>
                    document.getElementById('btn-copiar').onclick = function() {{
                        const text = "{st.session_state.last_final_url}";
                        // Intentar primero con navigator.clipboard
                        if (navigator.clipboard) {{
                            navigator.clipboard.writeText(text).then(function() {{
                                alert('¡Link copiado correctamente! ✅');
                            }}).catch(function() {{
                                // Fallback a textarea si falla
                                copyFallback(text);
                            }});
                        }} else {{
                            copyFallback(text);
                        }}
                    }};

                    function copyFallback(text) {{
                        const textArea = document.createElement("textarea");
                        textArea.value = text;
                        textArea.style.position = "fixed";
                        textArea.style.left = "-9999px";
                        textArea.style.top = "0";
                        document.body.appendChild(textArea);
                        textArea.select();
                        try {{
                            document.execCommand('copy');
                            alert('¡Link copiado con éxito! ✅');
                        }} catch (err) {{
                            alert('Error al copiar el link. Intenta seleccionarlo manualmente.');
                        }}
                        document.body.removeChild(textArea);
                    }}
                    </script>
                </body>
            </html>
            """
            components.html(copy_html, height=50)
            st.divider()
            st.download_button("Descargar TXT", data=st.session_state.last_final_url, file_name="link.txt", mime="text/plain")

# =========================
# Admin tabs
# =========================
if is_admin:
    if st.button("🔄 Refrescar aplicación"):
        st.rerun()

    # TAB 1: Catálogos
    with tabs[1]:
        st.subheader("Catálogos")
        t1, t2 = st.tabs(["Categorías", "Tipos"])

        with t1:
            display_cats = categories.copy()
            display_cats.insert(0, "#", range(1, len(display_cats) + 1))
            st.dataframe(display_cats, use_container_width=True, hide_index=True)
            with st.expander("➕ Agregar/editar categoría"):
                c_name = st.text_input("Nombre", key="cat_name")
                c_prefix = st.text_input("Prefijo", key="cat_prefix")
                if st.button("Guardar categoría"):
                    if not c_name.strip() or not c_prefix.strip():
                        st.error("Nombre y prefijo son requeridos.")
                    else:
                        conn = get_conn()
                        _upsert_category(conn, c_name.strip(), c_prefix.strip())
                        conn.commit()
                        conn.close()
                        st.success(f"Categoría '{c_name}' guardada/actualizada con éxito ✅")
                        st.toast("Categoría guardada")
                        # st.rerun() # Quitamos el rerun inmediato para que se vea el mensaje
            
            with st.expander("❌ Eliminar categoría"):
                cat_del_options = [f"{row.id} — {row.name}" for row in categories.itertuples(index=False)]
                cat_to_del = st.selectbox("Seleccionar categoría para eliminar", options=cat_del_options, key="del_cat_sel")
                if st.button("Confirmar Eliminación de Categoría", type="primary"):
                    cid = int(cat_to_del.split("—")[0].strip())
                    c_name_del = cat_to_del.split("—")[1].strip()
                    exec_sql("DELETE FROM categories WHERE id=?", (cid,))
                    st.success(f"Categoría '{c_name_del}' eliminada correctamente 🗑️")
                    st.toast("Categoría eliminada")
                    st.rerun()

        with t2:
            display_types = types_df.copy()
            display_types.insert(0, "#", range(1, len(display_types) + 1))
            st.dataframe(display_types, use_container_width=True, hide_index=True)

            st.markdown("### 📥 Importar tipos (pegado masivo)")
            st.caption("Formato: `Nombre<TAB>código` o `id<TAB>Nombre<TAB>código`.")
            bulk = st.text_area("Lista", height=220, key="bulk_types")

            if st.button("Importar/actualizar tipos"):
                rows = []
                for line in bulk.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    parts = re.split(r"\t+", line)
                    if len(parts) >= 3 and parts[0].strip().isdigit():
                        name = parts[1].strip()
                        code = parts[2].strip()
                    elif len(parts) >= 2:
                        name = parts[0].strip()
                        code = parts[1].strip()
                    else:
                        continue
                    if name and code:
                        rows.append((name, code))

                if not rows:
                    st.error("No pude leer la lista. Usá TAB entre columnas.")
                else:
                    conn = get_conn()
                    for name, code in rows:
                        _upsert_type(conn, name, code)
                        _ensure_orders_for_code(conn, code)
                    conn.commit()
                    conn.close()
                    st.success(f"Tipos importados: {len(rows)} ✅")
                    st.rerun()

            st.markdown("### ➕ Agregar tipo manual")
            tp_name = st.text_input("Nombre", key="tp_name")
            tp_code = st.text_input("Código", key="tp_code")
            if st.button("Guardar tipo"):
                if not tp_name.strip() or not tp_code.strip():
                    st.error("Nombre y código son requeridos.")
                else:
                    conn = get_conn()
                    _upsert_type(conn, tp_name.strip(), tp_code.strip())
                    _ensure_orders_for_code(conn, tp_code.strip())
                    conn.commit()
                    conn.close()
                    st.success(f"Tipo '{tp_name}' guardado/actualizada con éxito ✅")
                    st.toast("Tipo guardado")
                    # st.rerun()
            
            with st.expander("❌ Eliminar tipo"):
                type_del_options = [f"{row.id} — {row.name} ({row.code})" for row in types_df.itertuples(index=False)]
                type_to_del = st.selectbox("Seleccionar tipo para eliminar", options=type_del_options, key="del_type_sel")
                if st.button("Confirmar Eliminación de Tipo", type="primary"):
                    parts = type_to_del.split("—")
                    tid_del = int(parts[0].strip())
                    t_name_del = parts[1].strip()
                    # También eliminar órdenes asociados
                    exec_sql("DELETE FROM type_orders WHERE type_id=?", (tid_del,))
                    exec_sql("DELETE FROM types WHERE id=?", (tid_del,))
                    st.success(f"Tipo '{t_name_del}' eliminado correctamente 🗑️")
                    st.toast("Tipo eliminado")
                    st.rerun()

    # TAB 2: Orders por Tipo
    with tabs[2]:
        st.subheader("Orders por Tipo")
        type_options = [f"{row.id} — {row.name} ({row.code})" for row in types_df.itertuples(index=False)]
        sel = st.selectbox("Tipo", options=type_options, key="orders_sel")
        tid = int(sel.split("—")[0].strip())
        code = sel.split("(")[-1].split(")")[0].strip()

        current = df_query("SELECT order_no FROM type_orders WHERE type_id=? ORDER BY order_no ASC", (tid,))
        cur_list = current["order_no"].tolist()

        default_max = ORDER_MAX_BY_CODE.get(code, 20)
        default_list = list(range(1, default_max + 1))

        pick = st.multiselect("Orders permitidos", options=DEFAULT_ORDER_RANGE, default=cur_list or default_list)

        if st.button("Guardar orders"):
            conn = get_conn()
            cur = conn.cursor()
            cur.execute("DELETE FROM type_orders WHERE type_id=?", (tid,))
            for n in sorted(set(int(x) for x in pick)):
                cur.execute("INSERT OR IGNORE INTO type_orders(type_id, order_no) VALUES (?,?)", (tid, n))
            conn.commit()
            conn.close()
            st.success("Orders actualizados ✅")
            st.rerun()

    # TAB 3: Historial (incluye país)
    with tabs[3]:
        st.subheader("Historial")
        hist = df_query("""
            SELECT id, created_at, country, base_url, final_url, category_name, type_code, order_value, hid_value
            FROM history
            ORDER BY id DESC
        """)
        st.dataframe(hist, use_container_width=True, hide_index=True)
        if st.button("Limpiar todo el historial"):
            exec_sql("DELETE FROM history")
            st.success("Historial limpiado")
            st.rerun()

    # TAB 4: Usuarios
    with tabs[4]:
        st.subheader("Usuarios")
        users_df = df_query("SELECT id, username, role, created_at FROM users ORDER BY id ASC")
        display_users = users_df.copy()
        display_users.insert(0, "#", range(1, len(display_users) + 1))
        st.dataframe(display_users, use_container_width=True, hide_index=True)

        with st.expander("➕ Crear usuario"):
            nu = st.text_input("Usuario", key="nu_user")
            npw = st.text_input("Contraseña", type="password", key="nu_pwd")
            role = st.selectbox("Rol", ["user", "admin"], key="nu_role")

            if st.button("Crear"):
                u_norm = (nu or "").strip().lower()
                if not u_norm or not npw:
                    st.error("Usuario y contraseña son requeridos.")
                else:
                    salt, pwd_hash = make_password_record(npw)
                    try:
                        exec_sql(
                            "INSERT INTO users(username, role, salt, pwd_hash, created_at) VALUES (?,?,?,?,?)",
                            (u_norm, role, salt, pwd_hash, datetime.now().isoformat(timespec="seconds")),
                        )
                        st.success("Usuario creado ✅")
                        st.rerun()
                    except sqlite3.IntegrityError as e:
                        exists = df_query(
                            "SELECT id, username, role, created_at FROM users WHERE lower(trim(username)) = ?",
                            (u_norm,),
                        )
                        if not exists.empty:
                            st.error(f"Ese usuario ya existe (id={int(exists.iloc[0]['id'])}, rol={exists.iloc[0]['role']}).")
                        else:
                            st.error("No se pudo crear el usuario por una restricción de la base (IntegrityError).")
                            st.code(str(e))

        with st.expander("🔑 Cambiar contraseña"):
            u = st.text_input("Usuario existente", key="pw_user")
            newpw = st.text_input("Nueva contraseña", type="password", key="pw_new")
            if st.button("Actualizar contraseña"):
                u_norm = (u or "").strip().lower()
                if not u_norm or not newpw:
                    st.error("Usuario y nueva contraseña son requeridos.")
                else:
                    salt, pwd_hash = make_password_record(newpw)
                    conn = get_conn()
                    cur = conn.cursor()
                    cur.execute("UPDATE users SET salt=?, pwd_hash=? WHERE lower(trim(username))=?", (salt, pwd_hash, u_norm))
                    conn.commit()
                    conn.close()
                    st.success("Contraseña actualizada ✅")

        with st.expander("❌ Eliminar usuario"):
            user_del_options = users_df[users_df["username"] != "admin"]["username"].tolist()
            user_to_del = st.selectbox("Seleccionar usuario para eliminar", options=user_del_options)
            if st.button("Eliminar Usuario", type="primary"):
                if user_to_del.lower() == "admin":
                    st.error("No se puede eliminar el usuario administrador.")
                else:
                    exec_sql("DELETE FROM users WHERE username=?", (user_to_del,))
                    st.success(f"Usuario {user_to_del} eliminado")
                    st.rerun()
