from pagina_editorial import renderizar_pagina_editorial


# Os limites de potencial ficam em editorias_config.py.
# O desenho da página fica em pagina_editorial.py.
#
# Aqui a data de publicação da matéria de referência NÃO é exibida
# (eh_trends=True): ela vem do Google Trends e estava incorreta.

renderizar_pagina_editorial(
    editoria="trends_social",
    page_title="IA Editorial — Google Trends",
    page_icon="🔥",
    caption_topo="IA EDITORIAL",
    titulo="🔥 Google Trends",
    descricao="""
    Veja o que está em alta no Google Trends que possui potencial de gerar
    cliques, TLA ou assinaturas. A estimativa de performance é calculada
    comparando os títulos com matérias semelhantes do histórico da Gazeta do Povo.
    """,
    rotulo_analisadas="Tendências analisadas",
    msg_sem_analise="Ainda não há nenhuma análise gerada para Trends & Social.",
    msg_feed_vazio=(
        "Nenhuma tendência do Google Trends foi aprovada pelos "
        "filtros na última atualização."
    ),
    titulo_oportunidades="🎯 Oportunidades editoriais de tendências",
    msg_sem_oportunidade=(
        "Nenhuma tendência aprovada atingiu os critérios "
        "mínimos de potencial neste momento."
    ),
    texto_botao_link="Abrir referência / Google ↗",
    titulo_expander_historico="📚 Matérias históricas semelhantes na Gazeta do Povo",
    titulo_expander_sem_potencial="🔎 Tendências sem potencial estimado",
    msg_todas_com_potencial=(
        "Todas as tendências analisadas atingiram pelo menos um critério."
    ),
    legenda_sem_potencial=(
        "Estas tendências foram vetorizadas e analisadas, mas não "
        "atingiram nenhum dos critérios mínimos configurados."
    ),
    eh_trends=True,
)
