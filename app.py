import streamlit as st

# Configuração da aba do navegador
st.set_page_config(
    page_title="IA Editorial",
    page_icon="🧠",
    layout="wide"
)

# CSS para aumentar a fonte e o espaçamento do menu lateral
st.markdown("""
<style>
    [data-testid="stSidebarNav"] a span,
    [data-testid="stSidebarNavLink"] span {
        font-size: 1.1rem !important;
        font-weight: 600 !important;
    }
    [data-testid="stSidebarNav"] a,
    [data-testid="stSidebarNavLink"] {
        padding-top: 6px !important;
        padding-bottom: 6px !important;
    }
</style>
""", unsafe_allow_html=True)

# Mapeia as páginas com títulos personalizados e ícones
p1 = st.Page("pages/instrucoes.py", title="INSTRUÇÕES", icon="🏠")
p2 = st.Page("pages/calculadora_potencial.py", title="CALCULE SEU TÍTULO", icon="🧮")
p3 = st.Page("pages/politica.py", title="POLÍTICA", icon="🏛️")
p4 = st.Page("pages/mundo.py", title="MUNDO", icon="🌎")
p5 = st.Page("pages/ciencia_e_saude.py", title="CIÊNCIA E SAÚDE", icon="🩺")
p6 = st.Page("pages/trends_e_social.py", title="TRENDS & SOCIAL", icon="🔥")
p7 = st.Page("pages/sobre_o_app.py", title="SOBRE O APP", icon="ℹ️")
p8 = st.Page("pages/temas_semanais.py", title="TEMAS DA SEMANA", icon="🗓️")

# Configura e roda o menu lateral
pg = st.navigation([p1, p2, p3, p4, p5, p6, p7, p8])
pg.run()