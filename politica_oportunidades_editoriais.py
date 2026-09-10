import streamlit as st
import pandas as pd
import numpy as np
import json
from concurrent.futures import (
    ThreadPoolExecutor,
    as_completed,
    TimeoutError as FuturesTimeoutError
)
from utils import init_clients


# =============================================================================
# CONFIGURAÇÃO DA PÁGINA
# =============================================================================

st.set_page_config(
    page_title="Oportunidades - Política",
    page_icon="📰",
    layout="wide"
)

st.title("Pautas que podem render em POLÍTICA")

st.subheader(
    "Confira matérias publicadas em concorrentes e que podem render"
    "em termos de cliques, TLA e assinaturas"
)


# =============================================================================
# CLIENTES
# =============================================================================

try:

    supabase, openai_client = init_clients()

except Exception as e:

    st.error(f"Erro ao inicializar clientes de API: {e}")
    st.stop()


# =============================================================================
# PARÂMETROS
# =============================================================================

MODELO_EMBEDDING = "text-embedding-3-large"

DIMENSOES = 1536

TOP_K = 5

SIMILARIDADE_MINIMA = 0.55

LIMITE_CLIQUES = 2000

LIMITE_TLA_HORAS = 50

LIMITE_LAST_CLICKS = 10

# Quantas buscas históricas rodam ao mesmo tempo.
# Comece baixo (4) e só suba se confirmar que o banco aguenta mais
# carga simultânea sem ficar mais lento — buscas por vetor pesam no
# processador do banco, então "mais threads" nem sempre é mais rápido.
MAX_WORKERS = 4

# Tempo máximo (em segundos) que a página espera pelo lote inteiro de
# buscas. Se esse tempo passar e ainda faltar gente responder, a
# análise segue em frente só com o que já voltou, em vez de travar a
# página indefinidamente.
TIMEOUT_TOTAL_SEGUNDOS = 90


# =============================================================================
# PESOS DE RECÊNCIA
# =============================================================================

PESOS_RECENCIA = [
    1.00,
    0.90,
    0.80,
    0.70,
    0.60
]


# =============================================================================
# CONVERTER EMBEDDING DO SUPABASE PARA LISTA PYTHON
# =============================================================================

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


# =============================================================================
# BUSCAR MATÉRIAS DA ÚLTIMA HORA
# =============================================================================

def buscar_noticias_ultima_hora():

    try:

        response = (
            supabase
            .rpc("buscar_noticias_ultima_hora")
            .execute()
        )

        df = pd.DataFrame(response.data)

        return df

    except Exception as e:

        st.error(
            f"Erro ao buscar matérias da última hora: {e}"
        )

        return pd.DataFrame()


# =============================================================================
# BUSCAR AS 5 MATÉRIAS HISTÓRICAS
#
# IMPORTANTE: esta função roda dentro de threads (ver processar_noticia
# mais abaixo). Por isso ela não pode chamar st.warning/st.error aqui
# dentro — comandos do Streamlit só são seguros a partir da thread
# principal. Se der erro, a função apenas deixa a exceção subir, e quem
# trata isso é o código que chamou.
# =============================================================================

def buscar_historico(embedding):

    response = (
        supabase
        .rpc(
            "match_materias_republica",
            {
                "query_embedding": embedding,
                "match_count": TOP_K
            }
        )
        .execute()
    )

    df = pd.DataFrame(response.data)

    if df.empty:

        return pd.DataFrame()

    if "similarity" in df.columns:

        df["similarity"] = pd.to_numeric(
            df["similarity"],
            errors="coerce"
        )

        df = df[
            df["similarity"] >= SIMILARIDADE_MINIMA
        ].copy()

    return df


# =============================================================================
# MÉDIA PONDERADA
# =============================================================================

def media_ponderada(valores, pesos):

    # -------------------------------------------------------------------
    # Roda a média ponderada em escala logarítmica, não na escala bruta.
    #
    # Motivo: cliques e TLA costumam ter uma matéria "fora da curva" de
    # vez em quando (viralizou, virou capa etc.). Numa média direta,
    # essa matéria sozinha pode puxar o resultado inteiro pra cima. Em
    # escala log, ela continua contando, mas com peso proporcional bem
    # menor — sem precisar descartar nenhuma das 5 matérias.
    #
    # log1p (em vez de log puro) evita erro quando o valor é 0 — coisa
    # que log() sozinho não aceita. expm1 no final é só o caminho de
    # volta pra escala normal (o inverso do log1p).
    # -------------------------------------------------------------------

    if len(valores) == 0:

        return 0

    valores = pd.to_numeric(
        valores,
        errors="coerce"
    )

    pesos = pesos[:len(valores)]

    dados = pd.DataFrame({
        "valor": valores,
        "peso": pesos
    })

    dados = dados.dropna(
        subset=["valor"]
    )

    if dados.empty:

        return 0

    log_valores = np.log1p(dados["valor"])

    media_log = (
        (log_valores * dados["peso"]).sum()
        /
        dados["peso"].sum()
    )

    return np.expm1(media_log)


# =============================================================================
# CALCULAR DESEMPENHO HISTÓRICO
# =============================================================================

def calcular_desempenho(df_hist):

    if df_hist.empty:

        return None

    df_hist = df_hist.head(TOP_K).copy()

    if (
        "data" in df_hist.columns
        and
        "hora" in df_hist.columns
    ):

        try:

            df_hist["_data_hora"] = pd.to_datetime(
                df_hist["data"].astype(str)
                + " "
                + df_hist["hora"].astype(str),
                errors="coerce"
            )

        except Exception:

            df_hist["_data_hora"] = pd.NaT

    else:

        df_hist["_data_hora"] = pd.NaT

    # -------------------------------------------------------------------
    # As 5 matérias já foram escolhidas pela semelhança (na busca via
    # RPC). Aqui elas são reordenadas por recência para decidir o peso
    # de cada uma — ou seja, o peso não segue a semelhança, e sim qual
    # matéria é mais recente. Se a intenção for outra, é só trocar o
    # critério deste sort_values.
    # -------------------------------------------------------------------

    df_hist = df_hist.sort_values(
        "_data_hora",
        ascending=False,
        na_position="last"
    ).reset_index(drop=True)

    pesos = PESOS_RECENCIA[:len(df_hist)]

    cliques = pd.to_numeric(
        df_hist["cliques_gerados"],
        errors="coerce"
    ).fillna(0)

    media_cliques = media_ponderada(
        cliques,
        pesos
    )

    tla_segundos = pd.to_numeric(
        df_hist["tempo_leitura"],
        errors="coerce"
    ).fillna(0)

    media_tla_segundos = media_ponderada(
        tla_segundos,
        pesos
    )

    media_tla_horas = (
        media_tla_segundos / 3600
    )

    last_clicks = pd.to_numeric(
        df_hist["last_click"],
        errors="coerce"
    ).fillna(0)

    total_last_clicks = last_clicks.sum()

    potencial_cliques = (
        media_cliques >= LIMITE_CLIQUES
    )

    potencial_tla = (
        media_tla_horas > LIMITE_TLA_HORAS
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

        "historico": df_hist,
        "media_cliques": media_cliques,
        "media_tla_horas": media_tla_horas,
        "total_last_clicks": total_last_clicks,
        "potencial_cliques": potencial_cliques,
        "potencial_tla": potencial_tla,
        "potencial_assinaturas": potencial_assinaturas,
        "tem_potencial": tem_potencial

    }


# =============================================================================
# PROCESSAR UMA MATÉRIA (roda dentro de uma thread)
#
# Reúne "converter embedding -> buscar histórico -> calcular desempenho"
# numa função só, sem nenhuma chamada a st.*, para poder rodar em
# paralelo com segurança. Sempre devolve um status explicando o que
# aconteceu, em vez de misturar "deu erro" com "não achou nada" — é
# isso que alimenta o diagnóstico no final.
# =============================================================================

def processar_noticia(noticia):

    titulo = noticia.get("title")

    if titulo is None:

        titulo = "Sem título"

    embedding = converter_embedding(
        noticia.get("embedding")
    )

    if embedding is None:

        return {
            "status": "sem_embedding",
            "titulo": titulo
        }

    try:

        df_hist = buscar_historico(embedding)

    except Exception as e:

        return {
            "status": "erro_busca",
            "titulo": titulo,
            "erro": str(e)
        }

    if df_hist.empty:

        return {
            "status": "sem_historico",
            "titulo": titulo
        }

    try:

        resultado = calcular_desempenho(df_hist)

    except Exception as e:

        return {
            "status": "erro_calculo",
            "titulo": titulo,
            "erro": str(e)
        }

    if resultado is None:

        return {
            "status": "sem_historico",
            "titulo": titulo
        }

    return {
        "status": "ok",
        "titulo": titulo,
        "noticia": noticia,
        "resultado": resultado
    }


# =============================================================================
# INICIAR ANÁLISE
# =============================================================================

st.divider()

if st.button(
    "🔎 Analisar oportunidades",
    type="primary",
    use_container_width=True
):

    # =========================================================================
    # 1. BUSCAR MATÉRIAS
    # =========================================================================

    with st.spinner(
        "Buscando matérias publicadas na última hora..."
    ):

        df_noticias = buscar_noticias_ultima_hora()

    if df_noticias.empty:

        st.info(
            "Nenhuma matéria elegível foi encontrada na última hora."
        )

        st.stop()

    st.info(
        f"{len(df_noticias)} matérias encontradas para análise."
    )

    # =========================================================================
    # 2. PROCESSAR EM PARALELO
    #
    # Em vez de esperar uma busca terminar para só então começar a
    # próxima, várias matérias são enviadas ao mesmo tempo. O tempo
    # total passa a depender da busca mais lenta, não da soma de todas.
    # =========================================================================

    oportunidades = []

    total = len(df_noticias)

    progresso = st.progress(0)
    status = st.empty()

    # Atualiza a barra em ~20 passos, não a cada matéria — evita
    # redesenhar a tela sem necessidade quando "total" é grande.
    intervalo_atualizacao = max(1, total // 20)

    contador_sem_embedding = 0
    contador_erro_busca = 0
    contador_erro_calculo = 0
    contador_sem_historico = 0
    contador_com_potencial = 0
    contador_timeout = 0

    erros_amostra = []

    concluidas = 0

    executor = ThreadPoolExecutor(
        max_workers=min(MAX_WORKERS, total)
    )

    futuros = {
        executor.submit(processar_noticia, noticia): noticia
        for _, noticia in df_noticias.iterrows()
    }

    try:

        # "timeout" aqui é o tempo total para o LOTE inteiro, não por
        # matéria. Se estourar, cai no except abaixo em vez de ficar
        # esperando para sempre por uma busca que travou.
        for futuro in as_completed(futuros, timeout=TIMEOUT_TOTAL_SEGUNDOS):

            resultado_item = futuro.result()

            concluidas += 1

            if (
                concluidas % intervalo_atualizacao == 0
                or concluidas == total
            ):

                status.text(
                    f"Analisando {concluidas} de {total}..."
                )

                progresso.progress(
                    concluidas / total
                )

            status_item = resultado_item["status"]

            if status_item == "sem_embedding":

                contador_sem_embedding += 1

            elif status_item == "erro_busca":

                contador_erro_busca += 1

                if len(erros_amostra) < 5:

                    erros_amostra.append(
                        f"{resultado_item['titulo'][:80]}: "
                        f"{resultado_item['erro']}"
                    )

            elif status_item == "erro_calculo":

                contador_erro_calculo += 1

                if len(erros_amostra) < 5:

                    erros_amostra.append(
                        f"{resultado_item['titulo'][:80]}: "
                        f"{resultado_item['erro']}"
                    )

            elif status_item == "sem_historico":

                contador_sem_historico += 1

            elif status_item == "ok":

                resultado = resultado_item["resultado"]
                noticia = resultado_item["noticia"]

                if resultado["tem_potencial"]:

                    contador_com_potencial += 1

                    oportunidades.append({

                        "id": noticia.get("id"),
                        "titulo": resultado_item["titulo"],
                        "url": noticia.get("url"),
                        "source": noticia.get("source"),
                        "published_at": noticia.get("published_at"),
                        "media_cliques": resultado["media_cliques"],
                        "media_tla_horas": resultado["media_tla_horas"],
                        "total_last_clicks": resultado["total_last_clicks"],
                        "potencial_cliques": resultado["potencial_cliques"],
                        "potencial_tla": resultado["potencial_tla"],
                        "potencial_assinaturas": resultado["potencial_assinaturas"],
                        "historico": resultado["historico"]

                    })

    except FuturesTimeoutError:

        # Passou do tempo limite com buscas ainda pendentes. Em vez de
        # travar a página, segue com o que já voltou e avisa quantas
        # ficaram de fora.
        pendentes = [f for f in futuros if not f.done()]

        contador_timeout = len(pendentes)

        status.text(
            f"Tempo limite atingido: {contador_timeout} matéria(s) não "
            f"voltaram do banco a tempo e ficaram de fora desta análise."
        )

    finally:

        # wait=False: não fica esperando as threads presas numa chamada
        # de rede terminarem. Elas podem continuar rodando em segundo
        # plano, mas a página não fica mais refém delas.
        executor.shutdown(wait=False, cancel_futures=True)

    status.empty()
    progresso.empty()

    # =========================================================================
    # 3. DIAGNÓSTICO
    # =========================================================================

    with st.expander(
        "🔧 Diagnóstico da análise"
    ):

        st.write(f"**Matérias encontradas:** {total}")

        st.write(
            f"**Sem embedding válido:** {contador_sem_embedding}"
        )

        st.write(
            f"**Sem correspondência ≥ 55% no histórico:** "
            f"{contador_sem_historico}"
        )

        st.write(
            f"**Falhas ao consultar o histórico (erro técnico, não "
            f"falta de dado):** {contador_erro_busca}"
        )

        st.write(
            f"**Falhas ao calcular o desempenho:** {contador_erro_calculo}"
        )

        if contador_timeout:

            st.write(
                f"**Não voltaram a tempo (timeout de "
                f"{TIMEOUT_TOTAL_SEGUNDOS}s):** {contador_timeout}"
            )

        st.write(
            f"**Com potencial alto:** {contador_com_potencial}"
        )

        if erros_amostra:

            st.caption("Exemplos de erro (até 5):")

            for linha in erros_amostra:

                st.caption(f"• {linha}")

    # =========================================================================
    # 4. RESULTADOS
    # =========================================================================

    st.divider()

    if not oportunidades:

        st.warning(
            "Nenhuma matéria apresentou potencial alto "
            "de cliques, TLA ou assinaturas."
        )

        st.info(
            f"""
            Os critérios atuais são:

            • Cliques: média ponderada ≥ {LIMITE_CLIQUES:,.0f}
            • TLA: média ponderada > {LIMITE_TLA_HORAS} horas
            • Assinaturas: ≥ {LIMITE_LAST_CLICKS} last clicks
            • Similaridade mínima: {SIMILARIDADE_MINIMA * 100:.0f}%
            """
        )

        st.stop()

    def quantidade_potenciais(item):

        return sum([
            item["potencial_cliques"],
            item["potencial_tla"],
            item["potencial_assinaturas"]
        ])

    oportunidades = sorted(
        oportunidades,
        key=quantidade_potenciais,
        reverse=True
    )

    st.subheader(
        f"🎯 {len(oportunidades)} oportunidades editoriais encontradas"
    )

    st.caption(
        "Uma matéria é exibida quando apresenta pelo menos um dos três "
        "sinais de potencial alto. A comparação histórica considera "
        "somente matérias com similaridade mínima de 55%."
    )

    for numero, oportunidade in enumerate(
        oportunidades,
        start=1
    ):

        titulo = oportunidade["titulo"]

        st.markdown("---")

        st.markdown(f"### {numero}. {titulo}")

        if oportunidade["source"]:

            st.caption(f"Fonte: {oportunidade['source']}")

        col1, col2, col3 = st.columns(3)

        with col1:

            st.metric(
                "Média ponderada de cliques",
                f"{oportunidade['media_cliques']:,.0f}"
            )

            if oportunidade["potencial_cliques"]:

                st.success("🚀 Potencial alto de cliques")

            else:

                st.caption("Potencial baixo de cliques")

        with col2:

            st.metric(
                "Média ponderada de TLA",
                f"{oportunidade['media_tla_horas']:.1f} h"
            )

            if oportunidade["potencial_tla"]:

                st.success("⏱️ Potencial alto de TLA")

            else:

                st.caption("Potencial baixo de TLA")

        with col3:

            st.metric(
                "Last clicks",
                f"{oportunidade['total_last_clicks']:.0f}"
            )

            if oportunidade["potencial_assinaturas"]:

                st.success("💰 Potencial alto de assinaturas")

            else:

                st.caption("Potencial baixo de assinaturas")

        if oportunidade["url"]:

            st.caption(oportunidade["url"])

        df_hist = oportunidade["historico"]

        with st.expander(
            f"📚 Ver as {len(df_hist)} matérias históricas usadas na comparação"
        ):

            st.caption(
                "Estas são as matérias históricas que entraram no cálculo "
                "do potencial. A similaridade mínima é de 55%."
            )

            for posicao, (_, historico) in enumerate(
                df_hist.iterrows(),
                start=1
            ):

                similaridade = historico.get("similarity")

                if pd.notna(similaridade):

                    similaridade_texto = f"{float(similaridade) * 100:.1f}%"

                else:

                    similaridade_texto = "N/A"

                titulo_hist = historico.get("titulo", "Sem título")

                cliques_hist = pd.to_numeric(
                    historico.get("cliques_gerados", 0),
                    errors="coerce"
                )

                if pd.isna(cliques_hist):

                    cliques_hist = 0

                tla_hist_segundos = pd.to_numeric(
                    historico.get("tempo_leitura", 0),
                    errors="coerce"
                )

                if pd.isna(tla_hist_segundos):

                    tla_hist_segundos = 0

                tla_hist_horas = float(tla_hist_segundos) / 3600

                last_click_hist = pd.to_numeric(
                    historico.get("last_click", 0),
                    errors="coerce"
                )

                if pd.isna(last_click_hist):

                    last_click_hist = 0

                st.markdown(f"**{posicao}. {titulo_hist}**")

                st.write(
                    f"🔗 **Similaridade:** {similaridade_texto} "
                    f"| 🖱️ **Cliques:** {float(cliques_hist):,.0f} "
                    f"| ⏱️ **TLA:** {tla_hist_horas:.1f} h "
                    f"| 💰 **Last click:** {float(last_click_hist):.0f}"
                )

                if historico.get("url"):

                    st.caption(historico.get("url"))

                if posicao < len(df_hist):

                    st.divider()