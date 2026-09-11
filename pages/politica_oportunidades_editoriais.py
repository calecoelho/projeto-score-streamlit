import streamlit as st
import pandas as pd
import numpy as np
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

from utils import init_clients


# ============================================================
# CONFIGURAÇÕES
# ============================================================

DIMENSOES = 1536
TOP_K = 5
SIMILARIDADE_MINIMA = 0.60
MINIMO_MATCHES = 3
LIMITE_CLIQUES = 2000
LIMITE_TLA_HORAS = 50
LIMITE_LAST_CLICK_POR_MATERIA = 3
PESOS_RECENCIA = [
    1.00,
    0.95,
    0.90,
    0.85,
    0.80
]

MAX_WORKERS = 4
LIMITE_DEDUPLICACAO = 0.92


# ============================================================
# CONVERTER EMBEDDING DO SUPABASE
# ============================================================

def converter_embedding(embedding):
    if embedding is None:
        return None

    try:
        if isinstance(embedding, list):
            vetor = embedding
        elif isinstance(embedding, str):
            vetor = json.loads(embedding)
        else:
            return None

        vetor = [float(x) for x in vetor]

        if len(vetor) != DIMENSOES:
            return None

        return vetor
    except Exception:
        return None


# ============================================================
# MÉDIA PONDERADA LOGARÍTMICA
# ============================================================

def media_ponderada_log(valores, pesos):
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
    media_log = (valores_log * pesos).sum() / pesos.sum()

    return float(np.expm1(media_log))


# ============================================================
# CALCULA UMA OPORTUNIDADE
# ============================================================

def analisar_oportunidade(df_hist):
    if df_hist is None or len(df_hist) < MINIMO_MATCHES:
        return None

    df = df_hist.copy()

    if "similarity" not in df.columns:
        return None

    df["similarity"] = pd.to_numeric(df["similarity"], errors="coerce")
    df = df[df["similarity"] >= SIMILARIDADE_MINIMA].copy()

    if len(df) < MINIMO_MATCHES:
        return None

    if "data" in df.columns and "hora" in df.columns:
        df["_data_hora"] = pd.to_datetime(
            df["data"].astype(str) + " " + df["hora"].astype(str),
            errors="coerce"
        )
        df = df.sort_values("_data_hora", ascending=False)
    elif "data" in df.columns:
        df["data"] = pd.to_datetime(df["data"], errors="coerce")
        df = df.sort_values("data", ascending=False)

    df = df.head(TOP_K).copy()

    if len(df) < MINIMO_MATCHES:
        return None

    pesos = PESOS_RECENCIA[:len(df)]

    cliques = media_ponderada_log(df.get("cliques_gerados", pd.Series()), pesos)
    tla_segundos = media_ponderada_log(df.get("tempo_leitura", pd.Series()), pesos)
    tla_horas = tla_segundos / 3600

    last_clicks = pd.to_numeric(df.get("last_click", pd.Series()), errors="coerce").fillna(0)
    total_last_clicks = float(last_clicks.sum())

    potencial_cliques = (cliques >= LIMITE_CLIQUES)
    potencial_tla = (tla_horas > LIMITE_TLA_HORAS)
    potencial_assinaturas = bool((last_clicks >= LIMITE_LAST_CLICK_POR_MATERIA).any())

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
    if not resultados:
        return []

    if len(resultados) == 1:
        return resultados

    embeddings_np = np.array(embeddings, dtype=float)

    normas = np.linalg.norm(embeddings_np, axis=1, keepdims=True)
    normas[normas == 0] = 1
    embeddings_norm = embeddings_np / normas

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

    resultados_finais = []

    for grupo in grupos:
        if len(grupo) == 1:
            resultados_finais.append(resultados[grupo[0]])
            continue

        embeddings_grupo = [
            embeddings_np[resultados[i]["indice_feed"]]
            for i in grupo
        ]

        sao_iguais = all(
            np.array_equal(embeddings_grupo[0], embedding)
            for embedding in embeddings_grupo[1:]
        )

        if sao_iguais:
            melhor = grupo[0]
        else:
            melhor = max(
                grupo,
                key=lambda i: (
                    resultados[i]["cliques"],
                    resultados[i]["tla_horas"],
                    resultados[i]["last_clicks"]
                )
            )

        resultados_finais.append(resultados[melhor])

    return resultados_finais


# ============================================================
# CONSULTAS SUPABASE
# ============================================================

def buscar_noticias_ultima_hora():
    try:
        response = supabase.rpc("buscar_noticias_ultima_hora").execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        st.error(f"Erro ao buscar matérias da última hora: {e}")
        return pd.DataFrame()


def buscar_historico(embedding):
    response = supabase.rpc(
        "match_materias_republica",
        {
            "query_embedding": embedding,
            "match_count": TOP_K
        }
    ).execute()

    return pd.DataFrame(response.data)


# ============================================================
# FUNÇÃO DE PROCESSAMENTO
# ============================================================

def processar_noticia(indice, noticia):
    try:
        embedding = converter_embedding(noticia.get("embedding"))

        if embedding is None:
            return None

        df_hist = buscar_historico(embedding)

        if df_hist.empty:
            return None

        resultado = analisar_oportunidade(df_hist)

        if resultado is None:
            return None

        resultado["indice_feed"] = indice
        return resultado

    except Exception:
        return None


# ============================================================
# INTERFACE E FLUXO AUTOMÁTICO
# ============================================================

st.set_page_config(
    page_title="Oportunidades - Política",
    page_icon="🏛️",
    layout="wide"
)

st.title("🏛️ Oportunidades Editoriais — Política")

st.write(
    "Confira assuntos que outros jornais publicaram na última hora e "
    "que podem ter potencial editorial na Gazeta do Povo. "
    f"As regras atuais para definir sucesso são: mais de {LIMITE_CLIQUES:,.0f}".replace(",", ".") + " cliques, "
    f"ou mais de {LIMITE_TLA_HORAS} horas de TLA ou que uma matéria semelhante tenha tido mais de {LIMITE_LAST_CLICK_POR_MATERIA} last clicks"
)


# ============================================================
# CLIENTES
# ============================================================

try:
    supabase, openai_client = init_clients()
except Exception as e:
    st.error(f"Erro ao inicializar os clientes: {e}")
    st.stop()


# ============================================================
# BUSCA FEED
# ============================================================

with st.spinner("Buscando matérias recentes..."):
    df_noticias = buscar_noticias_ultima_hora()

if df_noticias.empty:
    st.info("Não há publicações recentes.")
    st.stop()


# ============================================================
# IDENTIFICA TÍTULO
# ============================================================

coluna_titulo = "titulo" if "titulo" in df_noticias.columns else ("title" if "title" in df_noticias.columns else None)

if not coluna_titulo:
    st.error("Não encontrei a coluna de título no feed.")
    st.stop()


# ============================================================
# PREPARAR EMBEDDINGS DO FEED PARA DEDUPLICAÇÃO
# ============================================================

lista_embeddings = [
    converter_embedding(noticia.get("embedding"))
    for _, noticia in df_noticias.iterrows()
]


# ============================================================
# PROCESSAMENTO PARALELO
# ============================================================

resultados = []

with st.spinner("Cruzando o feed com o histórico..."):
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [
            executor.submit(
                processar_noticia,
                i,
                noticia
            )
            for i, noticia in df_noticias.iterrows()
        ]

        for future in as_completed(futures):
            resultado = future.result()
            if resultado is not None:
                resultados.append(resultado)


# ============================================================
# SEPARA COM E SEM POTENCIAL
# ============================================================

resultados_sem_potencial = [
    resultado for resultado in resultados
    if not resultado["tem_potencial"]
]

resultados = [
    resultado for resultado in resultados
    if resultado["tem_potencial"]
]

quantidade_sem_potencial = len(resultados_sem_potencial)

titulos_sem_potencial = [
    df_noticias.iloc[resultado["indice_feed"]][coluna_titulo]
    for resultado in resultados_sem_potencial
]


# ============================================================
# DEDUPLICAÇÃO
# ============================================================

if resultados:
    quantidade_antes = len(resultados)

    resultados = deduplicar_resultados(
        resultados,
        lista_embeddings,
        limite_similaridade=LIMITE_DEDUPLICACAO
    )

    quantidade_depois = len(resultados)
else:
    quantidade_antes = 0
    quantidade_depois = 0


# ============================================================
# NADA ENCONTRADO
# ============================================================

if not resultados and not titulos_sem_potencial:
    st.info(
        "Nenhuma matéria recente com potencial, levando em conta dados do "
        f"histórico (mínimo de {MINIMO_MATCHES} matérias semelhantes, "
        f"similaridade mínima de {SIMILARIDADE_MINIMA:.0%})."
    )
    st.stop()


if resultados:

    # ============================================================
    # ORDENA OPORTUNIDADES
    # ============================================================

    resultados = sorted(
        resultados,
        key=lambda x: (
            x["cliques"],
            x["tla_horas"],
            x["last_clicks"]
        ),
        reverse=True
    )

    # ============================================================
    # RESUMO
    # ============================================================

    st.success(f"{quantidade_depois} oportunidades encontradas.")

    if quantidade_sem_potencial:
        st.caption(
            f"{quantidade_sem_potencial} matéria(s) tinham histórico "
            "semelhante, mas não apresentaram potencial e ficaram de fora."
        )

    if quantidade_antes > quantidade_depois:
        st.caption(
            f"{quantidade_antes - quantidade_depois} "
            "matéria(s) semelhante(s) foram agrupadas por deduplicação."
        )

    # ============================================================
    # EXIBIÇÃO
    # ============================================================

    for posicao, resultado in enumerate(resultados, start=1):
        indice = resultado["indice_feed"]
        materia = df_noticias.iloc[indice]

        titulo = materia.get(coluna_titulo, "Sem título")
        fonte = materia.get("source")
        url = materia.get("url")
        publicado_em = materia.get("published_at")
        historico = resultado["historico"]

        st.divider()

        st.subheader(f"{posicao}. {titulo}")

        info_meta = []
        if fonte:
            info_meta.append(f"**Fonte:** {fonte}")
        if publicado_em:
            info_meta.append(f"**Publicado em:** {publicado_em}")

        if info_meta:
            st.caption(" | ".join(info_meta))

        if url:
            st.caption(f"🔗 [Acessar matéria original]({url})")

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric(
                "Cliques estimados",
                f"{resultado['cliques']:,.0f}".replace(",", ".")
            )
            if resultado["potencial_cliques"]:
                st.success("Alto potencial")
            else:
                st.caption(
                    f"Abaixo de {LIMITE_CLIQUES:,.0f}".replace(",", ".")
                )

        with col2:
            st.metric(
                "TLA estimado",
                f"{resultado['tla_horas']:.1f} h"
            )
            if resultado["potencial_tla"]:
                st.success("Alto potencial")
            else:
                st.caption(f"Abaixo de {LIMITE_TLA_HORAS:.0f} h")

        with col3:
            st.metric(
                "Last clicks",
                f"{resultado['last_clicks']:,.0f}".replace(",", ".")
            )
            if resultado["potencial_assinaturas"]:
                st.success("Alto potencial")
            else:
                st.caption(
                    "Nenhuma das matérias bateu "
                    f"{LIMITE_LAST_CLICK_POR_MATERIA} sozinha"
                )

        st.success("🟢 Oportunidade editorial com potencial")

        with st.expander("Ver matérias históricas utilizadas"):
            df_exibir = historico.copy()
            df_exibir["similaridade"] = (df_exibir["similarity"] * 100).round(1)

            renomear = {
                "titulo": "Título",
                "similaridade": "Similaridade",
                "cliques_gerados": "Cliques",
                "tempo_leitura": "TLA",
                "last_click": "Last click",
                "url": "URL"
            }

            df_exibir = df_exibir.rename(columns=renomear)

            colunas_desejadas = [
                "Título",
                "Similaridade",
                "Cliques",
                "TLA",
                "Last click",
                "URL"
            ]

            colunas_finais = [
                coluna for coluna in colunas_desejadas
                if coluna in df_exibir.columns
            ]

            st.dataframe(
                df_exibir[colunas_finais],
                use_container_width=True,
                hide_index=True
            )

else:
    st.info("Nenhuma matéria bateu algum limiar de potencial desta vez.")


# ============================================================
# MATÉRIAS SEM POTENCIAL
# ============================================================

if titulos_sem_potencial:
    st.divider()

    with st.expander(
        f"Matérias analisadas sem potencial alto ({len(titulos_sem_potencial)})"
    ):
        st.caption(
            "Estas matérias foram analisadas, mas têm potencial "
            "baixo de cliques, tempo de leitura e assinatura."
        )

        for titulo_sem_potencial in titulos_sem_potencial:
            st.markdown(f"- {titulo_sem_potencial}")