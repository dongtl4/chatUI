import streamlit as st

def render():

    st.subheader("**Chat**")
    with st.expander("Features"):
        st.markdown("""
            1. *Quick navigation*: Click a link in the **Current Conversation** sidebar to jump directly to the corresponding chat.
            2. *Mark important chats*: Use the checkbox next to each link to mark chats as important and include them in the context (multiple selections allowed).
            3. *Delete unwanted chats*: Select chats and click **Delete Selected Chat** at the top to remove them.
            """)

    st.subheader("**Agent**")
    with st.expander("Features"):
        st.markdown("""
            1. In **Agent Configuration**, you can modify model parameters by editing fields in **Model Parameters**. You can also adjust the system prompt using four fields: *Description*, *Instruction*, *Additional Context*, and *Expected Output*.
            2. **Update Agent Settings** applies your current settings and creates a new agent, but does not save them to the database. The **Save** button only saves the settings without applying them.
            3. You can load saved settings by clicking **Load**, or remove them by clicking **✖️**.
            """)

    st.subheader("**Session**")
    with st.expander("Features"):
        st.markdown("""
            On the **Session Settings** page, configure historical chat context in the left panel, and add/select/remove sessions in the right panel.
            """)

    st.subheader("**Knowledge**")
    with st.expander("Features"):
        st.markdown("""
            1. You can configure your PostgreSQL database for knowledge storage on the **Connect Database** page.
            2. To create new database, suggest adjust the *PostgreSQL Database* field only.
            3. On the **Manage Files** page, you can add, edit metadata, or remove files from the knowledge base (only PDF files are supported for now; more file types will be added soon).
            4. By check boxes in colum *Mark Select* and press *Mark Selected Documents For Custom RAG*, you will doing RAG on selected docs only instead of all files in knowledge
            5. To batch delete files, check boxes in column *Del Select* and press *Delete Selected From KB* or you can remove all by *Clear Entire Database*
            6. You can also test knowledge queries using **Quick Query Test** on the **Manage Files** page.
            """)
        
