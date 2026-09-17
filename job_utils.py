"""
Criação de clientes (Supabase/OpenAI) para uso fora do Streamlit.

utils.init_clients() lê st.secrets, o que só funciona dentro de um
app Streamlit rodando. O job (job_gerar_analises.py) roda como um
script Python comum, disparado pelo GitHub Actions -- por isso ele
lê as mesmas credenciais de variáveis de ambiente.

Em produção, configure estes 3 segredos no GitHub Actions
(Settings > Secrets and variables > Actions) com os MESMOS valores
que já estão em st.secrets no Streamlit Cloud:

    SUPABASE_URL
    SUPABASE_KEY
    OPENAI_API_KEY
"""

import os

from supabase import create_client
from openai import OpenAI


def init_clients_job():

    supabase_url = os.environ["SUPABASE_URL"]
    supabase_key = os.environ["SUPABASE_KEY"]
    openai_key = os.environ["OPENAI_API_KEY"]

    supabase = create_client(supabase_url, supabase_key)
    openai_client = OpenAI(api_key=openai_key)

    return supabase, openai_client
