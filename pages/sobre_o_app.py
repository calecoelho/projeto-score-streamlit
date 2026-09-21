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
    f"**1. Matérias parecidas.** O título da pauta é transformado em um vetor numérico "
    f"(*embedding* de {pt_milhar(DIMENSOES)} dimensões) que representa o sentido do texto. "
    f"O sistema procura no histórico até {ESTIMATIVA_K} matérias parecidas, com "
    f"similaridade mínima de {SIMILARIDADE_MINIMA:.0%}. Esse é o componente de aprendizado de máquina: "
    "um método de vizinhos mais próximos (*k-NN*) sobre *embeddings*.\n\n"
    f"**2. Peso pela similaridade.** Quanto mais parecida, mais a matéria pesa: a cada +10 pontos "
    f"de similaridade, o peso é multiplicado por {pt(multiplicador_similaridade)}. "
    "A idade da matéria não altera o peso, porque nos testes ela não melhorou as estimativas.\n\n"
    "**3. Participação no total do dia.** Em vez de cliques absolutos, usamos a fatia "
    "(participação) que cada matéria teve no total de cliques e de tempo de leitura do dia "
    "em que foi publicada. Isso separa o desempenho da matéria do tamanho da audiência daquele dia.\n\n"
    "**4. Média logarítmica ponderada.** As participações das matérias parecidas são combinadas "
    "por média logarítmica (geométrica) ponderada. Assim, uma matéria com desempenho excepcional "
    "não domina o resultado, como acontece na média comum.\n\n"
    f"**5. Conversão em cliques e horas.** A participação estimada é multiplicada pela audiência "
    f"média dos últimos {JANELA_MEDIA_MOVEL_DIAS} dias do mesmo tipo de dia (útil ou fim de semana) "
    "e por um fator de correção por tipo de dia, calibrado no histórico. O fator existe porque, "
    "no fim de semana, cada matéria fica com uma fatia maior do total do dia.\n\n"
    f"**6. Chance de sucesso.** Uma curva logística, calibrada no histórico, "
    f"converte a participação estimada na chance de a pauta ficar entre as {pct_melhores}% melhores "
    "matérias do mesmo tipo de dia, que é o que chamamos de sucesso. O dia útil é comparado com o dia útil, "
    f"e o fim de semana com o fim de semana. Uma matéria normal tem {1 - FATIA_QUANTIL_PADRAO:.0%} de chance. "
    "O cartão compara a pauta com uma matéria normal: fica 🟢 verde quando ela tem "
    f"pelo menos {pt_vezes(CHANCE_RAZAO_ALTA)} vezes mais chances de sucesso, 🔴 vermelho quando tem menos chances "
    f"({pt_vezes(CHANCE_RAZAO_BAIXA)} vez ou menos) e 🟡 amarelo no meio.\n\n"
    f"**7. Last click (potencial de assinaturas).** Olhamos as {TOP_K} matérias mais parecidas. "
    f"Se pelo menos {LAST_CLICK_MIN_MATERIAS} delas tiveram last click, a pauta tem potencial. "
    f"Com {LAST_CLICK_MUITO_POTENCIAL} ou mais last clicks no total, tem muito potencial de assinaturas.\n\n"
    f"**8. Pautas repetidas.** Pautas com similaridade de {LIMITE_DEDUPLICACAO:.0%} ou mais entre si "
    "são tratadas como a mesma notícia, e fica só a de maior estimativa."
)

# ------------------------------------------------------------
# VALIDAÇÃO
# ------------------------------------------------------------

st.subheader("Como o modelo foi validado")

st.markdown(
    "- **Teste retroativo:** cada matéria antiga foi tratada como uma pauta nova e estimada usando "
    "apenas matérias ainda mais antigas, para que o teste nunca \"olhe o futuro\".\n"
    "- **Separação no tempo:** a parte mais antiga dos dados serviu para ajustar o modelo, e a parte "
    "mais recente serviu para conferir se o ajuste funciona em dados que ele não viu.\n"
    "- **Comparação de alternativas:** média simples, mediana, pesos diferentes e números "
    "diferentes de matérias parecidas foram comparados, com intervalos de confiança (*bootstrap*).\n"
    "- **Métricas:** erro típico (quantas vezes a estimativa erra para mais ou para menos), "
    "tendência (se costuma errar para cima ou para baixo), capacidade de separar as melhores pautas "
    "das demais (AUC) e conferência de calibração (a chance prevista precisa bater com a real).\n"
    "- **Tipo de dia:** o teste mostrou que uma régua única distorcia o fim de semana, e por isso "
    "a chance é sempre relativa ao mesmo tipo de dia."
)

# ------------------------------------------------------------
# LIMITAÇÕES
# ------------------------------------------------------------

st.subheader("O que o app não faz")

st.markdown(
    "- **A estimativa é uma pista, e não uma previsão exata.** A capacidade de ordenar as pautas é "
    "melhor que um sorteio, mas modesta. Mesmo uma chance alta costuma ficar bem abaixo de 100%.\n"
    "- **Não considera** posição na home, horário de publicação, distribuição em redes sociais "
    "nem eventos do dia. Só o título da pauta e o histórico entram no cálculo.\n"
    f"- **Pautas sem matérias parecidas** (menos de {MINIMO_MATCHES} acima da similaridade mínima) "
    "não recebem estimativa.\n"
    "- **O histórico é relativamente curto** e tem menos dados de fim de semana, então as estimativas "
    "desse tipo de dia são menos firmes. Ainda não há como captar sazonalidades longas.\n"
    "- **O modelo aprende com o passado.** Mudanças no site ou no comportamento dos leitores "
    "exigem recalibração."
)

# ------------------------------------------------------------
# ATUALIZAÇÃO
# ------------------------------------------------------------

st.subheader("Atualização")

st.markdown(
    f"As curvas de chance e os fatores de correção foram calibrados em **{CALIBRACAO_DATA}**. "
    "A análise das pautas é recalculada automaticamente a cada 30 minutos, mas a calibração "
    "deve ser refeita a cada trimestre ou semestre, para acompanhar as mudanças do público."
)

with st.expander("Parâmetros atuais do modelo"):

    st.markdown(
        "| Parâmetro | Valor |\n"
        "|---|---|\n"
        f"| Matérias parecidas na estimativa | até {ESTIMATIVA_K} |\n"
        f"| Similaridade mínima | {SIMILARIDADE_MINIMA:.0%} |\n"
        f"| Peso extra a cada +10 pontos de similaridade | x {pt(multiplicador_similaridade)} |\n"
        f"| Janela da audiência de referência | {JANELA_MEDIA_MOVEL_DIAS} dias |\n"
        f"| Fator de correção dos cliques (dia útil / fim de semana) | x {pt(fator_du, 2)} / x {pt(fator_fds, 2)} |\n"
        f"| Referência de sucesso | entre as {pct_melhores}% melhores do tipo de dia |\n"
        f"| Matérias do last click | as {TOP_K} mais parecidas |\n"
        f"| Similaridade para agrupar pautas repetidas | {LIMITE_DEDUPLICACAO:.0%} |"
    )

# ------------------------------------------------------------
# DESENVOLVIMENTO
# ------------------------------------------------------------

st.divider()

st.markdown(
    "**Desenvolvimento de Carlos Coelho, jornalista e cientista de dados.**"
)

exibir_assinatura()
