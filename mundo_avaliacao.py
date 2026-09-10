import streamlit as st
import pandas as pd
import numpy as np

from utils import (
    init_clients,
    buscar_candidatos_supabase,
)


# ============================================================
# CONFIGURAÇÕES FIXAS
# ============================================================

MODELO_EMBEDDING = "text-embedding-3-small"

TOP_K = 5

# Só consideramos histórico com similaridade >= 55%
SIMILARIDADE_MINIMA = 0.55

# Mínimo de matérias históricas semelhantes
MINIMO_MATCHES = 3

# Limiares de potencial
LIMITE_CLIQUES = 2000
LIMITE_TLA_HORAS = 50
LIMITE_LAST_CLICKS = 10

# Pesos de recência
PESOS_RECENCIA = [1.00, 0.90, 0.80, 0.70, 0.60]


# ============================================================
# FUNÇÕES
# ============================================================

def media_ponderada_log(valores, pesos):
    """
    Média ponderada em escala logarítmica.

    É a mesma lógica usada na página de Oportunidades
    da Política.
    """

    valores = pd.to_numeric(
        pd.Series(valores),
        errors="coerce"
    ).fillna(0)

    if len(valores) == 0:
        return 0.0

    pesos = np.array(
        pesos[:len(valores)],
        dtype=float
    )

    if pesos.sum() == 0:
        return 0.0

    valores_log = np.log1p(valores)

    media_log = (
        valores_log * pesos
    ).sum() / pesos.sum()

    return float(
        np.expm1(media_log)
    )


def preparar_historico(df):
    """
    Limita o histórico às matérias com similaridade >= 55%
    e verifica se existem pelo menos 3 correspondências.
    """

    if df is None or len(df) == 0:
        return None

    df = df.copy()

    if "similarity" not in df.columns:
        return None

    df["similarity"] = pd.to_numeric(
        df["similarity"],
        errors="coerce"
    )

    df = df[
        df["similarity"] >= SIMILARIDADE_MINIMA
    ].copy()

    if len(df) < MINIMO_MATCHES:
        return None

    # Ordena pela data mais recente quando houver data
    colunas_data = [
        c for c in [
            "data_publicacao",
            "published_at",
            "data",
            "created_at"
        ]
        if c in df.columns
    ]

    if colunas_data:
        coluna_data = colunas_data[0]

        df[coluna_data] = pd.to_datetime(
            df[coluna_data],
            errors="coerce"
        )

        df = df.sort_values(
            coluna_data,
            ascending=False
        )

    # Mantemos no máximo as 5 matérias usadas no cálculo
    df = df.head(TOP_K).copy()

    return df


def calcular_desempenho(df):
    """
    Calcula desempenho histórico usando:

    - média ponderada logarítmica para cliques
    - média ponderada logarítmica para TLA
    - soma dos últimos cliques
    - pesos de recência
    """

    if df is None or len(df) < MINIMO_MATCHES:
        return None

    df = df.copy()

    # --------------------------------------------------------
    # Pesos de recência
    # --------------------------------------------------------

    pesos = PESOS_RECENCIA[:len(df)]

    # --------------------------------------------------------
    # CLIQUES
    # --------------------------------------------------------

    if "cliques_gerados" in df.columns:
        coluna_cliques = "cliques_gerados"

    elif "cliques" in df.columns:
        coluna_cliques = "cliques"

    elif "clicks" in df.columns:
        coluna_cliques = "clicks"

    else:
        coluna_cliques = None

    if coluna_cliques:
        cliques = media_ponderada_log(
            df[coluna_cliques],
            pesos
        )
    else:
        cliques = 0.0

    # --------------------------------------------------------
    # TEMPO DE LEITURA
    # --------------------------------------------------------

    if "tempo_leitura" in df.columns:
        coluna_tla = "tempo_leitura"

    elif "tla" in df.columns:
        coluna_tla = "tla"

    elif "totalDuration" in df.columns:
        coluna_tla = "totalDuration"

    else:
        coluna_tla = None

    if coluna_tla:

        tla = pd.to_numeric(
            df[coluna_tla],
            errors="coerce"
        ).fillna(0)

        # O cálculo é feito em segundos,
        # depois convertido para horas.
        tla_segundos = media_ponderada_log(
            tla,
            pesos
        )

        tla_horas = tla_segundos / 3600

    else:
        tla_horas = 0.0

    # --------------------------------------------------------
    # LAST CLICK
    # --------------------------------------------------------

    if "last_click" in df.columns:

        last_clicks = pd.to_numeric(
            df["last_click"],
            errors="coerce"
        ).fillna(0)

        total_last_clicks = float(
            last_clicks.sum()
        )

    else:
        total_last_clicks = 0.0

    # --------------------------------------------------------
    # POTENCIAL
    # --------------------------------------------------------

    potencial_cliques = (
        cliques >= LIMITE_CLIQUES
    )

    potencial_tla = (
        tla_horas > LIMITE_TLA_HORAS
    )

    potencial_assinaturas = (
        total_last_clicks >= LIMITE_LAST_CLICKS
    )

    tem_potencial = (
        potencial_cliques
        or potencial_tla
        or potencial_assinaturas
    )

    return {
        "cliques": cliques,
        "tla_horas": tla_horas,
        "last_clicks": total_last_clicks,
        "potencial_cliques": potencial_cliques,
        "potencial_tla": potencial_tla,
        "potencial_assinaturas": potencial_assinaturas,
        "tem_potencial": tem_potencial,
    }


# ============================================================
# INTERFACE
# ============================================================

st.set_page_config(
    page_title="Mundo — Avaliação",
    page_icon="🌍",
    layout="wide"
)

st.title("🌍 Avaliação — Mundo / Internacional")

st.write(
    "Digite o título de uma nova matéria para avaliar "
    "seu potencial com base no desempenho histórico "
    "de matérias semelhantes."
)


# ============================================================
# INPUT
# ============================================================

novo_titulo = st.text_input(
    "Título da nova matéria",
    placeholder="Digite o título da matéria..."
)


analisar = st.button(
    "Analisar",
    type="primary"
)


# ============================================================
# ANÁLISE
# ============================================================

if analisar:

    if not novo_titulo.strip():

        st.warning(
            "Digite um título para realizar a análise."
        )

        st.stop()

    with st.spinner(
        "Buscando matérias semelhantes no histórico..."
    ):

        try:

            supabase, openai_client = init_clients()

            df_bruto = buscar_candidatos_supabase(
                supabase,
                openai_client,
                novo_titulo,
                pool_size=TOP_K
            )

        except Exception as e:

            st.error(
                f"Erro ao consultar o histórico: {e}"
            )

            st.stop()

    # --------------------------------------------------------
    # PREPARAÇÃO
    # --------------------------------------------------------

    df_hist = preparar_historico(df_bruto)

    if df_hist is None:

        st.warning(
            f"Não há pelo menos {MINIMO_MATCHES} "
            f"matérias históricas com similaridade de "
            f"{SIMILARIDADE_MINIMA:.0%} ou mais."
        )

        st.stop()

    # --------------------------------------------------------
    # CÁLCULO
    # --------------------------------------------------------

    resultado = calcular_desempenho(
        df_hist
    )

    if resultado is None:

        st.warning(
            "Não foi possível calcular o desempenho "
            "histórico."
        )

        st.stop()

    # ========================================================
    # RESULTADOS
    # ========================================================

    st.success(
        f"{len(df_hist)} matérias históricas semelhantes "
        f"encontradas."
    )

    st.subheader("Desempenho histórico estimado")

    col1, col2, col3 = st.columns(3)

    with col1:

        st.metric(
            "Cliques estimados",
            f"{resultado['cliques']:,.0f}".replace(
                ",", "."
            )
        )

        if resultado["potencial_cliques"]:
            st.success(
                "Alto potencial de cliques"
            )
        else:
            st.info(
                "Abaixo do limiar de 2.000 cliques"
            )

    with col2:

        st.metric(
            "TLA estimado",
            f"{resultado['tla_horas']:.1f} h"
        )

        if resultado["potencial_tla"]:
            st.success(
                "Alto potencial de TLA"
            )
        else:
            st.info(
                "Abaixo do limiar de 50 horas"
            )

    with col3:

        st.metric(
            "Last clicks",
            f"{resultado['last_clicks']:,.0f}".replace(
                ",", "."
            )
        )

        if resultado["potencial_assinaturas"]:
            st.success(
                "Alto potencial de conversão"
            )
        else:
            st.info(
                "Abaixo do limiar de 10"
            )

    # ========================================================
    # VEREDITO
    # ========================================================

    st.divider()

    if resultado["tem_potencial"]:

        st.success(
            "🟢 Esta pauta apresenta potencial editorial "
            "com base no histórico de matérias semelhantes."
        )

    else:

        st.warning(
            "🟡 O histórico encontrado não indica "
            "alto potencial nos indicadores analisados."
        )

    # ========================================================
    # HISTÓRICO
    # ========================================================

    st.divider()

    st.subheader(
        "Matérias históricas utilizadas no cálculo"
    )

    df_exibir = df_hist.copy()

    # Similaridade em %
    df_exibir["similaridade"] = (
        df_exibir["similarity"] * 100
    ).round(1)

    # Renomeia colunas quando disponíveis
    renomear = {}

    if "titulo" in df_exibir.columns:
        renomear["titulo"] = "Título"

    elif "title" in df_exibir.columns:
        renomear["title"] = "Título"

    if "cliques_gerados" in df_exibir.columns:
        renomear["cliques_gerados"] = "Cliques"

    elif "cliques" in df_exibir.columns:
        renomear["cliques"] = "Cliques"

    if "tempo_leitura" in df_exibir.columns:
        renomear["tempo_leitura"] = "TLA"

    if "last_click" in df_exibir.columns:
        renomear["last_click"] = "Last click"

    renomear["similaridade"] = "Similaridade"

    df_exibir = df_exibir.rename(
        columns=renomear
    )

    colunas_desejadas = [
        "Título",
        "Similaridade",
        "Cliques",
        "TLA",
        "Last click"
    ]

    colunas_finais = [
        c for c in colunas_desejadas
        if c in df_exibir.columns
    ]

    st.dataframe(
        df_exibir[colunas_finais],
        use_container_width=True,
        hide_index=True
    )