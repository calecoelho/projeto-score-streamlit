"""
Configuração centralizada das editorias do Preditor Editorial.

Antes, cada página em pages/ tinha sua própria cópia do filtro de URL.
Agora essa configuração mora em um único lugar e é usada pelo job
(job_gerar_analises.py), que é quem de fato calcula as oportunidades a
cada 30 minutos.

Não há mais meta fixa de cliques ou de horas por editoria: o sucesso é
"ficar entre as melhores pautas do mesmo tipo de dia" (ver config.py,
CHANCE_FATIA).

Sobre o last click: a regra não é mais um limite por editoria. Ela é
igual para todas e fica em config.py (LAST_CLICK_MIN_MATERIAS e
LAST_CLICK_MUITO_POTENCIAL).
"""

EDITORIAS = {

    "politica": {
        "titulo": "Política",
        "filtro_url": (
            r"(/politica/|/justica/|/eleicoes/|/economia/|"
            r"/agro/|/judiciario/|/executivo/|/forbes-money/|"
            r"/mercados/|/business/|/stf/|/tributos/|/negocios/|"
            r"/poder-justica/|/poder-governo/|/poder-eleicoes-2026/)"
        ),
    },

    "mundo": {
        "titulo": "Mundo",
        "filtro_url": r"(/mundo/|/internacional/)",
    },

    "ciencia_e_saude": {
        "titulo": "Ciência e Saúde",
        "filtro_url": (
            r"(/ciencia/|/ciencias/|/saude/|/bem-viver/|"
            r"/tecmundo/|/forbes-tech/|/forbes-saude/|"
            r"/bem-estar/|/cuidados-pessoais/|/vacina-e-saude/|"
            r"/historia/|/tecnologia/)"
        ),
    },

    # Trends não tem filtro_url: o feed vem do Google Trends
    # (executar_coleta_trends), não da tabela public.news.
    "trends_social": {
        "titulo": "Trends & Social",
    },

}
