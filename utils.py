"""
Funcoes compartilhadas entre as paginas do Preditor Editorial Triplo.
Centraliza conexao com Supabase/OpenAI, geracao de embeddings, calculo de
pesos/classificacao e diagnostico via LLM -- assim as duas paginas usam
exatamente a mesma logica de pontuacao.
"""

import json
import numpy as np
import pandas as pd
import streamlit as st
from supabase import create_client
from openai import OpenAI


@st.cache_resource
def init_clients():
    supabase_url = st.secrets["SUPABASE_URL"]
    supabase_key = st.secrets["SUPABASE_KEY"]
    openai_key = st.secrets["OPENAI_API_KEY"]

    supabase = create_client(supabase_url, supabase_key)
    openai_client = OpenAI(api_key=openai_key)
    return supabase, openai_client


# -----------------------------------------------------------------------------
# EMBEDDINGS E BUSCA
# -----------------------------------------------------------------------------

def gerar_embeddings(openai_client, textos, modelo="text-embedding-3-small"):
    """
    Gera embeddings para uma lista de textos em uma unica chamada
    (mais barato e mais rapido que chamar 1 titulo por vez).
    """
    res = openai_client.embeddings.create(input=textos, model=modelo)
    return [item.embedding for item in res.data]


def buscar_candidatos_por_embedding(supabase, vetor_embedding, pool_size=30):
    """Busca candidatos no Supabase (RPC match_materias) a partir de um embedding ja calculado."""
    rpc_res = supabase.rpc('match_materias', {
        'query_embedding': vetor_embedding,
        'match_count': pool_size
    }).execute()

    if not rpc_res.data:
        return pd.DataFrame()

    return pd.DataFrame(rpc_res.data)


def buscar_candidatos_supabase(supabase, openai_client, novo_titulo, pool_size=30):
    """Gera embedding de um unico titulo e recupera o pool no Supabase via RPC."""
    vetor_titulo = gerar_embeddings(openai_client, [novo_titulo])[0]
    return buscar_candidatos_por_embedding(supabase, vetor_titulo, pool_size=pool_size)


# -----------------------------------------------------------------------------
# CLASSIFICACAO EM 3 FAIXAS
# -----------------------------------------------------------------------------

def classificar_cliques(valor):
    """Fraco: <1000 | Mediano: 1000-3000 | Alto: >3000."""
    if valor < 1000:
        return "Fraco"
    elif valor <= 3000:
        return "Mediano"
    else:
        return "Alto"


def classificar_tempo(valor_horas):
    """Fraco: <10h | Mediano: 10h-50h | Alto: >=50h."""
    if valor_horas < 10:
        return "Fraco"
    elif valor_horas < 50:
        return "Mediano"
    else:
        return "Alto"


def classificar_last_click(valor, meta_minima=5.0):
    """
    Classifica a soma de last_click das 5 materias mais relevantes.
    A escala mudou (antes era media ponderada, agora e soma de 5 materias) --
    'meta_minima' e ajustavel para recalibrar com dados reais.
    """
    return "Meta atingida" if valor >= meta_minima else "Abaixo da meta"


# -----------------------------------------------------------------------------
# CALCULO DE PESOS E METRICAS
# -----------------------------------------------------------------------------

def processar_tres_frentes(df_candidatos, similarity_threshold=0.40, meia_vida_dias=30,
                            expoente_similaridade=2.0, meta_last_click=5.0):
    """
    Aplica filtro de similaridade, recencia exponencial e calcula metricas em horas.
    Cliques e tempo de leitura usam a media ponderada de TODO o pool filtrado.
    Last_click usa a SOMA das 5 materias mais bem rankeadas no calculo ponderado.
    """
    if df_candidatos.empty:
        return None, pd.DataFrame()

    df = df_candidatos.copy()
    df['tempo_leitura_horas'] = df['tempo_leitura'] / 3600.0

    df['sim_filtrada'] = np.where(df['similarity'] >= similarity_threshold, df['similarity'], 0.0)
    df['peso_semantico'] = df['sim_filtrada'] ** expoente_similaridade

    hoje = pd.to_datetime('today')
    df['data_publicacao'] = pd.to_datetime(df['data_publicacao'])
    df['dias_passados'] = (hoje - df['data_publicacao']).dt.days.clip(lower=0)

    lambda_decay = np.log(2) / max(meia_vida_dias, 1)
    df['peso_temporal'] = np.exp(-lambda_decay * df['dias_passados'])

    df['peso_final'] = df['peso_semantico'] * df['peso_temporal']

    soma_pesos = df['peso_final'].sum()
    if soma_pesos == 0:
        return None, df

    cliques_est = int(np.average(df['cliques_gerados'], weights=df['peso_final']))
    tempo_horas_est = round(float(np.average(df['tempo_leitura_horas'], weights=df['peso_final'])), 1)

    df_top5 = df.sort_values(by='peso_final', ascending=False).head(5)
    last_click_est = int(df_top5['last_click'].sum())

    soma_pesos_quad = (df['peso_final'] ** 2).sum()
    tamanho_efetivo_amostra = round((soma_pesos ** 2) / soma_pesos_quad, 1) if soma_pesos_quad > 0 else 0
    cobertura_validos = int((df['peso_final'] > 0).sum())

    classe_cliques = classificar_cliques(cliques_est)
    classe_tempo = classificar_tempo(tempo_horas_est)
    classe_last_click = classificar_last_click(last_click_est, meta_minima=meta_last_click)

    if classe_cliques == "Fraco" or classe_tempo == "Fraco":
        veredito_geral = "atencao"
    elif classe_cliques == "Alto" and classe_tempo == "Alto" and classe_last_click == "Meta atingida":
        veredito_geral = "alto_potencial"
    else:
        veredito_geral = "mediano"

    metricas_estimadas = {
        "cliques_esperados": cliques_est,
        "tempo_horas_esperado": tempo_horas_est,
        "last_click_esperado": last_click_est,
        "classe_cliques": classe_cliques,
        "classe_tempo": classe_tempo,
        "classe_last_click": classe_last_click,
        "veredito_geral": veredito_geral,
        "cobertura_validos": cobertura_validos,
        "tamanho_efetivo_amostra": tamanho_efetivo_amostra,
    }

    return metricas_estimadas, df_top5


def analisar_com_llm(openai_client, novo_titulo, metricas, df_top5):
    """Gera um diagnostico estritamente baseado em fatos do historico."""
    top_3_historico = df_top5[[
        "titulo", "cliques_gerados", "tempo_leitura_horas", "last_click", "data_publicacao", "similarity"
    ]].head(3).to_dict(orient="records")

    prompt = f"""
    Voce e um auditor de dados editoriais focado em metricas frias.
    Justifique as projecoes calculadas para o novo titulo: "{novo_titulo}"

    PROJECOES CALCULADAS:
    - Cliques Projetados: {metricas['cliques_esperados']:,} -> classificacao: {metricas['classe_cliques']} (Fraco: <1000 | Mediano: 1000-3000 | Alto: >3000)
    - Tempo de Leitura Projetado: {metricas['tempo_horas_esperado']} horas -> classificacao: {metricas['classe_tempo']} (Fraco: <10h | Mediano: 10-50h | Alto: >=50h)
    - Soma de last_click das 5 materias mais relevantes: {metricas['last_click_esperado']} -> {metricas['classe_last_click']}

    MATERIAS MAIS SIMILARES NO ACERVO (Top 3 do ranking ponderado):
    {json.dumps(top_3_historico, ensure_ascii=False, default=str)}

    REGRAS RIGIDAS DE RESPOSTA:
    1. PROIBIDO usar adjetivos genericos ou de preenchimento (ex: "promissor", "excelente", "bom", "potencial moderado", "interessante").
    2. CADA DIAGNOSTICO DEVE obrigatoriamente citar o titulo exato de pelo menos uma materia do historico, sua data de publicacao e seu valor numerico real.
    3. Se o valor historico for zero ou muito baixo, declare o fato de forma direta e sem rodeios (ex: "A projecao e zero porque a materia historica X publicou em Y e nao registrou conversoes").

    Retorne ESTRITAMENTE o JSON:
    {{
      "diagnostico_cliques": "<Justificativa factual de cliques citando titulo e numeros do historico>",
      "diagnostico_tempo": "<Justificativa factual de tempo em horas citando titulo e numeros do historico>",
      "diagnostico_last_click": "<Justificativa factual de conversoes citando titulo e numeros do historico>"
    }}
    """

    response = openai_client.chat.completions.create(
        model="gpt-4o",
        response_format={"type": "json_object"},
        temperature=0.1,
        messages=[{"role": "user", "content": prompt}]
    )
    conteudo = json.loads(response.choices[0].message.content)
    chaves_esperadas = ["diagnostico_cliques", "diagnostico_tempo", "diagnostico_last_click"]
    return {chave: conteudo.get(chave, "Diagnostico nao retornado pelo modelo.") for chave in chaves_esperadas}


def exibir_badge(classe):
    """Mostra a classificacao com uma cor: vermelho (Fraco), amarelo (Mediano), verde (Alto)."""
    if classe in ("Alto", "Meta atingida"):
        st.success(f"* {classe}")
    elif classe == "Mediano":
        st.warning(f"* {classe}")
    else:
        st.error(f"* {classe}")
