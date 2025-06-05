# -*- coding: utf-8 -*-
"""
Modelo Getzen – Versão Brasil (Streamlit / Offline)
--------------------------------------------------
* Projeção inicia em 2026 com base no histórico até 2024.
* Ano de 2025 estimado por regressão linear manual (2021–2024).
* Projeção futura suavizada até convergir ao crescimento médico pleno.
* Embute um CSV de exemplo no repositório para download direto.
* 100% offline, exporta CSV e gera gráficos comparativos.
"""

import os
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt

# ------------------------------------------------------------------------
# CONFIGURAÇÃO GERAL DA PÁGINA
# ------------------------------------------------------------------------
st.set_page_config(
    page_title="Modelo Getzen Brasil",
    layout="wide",
    page_icon="📈",  # Ícone discreto, sem excesso de clareza
)

# Estilo CSS customizado para um visual mais refinado
st.markdown(
    """
    <style>
        /* Fonte corporativa e espaçamentos */
        .css-18e3th9 {
            padding-top: 2rem;
            padding-bottom: 2rem;
        }
        /* Container principal */
        .main-header {
            font-size: 2.5rem;
            font-weight: 700;
            color: #1F2833;  /* Azul-escuro corporativo */
            margin-bottom: 0.5rem;
        }
        .subheader {
            font-size: 1.1rem;
            color: #444444;
            margin-bottom: 1.5rem;
        }
        /* Cabeçalho da sidebar */
        .sidebar .sidebar-content {
            padding-top: 1.5rem;
        }
        .sidebar-header {
            font-size: 1.5rem;
            font-weight: 600;
            color: #1F2833;
            margin-bottom: 1rem;
        }
        .expander-header {
            font-size: 1.1rem;
            font-weight: 500;
            color: #222222;
        }
        /* Metricas principais */
        .stMetric {
            text-align: center;
        }
    </style>
    """,
    unsafe_allow_html=True
)

# ------------------------------------------------------------------------
# BANNER INSTITUCIONAL (LOGO + TÍTULO)
# ------------------------------------------------------------------------
with st.container():
    col_logo, col_title = st.columns([1, 8])
    with col_logo:
        # Caso haja um arquivo 'logo.png' na pasta, exibe; caso contrário, apenas título
        logo_path = Path(__file__).parent / "logo.png"
        if logo_path.exists():
            st.image(str(logo_path), width=120)
    with col_title:
        st.markdown('<div class="main-header">Inflação Médica – Modelo Getzen Adaptado ao Brasil</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="subheader">Painel para projeções atuariais de HCCTR e share de saúde no PIB, em consonância com melhores práticas corporativas.</div>',
            unsafe_allow_html=True
        )

st.markdown("---")

# ------------------------------------------------------------------------
# SIDEBAR: DADOS DE ENTRADA E DOWNLOAD
# ------------------------------------------------------------------------
st.sidebar.markdown('<div class="sidebar-header">Parâmetros e Recursos</div>', unsafe_allow_html=True)

# DOWNLOAD DE DADOS DE REFERÊNCIA
with st.sidebar.expander("Dados de Referência"):
    path_exemplo = os.path.join(os.path.dirname(__file__), "pib_percapita_brasil.csv")
    if os.path.exists(path_exemplo):
        with open(path_exemplo, "rb") as f:
            exemplo_bytes = f.read()
        st.download_button(
            label="Download: PIB per capita (exemplo)",
            data=exemplo_bytes,
            file_name="pib_percapita_modelo.csv",
            mime="text/csv",
            help="Arquivo de calibração com colunas 'Ano' e 'Valor' (até 2024)."
        )
    else:
        st.warning("Arquivo de exemplo não encontrado.")

# CONFIGURAÇÃO DOS PARÂMETROS ATUARIAIS
with st.sidebar.expander("1. Horizon e Cenários Atuais"):
    st.markdown("##### Horizonte de Projeção")
    anos_proj = st.slider(
        label="Horizonte (anos)",
        min_value=10, max_value=100, value=60, step=1,
        help="Define o horizonte de tempo para projeção atuária (ex.: 60 anos para planos de longo prazo)."
    )

    st.markdown("##### Ano de Início da Projeção")
    ano_inicio = 2026
    st.markdown(f"**Ano efetivo de partida:** {ano_inicio}", unsafe_allow_html=True)

    st.markdown("##### Ano de Convergência de HCCTR")
    ano_limite = st.number_input(
        label="Ano em que HCCTR → 0",
        min_value=2035, max_value=2100, value=2060, step=1,
        help="Ano a partir do qual o crescimento médico converge para o crescimento da renda per capita."
    )

# PARÂMETROS MACROECONÔMICOS
with st.sidebar.expander("2. Inflação e Renda Per Capita"):
    st.markdown("##### Inflação (IPCA/CPI)")
    inflacao = st.number_input(
        label="Inflação Média Projetada",
        min_value=0.000000, max_value=1.000000, value=0.035000,
        step=0.000001, format="%.6f",
        help="Infl ação média anual estimada (ex.: 0.035 = 3,5%)."
    )

    st.markdown("##### Crescimento Real da Renda")
    renda_real = st.number_input(
        label="Crescimento Real da Renda Per Capita",
        min_value=0.000000, max_value=1.000000, value=0.015000,
        step=0.000001, format="%.6f",
        help="Variação real adicional da renda per capita (ex.: 0.015 = 1,5%)."
    )

    renda_pc_padrao = inflacao + renda_real

    st.markdown("##### Carregar Base Externa (Opcional)")
    uploaded_file = st.file_uploader(
        label="CSV: PIB per capita",
        type="csv",
        help="Arquivo com colunas 'Ano' e 'Valor' (PIB per capita em R$)."
    )
    if uploaded_file:
        try:
            pib_df = pd.read_csv(uploaded_file)
            if not {"Ano", "Valor"}.issubset(pib_df.columns):
                raise ValueError("O CSV deve conter as colunas 'Ano' e 'Valor'.")
            pib_df["Valor"] = pd.to_numeric(pib_df["Valor"], errors="coerce")
            pib_df = pib_df.dropna().set_index("Ano")
            lista_cres_real = []
            for ano in pib_df.index:
                if (ano - 1) in pib_df.index:
                    g_nominal = pib_df.loc[ano, "Valor"] / pib_df.loc[ano - 1, "Valor"] - 1
                    lista_cres_real.append(g_nominal)
            media_real = np.mean(lista_cres_real)
            renda_pc_proj = inflacao + media_real
            st.markdown(
                f"<div><small>Crescimento real estimado historicamente: <strong>{media_real:.4%}</strong></small></div>",
                unsafe_allow_html=True
            )
        except Exception as e:
            st.error(f"Falha ao ler CSV de PIB: {e}")
            renda_pc_proj = renda_pc_padrao
    else:
        renda_pc_proj = renda_pc_padrao

# HIPÓTESES HISTÓRICAS DE CRESCIMENTO MÉDICO
with st.sidebar.expander("3. Crescimento Médico (2021–2024)"):
    st.markdown("#### Insira os valores observados:")
    g_manual = [
        st.number_input(
            label="2021 – Crescimento Médico",
            min_value=0.000000, max_value=1.000000, value=0.250000,
            step=0.000001, format="%.6f",
            help="Ex.: 0.250 = 25,0% em 2021."
        ),
        st.number_input(
            label="2022 – Crescimento Médico",
            min_value=0.000000, max_value=1.000000, value=0.230000,
            step=0.000001, format="%.6f",
            help="Ex.: 0.230 = 23,0% em 2022."
        ),
        st.number_input(
            label="2023 – Crescimento Médico",
            min_value=0.000000, max_value=1.000000, value=0.142500,
            step=0.000001, format="%.6f",
            help="Ex.: 0.1425 = 14,25% em 2023."
        ),
        st.number_input(
            label="2024 – Crescimento Médico",
            min_value=0.000000, max_value=1.000000, value=0.142500,
            step=0.000001, format="%.6f",
            help="Ex.: 0.1425 = 14,25% em 2024."
        )
    ]
    # Regressão linear manual para cálculo de g_2025
    anos_hist = np.array([2021, 2022, 2023, 2024])
    valores_hist = np.array(g_manual)
    b = np.cov(anos_hist, valores_hist, bias=True)[0, 1] / np.var(anos_hist)
    a = valores_hist.mean() - b * anos_hist.mean()
    g_2025 = a + b * 2025
    st.markdown(f"**Estimativa g_2025 (regressão linear):** {g_2025:.4%}", unsafe_allow_html=True)

# PARÂMETROS DE SHARE E RESISTÊNCIA POLÍTICO-FISCAL
with st.sidebar.expander("4. Share de Saúde e Resistência"):
    st.markdown("##### Share Inicial")
    share_inicial = st.number_input(
        label="Participação Inicial da Saúde no PIB",
        min_value=0.000000, max_value=1.000000, value=0.096000,
        step=0.000001, format="%.6f",
        help="Ex.: 0.096 = 9,6% do PIB destinado à saúde."
    )

    st.markdown("##### Limite Máximo Tolerado")
    share_resistencia = st.number_input(
        label="Limite de Resistência (Share Máximo)",
        min_value=0.000000, max_value=1.000000, value=0.150000,
        step=0.000001, format="%.6f",
        help="Ex.: 0.15 = 15% do PIB como teto para despesas com saúde."
    )

st.sidebar.markdown("---")
st.sidebar.markdown("© 2025 – Comitê de Modelagem Atuarial")

# ------------------------------------------------------------------------
# FUNÇÕES DE CÁLCULO E SIMULAÇÃO
# ------------------------------------------------------------------------

def resistencia(share_atual: float, limite: float, k: float = 0.02) -> float:
    """
    Função logística de resistência:
      f(share) = 1 / [1 + exp((share - limite)/k)]
    Quando o share se aproxima do limite, a taxa de crescimento adicional diminui gradualmente.
    """
    return 1.0 / (1.0 + np.exp((share_atual - limite) / k))


def simular_projecao(g_medico_final: float):
    """
    Executa a simulação do share de saúde, HCCTR e custo acumulado ao longo do horizonte definido.
    Retorna: (lista_share, lista_crescimento_médico, lista_hcctr, lista_custo_acumulado)
    """
    anos = list(range(ano_inicio, ano_inicio + anos_proj))
    crescimento_medico = []
    hcctr = []
    share = [share_inicial]
    custo = [1.0]

    for ano in anos:
        # Fase de interpolação entre g_2025 e g_medico_final (2026–2030)
        if ano <= 2030:
            denom = 2030 - 2025
            frac = (ano - 2025) / denom if denom != 0 else 1.0
            frac = min(max(frac, 0.0), 1.0)
            g_m = g_2025 + (g_medico_final - g_2025) * frac
        # Convergência absoluta ao crescimento da renda após o ano limite
        elif ano >= ano_limite:
            g_m = renda_pc_proj
        # Aplicação de resistência política-fiscal entre 2031 e ano_limite
        else:
            excesso = max(g_medico_final - renda_pc_proj, 0.0)
            fator_res = resistencia(share[-1], share_resistencia)
            g_m = renda_pc_proj + excesso * fator_res

        crescimento_medico.append(g_m)
        hcctr.append(g_m - renda_pc_proj)
        custo.append(custo[-1] * (1.0 + g_m))
        share.append(share[-1] * (1.0 + (g_m - renda_pc_proj)))

    return share, crescimento_medico, hcctr, custo

# ------------------------------------------------------------------------
# DETERMINAÇÃO DO CRESCIMENTO MÉDICO PLENO
# ------------------------------------------------------------------------
intervalo_testes = np.linspace(0.05, 0.12, 200)
best_gmed = renda_pc_proj

for g in intervalo_testes:
    s_sim, _, _, _ = simular_projecao(g)
    # Verifica o primeiro g que atinja o share de resistência no final do horizonte
    if s_sim[-1] >= share_resistencia:
        best_gmed = g
        break

# ------------------------------------------------------------------------
# COMPILAÇÃO DOS RESULTADOS EM DATAFRAME PARA EXIBIÇÃO
# ------------------------------------------------------------------------
anos_result = list(range(ano_inicio, ano_inicio + anos_proj))
crescimento_medico = []
hcctr = []
share = [share_inicial]
custo = [1.0]
debug_data = []

for ano in anos_result:
    if ano <= 2030:
        denom = 2030 - 2025
        frac = (ano - 2025) / denom if denom != 0 else 1.0
        frac = min(max(frac, 0.0), 1.0)
        g_m = g_2025 + (best_gmed - g_2025) * frac
        motivo = "Interpolação 2025–2030"
    elif ano >= ano_limite:
        g_m = renda_pc_proj
        motivo = "Convergência de Crescimento"
    else:
        excesso = max(best_gmed - renda_pc_proj, 0.0)
        fator_res = resistencia(share[-1], share_resistencia)
        g_m = renda_pc_proj + excesso * fator_res
        motivo = "Resistência Aplicada"

    crescimento_medico.append(g_m)
    hcctr.append(g_m - renda_pc_proj)
    custo.append(custo[-1] * (1.0 + g_m))
    share.append(share[-1] * (1.0 + (g_m - renda_pc_proj)))

    debug_data.append({
        "Ano":                     ano,
        "Crescimento Médico (%)":  g_m * 100,
        "HCCTR (%)":               (g_m - renda_pc_proj) * 100,
        "Share Saúde no PIB (%)":  share[-2] * 100,
        "Motivo da Hipótese":      motivo
    })

df = pd.DataFrame(debug_data)

# ------------------------------------------------------------------------
# EXIBIÇÃO DOS RESULTADOS NO DASHBOARD PRINCIPAL
# ------------------------------------------------------------------------

# Seção: Destaque do crescimento médico pleno
st.markdown("---")
st.markdown(
    f"<div style='font-size:1.2rem; font-weight:600; color:#1F2833;'>"
    f"Crescimento Médico Pleno Estimado: <span style='color:#1F2833;'>{best_gmed:.4%}</span> ao ano"
    f"</div>",
    unsafe_allow_html=True
)

# Seção: Principais indicadores de HCCTR em colunas
curto = np.mean(hcctr[:5]) * 100
medio = np.mean(hcctr[5:9]) * 100
longo = np.mean(hcctr[9:]) * 100

st.markdown("#### Indicadores de HCCTR por Horizonte")
col1, col2, col3 = st.columns(3)
col1.metric(label="HCCTR Curto Prazo (1–5 anos)", value=f"{curto:.2f}%", delta=None)
col2.metric(label="HCCTR Médio Prazo (6–9 anos)", value=f"{medio:.2f}%", delta=None)
col3.metric(label="HCCTR Longo Prazo (10+ anos)", value=f"{longo:.2f}%", delta=None)

# Seção: Tabela de Projeção (com expander para evitar poluição visual)
with st.expander("Exibir Tabela Completa de Projeção"):
    st.dataframe(df, use_container_width=True)

# Seção: Botão de Exportação de CSV
csv_bytes = df.to_csv(index=False).encode("utf-8")
st.download_button(
    label="Exportar Tabela (CSV)",
    data=csv_bytes,
    file_name="projecao_getzen.csv",
    mime="text/csv"
)

# Seção: Gráficos organizados em abas para análise comparativa
st.markdown("---")
st.markdown("### Visualização Gráfica dos Resultados")

tab1, tab2, tab3 = st.tabs([
    "Evolução do HCCTR (%)",
    "Share da Saúde no PIB (%)",
    "Inflação Médica Acumulada"
])

with tab1:
    fig1, ax1 = plt.subplots(figsize=(8, 4))
    ax1.plot(df["Ano"], df["HCCTR (%)"], marker="o", color="#1F77B4", label="HCCTR")
    ax1.axhline(0, color="gray", linestyle="--", linewidth=1)
    ax1.set_xlabel("Ano", fontsize=12)
    ax1.set_ylabel("HCCTR (%)", fontsize=12)
    ax1.set_title("Evolução do HCCTR (%)", fontsize=14, fontweight='600')
    ax1.grid(alpha=0.3)
    ax1.legend()
    st.pyplot(fig1)

with tab2:
    fig2, ax2 = plt.subplots(figsize=(8, 4))
    ax2.plot(df["Ano"], df["Share Saúde no PIB (%)"], marker="s", color="#FF7F0E", label="Share Saúde")
    ax2.axhline(share_resistencia * 100, color="red", linestyle="--", linewidth=1, label="Limite de Resistência")
    ax2.set_xlabel("Ano", fontsize=12)
    ax2.set_ylabel("Share Saúde no PIB (%)", fontsize=12)
    ax2.set_title("Participação da Saúde no PIB ao Longo dos Anos", fontsize=14, fontweight='600')
    ax2.grid(alpha=0.3)
    ax2.legend()
    st.pyplot(fig2)

with tab3:
    fig3, ax3 = plt.subplots(figsize=(8, 4))
    acumulado = [custo[i + 1] for i in range(len(anos_result))]
    ax3.plot(df["Ano"], acumulado, marker="^", color="#1F77B4", label="Acumulado")
    ax3.set_xlabel("Ano", fontsize=12)
    ax3.set_ylabel("Fator Acumulado", fontsize=12)
    ax3.set_title("Inflação Médica Acumulada", fontsize=14, fontweight='600')
    ax3.grid(alpha=0.3)
    ax3.legend()
    st.pyplot(fig3)

# ------------------------------------------------------------------------
# RODAPÉ COM NOTAS INSTITUCIONAIS
# ------------------------------------------------------------------------
st.markdown("---")
st.markdown(
    "<div style='font-size:0.85rem; color:#666666;'>"
    "Painel desenvolvido com base em melhores práticas atuariais e relatórios corporativos. "
    "© 2025 – Equipe de Modelagem Atuarial. Todos os direitos reservados."
    "</div>",
    unsafe_allow_html=True
)
