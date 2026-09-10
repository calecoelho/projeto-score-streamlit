import streamlit as st
import pandas as pd
from utils import init_clients

# -----------------------------------------------------------------------------
# CONFIGURAÇÃO
# -----------------------------------------------------------------------------

st.set_page_config(
    page_title="Força Editorial dos Temas",
    page_icon="📊",
    layout="wide"
)

st.title("📊 Força Editorial dos Temas")

st.caption(
    "Veja como o tema sobre o qual você pretende escrever tem se saído "
    "em termos de cliques, TLA e assinaturas"
)

# -----------------------------------------------------------------------------
# CLIENTES
# -----------------------------------------------------------------------------

try:
    supabase, openai_client = init_clients()

except Exception as e:
    st.error(f"Erro ao inicializar clientes de API: {e}")
    st.stop()

# -----------------------------------------------------------------------------
# ENTRADA
# -----------------------------------------------------------------------------

novo_titulo = st.text_input(
    "Digite o título da matéria ou tema que deseja analisar:",
    placeholder="Ex: Governo anuncia novas medidas para conter inflação"
)

# -----------------------------------------------------------------------------
# BUSCA
# -----------------------------------------------------------------------------

if st.button("Analisar força editorial", type="primary"):

    if not novo_titulo.strip():

        st.warning("Por favor, digite um título ou tema.")

    else:

        with st.spinner(
            "Analisando o histórico de matérias semelhantes..."
        ):

            try:

                # =============================================================
                # 1. GERAR EMBEDDING
                # =============================================================

                response = openai_client.embeddings.create(
                    input=novo_titulo,
                    model="text-embedding-3-large",
                    dimensions=1536
                )

                query_embedding = response.data[0].embedding

                # =============================================================
                # 2. CONFERIR DIMENSÃO
                # =============================================================

                if len(query_embedding) != 1536:

                    st.error(
                        "ERRO: o embedding não possui 1536 dimensões."
                    )

                    st.stop()

                # =============================================================
                # 3. BUSCAR AS 5 MATÉRIAS MAIS SIMILARES
                # =============================================================

                res = supabase.rpc(
                    "match_materias_republica",
                    {
                        "query_embedding": query_embedding,
                        "match_count": 5
                    }
                ).execute()

                df_resultados = pd.DataFrame(res.data)

                # =============================================================
                # 4. VERIFICAR RESULTADOS
                # =============================================================

                if df_resultados.empty:

                    st.warning(
                        "Nenhuma matéria semelhante foi encontrada."
                    )

                    st.stop()

                # =============================================================
                # 5. PREPARAR DATA
                # =============================================================

                df_resultados["data"] = pd.to_datetime(
                    df_resultados["data"],
                    errors="coerce"
                )

                # =============================================================
                # 6. ORDENAR POR RECÊNCIA
                # =============================================================
                #
                # A matéria mais recente recebe o maior peso.
                #
                # Pesos:
                # 1ª mais recente = 1.0
                # 2ª mais recente = 0.9
                # 3ª mais recente = 0.8
                # 4ª mais recente = 0.7
                # 5ª mais recente = 0.6
                #
                # Em caso de mesma data, a similaridade é usada
                # como critério de desempate.
                # =============================================================

                df_resultados = df_resultados.sort_values(
                    by=["data", "similarity"],
                    ascending=[False, False]
                ).reset_index(drop=True)

                pesos = [1.0, 0.9, 0.8, 0.7, 0.6]

                # Caso por alguma razão retornem menos de 5
                pesos = pesos[:len(df_resultados)]

                df_resultados["peso_recencia"] = pesos

                # =============================================================
                # 7. GARANTIR QUE AS MÉTRICAS SÃO NUMÉRICAS
                # =============================================================

                df_resultados["tempo_leitura"] = pd.to_numeric(
                    df_resultados["tempo_leitura"],
                    errors="coerce"
                ).fillna(0)

                df_resultados["cliques_gerados"] = pd.to_numeric(
                    df_resultados["cliques_gerados"],
                    errors="coerce"
                ).fillna(0)

                df_resultados["last_click"] = pd.to_numeric(
                    df_resultados["last_click"],
                    errors="coerce"
                ).fillna(0)

                # =============================================================
                # 8. MÉDIA PONDERADA DE TEMPO DE LEITURA
                # =============================================================

                soma_pesos = df_resultados["peso_recencia"].sum()

                tla_ponderado_segundos = (
                    (
                        df_resultados["tempo_leitura"]
                        * df_resultados["peso_recencia"]
                    ).sum()
                    / soma_pesos
                )

                # Converte o resultado FINAL de segundos para horas
                tla_ponderado_horas = (
                    tla_ponderado_segundos / 3600
                )

                # =============================================================
                # 9. MÉDIA PONDERADA DE CLIQUES
                # =============================================================

                cliques_ponderados = (
                    (
                        df_resultados["cliques_gerados"]
                        * df_resultados["peso_recencia"]
                    ).sum()
                    / soma_pesos
                )

                # =============================================================
                # 10. CONTAGEM DE LAST CLICKS
                # =============================================================

                total_last_clicks = (
                    df_resultados["last_click"].sum()
                )

                # =============================================================
                # 11. CLASSIFICAÇÃO DE CLIQUES
                # =============================================================

                if cliques_ponderados > 2000:

                    classificacao_cliques = (
                        "Potencial alto de cliques"
                    )

                else:

                    classificacao_cliques = (
                        "Potencial baixo de cliques"
                    )

                # =============================================================
                # 12. CLASSIFICAÇÃO DE TLA
                # =============================================================

                if tla_ponderado_horas > 50:

                    classificacao_tla = (
                        "Potencial alto de TLA"
                    )

                else:

                    classificacao_tla = (
                        "Potencial baixo de TLA"
                    )

                # =============================================================
                # 13. CLASSIFICAÇÃO DE ASSINATURAS
                # =============================================================

                if total_last_clicks >= 10:

                    classificacao_assinaturas = (
                        "Potencial alto de assinaturas"
                    )

                else:

                    classificacao_assinaturas = (
                        "Potencial baixo de assinaturas"
                    )

                # =============================================================
                # 14. RESULTADO PRINCIPAL
                # =============================================================

                st.subheader("Resultado da análise")

                col1, col2, col3 = st.columns(3)

                with col1:

                    st.metric(
                        "Cliques históricos ponderados",
                        f"{cliques_ponderados:,.0f}"
                    )

                    st.write(
                        f"**{classificacao_cliques}**"
                    )

                with col2:

                    st.metric(
                        "TLA histórico ponderado",
                        f"{tla_ponderado_horas:,.2f} horas"
                    )

                    st.write(
                        f"**{classificacao_tla}**"
                    )

                with col3:

                    st.metric(
                        "Last clicks",
                        f"{total_last_clicks:,.0f}"
                    )

                    st.write(
                        f"**{classificacao_assinaturas}**"
                    )

                # =============================================================
                # 15. EXIBIR AS 5 MATÉRIAS UTILIZADAS
                # =============================================================

                st.subheader(
                    "As 5 matérias históricas mais semelhantes"
                )

                df_exibicao = df_resultados.copy()

                # Similaridade em %
                if "similarity" in df_exibicao.columns:

                    df_exibicao["similaridade_%"] = (
                        df_exibicao["similarity"] * 100
                    ).round(2)

                # Data em formato brasileiro
                df_exibicao["data"] = (
                    df_exibicao["data"]
                    .dt.strftime("%d/%m/%Y")
                )

                # TLA em horas apenas para visualização
                df_exibicao["tempo_leitura_horas"] = (
                    df_resultados["tempo_leitura"] / 3600
                ).round(2)

                # Selecionar colunas para mostrar
                colunas = [
                    "titulo",
                    "data",
                    "similaridade_%",
                    "tempo_leitura",
                    "tempo_leitura_horas",
                    "cliques_gerados",
                    "last_click",
                    "peso_recencia"
                ]

                colunas = [
                    c for c in colunas
                    if c in df_exibicao.columns
                ]

                st.dataframe(
                    df_exibicao[colunas],
                    use_container_width=True,
                    hide_index=True
                )

            except Exception as e:

                st.error(
                    f"Erro durante a análise: {e}"
                )