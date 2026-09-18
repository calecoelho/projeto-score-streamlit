from pagina_editorial import renderizar_pagina_editorial


# Filtro de URL e limites de potencial ficam em editorias_config.py.
# O desenho da página fica em pagina_editorial.py.

renderizar_pagina_editorial(
    editoria="ciencia_e_saude",
    page_title="IA Editorial — Ciência e Saúde",
    page_icon="🔬",
    caption_topo="IA EDITORIAL",
    titulo="🔬 Ciência e Saúde",
    descricao="""
    Veja o que está rolando nos trends e nos principais jornais
    que pode render cliques, TLA ou assinaturas em
    **CIÊNCIA E SAÚDE**.

    A estimativa de performance é calculada com base em dados
    históricos de matérias semelhantes publicadas na
    Gazeta do Povo.
    """,
    help_analisadas=(
        "Notícias recebidas pelos filtros de Ciência "
        "e Saúde na última atualização."
    ),
    msg_sem_analise="Ainda não há nenhuma análise gerada para Ciência e Saúde.",
    msg_feed_vazio=(
        "Nenhuma notícia de Ciência e Saúde encontrada para os "
        "critérios atuais na última atualização."
    ),
    titulo_expander_sem_potencial=(
        "🔎 Matérias sem potencial "
        "(de acordo com o histórico da Gazeta do Povo)"
    ),
    legenda_sem_potencial=(
        "Estas matérias foram analisadas, mas não atingiram nenhum "
        "dos critérios configurados para Ciência e Saúde."
    ),
)
