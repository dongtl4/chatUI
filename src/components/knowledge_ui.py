import streamlit as st
import pathlib
import src.core.knowledge as kb_logic
from uuid import uuid4

def render():
    st.header("📚 Knowledge File Management")

    # Verify connection first
    if st.session_state.get('kb_active_type') != "PostgreSQL + PGVector" or not st.session_state.get('kb_confirmed_config'):
        st.error("Please configure the PostgreSQL connection in 'Connect Database' first.")
        return

    # Initialize KB Connection just for this view
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
    
    # --- List & Delete ---
    try:
        contents, _ = knowledge.contents_db.get_knowledge_contents()
    except Exception as e:
        st.error(f"Error fetching knowledge contents: {e}")
        contents = []

    if contents:
        # Column headers
        h_col1, h_col2 = st.columns([0.5, 6])
        with h_col1:
            st.markdown("**Sel**")
        with h_col2:
            st.markdown("**Document Name**")

        
        st.markdown("""
            <style>
                div[class*="st-key-knowledge_management_checkboxes_container_"] div[data-testid="stCheckbox"] {
                    margin-top: 0px !important;
                }
            </style>
            """, unsafe_allow_html=True)
        # Display list with checkboxes [Check | Name]
        for content in contents:
            col_check, col_name = st.columns([0.5, 6])
            with col_check:
                with st.container(key=f"knowledge_management_checkboxes_container_{content.id}"):
                    st.checkbox("select box", key=f"sel_{content.id}", label_visibility="collapsed")
            with col_name:
                st.write(content.name)
        
        st.write("") # Add a little spacing
        
        # --- Delete Selected Button ---
        if st.button("🗑️ Delete Selected", type="primary"):
            # Identify which items were selected
            selected_items = [c for c in contents if st.session_state.get(f"sel_{c.id}")]
            
            if not selected_items:
                st.warning("Please select at least one document to delete.")
            else:
                try:
                    with st.spinner(f"Deleting {len(selected_items)} documents..."):
                        for item in selected_items:
                            knowledge.remove_content_by_id(item.id)
                    st.success("Selected documents deleted successfully!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error deleting documents: {e}")

    # --- Clear Entire Database ---
    # Kept this utility as a fallback for clearing everything
    if st.button("⚠️ Clear Entire Database"):
        try:
            with st.spinner("Clearing database..."):
                # Re-fetch contents to ensure we have the latest list
                contents_to_clear, _ = knowledge.contents_db.get_knowledge_contents()
                for content in contents_to_clear:
                    knowledge.remove_content_by_id(content.id)
                st.success("Knowledge base cleared!")
                st.rerun()
        except Exception as e:
            st.error(f"Error clearing database: {e}")