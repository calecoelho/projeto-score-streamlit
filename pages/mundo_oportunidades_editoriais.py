import streamlit as st
import pandas as pd
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed

from utils import (
    init_clients,
    gerar_embeddings,
    buscar_candidatos_por_embedding,
)


# ============================================================
# CONFIGURAÇÕES
# ============================================================

MODELO_EMBEDDING = "text-embedding-3-small"

TOP_K = 5

# Similaridade mínima entre a nova matéria
# e as matérias históricas
SIMILARIDADE_MINIMA = 0.55

# Mínimo de matérias históricas semelhantes
MINIMO_MATCHES = 3

# Oportunidades do feed da última hora
HORAS_ATRAS = 1

# Limiares de potencial
LIMITE_CLIQUES = 2000
LIMITE_TLA_HORAS = 50
LIMITE_LAST_CLICKS = 10

# Pesos de recência
PESOS_RECENCIA = [
    1.00,
    0.90,
    0.80,
    0.70,
    0.60
]

# Número máximo de análises simultâneas
MAX_WORKERS = 4

# Similaridade entre embeddings do próprio feed
# usada para identificar duplicações
LIMITE_DEDUPLICACAO = 0.95


# ============================================================
# MÉDIA PONDERADA LOGARÍTMICA
# ============================================================

def media_ponderada_log(valores, pesos):
    """
    Calcula uma média ponderada em escala logarítmica.

    A transformação log1p reduz a influência de valores
    muito extremos. Depois, expm1 retorna o resultado
    para a escala original.
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

    valores_log = np.log1p(
        valores
    )

    media_log = (
        valores_log * pesos
    ).sum() / pesos.sum()

    return float(
        np.expm1(media_log)
    )


# ============================================================
# CALCULA UMA OPORTUNIDADE
# ============================================================

def analisar_oportunidade(df_hist):

    if df_hist is None:
        return None

    if len(df_hist) < MINIMO_MATCHES:
        return None

    df = df_hist.copy()

    # --------------------------------------------------------
    # Similaridade
    # --------------------------------------------------------

    if "similarity" not in df.columns:
        return None

    df["similarity"] = pd.to_numeric(
        df["similarity"],
        errors="coerce"
    )

    # Só entram matérias com similaridade >= 55%
    df = df[
        df["similarity"] >= SIMILARIDADE_MINIMA
    ].copy()

    # Precisamos de pelo menos 3 matérias
    if len(df) < MINIMO_MATCHES:
        return None

    # --------------------------------------------------------
    # Ordena histórico pela recência
    # --------------------------------------------------------

    coluna_data = None

    for coluna in [
        "data_publicacao",
        "published_at",
        "data",
        "created_at"
    ]:

        if coluna in df.columns:
            coluna_data = coluna
            break

    if coluna_data:

        df[coluna_data] = pd.to_datetime(
            df[coluna_data],
            errors="coerce"
        )

        df = df.sort_values(
            coluna_data,
            ascending=False
        )

    # --------------------------------------------------------
    # Mantém somente as 5 matérias usadas no cálculo
    # --------------------------------------------------------

    df = df.head(TOP_K).copy()

    if len(df) < MINIMO_MATCHES:
        return None

    # Pesos de recência
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
    # TLA
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

        # O cálculo é feito em segundos
        # e depois convertido para horas.
        tla_segundos = media_ponderada_log(
            df[coluna_tla],
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
        "historico": df,
        "cliques": cliques,
        "tla_horas": tla_horas,
        "last_clicks": total_last_clicks,
        "potencial_cliques": potencial_cliques,
        "potencial_tla": potencial_tla,
        "potencial_assinaturas": potencial_assinaturas,
        "tem_potencial": tem_potencial,
    }


# ============================================================
# DEDUPLICAÇÃO DAS MATÉRIAS DO FEED
# ============================================================

def deduplicar_resultados(
    resultados,
    embeddings,
    limite_similaridade=LIMITE_DEDUPLICACAO
):
    """
    Remove matérias do feed que possuem embeddings muito próximos.

    Regras:

    1. Embeddings exatamente iguais:
       mantém o primeiro título da sequência.

    2. Embeddings muito próximos (>= 95%):
       mantém o título com maior potencial de cliques.

    3. Em caso de empate no potencial de cliques:
       usa TLA e depois last clicks como critérios
       secundários.

    Importante:
    a comparação é feita somente entre matérias que
    já passaram pela análise histórica.
    """

    if not resultados:
        return []

    if len(resultados) == 1:
        return resultados

    embeddings_np = np.array(
        embeddings,
        dtype=float
    )

    # --------------------------------------------------------
    # Normalização dos embeddings
    # --------------------------------------------------------

    normas = np.linalg.norm(
        embeddings_np,
        axis=1,
        keepdims=True
    )

    normas[normas == 0] = 1

    embeddings_norm = (
        embeddings_np / normas
    )

    # --------------------------------------------------------
    # Identifica grupos de matérias semelhantes
    # --------------------------------------------------------

    grupos = []

    visitados = set()

    for i in range(len(resultados)):

        if i in visitados:
            continue

        grupo = [i]

        indice_i = resultados[i]["indice_feed"]

        for j in range(i + 1, len(resultados)):

            if j in visitados:
                continue

            indice_j = resultados[j]["indice_feed"]

            similaridade = float(
                np.dot(
                    embeddings_norm[indice_i],
                    embeddings_norm[indice_j]
                )
            )

            if similaridade >= limite_similaridade:

                grupo.append(j)

        visitados.update(grupo)

        grupos.append(grupo)

    # --------------------------------------------------------
    # Escolhe um título por grupo
    # --------------------------------------------------------

    resultados_finais = []

    for grupo in grupos:

        # Não há duplicação
        if len(grupo) == 1:

            resultados_finais.append(
                resultados[grupo[0]]
            )

            continue

        # ----------------------------------------------------
        # Verifica se os embeddings são exatamente iguais
        # ----------------------------------------------------

        embeddings_grupo = [
            embeddings_np[
                resultados[i]["indice_feed"]
            ]
            for i in grupo
        ]

        sao_iguais = all(
            np.array_equal(
                embeddings_grupo[0],
                embedding
            )
            for embedding in embeddings_grupo[1:]
        )

        if sao_iguais:

            # Exatamente iguais:
            # mantém o primeiro da sequência.
            melhor = grupo[0]

        else:

            # ------------------------------------------------
            # Embeddings muito próximos:
            # escolhe o maior potencial de cliques.
            # ------------------------------------------------

            melhor = max(
                grupo,
                key=lambda i: (
                    resultados[i]["cliques"],
                    resultados[i]["tem_potencial"],
                    resultados[i]["tla_horas"],
                    resultados[i]["last_clicks"]
                )
            )

        resultados_finais.append(
            resultados[melhor]
        )

    return resultados_finais


# ============================================================
# INTERFACE
# ============================================================

st.set_page_config(
    page_title="Mundo — Oportunidades",
    page_icon="🌍",
    layout="wide"
)

st.title(
    "🌍 Oportunidades Editoriais — Mundo / Internacional"
)

st.write(
    "Cruza automaticamente o feed recente com o histórico "
    "de matérias semelhantes para identificar pautas com "
    "potencial editorial."
)


# ============================================================
# CLIENTES
# ============================================================

try:

    supabase, openai_client = init_clients()

except Exception as e:

    st.error(
        f"Erro ao inicializar os clientes: {e}"
    )

    st.stop()


# ============================================================
# BUSCA FEED
# ============================================================

with st.spinner(
    "Buscando matérias recentes..."
):

    try:

        resposta = supabase.rpc(
            "buscar_feed_recente",
            {
                "horas_atras": HORAS_ATRAS
            }
        ).execute()

        feed = resposta.data

    except Exception as e:

        st.error(
            f"Erro ao buscar o feed: {e}"
        )

        st.stop()


if not feed:

    st.info(
        "Nenhuma matéria encontrada no feed recente."
    )

    st.stop()


df_feed = pd.DataFrame(feed)


# ============================================================
# IDENTIFICA TÍTULO
# ============================================================

if "titulo" in df_feed.columns:

    coluna_titulo = "titulo"

elif "title" in df_feed.columns:

    coluna_titulo = "title"

else:

    st.error(
        "Não encontrei a coluna de título no feed."
    )

    st.stop()


# ============================================================
# LIMPA TÍTULOS
# ============================================================

titulos = (
    df_feed[coluna_titulo]
    .fillna("")
    .astype(str)
    .tolist()
)


# ============================================================
# EMBEDDINGS
# ============================================================

with st.spinner(
    "Analisando semanticamente as matérias..."
):

    try:

        embeddings = gerar_embeddings(
            openai_client,
            titulos,
            modelo=MODELO_EMBEDDING
        )

    except Exception as e:

        st.error(
            f"Erro ao gerar embeddings: {e}"
        )

        st.stop()


# ============================================================
# FUNÇÃO DE PROCESSAMENTO
# ============================================================

def processar_materia(
    indice,
    embedding
):

    try:

        candidatos = buscar_candidatos_por_embedding(
            supabase,
            embedding,
            pool_size=TOP_K
        )

        if candidatos is None:
            return None

        df_hist = pd.DataFrame(
            candidatos
        )

        if df_hist.empty:
            return None

        resultado = analisar_oportunidade(
            df_hist
        )

        if resultado is None:
            return None

        resultado["indice_feed"] = indice

        return resultado

    except Exception:

        return None


# ============================================================
# PROCESSAMENTO PARALELO
# ============================================================

resultados = []

with st.spinner(
    "Cruzando o feed com o histórico..."
):

    with ThreadPoolExecutor(
        max_workers=MAX_WORKERS
    ) as executor:

        futures = [
            executor.submit(
                processar_materia,
                i,
                embedding
            )
            for i, embedding in enumerate(
                embeddings
            )
        ]

        for future in as_completed(futures):

            resultado = future.result()

            if resultado is not None:

                resultados.append(
                    resultado
                )


# ============================================================
# DEDUPLICAÇÃO
# ============================================================

if resultados:

    quantidade_antes = len(
        resultados
    )

    resultados = deduplicar_resultados(
        resultados,
        embeddings,
        limite_similaridade=LIMITE_DEDUPLICACAO
    )

    quantidade_depois = len(
        resultados
    )

else:

    quantidade_antes = 0
    quantidade_depois = 0


# ============================================================
# NENHUMA OPORTUNIDADE
# ============================================================

if not resultados:

    st.info(
        "Nenhuma oportunidade editorial encontrada "
        f"com pelo menos {MINIMO_MATCHES} matérias "
        f"históricas e similaridade mínima de "
        f"{SIMILARIDADE_MINIMA:.0%}."
    )

    st.stop()


# ============================================================
# ORDENA OPORTUNIDADES
# ============================================================

resultados = sorted(
    resultados,
    key=lambda x: (
        x["tem_potencial"],
        x["cliques"],
        x["tla_horas"],
        x["last_clicks"]
    ),
    reverse=True
)


# ============================================================
# RESUMO
# ============================================================

if quantidade_antes > quantidade_depois:

    st.success(
        f"{quantidade_depois} oportunidades encontradas."
    )

    st.caption(
        f"{quantidade_antes - quantidade_depois} "
        "matéria(s) semelhante(s) foram agrupadas "
        "por deduplicação."
    )

else:

    st.success(
        f"{quantidade_depois} oportunidades encontradas."
    )


# ============================================================
# EXIBIÇÃO
# ============================================================

for posicao, resultado in enumerate(
    resultados,
    start=1
):

    indice = resultado[
        "indice_feed"
    ]

    titulo = df_feed.iloc[
        indice
    ][coluna_titulo]

    historico = resultado[
        "historico"
    ]

    st.divider()

    # --------------------------------------------------------
    # TÍTULO
    # --------------------------------------------------------

    st.subheader(
        f"{posicao}. {titulo}"
    )

    # --------------------------------------------------------
    # MÉTRICAS
    # --------------------------------------------------------

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
                "Alto potencial"
            )

        else:

            st.caption(
                "Abaixo de 2.000"
            )

    with col2:

        st.metric(
            "TLA estimado",
            f"{resultado['tla_horas']:.1f} h"
        )

        if resultado["potencial_tla"]:

            st.success(
                "Alto potencial"
            )

        else:

            st.caption(
                "Abaixo de 50 h"
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
                "Alto potencial"
            )

        else:

            st.caption(
                "Abaixo de 10"
            )

    # --------------------------------------------------------
    # VEREDITO
    # --------------------------------------------------------

    if resultado["tem_potencial"]:

        st.success(
            "🟢 Oportunidade editorial com potencial"
        )

    else:

        st.warning(
            "🟡 Há histórico semelhante, mas sem "
            "indicador acima dos limiares."
        )

    # --------------------------------------------------------
    # HISTÓRICO
    # --------------------------------------------------------

    with st.expander(
        "Ver matérias históricas utilizadas"
    ):

        df_exibir = historico.copy()

        # Similaridade em porcentagem
        df_exibir["similaridade"] = (
            df_exibir["similarity"] * 100
        ).round(1)

        renomear = {}

        # Título
        if "titulo" in df_exibir.columns:

            renomear["titulo"] = "Título"

        elif "title" in df_exibir.columns:

            renomear["title"] = "Título"

        # Cliques
        if "cliques_gerados" in df_exibir.columns:

            renomear[
                "cliques_gerados"
            ] = "Cliques"

        elif "cliques" in df_exibir.columns:

            renomear[
                "cliques"
            ] = "Cliques"

        # TLA
        if "tempo_leitura" in df_exibir.columns:

            renomear[
                "tempo_leitura"
            ] = "TLA"

        # Last click
        if "last_click" in df_exibir.columns:

            renomear[
                "last_click"
            ] = "Last click"

        # Similaridade
        renomear[
            "similaridade"
        ] = "Similaridade"

        # URL
        if "url" in df_exibir.columns:

            renomear[
                "url"
            ] = "URL"

        df_exibir = df_exibir.rename(
            columns=renomear
        )

        colunas_desejadas = [
            "Título",
            "Similaridade",
            "Cliques",
            "TLA",
            "Last click",
            "URL"
        ]

        colunas_finais = [
            coluna
            for coluna in colunas_desejadas
            if coluna in df_exibir.columns
        ]

        st.dataframe(
            df_exibir[colunas_finais],
            use_container_width=True,
            hide_index=True
        )