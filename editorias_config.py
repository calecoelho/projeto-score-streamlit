"""
Configuração centralizada das editorias do Preditor Editorial.

Antes, cada página em pages/ tinha sua própria cópia do filtro de URL
e dos limites de potencial. Agora essa configuração mora em um único
lugar e é usada pelo job (job_gerar_analises.py), que é quem de fato
calcula as oportunidades a cada 30 minutos.

As páginas do Streamlit não leem este arquivo: elas só usam a chave
(ex.: "politica") para saber qual snapshot buscar no cache.
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
        "limite_cliques": 2000,
        "limite_tla_horas": 50,
        "limite_last_clicks": 5,
    },

    "mundo": {
        "titulo": "Mundo",
        "filtro_url": r"(/mundo/|/internacional/)",
        "limite_cliques": 2000,
        "limite_tla_horas": 50,
        "limite_last_clicks": 5,
    },

    "ciencia_e_saude": {
    "titulo": "Ciência e Saúde",
    "filtro_url": (
        r"(/ciencia/|/ciencias/|/saude/|/bem-viver/|"
        r"/tecmundo/|/forbes-tech/|/forbes-saude/|"
        r"/bem-estar/|/cuidados-pessoais/|/vacina-e-saude/|"
        r"/historia/|/tecnologia/)"
    ),
    "limite_cliques": 1000,
    "limite_tla_horas": 50,
    "limite_last_clicks": 5,
},

    # Trends não tem filtro_url: o feed vem do Google Trends
    # (executar_coleta_trends), não da tabela public.news.
    "trends_social": {
        "titulo": "Trends & Social",
        "limite_cliques": 2000,
        "limite_tla_horas": 50,
        "limite_last_clicks": 5,
    },

}
