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
    page_title="IA Editorial — Google Trends",
    page_icon="🔥",
    layout="wide",
)


# ============================================================
# CONFIGURAÇÃO EDITORIAL — TRENDS
# ============================================================
#
# Os limites de potencial agora moram em editorias_config.py,
# porque quem faz o cálculo é o job (job_gerar_analises.py),
# não mais esta página.

EDITORIA = "trends_social"


# ============================================================
# CSS
# ============================================================

st.markdown(
    """
    <style>
    .block-container {
        max-width: 1250px;
        padding-top: 2rem;
        padding-bottom: 4rem;
    }

    h1 { letter-spacing: -0.035em; }
    h2 { letter-spacing: -0.025em; }
    h3 { letter-spacing: -0.02em; }

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

    [data-testid="stVerticalBlockBorderWrapper"] { border-radius: 16px; }
    .stLinkButton { border-radius: 9px; font-weight: 650; }
    [data-testid="stExpander"] { border-radius: 12px; }
    [data-testid="stDataFrame"] { border-radius: 10px; }

    hr {
        margin-top: 1.8rem;
        margin-bottom: 1.8rem;
        opacity: 0.25;
    }

    .subtle-text { opacity: 0.58; }
    .badge-text { font-size: 0.78rem; font-weight: 650; opacity: 0.72; }

    @media (max-width: 768px) {
        .block-container {
            padding-top: 1rem;
            padding-left: 1rem;
            padding-right: 1rem;
        }
        h1 { font-size: 1.8rem; }
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
st.title("🔥 Google Trends")
st.markdown(
    """
    Veja o que está em alta no Google Trends que possui potencial de gerar 
    cliques, TLA ou assinaturas. A estimativa de performance é calculada 
    comparando os títulos com matérias semelhantes do histórico da Gazeta do Povo.
    """
)


# ============================================================
# CARREGAR ANÁLISE (CACHE)
# ============================================================
#
# Esta página não coleta mais o Google Trends nem gera embeddings
# na hora. Ela apenas exibe o retrato (snapshot) mais recente salvo
# pelo job job_gerar_analises.py, que roda a cada 30 minutos fora
# do Streamlit.

cache = carregar_cache(supabase, EDITORIA)

if cache is None:
    st.info(
        "Ainda não há nenhuma análise gerada para Trends & Social. "
        "O job de atualização roda a cada 30 minutos — volte em instantes."
    )
    st.stop()

audiencia = cache["audiencia"]
resultados_potenciais = cache["resultados_potenciais"]
resultados_sem_potencial = cache["resultados_sem_potencial"]
feed_total = cache["feed_total"]
descartados = cache["extra"].get("descartados", [])
df_descartados = pd.DataFrame(descartados)

gerado_em = pd.to_datetime(cache["gerado_em"])

st.caption(
    f"Atualizado às {gerado_em.strftime('%H:%M')}  ·  "
    "a análise é recalculada automaticamente a cada 30 minutos"
)


# ============================================================
# AUDIÊNCIA
# ============================================================

with st.expander("📊 Audiência de referência", expanded=False):
    st.caption(
        f"A referência utiliza os {audiencia['n_dias_referencia']} dias anteriores "
        f"do mesmo tipo de dia: **{audiencia['tipo_dia']}**."
    )
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Cliques médios", formatar_numero(audiencia["clique_geral_medio"]))
    with col2:
        st.metric("Tempo de leitura médio", formatar_tla_real(audiencia["tempo_leitura_geral_medio"]))


if feed_total == 0:
    st.info(
        "Nenhuma tendência do Google Trends foi aprovada pelos "
        "filtros na última atualização."
    )
    st.stop()


# ============================================================
# RESUMO
# ============================================================

st.divider()
st.subheader("Visão geral")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Tendências analisadas", feed_total)

with col2:
    st.metric("Oportunidades", len(resultados_potenciais))

with col3:
    st.metric("Sem potencial", len(resultados_sem_potencial))


# ============================================================
# OPORTUNIDADES
# ============================================================

st.divider()
st.subheader("🎯 Oportunidades editoriais de tendências")
st.caption("As oportunidades abaixo são ordenadas pelo potencial estimado de cliques.")

if not resultados_potenciais:
    st.info("Nenhuma tendência aprovada atingiu os critérios mínimos de potencial neste momento.")
else:
    for numero, resultado in enumerate(resultados_potenciais, start=1):
        titulo = resultado.get("titulo", resultado.get("title", "Título não disponível"))
        termo_original = resultado.get("termo", None)
        fonte = resultado.get("source", resultado.get("fonte", "Google Trends"))
        url = resultado.get("url", None)
        published_at = resultado.get("published_at", None)

        if published_at:
            try:
                publicado = pd.to_datetime(published_at).strftime("%d/%m/%Y às %H:%M")
            except Exception:
                publicado = str(published_at)
        else:
            publicado = "-"

        cliques_estimados = resultado.get("cliques_estimados", 0)
        tla_estimado = resultado.get("tempo_leitura_estimado_horas", 0)
        last_click = resultado.get("max_last_click", 0)

        criterios = []
        if resultado.get("potencial_cliques", False):
            criterios.append("Cliques")
        if resultado.get("potencial_tla", False):
            criterios.append("TLA")
        if resultado.get("potencial_last_click", False):
            criterios.append("Last click")

        with st.container(border=True):
            col_titulo, col_numero = st.columns([8, 1])

            with col_titulo:
                st.markdown(f"### {titulo}")
                info_sub = f"{fonte}  ·  {publicado}"
                if termo_original and termo_original.lower() != titulo.lower():
                    info_sub = f"Termo: **{termo_original}**  ·  " + info_sub
                st.caption(info_sub)

            with col_numero:
                st.markdown(f"**#{numero:02d}**")

            st.write("")
            m1, m2, m3 = st.columns(3)

            with m1:
                st.metric("Cliques estimados", formatar_numero(cliques_estimados))
            with m2:
                st.metric("TLA estimado", formatar_horas(tla_estimado))
            with m3:
                st.metric("Maior last click", formatar_numero(last_click))

            if criterios:
                st.write("")
                st.markdown("**Critérios atingidos**")
                st.caption("  ·  ".join(criterios))

            if url:
                st.write("")
                st.link_button("Abrir referência / Google ↗", url)

            # HISTÓRICO COM FORMATAÇÃO COMPLETA RESTAURADA
            historico = resultado.get("historico", pd.DataFrame())
            if historico is not None and not historico.empty:
                with st.expander("📚 Matérias históricas semelhantes na Gazeta do Povo", expanded=False):
                    historico_exibicao = historico.copy()

                    if "titulo" in historico_exibicao.columns:
                        historico_exibicao["Título"] = historico_exibicao["titulo"]
                    elif "title" in historico_exibicao.columns:
                        historico_exibicao["Título"] = historico_exibicao["title"]

                    if "similarity" in historico_exibicao.columns:
                        historico_exibicao["Similaridade"] = historico_exibicao["similarity"].round(3)

                    if "cliques" in historico_exibicao.columns:
                        historico_exibicao["Cliques"] = historico_exibicao["cliques"].apply(formatar_numero)

                    if "tempo_leitura" in historico_exibicao.columns:
                        historico_exibicao["TLA"] = historico_exibicao["tempo_leitura"].apply(formatar_tla_real)

                    if "last_click" in historico_exibicao.columns:
                        historico_exibicao["Last click"] = historico_exibicao["last_click"].apply(formatar_numero)

                    if "data" in historico_exibicao.columns:
                        historico_exibicao["Data"] = pd.to_datetime(
                            historico_exibicao["data"], errors="coerce"
                        ).dt.strftime("%d/%m/%Y")

                    if "url" in historico_exibicao.columns:
                        historico_exibicao["URL"] = historico_exibicao["url"]

                    colunas = ["Título", "Similaridade", "Cliques", "TLA", "Last click", "Data", "URL"]
                    colunas = [c for c in colunas if c in historico_exibicao.columns]

                    st.dataframe(
                        historico_exibicao[colunas],
                        use_container_width=True,
                        hide_index=True,
                    )

            st.write("")


# ============================================================
# MATÉRIAS SEM POTENCIAL
# ============================================================

st.divider()

with st.expander(f"🔎 Tendências sem potencial estimado ({len(resultados_sem_potencial)})"):
    if not resultados_sem_potencial:
        st.success("Todas as tendências analisadas atingiram pelo menos um critério.")
    else:
        st.caption("Estas tendências foram vetorizadas e analisadas, mas não atingiram nenhum dos critérios mínimos configurados.")
        for resultado in resultados_sem_potencial:
            titulo = resultado.get("titulo", resultado.get("title", "Título não disponível"))
            cliques = resultado.get("cliques_estimados", 0)
            tla = resultado.get("tempo_leitura_estimado_horas", 0)
            last_click = resultado.get("max_last_click", 0)

            st.markdown(f"**{titulo}**")
            st.caption(
                f"Cliques estimados: {formatar_numero(cliques)}  ·  "
                f"TLA: {formatar_horas(tla)}  ·  "
                f"Last click: {formatar_numero(last_click)}"
            )


# ============================================================
# REGISTROS DESCARTADOS
# ============================================================

with st.expander(f"🚫 Tendências ignoradas pelos Filtros de Exclusão ({len(df_descartados)})"):
    if not df_descartados.empty:
        st.dataframe(df_descartados, use_container_width=True, hide_index=True)
    else:
        st.write("Nenhuma tendência foi descartada nas regras de exclusão.")