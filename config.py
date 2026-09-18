DIMENSOES = 1536
POOL_SIZE = 50
TOP_K = 5
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
# PESO DAS MATÉRIAS DO HISTÓRICO NA ESTIMATIVA
# ------------------------------------------------------------
# Cada matéria do histórico entra na média (dos indicadores
# relativos de cliques e de TLA) com um peso:
#
#     peso final = peso de recência x peso de similaridade
#
# RECÊNCIA: pares (idade em dias, peso). Até a primeira idade o peso
# é o da primeira linha (o maior). Entre uma idade e a seguinte o
# peso cai em linha reta. Depois da última idade, fica no peso da
# última linha.
#
#   até 30 dias  -> 1,00 (peso máximo)
#   6 meses      -> 0,65
#   1 ano        -> 0,35
#   2 anos ou +  -> 0,10 (cai bem)
PESO_RECENCIA_PONTOS = (
    (30, 1.00),
    (180, 0.65),
    (365, 0.35),
    (730, 0.10),
)

# SIMILARIDADE: faixas (similaridade mínima, peso), da maior para a
# menor. A similaridade aqui é a fração (0,70 = 70%).
#
#   70% ou mais       -> 1,00 (maior peso)
#   de 65% a 69,9%    -> 0,60
#   de 60% a 64,9%    -> 0,35
#   abaixo de 60%     -> 0,15 (todas iguais)
PESO_SIMILARIDADE_FAIXAS = (
    (0.70, 1.00),
    (0.65, 0.60),
    (0.60, 0.35),
)

PESO_SIMILARIDADE_BASE = 0.15
