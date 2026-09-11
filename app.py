import streamlit as st

st.set_page_config(
    page_title="Central de Inteligência Editorial",
    page_icon="🧠",
    layout="wide"
)

st.title("Central de Inteligência Editorial")
st.write("Escolha um assunto no menu ao lado.")

st.info(
    "Use o menu lateral para acessar as ferramentas "
    "de análise e monitoramento. \n"
    "O que cada menu faz: \n"
    "- Mundo Avalaiação: Você digita o título ou assunto para a cobertura de mundo e ele avalia a força\n"
    "- Mundo Oportunidades: Ele rastreia notícias de outros sites e diz o que pode funcionar na cobertura de Mundo da Gazeta\n"
    "- Política Avaliação: Você digita o título ou assunto para a cobertura de política e ele avalia a força\n"
    "- Política Oportunidades: Ele rastreia notícias de outros sites e diz o que pode funcionar na cobertura de Política da Gazeta\n"
)