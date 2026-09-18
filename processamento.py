from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from config import (
    DIMENSOES,
    TOP_K,
    SIMILARIDADE_MINIMA,
    MINIMO_MATCHES,
    JANELA_MEDIA_MOVEL_DIAS,
    MEIA_VIDA_RECENCIA_DIAS,
    LIMITE_DEDUPLICACAO,
    MAX_WORKERS,
    LAST_CLICK_MIN_MATERIAS,
    LAST_CLICK_MUITO_POTENCIAL,
)

from database import (
    buscar_historico_gazeta,
)


# ============================================================
# CONVERSÃO DE EMBEDDING
# ============================================================

def converter_embedding(embedding):
    """
    Converte um embedding vindo do Supabase para uma lista
    de floats com exatamente DIMENSOES dimensões.
    """

    if embedding is None:
        return None

    try:

        if isinstance(embedding, str):
            import json
            embedding = json.loads(embedding)

        vetor = [float(x) for x in embedding]

        if len(vetor) != DIMENSOES:
            return None

        return vetor

    except Exception:
        return None


# ============================================================
# FORMATAÇÃO
# ============================================================

def formatar_numero(valor):
    """
    Formata números no padrão brasileiro.
    """

    if valor is None or pd.isna(valor):
        return "-"

    return f"{valor:,.0f}".replace(",", ".")


def formatar_horas(valor):
    """
    Formata horas com uma casa decimal.
    """

    if valor is None or pd.isna(valor):
        return "-"

    return f"{valor:.1f}h".replace(".", ",")


def formatar_tla_real(segundos):
    """
    Converte segundos para horas apenas para exibição.
    """

    if segundos is None or pd.isna(segundos):
        return "-"

    horas = float(segundos) / 3600

    return f"{horas:.1f}h".replace(".", ",")


# ============================================================
# PESO DE RECÊNCIA
# ============================================================

def calcular_peso_recencia(data):
    """
    Calcula o peso de recência usando meia-vida exponencial.
    """

    if pd.isna(data):
        return 0

    hoje = pd.Timestamp.now(tz="America/Sao_Paulo").tz_localize(None)

    data = pd.Timestamp(data)

    if data.tzinfo is not None:
        data = data.tz_localize(None)

    dias = max(
        0,
        (hoje - data).total_seconds() / 86400
    )

    peso = 0.5 ** (
        dias / MEIA_VIDA_RECENCIA_DIAS
    )

    return peso


# ============================================================
# MÉDIA PONDERADA
# ============================================================

def media_ponderada(valores, pesos):
    """
    Calcula média ponderada ignorando valores inválidos.
    """

    valores = np.asarray(valores, dtype=float)
    pesos = np.asarray(pesos, dtype=float)

    mascara = (
        np.isfinite(valores)
        & np.isfinite(pesos)
    )

    if not mascara.any():
        return 0.0

    valores = valores[mascara]
    pesos = pesos[mascara]

    soma_pesos = pesos.sum()

    if soma_pesos == 0:
        return float(np.mean(valores))

    return float(
        np.sum(valores * pesos) / soma_pesos
    )


# ============================================================
# PREPARAÇÃO DO HISTÓRICO
# ============================================================

def preparar_historico(df):
    """
    Aplica os critérios de seleção do histórico:

    1. similaridade mínima
    2. conversão dos campos numéricos
    3. ordenação por similaridade
    4. seleção dos TOP_K
    5. cálculo do peso de recência
    """

    if df is None or df.empty:
        return pd.DataFrame()

    df = df.copy()

    if "similarity" not in df.columns:
        return pd.DataFrame()

    df["similarity"] = pd.to_numeric(
        df["similarity"],
        errors="coerce"
    )

    df = df.dropna(
        subset=["similarity"]
    )

    df = df[
        df["similarity"] >= SIMILARIDADE_MINIMA
    ].copy()

    if len(df) < MINIMO_MATCHES:
        return pd.DataFrame()

    if "data" in df.columns:
        df["data"] = pd.to_datetime(
            df["data"],
            errors="coerce"
        )

    colunas_numericas = [
        "cliques",
        "tempo_leitura",
        "clique_geral",
        "tempo_leitura_geral",
        "clique_relativo",
        "tempo_leitura_relativo",
        "last_click",
    ]

    for coluna in colunas_numericas:

        if coluna in df.columns:

            df[coluna] = pd.to_numeric(
                df[coluna],
                errors="coerce"
            )

    df = (
        df
        .sort_values(
            "similarity",
            ascending=False
        )
        .head(TOP_K)
        .copy()
    )

    if "data" in df.columns:

        df["peso_recencia"] = (
            df["data"]
            .apply(calcular_peso_recencia)
        )

    else:

        df["peso_recencia"] = 1.0

    return df


# ============================================================
# LAST CLICK (POTENCIAL DE ASSINATURAS)
# ============================================================

def resumir_last_click(last_clicks):
    """
    Resume os last clicks das matérias do histórico
    usadas como referência (até 5).

    Regra:

    - "Potencial de last click": pelo menos
      LAST_CLICK_MIN_MATERIAS matérias do histórico tiveram
      algum last click.

    - "Muito potencial de assinaturas": além de ter potencial,
      a SOMA dos last clicks das matérias do histórico chega
      a LAST_CLICK_MUITO_POTENCIAL.

    O número exibido para o usuário é o total (a soma).
    """

    valores = (
        pd.to_numeric(
            pd.Series(last_clicks, dtype=float),
            errors="coerce"
        )
        .fillna(0)
        .clip(lower=0)
    )

    n_historico = int(len(valores))

    materias_com_last_click = int(
        (valores > 0).sum()
    )

    total_last_click = int(
        round(valores.sum())
    )

    potencial_last_click = (
        materias_com_last_click
        >= LAST_CLICK_MIN_MATERIAS
    )

    muito_potencial_assinaturas = (
        potencial_last_click
        and total_last_click
        >= LAST_CLICK_MUITO_POTENCIAL
    )

    return {
        "n_historico": n_historico,

        "materias_com_last_click": (
            materias_com_last_click
        ),

        "total_last_click": total_last_click,

        "potencial_last_click": bool(
            potencial_last_click
        ),

        "muito_potencial_assinaturas": bool(
            muito_potencial_assinaturas
        ),
    }


# ============================================================
# DESEMPENHO HISTÓRICO
# ============================================================

def calcular_desempenho(df):
    """
    Calcula o desempenho histórico ponderado.

    Usa diretamente os campos relativos já existentes
    no gp_historico:

    - clique_relativo
    - tempo_leitura_relativo

    Não recalcula esses indicadores.

    Também resume os last clicks das matérias do histórico
    (ver resumir_last_click).
    """

    if df is None or df.empty:
        return None

    if (
        "clique_relativo" not in df.columns
        or
        "tempo_leitura_relativo" not in df.columns
    ):
        return None

    pesos = df["peso_recencia"]

    clique_relativo = media_ponderada(
        df["clique_relativo"],
        pesos
    )

    tempo_leitura_relativo = media_ponderada(
        df["tempo_leitura_relativo"],
        pesos
    )

    if "last_click" in df.columns:
        last_clicks = df["last_click"]
    else:
        last_clicks = []

    return {
        "clique_relativo": clique_relativo,
        "tempo_leitura_relativo": tempo_leitura_relativo,
        **resumir_last_click(last_clicks),
    }


# ============================================================
# PROJEÇÃO DE DESEMPENHO
# ============================================================

def projetar_desempenho(
    resultado_historico,
    audiencia,
    limite_cliques,
    limite_tla_horas,
):
    """
    Projeta o desempenho esperado da nova matéria.

    Os limiares de cliques e TLA são recebidos como
    parâmetros porque cada editoria pode ter critérios
    diferentes. A regra do last click é a mesma para todas
    (ver resumir_last_click).
    """

    if resultado_historico is None:
        return None

    if audiencia is None:
        return None

    clique_relativo = (
        resultado_historico["clique_relativo"]
    )

    tempo_leitura_relativo = (
        resultado_historico["tempo_leitura_relativo"]
    )

    # --------------------------------------------------------
    # PROJEÇÃO DE CLIQUES
    # --------------------------------------------------------

    cliques_estimados = (
        clique_relativo
        * audiencia["clique_geral_medio"]
    )

    # --------------------------------------------------------
    # PROJEÇÃO DE TEMPO DE LEITURA
    # --------------------------------------------------------

    tempo_leitura_estimado_segundos = (
        tempo_leitura_relativo
        * audiencia["tempo_leitura_geral_medio"]
    )

    tempo_leitura_estimado_horas = (
        tempo_leitura_estimado_segundos
        / 3600
    )

    # --------------------------------------------------------
    # CRITÉRIOS DE POTENCIAL
    # --------------------------------------------------------

    potencial_cliques = bool(
        cliques_estimados >= limite_cliques
    )

    potencial_tla = bool(
        tempo_leitura_estimado_horas
        >= limite_tla_horas
    )

    potencial_last_click = (
        resultado_historico["potencial_last_click"]
    )

    potencial = (
        potencial_cliques
        or potencial_tla
        or potencial_last_click
    )

    return {
        "cliques_estimados": float(
            cliques_estimados
        ),

        "tempo_leitura_estimado_segundos": float(
            tempo_leitura_estimado_segundos
        ),

        "tempo_leitura_estimado_horas": float(
            tempo_leitura_estimado_horas
        ),

        "n_historico": (
            resultado_historico["n_historico"]
        ),

        "materias_com_last_click": (
            resultado_historico[
                "materias_com_last_click"
            ]
        ),

        "total_last_click": (
            resultado_historico["total_last_click"]
        ),

        "potencial_cliques": potencial_cliques,
        "potencial_tla": potencial_tla,
        "potencial_last_click": potencial_last_click,

        "muito_potencial_assinaturas": (
            resultado_historico[
                "muito_potencial_assinaturas"
            ]
        ),

        "potencial": potencial,
    }


# ============================================================
# PROCESSAMENTO DE UMA NOTÍCIA
# ============================================================

def processar_noticia(
    indice,
    noticia,
    supabase,
    audiencias,
    limite_cliques,
    limite_tla_horas,
    pool_size,
):
    """
    Processa uma notícia individual:

    feed
      ↓
    embedding
      ↓
    histórico semântico   (uma única busca)
      ↓
    filtro de similaridade
      ↓
    top 5
      ↓
    desempenho histórico
      ↓
    projeção para cada cenário (dia útil / fim de semana)

    O histórico é buscado uma vez só e reaproveitado nos
    dois cenários: o que muda entre eles é apenas a
    audiência usada para converter os indicadores relativos
    em cliques e horas.

    Retorna um dicionário {tipo_dia: resultado} ou None.
    """

    try:

        embedding = converter_embedding(
            noticia.get("embedding")
        )

        if embedding is None:
            return None

        historico_bruto = (
            buscar_historico_gazeta(
                supabase,
                embedding,
                pool_size
            )
        )

        historico = preparar_historico(
            historico_bruto
        )

        if historico.empty:
            return None

        desempenho = calcular_desempenho(
            historico
        )

        if desempenho is None:
            return None

        resultados = {}

        for tipo_dia, audiencia in audiencias.items():

            projecao = projetar_desempenho(
                desempenho,
                audiencia,
                limite_cliques,
                limite_tla_horas,
            )

            if projecao is None:
                continue

            resultado = noticia.to_dict()

            resultado.update(projecao)

            resultado["historico"] = historico

            resultado["indice_feed"] = indice

            resultados[tipo_dia] = resultado

        return resultados or None

    except Exception:
        return None


# ============================================================
# DEDUPLICAÇÃO
# ============================================================

def deduplicar_resultados(
    resultados,
    embeddings,
    limite_similaridade=LIMITE_DEDUPLICACAO,
):
    """
    Remove oportunidades praticamente idênticas
    usando similaridade entre embeddings.

    Entre duas matérias muito semelhantes, mantém:
    1. maior clique estimado
    2. maior TLA estimado
    3. maior total de last clicks
    """

    if not resultados:
        return []

    if len(resultados) == 1:
        return resultados

    vetores = []

    for resultado in resultados:

        embedding = converter_embedding(
            resultado.get("embedding")
        )

        vetores.append(embedding)

    grupos = []

    usados = set()

    for i in range(len(resultados)):

        if i in usados:
            continue

        grupo = [i]

        for j in range(i + 1, len(resultados)):

            if j in usados:
                continue

            a = vetores[i]
            b = vetores[j]

            if a is None or b is None:
                continue

            a = np.asarray(a, dtype=float)
            b = np.asarray(b, dtype=float)

            norma_a = np.linalg.norm(a)
            norma_b = np.linalg.norm(b)

            if norma_a == 0 or norma_b == 0:
                continue

            similaridade = (
                np.dot(a, b)
                / (norma_a * norma_b)
            )

            if similaridade >= limite_similaridade:
                grupo.append(j)

        if len(grupo) > 1:

            melhor = max(
                grupo,
                key=lambda x: (
                    resultados[x].get(
                        "cliques_estimados",
                        0
                    ),
                    resultados[x].get(
                        "tempo_leitura_estimado_horas",
                        0
                    ),
                    resultados[x].get(
                        "total_last_click",
                        0
                    ),
                )
            )

            grupos.append(melhor)

            usados.update(grupo)

        else:

            grupos.append(i)
            usados.add(i)

    return [
        resultados[i]
        for i in grupos
    ]


# ============================================================
# GERAR OPORTUNIDADES
# ============================================================

def gerar_oportunidades(
    feed,
    supabase,
    audiencias,
    limite_cliques,
    limite_tla_horas,
    pool_size,
):
    """
    Processa todo o feed para cada cenário de audiência.

    Parâmetros:
        audiencias: {"dia_util": {...}, "fim_de_semana": {...}}
                    (só os cenários com audiência disponível)

    Retorna um dicionário, um item por cenário:

        {
            "dia_util": (potenciais, sem_potencial),
            "fim_de_semana": (potenciais, sem_potencial),
        }

    - potenciais: oportunidades que atingiram algum critério
    - sem_potencial: matérias que não atingiram nenhum
    """

    if feed is None or feed.empty:
        return {
            tipo_dia: ([], [])
            for tipo_dia in audiencias
        }

    feed = feed.reset_index(drop=True)

    por_cenario = {
        tipo_dia: []
        for tipo_dia in audiencias
    }

    # --------------------------------------------------------
    # PROCESSAMENTO PARALELO
    # --------------------------------------------------------

    from concurrent.futures import (
        ThreadPoolExecutor,
        as_completed,
    )

    with ThreadPoolExecutor(
        max_workers=MAX_WORKERS
    ) as executor:

        futuros = {}

        for indice, noticia in feed.iterrows():

            futuro = executor.submit(
                processar_noticia,
                indice,
                noticia,
                supabase,
                audiencias,
                limite_cliques,
                limite_tla_horas,
                pool_size,
            )

            futuros[futuro] = indice

        for futuro in as_completed(futuros):

            resultado = futuro.result()

            if resultado is None:
                continue

            for tipo_dia, item in resultado.items():
                por_cenario[tipo_dia].append(item)

    # --------------------------------------------------------
    # SEPARAÇÃO, DEDUPLICAÇÃO E ORDENAÇÃO (POR CENÁRIO)
    # --------------------------------------------------------

    saida = {}

    for tipo_dia, resultados in por_cenario.items():

        resultados_potenciais = [
            r
            for r in resultados
            if r.get("potencial", False)
        ]

        resultados_sem_potencial = [
            r
            for r in resultados
            if not r.get("potencial", False)
        ]

        resultados_potenciais = (
            deduplicar_resultados(
                resultados_potenciais,
                [
                    r.get("embedding")
                    for r in resultados_potenciais
                ],
            )
        )

        resultados_potenciais.sort(
            key=lambda r: (
                r.get(
                    "cliques_estimados",
                    0
                ),
                r.get(
                    "tempo_leitura_estimado_horas",
                    0
                ),
                r.get(
                    "total_last_click",
                    0
                ),
            ),
            reverse=True,
        )

        resultados_sem_potencial.sort(
            key=lambda r: r.get(
                "cliques_estimados",
                0
            ),
            reverse=True,
        )

        saida[tipo_dia] = (
            resultados_potenciais,
            resultados_sem_potencial,
        )

    return saida
