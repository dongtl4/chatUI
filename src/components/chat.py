import streamlit as st
import streamlit.components.v1 as components
from uuid import uuid4
from typing import Dict, Any, Optional
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

def format_tool_args(args):
    """Helper to try and parse tool arguments as JSON for better display."""
    if isinstance(args, dict):
        return args
    try:
        return json.loads(args)
    except:
        return args
    
def extract_assistant_content(event_string: str) -> str:
    """
    Extracts the clean text content from the final 'RunCompleted' event 
    stored in the history string.
    """
    if not event_string:
        return ""

    # We split by lines and check the last non-empty one is RunCompleted or not.
    lines = [line for line in event_string.splitlines() if line.strip()]
    if not lines:
        return ""
    try:
        last_event = json.loads(lines[-1])
        if last_event.get("event") == "RunCompleted":
            return last_event.get("content", "")
        return ""
    except:
        return ""
    
def extract_run_metrics(event_string: str) -> Dict[str, Any]:
    """
    Extract the metrics for the corresponding run
    """
    if not event_string:
        return {}
    
    # We split by lines and check the last non-empty one is RunCompleted or not.
    lines = [line for line in event_string.splitlines() if line.strip()]
    if not lines:
        return {}

    try:
        last_event = json.loads(lines[-1])
        if last_event.get("event") == "RunCompleted":
            return last_event.get("metrics", {})
        return {}
    except:
        return {}

def render_message_events(event_string: str, show_run_metrics: bool = False):
    """
    Parses a string of JSON events and renders the chat message components
    (Text content and Tool Popovers).
    """
    if not event_string:
        return

    # 1. Parse lines into JSON objects
    events = []
    for line in event_string.splitlines():
        if line.strip():
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    
    # 2. Group events into render blocks
    # Blocks can be: ('text', content_string) or ('tool', tool_data_dict)
    render_blocks = []
    current_text_buffer = []
    
    # Track the currently running tool to merge Start/Complete events
    active_tool_block = None

    for event in events:
        event_type = event.get("event")

        if event_type == "RunContent":
            content = event.get("content", "")
            if content:
                current_text_buffer.append(content)
        
        elif event_type == "ToolCallStarted":
            # Flush pending text content before showing tool
            if current_text_buffer:
                render_blocks.append({"type": "text", "content": "".join(current_text_buffer)})
                current_text_buffer = []
            
            tool_data = event.get("tool", {})
            active_tool_block = {
                "type": "tool",
                "name": tool_data.get("tool_name", "Unknown Tool"),
                "args": tool_data.get("tool_args", ""),
                "result": None,
                "completed": False
            }
            render_blocks.append(active_tool_block)

        elif event_type == "ToolCallCompleted":
            # Update the active tool with its result
            tool_data = event.get("tool", {})
            result = tool_data.get("result", "")
            
            if active_tool_block and not active_tool_block["completed"]:
                active_tool_block["result"] = result
                active_tool_block["completed"] = True
            else:
                # Fallback for orphaned results (e.g. if streaming started mid-tool)
                if current_text_buffer:
                    render_blocks.append({"type": "text", "content": "".join(current_text_buffer)})
                    current_text_buffer = []
                    
                render_blocks.append({
                    "type": "tool",
                    "name": "Tool Result",
                    "args": None,
                    "result": result,
                    "completed": True
                })
            
            # Reset active tool tracker
            active_tool_block = None

    # Flush any remaining text at the end
    if current_text_buffer:
        render_blocks.append({"type": "text", "content": "".join(current_text_buffer)})

    # 3. Render the blocks using Streamlit components
    for block in render_blocks:
        if block["type"] == "text":
            st.markdown(block["content"])
        elif block["type"] == "tool":
            tool_name = block["name"]
            tool_args = block["args"]
            tool_result = block["result"]
            
            # Create Popover for the tool
            with st.popover(f"🛠️ {tool_name}"):
                # 1. Tool Name
                st.markdown(f"**Tool:** `{tool_name}`")
                
                # 2. Tool Arguments
                if tool_args:
                    st.markdown("**Arguments:**")
                    st.json(format_tool_args(tool_args), expanded=False)
                
                # 3. Tool Result
                st.markdown("**Result:**")
                if tool_result:
                    # Try to format result as JSON if possible, otherwise Markdown
                    formatted_res = format_tool_args(tool_result)
                    if isinstance(formatted_res, (dict, list)):
                        st.json(formatted_res, expanded=True)
                    else:
                        st.markdown(tool_result)
                elif not block["completed"]:
                    st.caption("⏳ Running...")
                else:
                    st.caption("No result returned.")

    # Render Metrics Button (if metrics exist)
    if show_run_metrics:
        metrics = extract_run_metrics(event_string)
        if metrics:
            with st.popover("📊"):
                st.json(metrics)

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
                render_message_events(msg_pair.get("assistant", ""))

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
            render_message_events(entry.get("assistant"), True)

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
            
            # --- CONTEXT BUILDING ---
            use_marked = st.session_state.get("use_marked_context", False)
            use_history = st.session_state.get("use_history", False)
            marked_context_str = ""
            history_context_str = ""

            if use_marked:                
                existing_history = st.session_state["history"][:-1]
                for msg in existing_history:
                    if msg.get("marked", False):
                        content = extract_assistant_content(msg.get("assistant", ""))
                        if content:
                             marked_context_str += f"User: {msg['user']}\nAssistant: {content}\n---\n"

            if use_history:                
                hist_source = st.session_state["history"][:-1]
                if not st.session_state.get("use_full_history", True):
                     hist_source = hist_source[-st.session_state.get("history_length", 5):]

                for msg in hist_source:
                    content = extract_assistant_content(msg.get("assistant", ""))
                    if content:
                        history_context_str += f"User: {msg['user']}\nAssistant: {content}\n\n"

            # --- STREAMING ---
            full_response = ""
            try:
                if not agent:
                    full_response = "⚠️ Agent not initialized. Please configure the model in the 'Agent' > 'Agent Configuration' section."
                    st.session_state["current_chat"][-1]["assistant"] = full_response
                    render_current_chat_container(current_chat_placeholder)
                else:
                    stream = agent.run(
                            original_query,
                            stream=True, 
                            stream_events=True, 
                            dependencies = {'Previous chats which are marked as important':marked_context_str, 'Current chats':history_context_str},
                            add_dependencies_to_context = True,
                            knowledge_filters=st.session_state.get("knowledge_filters", None)
                        )
                    for chunk in stream:
                        if hasattr(chunk, 'references') and chunk.references and chunk.event != 'RunCompleted':
                            chunk.references = ''
                        
                        # Process Event
                        event = chunk.to_dict()
                        str_event = json.dumps(event)
                        
                        # Store RAW JSON string for the renderer (this is the key change)
                        full_response += str_event + "\n"
                        st.session_state["current_chat"][-1]["assistant"] = full_response
                        
                        # Re-render the container using the new logic
                        render_current_chat_container(current_chat_placeholder)

            except Exception as e:
                 # If error, append it as a fake content event or just text
                 error_event = json.dumps({"event": "RunContent", "content": f"\n\nError: {str(e)}"})
                 full_response += error_event + "\n"
                 st.session_state["current_chat"][-1]["assistant"] = full_response
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