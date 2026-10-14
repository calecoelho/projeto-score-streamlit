"""
Temas quentes da semana.

Mostra o resultado mais recente de tendencias_semanais.py: os
assuntos com maior tempo de leitura médio em cada semana, agrupados
por semelhança entre os títulos.

A métrica é direta: para cada grupo, soma o tempo_leitura das
matérias e divide pelo número de matérias do grupo -- sem nenhuma
normalização ou projeção.

Diferente das outras páginas, esta NÃO atualiza sozinha a cada 30
minutos -- os dados vêm de uma rodada manual do script
tendencias_semanais.py, feita por você sempre que a semana vira.
"""

import pandas as pd
import streamlit as st

from utils import init_clients

from componentes_ui import aplicar_css, exibir_assinatura

st.set_page_config(
    page_title="Temas da semana",
    page_icon="🔥",
    layout="wide",
)

aplicar_css()

supabase, _openai_client = init_clients()

st.title("🔥 Temas quentes da semana")

st.markdown(
    "Os assuntos com maior tempo de leitura médio em cada semana, "
    "agrupados por semelhança entre os títulos."
)

st.caption(
    "⚠️ Esta página **não atualiza sozinha**: os dados vêm de uma "
    "rodada manual do script `tendencias_semanais.py`, feita sempre "
    "que a semana vira."
)

# ------------------------------------------------------------
# CARREGAR A RODADA MAIS RECENTE
# ------------------------------------------------------------

resposta = (
    supabase
    .table("gp_temas_semanais")
    .select("*")
    .order("posicao")
    .execute()
)

linhas = resposta.data or []

if not linhas:

    st.info(
        "Ainda não há nenhuma rodada salva. Rode "
        "`python tendencias_semanais.py` localmente para gerar os "
        "primeiros dados."
    )

    exibir_assinatura()

    st.stop()

df = pd.DataFrame(linhas)

gerado_em = (
    pd.to_datetime(df["gerado_em"], utc=True)
    .max()
    .tz_convert("America/Sao_Paulo")
)

st.caption(f"Última rodada: {gerado_em.strftime('%d/%m/%Y às %H:%M')}")

# ------------------------------------------------------------
# UMA ABA POR SEMANA
# ------------------------------------------------------------

semanas = list(dict.fromkeys(df["semana"]))  # ordem de chegada, sem repetir

abas = st.tabs([f"Semana {s}" for s in semanas])

for semana, aba in zip(semanas, abas):

    with aba:

        df_semana = df[df["semana"] == semana].sort_values("posicao")

        periodo_ini = df_semana["periodo_inicio"].iloc[0]
        periodo_fim = df_semana["periodo_fim"].iloc[0]

        st.caption(f"Período: {periodo_ini} a {periodo_fim}")

        for _, linha in df_semana.iterrows():

            with st.container(border=True):

                col_titulo, col_pos = st.columns([8, 1])

                # O "nome" do grupo é a explicação da IA; se a rodada
                # foi feita com --sem-ia (ou é uma rodada antiga, de
                # antes dessa coluna existir), cai de volta pro título
                # da matéria mais central, só pra nunca ficar vazio.
                explicacao = linha.get("explicacao")
                tem_explicacao = isinstance(explicacao, str) and explicacao.strip()
                nome_grupo = explicacao if tem_explicacao else linha["titulo"]

                with col_titulo:
                    st.markdown(f"### {nome_grupo}")

                with col_pos:
                    st.markdown(f"**#{int(linha['posicao']):02d}**")

                # Range (mín/máx) do grupo: só mostra se a rodada que
                # gerou essa linha já calculava essas colunas (rodadas
                # antigas podem não ter).
                minimo = linha.get("tempo_min_horas")
                maximo = linha.get("tempo_max_horas")

                faixa = ""
                if pd.notna(minimo) and pd.notna(maximo):
                    faixa = f" (varia de {minimo:.1f} h a {maximo:.1f} h dentro do grupo)"

                st.markdown(
                    f"**{linha['tempo_medio_horas']:.1f} h** de tempo de "
                    f"leitura médio{faixa}  ·  {int(linha['n_materias'])} matérias"
                )

                exemplos = linha.get("exemplos") or []

                if isinstance(exemplos, list) and len(exemplos) > 0:

                    with st.expander("Exemplos de matérias deste grupo"):

                        for ex in exemplos:
                            st.write(f"- {ex}")

exibir_assinatura()
