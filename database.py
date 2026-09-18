import pandas as pd
import streamlit as st

from config import (
    DIA_UTIL,
    FIM_DE_SEMANA,
    TIPOS_DIA,
    ROTULOS_TIPO_DIA,
)


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
# DIA ÚTIL x FIM DE SEMANA
# ============================================================

def tipo_dia_da_data(data):
    """
    Diz se uma data é dia útil ou fim de semana.

    Retorna a chave "dia_util" ou "fim_de_semana"
    (as mesmas usadas em config.py).
    """

    if pd.Timestamp(data).weekday() < 5:
        return DIA_UTIL

    return FIM_DE_SEMANA


# ============================================================
# AUDIÊNCIA DE REFERÊNCIA
# ============================================================

def _carregar_serie_audiencia(supabase):
    """
    Lê a série histórica de audiência (gp_timeseries) e deixa
    os tipos das colunas prontos para o cálculo.

    Retorna um DataFrame, ou None se não houver dados válidos.
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

    return ts


def _calcular_audiencia(
    ts,
    data_alvo,
    tipo_dia,
    janela_media_movel_dias
):
    """
    Calcula a audiência média para um tipo de dia
    ("dia_util" ou "fim_de_semana"), olhando apenas os dias
    anteriores à data-alvo dentro da janela definida.
    """

    data_referencia = (
        pd.Timestamp(data_alvo)
        .normalize()
    )

    if tipo_dia == DIA_UTIL:

        ts = ts[
            ts["data"].dt.weekday < 5
        ].copy()

    else:

        ts = ts[
            ts["data"].dt.weekday >= 5
        ].copy()

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

    return {
        "tipo_dia": ROTULOS_TIPO_DIA[tipo_dia],

        "chave_tipo_dia": tipo_dia,

        "clique_geral_medio": float(
            ts["clique_geral"].mean()
        ),

        "tempo_leitura_geral_medio": float(
            ts["tempo_leitura_geral"].mean()
        ),

        "n_dias_referencia": len(ts)
    }


def obter_audiencia_referencia(
    supabase,
    data_alvo,
    janela_media_movel_dias,
    tipo_dia=None
):
    """
    Calcula a audiência média de referência para a data
    da análise.

    A comparação é feita separando:

    - dias úteis
    - fins de semana

    Por padrão, o tipo de dia é o da própria data-alvo.
    Para simular outro cenário (por exemplo, projetar numa
    sexta-feira como se fosse fim de semana), passe
    tipo_dia="fim_de_semana" ou tipo_dia="dia_util".

    São considerados apenas os dias anteriores à data-alvo,
    dentro da janela definida.

    Retorna:
        tipo_dia
        clique_geral_medio
        tempo_leitura_geral_medio
        n_dias_referencia
    """

    ts = _carregar_serie_audiencia(supabase)

    if ts is None:
        return None

    if tipo_dia is None:
        tipo_dia = tipo_dia_da_data(data_alvo)

    return _calcular_audiencia(
        ts,
        data_alvo,
        tipo_dia,
        janela_media_movel_dias
    )


def obter_audiencias_referencia(
    supabase,
    data_alvo,
    janela_media_movel_dias
):
    """
    Calcula a audiência de referência dos DOIS cenários
    (dia útil e fim de semana), lendo a série histórica
    uma única vez.

    Retorna um dicionário:

        {
            "dia_util": {...} ou None,
            "fim_de_semana": {...} ou None,
        }

    O valor é None quando não há dias suficientes daquele
    tipo dentro da janela.
    """

    ts = _carregar_serie_audiencia(supabase)

    if ts is None:
        return {tipo: None for tipo in TIPOS_DIA}

    return {
        tipo: _calcular_audiencia(
            ts,
            data_alvo,
            tipo,
            janela_media_movel_dias
        )
        for tipo in TIPOS_DIA
    }
