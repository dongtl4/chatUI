import streamlit as st
import pathlib
import src.core.knowledge as kb_logic
import src.core.db as db_logic
from agno.filters import AND, EQ, IN, NOT
from uuid import uuid4

def render(history_db=None):
    st.header("📚 Knowledge File Management")

    if history_db is None:
        history_db = db_logic.get_db()

    # Verify connection first
    if st.session_state.get('kb_active_type') != "PostgreSQL + PGVector" or not st.session_state.get('kb_confirmed_config'):
        st.error("Please configure the PostgreSQL connection in 'Connect Database' first.")
        return

    # Initialize KB Connection
    try:
        knowledge = kb_logic.setup_knowledge_base(st.session_state['kb_confirmed_config'])
    except Exception as e:
        st.error(f"Could not connect to Knowledge Base: {e}")
        return

    col_add_url, col_add_file = st.columns(2)

    # --- Add URLs ---
    with col_add_url:
        st.subheader("🌐 Add URLs")
        urls_input = st.text_area("Enter URLs (one per line)", height=100)
        if st.button("Add URLs"):
            if urls_input:
                urls = [url.strip() for url in urls_input.split('\n') if url.strip()]
                if urls:
                    with st.spinner("Processing URLs..."):
                        try:
                            for url in urls:
                                knowledge.add_web_page(url)
                            st.success(f"Added {len(urls)} URLs successfully!")
                        except Exception as e:
                            st.error(f"Error adding URLs: {e}")
            else:
                st.warning("Please enter at least one URL.")

    # --- Add Files ---
    with col_add_file:
        if "file_uploader_key" not in st.session_state:
            st.session_state["file_uploader_key"] = 0
        st.subheader("📄 Add Files")
        uploaded_files = st.file_uploader(
            "Upload PDFs/Text", 
            accept_multiple_files=True, 
            key=f"uploader_{st.session_state['file_uploader_key']}"
        )
        
        if st.button("Add File(s)", type="primary"):
            if uploaded_files:
                with st.spinner("📥 Loading documents..."):
                    contents_to_add = []
                    temp_paths = []
                    pathlib.Path("tmp").mkdir(parents=True, exist_ok=True)

                    for file in uploaded_files:
                        temp_path = pathlib.Path("tmp") / file.name
                        with open(temp_path, "wb") as f:
                            f.write(file.getbuffer())
                        metaid = str(uuid4())
                        contents_to_add.append({
                            "path": str(temp_path),
                            "name": file.name,
                            "metadata": {"metaid": metaid},
                        })
                        temp_paths.append(temp_path)

                    try:
                        if contents_to_add:
                            knowledge.add_contents(contents_to_add)
                            st.success(f"✅ Added {len(contents_to_add)} file(s)")
                        
                        for path in temp_paths:
                            if path.exists(): path.unlink()
                                
                    except Exception as e:
                        st.error(f"Error adding files: {e}")
                    
                    st.session_state["file_uploader_key"] += 1
                    st.rerun()

    st.divider()
    st.subheader("🗄️ Stored Knowledge")
    
    # --- Fetch Content List ---
    try:
        contents, _ = knowledge.contents_db.get_knowledge_contents()
    except Exception as e:
        st.error(f"Error fetching knowledge contents: {e}")
        contents = []

    # --- Fetch Marked Docs for Session ---
    current_session_id = st.session_state.get("session_id")
    marked_metaids = []
    if current_session_id:
        marked_metaids = db_logic.get_session_documents(history_db, current_session_id)

    if contents:
        # Column headers
        mark_col, del_col, name_col = st.columns([1, 1, 6])
        with mark_col:
            st.markdown("**Mark Sel**")
        with del_col:
            st.markdown("**Del Sel**")
        with name_col:
            st.markdown("**Document Name**")

        st.markdown("""
            <style>
                div[class*="st-key-knowledge_management_checkboxes_container_"] div[data-testid="stCheckbox"] {
                    margin-top: 0px !important;
                }
            </style>
            """, unsafe_allow_html=True)
        
        # Display list with checkboxes
        for content in contents:
            col_mark, col_del, col_name = st.columns([1, 1, 6])
            
            # --- 1. Mark Column ---
            with col_mark:
                content_metaid = content.metadata.get("metaid") if content.metadata else None
                is_checked = (content_metaid in marked_metaids) if content_metaid else False
                
                # Key: sel_{id}_{session}
                chk_key = f"sel_{content.id}_{current_session_id}"
                
                with st.container(key=f"knowledge_management_checkboxes_container_{chk_key}_mark"):
                    if current_session_id and content_metaid:
                        st.checkbox("select box", value=is_checked, key=chk_key, label_visibility="collapsed")
                    else:
                        st.checkbox("select box", value=False, key=chk_key, label_visibility="collapsed", disabled=True)
            
            # --- 2. Delete Column ---
            with col_del:
                # Key: del_sel_{id}_{session} 
                del_key = f"del_{chk_key}"
                with st.container(key=f"knowledge_management_checkboxes_container_{chk_key}_del"):
                    st.checkbox("select box", value=False, key=del_key, label_visibility="collapsed")
            
            # --- 3. Name Column ---
            with col_name:
                st.write(content.name)
        
        st.write("") 
        
        c_mark, c_del = st.columns(2)

        # --- Button 1: Mark Selected Documents ---
        with c_mark:
            if st.button("📌 Mark Selected Documents for Custom RAG"):
                if not current_session_id:
                    st.error("No active session found.")
                else:
                    selected_metaids = []
                    for content in contents:
                        chk_key = f"sel_{content.id}_{current_session_id}"
                        # Check the Mark checkbox state
                        if st.session_state.get(chk_key):
                            metaid = content.metadata.get("metaid")
                            if metaid:
                                selected_metaids.append(metaid)
                    
                    db_logic.save_session_documents(history_db, current_session_id, selected_metaids)
                    st.success(f"Marked {len(selected_metaids)} documents for session '{current_session_id}'!")
                    st.rerun()

        # --- Button 2: Delete Selected Documents ---
        with c_del:
            if st.button("🗑️ Delete Selected from KB"):
                selected_items_to_del = []
                for content in contents:
                    chk_key = f"sel_{content.id}_{current_session_id}"
                    del_key = f"del_{chk_key}"
                    
                    # Check the DELETE checkbox state
                    if st.session_state.get(del_key):
                        selected_items_to_del.append(content)
                
                if not selected_items_to_del:
                    st.warning("Please select at least one document to delete.")
                else:
                    try:
                        with st.spinner(f"Deleting {len(selected_items_to_del)} documents..."):
                            for item in selected_items_to_del:
                                metaid = item.metadata.get("metaid")
                                # 1. Remove from usages DB (This effectively "unpresses" the mark button)
                                if metaid:
                                    db_logic.remove_document_from_usages(history_db, metaid)
                                
                                # 2. Remove from actual Knowledge Base
                                knowledge.remove_content_by_id(item.id)
                        
                        st.success("Selected documents deleted successfully!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error deleting documents: {e}")

    # --- Clear Database Utility ---
    if st.button("⚠️ Clear Entire Database"):
        try:
            with st.spinner("Clearing database..."):
                contents_to_clear, _ = knowledge.contents_db.get_knowledge_contents()
                for content in contents_to_clear:
                    metaid = content.metadata.get("metaid")
                    if metaid:
                        db_logic.remove_document_from_usages(history_db, metaid)
                    knowledge.remove_content_by_id(content.id)
                st.success("Knowledge base cleared!")
                st.rerun()
        except Exception as e:
            st.error(f"Error clearing database: {e}")

    st.divider()
    st.subheader("Quick Test Query 🔍")
    st.checkbox("Use custom RAG filtering based on marked documents", key="use_knowledge_filter", value=False)
    test_query = st.text_input("Enter a test query to validate knowledge integration")
    if st.button("Run Test Query"):
        if not test_query.strip():
            st.warning("Please enter a valid query.")
        else:
            try:
                filters = [IN("metaid", marked_metaids)] if marked_metaids else None
                with st.spinner(f"Running test query for '{test_query}'..."):
                    response = knowledge.vector_db.search(
                        query=test_query,
                        limit=5,
                        filters=filters if st.session_state["use_knowledge_filter"] else None,
                    )
                    st.markdown(f"**Response for query '{test_query}':**")
                    for res in response:
                        st.write(f"- Name: {res.name}")
                        st.write(f"  - Content (truncated): {res.content[:500]}...")
                        st.write(f"  - Metadata: {res.meta_data}")
                        st.write("-----")
            except Exception as e:
                st.error(f"Error during test query: {e}")