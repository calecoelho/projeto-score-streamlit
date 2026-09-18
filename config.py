DIMENSOES = 1536
POOL_SIZE = 50
TOP_K = 5
SIMILARIDADE_MINIMA = 0.55
MINIMO_MATCHES = 2
JANELA_MEDIA_MOVEL_DIAS = 28
MEIA_VIDA_RECENCIA_DIAS = 365
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
