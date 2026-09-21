import streamlit as st
import pandas as pd

from datetime import datetime
from zoneinfo import ZoneInfo

from utils import init_clients

from database import obter_audiencias_referencia

from config import (
    JANELA_MEDIA_MOVEL_DIAS,
    MINIMO_MATCHES,
    POOL_SIZE,
    SIMILARIDADE_MINIMA,
    TOP_K,
)

from processamento import (
    calcular_desempenho,
    preparar_historico,
    projetar_desempenho,
)

from componentes_ui import (
    LEGENDA_CORES,
    aviso_de_simulacao,
    cartao_chance,
    cartao_last_click,
    criar_abas_de_cenario,
    aplicar_css,
    exibir_assinatura,
    peso_no_calculo,
)


# ============================================================
# CONFIGURAÇÕES
# ============================================================

MODELO_EMBEDDING = "text-embedding-3-large"
DIMENSOES_EMBEDDING = 1536

# Quantas matérias buscar, quantas entram na estimativa (ESTIMATIVA_K)
# e a similaridade mínima ficam em config.py, para a calculadora e as
# páginas de editoria usarem exatamente as mesmas regras.

# Não há meta fixa de cliques ou de horas: o sucesso é ficar entre as
# melhores pautas do mesmo tipo de dia (config.py, CHANCE_FATIA). O last
# click segue a regra de config.py: LAST_CLICK_MIN_MATERIAS e
# LAST_CLICK_MUITO_POTENCIAL.

# A estimativa (pesos, média em log, chance) é calculada em
# processamento.py -- o mesmo cálculo usado pelo job das páginas de
# editoria, para as estimativas baterem.


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
# RESULTADO DE UM CENÁRIO (UMA ABA)
# ============================================================

def mostrar_cenario(tipo_dia, e_hoje, resultado, audiencia):
    """
    Mostra o desempenho estimado de um cenário
    (dia útil ou fim de semana).
    """

    if not e_hoje:
        aviso_de_simulacao(tipo_dia)

    if resultado is None or audiencia is None:

        st.info(
            "Não há dados de audiência suficientes "
            "para simular este cenário."
        )

        return

    st.caption(
        f"Audiência de referência: "
        f"{audiencia['tipo_dia']} | "
        f"média móvel dos últimos "
        f"{JANELA_MEDIA_MOVEL_DIAS} dias | "
        f"{audiencia['n_dias_referencia']} dias "
        "efetivamente utilizados."
    )

    st.subheader(
        "Desempenho estimado com base no histórico"
    )

    st.caption(LEGENDA_CORES)

    col1, col2, col3 = st.columns(3)

    # ========================================================
    # CLIQUES
    # ========================================================

    with col1:

        st.markdown(
            cartao_chance(
                rotulo="Cliques estimados",
                valor=formatar_numero(
                    resultado["cliques_estimados"]
                ),
                resultado=resultado,
                chave="cliques",
            ),
            unsafe_allow_html=True,
        )

    # ========================================================
    # TLA
    # ========================================================

    with col2:

        st.markdown(
            cartao_chance(
                rotulo="TLA estimado",
                valor=formatar_horas(
                    resultado["tempo_leitura_estimado_horas"]
                ),
                resultado=resultado,
                chave="tla",
            ),
            unsafe_allow_html=True,
        )

    # ========================================================
    # LAST CLICK
    # ========================================================

    with col3:

        st.markdown(
            cartao_last_click(resultado),
            unsafe_allow_html=True,
        )

    # ========================================================
    # VEREDITO
    # ========================================================

    st.divider()

    if resultado["potencial"]:

        indicadores = []

        if resultado["potencial_cliques"]:
            indicadores.append("chance alta em cliques")

        if resultado["potencial_tla"]:
            indicadores.append("chance alta em TLA")

        if resultado["muito_potencial_assinaturas"]:
            indicadores.append("muito potencial de assinaturas")

        elif resultado["potencial_last_click"]:
            indicadores.append("potencial de last click")

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


# ============================================================
# TABELA DE MATÉRIAS DE REFERÊNCIA
# ============================================================

def mostrar_referencias(df_hist):
    """
    Mostra as matérias do histórico usadas como referência.
    (São as mesmas nos dois cenários.)
    """

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

    df_exibir["Similaridade"] = (
        df_exibir["similarity"]
        * 100
    ).round(1)

    if "titulo" in df_exibir.columns:
        df_exibir["Título"] = df_exibir["titulo"]

    elif "title" in df_exibir.columns:
        df_exibir["Título"] = df_exibir["title"]

    peso = peso_no_calculo(df_hist)

    if peso is not None:
        df_exibir["Peso no cálculo"] = peso

    if "cliques" in df_exibir.columns:

        df_exibir["Cliques"] = pd.to_numeric(
            df_exibir["cliques"],
            errors="coerce"
        )

    elif "cliques_gerados" in df_exibir.columns:

        df_exibir["Cliques"] = pd.to_numeric(
            df_exibir["cliques_gerados"],
            errors="coerce"
        )

    if "tempo_leitura" in df_exibir.columns:

        df_exibir["TLA"] = (
            df_exibir["tempo_leitura"]
            .apply(formatar_tla_real)
        )

    if "last_click" in df_exibir.columns:

        df_exibir["Last click"] = (
            pd.to_numeric(
                df_exibir["last_click"],
                errors="coerce"
            )
            .fillna(0)
            .astype(int)
        )

    if "data" in df_exibir.columns:

        df_exibir["Data"] = (
            pd.to_datetime(
                df_exibir["data"],
                errors="coerce"
            )
            .dt.strftime("%d/%m/%Y")
        )

    colunas_desejadas = [
        "Título",
        "Data",
        "Similaridade",
        "Peso no cálculo",
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
        df_exibir[colunas_finais],
        use_container_width=True,
        hide_index=True
    )


# ============================================================
# DIAGNÓSTICO (POUCAS MATÉRIAS SEMELHANTES)
# ============================================================

def mostrar_diagnostico(df_bruto):
    """
    Quando não há matérias semelhantes suficientes, mostra as
    melhores correspondências encontradas mesmo abaixo do limiar.
    """

    diagnostico = df_bruto.copy()

    diagnostico["similarity"] = pd.to_numeric(
        diagnostico["similarity"],
        errors="coerce"
    )

    diagnostico = diagnostico.dropna(
        subset=["similarity"]
    )

    diagnostico = (
        diagnostico
        .sort_values(
            "similarity",
            ascending=False
        )
        .head(10)
        .copy()
    )

    if "titulo" in diagnostico.columns:
        diagnostico["Título"] = diagnostico["titulo"]

    elif "title" in diagnostico.columns:
        diagnostico["Título"] = diagnostico["title"]

    if "data" in diagnostico.columns:

        diagnostico["Data"] = (
            pd.to_datetime(
                diagnostico["data"],
                errors="coerce"
            )
            .dt.strftime("%d/%m/%Y")
        )

    diagnostico["Similaridade"] = (
        diagnostico["similarity"] * 100
    ).round(1)

    # Usa "cliques" (total da matéria), NÃO clique_geral.
    if "cliques" in diagnostico.columns:

        diagnostico["Cliques"] = (
            pd.to_numeric(
                diagnostico["cliques"],
                errors="coerce"
            )
        )

    # Usa "tempo_leitura" (segundos), convertido só para exibir.
    if "tempo_leitura" in diagnostico.columns:

        diagnostico["TLA"] = (
            pd.to_numeric(
                diagnostico["tempo_leitura"],
                errors="coerce"
            )
            .apply(formatar_tla_real)
        )

    if "last_click" in diagnostico.columns:

        diagnostico["Last click"] = (
            pd.to_numeric(
                diagnostico["last_click"],
                errors="coerce"
            )
            .fillna(0)
            .astype(int)
        )

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

    if len(colunas_diagnostico) > 0:

        st.caption(
            "As 10 matérias semanticamente mais "
            "próximas encontradas pelo modelo, "
            "mesmo quando estão abaixo do limiar "
            f"de {SIMILARIDADE_MINIMA:.0%}:"
        )

        st.dataframe(
            diagnostico[colunas_diagnostico],
            use_container_width=True,
            hide_index=True
        )


# ============================================================
# ANÁLISE COMPLETA
# ============================================================

def executar_analise(novo_titulo):
    """
    Roda a análise do título digitado e mostra o resultado.

    Usa "return" para encerrar em caso de problema (em vez de
    st.stop()), para que a assinatura do rodapé apareça sempre.
    """

    # ========================================================
    # VALIDAÇÃO
    # ========================================================

    if not novo_titulo.strip():

        st.warning(
            "Digite um título para realizar a análise."
        )

        return

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

        return

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

            return

    if df_bruto is None or len(df_bruto) == 0:

        st.warning(
            "A busca não retornou nenhuma matéria "
            "do histórico."
        )

        return

    # ========================================================
    # PREPARAÇÃO
    # ========================================================

    df_hist = preparar_historico(
        df_bruto
    )

    if df_hist is None or df_hist.empty:

        st.warning(
            f"Não foram encontradas pelo menos "
            f"{MINIMO_MATCHES} matérias no histórico "
            f"com similaridade de "
            f"{SIMILARIDADE_MINIMA:.0%} ou mais. "
            "Isso inviabiliza a análise."
        )

        mostrar_diagnostico(df_bruto)

        return

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

        return

    # ========================================================
    # AUDIÊNCIA DE REFERÊNCIA (DIA ÚTIL E FIM DE SEMANA)
    # ========================================================

    with st.spinner(
        "Calculando a audiência de referência..."
    ):

        audiencias = (
            obter_audiencias_referencia(
                supabase,
                data_alvo,
                JANELA_MEDIA_MOVEL_DIAS
            )
        )

    if not any(audiencias.values()):

        st.warning(
            "Não foi possível calcular a audiência "
            "de referência para a projeção."
        )

        return

    # ========================================================
    # PROJEÇÃO (UMA POR CENÁRIO)
    # ========================================================

    resultados = {
        tipo_dia: projetar_desempenho(
            resultado_historico,
            audiencia,
        )
        for tipo_dia, audiencia in audiencias.items()
    }

    # ========================================================
    # RESULTADO
    # ========================================================

    st.success(
        f"{len(df_hist)} matérias do histórico "
        f"semelhantes utilizadas na estimativa (as {min(TOP_K, len(df_hist))} "
        "mais parecidas definem o last click)."
    )

    # A aba do dia de hoje abre primeiro; a outra é a simulação.
    for tipo_dia, aba, e_hoje in criar_abas_de_cenario():

        with aba:

            mostrar_cenario(
                tipo_dia,
                e_hoje,
                resultados[tipo_dia],
                audiencias[tipo_dia],
            )

    mostrar_referencias(df_hist)


# ============================================================
# INTERFACE
# ============================================================

st.set_page_config(
    page_title="Força Editorial dos Temas",
    page_icon="📊",
    layout="wide"
)

aplicar_css()

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

    executar_analise(novo_titulo)


# ============================================================
# ASSINATURA
# ============================================================

exibir_assinatura()
