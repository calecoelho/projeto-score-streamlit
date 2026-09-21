"""
Componentes visuais compartilhados por todas as páginas.

Aqui ficam as peças que antes eram copiadas em cada página:

- o estilo (CSS) das páginas;
- a assinatura do rodapé;
- o cartão de métrica: para cliques e TLA mostra a CHANCE de passar
  da meta (verde = acima da média, amarelo = na média, vermelho =
  abaixo); para o last click, verde quando a regra é atingida e
  vermelho quando não é;
- a tabela de matérias históricas;
- as regras de qual aba (dia útil / fim de semana) abre primeiro.
"""

from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from config import (
    ASSINATURA,
    DIA_UTIL,
    FATIA_QUANTIL_PADRAO,
    FIM_DE_SEMANA,
    ROTULOS_TIPO_DIA,
    TIPOS_DIA,
    LAST_CLICK_MIN_MATERIAS,
    LAST_CLICK_MUITO_POTENCIAL,
)

from database import tipo_dia_da_data

from processamento import (
    formatar_numero,
    formatar_tla_real,
)


# ============================================================
# ASSINATURA
# ============================================================

def exibir_assinatura():
    """
    Assinatura no rodapé da página.
    """

    st.divider()

    st.caption(ASSINATURA)


# ============================================================
# ESTILO (CSS)
# ============================================================

CSS_PAGINAS = """
<style>

/* ============================================================
   ÁREA PRINCIPAL
   ============================================================ */

.block-container {
    max-width: 1250px;
    padding-top: 2rem;
    padding-bottom: 4rem;
}

h1 { letter-spacing: -0.035em; }
h2 { letter-spacing: -0.025em; }
h3 { letter-spacing: -0.02em; }


/* ============================================================
   MÉTRICAS (visão geral)
   ============================================================ */

[data-testid="stMetric"] {
    background: rgba(128, 128, 128, 0.055);
    border: 1px solid rgba(128, 128, 128, 0.18);
    padding: 18px 20px;
    border-radius: 14px;
}

[data-testid="stMetricLabel"] {
    font-size: 0.75rem;
    font-weight: 700;
}

[data-testid="stMetricValue"] {
    font-weight: 750;
    letter-spacing: -0.03em;
}


/* ============================================================
   CARTÕES DE CRITÉRIO (verde = atingiu / vermelho = não atingiu)
   ============================================================ */

.score-card {
    border-radius: 14px;
    padding: 16px 18px;
    border: 1.5px solid;
    min-height: 150px;
}

.score-card.ok {
    background: rgba(46, 160, 67, 0.16);
    border-color: rgba(46, 160, 67, 0.80);
}

.score-card.medio {
    background: rgba(230, 160, 20, 0.15);
    border-color: rgba(230, 160, 20, 0.80);
}

.score-card.nao {
    background: rgba(229, 72, 77, 0.13);
    border-color: rgba(229, 72, 77, 0.70);
}

.score-card-topo {
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 6px;
}

.score-card-rotulo {
    font-size: 0.75rem;
    font-weight: 700;
    opacity: 0.85;
}

.score-card-selo {
    font-size: 0.72rem;
    font-weight: 750;
    padding: 2px 10px;
    border-radius: 999px;
    color: #ffffff;
    white-space: nowrap;
}

.score-card.ok    .score-card-selo { background: rgba(38, 140, 58, 0.95); }
.score-card.medio .score-card-selo { background: rgba(176, 116, 0, 0.95); }
.score-card.nao   .score-card-selo { background: rgba(214, 58, 64, 0.95); }

.score-card-valor {
    font-size: 2rem;
    font-weight: 750;
    letter-spacing: -0.03em;
    line-height: 1.2;
    margin-top: 6px;
}

.score-card-linha {
    font-size: 0.8rem;
    opacity: 0.75;
    margin-top: 3px;
}

.score-card-destaque {
    font-size: 0.85rem;
    font-weight: 750;
    margin-top: 8px;
}


/* ============================================================
   OUTROS
   ============================================================ */

[data-testid="stVerticalBlockBorderWrapper"] { border-radius: 16px; }
.stLinkButton { border-radius: 9px; font-weight: 650; }
[data-testid="stExpander"] { border-radius: 12px; }
[data-testid="stDataFrame"] { border-radius: 10px; }

hr {
    margin-top: 1.8rem;
    margin-bottom: 1.8rem;
    opacity: 0.25;
}

.subtle-text { opacity: 0.58; }
.badge-text { font-size: 0.78rem; font-weight: 650; opacity: 0.72; }

@media (max-width: 768px) {
    .block-container {
        padding-top: 1rem;
        padding-left: 1rem;
        padding-right: 1rem;
    }
    h1 { font-size: 1.8rem; }
}

</style>
"""


def aplicar_css():
    st.markdown(CSS_PAGINAS, unsafe_allow_html=True)


# ============================================================
# CARTÃO DE CRITÉRIO (VERDE / VERMELHO)
# ============================================================

NIVEIS = {
    "alta":  ("ok",    "▲ Chance alta"),
    "media": ("medio", "● Chance média"),
    "baixa": ("nao",   "▼ Chance baixa"),
}


def cartao_criterio(
    rotulo,
    valor,
    atingiu=None,
    linhas=(),
    destaque=None,
    selo_ok="✓ Atingiu",
    selo_nao="✗ Não atingiu",
    nivel=None,
):
    """
    Desenha um cartão de métrica.

    Dois modos:

    - Por critério (atingiu=True/False): verde quando atingiu,
      vermelho quando não (usado no last click).
    - Por nível de chance (nivel="alta" / "media" / "baixa"):
      verde, amarelo ou vermelho (usado em cliques e TLA).

    Além da cor, o cartão traz um selo escrito, para que a leitura
    não dependa só da cor.

    Parâmetros:
        rotulo:   nome da métrica (ex.: "Cliques estimados")
        valor:    número já formatado
        atingiu:  True/False (ignorado quando há nivel)
        nivel:    "alta", "media" ou "baixa" (opcional)
        linhas:   textos pequenos abaixo do valor (meta, detalhes)
        destaque: frase em negrito ao final (opcional)
    """

    if nivel in NIVEIS:

        classe, selo = NIVEIS[nivel]

    else:

        classe = "ok" if atingiu else "nao"

        selo = selo_ok if atingiu else selo_nao

    # Atenção: o HTML fica sem indentação/linhas em branco
    # de propósito. O markdown do Streamlit trata linhas
    # indentadas como bloco de código.
    partes = [
        f'<div class="score-card {classe}">',
        '<div class="score-card-topo">',
        f'<span class="score-card-rotulo">{escape(rotulo)}</span>',
        f'<span class="score-card-selo">{escape(selo)}</span>',
        '</div>',
        f'<div class="score-card-valor">{escape(str(valor))}</div>',
    ]

    for linha in linhas:
        partes.append(
            f'<div class="score-card-linha">{escape(linha)}</div>'
        )

    if destaque:
        partes.append(
            f'<div class="score-card-destaque">{escape(destaque)}</div>'
        )

    partes.append('</div>')

    return "".join(partes)


def formatar_chance(chance):
    """
    Chance em porcentagem, arredondada de 5 em 5 pontos: passar
    a ideia de estimativa, não de precisão.
    """

    if chance is None:
        return "-"

    if chance < 0.025:
        return "menos de 5%"

    return f"cerca de {int(round(chance * 20) * 5)}%"


def cartao_chance(rotulo, valor, resultado, chave):
    """
    Cartão de cliques ou de TLA com a chance de a pauta ficar entre
    as melhores do seu tipo de dia (útil ou fim de semana).

    chave: "cliques" ou "tla" (lê chance_*, nivel_*, taxa_base_* e
    limiar_* do resultado).

    A chance vem da FATIA estimada (participação nos cliques do dia),
    então não depende do tamanho da audiência do dia.
    """

    chance = resultado.get(f"chance_{chave}")

    nivel = resultado.get(f"nivel_{chave}")

    taxa_base = resultado.get(f"taxa_base_{chave}")

    quantil = resultado.get("quantil_melhores", FATIA_QUANTIL_PADRAO)

    pct_melhores = int(round((1 - quantil) * 100))

    tipo_dia = ROTULOS_TIPO_DIA.get(resultado.get("tipo_dia"), "")

    if chave == "cliques":

        limiar = resultado.get("limiar_cliques")

        limiar_txt = (
            None if limiar is None
            else f"{formatar_numero(limiar)} cliques"
        )

    else:

        limiar = resultado.get("limiar_tla_horas")

        limiar_txt = (
            None if limiar is None
            else f"{limiar:.0f} h de leitura"
        )

    if nivel not in NIVEIS:
        nivel = "media"

    if chance is None:

        linhas = ["Sem curva de chance calibrada"]

    else:

        linhas = [
            f"Chance de ficar entre as {pct_melhores}% melhores"
            + (f" do {tipo_dia}" if tipo_dia else "")
            + f": {formatar_chance(chance)}",
        ]

        if limiar_txt:
            linhas.append(
                f"Entre as melhores = a partir de ≈ {limiar_txt}"
            )

        linhas.append(
            f"Chance de uma pauta qualquer: {taxa_base:.0%}"
        )

    return cartao_criterio(
        rotulo=rotulo,
        valor=valor,
        nivel=nivel,
        linhas=linhas,
    )


def mostrar_cartao_criterio(*args, **kwargs):
    st.markdown(
        cartao_criterio(*args, **kwargs),
        unsafe_allow_html=True,
    )


def cartao_last_click(resultado):
    """
    Cartão do last click, com a regra nova:

    - Verde ("potencial de last click") quando pelo menos
      LAST_CLICK_MIN_MATERIAS das matérias do histórico tiveram
      last click.
    - O número mostrado é o TOTAL de last clicks dessas matérias.
    - Se o total chega a LAST_CLICK_MUITO_POTENCIAL, aparece o
      destaque "Muito potencial de assinaturas".
    """

    n_historico = int(resultado.get("n_historico", 0) or 0)

    n_com = int(resultado.get("materias_com_last_click", 0) or 0)

    total = resultado.get("total_last_click", 0)

    atingiu = bool(resultado.get("potencial_last_click", False))

    muito = bool(resultado.get("muito_potencial_assinaturas", False))

    return cartao_criterio(
        rotulo="Last click (total no histórico)",
        valor=formatar_numero(total),
        atingiu=atingiu,
        linhas=[
            f"Presente em {n_com} de {n_historico} matérias do histórico",
            (
                f"Meta: last click em {LAST_CLICK_MIN_MATERIAS}+ matérias "
                f"· muito potencial: {LAST_CLICK_MUITO_POTENCIAL}+ no total"
            ),
        ],
        destaque=(
            "⭐ Muito potencial de assinaturas"
            if muito
            else ("Potencial de last click" if atingiu else None)
        ),
        selo_ok="★ Muito potencial" if muito else "✓ Atingiu",
    )


# ============================================================
# TABELA DE MATÉRIAS HISTÓRICAS
# ============================================================

def peso_no_calculo(historico):
    """
    Quanto cada matéria do histórico pesou na estimativa,
    em porcentagem (as matérias somam 100%).

    Retorna None quando o histórico não tem a coluna de peso
    (por exemplo, análises salvas antes desta versão).
    """

    if "peso_final" not in historico.columns:
        return None

    pesos = pd.to_numeric(
        historico["peso_final"],
        errors="coerce"
    ).fillna(0)

    total = pesos.sum()

    if total <= 0:
        return None

    return (pesos / total * 100).round(0).astype(int).astype(str) + "%"


def tabela_historico(historico, key):
    """
    Mostra as matérias históricas semelhantes.

    'key' precisa ser único na página (as duas abas mostram as
    mesmas matérias históricas).
    """

    exibicao = historico.copy()

    if "titulo" in exibicao.columns:
        exibicao["Título"] = exibicao["titulo"]
    elif "title" in exibicao.columns:
        exibicao["Título"] = exibicao["title"]

    if "similarity" in exibicao.columns:
        exibicao["Similaridade"] = exibicao["similarity"].round(3)

    peso = peso_no_calculo(historico)

    if peso is not None:
        exibicao["Peso no cálculo"] = peso

    if "cliques" in exibicao.columns:
        exibicao["Cliques"] = exibicao["cliques"].apply(formatar_numero)

    if "tempo_leitura" in exibicao.columns:
        exibicao["TLA"] = exibicao["tempo_leitura"].apply(formatar_tla_real)

    if "last_click" in exibicao.columns:
        exibicao["Last click"] = exibicao["last_click"].apply(formatar_numero)

    if "data" in exibicao.columns:
        exibicao["Data"] = pd.to_datetime(
            exibicao["data"],
            errors="coerce",
        ).dt.strftime("%d/%m/%Y")

    if "url" in exibicao.columns:
        exibicao["URL"] = exibicao["url"]

    colunas = [
        "Título",
        "Similaridade",
        "Peso no cálculo",
        "Cliques",
        "TLA",
        "Last click",
        "Data",
        "URL",
    ]

    colunas = [c for c in colunas if c in exibicao.columns]

    st.dataframe(
        exibicao[colunas],
        use_container_width=True,
        hide_index=True,
        key=key,
    )


# ============================================================
# ABAS: DIA ÚTIL x FIM DE SEMANA
# ============================================================

ROTULOS_ABA = {
    DIA_UTIL: "📅 Dia útil",
    FIM_DE_SEMANA: "🏖️ Fim de semana",
}

FRASE_CENARIO = {
    DIA_UTIL: "em um dia útil (audiência média de dias úteis)",
    FIM_DE_SEMANA: "em um fim de semana (audiência média de fins de semana)",
}


def tipo_dia_de_hoje():
    """
    Tipo de dia de hoje, no horário de Brasília.
    É a aba que abre primeiro.
    """

    agora = datetime.now(ZoneInfo("America/Sao_Paulo"))

    return tipo_dia_da_data(agora.date())


def criar_abas_de_cenario():
    """
    Cria as duas abas (dia útil / fim de semana), com a aba de HOJE
    sempre em primeiro lugar -- é ela que abre por padrão.

    Retorna uma lista de (tipo_dia, aba, e_hoje).

    Uso:

        for tipo_dia, aba, e_hoje in criar_abas_de_cenario():
            with aba:
                ...
    """

    hoje = tipo_dia_de_hoje()

    ordem = [hoje] + [t for t in TIPOS_DIA if t != hoje]

    rotulos = [
        ROTULOS_ABA[t] + (" · hoje" if t == hoje else "")
        for t in ordem
    ]

    abas = st.tabs(rotulos)

    return [
        (tipo_dia, aba, tipo_dia == hoje)
        for tipo_dia, aba in zip(ordem, abas)
    ]


def aviso_de_simulacao(tipo_dia):
    """
    Aviso mostrado na aba que NÃO é a de hoje, explicando que
    é uma simulação.
    """

    st.info(
        "🔮 **Simulação:** as mesmas pautas, projetadas como se fossem "
        f"publicadas {FRASE_CENARIO[tipo_dia]}."
    )


# ============================================================
# LEGENDA DAS CORES
# ============================================================

LEGENDA_CORES = (
    "Chance de a pauta ficar entre as "
    f"{int(round((1 - FATIA_QUANTIL_PADRAO) * 100))}% melhores do mesmo "
    "tipo de dia (dia útil ou fim de semana): "
    "🟢 alta  ·  🟡 média  ·  🔴 baixa. "
    "É uma pista baseada no histórico, não uma garantia."
)
