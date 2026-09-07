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
