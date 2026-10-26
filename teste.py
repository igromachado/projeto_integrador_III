
import streamlit as st
import requests
from streamlit_autorefresh import st_autorefresh
from datetime import datetime

st.set_page_config(page_title="API em tempo real", layout="wide")

st.title("📡 Monitoramento de API")

# Atualiza a interface a cada 5 segundos
st_autorefresh(
    interval=5000,
    key="atualizacao"
)

url = "http://10.107.67.92:8080/maquinas"

try:
    resposta = requests.get(url, timeout=10)
    resposta.raise_for_status()
    usuarios = resposta.json()

    st.success("API conectada!")

    col1, col2 = st.columns(2)

    with col1:
        st.metric("Total de usuários", len(usuarios))

    with col2:
        st.write(
            "Última consulta:",
            datetime.now().strftime("%H:%M:%S")
        )

    st.subheader("Dados recebidos")

    st.dataframe(
        usuarios,
        use_container_width=True
    )

except requests.RequestException as erro:
    st.error(f"Erro ao consultar API: {erro}")
