import sys
import time
import pandas as pd
from trendspy import Trends

sys.stdout.reconfigure(encoding='utf-8')

# ============================================================
# CONFIGURAÇÃO
# ============================================================

GEO = 'BR'
LIMITE_TRENDS = 100
INTERVALO_ENTRE_REQUISICOES = 0.5

# Categoria do Google Trends para esportes
CATEGORIA_ESPORTES = 17


# ============================================================
# TERMOS QUE DEVEM SER EXCLUÍDOS
# ============================================================

TERMOS_ESPORTES = [
    'futebol', 'brasileirão', 'brasileirao', 'libertadores', 'copa do brasil',
    'champions league', 'premier league', 'mundial de clubes', 'nba', 'nfl',
    'nhl', 'mlb', 'f1', 'fórmula 1', 'formula 1', 'fórmula 2', 'formula 2',
    'motogp', 'tênis', 'tenis', 'vôlei', 'volei', 'basquete', 'boxe', 'ufc',
    'mma', 'surfe', 'surf', 'skate', 'atletismo', 'natação', 'natacao',
    'ciclismo', 'automobilismo', 'corrida', 'gp ', 'grande prêmio',
    'grande premio', 'jogo de hoje', 'jogos de hoje', 'placar',
    'resultado do jogo', 'resultado jogo', 'escalação', 'escalacao',
    'onde assistir', 'transmissão', 'transmissao', 'rodada', 'campeonato',
    'classificação', 'classificacao', 'tabela do campeonato',
    'tabela campeonato', 'time', 'times', 'jogador', 'jogadores',
    'treinador', 'técnico', 'tecnico', 'atleta', 'atletas', 'gol', 'gols',
    'partida', 'partidas',
]

TERMOS_LOTERIAS = [
    'loteria', 'lotofacil', 'lotofácil', 'mega-sena', 'megasena', 'quina',
    'lotomania', 'dupla sena', 'duplasena', 'timemania', 'dia de sorte',
    'super sete', 'loteria federal', 'sorteio da caixa', 'resultado da mega',
    'resultado mega', 'resultado da quina', 'resultado quina',
    'resultado lotofácil', 'resultado lotofacil',
]

TERMOS_HOROSCOPO = [
    'horóscopo', 'horoscopo', 'horóscopo do dia', 'horoscopo do dia',
    'signo', 'signos', 'signo de hoje', 'signos de hoje', 'zodíaco',
    'zodiaco', 'astrologia', 'previsão astral', 'previsao astral',
    'mapa astral', 'lua em', 'ascendente',
]

TERMOS_NOVELAS = [
    'novela', 'novelas', 'resumo da novela', 'resumo de novela',
    'capítulo da novela', 'capitulo da novela', 'capítulos da novela',
    'capitulos da novela', 'próximo capítulo', 'proximo capitulo',
    'próximos capítulos', 'proximos capitulos', 'capítulo de hoje',
    'capitulo de hoje', 'quem morre na novela', 'quem morreu na novela',
    'final da novela', 'último capítulo', 'ultimo capitulo',
]

TERMOS_TEMPO_SERVICO = [
    'previsão do tempo', 'previsao do tempo', 'tempo hoje', 'tempo amanhã',
    'tempo amanha', 'tempo nesta semana', 'previsão para hoje',
    'previsao para hoje', 'previsão para amanhã', 'previsao para amanha',
    'previsão para o fim de semana', 'previsao para o fim de semana',
    'como fica o tempo', 'como estará o tempo', 'como estara o tempo',
    'vai chover hoje', 'vai chover amanhã', 'vai chover amanha',
    'temperatura hoje', 'temperatura amanhã', 'temperatura amanha',
    'clima hoje', 'clima amanhã', 'clima amanha', 'meteorologia hoje',
]

TERMOS_OUTROS = [
    'reality show', 'bbb', 'big brother brasil', 'a fazenda',
    'eliminado do bbb', 'eliminada do bbb', 'paredão', 'paredao',
    'quem saiu do bbb', 'quem saiu da fazenda', 'fofoca dos famosos', 'famosos',
]


# ============================================================
# FUNÇÕES
# ============================================================

def normalizar(texto):
    if texto is None:
        return ''
    return str(texto).lower().strip().replace('’', "'")


def encontrar_termo(texto, lista_termos):
    texto = normalizar(texto)
    for termo in lista_termos:
        if normalizar(termo) in texto:
            return termo
    return None


def classificar_conteudo(termo, titulo, topics):
    termo = normalizar(termo)
    titulo = normalizar(titulo)
    texto_completo = f'{termo} {titulo}'.strip()

    # 1. ESPORTES (Evita crash se topics for None)
    if topics and CATEGORIA_ESPORTES in topics:
        return True, 'esportes_categoria'

    encontrado = encontrar_termo(texto_completo, TERMOS_ESPORTES)
    if encontrado:
        return True, f'esporte:{encontrado}'

    # 2. LOTERIAS
    encontrado = encontrar_termo(texto_completo, TERMOS_LOTERIAS)
    if encontrado:
        return True, f'loteria:{encontrado}'

    # 3. HORÓSCOPO / ASTROLOGIA
    encontrado = encontrar_termo(texto_completo, TERMOS_HOROSCOPO)
    if encontrado:
        return True, f'horoscopo:{encontrado}'

    # 4. NOVELAS
    encontrado = encontrar_termo(texto_completo, TERMOS_NOVELAS)
    if encontrado:
        return True, f'novela:{encontrado}'

    # 5. PREVISÃO DO TEMPO
    encontrado = encontrar_termo(texto_completo, TERMOS_TEMPO_SERVICO)
    if encontrado:
        return True, f'tempo_servico:{encontrado}'

    # 6. OUTROS CONTEÚDOS
    encontrado = encontrar_termo(texto_completo, TERMOS_OUTROS)
    if encontrado:
        return True, f'outros:{encontrado}'

    return False, None


def executar_coleta_trends():
    tr = Trends()
    
    print('Buscando tendências do Google Trends...')
    trends = tr.trending_now(geo=GEO)

    registros = []
    descartados = []

    for i, t in enumerate(trends[:LIMITE_TRENDS]):
        termo = t.keyword

        # 1º FILTRO: categorias e termo
        excluir, motivo = classificar_conteudo(
            termo=termo,
            titulo='',
            topics=getattr(t, 'topics', [])
        )

        if excluir:
            descartados.append({
                'termo': termo,
                'motivo': motivo,
                'titulo_noticia': '(Ignorado no 1º filtro - termo/categoria)'
            })
            continue

        # BUSCA NOTÍCIA ASSOCIADA
        titulo = None
        link = None
        data = None

        try:
            tokens = getattr(t, 'news_tokens', [])
            if tokens:
                noticias = tr.trending_now_news_by_ids(tokens, max_news=1)
                if noticias:
                    titulo = getattr(noticias[0], 'title', None)
                    link = getattr(noticias[0], 'url', None)
                    data = getattr(noticias[0], 'time', None)
        except Exception as e:
            print(f'Erro ao buscar notícia para {termo}: {e}')

        # 2º FILTRO: analisa também o título da notícia
        excluir, motivo = classificar_conteudo(
            termo=termo,
            titulo=titulo,
            topics=getattr(t, 'topics', [])
        )

        if excluir:
            descartados.append({
                'termo': termo,
                'motivo': motivo,
                'titulo_noticia': titulo or '(Sem título de notícia)'
            })
            time.sleep(INTERVALO_ENTRE_REQUISICOES)
            continue

        registros.append({
            'termo': termo,
            'titulo_noticia': titulo,
            'link_noticia': link,
            'data_noticia': data,
        })

        time.sleep(INTERVALO_ENTRE_REQUISICOES)

    return pd.DataFrame(registros), pd.DataFrame(descartados)
