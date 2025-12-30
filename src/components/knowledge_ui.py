import streamlit as st
import pathlib
import src.core.knowledge as kb_logic
import src.core.db as db_logic
from agno.filters import AND, EQ, IN, NOT
from uuid import uuid4
import json
import pandas as pd
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
        kb_logic.setup_knowledge_base.clear()
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
            url_contents = []
            if urls_input:
                urls = [url.strip() for url in urls_input.split('\n') if url.strip()]
                if urls:
                    with st.spinner("Processing URLs..."):
                        try:
                            for url in urls:
                                metaid = str(uuid4())
                                url_contents.append({
                                    "url": url,
                                    "name": url,
                                    "metadata": {"metaid": metaid},
                                })
                            knowledge.add_contents(url_contents)
                            st.success(f"Added {len(urls)} URLs successfully!")
                        except Exception as e:
                            st.error(f"Error adding URLs: {e}")
                    get_cached_contents.clear()
                    kb_logic.setup_knowledge_base.clear()
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
                    kb_logic.setup_knowledge_base.clear()
                    st.rerun()

    st.divider()
    st.subheader("🗄️ Stored Knowledge")

    # --- Fetch Content List ---      
    contents, _ = get_cached_contents(knowledge, st.session_state['kb_confirmed_config'])

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

    # Mapping
    content_map = {c.id: c for c in contents}

    # select/unselect all functionality
    if "kb_table_version" not in st.session_state:
        st.session_state.kb_table_version = 0
    if "mark_all_state" not in st.session_state:
        st.session_state.mark_all_state = None  # None = use DB, True = all yes, False = all no
    if "delete_all_state" not in st.session_state:
        st.session_state.delete_all_state = None

    def set_table_state(mark=None, delete=None):
        """Updates the default state for columns and forces table refresh"""
        if mark is not None:
            st.session_state.mark_all_state = mark
        if delete is not None:
            st.session_state.delete_all_state = delete
        st.session_state.kb_table_version += 1
    # We use small columns to place these buttons neatly above the table
    c_all_1, c_all_2, c_all_3, c_all_4, c_key, c_rela, c_value, c_search = st.columns([0.4, 1.1, 0.4, 1.1, 2, 1, 2.5, 0.5])
    
    with c_all_1:
        st.button("☑️", on_click=set_table_state, kwargs={"mark": True}, help="Select all for RAG", width='content')
    with c_all_2:
        st.button("⬜", on_click=set_table_state, kwargs={"mark": False}, help="Clear RAG selections", width='content')
    with c_all_3:
        st.button("☑️", on_click=set_table_state, kwargs={"delete": True}, help="Select all for Deletion", width='content')
    with c_all_4:
        st.button("⬜", on_click=set_table_state, kwargs={"delete": False}, help="Clear Delete selections", width='content')

    # Build the DataFrame rows
    table_data = []
    for c in contents:
        # Determine if marked
        c_metaid = c.metadata.get("metaid")
        
        # Logic: Priority to Button State > DB State
        if st.session_state.mark_all_state is not None:
            is_marked = st.session_state.mark_all_state
        else:
            is_marked = (c_metaid in marked_metaids) if c_metaid else False

        if st.session_state.delete_all_state is not None:
            is_deleted = st.session_state.delete_all_state
        else:
            is_deleted = False
        
        table_data.append({
            "Mark": is_marked,
            "Delete": is_deleted,  # Default to unchecked
            "Name": c.name,
            "Updated At": str(time_convert(str(c.updated_at)))[:-9] + " GMT",
            "Status": c.status,
            "Edit": False,    # Default to unchecked
            "ID": c.id,          # Hidden ID column
            "MetaID": c_metaid,  # Hidden MetaID column
        })

    df = pd.DataFrame(table_data)

    # --- 2. Render Table ---
    editor_key = f"kb_table_{current_session_id}_{st.session_state.get('file_uploader_key', 0)}"
    
    edited_df = st.data_editor(
        df,
        key=editor_key,
        hide_index=True,
        width='stretch',
        column_config={
            "Mark": st.column_config.CheckboxColumn("Mark (RAG)", default=False),
            "Delete": st.column_config.CheckboxColumn("Delete", default=False),
            "Name": st.column_config.TextColumn("Name", disabled=True),
            "Updated At": st.column_config.TextColumn("Updated At", disabled=True),
            "Status": st.column_config.TextColumn("Status", disabled=True),
            "Edit": st.column_config.CheckboxColumn("Edit", default=False),
            "ID": None,     # Hidden
            "MetaID": None, # Hidden
        }
    )

    # --- 3. Action Buttons ---
    st.write("")
    c_mark, c_del, c_edit = st.columns([1, 1, 1])

    # [ACTION 1] Mark Selected
    with c_mark:
        if st.button("📌 Mark Selected for RAG", use_container_width=True):
            if not current_session_id:
                st.error("No active session.")
            else:
                selected_metaids = edited_df[edited_df["Mark"] == True]["MetaID"].tolist()
                selected_metaids = [m for m in selected_metaids if m]
                
                db_logic.save_session_documents(history_db, current_session_id, selected_metaids)
                st.success(f"Marked {len(selected_metaids)} documents!")
                st.rerun()

    # [ACTION 2] Delete Selected
    with c_del:
        if st.button("🗑️ Delete Selected", use_container_width=True):
            to_delete_rows = edited_df[edited_df["Delete"] == True]
            if to_delete_rows.empty:
                st.warning("Select items in the 'Delete' column first.")
            else:
                try:
                    with st.spinner(f"Deleting {len(to_delete_rows)} documents..."):
                        for _, row in to_delete_rows.iterrows():
                            # Use ID from the table
                            knowledge.remove_content_by_id(row["ID"])
                            if row["MetaID"]:
                                db_logic.remove_document_from_usages(history_db, row["MetaID"])
                    st.success("Deleted successfully!")
                except Exception as e:
                    st.error(f"Error: {e}")
                get_cached_contents.clear()
                kb_logic.setup_knowledge_base.clear()
                st.rerun()

    # [ACTION 3] Edit Selected
    with c_edit:
        if st.button("✏️ Edit Selected", use_container_width=True):
            # Check marked OR delete columns for selection
            selected_rows = edited_df[(edited_df["Edit"] == True)]
            
            if len(selected_rows) != 1:
                st.warning("Please select exactly one file (via Mark or Delete checkbox) to edit.")
            else:
                # [FIX] Lookup the original object using the ID
                row_id = selected_rows.iloc[0]["ID"]
                original_content = content_map.get(row_id) # <--- Retrieving from Map
                
                if original_content:
                    edit_content_dialog(
                        content_id=original_content.id,
                        current_name=original_content.name,
                        current_description=original_content.description,
                        current_metadata=original_content.metadata,
                        current_updated_at=str(original_content.updated_at),
                        knowledge=knowledge,
                    )
    



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