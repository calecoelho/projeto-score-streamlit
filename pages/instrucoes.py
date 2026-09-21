import streamlit as st

from componentes_ui import exibir_assinatura
from config import (
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

st.subheader("Como ler os resultados")

st.markdown(
    "**Dia útil ou fim de semana.** Cada página tem duas abas. A aba do dia de hoje "
    "abre primeiro. A outra é uma simulação: mostra as mesmas pautas como se fossem "
    "publicadas em outro tipo de dia (por exemplo, numa sexta-feira você pode ver como "
    "elas se sairiam num fim de semana).\n\n"
    f"**Como a estimativa é feita.** O sistema procura as {ESTIMATIVA_K} matérias mais parecidas "
    "do histórico da Gazeta do Povo. As mais parecidas pesam mais. O que essas matérias renderam, "
    "medido como fatia do total de cliques do dia (e do tempo de leitura), é convertido em cliques e "
    "horas usando a audiência esperada do tipo de dia. Como o dia útil e o fim de semana têm públicos "
    "diferentes, a estimativa é corrigida por tipo de dia.\n\n"
    "**Chance de ficar entre as melhores.** A estimativa é uma pista, não uma garantia. Por isso, em vez de "
    "dizer só \"passa\" ou \"não passa\", cada cartão mostra a chance de a pauta ficar entre as "
    f"{int(round((1 - FATIA_QUANTIL_PADRAO) * 100))}% melhores do mesmo tipo de dia. Isso quer dizer que o dia útil é comparado com o dia útil, "
    "e o fim de semana com o fim de semana, e nenhum dos dois é favorecido. "
    "🟢 Verde = chance alta; 🟡 amarelo = média; 🔴 vermelho = baixa. "
    "Uma pauta qualquer tem a chance de referência mostrada no cartão; mesmo uma chance alta costuma ser "
    "bem menor que 100%. As duas abas mostram praticamente a mesma chance. O que muda entre elas é a "
    "estimativa de cliques e o número de cliques que separa as melhores.\n\n"
    f"**Last click.** Olhamos as {TOP_K} matérias mais parecidas do histórico. "
    f"Se pelo menos {LAST_CLICK_MIN_MATERIAS} delas tiveram last click, a pauta tem potencial de last click "
    f"(cartão verde). O número mostrado é o total de last clicks dessas matérias. "
    f"Com {LAST_CLICK_MUITO_POTENCIAL} ou mais no total, a pauta ganha o destaque "
    f"**muito potencial de assinaturas**."
)

exibir_assinatura()
