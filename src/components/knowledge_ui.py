import streamlit as st
import pathlib
import src.core.knowledge as kb_logic
import src.core.db as db_logic
from agno.filters import AND, EQ, IN, NOT
from uuid import uuid4
import json
from sqlalchemy import text
from agno.knowledge import Knowledge

@st.cache_data 
def get_cached_contents(_knowledge, kb_config): 
    try:
        return _knowledge.contents_db.get_knowledge_contents()
    except Exception as e:
        return [], str(e)

def auto_initialize(history_db):
    """
    Initializes the knowledge_filters session state based on the current session's marked documents in the database.
    """
    # Only initialize if it doesn't exist yet
    if "knowledge_filters" not in st.session_state:
        st.session_state["knowledge_filters"] = None
        
    # Sync with DB
    session_id = st.session_state.get("session_id")
    if session_id and history_db:
        try:
            marked_ids = db_logic.get_session_documents(history_db, session_id)
            if marked_ids:
                st.session_state["knowledge_filters"] = [IN("metaid", marked_ids)]
            else:
                st.session_state["knowledge_filters"] = None
        except Exception:
            # On error (e.g. DB not ready), default to None
            st.session_state["knowledge_filters"] = None
    else:
        st.session_state["knowledge_filters"] = None

def time_convert(timestamp):
    import datetime
    return datetime.datetime.fromtimestamp(int(timestamp), datetime.UTC)

# Function to edit content of Embedded Documents
@st.dialog("Edit Content")
def edit_content_dialog(
    content_id: str,
    current_name: str,
    current_description: str,
    current_metadata: dict,
    current_updated_at: str,
    knowledge: Knowledge
):
    """
    Dialog to edit content name, description, and metadata.
    Enforces read-only meta_id and update_date.
    """
    # 1. Show Update Date (Read-only)
    st.info(f"Last Updated: {time_convert(current_updated_at)} GMT")

    # 2. Editable Fields: Name & Description
    new_name = st.text_input("Name", value=current_name, help="Update the display name of this content.")
    new_description = st.text_area("Description", value=current_description, help="Update the description.")

    # 3. Metadata Handling
    st.write("### Metadata")
    
    # Extract meta_id to keep it safe (read-only)
    metaid = current_metadata.get("metaid")
    if metaid:
        st.info(f"Meta ID: `{metaid}`", icon="🔒")

    # Filter out meta_id for the editable JSON area
    editable_metadata = {k: v for k, v in current_metadata.items() if k != "metaid"}
    
    # Display JSON editor for remaining metadata
    metadata_str = st.text_area(
        "Edit Metadata (JSON)",
        value=json.dumps(editable_metadata, indent=2),
        height=200,
        help='Modify metadata values. Must be follow strict JSON rule, for example: {"type": "pdf", "source" : "ACM paper"}'
    )

    # 4. Save Action
    if st.button(label="Save", type="primary"):
        new_metadata = json.loads(metadata_str)
        new_metadata['metaid'] = metaid
        from agno.knowledge.content import Content
        saved_content = Content(id=content_id, name=new_name, description=new_description, metadata=new_metadata)
        # Update content in contentdb
        knowledge._update_content(saved_content)
        get_cached_contents.clear()
        st.rerun()
    

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
                            get_cached_contents.clear()
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
                    get_cached_contents.clear()
                    st.rerun()

    st.divider()
    st.subheader("🗄️ Stored Knowledge")

    # Column headers
    mark_col, del_col, name_col, uptime_col, stat_col, edit_col = st.columns([1, 1, 4, 2, 1, 1])
    with mark_col:
        st.markdown("**Mark Select**")
    with del_col:
        st.markdown("**Del Select**")
    with name_col:
        st.markdown("**Name**")
    with uptime_col:
        st.markdown("**Update At**")
    with stat_col:
        st.markdown("**Status**")
    with edit_col:
        st.selectbox("Sort by", options= ['name asc', 'name des', 'time asc', 'time des', 'status'], key='contents_sort_key', index=3)

    # Sorting function
    def sort_contents(contents, sort_option):
        if sort_option == "name asc":
            return sorted(contents, key=lambda x: x.name)
        if sort_option == "name des":
            return sorted(contents, key=lambda x: x.name, reverse=True)
        if sort_option == "time asc":
            return sorted(contents, key=lambda x: x.updated_at)
        if sort_option == "time des":
            return sorted(contents, key=lambda x: x.updated_at, reverse=True)
        if sort_option == "status":
            return sorted(contents, key=lambda x: x.status)
        return contents

    
    # --- Fetch Content List ---      
    raw_contents, _ = get_cached_contents(knowledge, st.session_state['kb_confirmed_config'])
    contents = sort_contents(raw_contents, st.session_state.contents_sort_key)

    # --- Fetch Marked Docs for Session ---
    current_session_id = st.session_state.get("session_id")
    marked_metaids = []
    if current_session_id:
        marked_metaids = db_logic.get_session_documents(history_db, current_session_id)

    # --- Update Knowledge Filters based on Marked Docs ---
    if marked_metaids:
        st.session_state["knowledge_filters"] = [IN("metaid", marked_metaids)]
    else:
        st.session_state["knowledge_filters"] = None

    if contents:
        st.markdown("""
            <style>
                div[class*="st-key-knowledge_management_checkboxes_container_"] div[data-testid="stCheckbox"] {
                    margin-top: 0px !important;
                }
            </style>
            """, unsafe_allow_html=True)
        st.markdown("""
            <style>
                div[class*="st-key-knowledge_management_edit_button_"] button {
                    margin-top: -8px !important;
                }
            </style>
            """, unsafe_allow_html=True)
        
        # Display list with checkboxes
        for content in contents:
            col_mark, col_del, col_name, col_uptime, col_stat, col_edit = st.columns([1, 1, 4, 2, 1, 1])

            # Key: sel_{id}_{session}
            chk_key = f"sel_{content.id}_{current_session_id}"
            
            # --- 1. Mark Column ---
            with col_mark:
                content_metaid = content.metadata.get("metaid") if content.metadata else None
                is_checked = (content_metaid in marked_metaids) if content_metaid else False
                
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

            # --- 4. Update Time ---
            with col_uptime:
                st.write(f"{str(time_convert(str(content.updated_at)))[:-9]} GMT")

            # --- 5. Status ---
            with col_stat:
                st.write(content.status)

            # --- 6. Edit Column ---
            with col_edit:
                with st.container(key=f"knowledge_management_edit_button_{content.id}"):
                    if st.button("Edit", key=f"edit_{content.id}"):
                        edit_content_dialog(
                            content_id=content.id,
                            current_name=content.name,
                            current_description=content.description,
                            current_metadata=content.metadata,
                            current_updated_at=str(content.updated_at),
                            knowledge=knowledge,
                        )
        
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
                        get_cached_contents.clear()
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
                get_cached_contents.clear()
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
                # Use the session state knowledge filters if the checkbox is checked
                active_filters = st.session_state["knowledge_filters"] if st.session_state.get("use_knowledge_filter") else None
                
                with st.spinner(f"Running test query for '{test_query}'..."):
                    response = knowledge.search(
                        query=test_query,
                        filters=active_filters
                    )
                    st.markdown(f"**Found {len(response)} responses for query '{test_query}':**")
                    for res in response:
                        st.write(f"- Name: {res.name}")
                        st.write(f"  - Content (truncated): {res.content[:500]}...")
                        st.write(f"  - Metadata: {res.meta_data}")
                        st.write("-----")
            except Exception as e:
                st.error(f"Error during test query: {e}")