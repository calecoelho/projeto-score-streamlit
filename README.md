# Preditor Editorial Triplo

Aplicação Streamlit para projeção de desempenho editorial usando histórico, embeddings, Supabase e OpenAI.

## Deploy no Streamlit Community Cloud

1. Suba este projeto para um repositório GitHub.
2. Não suba `.streamlit/secrets.toml`.
3. No Streamlit Community Cloud, configure os seguintes Secrets:

```toml
SUPABASE_URL = "..."
SUPABASE_KEY = "..."
OPENAI_API_KEY = "..."
```

4. Selecione `app.py` como arquivo principal.

## Desenvolvimento local

Crie `.streamlit/secrets.toml` localmente com as três credenciais. Esse arquivo está no `.gitignore` e não deve ser versionado.

## Como a análise funciona

- O job `job_gerar_analises.py` roda a cada 30 minutos (GitHub Actions) e calcula tudo para **dois cenários**: dia útil e fim de semana. Cada página mostra os dois em abas; a aba do dia de hoje abre primeiro.
- O cache no Supabase guarda uma linha por editoria **e** por cenário (`politica__dia_util`, `politica__fim_de_semana` etc.). A tabela `preditor_analises_cache` não mudou.
- A estimativa usa as `ESTIMATIVA_K` (20) matérias mais parecidas do histórico, com mais peso para as mais parecidas, e combina os valores com uma média em log (uma matéria gigante não manda sozinha). Esses valores vêm do teste retroativo em R (`backtest_pesos.R`) e ficam em `config.py`.
- Cliques e TLA mostram a **chance de a pauta ficar entre as 25% melhores do mesmo tipo de dia** (útil ou fim de semana), medida pela fatia dos cliques do dia. A estimativa em cliques e horas é corrigida por tipo de dia (`FATOR_TIPO_DIA`). As curvas (`CHANCE_FATIA`) vêm do teste em R (`backtest_pesos.R`, seção 12) e ficam em `config.py`. Refaça o teste a cada trimestre ou semestre e atualize esses números.
- Regra do last click (em `config.py`): pelo menos `LAST_CLICK_MIN_MATERIAS` das matérias do histórico com last click = potencial; total de `LAST_CLICK_MUITO_POTENCIAL` ou mais = muito potencial de assinaturas.
- Depois de publicar esta versão, rode o workflow uma vez na mão (aba **Actions** > **Run workflow**) para as páginas ganharem os dados novos.

## Onde está cada coisa

- `pagina_editorial.py`: desenho das páginas Política, Mundo, Ciência e Saúde e Trends.
- `componentes_ui.py`: estilo, cartões verde/vermelho, abas e assinatura do rodapé.
- `editorias_config.py`: filtros de URL de cada editoria.
- `pages/sobre_o_app.py`: página "Sobre o app" (texto do método; os números vêm do `config.py`, então ela se atualiza quando você recalibra).
