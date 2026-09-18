"""
Job de atualização das análises editoriais.

Roda TODO o cálculo pesado que antes acontecia dentro das páginas do
Streamlit (busca de feed, embeddings, busca vetorial no Supabase,
pesos de recência/similaridade) e salva o resultado de cada editoria
em preditor_analises_cache, via cache_utils.salvar_cache().

As páginas do Streamlit passam a apenas LER esse cache -- o usuário
final nunca mais dispara esse processamento.

Cada editoria é calculada para os DOIS cenários de audiência
(dia útil e fim de semana), assim o usuário pode alternar entre as
abas da página sem esperar nenhum cálculo. O histórico semântico de
cada matéria é buscado uma única vez e reaproveitado nos dois cenários.

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
    ROTULOS_TIPO_DIA,
)

from database import (
    gp_preditor_buscar_noticias,
    obter_audiencias_referencia,
)

from processamento import gerar_oportunidades

from cache_utils import salvar_cache

from editorias_config import EDITORIAS

from trends_config import executar_coleta_trends


# ============================================================
# EDITORIAS BASEADAS NO FEED public.news
# ============================================================

def salvar_todos_os_cenarios(
    supabase,
    editoria,
    audiencias,
    resultados_por_cenario,
    feed_total,
    extra=None,
):
    """
    Salva no cache um snapshot para cada cenário
    (dia útil e fim de semana) de uma editoria.
    """

    for tipo_dia, audiencia in audiencias.items():

        potenciais, sem_potencial = resultados_por_cenario[tipo_dia]

        salvar_cache(
            supabase=supabase,
            editoria=editoria,
            tipo_dia=tipo_dia,
            audiencia=audiencia,
            resultados_potenciais=potenciais,
            resultados_sem_potencial=sem_potencial,
            feed_total=feed_total,
            extra=extra,
        )

        print(
            f"[{editoria}/{ROTULOS_TIPO_DIA[tipo_dia]}] "
            f"feed={feed_total} "
            f"oportunidades={len(potenciais)} "
            f"sem_potencial={len(sem_potencial)}"
        )


def processar_editoria_feed(supabase, audiencias, chave):
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

        print(f"[{chave}] nenhuma notícia encontrada no feed.")

    resultados_por_cenario = gerar_oportunidades(
        feed=feed,
        supabase=supabase,
        audiencias=audiencias,
        limite_cliques=cfg["limite_cliques"],
        limite_tla_horas=cfg["limite_tla_horas"],
        pool_size=POOL_SIZE,
    )

    salvar_todos_os_cenarios(
        supabase=supabase,
        editoria=chave,
        audiencias=audiencias,
        resultados_por_cenario=resultados_por_cenario,
        feed_total=len(feed),
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


def processar_trends(supabase, openai_client, audiencias, agora):

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

        print("[trends_social] nenhuma tendência aprovada pelos filtros.")

    resultados_por_cenario = gerar_oportunidades(
        feed=feed,
        supabase=supabase,
        audiencias=audiencias,
        limite_cliques=cfg["limite_cliques"],
        limite_tla_horas=cfg["limite_tla_horas"],
        pool_size=POOL_SIZE,
    )

    salvar_todos_os_cenarios(
        supabase=supabase,
        editoria="trends_social",
        audiencias=audiencias,
        resultados_por_cenario=resultados_por_cenario,
        feed_total=len(feed),
        extra=extra,
    )


# ============================================================
# MAIN
# ============================================================

def main():

    supabase, openai_client = init_clients_job()

    agora = datetime.now(ZoneInfo("America/Sao_Paulo"))
    data_alvo = agora.date()

    todas_audiencias = obter_audiencias_referencia(
        supabase=supabase,
        data_alvo=data_alvo,
        janela_media_movel_dias=JANELA_MEDIA_MOVEL_DIAS,
    )

    # Só seguimos com os cenários que têm audiência calculada.
    audiencias = {
        tipo_dia: audiencia
        for tipo_dia, audiencia in todas_audiencias.items()
        if audiencia is not None
    }

    if not audiencias:
        print(
            "Não foi possível calcular a audiência de referência. "
            "Abortando job sem salvar cache."
        )
        sys.exit(1)

    for tipo_dia, audiencia in todas_audiencias.items():
        if audiencia is None:
            print(
                f"Aviso: sem dados de audiência para o cenário "
                f"'{ROTULOS_TIPO_DIA[tipo_dia]}'. "
                "Esse cenário não será atualizado nesta rodada."
            )

    erros = []

    for chave in ("politica", "mundo", "ciencia_e_saude"):

        try:
            processar_editoria_feed(supabase, audiencias, chave)
        except Exception:
            erros.append(chave)
            traceback.print_exc()

    try:
        processar_trends(supabase, openai_client, audiencias, agora)
    except Exception:
        erros.append("trends_social")
        traceback.print_exc()

    if erros:
        print(f"Editorias com erro nesta rodada: {erros}")
        sys.exit(1)

    print("Todas as análises foram atualizadas com sucesso.")


if __name__ == "__main__":
    main()
