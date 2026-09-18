"""
Camada de cache das análises editoriais.

O job (job_gerar_analises.py) roda a cada 30 minutos, calcula as
oportunidades de cada editoria e salva um "retrato" (snapshot) no
Supabase, na tabela preditor_analises_cache -- uma linha por editoria
E por tipo de dia (dia útil / fim de semana), sempre sobrescrita com
o resultado mais recente.

A chave da linha é montada por chave_cache(), por exemplo
"politica__dia_util" e "politica__fim_de_semana". Assim a tabela
continua com a mesma estrutura de antes (não precisa alterar nada
no Supabase).

As páginas do Streamlit (pages/politica.py, pages/mundo.py,
pages/ciencia_e_saude.py, pages/trends_e_social.py) só leem esse
snapshot com carregar_cache(). Elas não fazem mais nenhuma chamada
de embedding, RPC de similaridade ou cálculo de peso -- por isso
ficam muito mais rápidas para o usuário final.

Exceção: pages/calculadora_potencial.py continua calculando na hora,
porque depende de um título digitado pelo usuário.
"""

import numpy as np
import pandas as pd


TABELA_CACHE = "preditor_analises_cache"


def chave_cache(editoria, tipo_dia):
    """
    Monta a chave da linha no cache.

    Exemplo: chave_cache("politica", "dia_util")
             -> "politica__dia_util"
    """

    return f"{editoria}__{tipo_dia}"


# ============================================================
# CONVERSÃO PARA TIPOS SERIALIZÁVEIS EM JSON
# ============================================================

def _to_jsonable(valor):
    """
    Converte tipos numpy/pandas (que o cliente do Supabase não
    sabe serializar) para tipos nativos do Python.
    """

    if isinstance(valor, np.integer):
        return int(valor)

    if isinstance(valor, np.floating):
        valor = float(valor)
        return None if pd.isna(valor) else valor

    if isinstance(valor, np.bool_):
        return bool(valor)

    if isinstance(valor, pd.Timestamp):
        return None if pd.isna(valor) else valor.isoformat()

    if isinstance(valor, float) and pd.isna(valor):
        return None

    return valor


def _serializar_historico(historico):
    """
    Converte o DataFrame 'historico' (matérias semelhantes) em uma
    lista de dicionários pronta para virar JSON. Remove a coluna
    'embedding', que é pesada e não é usada na exibição.
    """

    if historico is None or not hasattr(historico, "empty") or historico.empty:
        return []

    df = historico.copy()

    if "embedding" in df.columns:
        df = df.drop(columns=["embedding"])

    registros = df.to_dict(orient="records")

    return [
        {chave: _to_jsonable(valor) for chave, valor in registro.items()}
        for registro in registros
    ]


def serializar_resultados(resultados):
    """
    Prepara a lista de resultados (saída de gerar_oportunidades) para
    ser salva como JSON: remove o embedding de cada notícia, converte
    o histórico em lista de registros e normaliza os tipos numéricos.
    """

    serializados = []

    for resultado in resultados:

        item = dict(resultado)
        item.pop("embedding", None)
        item["historico"] = _serializar_historico(item.get("historico"))

        item = {
            chave: _to_jsonable(valor)
            for chave, valor in item.items()
        }

        serializados.append(item)

    return serializados


def desserializar_resultados(resultados_json):
    """
    Reconstrói, a partir do JSON salvo no Supabase, o formato que as
    páginas esperam -- incluindo o DataFrame 'historico'.
    """

    if not resultados_json:
        return []

    resultados = []

    for item in resultados_json:
        item = dict(item)
        item["historico"] = pd.DataFrame(item.get("historico") or [])
        resultados.append(item)

    return resultados


# ============================================================
# LEITURA / GRAVAÇÃO NO SUPABASE
# ============================================================

def salvar_cache(
    supabase,
    editoria,
    tipo_dia,
    audiencia,
    resultados_potenciais,
    resultados_sem_potencial,
    feed_total,
    extra=None,
):
    """
    Salva (substitui) o snapshot mais recente de uma editoria
    para um tipo de dia ("dia_util" ou "fim_de_semana").
    Sempre uma linha por editoria + tipo de dia -- upsert por
    'editoria' (que guarda a chave composta, ver chave_cache).
    """

    payload = {
        "editoria": chave_cache(editoria, tipo_dia),
        "gerado_em": pd.Timestamp.now(tz="America/Sao_Paulo").isoformat(),
        "audiencia": audiencia,
        "feed_total": int(feed_total),
        "resultados_potenciais": serializar_resultados(resultados_potenciais),
        "resultados_sem_potencial": serializar_resultados(resultados_sem_potencial),
        "extra": extra or {},
    }

    (
        supabase
        .table(TABELA_CACHE)
        .upsert(payload, on_conflict="editoria")
        .execute()
    )


def carregar_cache(supabase, editoria, tipo_dia):
    """
    Carrega o snapshot mais recente de uma editoria para um
    tipo de dia ("dia_util" ou "fim_de_semana").
    Retorna None se o job ainda não rodou para essa combinação.
    """

    resposta = (
        supabase
        .table(TABELA_CACHE)
        .select("*")
        .eq("editoria", chave_cache(editoria, tipo_dia))
        .limit(1)
        .execute()
    )

    if not resposta.data:
        return None

    linha = resposta.data[0]

    return {
        "gerado_em": linha.get("gerado_em"),
        "audiencia": linha.get("audiencia"),
        "feed_total": linha.get("feed_total", 0),
        "resultados_potenciais": desserializar_resultados(
            linha.get("resultados_potenciais")
        ),
        "resultados_sem_potencial": desserializar_resultados(
            linha.get("resultados_sem_potencial")
        ),
        "extra": linha.get("extra") or {},
    }
