DIMENSOES = 1536
POOL_SIZE = 50
TOP_K = 5   # matérias mais parecidas usadas na regra do last click
SIMILARIDADE_MINIMA = 0.55
MINIMO_MATCHES = 2
JANELA_MEDIA_MOVEL_DIAS = 28
MAX_WORKERS = 4
LIMITE_DEDUPLICACAO = 0.92

# ------------------------------------------------------------
# LAST CLICK (potencial de assinaturas)
# ------------------------------------------------------------
# Olhamos as matérias do histórico usadas como referência (até 5):
#
#   - "Potencial de last click": pelo menos LAST_CLICK_MIN_MATERIAS
#     delas tiveram algum last click.
#   - "Muito potencial de assinaturas": além disso, a SOMA dos last
#     clicks dessas matérias chega a LAST_CLICK_MUITO_POTENCIAL.
LAST_CLICK_MIN_MATERIAS = 3
LAST_CLICK_MUITO_POTENCIAL = 10

# ------------------------------------------------------------
# DIA ÚTIL x FIM DE SEMANA
# ------------------------------------------------------------
DIA_UTIL = "dia_util"
FIM_DE_SEMANA = "fim_de_semana"

TIPOS_DIA = (DIA_UTIL, FIM_DE_SEMANA)

ROTULOS_TIPO_DIA = {
    DIA_UTIL: "dia útil",
    FIM_DE_SEMANA: "fim de semana",
}

# ------------------------------------------------------------
# ASSINATURA (aparece no rodapé de todas as páginas)
# ------------------------------------------------------------
ASSINATURA = (
    "Desenvolvido por Carlos Coelho "
    "(ccoelho@gazetadopovo.com.br) - 2026"
)

# ------------------------------------------------------------
# COMO A ESTIMATIVA É CALCULADA (método final do teste retroativo)
# ------------------------------------------------------------
# Valores escolhidos no script backtest_pesos.R (em R), testando o
# histórico da Gazeta: quantas matérias usar, como pesar cada uma e
# como combinar os valores.
#
#   - ESTIMATIVA_K: quantas matérias parecidas entram na estimativa.
#     (O last click continua olhando só as TOP_K = 5 mais parecidas.)
#   - PESO_SIMILARIDADE_BETA: quanto mais parecida, mais pesa. A cada
#     +10 pontos de similaridade, o peso é multiplicado por exp(beta).
#   - PESO_RECENCIA_*: peso pela idade da matéria. O teste mostrou que,
#     nos dados atuais, a idade não melhora a estimativa; por isso não
#     há queda (meia-vida = None). Para voltar a dar menos peso às mais
#     antigas, informe a meia-vida em dias (e o platô, em dias, com peso
#     máximo).
#   - AGREGACAO_ESTIMATIVA: "media_log" = média em log (uma matéria
#     gigante não manda sozinha). "media" = média simples ponderada.
#   - PISO_RELATIVO: menor valor usado no log (evita log de zero).
ESTIMATIVA_K = 20
PESO_SIMILARIDADE_BETA = 1.00
PESO_RECENCIA_PLATO_DIAS = 0
PESO_RECENCIA_MEIA_VIDA_DIAS = None  # sem queda por idade
AGREGACAO_ESTIMATIVA = "media_log"
PISO_RELATIVO = 0.0000164

# ------------------------------------------------------------
# CHANCE DE FICAR ENTRE AS MELHORES PAUTAS DO TIPO DE DIA
# ------------------------------------------------------------
# A estimativa é uma pista, não uma certeza. No teste retroativo (em R,
# script backtest_pesos.R) vimos que:
#
#   1. Passar de uma meta fixa de cliques (ex.: 2.000) não é justo entre
#      dia útil e fim de semana: no fim de semana cada matéria pega uma
#      fatia maior do total do dia, e a mesma estimativa tinha 2,2 vezes
#      mais chance de passar da meta.
#   2. Medindo o sucesso como "ficar entre as X% melhores matérias DO
#      MESMO TIPO DE DIA" (pela fatia dos cliques do dia), a distorção
#      some (razão de chances de 0,98 a 1,00).
#
# Então a chance é sempre relativa ao tipo de dia (útil ou fim de
# semana) e sai da FATIA estimada (participação nos cliques do dia):
#
#     chance = 1 / (1 + exp(-(a + b * log(fatia estimada))))
#
# FATIA_QUANTIL_PADRAO = 0.75 quer dizer "entre as 25% melhores".
# Outras opções calibradas: 0.50 (metade melhor) e 0.90 (10% melhores).
#
# "taxa_base" é a chance de uma matéria normal (= 1 - quantil).
#
# Para o usuário, a chance vira uma comparação simples: "quantas vezes
# mais chances de sucesso do que uma matéria normal" (chance / taxa_base).
#   - CHANCE_RAZAO_ALTA: a partir de quantas vezes mais chances o cartão
#     fica verde ("chance alta de sucesso"). Padrão: 2.
#   - CHANCE_RAZAO_BAIXA: abaixo de quantas vezes o cartão fica vermelho
#     ("chance baixa"). Padrão: 1, isto é, menos chances que uma
#     matéria normal. Entre os dois, o cartão fica amarelo.
#
# limiar_* = fatia do dia (fração) que separa as melhores em cada tipo
# de dia. É usada só para mostrar "melhores = a partir de X cliques".
#
# Refaça o teste em R a cada trimestre ou semestre e atualize os
# números abaixo (o script imprime o bloco pronto).
# Mês da última calibração das curvas e dos fatores abaixo (aparece na
# página "Sobre o app"). Atualize sempre que refizer o teste em R.
CALIBRACAO_DATA = "setembro de 2026"

FATIA_QUANTIL_PADRAO = 0.75
CHANCE_RAZAO_BAIXA = 1.0
CHANCE_RAZAO_ALTA = 2.0

# Correção da estimativa de cliques e de horas por tipo de dia. O
# histórico mistura dia útil e fim de semana, e o teste mostrou que a
# estimativa ficava ~20% alta no dia útil e ~32% baixa no fim de
# semana. Multiplique a estimativa por estes fatores.
FATOR_TIPO_DIA = {
    "dia_util": {"cliques": 0.8346, "tla": 0.8171},
    "fim_de_semana": {"cliques": 1.4652, "tla": 1.4817},
}

CHANCE_FATIA = {
    0.50: {
        "cliques": {"a": 7.18851, "b": 1.25983, "taxa_base": 0.5002, "limiar_dia_util": 0.002324, "limiar_fim_de_semana": 0.004082},
        "tla": {"a": 6.55122, "b": 1.14433, "taxa_base": 0.5002, "limiar_dia_util": 0.002162, "limiar_fim_de_semana": 0.004236},
    },
    0.75: {
        "cliques": {"a": 6.36473, "b": 1.32793, "taxa_base": 0.2503, "limiar_dia_util": 0.005907, "limiar_fim_de_semana": 0.010670},
        "tla": {"a": 5.62747, "b": 1.19634, "taxa_base": 0.2503, "limiar_dia_util": 0.006253, "limiar_fim_de_semana": 0.012702},
    },
    0.90: {
        "cliques": {"a": 4.94012, "b": 1.28310, "taxa_base": 0.1004, "limiar_dia_util": 0.012570, "limiar_fim_de_semana": 0.022964},
        "tla": {"a": 4.34865, "b": 1.18003, "taxa_base": 0.1004, "limiar_dia_util": 0.015464, "limiar_fim_de_semana": 0.030163},
    },
}
