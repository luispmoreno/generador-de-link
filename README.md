
# Generador de Links (Reemplazo Excel)

Esta app reemplaza tu Excel/macros y te permite:
- Mantener catálogos editables: **Categorías (prefijos)**, **Tipos (códigos)** y **Elementos** (campos extra).
- Generar links automáticamente agregando `hid=` y opcionalmente otros parámetros.
- Guardar cada link en un **historial**.
- Exportar todo a Excel o respaldar la base SQLite.

## Cómo correr
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Qué es un "Elemento"
Un elemento es un campo extra que podés agregar sin tocar código (ej: `campaign`, `placement`, `subcat`, etc.).
- `Include in HID`: agrega ese valor al final del HID, separado por `_`.
- `Include as query param`: agrega `&key=valor` en la URL.

## Base de datos
Se guarda en `links.db` (SQLite) en la misma carpeta.
