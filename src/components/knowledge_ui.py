import streamlit as st
import pathlib
import src.core.knowledge as kb_logic

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
                        
                        contents_to_add.append({
                            "path": str(temp_path),
                            "name": file.name
                        })
                        temp_paths.append(temp_path)

                    try:
                        if contents_to_add:
                            knowledge.add_contents(contents_to_add)
                            st.success(f"✅ Added {len(contents_to_add)} file(s)")
                        
                        for path in temp_paths:
                            if path.exists(): path.unlink()
                                
                    except Exception as e:
                        st.error(f"❌ Error adding files: {e}")
                    
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
        # Custom CSS for compact delete buttons
        st.markdown("""
            <style>
                div[class*="st-key-del_btn_wrap_"] button {
                    padding: 0px 5px !important;
                    min-height: 0px !important;
                    height: auto !important;
                    line-height: 1 !important;
                    margin-top: 5px !important;
                    border: none !important;
                }
            </style>
            """, unsafe_allow_html=True)
            
        for i, content in enumerate(contents):
            col_name, col_check = st.columns([4, 1])
            with col_name:
                st.markdown(f"- **{content.name}** ({content.media_type})")
            with col_check:
                if st.button("❌", key=f"del_{i}"):
                    try:
                        with st.spinner(f"Deleting {content.name}..."):
                            knowledge.remove_vector_by_id(content.id)
                            knowledge.remove_content_by_id(content.id)
                            st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")

    # --- Clear Database ---
    if st.button("⚠️ Clear Entire Database"):
        try:
            with st.spinner("Clearing database..."):
                contents, _ = knowledge.contents_db.get_knowledge_contents()
                for content in contents:
                    knowledge.remove_vector_by_id(content.id)
                    knowledge.remove_content_by_id(content.id)
                st.success("Knowledge base cleared!")
                st.rerun()
        except Exception as e:
            st.error(f"Error clearing database: {e}")