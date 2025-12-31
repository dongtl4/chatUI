import streamlit as st
import streamlit.components.v1 as components
from uuid import uuid4
import json
import src.core.db as db_logic
from agno.agent import Agent

def scroll_to_anchor():
    """
    Injects JS to scroll specifically to the 'current_response_anchor' element.
    This is more reliable than scrolling to the bottom of the page.
    """
    js = """
    <script>
        // Wait slightly for the DOM to update
        setTimeout(function() {
            // Target the specific anchor ID we placed in the app
            var element = window.parent.document.getElementById('current_response_anchor');
            if (element) {
                // Scroll the element into view. 
                // 'block: start' tries to align the top of the element with the top of the viewport
                element.scrollIntoView({behavior: 'smooth', block: 'start'});
            }
        }, 100);
    </script>
    """
    components.html(js, height=0, width=0)

def render_current_chat_container(placeholder):
    placeholder.empty()
    if not st.session_state.get("current_chat"):
        return

    current_idx = len(st.session_state.get("history", [])) - 1
    if current_idx < 0: current_idx = 0

    with placeholder.container():
        st.markdown(f"<div id='msg-{current_idx}'></div>", unsafe_allow_html=True)
        if st.session_state["current_chat"]:
            msg_pair = st.session_state["current_chat"][-1]
            with st.chat_message("user"):
                st.markdown(msg_pair.get("user", ""))
            with st.chat_message("assistant"):
                st.markdown(msg_pair.get("assistant", "") or "_(thinking...)_")

def render_history_ui():
    """Renders the historical messages."""
    history_to_show = st.session_state.history[:-1] if st.session_state.get('running', None) is not None else st.session_state.history
    
    if not history_to_show:
        st.info("Start a conversation!")

    for idx, entry in enumerate(history_to_show):
        st.markdown(f"<div id='msg-{idx}'></div>", unsafe_allow_html=True)
        if entry.get("marked"):
            st.caption(f"📌 Marked Context (ID: {entry.get('id')})")
        with st.chat_message("user"):
            st.markdown(entry.get("user", "") or "_(no user message)_")
        with st.chat_message("assistant"):
            event_string = entry.get("assistant")
            events = []
            for event in event_string.splitlines():
                if event.strip():
                    events.append(json.loads(event))
            history_lines = ""
            for event in events:
                if event.get("event", "") == "RunContent":
                    history_lines += event.get("content", "")
            st.markdown(history_lines or "_(no assistant message)_")

def render(agent: Agent, history_db):
    """Main rendering entry point for chat."""
    st.header("💬 Chat Interface")
    
    # 1. Show History
    render_history_ui()
    st.divider()

    # 2. Prepare for Streaming
    st.markdown("<div id='current_response_anchor'></div>", unsafe_allow_html=True)
    current_chat_placeholder = st.container().empty()

    # 3. Input
    query = st.chat_input("Ask a question...")

    if query:
        st.session_state["current_chat"] = [{"user": query, "assistant": ""}]
        st.session_state["history"].append({
            "user": query, "assistant": "", "marked": False 
        })
        st.session_state.running = str(uuid4())
        st.rerun()

    # 4. Processing Loop
    if st.session_state.get('running', False):
        token = st.session_state['running']
        if token != 'in_progress':
            st.session_state['running'] = 'in_progress'
            scroll_to_anchor()
            render_current_chat_container(current_chat_placeholder)

            # Build Prompt
            original_query = st.session_state["current_chat"][-1]["user"]
            final_prompt = ""
            
            # Use Config from Session State (set by other tabs)
            use_marked = st.session_state.get("use_marked_context", False)
            use_history = st.session_state.get("use_history", False)
            
            if use_marked:
                marked_context_str = ""
                existing_history = st.session_state["history"][:-1]
                for msg in existing_history:
                    if msg.get("marked", False):
                        marked_context_str += f"User: {msg['user']}\nAssistant: {msg['assistant']}\n---\n"
                if marked_context_str:
                    final_prompt += f"!!! IMPORTANT CONTEXT !!!\n{marked_context_str}\n!!! END CONTEXT !!!\n\n"

            if use_history:
                final_prompt += f"User's current question: {original_query}\n\n"
                history_context_str = ""
                hist_source = st.session_state["history"][:-1]
                if not st.session_state.get("use_full_history", True):
                     hist_source = hist_source[-st.session_state.get("history_length", 5):]

                for msg in hist_source:
                    history_context_str += f"User: {msg['user']}\nAssistant: {msg['assistant']}\n\n"
                final_prompt += f"---Conversation history:\n{history_context_str}\n\n"
            else:
                final_prompt += original_query

            # Stream
            full_response = ""
            content_response = ""
            try:
                if not agent:
                    full_response = "⚠️ Agent not initialized. Please configure the model in the 'Agent' > 'Agent Configuration' section."
                    st.session_state["current_chat"][-1]["assistant"] = full_response
                    render_current_chat_container(current_chat_placeholder)
                else:
                    stream = agent.run(final_prompt, stream=True, knowledge_filters=st.session_state.get("knowledge_filters", None))
                    for chunk in stream:
                        if hasattr(chunk, 'event') and chunk.event == "RunContent":
                            str_chunk = json.dumps(chunk.to_dict())
                            full_response += str_chunk + "\n"
                            if hasattr(chunk, 'content') and chunk.content:
                                content_response += chunk.content
                                st.session_state["current_chat"][-1]["assistant"] = content_response
                                render_current_chat_container(current_chat_placeholder)
            except Exception as e:
                 full_response += f"\n\nError: {str(e)}"
                 st.session_state["current_chat"][-1]["assistant"] = content_response
                 render_current_chat_container(current_chat_placeholder)
            finally:
                st.session_state.running = None
                db_logic.save_exchange_to_db(
                    history_db, st.session_state["session_id"], original_query, full_response
                )
                st.session_state.history = db_logic.load_history_from_db(
                    history_db, st.session_state.get("session_id")
                )
                st.rerun()