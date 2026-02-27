# ... (mismo código de inicio, estilos y auth)

# =========================
# TAB ADMINISTRACIÓN
# =========================
if st.session_state.auth["role"] == "admin":
    with tabs[2]:
        # ... (sección de gestión de usuarios sin cambios)
        
        st.divider()

        # --- SECCIÓN CATÁLOGOS CORREGIDA ---
        st.subheader("📁 Mantenimiento de Catálogos")
        cl, cr = st.columns(2)
        
        with cl:
            st.write("**Categorías**")
            with st.expander("➕ Añadir Categoría"):
                cat_n = st.text_input("Nombre", key="add_cat_name")
                cat_p = st.text_input("Prefijo", key="add_cat_pref")
                if st.button("Guardar Categoría", key="btn_save_cat"):
                    exec_sql("INSERT INTO categories(name, prefix) VALUES (?,?)", (cat_n, cat_p))
                    st.toast(f"✅ Categoría '{cat_n}' creada")
                    time.sleep(1); st.rerun()
            
            if not cats_df.empty:
                c_sel_ed = st.selectbox("Editar/Borrar", cats_df['name'].tolist(), key="sb_cat_edit")
                row_c = cats_df[cats_df['name'] == c_sel_ed].iloc[0]
                with st.expander("📝 Editar"):
                    ed_cn = st.text_input("Nombre", value=row_c['name'], key="e_cat_n")
                    ed_cp = st.text_input("Prefijo", value=row_c['prefix'], key="e_cat_p")
                    if st.button("Actualizar Categoría", key="btn_upd_cat"):
                        exec_sql("UPDATE categories SET name=?, prefix=? WHERE id=?", (ed_cn, ed_cp, int(row_c['id'])))
                        st.toast("✅ Categoría actualizada")
                        time.sleep(1); st.rerun()
                
                # Botón de eliminar categoría (siempre visible al seleccionar una)
                if st.button(f"❌ Eliminar Categoría: {c_sel_ed}", key="btn_del_cat"):
                    exec_sql("DELETE FROM categories WHERE id=?", (int(row_c['id']),))
                    st.toast("🗑️ Categoría eliminada")
                    time.sleep(1); st.rerun()

        with cr:
            st.write("**Tipos de Componentes**")
            with st.expander("➕ Añadir Nuevo Tipo"):
                tp_n = st.text_input("Nombre", key="add_tp_name")
                tp_c = st.text_input("Código", key="add_tp_code")
                tp_o = st.number_input("Posiciones iniciales", 1, 50, 5, key="add_tp_pos")
                if st.button("Crear Tipo", key="btn_create_type"):
                    exec_sql("INSERT INTO types(name, code) VALUES (?,?)", (tp_n, tp_c))
                    new_id_res = df_query("SELECT id FROM types WHERE code=?", (tp_c,))
                    if not new_id_res.empty:
                        new_id = new_id_res.iloc[0]['id']
                        for i in range(1, int(tp_o)+1): 
                            exec_sql("INSERT INTO type_orders(type_id, order_no) VALUES (?,?)", (new_id, i))
                        st.toast(f"✅ Tipo '{tp_n}' creado")
                        time.sleep(1); st.rerun()

            if not types_df.empty:
                t_sel_ed = st.selectbox("Seleccionar para Editar/Borrar", types_df['name'].tolist(), key="sb_tp_edit")
                row_t = types_df[types_df['name'] == t_sel_ed].iloc[0]
                tid = int(row_t['id'])
                current_count = len(df_query("SELECT id FROM type_orders WHERE type_id=?", (tid,)))
                
                with st.expander("📝 Editar Seleccionado"):
                    ed_tn = st.text_input("Nuevo Nombre Tipo", value=row_t['name'], key="e_tp_n")
                    ed_tc = st.text_input("Nuevo Código", value=row_t['code'], key="e_tp_c")
                    ed_to = st.number_input("Cantidad de Posiciones", 1, 50, value=max(1, current_count), key="e_tp_o")
                    if st.button("Actualizar Tipo", key="btn_upd_type"):
                        exec_sql("UPDATE types SET name=?, code=? WHERE id=?", (ed_tn, ed_tc, tid))
                        if ed_to > current_count:
                            for i in range(current_count + 1, int(ed_to) + 1):
                                exec_sql("INSERT INTO type_orders(type_id, order_no) VALUES (?,?)", (tid, i))
                        elif ed_to < current_count:
                            exec_sql("DELETE FROM type_orders WHERE type_id=? AND order_no > ?", (tid, int(ed_to)))
                        st.toast(f"✅ Tipo '{ed_tn}' actualizado")
                        time.sleep(1); st.rerun()
                
                # OPCIÓN DE BORRAR TIPOS REINCORPORADA
                st.markdown("---")
                if st.button(f"🗑️ Eliminar Tipo: {t_sel_ed}", key="btn_del_type"):
                    # Borramos primero las órdenes relacionadas para mantener integridad
                    exec_sql("DELETE FROM type_orders WHERE type_id=?", (tid,))
                    exec_sql("DELETE FROM types WHERE id=?", (tid,))
                    st.toast(f"✅ Tipo '{t_sel_ed}' y sus posiciones han sido eliminados")
                    time.sleep(1); st.rerun()
