-- ============================================================
-- Tabela de cache das análises editoriais
-- ============================================================
--
-- Uma linha por editoria (política, mundo, ciencia_e_saude,
-- trends_social), sempre sobrescrita com o snapshot mais recente
-- calculado pelo job job_gerar_analises.py (a cada 30 minutos).
--
-- Rode este script UMA VEZ no SQL Editor do seu projeto Supabase,
-- antes de ativar o workflow do GitHub Actions.

create table if not exists public.preditor_analises_cache (
    editoria               text primary key,
    gerado_em              timestamptz not null default now(),
    audiencia              jsonb,
    feed_total             integer not null default 0,
    resultados_potenciais  jsonb not null default '[]'::jsonb,
    resultados_sem_potencial jsonb not null default '[]'::jsonb,
    extra                  jsonb not null default '{}'::jsonb
);

comment on table public.preditor_analises_cache is
    'Snapshot mais recente da análise de cada editoria do Preditor Editorial. '
    'Sobrescrita a cada 30 min pelo job job_gerar_analises.py. '
    'As páginas do Streamlit só leem esta tabela.';

-- ------------------------------------------------------------
-- RLS (Row Level Security)
-- ------------------------------------------------------------
--
-- Se o seu projeto já usa RLS nas demais tabelas (gp_historico,
-- gp_timeseries etc.), habilite aqui também e libere leitura para
-- a chave usada pelo Streamlit (normalmente a anon/service key
-- configurada em st.secrets). Ajuste a policy conforme o esquema
-- de segurança que você já usa nas outras tabelas do projeto.
--
-- alter table public.preditor_analises_cache enable row level security;
--
-- create policy "Leitura publica do cache"
--     on public.preditor_analises_cache
--     for select
--     using (true);
