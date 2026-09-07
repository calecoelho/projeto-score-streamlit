import streamlit as st
import pandas as pd

from utils import (
    init_clients,
    gerar_embeddings,
    buscar_candidatos_por_embedding,
    processar_tres_frentes,
)

# -----------------------------------------------------------------------------
# CONFIGURACAO
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Feed Mundo/Internacional | Cruzamento",
    page_icon="🌍",
    layout="wide"
)

try:
    supabase, openai_client = init_clients()
except Exception:
    st.error("Não foi possível inicializar os serviços necessários. Verifique a configuração de Secrets ou entre em contato com o administrador.")
    st.stop()

st.title("🌍 Cruzamento de Feed — Mundo / Internacional")
st.caption("Projeção de desempenho por frente com detalhamento das matérias de comparação históricas")


def buscar_feed_recente(horas_atras=3):
    rpc_res = supabase.rpc('buscar_feed_recente', {'horas_atras': horas_atras}).execute()
    if not rpc_res.data:
        return pd.DataFrame()
    return pd.DataFrame(rpc_res.data)


with st.sidebar:
    st.header("⚙️ Filtro do Feed")
    horas_atras = st.slider("Janela de tempo (horas)", min_value=1, max_value=12, value=3, step=1)

    st.divider()
    st.header("⚙️ Calibração de Pesos")
    sim_thresh = st.slider("Similaridade Mínima (Corte)", 0.20, 0.70, 0.40, 0.05, key="feed_sim_thresh")
    expoente_sim = st.slider(
        "Peso da Similaridade (expoente)", 1.0, 3.0, 2.0, 0.5, key="feed_expoente",
        help="1 = linear, 2 = quadrático, 3 = cúbico."
    )
    meia_vida = st.slider("Meia-vida da Recência (Dias)", 7, 180, 30, 7, key="feed_meia_vida")
    pool_size = st.slider("Pool de Busca no Banco", 15, 50, 30, key="feed_pool_size")
    meta_last_click = st.slider("Meta mínima de last_click (soma Top 5)", 1, 30, 5, 1, key="feed_meta_lc")

if st.button("Buscar e Analisar Feed", type="primary"):
    with st.spinner(f"Buscando matérias das últimas {horas_atras}h em Mundo/Internacional..."):
        try:
            df_feed = buscar_feed_recente(horas_atras=horas_atras)
        except Exception as e:
            st.error("Não foi possível consultar o feed no banco de dados. Tente novamente.")
            st.stop()

    if df_feed.empty:
        st.warning("Nenhuma matéria encontrada no feed para essa janela de tempo.")
        st.stop()

    st.success(f"{len(df_feed)} matérias analisadas no feed.")

    with st.spinner("Gerando embeddings e cruzando com o histórico..."):
        try:
            vetores = gerar_embeddings(openai_client, df_feed['title'].tolist())
        except Exception as e:
            st.error("Não foi possível gerar os embeddings neste momento. Tente novamente.")
            st.stop()

        resultados = []
        barra = st.progress(0.0)
        total = len(df_feed)

        for i, (_, linha) in enumerate(df_feed.iterrows()):
            try:
                df_candidatos = buscar_candidatos_por_embedding(supabase, vetores[i], pool_size=pool_size)
                metricas, df_top5 = processar_tres_frentes(
                    df_candidatos,
                    similarity_threshold=sim_thresh,
                    meia_vida_dias=meia_vida,
                    expoente_similaridade=expoente_sim,
                    meta_last_click=meta_last_click
                )
            except Exception:
                metricas, df_top5 = None, pd.DataFrame()

            if metricas is not None:
                resultados.append({
                    "title": linha["title"],
                    "url": linha["url"],
                    "published_at": linha["published_at"],
                    "cliques_esperados": metricas.get("cliques_esperados", 0),
                    "tempo_horas_esperado": metricas.get("tempo_horas_esperado", 0.0),
                    "last_click_esperado": metricas.get("last_click_esperado", 0.0),
                    "df_top5": df_top5
                })

            barra.progress((i + 1) / total)

        barra.empty()

    if not resultados:
        st.warning("Nenhuma matéria obteve histórico comparável com os parâmetros atuais.")
        st.stop()

    df_res = pd.DataFrame(resultados)

    st.divider()

    # -------------------------------------------------------------------------
    # PAINEL DE RESPOSTAS EM 3 ABAS
    # -------------------------------------------------------------------------
    tab_cliques, tab_tempo, tab_assinaturas = st.tabs([
        "🔥 Potencial de Cliques (> 1.000)",
        "⏱️ Alto Tempo de Leitura (≥ 50h)",
        "🎯 Geradores de Assinatura (≥ 1)"
    ])

    # 1) MATÉRIAS COM BOM NÚMERO DE CLIQUES (> 1000)
    with tab_cliques:
        df_cliques = df_res[df_res["cliques_esperados"] >= 1000].sort_values(by="cliques_esperados", ascending=False)
        st.subheader(f"Matérias com projeção acima de 1.000 cliques ({len(df_cliques)})")
        
        if df_cliques.empty:
            st.info("Nenhuma matéria atingiu a projeção mínima de 1.000 cliques.")
        else:
            for _, row in df_cliques.iterrows():
                col_info, col_val = st.columns([4, 1])
                with col_info:
                    st.markdown(f"### [{row['title']}]({row['url']})")
                    st.caption(f"Publicado em: {row['published_at']}")
                with col_val:
                    st.metric("Cliques Est.", f"{row['cliques_esperados']:,}")

                with st.expander("🔍 Ver matérias de comparação (Base Histórica)"):
                    if not row["df_top5"].empty:
                        st.dataframe(
                            row["df_top5"][[
                                "titulo", "cliques_gerados", "tempo_leitura", 
                                "last_click", "data_publicacao", "similarity"
                            ]],
                            use_container_width=True,
                            hide_index=True
                        )
                    else:
                        st.write("Sem dados detalhados do Top 5.")
                st.divider()

    # 2) MATÉRIAS COM BOM TEMPO DE LEITURA (≥ 50h)
    with tab_tempo:
        df_tempo = df_res[df_res["tempo_horas_esperado"] >= 50.0].sort_values(by="tempo_horas_esperado", ascending=False)
        st.subheader(f"Matérias com alta retenção/tempo de leitura ({len(df_tempo)})")

        if df_tempo.empty:
            st.info("Nenhuma matéria atingiu o limiar de 50 horas estimadas de leitura.")
        else:
            for _, row in df_tempo.iterrows():
                col_info, col_val = st.columns([4, 1])
                with col_info:
                    st.markdown(f"### [{row['title']}]({row['url']})")
                    st.caption(f"Publicado em: {row['published_at']}")
                with col_val:
                    st.metric("Tempo Est.", f"{row['tempo_horas_esperado']} hs")

                with st.expander("🔍 Ver matérias de comparação (Base Histórica)"):
                    if not row["df_top5"].empty:
                        st.dataframe(
                            row["df_top5"][[
                                "titulo", "tempo_leitura", "cliques_gerados", 
                                "last_click", "data_publicacao", "similarity"
                            ]],
                            use_container_width=True,
                            hide_index=True
                        )
                    else:
                        st.write("Sem dados detalhados do Top 5.")
                st.divider()

    # 3) MATÉRIAS QUE PODEM GERAR PELO MENOS UMA ASSINATURA (≥ 1)
    with tab_assinaturas:
        df_subs = df_res[df_res["last_click_esperado"] >= 1.0].sort_values(by="last_click_esperado", ascending=False)
        st.subheader(f"Matérias com potencial de conversão de assinatura ({len(df_subs)})")

        if df_subs.empty:
            st.info("Nenhuma matéria atingiu a projeção mínima de 1 assinatura (last_click).")
        else:
            for _, row in df_subs.iterrows():
                col_info, col_val = st.columns([4, 1])
                with col_info:
                    st.markdown(f"### [{row['title']}]({row['url']})")
                    st.caption(f"Publicado em: {row['published_at']}")
                with col_val:
                    st.metric("Last Clicks Est.", f"{row['last_click_esperado']}")

                with st.expander("🔍 Ver matérias de comparação (Base Histórica)"):
                    if not row["df_top5"].empty:
                        st.dataframe(
                            row["df_top5"][[
                                "titulo", "last_click", "cliques_gerados", 
                                "tempo_leitura", "data_publicacao", "similarity"
                            ]],
                            use_container_width=True,
                            hide_index=True
                        )
                    else:
                        st.write("Sem dados detalhados do Top 5.")
                st.divider()