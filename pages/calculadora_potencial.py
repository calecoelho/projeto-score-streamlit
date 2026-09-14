import streamlit as st
import pandas as pd
import numpy as np

from datetime import datetime
from zoneinfo import ZoneInfo

from utils import init_clients


# ============================================================
# CONFIGURAÇÕES
# ============================================================

MODELO_EMBEDDING = "text-embedding-3-large"
DIMENSOES_EMBEDDING = 1536

# Quantas matérias buscar inicialmente no Supabase
POOL_SIZE = 50

# Quantas matérias efetivamente serão utilizadas
TOP_K = 5

# Similaridade mínima
SIMILARIDADE_MINIMA = 0.55

# Número mínimo de matérias semelhantes
MINIMO_MATCHES = 2

# Limiares de potencial
LIMITE_CLIQUES = 2000
LIMITE_TLA_HORAS = 50
LIMITE_LAST_CLICKS = 3

# Janela da média móvel da audiência
JANELA_MEDIA_MOVEL_DIAS = 28

# Meia-vida do peso de recência
#
# 365 dias significa:
#
# hoje       = 1,00
# 365 dias   = 0,50
# 730 dias   = 0,25
#
MEIA_VIDA_RECENCIA_DIAS = 365


# ============================================================
# FORMATAÇÃO
# ============================================================

def formatar_numero(valor, casas=0):
    """
    Formata números no padrão brasileiro.

    Exemplo:
        12345     -> 12.345
        12345.67  -> 12.345,67
    """

    if valor is None or pd.isna(valor):
        return "-"

    if casas == 0:
        return f"{valor:,.0f}".replace(",", ".")

    return (
        f"{valor:,.{casas}f}"
        .replace(",", "X")
        .replace(".", ",")
        .replace("X", ".")
    )


def formatar_horas(horas):
    """
    Formata horas decimais.
    """

    if horas is None or pd.isna(horas):
        return "-"

    return f"{horas:.1f} h"


def formatar_tla_real(segundos):
    """
    Converte o tempo de leitura real armazenado em segundos
    para horas apenas para apresentação.

    Exemplo:
        3600 segundos = 1,0 h
        5400 segundos = 1,5 h
    """

    if segundos is None or pd.isna(segundos):
        return "-"

    segundos = float(segundos)

    return f"{segundos / 3600:.1f} h"


# ============================================================
# PESO DE RECÊNCIA
# ============================================================

def calcular_peso_recencia(data):
    """
    Calcula o peso de recência da matéria.

    A recência NÃO determina quais são as cinco matérias.
    As cinco são escolhidas pela similaridade.

    A recência apenas influencia o peso de cada matéria
    no cálculo dos indicadores relativos.
    """

    if data is None or pd.isna(data):
        return 1.0

    data = pd.Timestamp(data)

    # Remove timezone, se houver
    if data.tzinfo is not None:
        data = data.tz_localize(None)

    hoje = pd.Timestamp.now(
        tz="America/Sao_Paulo"
    ).tz_localize(None)

    idade_dias = max(
        0,
        (hoje - data).total_seconds() / 86400
    )

    peso = (
        0.5
        ** (
            idade_dias
            / MEIA_VIDA_RECENCIA_DIAS
        )
    )

    return float(peso)


# ============================================================
# MÉDIA PONDERADA
# ============================================================

def media_ponderada(valores, pesos):
    """
    Calcula média aritmética ponderada.

    Usada para os indicadores relativos:
        - clique_relativo
        - tempo_leitura_relativo
    """

    valores = pd.to_numeric(
        pd.Series(valores),
        errors="coerce"
    )

    pesos = pd.to_numeric(
        pd.Series(pesos),
        errors="coerce"
    )

    mascara = (
        valores.notna()
        & pesos.notna()
        & (pesos > 0)
    )

    valores = valores[mascara]
    pesos = pesos[mascara]

    if len(valores) == 0:
        return 0.0

    if pesos.sum() == 0:
        return 0.0

    return float(
        np.average(
            valores,
            weights=pesos
        )
    )


# ============================================================
# EMBEDDING
# ============================================================

def gerar_embedding(
    openai_client,
    texto
):
    """
    Gera embedding do título.
    """

    resposta = openai_client.embeddings.create(
        model=MODELO_EMBEDDING,
        input=texto,
        dimensions=DIMENSOES_EMBEDDING
    )

    return resposta.data[0].embedding


# ============================================================
# BUSCA NO HISTÓRICO
# ============================================================

def buscar_historico_similar(
    supabase,
    openai_client,
    novo_titulo
):
    """
    Busca um conjunto amplo de matérias semanticamente
    próximas.

    IMPORTANTE:

    Não aplicamos aqui o corte de similaridade.

    Primeiro buscamos 50 candidatas.
    Depois o Python aplica o corte de similaridade.

    Isso evita que uma busca limitada a apenas 5 registros
    esconda boas correspondências.
    """

    embedding = gerar_embedding(
        openai_client,
        novo_titulo
    )

    resposta = supabase.rpc(
        "match_gp_historico",
        {
            "query_embedding": embedding,
            "match_count": POOL_SIZE
        }
    ).execute()

    if resposta.data is None:
        return pd.DataFrame()

    return pd.DataFrame(
        resposta.data
    )


# ============================================================
# PREPARAÇÃO DO HISTÓRICO
# ============================================================

def preparar_historico(df):
    """
    Processo:

    1. Recebe os 50 candidatos.
    2. Aplica similaridade >= SIMILARIDADE_MINIMA.
    3. Ordena pela similaridade.
    4. Seleciona as 5 melhores.
    """

    if df is None or len(df) == 0:
        return None

    df = df.copy()

    if "similarity" not in df.columns:
        return None

    # --------------------------------------------------------
    # Similaridade
    # --------------------------------------------------------

    df["similarity"] = pd.to_numeric(
        df["similarity"],
        errors="coerce"
    )

    df = df.dropna(
        subset=["similarity"]
    )

    # --------------------------------------------------------
    # CORTE DE SIMILARIDADE
    # --------------------------------------------------------

    df = df[
        df["similarity"]
        >= SIMILARIDADE_MINIMA
    ].copy()

    # --------------------------------------------------------
    # Verifica mínimo de correspondências
    # --------------------------------------------------------

    if len(df) < MINIMO_MATCHES:
        return None

    # --------------------------------------------------------
    # Data
    # --------------------------------------------------------

    if "data" in df.columns:

        df["data"] = pd.to_datetime(
            df["data"],
            errors="coerce"
        )

    # --------------------------------------------------------
    # Campos numéricos
    # --------------------------------------------------------

    colunas_numericas = [
        "cliques",
        "tempo_leitura",
        "clique_geral",
        "tempo_leitura_geral",
        "clique_relativo",
        "tempo_leitura_relativo",
        "last_click"
    ]

    for coluna in colunas_numericas:

        if coluna in df.columns:

            df[coluna] = pd.to_numeric(
                df[coluna],
                errors="coerce"
            )

    # --------------------------------------------------------
    # ORDENAÇÃO PELA SIMILARIDADE
    # --------------------------------------------------------

    df = df.sort_values(
        "similarity",
        ascending=False
    ).copy()

    # --------------------------------------------------------
    # TOP 5
    # --------------------------------------------------------

    df = df.head(
        TOP_K
    ).copy()

    # --------------------------------------------------------
    # PESO DE RECÊNCIA
    # --------------------------------------------------------

    if "data" in df.columns:

        df["peso_recencia"] = (
            df["data"]
            .apply(calcular_peso_recencia)
        )

    else:

        df["peso_recencia"] = 1.0

    return df


# ============================================================
# CÁLCULO DO DESEMPENHO HISTÓRICO
# ============================================================

def calcular_desempenho(df):
    """
    Calcula:

    - média ponderada do clique_relativo
    - média ponderada do tempo_leitura_relativo
    - maior last_click entre as cinco matérias
    """

    if df is None or len(df) < MINIMO_MATCHES:
        return None

    df = df.copy()

    # ========================================================
    # CLIQUE RELATIVO
    # ========================================================

    if "clique_relativo" not in df.columns:

        return None

    clique_relativo = pd.to_numeric(
        df["clique_relativo"],
        errors="coerce"
    )

    pesos = df["peso_recencia"]

    clique_relativo_ponderado = (
        media_ponderada(
            clique_relativo,
            pesos
        )
    )

    # ========================================================
    # TLA RELATIVO
    # ========================================================

    if "tempo_leitura_relativo" not in df.columns:

        return None

    tempo_relativo = pd.to_numeric(
        df["tempo_leitura_relativo"],
        errors="coerce"
    )

    tla_relativo_ponderado = (
        media_ponderada(
            tempo_relativo,
            pesos
        )
    )

    # ========================================================
    # LAST CLICK
    # ========================================================

    if "last_click" in df.columns:

        last_clicks = pd.to_numeric(
            df["last_click"],
            errors="coerce"
        ).fillna(0)

        # REGRA:
        #
        # basta uma das cinco matérias ter
        # pelo menos 3 last clicks.
        #
        max_last_click = float(
            last_clicks.max()
        )

    else:

        max_last_click = 0.0

    # ========================================================
    # RETORNO
    # ========================================================

    return {

        "clique_relativo":
            clique_relativo_ponderado,

        "tla_relativo":
            tla_relativo_ponderado,

        "max_last_click":
            max_last_click
    }


# ============================================================
# AUDIÊNCIA DE REFERÊNCIA
# ============================================================

def obter_audiencia_referencia(
    supabase,
    data_alvo
):
    """
    Calcula a média móvel da audiência.

    Janela:
        últimos 28 dias

    Mas respeitando:
        - dia útil
        - fim de semana

    A data da análise NÃO entra na média.

    Exemplo:

    Análise numa terça-feira:
        considera apenas segunda a sexta
        dos 28 dias anteriores.

    Análise num sábado:
        considera apenas sábados e domingos
        dos 28 dias anteriores.
    """

    try:

        resposta = (
            supabase
            .table("gp_timeseries")
            .select(
                "data,"
                "clique_geral,"
                "tempo_leitura_geral,"
                "dia_semana"
            )
            .execute()
        )

    except Exception as e:

        st.error(
            "Erro ao consultar a série histórica "
            f"de audiência: {e}"
        )

        return None

    if resposta.data is None:
        return None

    ts = pd.DataFrame(
        resposta.data
    )

    if len(ts) == 0:
        return None

    # ========================================================
    # PREPARAÇÃO
    # ========================================================

    ts["data"] = pd.to_datetime(
        ts["data"],
        errors="coerce"
    )

    ts["clique_geral"] = pd.to_numeric(
        ts["clique_geral"],
        errors="coerce"
    )

    ts["tempo_leitura_geral"] = pd.to_numeric(
        ts["tempo_leitura_geral"],
        errors="coerce"
    )

    ts = ts.dropna(
        subset=[
            "data",
            "clique_geral",
            "tempo_leitura_geral"
        ]
    ).copy()

    if len(ts) == 0:
        return None

    # ========================================================
    # DATA DE REFERÊNCIA
    # ========================================================

    data_referencia = pd.Timestamp(
        data_alvo
    ).normalize()

    # ========================================================
    # TIPO DE DIA
    # ========================================================

    weekday = data_referencia.weekday()

    if weekday < 5:

        tipo_dia = "dia útil"

        ts = ts[
            ts["data"].dt.weekday < 5
        ].copy()

    else:

        tipo_dia = "fim de semana"

        ts = ts[
            ts["data"].dt.weekday >= 5
        ].copy()

    # ========================================================
    # JANELA MÓVEL
    # ========================================================

    inicio_janela = (
        data_referencia
        - pd.Timedelta(
            days=JANELA_MEDIA_MOVEL_DIAS
        )
    )

    ts = ts[
        (ts["data"] >= inicio_janela)
        &
        (ts["data"] < data_referencia)
    ].copy()

    if len(ts) == 0:
        return None

    # ========================================================
    # MÉDIA
    # ========================================================

    clique_geral_medio = (
        ts["clique_geral"].mean()
    )

    tempo_leitura_geral_medio = (
        ts["tempo_leitura_geral"].mean()
    )

    return {

        "tipo_dia":
            tipo_dia,

        "clique_geral_medio":
            float(clique_geral_medio),

        "tempo_leitura_geral_medio":
            float(tempo_leitura_geral_medio),

        "n_dias_referencia":
            len(ts)
    }


# ============================================================
# PROJEÇÃO
# ============================================================

def projetar_desempenho(
    resultado_historico,
    audiencia
):
    """
    Converte os indicadores relativos históricos
    em valores absolutos projetados.

    CLIQUES:

        clique_relativo
        ×
        média móvel de cliques da audiência

    TLA:

        tla_relativo
        ×
        média móvel do TLA da audiência

    IMPORTANTE:

    tempo_leitura_geral está em SEGUNDOS.

    Portanto:

        relativo × segundos = segundos

    e somente depois:

        segundos / 3600 = horas
    """

    if resultado_historico is None:
        return None

    if audiencia is None:
        return None

    # ========================================================
    # CLIQUES
    # ========================================================

    cliques_estimados = (
        resultado_historico[
            "clique_relativo"
        ]
        *
        audiencia[
            "clique_geral_medio"
        ]
    )

    # ========================================================
    # TLA EM SEGUNDOS
    # ========================================================

    tla_estimado_segundos = (
        resultado_historico[
            "tla_relativo"
        ]
        *
        audiencia[
            "tempo_leitura_geral_medio"
        ]
    )

    # ========================================================
    # TLA EM HORAS
    # ========================================================

    tla_estimado_horas = (
        tla_estimado_segundos
        / 3600
    )

    # ========================================================
    # POTENCIAL
    # ========================================================

    potencial_cliques = (
        cliques_estimados
        >= LIMITE_CLIQUES
    )

    potencial_tla = (
        tla_estimado_horas
        >= LIMITE_TLA_HORAS
    )

    potencial_assinaturas = (
        resultado_historico[
            "max_last_click"
        ]
        >= LIMITE_LAST_CLICKS
    )

    tem_potencial = (
        potencial_cliques
        or potencial_tla
        or potencial_assinaturas
    )

    return {

        "cliques_estimados":
            float(cliques_estimados),

        "tla_estimado_segundos":
            float(tla_estimado_segundos),

        "tla_estimado_horas":
            float(tla_estimado_horas),

        "clique_relativo":
            float(
                resultado_historico[
                    "clique_relativo"
                ]
            ),

        "tla_relativo":
            float(
                resultado_historico[
                    "tla_relativo"
                ]
            ),

        "max_last_click":
            float(
                resultado_historico[
                    "max_last_click"
                ]
            ),

        "potencial_cliques":
            potencial_cliques,

        "potencial_tla":
            potencial_tla,

        "potencial_assinaturas":
            potencial_assinaturas,

        "tem_potencial":
            tem_potencial
    }


# ============================================================
# INTERFACE
# ============================================================

st.set_page_config(
    page_title="Força Editorial dos Temas",
    page_icon="📊",
    layout="wide"
)


st.title(
    "📊 Calculadora de potencial de clique, TLA e assinatura"
)

st.write(
    "Digite o título de uma nova matéria para estimar "
    "seu potencial editorial com base no desempenho "
    "histórico de matérias semanticamente semelhantes."
)


# ============================================================
# INPUT
# ============================================================

novo_titulo = st.text_input(
    "Título da nova matéria",
    placeholder=(
        "Digite o título da matéria..."
    )
)


analisar = st.button(
    "Analisar",
    type="primary"
)


# ============================================================
# ANÁLISE
# ============================================================

if analisar:

    # ========================================================
    # VALIDAÇÃO
    # ========================================================

    if not novo_titulo.strip():

        st.warning(
            "Digite um título para realizar a análise."
        )

        st.stop()

    # ========================================================
    # CLIENTES
    # ========================================================

    try:

        supabase, openai_client = (
            init_clients()
        )

    except Exception as e:

        st.error(
            "Erro ao inicializar os clientes: "
            f"{e}"
        )

        st.stop()

    # ========================================================
    # DATA DA ANÁLISE
    # ========================================================

    data_alvo = datetime.now(
        ZoneInfo("America/Sao_Paulo")
    ).date()

    # ========================================================
    # BUSCA SEMÂNTICA
    # ========================================================

    with st.spinner(
        "Buscando matérias semelhantes no histórico..."
    ):

        try:

            df_bruto = (
                buscar_historico_similar(
                    supabase,
                    openai_client,
                    novo_titulo
                )
            )

        except Exception as e:

            st.error(
                "Erro ao consultar o histórico: "
                f"{e}"
            )

            st.stop()

    # ========================================================
    # VERIFICAÇÃO DA BUSCA
    # ========================================================

    if df_bruto is None or len(df_bruto) == 0:

        st.warning(
            "A busca não retornou nenhuma matéria "
            "do histórico."
        )

        st.stop()

    # ========================================================
    # PREPARAÇÃO
    # ========================================================

    df_hist = preparar_historico(
        df_bruto
    )

    # ========================================================
    # DIAGNÓSTICO
    # ========================================================

    if df_hist is None:

        st.warning(
            f"Não foram encontradas pelo menos "
            f"{MINIMO_MATCHES} matérias no histórico "
            f"com similaridade de "
            f"{SIMILARIDADE_MINIMA:.0%} ou mais. "
            "Isso inviabiliza a análise."
        )

        # ----------------------------------------------------
        # Mostra as melhores correspondências encontradas
        # mesmo abaixo do limiar
        # ----------------------------------------------------

        diagnostico = df_bruto.copy()

        # Garante que a similaridade seja numérica
        diagnostico["similarity"] = pd.to_numeric(
            diagnostico["similarity"],
            errors="coerce"
        )

        diagnostico = diagnostico.dropna(
            subset=["similarity"]
        )

        # ----------------------------------------------------
        # Ordena pela maior similaridade
        # ----------------------------------------------------

        diagnostico = (
            diagnostico
            .sort_values(
                "similarity",
                ascending=False
            )
            .head(10)
            .copy()
        )

        # ----------------------------------------------------
        # TÍTULO
        # ----------------------------------------------------

        if "titulo" in diagnostico.columns:

            diagnostico["Título"] = (
                diagnostico["titulo"]
            )

        elif "title" in diagnostico.columns:

            diagnostico["Título"] = (
                diagnostico["title"]
            )

        # ----------------------------------------------------
        # DATA DE PUBLICAÇÃO
        # ----------------------------------------------------

        if "data" in diagnostico.columns:

            diagnostico["Data"] = (
                pd.to_datetime(
                    diagnostico["data"],
                    errors="coerce"
                )
                .dt.strftime("%d/%m/%Y")
            )

        # ----------------------------------------------------
        # SIMILARIDADE
        # ----------------------------------------------------

        diagnostico["Similaridade"] = (
            diagnostico["similarity"] * 100
        ).round(1)

        # ----------------------------------------------------
        # CLIQUES TOTAIS DA MATÉRIA
        #
        # Usa "cliques", conforme solicitado.
        # NÃO usa clique_geral.
        # ----------------------------------------------------

        if "cliques" in diagnostico.columns:

            diagnostico["Cliques"] = (
                pd.to_numeric(
                    diagnostico["cliques"],
                    errors="coerce"
                )
            )

        # ----------------------------------------------------
        # TEMPO DE LEITURA
        #
        # Usa "tempo_leitura", conforme solicitado.
        # O valor armazenado em segundos é convertido
        # para horas apenas para apresentação.
        # ----------------------------------------------------

        if "tempo_leitura" in diagnostico.columns:

            diagnostico["TLA"] = (
                pd.to_numeric(
                    diagnostico["tempo_leitura"],
                    errors="coerce"
                )
                .apply(formatar_tla_real)
            )

        # ----------------------------------------------------
        # LAST CLICKS
        # ----------------------------------------------------

        if "last_click" in diagnostico.columns:

            diagnostico["Last click"] = (
                pd.to_numeric(
                    diagnostico["last_click"],
                    errors="coerce"
                )
                .fillna(0)
                .astype(int)
            )

        # ----------------------------------------------------
        # COLUNAS FINAIS
        # ----------------------------------------------------

        colunas_diagnostico = [
            "Título",
            "Data",
            "Similaridade",
            "Cliques",
            "TLA",
            "Last click"
        ]

        colunas_diagnostico = [
            coluna
            for coluna in colunas_diagnostico
            if coluna in diagnostico.columns
        ]

        # ----------------------------------------------------
        # EXIBIÇÃO
        # ----------------------------------------------------

        if len(colunas_diagnostico) > 0:

            st.caption(
                "As 10 matérias semanticamente mais "
                "próximas encontradas pelo modelo, "
                "mesmo quando estão abaixo do limiar "
                f"de {SIMILARIDADE_MINIMA:.0%}:"
            )

            st.dataframe(
                diagnostico[
                    colunas_diagnostico
                ],
                use_container_width=True,
                hide_index=True
            )

        st.stop()

    # ========================================================
    # DESEMPENHO HISTÓRICO
    # ========================================================

    resultado_historico = (
        calcular_desempenho(
            df_hist
        )
    )

    if resultado_historico is None:

        st.warning(
            "Não foi possível calcular o desempenho "
            "das matérias históricas."
        )

        st.stop()

    # ========================================================
    # AUDIÊNCIA DE REFERÊNCIA
    # ========================================================

    with st.spinner(
        "Calculando a audiência de referência..."
    ):

        audiencia = (
            obter_audiencia_referencia(
                supabase,
                data_alvo
            )
        )

    if audiencia is None:

        st.warning(
            "Não foi possível calcular a audiência "
            "de referência para a projeção."
        )

        st.stop()

    # ========================================================
    # PROJEÇÃO
    # ========================================================

    resultado = (
        projetar_desempenho(
            resultado_historico,
            audiencia
        )
    )

    if resultado is None:

        st.warning(
            "Não foi possível realizar a projeção."
        )

        st.stop()

    # ========================================================
    # RESULTADO
    # ========================================================

    st.success(
        f"{len(df_hist)} matérias do histórico "
        "semelhantes utilizadas na análise."
    )

    st.caption(
        f"Audiência de referência: "
        f"{audiencia['tipo_dia']} | "
        f"média móvel dos últimos "
        f"{JANELA_MEDIA_MOVEL_DIAS} dias | "
        f"{audiencia['n_dias_referencia']} dias "
        "efetivamente utilizados."
    )

    # ========================================================
    # DESEMPENHO ESTIMADO
    # ========================================================

    st.subheader(
        "Desempenho estimado com base no histórico"
    )

    col1, col2, col3 = st.columns(3)

    # ========================================================
    # CLIQUES
    # ========================================================

    with col1:

        st.metric(
            "Cliques estimados",
            formatar_numero(
                resultado[
                    "cliques_estimados"
                ]
            )
        )

        st.caption(
            "Taxa relativa histórica: "
            f"{resultado['clique_relativo']:.2%}"
        )

        if resultado[
            "potencial_cliques"
        ]:

            st.success(
                "Alto potencial de cliques "
                f"(≥ {formatar_numero(LIMITE_CLIQUES)})"
            )

        else:

            st.info(
                "Abaixo do limiar de "
                f"{formatar_numero(LIMITE_CLIQUES)} "
                "cliques"
            )

    # ========================================================
    # TLA
    # ========================================================

    with col2:

        st.metric(
            "TLA estimado",
            formatar_horas(
                resultado[
                    "tla_estimado_horas"
                ]
            )
        )

        st.caption(
            "Taxa relativa histórica: "
            f"{resultado['tla_relativo']:.2%}"
        )

        if resultado[
            "potencial_tla"
        ]:

            st.success(
                "Alto potencial de TLA "
                f"(≥ {LIMITE_TLA_HORAS} h)"
            )

        else:

            st.info(
                "Abaixo do limiar de "
                f"{LIMITE_TLA_HORAS} horas"
            )

    # ========================================================
    # LAST CLICK
    # ========================================================

    with col3:

        st.metric(
            "Maior last click histórico",
            formatar_numero(
                resultado[
                    "max_last_click"
                ]
            )
        )

        if resultado[
            "potencial_assinaturas"
        ]:

            st.success(
                "Potencial de gerar assinaturas "
                f"(≥ {LIMITE_LAST_CLICKS} last clicks)"
            )

        else:

            st.info(
                "Nenhuma referência atingiu "
                f"{LIMITE_LAST_CLICKS} last clicks"
            )

    # ========================================================
    # VEREDITO
    # ========================================================

    st.divider()

    if resultado[
        "tem_potencial"
    ]:

        indicadores = []

        if resultado[
            "potencial_cliques"
        ]:

            indicadores.append(
                "cliques"
            )

        if resultado[
            "potencial_tla"
        ]:

            indicadores.append(
                "TLA"
            )

        if resultado[
            "potencial_assinaturas"
        ]:

            indicadores.append(
                "assinaturas"
            )

        indicadores_texto = ", ".join(
            indicadores
        )

        st.success(
            "🟢 Esta pauta apresenta potencial "
            "editorial com base no histórico de "
            "matérias semelhantes. "
            f"Indicador(es): {indicadores_texto}."
        )

    else:

        st.warning(
            "🟡 O histórico encontrado não indica "
            "alto potencial nos indicadores analisados."
        )

    # ========================================================
    # MATÉRIAS DE REFERÊNCIA
    # ========================================================

    st.divider()

    st.subheader(
        "Matérias do histórico utilizadas como referência"
    )

    st.caption(
        "Os cliques e o tempo de leitura abaixo "
        "são os valores reais registrados para "
        "cada matéria. Os indicadores relativos "
        "são usados apenas no cálculo da projeção."
    )

    df_exibir = df_hist.copy()

    # ========================================================
    # SIMILARIDADE
    # ========================================================

    df_exibir["Similaridade"] = (
        df_exibir["similarity"]
        * 100
    ).round(1)

    # ========================================================
    # TÍTULO
    # ========================================================

    if "titulo" in df_exibir.columns:

        df_exibir["Título"] = (
            df_exibir["titulo"]
        )

    elif "title" in df_exibir.columns:

        df_exibir["Título"] = (
            df_exibir["title"]
        )

    # ========================================================
    # CLIQUES REAIS
    # ========================================================

    if "cliques" in df_exibir.columns:

        df_exibir["Cliques"] = (
            pd.to_numeric(
                df_exibir["cliques"],
                errors="coerce"
            )
        )

    elif "cliques_gerados" in df_exibir.columns:

        df_exibir["Cliques"] = (
            pd.to_numeric(
                df_exibir["cliques_gerados"],
                errors="coerce"
            )
        )

    # ========================================================
    # TLA REAL
    # ========================================================

    if "tempo_leitura" in df_exibir.columns:

        df_exibir["TLA"] = (
            df_exibir[
                "tempo_leitura"
            ]
            .apply(
                formatar_tla_real
            )
        )

    # ========================================================
    # LAST CLICK REAL
    # ========================================================

    if "last_click" in df_exibir.columns:

        df_exibir["Last click"] = (
            pd.to_numeric(
                df_exibir[
                    "last_click"
                ],
                errors="coerce"
            )
            .fillna(0)
            .astype(int)
        )

    # ========================================================
    # DATA
    # ========================================================

    if "data" in df_exibir.columns:

        df_exibir["Data"] = (
            pd.to_datetime(
                df_exibir["data"],
                errors="coerce"
            )
            .dt.strftime(
                "%d/%m/%Y"
            )
        )

    # ========================================================
    # COLUNAS FINAIS
    # ========================================================

    colunas_desejadas = [
        "Título",
        "Data",
        "Similaridade",
        "Cliques",
        "TLA",
        "Last click"
    ]

    colunas_finais = [
        coluna
        for coluna in colunas_desejadas
        if coluna in df_exibir.columns
    ]

    st.dataframe(
        df_exibir[
            colunas_finais
        ],
        use_container_width=True,
        hide_index=True
    )