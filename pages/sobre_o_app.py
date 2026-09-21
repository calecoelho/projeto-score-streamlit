import math

import streamlit as st

from componentes_ui import exibir_assinatura

from config import (
    CALIBRACAO_DATA,
    CHANCE_RAZAO_ALTA,
    CHANCE_RAZAO_BAIXA,
    DIMENSOES,
    ESTIMATIVA_K,
    FATIA_QUANTIL_PADRAO,
    FATOR_TIPO_DIA,
    JANELA_MEDIA_MOVEL_DIAS,
    LAST_CLICK_MIN_MATERIAS,
    LAST_CLICK_MUITO_POTENCIAL,
    LIMITE_DEDUPLICACAO,
    MINIMO_MATCHES,
    PESO_SIMILARIDADE_BETA,
    SIMILARIDADE_MINIMA,
    TOP_K,
)


# Os números deste texto vêm do config.py: quando o modelo for
# recalibrado, esta página se atualiza sozinha.

def pt(valor, casas=1):
    """Número com vírgula decimal."""
    return f"{valor:.{casas}f}".replace(".", ",")


def pt_vezes(valor):
    """2.0 -> "2"; 2.5 -> "2,5"."""
    return str(int(valor)) if float(valor).is_integer() else pt(valor)


def pt_milhar(valor):
    """Inteiro com ponto de milhar."""
    return f"{valor:,}".replace(",", ".")


pct_melhores = int(round((1 - FATIA_QUANTIL_PADRAO) * 100))

multiplicador_similaridade = math.exp(PESO_SIMILARIDADE_BETA)

fator_du = FATOR_TIPO_DIA["dia_util"]["cliques"]
fator_fds = FATOR_TIPO_DIA["fim_de_semana"]["cliques"]


st.title("ℹ️ Sobre o app")

st.markdown(
    "Este app é um **modelo de aprendizado de máquina aplicado ao jornalismo**. "
    "As estimativas levam em conta o **histórico de desempenho da Gazeta do Povo**, "
    "com ajuste pela audiência do tipo de dia (dia útil ou fim de semana). "
    "O modelo atual usa **média logarítmica** sobre o peso de participação das matérias "
    "no total de audiência do tipo de dia.\n\n"
    "Os cálculos estatísticos seguem práticas científicas de validação: os métodos foram "
    "escolhidos por comparação em dados reais, com separação entre dados de ajuste e de "
    "conferência, intervalos de confiança e métricas de erro e de capacidade de ordenar as pautas."
)

# ------------------------------------------------------------
# LINHAS GERAIS DO CÁLCULO
# ------------------------------------------------------------

st.subheader("Linhas gerais do cálculo")

st.markdown(
    f"**1. Busca**. O sistema procura no histórico até {ESTIMATIVA_K} matérias parecidas, com "
    f"similaridade mínima de {SIMILARIDADE_MINIMA:.0%}.\n\n"
    "**2. Peso pela similaridade.** Quanto mais parecida, mais a matéria pesa.\n\n"
    "**3. Média logarítmica ponderada.** As participações das matérias parecidas são combinadas "
    "por média logarítmica (geométrica) ponderada. Assim, uma matéria com desempenho excepcional "
    "não domina o resultado, como acontece na média comum.\n\n"
    f"**4. Conversão em cliques e horas.** A participação estimada é multiplicada pela audiência "
    f"média dos últimos {JANELA_MEDIA_MOVEL_DIAS} dias do mesmo tipo de dia (útil ou fim de semana) "
    "e por um fator de correção por tipo de dia, calibrado no histórico.\n\n"
    f"**5. Chance de sucesso.** Uma curva logística, calibrada no histórico, "
    f"converte a participação estimada na chance de a pauta ficar entre as {pct_melhores}% melhores "
    "matérias do mesmo tipo de dia, que é o que chamamos de sucesso. O dia útil é comparado com o dia útil, "
    f"e o fim de semana com o fim de semana. Uma matéria normal tem {1 - FATIA_QUANTIL_PADRAO:.0%} de chance. "
    "O cartão compara a pauta com uma matéria normal: fica 🟢 verde quando ela tem "
    f"pelo menos {pt_vezes(CHANCE_RAZAO_ALTA)} vezes mais chances de sucesso, 🔴 vermelho quando tem menos chances "
    "de sucesso que uma matéria normal e 🟡 amarelo no meio.\n\n"
    f"**6. Last click (potencial de assinaturas).** Olhamos as {TOP_K} matérias mais parecidas. "
    f"Se pelo menos {LAST_CLICK_MIN_MATERIAS} delas tiveram last click, a pauta tem potencial. "
    f"Com {LAST_CLICK_MUITO_POTENCIAL} ou mais last clicks no total, tem muito potencial de assinaturas.\n\n"
)


# ------------------------------------------------------------
# LIMITAÇÕES
# ------------------------------------------------------------

st.subheader("O que o app não faz")

st.markdown(
    "- **A estimativa é uma pista, e não uma previsão exata.**\n"
    f"- **Pautas sem matérias parecidas** (menos de {MINIMO_MATCHES} acima da similaridade mínima) "
    "não recebem estimativa.\n"
    "- **O modelo aprende com o passado.** Mudanças no site ou no comportamento dos leitores "
    "são recalibradas com frequência."
)

# ------------------------------------------------------------
# ATUALIZAÇÃO
# ------------------------------------------------------------

st.subheader("Atualização")

st.markdown(
    f"As curvas de chance e os fatores de correção foram calibrados em **{CALIBRACAO_DATA}**. "
)


# ------------------------------------------------------------
# DESENVOLVIMENTO
# ------------------------------------------------------------

st.divider()

st.markdown(
    "**Desenvolvimento de Carlos Coelho, jornalista e cientista de dados.**"
)

exibir_assinatura()
