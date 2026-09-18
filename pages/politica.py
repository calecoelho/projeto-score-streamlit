from pagina_editorial import renderizar_pagina_editorial


# Filtro de URL e limites de potencial ficam em editorias_config.py.
# O desenho da página fica em pagina_editorial.py.

renderizar_pagina_editorial(
    editoria="politica",
    page_title="Preditor Editorial — Política",
    page_icon="🏛️",
    caption_topo="PREDITOR EDITORIAL",
    titulo="🏛️ Política",
    descricao="""
    Veja o que está rolando nos trends e nos principais jornais
    que pode render cliques, TLA ou assinaturas em **POLÍTICA, ECONOMIA E JUSTIÇA**.
    A estimativa de performance é calculada com base em dados históricos de matérias semelhantes publicadas na Gazeta do Povo.
    """,
    help_analisadas="Notícias recebidas pelo filtro de Política na última atualização.",
    msg_sem_analise="Ainda não há nenhuma análise gerada para Política.",
    legenda_sem_potencial=(
        "Estas matérias foram analisadas, mas não atingiram nenhum "
        "dos critérios configurados para Política."
    ),
)
