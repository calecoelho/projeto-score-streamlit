import streamlit as st
import pandas as pd

from utils import init_clients

from cache_utils import carregar_cache

from processamento import (
    formatar_numero,
    formatar_horas,
    formatar_tla_real,
)


# ============================================================
# CONFIGURAÇÃO DA PÁGINA
# ============================================================

st.set_page_config(
    page_title="IA Editorial — Ciência e Saúde",
    page_icon="🔬",
    layout="wide",
)


# ============================================================
# CONFIGURAÇÃO EDITORIAL — CIÊNCIA E SAÚDE
# ============================================================
#
# O filtro de URL e os limites de potencial agora moram em
# editorias_config.py, porque quem faz o cálculo é o job
# (job_gerar_analises.py), não mais esta página.

EDITORIA = "ciencia_e_saude"


# ============================================================
# CSS
# ============================================================

st.markdown(
    """
    <style>

    /* ========================================================
       ÁREA PRINCIPAL
       ======================================================== */

    .block-container {
        max-width: 1250px;
        padding-top: 2rem;
        padding-bottom: 4rem;
    }


    /* ========================================================
       TÍTULOS
       ======================================================== */

    h1 {
        letter-spacing: -0.035em;
    }

    h2 {
        letter-spacing: -0.025em;
    }

    h3 {
        letter-spacing: -0.02em;
    }


    /* ========================================================
       MÉTRICAS
       ======================================================== */

    [data-testid="stMetric"] {
        background: rgba(128, 128, 128, 0.055);
        border: 1px solid rgba(128, 128, 128, 0.18);
        padding: 18px 20px;
        border-radius: 14px;
    }

    [data-testid="stMetricLabel"] {
        font-size: 0.75rem;
        font-weight: 700;
    }

    [data-testid="stMetricValue"] {
        font-weight: 750;
        letter-spacing: -0.03em;
    }


    /* ========================================================
       CONTAINERS
       ======================================================== */

    [data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: 16px;
    }


    /* ========================================================
       BOTÕES
       ======================================================== */

    .stLinkButton {
        border-radius: 9px;
        font-weight: 650;
    }


    /* ========================================================
       EXPANDERS
       ======================================================== */

    [data-testid="stExpander"] {
        border-radius: 12px;
    }


    /* ========================================================
       DATAFRAME
       ======================================================== */

    [data-testid="stDataFrame"] {
        border-radius: 10px;
    }


    /* ========================================================
       DIVISORES
       ======================================================== */

    hr {
        margin-top: 1.8rem;
        margin-bottom: 1.8rem;
        opacity: 0.25;
    }


    /* ========================================================
       TEXTO SECUNDÁRIO
       ======================================================== */

    .subtle-text {
        opacity: 0.58;
    }


    /* ========================================================
       BADGES
       ======================================================== */

    .badge-text {
        font-size: 0.78rem;
        font-weight: 650;
        opacity: 0.72;
    }


    /* ========================================================
       MOBILE
       ======================================================== */

    @media (max-width: 768px) {

        .block-container {
            padding-top: 1rem;
            padding-left: 1rem;
            padding-right: 1rem;
        }

        h1 {
            font-size: 1.8rem;
        }

    }

    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# CLIENTES
# ============================================================

supabase, openai_client = init_clients()


# ============================================================
# CABEÇALHO
# ============================================================

st.caption("IA EDITORIAL")

st.title("🔬 Ciência e Saúde")

st.markdown(
    """
    Veja o que está rolando nos trends e nos principais jornais
    que pode render cliques, TLA ou assinaturas em
    **CIÊNCIA E SAÚDE**.

    A estimativa de performance é calculada com base em dados
    históricos de matérias semelhantes publicadas na
    Gazeta do Povo.
    """
)


# ============================================================
# CARREGAR ANÁLISE (CACHE)
# ============================================================
#
# Esta página não calcula mais nada em tempo real. Ela apenas
# exibe o retrato (snapshot) mais recente salvo pelo job
# job_gerar_analises.py, que roda a cada 30 minutos fora do
# Streamlit. Isso tira o processamento pesado da mão do usuário
# e deixa a página rápida.

cache = carregar_cache(supabase, EDITORIA)

if cache is None:

    st.info(
        "Ainda não há nenhuma análise gerada para Ciência e Saúde. "
        "O job de atualização roda a cada 30 minutos — volte em instantes."
    )

    st.stop()

audiencia = cache["audiencia"]
resultados_potenciais = cache["resultados_potenciais"]
resultados_sem_potencial = cache["resultados_sem_potencial"]
feed_total = cache["feed_total"]

gerado_em = pd.to_datetime(cache["gerado_em"], utc=True).tz_convert("America/Sao_Paulo")

st.caption(
    f"Atualizado às {gerado_em.strftime('%H:%M')}  ·  "
    "a análise é recalculada automaticamente a cada 30 minutos"
)


# ============================================================
# AUDIÊNCIA
# ============================================================

with st.expander(
    "📊 Audiência de referência",
    expanded=False,
):

    st.caption(
        f"A referência utiliza os "
        f"{audiencia['n_dias_referencia']} dias anteriores "
        f"do mesmo tipo de dia: "
        f"**{audiencia['tipo_dia']}**."
    )

    col1, col2 = st.columns(2)

    with col1:

        st.metric(
            "Cliques médios",
            formatar_numero(
                audiencia["clique_geral_medio"]
            ),
        )

    with col2:

        st.metric(
            "Tempo de leitura médio",
            formatar_tla_real(
                audiencia["tempo_leitura_geral_medio"]
            ),
        )


if feed_total == 0:

    st.info(
        "Nenhuma notícia de Ciência e Saúde encontrada para os "
        "critérios atuais na última atualização."
    )

    st.stop()


# ============================================================
# RESUMO
# ============================================================

st.divider()

st.subheader("Visão geral")

col1, col2, col3 = st.columns(3)


with col1:

    st.metric(
        "Notícias analisadas",
        feed_total,
        help=(
            "Notícias recebidas pelos filtros de Ciência "
            "e Saúde na última atualização."
        ),
    )


with col2:

    st.metric(
        "Oportunidades",
        len(resultados_potenciais),
        help=(
            "Matérias que atingiram pelo menos um "
            "dos critérios de potencial."
        ),
    )


with col3:

    st.metric(
        "Sem potencial",
        len(resultados_sem_potencial),
        help=(
            "Matérias processadas que não atingiram "
            "nenhum critério de potencial."
        ),
    )


# ============================================================
# OPORTUNIDADES
# ============================================================

st.divider()

st.subheader("🎯 Oportunidades editoriais")

st.caption(
    "As oportunidades abaixo são ordenadas pelo "
    "potencial estimado de cliques."
)


if not resultados_potenciais:

    st.info(
        "Nenhuma oportunidade atingiu os critérios "
        "de potencial neste momento."
    )

else:

    for numero, resultado in enumerate(
        resultados_potenciais,
        start=1,
    ):

        # ====================================================
        # DADOS PRINCIPAIS
        # ====================================================

        titulo = resultado.get(
            "titulo",
            resultado.get(
                "title",
                "Título não disponível",
            ),
        )

        fonte = resultado.get(
            "source",
            resultado.get(
                "fonte",
                "-",
            ),
        )

        url = resultado.get(
            "url",
            None,
        )

        published_at = resultado.get(
            "published_at",
            None,
        )


        # ====================================================
        # DATA
        # ====================================================

        if published_at:

            try:

                publicado = pd.to_datetime(
                    published_at
                ).strftime(
                    "%d/%m/%Y às %H:%M"
                )

            except Exception:

                publicado = str(
                    published_at
                )

        else:

            publicado = "-"


        # ====================================================
        # MÉTRICAS
        # ====================================================

        cliques_estimados = resultado.get(
            "cliques_estimados",
            0,
        )

        tla_estimado = resultado.get(
            "tempo_leitura_estimado_horas",
            0,
        )

        last_click = resultado.get(
            "max_last_click",
            0,
        )


        # ====================================================
        # CRITÉRIOS ATINGIDOS
        # ====================================================

        criterios = []


        if resultado.get(
            "potencial_cliques",
            False,
        ):

            criterios.append(
                "Cliques"
            )


        if resultado.get(
            "potencial_tla",
            False,
        ):

            criterios.append(
                "TLA"
            )


        if resultado.get(
            "potencial_last_click",
            False,
        ):

            criterios.append(
                "Last click"
            )


        # ====================================================
        # CARD DA OPORTUNIDADE
        # ====================================================

        with st.container(
            border=True,
        ):

            # -----------------------------------------------
            # CABEÇALHO
            # -----------------------------------------------

            col_titulo, col_numero = st.columns(
                [8, 1]
            )


            with col_titulo:

                st.markdown(
                    f"### {titulo}"
                )

                st.caption(
                    f"{fonte}  ·  {publicado}"
                )


            with col_numero:

                st.markdown(
                    f"**#{numero:02d}**"
                )


            # -----------------------------------------------
            # MÉTRICAS
            # -----------------------------------------------

            st.write("")

            m1, m2, m3 = st.columns(3)


            with m1:

                st.metric(
                    "Cliques estimados",
                    formatar_numero(
                        cliques_estimados
                    ),
                )


            with m2:

                st.metric(
                    "TLA estimado",
                    formatar_horas(
                        tla_estimado
                    ),
                )


            with m3:

                st.metric(
                    "Maior last click",
                    formatar_numero(
                        last_click
                    ),
                )


            # -----------------------------------------------
            # CRITÉRIOS
            # -----------------------------------------------

            if criterios:

                st.write("")

                st.markdown(
                    "**Critérios atingidos**"
                )

                st.caption(
                    "  ·  ".join(
                        criterios
                    )
                )


            # -----------------------------------------------
            # LINK
            # -----------------------------------------------

            if url:

                st.write("")

                st.link_button(
                    "Abrir matéria ↗",
                    url,
                )


            # -----------------------------------------------
            # HISTÓRICO
            # -----------------------------------------------

            historico = resultado.get(
                "historico",
                pd.DataFrame(),
            )


            if (
                historico is not None
                and not historico.empty
            ):

                with st.expander(
                    "📚 Matérias históricas semelhantes",
                    expanded=False,
                ):

                    historico_exibicao = (
                        historico.copy()
                    )


                    # ---------------------------------------
                    # TÍTULO
                    # ---------------------------------------

                    if (
                        "titulo"
                        in historico_exibicao.columns
                    ):

                        historico_exibicao[
                            "Título"
                        ] = historico_exibicao[
                            "titulo"
                        ]

                    elif (
                        "title"
                        in historico_exibicao.columns
                    ):

                        historico_exibicao[
                            "Título"
                        ] = historico_exibicao[
                            "title"
                        ]


                    # ---------------------------------------
                    # SIMILARIDADE
                    # ---------------------------------------

                    if (
                        "similarity"
                        in historico_exibicao.columns
                    ):

                        historico_exibicao[
                            "Similaridade"
                        ] = (
                            historico_exibicao[
                                "similarity"
                            ]
                            .round(3)
                        )


                    # ---------------------------------------
                    # CLIQUES
                    # ---------------------------------------

                    if (
                        "cliques"
                        in historico_exibicao.columns
                    ):

                        historico_exibicao[
                            "Cliques"
                        ] = (
                            historico_exibicao[
                                "cliques"
                            ]
                            .apply(
                                formatar_numero
                            )
                        )


                    # ---------------------------------------
                    # TEMPO DE LEITURA
                    # ---------------------------------------

                    if (
                        "tempo_leitura"
                        in historico_exibicao.columns
                    ):

                        historico_exibicao[
                            "TLA"
                        ] = (
                            historico_exibicao[
                                "tempo_leitura"
                            ]
                            .apply(
                                formatar_tla_real
                            )
                        )


                    # ---------------------------------------
                    # LAST CLICK
                    # ---------------------------------------

                    if (
                        "last_click"
                        in historico_exibicao.columns
                    ):

                        historico_exibicao[
                            "Last click"
                        ] = (
                            historico_exibicao[
                                "last_click"
                            ]
                            .apply(
                                formatar_numero
                            )
                        )


                    # ---------------------------------------
                    # DATA
                    # ---------------------------------------

                    if (
                        "data"
                        in historico_exibicao.columns
                    ):

                        historico_exibicao[
                            "Data"
                        ] = pd.to_datetime(
                            historico_exibicao[
                                "data"
                            ],
                            errors="coerce",
                        ).dt.strftime(
                            "%d/%m/%Y"
                        )


                    # ---------------------------------------
                    # URL
                    # ---------------------------------------

                    if (
                        "url"
                        in historico_exibicao.columns
                    ):

                        historico_exibicao[
                            "URL"
                        ] = historico_exibicao[
                            "url"
                        ]


                    # ---------------------------------------
                    # COLUNAS
                    # ---------------------------------------

                    colunas = [
                        "Título",
                        "Similaridade",
                        "Cliques",
                        "TLA",
                        "Last click",
                        "Data",
                        "URL",
                    ]

                    colunas = [
                        coluna
                        for coluna in colunas
                        if coluna
                        in historico_exibicao.columns
                    ]


                    st.dataframe(
                        historico_exibicao[
                            colunas
                        ],
                        use_container_width=True,
                        hide_index=True,
                    )


        # ====================================================
        # ESPAÇAMENTO
        # ====================================================

        st.write("")


# ============================================================
# MATÉRIAS SEM POTENCIAL
# ============================================================

st.divider()

with st.expander(
    "🔎 Matérias sem potencial "
    "(de acordo com o histórico da Gazeta do Povo) "
    f"({len(resultados_sem_potencial)})"
):

    if not resultados_sem_potencial:

        st.success(
            "Todas as matérias processadas atingiram "
            "pelo menos um critério."
        )

    else:

        st.caption(
            "Estas matérias foram analisadas, mas não "
            "atingiram nenhum dos critérios configurados "
            "para Ciência e Saúde."
        )


        for resultado in resultados_sem_potencial:

            titulo = resultado.get(
                "titulo",
                resultado.get(
                    "title",
                    "Título não disponível",
                ),
            )

            cliques = resultado.get(
                "cliques_estimados",
                0,
            )

            tla = resultado.get(
                "tempo_leitura_estimado_horas",
                0,
            )

            last_click = resultado.get(
                "max_last_click",
                0,
            )


            st.markdown(
                f"**{titulo}**"
            )

            st.caption(
                f"Cliques estimados: "
                f"{formatar_numero(cliques)}"
                f"  ·  "
                f"TLA: "
                f"{formatar_horas(tla)}"
                f"  ·  "
                f"Last click: "
                f"{formatar_numero(last_click)}"
            )
