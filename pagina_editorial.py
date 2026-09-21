"""
Desenha as páginas de editoria (Política, Mundo, Ciência e Saúde)
e a página de Trends & Social.

Essas quatro páginas eram quase idênticas -- mudavam só os textos.
Agora o desenho mora aqui, e cada arquivo em pages/ apenas informa
seus textos. Qualquer ajuste visual vale para todas de uma vez.

A página não calcula nada: ela lê o retrato (snapshot) mais recente
que o job (job_gerar_analises.py) salvou no Supabase, para os dois
cenários -- dia útil e fim de semana -- e mostra cada um em uma aba.
"""

import pandas as pd
import streamlit as st

from utils import init_clients

from cache_utils import carregar_cache

from config import (
    ESTIMATIVA_K,
    TIPOS_DIA,
    TOP_K,
    LAST_CLICK_MIN_MATERIAS,
    LAST_CLICK_MUITO_POTENCIAL,
)

from processamento import (
    formatar_numero,
    formatar_horas,
    formatar_tla_real,
)

from componentes_ui import (
    aplicar_css,
    aviso_de_simulacao,
    cartao_chance,
    cartao_last_click,
    criar_abas_de_cenario,
    exibir_assinatura,
    linha_limiar_sucesso,
    rotulo_nivel,
    tabela_historico,
    texto_como_ler,
)


# ============================================================
# PÁGINA
# ============================================================

def renderizar_pagina_editorial(
    editoria,
    page_title,
    page_icon,
    caption_topo,
    titulo,
    descricao,
    rotulo_analisadas="Notícias analisadas",
    help_analisadas=None,
    msg_sem_analise="Ainda não há nenhuma análise gerada.",
    msg_feed_vazio=(
        "Nenhuma notícia encontrada para os critérios atuais "
        "na última atualização."
    ),
    titulo_oportunidades="🎯 Oportunidades editoriais",
    msg_sem_oportunidade=(
        "Nenhuma oportunidade atingiu os critérios "
        "de potencial neste momento."
    ),
    texto_botao_link="Abrir matéria ↗",
    titulo_expander_historico="📚 Matérias históricas semelhantes",
    titulo_expander_sem_potencial="🔎 Matérias sem potencial",
    msg_todas_com_potencial=(
        "Todas as matérias processadas atingiram "
        "pelo menos um critério."
    ),
    legenda_sem_potencial=(
        "Estas matérias foram analisadas, mas não "
        "atingiram nenhum dos critérios configurados."
    ),
    eh_trends=False,
):
    """
    Desenha uma página completa.

    Parâmetros principais:
        editoria: chave da editoria (a mesma de editorias_config.py
                  e do cache), ex.: "politica"
        eh_trends: True para a página do Google Trends. Ela mostra o
                   termo original e a lista de tendências descartadas,
                   e NÃO mostra a data de publicação da matéria de
                   referência (que vem do Trends e estava incorreta).
    """

    st.set_page_config(
        page_title=page_title,
        page_icon=page_icon,
        layout="wide",
    )

    aplicar_css()

    supabase, _openai_client = init_clients()

    # --------------------------------------------------------
    # CABEÇALHO
    # --------------------------------------------------------

    st.caption(caption_topo)

    st.title(titulo)

    st.markdown(descricao)

    st.info(texto_como_ler())

    # --------------------------------------------------------
    # CARREGAR ANÁLISE (CACHE) DOS DOIS CENÁRIOS
    # --------------------------------------------------------

    caches = {
        tipo_dia: carregar_cache(supabase, editoria, tipo_dia)
        for tipo_dia in TIPOS_DIA
    }

    if all(cache is None for cache in caches.values()):

        st.info(
            f"{msg_sem_analise} "
            "O job de atualização roda a cada 30 minutos — "
            "volte em instantes."
        )

        exibir_assinatura()

        return

    # --------------------------------------------------------
    # ABAS: DIA ÚTIL x FIM DE SEMANA (a de hoje abre primeiro)
    # --------------------------------------------------------

    for tipo_dia, aba, e_hoje in criar_abas_de_cenario():

        with aba:

            _renderizar_cenario(
                tipo_dia=tipo_dia,
                e_hoje=e_hoje,
                cache=caches[tipo_dia],
                rotulo_analisadas=rotulo_analisadas,
                help_analisadas=help_analisadas,
                msg_feed_vazio=msg_feed_vazio,
                titulo_oportunidades=titulo_oportunidades,
                msg_sem_oportunidade=msg_sem_oportunidade,
                texto_botao_link=texto_botao_link,
                titulo_expander_historico=titulo_expander_historico,
                titulo_expander_sem_potencial=titulo_expander_sem_potencial,
                msg_todas_com_potencial=msg_todas_com_potencial,
                legenda_sem_potencial=legenda_sem_potencial,
                eh_trends=eh_trends,
            )

    exibir_assinatura()


# ============================================================
# UM CENÁRIO (UMA ABA)
# ============================================================

def _renderizar_cenario(
    tipo_dia,
    e_hoje,
    cache,
    rotulo_analisadas,
    help_analisadas,
    msg_feed_vazio,
    titulo_oportunidades,
    msg_sem_oportunidade,
    texto_botao_link,
    titulo_expander_historico,
    titulo_expander_sem_potencial,
    msg_todas_com_potencial,
    legenda_sem_potencial,
    eh_trends,
):

    if not e_hoje:
        aviso_de_simulacao(tipo_dia)

    if cache is None:

        st.info(
            "Ainda não há análise gerada para este cenário. "
            "Volte na próxima atualização."
        )

        return

    audiencia = cache["audiencia"]
    resultados_potenciais = cache["resultados_potenciais"]
    resultados_sem_potencial = cache["resultados_sem_potencial"]
    feed_total = cache["feed_total"]

    gerado_em = pd.to_datetime(
        cache["gerado_em"],
        utc=True,
    ).tz_convert("America/Sao_Paulo")

    st.caption(
        f"Atualizado às {gerado_em.strftime('%H:%M')}  ·  "
        "a análise é recalculada automaticamente a cada 30 minutos"
    )

    # --------------------------------------------------------
    # AUDIÊNCIA
    # --------------------------------------------------------

    if audiencia:

        with st.expander("📊 Audiência de referência", expanded=False):

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
                    formatar_numero(audiencia["clique_geral_medio"]),
                )

            with col2:
                st.metric(
                    "Tempo de leitura médio",
                    formatar_tla_real(
                        audiencia["tempo_leitura_geral_medio"]
                    ),
                )

    if feed_total == 0:

        st.info(msg_feed_vazio)

        return

    # --------------------------------------------------------
    # RESUMO
    # --------------------------------------------------------

    st.divider()

    st.subheader("Visão geral")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            rotulo_analisadas,
            feed_total,
            help=help_analisadas,
        )

    with col2:
        st.metric(
            "Oportunidades",
            len(resultados_potenciais),
            help=(
                "Matérias com chance alta de ficar entre as melhores "
                "do tipo de dia em cliques ou em TLA, ou com "
                "potencial de last click."
            ),
        )

    with col3:
        st.metric(
            "Sem potencial",
            len(resultados_sem_potencial),
            help=(
                "Matérias processadas sem chance acima da média "
                "em nenhum critério."
            ),
        )

    # --------------------------------------------------------
    # OPORTUNIDADES
    # --------------------------------------------------------

    st.divider()

    st.subheader(titulo_oportunidades)

    linha_limiar = linha_limiar_sucesso(tipo_dia, audiencia)

    if linha_limiar:
        st.caption(linha_limiar)

    st.caption(
        f"Ordenadas pela estimativa de cliques. A estimativa usa as "
        f"{ESTIMATIVA_K} matérias mais parecidas do histórico. Last click: "
        f"verde quando {LAST_CLICK_MIN_MATERIAS}+ das {TOP_K} mais "
        f"parecidas tiveram last click (muito potencial de assinaturas: "
        f"{LAST_CLICK_MUITO_POTENCIAL}+ last clicks no total)."
    )

    if not resultados_potenciais:

        st.info(msg_sem_oportunidade)

    else:

        for numero, resultado in enumerate(
            resultados_potenciais,
            start=1,
        ):

            _renderizar_oportunidade(
                tipo_dia=tipo_dia,
                numero=numero,
                resultado=resultado,
                texto_botao_link=texto_botao_link,
                titulo_expander_historico=titulo_expander_historico,
                eh_trends=eh_trends,
            )

            st.write("")

    # --------------------------------------------------------
    # MATÉRIAS SEM POTENCIAL
    # --------------------------------------------------------

    st.divider()

    with st.expander(
        f"{titulo_expander_sem_potencial} "
        f"({len(resultados_sem_potencial)})"
    ):

        if not resultados_sem_potencial:

            st.success(msg_todas_com_potencial)

        else:

            st.caption(legenda_sem_potencial)

            for resultado in resultados_sem_potencial:

                titulo = resultado.get(
                    "titulo",
                    resultado.get("title", "Título não disponível"),
                )

                st.markdown(f"**{titulo}**")

                st.caption(
                    f"Cliques estimados: "
                    f"{formatar_numero(resultado.get('cliques_estimados', 0))}"
                    f" ({rotulo_nivel(resultado.get('nivel_cliques'))} de sucesso)"
                    f"  ·  "
                    f"TLA: "
                    f"{formatar_horas(resultado.get('tempo_leitura_estimado_horas', 0))}"
                    f" ({rotulo_nivel(resultado.get('nivel_tla'))} de sucesso)"
                    f"  ·  "
                    f"Last click: "
                    f"{formatar_numero(resultado.get('total_last_click', 0))}"
                    f" (em {resultado.get('materias_com_last_click', 0)} de "
                    f"{resultado.get('n_historico', 0)} matérias)"
                )

    # --------------------------------------------------------
    # REGISTROS DESCARTADOS (SÓ NO TRENDS)
    # --------------------------------------------------------

    if eh_trends:

        descartados = cache["extra"].get("descartados", [])

        df_descartados = pd.DataFrame(descartados)

        with st.expander(
            "🚫 Tendências ignoradas pelos Filtros de Exclusão "
            f"({len(df_descartados)})"
        ):

            if not df_descartados.empty:

                st.dataframe(
                    df_descartados,
                    use_container_width=True,
                    hide_index=True,
                    key=f"descartados_{tipo_dia}",
                )

            else:

                st.write(
                    "Nenhuma tendência foi descartada "
                    "nas regras de exclusão."
                )


# ============================================================
# UMA OPORTUNIDADE (CARD)
# ============================================================

def _renderizar_oportunidade(
    tipo_dia,
    numero,
    resultado,
    texto_botao_link,
    titulo_expander_historico,
    eh_trends,
):

    titulo = resultado.get(
        "titulo",
        resultado.get("title", "Título não disponível"),
    )

    fonte = resultado.get(
        "source",
        resultado.get("fonte", "Google Trends" if eh_trends else "-"),
    )

    url = resultado.get("url", None)

    # --------------------------------------------------------
    # LINHA DE APOIO DO TÍTULO
    # --------------------------------------------------------
    #
    # Nas editorias: fonte + data de publicação.
    # No Trends: termo + fonte, SEM a data (a data da matéria de
    # referência que vem do Google Trends estava incorreta).

    if eh_trends:

        info_sub = f"{fonte}"

        termo_original = resultado.get("termo", None)

        if (
            termo_original
            and str(termo_original).lower() != str(titulo).lower()
        ):
            info_sub = f"Termo: **{termo_original}**  ·  " + info_sub

    else:

        published_at = resultado.get("published_at", None)

        if published_at:

            try:
                publicado = pd.to_datetime(
                    published_at
                ).strftime("%d/%m/%Y às %H:%M")

            except Exception:
                publicado = str(published_at)

        else:
            publicado = "-"

        info_sub = f"{fonte}  ·  {publicado}"

    # --------------------------------------------------------
    # CARD
    # --------------------------------------------------------

    with st.container(border=True):

        col_titulo, col_numero = st.columns([8, 1])

        with col_titulo:

            st.markdown(f"### {titulo}")

            st.caption(info_sub)

        with col_numero:

            st.markdown(f"**#{numero:02d}**")

        st.write("")

        # ----------------------------------------------------
        # CHANCE DE PASSAR DA META (CLIQUES E TLA) E LAST CLICK
        # ----------------------------------------------------

        m1, m2, m3 = st.columns(3)

        with m1:

            st.markdown(
                cartao_chance(
                    rotulo="Cliques estimados",
                    valor=formatar_numero(
                        resultado.get("cliques_estimados", 0)
                    ),
                    resultado=resultado,
                    chave="cliques",
                ),
                unsafe_allow_html=True,
            )

        with m2:

            st.markdown(
                cartao_chance(
                    rotulo="TLA estimado",
                    valor=formatar_horas(
                        resultado.get("tempo_leitura_estimado_horas", 0)
                    ),
                    resultado=resultado,
                    chave="tla",
                ),
                unsafe_allow_html=True,
            )

        with m3:

            st.markdown(
                cartao_last_click(resultado),
                unsafe_allow_html=True,
            )

        # ----------------------------------------------------
        # LINK
        # ----------------------------------------------------

        if url:

            st.write("")

            st.link_button(
                texto_botao_link,
                url,
            )

        # ----------------------------------------------------
        # HISTÓRICO
        # ----------------------------------------------------

        historico = resultado.get("historico", pd.DataFrame())

        if historico is not None and not historico.empty:

            with st.expander(
                titulo_expander_historico,
                expanded=False,
            ):

                st.caption(
                    f"As {len(historico)} matérias abaixo entram na "
                    f"estimativa, com mais peso para as mais parecidas. "
                    f"As {min(TOP_K, len(historico))} primeiras "
                    "(mais parecidas) definem o last click."
                )

                tabela_historico(
                    historico,
                    key=f"historico_{tipo_dia}_{numero}",
                )
