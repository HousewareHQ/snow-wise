from langchain_community.callbacks.streamlit import StreamlitCallbackHandler
from langchain_openai import ChatOpenAI
from langchain_community.utilities import SQLDatabase

import snowflake.connector
import streamlit as st

from agent import Agent


@st.cache_resource(ttl='5h')
def get_db(username, password, account, warehouse, role):
    database = "SNOWFLAKE"
    schema = "ACCOUNT_USAGE"
    snowflake_uri = f"snowflake://{username}:{password}@{account}/{database}/{schema}?warehouse={warehouse}&role={role}"
    db = SQLDatabase.from_uri(snowflake_uri, view_support=True)
    # refactor TODO: relying on snowflake-connector cursor for retrieving query_ids
    con = snowflake.connector.connect(
        user=username,
        password=password,
        account=account,
        database=database,
        schema=schema,
        warehouse=warehouse,
        role=role,
    )
    return db, con


st.set_page_config(page_title="Snow-wise", page_icon="❄️")
st.title("❄️ Snow-wise Agent")
st.write('Your go-to-assistant for monitoring and optimizing Snowflake queries!')

with st.sidebar:
    st.title('Your Secrets')
    st.caption('Please use a role with SNOWFLAKE database privileges ([docs](https://docs.snowflake.com/en/sql-reference/account-usage#enabling-the-snowflake-database-usage-for-other-roles))')
    openai_api_key = st.text_input("OpenAI API Key", key="openai_api_key", type="password")
    snowflake_account= st.text_input("Snowflake Account", key="snowflake_account")
    snowflake_username= st.text_input("Snowflake Username", key="snowflake_username")
    snowflake_password= st.text_input("Snowflake Password", key="snowflake_password", type="password")
    snowflake_warehouse= st.text_input("Snowflake Warehouse", key="snowflake_warehouse")
    snowflake_role= st.text_input("Snowflake Role", key="snowflake_role")

    if openai_api_key and snowflake_account and snowflake_username and snowflake_role and snowflake_password and snowflake_warehouse:
        llm = ChatOpenAI(model="gpt-4o", temperature=0, streaming=True, api_key=openai_api_key)
        db, con = get_db(
            username=snowflake_username,
            password=snowflake_password,
            account=snowflake_account,
            warehouse=snowflake_warehouse,
            role=snowflake_role,
        )
        agent_executor = Agent(db=db, llm=llm, con=con).get_executor()


if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("I need help with finding the long running queries on my Snowflake"):
    if not (openai_api_key and snowflake_account and snowflake_username and snowflake_role and snowflake_password and snowflake_warehouse):
        st.info("Please add the secrets to continue!")
        st.stop()

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        st_callback = StreamlitCallbackHandler(st.container())
        response = agent_executor.invoke({
            "input": prompt,
            "chat_history": st.session_state.messages
        }, {"callbacks": [st_callback]})
        st.markdown(response["output"])
    st.session_state.messages.append({"role": "assistant", "content": response["output"]})
