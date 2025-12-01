import streamlit as st
from typing import List, Dict, Any, Optional

def load_history_from_db(agent_obj) -> List[Dict[str, Any]]:
    """
    Loads history from SqliteDb via the Agent object and merges 
    consecutive messages into User/Assistant pairs.
    """
    merged: List[Dict[str, Any]] = []
    try:
        # Agent.get_chat_history is a built-in Agno method
        db_history = agent_obj.get_chat_history(session_id=agent_obj.session_id)
        pending_user: Optional[str] = None

        for chat in db_history:
            if chat.role == "user":
                if pending_user is not None:
                    # Previous user msg had no assistant response
                    merged.append({"user": pending_user, "assistant": ""})
                pending_user = chat.content

            elif chat.role == "assistant":
                if pending_user is None:
                    # Orphan assistant message (append to previous if exists)
                    if merged and merged[-1]["user"] == "" and merged[-1]["assistant"]:
                        merged[-1]["assistant"] += chat.content
                    else:
                        merged.append({"user": "", "assistant": chat.content})
                else:
                    merged.append({"user": pending_user, "assistant": chat.content})
                    pending_user = None

        if pending_user is not None:
            merged.append({"user": pending_user, "assistant": ""})

    except Exception as e:
        print(f"Error loading chat history from database: {e}")

    return merged

def render_history_ui():
    """Renders the merged chat history stored in session_state."""
    # If running, ignore the very last entry as it is currently being built
    history_to_show = st.session_state.history[:-1] if st.session_state.get('running', None) is not None else st.session_state.history

    for entry in history_to_show:
        with st.chat_message("user"):
            st.markdown(entry.get("user", "") or "_(no user message)_")
        with st.chat_message("assistant"):
            st.markdown(entry.get("assistant", "") or "_(no assistant message)_")