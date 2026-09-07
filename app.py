import streamlit as st
import pandas as pd
import plotly.express as px

from utils import (
    init_clients,
    buscar_candidatos_supabase,
    processar_tres_frentes,
    analisar_com_llm,
    exibir_badge,
)

# -----------------------------------------------------------------------------
# CONFIGURACAO
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Preditor Editorial Triplo | Score",
    page_icon="📊",
    layout="wide"
)

try:
    supabase, openai_client = init_clients()
except Exception:
    st.error("Não foi possível inicializar os serviços necessários. Verifique a configuração de Secrets ou entre em contato com o administrador.")
    st.stop()

# -----------------------------------------------------------------------------
# INTERFACE GRAFICA
# -----------------------------------------------------------------------------

st.title("📊 Preditor Editorial Triplo")
st.caption("Análise preditiva de desempenho com classificação em 3 faixas por frente")

with st.sidebar:
    st.header("⚙️ Calibração de Pesos")
    sim_thresh = st.slider(
        "Similaridade Mínima (Corte)",
        min_value=0.20, max_value=0.70, value=0.40, step=0.05
    )
    expoente_sim = st.slider(
        "Peso da Similaridade (expoente)",
        min_value=1.0, max_value=3.0, value=2.0, step=0.5,
        help="1 = linear, 2 = quadrático, 3 = cúbico. Quanto maior, mais a diferença "
             "de similaridade entre matérias é amplificada no peso final."
    )
    meia_vida = st.slider(
        "Meia-vida da Recência (Dias)",
        min_value=7, max_value=180, value=30, step=7
    )
    pool_size = st.slider("Pool de Busca no Banco", min_value=15, max_value=50, value=30)

    st.divider()
    meta_last_click = st.slider(
        "Meta mínima de last_click (soma Top 5)",
        min_value=1, max_value=30, value=5, step=1,
        help="Antes era média ponderada de até 30 matérias, agora é soma de só 5 — "
             "recalibre olhando dados reais antes de confiar no valor padrão."
    )

novo_titulo = st.text_input("Digite o novo título da matéria:", placeholder="Ex: Banco Central sinaliza alta na taxa de juros após reunião")

if st.button("Analisar em 3 Frentes", type="primary"):
    if not novo_titulo.strip():
        st.warning("Insira um título antes de realizar a análise.")
    else:
        with st.spinner("Analisando vetores, recência e conversões no Supabase..."):
            try:
                df_bruto = buscar_candidatos_supabase(supabase, openai_client, novo_titulo, pool_size=pool_size)
            except Exception as e:
                st.error("Não foi possível consultar o histórico no banco de dados. Tente novamente ou contate o administrador.")
                st.stop()

            if df_bruto.empty:
                st.error("Nenhuma matéria correspondente encontrada no banco.")
            else:
                metricas, df_top5 = processar_tres_frentes(
                    df_bruto,
                    similarity_threshold=sim_thresh,
                    meia_vida_dias=meia_vida,
                    expoente_similaridade=expoente_sim,
                    meta_last_click=meta_last_click
                )

                if metricas is None:
                    st.warning(f"Nenhuma matéria no acervo atingiu a similaridade mínima de {sim_thresh*100:.0f}%. Tente diminuir o corte na barra lateral.")
                else:
                    try:
                        llm_diag = analisar_com_llm(openai_client, novo_titulo, metricas, df_top5)
                    except Exception as e:
                        st.error("Não foi possível gerar o diagnóstico neste momento. Tente novamente.")
                        st.stop()

                    st.divider()

                    if metricas["veredito_geral"] == "alto_potencial":
                        st.success("🔥 **Alto Potencial de Sucesso:** as 3 frentes estão na faixa Alta / meta atingida.")
                    elif metricas["veredito_geral"] == "atencao":
                        st.warning("⚠️ **Atenção:** pelo menos uma frente está na faixa Fraca.")
                    else:
                        st.info("➖ **Desempenho Mediano:** nenhuma frente fraca, mas nem todas atingiram a faixa Alta.")

                    st.caption(
                        f"Estimativa de cliques e tempo baseada em {metricas['cobertura_validos']} matérias com peso > 0 "
                        f"(tamanho efetivo da amostra: {metricas['tamanho_efetivo_amostra']}). "
                        "Quanto mais perto esse número estiver da cobertura total, mais distribuída está a estimativa; "
                        "quanto menor, mais ela depende de poucas matérias dominantes."
                    )

                    st.subheader("🎯 Projeção de Desempenho por Frente")

                    c1, c2, c3 = st.columns(3)

                    with c1:
                        st.metric(label="1. Cliques Gerados (estimativa)", value=f"{metricas['cliques_esperados']:,}")
                        exibir_badge(metricas["classe_cliques"])

                    with c2:
                        st.metric(label="2. Tempo de Leitura (estimativa)", value=f"{metricas['tempo_horas_esperado']} horas")
                        exibir_badge(metricas["classe_tempo"])

                    with c3:
                        st.metric(label="3. Last Click — soma Top 5", value=f"{metricas['last_click_esperado']}")
                        exibir_badge(metricas["classe_last_click"])

                    st.divider()

                    st.subheader("🧠 Diagnóstico Preditivo por Frente (GPT-4o)")

                    col_a, col_b, col_c = st.columns(3)
                    with col_a:
                        st.markdown("**Frente: Cliques**")
                        st.info(llm_diag["diagnostico_cliques"])
                    with col_b:
                        st.markdown("**Frente: Tempo de Leitura**")
                        st.info(llm_diag["diagnostico_tempo"])
                    with col_c:
                        st.markdown("**Frente: Assinaturas**")
                        st.info(llm_diag["diagnostico_last_click"])

                    st.divider()

                    st.subheader("📈 Matérias do Histórico no Re-rank Ponderado")

                    df_plot = df_top5.copy()
                    df_plot["Similaridade (%)"] = (df_plot["similarity"] * 100).round(1)
                    df_plot["Tempo (Horas)"] = df_plot["tempo_leitura_horas"].round(1)

                    fig = px.bar(
                        df_plot,
                        x="peso_final",
                        y="titulo",
                        orientation="h",
                        color="last_click",
                        hover_data=["cliques_gerados", "Tempo (Horas)", "data_publicacao", "Similaridade (%)"],
                        labels={
                            "peso_final": f"Peso Combinado (Similaridade^{expoente_sim:g} × Recência)",
                            "titulo": "",
                            "last_click": "Assinaturas"
                        },
                        title="Top Matches do Histórico com Maior Relevância Ponderada"
                    )
                    fig.update_layout(yaxis={'categoryorder': 'total ascending'}, height=350)
                    st.plotly_chart(fig, use_container_width=True)

                    with st.expander("Ver tabela detalhada com pesos do Top 5"):
                        st.dataframe(
                            df_top5[[
                                "titulo", "cliques_gerados", "tempo_leitura_horas", "last_click",
                                "data_publicacao", "dia_semana", "similarity",
                                "peso_semantico", "peso_temporal", "peso_final"
                            ]].rename(columns={"tempo_leitura_horas": "tempo_leitura_hs"}),
                            use_container_width=True
                        )
