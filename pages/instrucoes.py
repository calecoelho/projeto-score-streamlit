import streamlit as st

from componentes_ui import exibir_assinatura
from config import LAST_CLICK_MIN_MATERIAS, LAST_CLICK_MUITO_POTENCIAL

st.title("🧠 IA Editorial")
st.write("Escolha um assunto no menu ao lado para começar.")

st.info(
    "Use o menu lateral para acessar as ferramentas de análise e monitoramento.\n\n"
    "**O que cada menu faz:**\n"
    "- **CALCULE SEU TÍTULO:** Digite o título ou assunto para avaliar a força estimada.\n"
    "- **MUNDO:** Rastreia notícias de outros sites e indica o que pode funcionar em Mundo.\n"
    "- **POLÍTICA:** Avalia a força da cobertura de política, economia e justiça.\n"
    "- **CIÊNCIA E SAÚDE:** Rastreia notícias de outros sites para Ciência e Saúde.\n"
    "- **TRENDS & SOCIAL:** Rastreia Google Trends e redes sociais para pautas em alta."
)

st.subheader("Como ler os resultados")

st.markdown(
    "**Dia útil ou fim de semana.** Cada página tem duas abas. A aba do dia de hoje "
    "abre primeiro. A outra é uma simulação: mostra as mesmas pautas como se fossem "
    "publicadas em outro tipo de dia (por exemplo, numa sexta-feira você pode ver como "
    "elas se sairiam num fim de semana).\n\n"
    "**Cores dos critérios.** Cada pauta mostra três cartões: cliques, TLA e last click. "
    "🟢 Verde quer dizer que a pauta atingiu aquele critério; 🔴 vermelho quer dizer que não atingiu. "
    "Se passar nos três, os três ficam verdes.\n\n"
    f"**Last click.** Olhamos as matérias do histórico usadas como referência (até 5). "
    f"Se pelo menos {LAST_CLICK_MIN_MATERIAS} delas tiveram last click, a pauta tem potencial de last click. "
    f"O número mostrado é o total de last clicks dessas matérias. "
    f"Com {LAST_CLICK_MUITO_POTENCIAL} ou mais no total, a pauta ganha o destaque "
    f"**muito potencial de assinaturas**."
)

exibir_assinatura()
