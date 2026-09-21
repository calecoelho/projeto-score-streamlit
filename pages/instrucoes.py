import streamlit as st

from componentes_ui import exibir_assinatura
from config import (
    CHANCE_RAZAO_ALTA,
    ESTIMATIVA_K,
    FATIA_QUANTIL_PADRAO,
    LAST_CLICK_MIN_MATERIAS,
    LAST_CLICK_MUITO_POTENCIAL,
    TOP_K,
)

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

vezes_alta = str(int(CHANCE_RAZAO_ALTA)) if float(CHANCE_RAZAO_ALTA).is_integer() else str(CHANCE_RAZAO_ALTA).replace(".", ",")

st.subheader("Como ler os resultados")

st.markdown(
    "**Dia útil ou fim de semana.** Cada página tem duas abas. A aba do dia de hoje "
    "abre primeiro. A outra é uma simulação: mostra as mesmas pautas como se fossem "
    "publicadas em outro tipo de dia (por exemplo, numa sexta-feira você pode ver como "
    "elas se sairiam num fim de semana).\n\n"
    f"**Como a estimativa é feita.** O sistema procura as {ESTIMATIVA_K} matérias mais parecidas "
    "do histórico da Gazeta do Povo. As mais parecidas pesam mais. \n\n "
    "**Chance de sucesso.** A estimativa é uma pista, não uma garantia. "
    f"Aqui, **sucesso** quer dizer ficar entre as {int(round((1 - FATIA_QUANTIL_PADRAO) * 100))}% melhores matérias "
    "do mesmo tipo de dia: o dia útil é comparado com o dia útil, e o fim de semana com o fim de semana. "
    "Cada cartão compara a pauta com uma matéria normal: "
    f"🟢 verde = pelo menos {vezes_alta} vezes mais chances de sucesso; "
    f"🟡 amarelo = mais chances que uma matéria normal, mas menos de {vezes_alta} vezes mais; "
    "🔴 vermelho = menos chances que uma matéria normal. "
    "As duas abas mostram praticamente o mesmo nível. O que muda entre elas é a "
    "estimativa de cliques e o número de cliques que separa as melhores.\n\n"
    f"**Last click.** Olhamos as {TOP_K} matérias mais parecidas do histórico. "
    f"Se pelo menos {LAST_CLICK_MIN_MATERIAS} delas tiveram last click, a pauta tem potencial de last click "
    f"(cartão verde). O número mostrado é o total de last clicks dessas matérias. "
    f"Com {LAST_CLICK_MUITO_POTENCIAL} ou mais no total, a pauta ganha o destaque "
    f"**muito potencial de assinaturas**."
)

exibir_assinatura()
