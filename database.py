import pandas as pd
import streamlit as st


def _reportar_erro(mensagem):
    """
    Reporta um erro tanto no app Streamlit (caixa vermelha) quanto
    no console -- usado também pelo job_gerar_analises.py, que roda
    fora de uma sessão Streamlit (onde st.error sozinho só geraria
    um aviso silencioso de contexto ausente).
    """

    print(mensagem)

    try:
        st.error(mensagem)
    except Exception:
        pass


# ============================================================
# BUSCAR NOTÍCIAS DO FEED
# ============================================================

def gp_preditor_buscar_noticias(supabase, filtro_url):
    """
    Busca as notícias recentes de uma editoria.

    O filtro da editoria é aplicado no banco, diretamente
    sobre a coluna URL da tabela public.news.

    Parâmetros:
        supabase: cliente Supabase
        filtro_url: expressão regular para filtrar as URLs

    Retorna:
        DataFrame com as notícias encontradas.
    """

    try:

        response = (
            supabase
            .rpc(
                "gp_preditor_buscar_noticias",
                {
                    "filtro_url": filtro_url
                }
            )
            .execute()
        )

        if response.data is None:
            return pd.DataFrame()

        return pd.DataFrame(response.data)

    except Exception as e:

        _reportar_erro(
            f"Erro ao buscar notícias: {e}"
        )

        return pd.DataFrame()


# ============================================================
# BUSCAR HISTÓRICO SEMÂNTICO
# ============================================================

def buscar_historico_gazeta(
    supabase,
    embedding,
    pool_size
):
    """
    Busca no gp_historico as matérias semanticamente
    mais semelhantes ao embedding da notícia atual.

    Importante:
    - Busca um pool maior de candidatos.
    - O filtro de similaridade mínima é feito depois,
      no Python.
    - Não usamos min_similarity no RPC.
    """

    try:

        response = (
            supabase
            .rpc(
                "match_gp_historico",
                {
                    "query_embedding": embedding,
                    "match_count": pool_size
                }
            )
            .execute()
        )

        if response.data is None:
            return pd.DataFrame()

        return pd.DataFrame(response.data)

    except Exception:

        return pd.DataFrame()


# ============================================================
# AUDIÊNCIA DE REFERÊNCIA
# ============================================================

def obter_audiencia_referencia(
    supabase,
    data_alvo,
    janela_media_movel_dias
):
    """
    Calcula a audiência média de referência para a data
    da análise.

    A comparação é feita separando:

    - dias úteis
    - fins de semana

    São considerados apenas os dias anteriores à data-alvo,
    dentro da janela definida.

    Retorna:
        tipo_dia
        clique_geral_medio
        tempo_leitura_geral_medio
        n_dias_referencia
    """

    try:

        resposta = (
            supabase
            .table("gp_timeseries")
            .select(
                "data, clique_geral, tempo_leitura_geral, dia_semana"
            )
            .execute()
        )

    except Exception as e:

        _reportar_erro(
            "Erro ao consultar a série histórica "
            f"de audiência: {e}"
        )

        return None

    if not resposta.data:
        return None

    ts = pd.DataFrame(
        resposta.data
    )

    # --------------------------------------------------------
    # CONVERSÃO DOS TIPOS
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # REMOVER REGISTROS INVÁLIDOS
    # --------------------------------------------------------

    ts = ts.dropna(
        subset=[
            "data",
            "clique_geral",
            "tempo_leitura_geral"
        ]
    ).copy()

    if len(ts) == 0:
        return None

    # --------------------------------------------------------
    # DATA DE REFERÊNCIA
    # --------------------------------------------------------

    data_referencia = (
        pd.Timestamp(data_alvo)
        .normalize()
    )

    weekday = data_referencia.weekday()

    # --------------------------------------------------------
    # SEPARAR DIA ÚTIL / FIM DE SEMANA
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # JANELA TEMPORAL
    # --------------------------------------------------------

    inicio_janela = (
        data_referencia
        - pd.Timedelta(
            days=janela_media_movel_dias
        )
    )

    ts = ts[
        (ts["data"] >= inicio_janela)
        & (ts["data"] < data_referencia)
    ].copy()

    if len(ts) == 0:
        return None

    # --------------------------------------------------------
    # MÉDIAS
    # --------------------------------------------------------

    clique_geral_medio = float(
        ts["clique_geral"].mean()
    )

    tempo_leitura_geral_medio = float(
        ts["tempo_leitura_geral"].mean()
    )

    return {
        "tipo_dia": tipo_dia,

        "clique_geral_medio": (
            clique_geral_medio
        ),

        "tempo_leitura_geral_medio": (
            tempo_leitura_geral_medio
        ),

        "n_dias_referencia": len(ts)
    }