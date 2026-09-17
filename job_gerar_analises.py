"""
Job de atualização das análises editoriais.

Roda TODO o cálculo pesado que antes acontecia dentro das páginas do
Streamlit (busca de feed, embeddings, busca vetorial no Supabase,
pesos de recência/similaridade) e salva o resultado de cada editoria
em preditor_analises_cache, via cache_utils.salvar_cache().

As páginas do Streamlit passam a apenas LER esse cache -- o usuário
final nunca mais dispara esse processamento.

Pensado para ser executado a cada 30 minutos por um workflow agendado
do GitHub Actions (ver .github/workflows/atualizar-analises.yml),
mas também pode ser rodado manualmente:

    python job_gerar_analises.py

Exceção: pages/calculadora_potencial.py NÃO usa este job -- ela
continua calculando na hora, a partir do título que o usuário digita.
"""

import sys
import traceback
import urllib.parse
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

from job_utils import init_clients_job

from config import (
    POOL_SIZE,
    JANELA_MEDIA_MOVEL_DIAS,
)

from database import (
    gp_preditor_buscar_noticias,
    obter_audiencia_referencia,
)

from processamento import gerar_oportunidades

from cache_utils import salvar_cache

from editorias_config import EDITORIAS

from trends_config import executar_coleta_trends


# ============================================================
# EDITORIAS BASEADAS NO FEED public.news
# ============================================================

def processar_editoria_feed(supabase, audiencia, chave):
    """
    Processa uma editoria cujo feed vem da tabela public.news
    (política, mundo, ciência e saúde).
    """

    cfg = EDITORIAS[chave]

    feed = gp_preditor_buscar_noticias(
        supabase=supabase,
        filtro_url=cfg["filtro_url"],
    )

    if feed.empty:

        salvar_cache(
            supabase=supabase,
            editoria=chave,
            audiencia=audiencia,
            resultados_potenciais=[],
            resultados_sem_potencial=[],
            feed_total=0,
        )

        print(f"[{chave}] nenhuma notícia encontrada no feed.")
        return

    resultados_potenciais, resultados_sem_potencial = gerar_oportunidades(
        feed=feed,
        supabase=supabase,
        audiencia=audiencia,
        limite_cliques=cfg["limite_cliques"],
        limite_tla_horas=cfg["limite_tla_horas"],
        limite_last_clicks=cfg["limite_last_clicks"],
        pool_size=POOL_SIZE,
    )

    salvar_cache(
        supabase=supabase,
        editoria=chave,
        audiencia=audiencia,
        resultados_potenciais=resultados_potenciais,
        resultados_sem_potencial=resultados_sem_potencial,
        feed_total=len(feed),
    )

    print(
        f"[{chave}] feed={len(feed)} "
        f"oportunidades={len(resultados_potenciais)} "
        f"sem_potencial={len(resultados_sem_potencial)}"
    )


# ============================================================
# TRENDS & SOCIAL
# ============================================================

def _preparar_feed_trends(openai_client, agora):
    """
    Reproduz exatamente o que a página trends_e_social.py fazia em
    carregar_e_vetorizar_feed(): coleta o Google Trends, garante
    título/URL/data e gera os embeddings em lote.
    """

    df_aprovados, df_descartados = executar_coleta_trends()

    if df_aprovados.empty:
        return pd.DataFrame(), df_descartados

    df_feed = df_aprovados.copy()

    df_feed["titulo"] = df_feed["titulo_noticia"].apply(
        lambda x: str(x).strip() if (pd.notna(x) and str(x).strip()) else None
    )
    df_feed["titulo"] = df_feed["titulo"].fillna(df_feed["termo"])

    urls = []

    for _, row in df_feed.iterrows():

        link = row.get("link_noticia")
        termo = row.get("termo", "")

        if pd.notna(link) and str(link).strip():
            urls.append(str(link))
        else:
            urls.append(
                "https://www.google.com/search?q="
                + urllib.parse.quote(str(termo))
            )

    df_feed["url"] = urls
    df_feed["source"] = "Google Trends"
    df_feed["published_at"] = df_feed["data_noticia"].fillna(
        agora.strftime("%Y-%m-%d %H:%M:%S")
    )

    textos = df_feed["titulo"].astype(str).tolist()

    response = openai_client.embeddings.create(
        model="text-embedding-3-large",
        input=textos,
        dimensions=1536,
    )

    df_feed["embedding"] = [item.embedding for item in response.data]

    return df_feed, df_descartados


def processar_trends(supabase, openai_client, audiencia, agora):

    cfg = EDITORIAS["trends_social"]

    feed, df_descartados = _preparar_feed_trends(openai_client, agora)

    extra = {
        "descartados": (
            df_descartados.to_dict(orient="records")
            if df_descartados is not None and not df_descartados.empty
            else []
        )
    }

    if feed.empty:

        salvar_cache(
            supabase=supabase,
            editoria="trends_social",
            audiencia=audiencia,
            resultados_potenciais=[],
            resultados_sem_potencial=[],
            feed_total=0,
            extra=extra,
        )

        print("[trends_social] nenhuma tendência aprovada pelos filtros.")
        return

    resultados_potenciais, resultados_sem_potencial = gerar_oportunidades(
        feed=feed,
        supabase=supabase,
        audiencia=audiencia,
        limite_cliques=cfg["limite_cliques"],
        limite_tla_horas=cfg["limite_tla_horas"],
        limite_last_clicks=cfg["limite_last_clicks"],
        pool_size=POOL_SIZE,
    )

    salvar_cache(
        supabase=supabase,
        editoria="trends_social",
        audiencia=audiencia,
        resultados_potenciais=resultados_potenciais,
        resultados_sem_potencial=resultados_sem_potencial,
        feed_total=len(feed),
        extra=extra,
    )

    print(
        f"[trends_social] feed={len(feed)} "
        f"oportunidades={len(resultados_potenciais)} "
        f"sem_potencial={len(resultados_sem_potencial)}"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    supabase, openai_client = init_clients_job()

    agora = datetime.now(ZoneInfo("America/Sao_Paulo"))
    data_alvo = agora.date()

    audiencia = obter_audiencia_referencia(
        supabase=supabase,
        data_alvo=data_alvo,
        janela_media_movel_dias=JANELA_MEDIA_MOVEL_DIAS,
    )

    if audiencia is None:
        print(
            "Não foi possível calcular a audiência de referência. "
            "Abortando job sem salvar cache."
        )
        sys.exit(1)

    erros = []

    for chave in ("politica", "mundo", "ciencia_e_saude"):

        try:
            processar_editoria_feed(supabase, audiencia, chave)
        except Exception:
            erros.append(chave)
            traceback.print_exc()

    try:
        processar_trends(supabase, openai_client, audiencia, agora)
    except Exception:
        erros.append("trends_social")
        traceback.print_exc()

    if erros:
        print(f"Editorias com erro nesta rodada: {erros}")
        sys.exit(1)

    print("Todas as análises foram atualizadas com sucesso.")


if __name__ == "__main__":
    main()
