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

import io
import os
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt

###############################################################################
# INTERFACE E BOTÃO DE DOWNLOAD DO CSV DE EXEMPLO
###############################################################################

st.set_page_config(page_title="Modelo Getzen Brasil", layout="centered")
st.title("📊 Inflação Médica – Modelo Getzen Adaptado ao Brasil")

# Botão para baixar o CSV de exemplo que está no repositório
caminho_csv_exemplo = os.path.join(os.path.dirname(__file__), "pib_percapita_brasil.csv")
if os.path.exists(caminho_csv_exemplo):
    with open(caminho_csv_exemplo, "rb") as f:
        dados_exemplo = f.read()
    st.sidebar.download_button(
        label="📥 Baixar CSV de Exemplo (PIB per capita)",
        data=dados_exemplo,
        file_name="pib_percapita_modelo.csv",
        mime="text/csv",
        help="Este é o arquivo de modelo contendo colunas 'Ano' e 'Valor' até 2024."
    )
else:
    st.sidebar.warning("CSV de exemplo não encontrado no repositório.")

###############################################################################
# PARÂMETROS DE ENTRADA (BARRA LATERAL)
###############################################################################

st.sidebar.header("Parâmetros de Entrada")

# Horizonte de projeção em anos
anos_proj = st.sidebar.slider(
    "Anos de Projeção", 10, 100, 60,
    help="Defina o horizonte da projeção atuarial em anos. Ex: 60 anos para planos de longo prazo."
)

# Ano em que a projeção efetiva começa
ano_inicio = 2026

# Ano limite para HCCTR convergir a zero (crescimento médico = crescimento de renda)
ano_limite = st.sidebar.number_input(
    "Ano limite para convergência HCCTR = 0", 2035, 2100, 2060,
    help="Ano a partir do qual se assume que o crescimento médico = crescimento da renda per capita."
)

# Inflação esperada (IPCA/CPI)
inflacao = st.sidebar.number_input(
    "Inflação esperada (CPI)", 0.0, 1.0, 0.035,
    step=0.000001, format="%.6f",
    help="Inflação média anual esperada. Ex: 0.035 representa 3,5%."
)

# Crescimento real da renda per capita (fallback, se não houver CSV)
renda_real = st.sidebar.number_input(
    "Crescimento real da renda per capita", 0.0, 1.0, 0.015,
    step=0.000001, format="%.6f",
    help="Variação real da renda per capita além da inflação. Ex: 0.015 = 1,5%."
)

# Soma de inflação + crescimento real = crescimento projetado da renda per capita
renda_pc_padrao = inflacao + renda_real

# Upload opcional do CSV de PIB per capita (Ano,Valor)
uploaded_file = st.sidebar.file_uploader(
    "📂 Carregar CSV PIB per capita (opcional)", type="csv",
    help="Deve conter colunas: Ano,Valor – onde Valor é o PIB per capita em R$"
)

if uploaded_file:
    try:
        pib_df = pd.read_csv(uploaded_file)
        if not {"Ano", "Valor"}.issubset(pib_df.columns):
            raise ValueError("CSV deve conter as colunas 'Ano' e 'Valor'")
        pib_df["Valor"] = pd.to_numeric(pib_df["Valor"], errors="coerce")
        pib_df = pib_df.dropna()
        pib_df = pib_df.set_index("Ano")
        # Calcular média histórica de crescimento real per capita
        lista_cres_real = []
        for ano in pib_df.index:
            if (ano - 1) in pib_df.index:
                g_nominal = (pib_df.loc[ano, "Valor"] / pib_df.loc[ano - 1, "Valor"]) - 1
                lista_cres_real.append(g_nominal)
        # Como não temos inflação ano a ano no CSV, assumimos que a soma já reflete o nominal
        media_real = np.mean(lista_cres_real)  # aproximação de crescimento real médio
        renda_pc_proj = inflacao + media_real
        st.sidebar.markdown(
            f"<small>⏳ Crescimento real da renda estimado pela média histórica: "
            f"<strong>{media_real:.4%}</strong></small>",
            unsafe_allow_html=True
        )
    except Exception as e:
        st.error(f"Erro ao ler CSV: {e}")
        renda_pc_proj = renda_pc_padrao
else:
    renda_pc_proj = renda_pc_padrao

# Ano em que a transição linear termina (crescimento pleno começa após isso)
ano_transicao_fim = 2030

# Share inicial da saúde no PIB (em % do PIB total)
share_inicial = st.sidebar.number_input(
    "Participação inicial da Saúde no PIB", 0.0, 1.0, 0.096,
    step=0.000001, format="%.6f",
    help="Ex: 0.096 representa 9,6% do PIB total destinado à saúde no início da projeção."
)

# Limite de resistência (share máximo tolerado)
share_resistencia = st.sidebar.number_input(
    "Limite de resistência (share máximo)", 0.0, 1.0, 0.15,
    step=0.000001, format="%.6f",
    help="Ex: 0.15 representa 15% do PIB como teto político-fiscal para despesas com saúde."
)

# Dados históricos de crescimento médico (2021–2024)
g_manual = [
    st.sidebar.number_input("Ano 1 – Crescimento Médico (2021)", 0.0, 1.0, 0.250,
                            step=0.000001, format="%.6f",
                            help="Crescimento médico observado em 2021 (ex: 0.250 = 25,0%)."),
    st.sidebar.number_input("Ano 2 – Crescimento Médico (2022)", 0.0, 1.0, 0.230,
                            step=0.000001, format="%.6f",
                            help="Crescimento médico observado em 2022 (ex: 0.230 = 23,0%)."),
    st.sidebar.number_input("Ano 3 – Crescimento Médico (2023)", 0.0, 1.0, 0.1425,
                            step=0.000001, format="%.6f",
                            help="Crescimento médico observado em 2023 (ex: 0.1425 = 14,25%)."),
    st.sidebar.number_input("Ano 4 – Crescimento Médico (2024)", 0.0, 1.0, 0.1425,
                            step=0.000001, format="%.6f",
                            help="Crescimento médico observado em 2024 (ex: 0.1425 = 14,25%).")
]

# Estimar g_2025 via regressão linear manual (anos 2021–2024)
anos_hist = np.array([2021, 2022, 2023, 2024])
valores_hist = np.array(g_manual)
# Coeficiente angular b = Cov(x,y) / Var(x)
b = np.cov(anos_hist, valores_hist, bias=True)[0, 1] / np.var(anos_hist)
# Intercepto a = média(y) – b * média(x)
a = valores_hist.mean() - b * anos_hist.mean()
# Prever g para 2025
g_2025 = a + b * 2025

###############################################################################
# FUNÇÕES DE SIMULAÇÃO
###############################################################################

def resistencia(share_atual: float, limite: float, k: float = 0.02) -> float:
    """
    Função logística de resistência:
      f(share) = 1 / [1 + exp((share - limite)/k)]
    Quanto mais próximo do limite, mais reduzido será o excesso.
    """
    return 1.0 / (1.0 + np.exp((share_atual - limite) / k))


def simular_projecao(g_medico_final: float):
    """
    Simula a projeção de share, crescimento médico, HCCTR e custo
    ao longo dos anos, dado um valor de crescimento médico pleno g_medico_final.
    Retorna tupla de listas: (share, crescimento_medico, hcctr, custo_acumulado).
    """
    anos = list(range(ano_inicio, ano_inicio + anos_proj))
    crescimento_medico = []
    hcctr = []
    share = [share_inicial]
    custo = [1.0]

    for ano in anos:
        # 1) De 2026 a 2030: interpolar entre g_2025 e g_medico_final
        if ano <= ano_transicao_fim:
            denom = ano_transicao_fim - 2025
            frac = (ano - 2025) / denom if denom != 0 else 1.0
            frac = min(max(frac, 0.0), 1.0)
            g_m = g_2025 + (g_medico_final - g_2025) * frac

        # 2) Acima do ano_limite: g_m = renda per capita projetada (convergência)
        elif ano >= ano_limite:
            g_m = renda_pc_proj

        # 3) Entre 2031 e ano_limite: aplicar resistência
        else:
            excesso = max(g_medico_final - renda_pc_proj, 0.0)
            fator_res = resistencia(share[-1], share_resistencia)
            g_m = renda_pc_proj + excesso * fator_res

        crescimento_medico.append(g_m)
        hcctr.append(g_m - renda_pc_proj)
        custo.append(custo[-1] * (1.0 + g_m))
        share.append(share[-1] * (1.0 + (g_m - renda_pc_proj)))

    return share, crescimento_medico, hcctr, custo


###############################################################################
# DETERMINAÇÃO DE g_medico_final (CRESCIMENTO MÉDICO PLENO)
###############################################################################

# Testar valores de 5% a 12% em 200 passos
intervalo_testes = np.linspace(0.05, 0.12, 200)
best_gmed = renda_pc_proj

for g in intervalo_testes:
    s_sim, _, _, _ = simular_projecao(g)
    # share_sim[-1] = share em (ano_inicio + anos_proj - 1)
    if s_sim[-1] >= share_resistencia:
        best_gmed = g
        break

###############################################################################
# COMPUTAR RESULTADOS FINAIS E MONTAR DATAFRAME
###############################################################################

anos = list(range(ano_inicio, ano_inicio + anos_proj))
crescimento_medico = []
hcctr = []
share = [share_inicial]
custo = [1.0]
debug_data = []

for ano in anos:
    if ano <= ano_transicao_fim:
        denom = ano_transicao_fim - 2025
        frac = (ano - 2025) / denom if denom != 0 else 1.0
        frac = min(max(frac, 0.0), 1.0)
        g_m = g_2025 + (best_gmed - g_2025) * frac
        motivo = "Interpolação 2025–2030"

    elif ano >= ano_limite:
        g_m = renda_pc_proj
        motivo = "Ano limite: crescimento médico = renda"

    else:
        excesso = max(best_gmed - renda_pc_proj, 0.0)
        fator_res = resistencia(share[-1], share_resistencia)
        g_m = renda_pc_proj + excesso * fator_res
        motivo = "Resistência aplicada"

    crescimento_medico.append(g_m)
    hcctr.append(g_m - renda_pc_proj)
    custo.append(custo[-1] * (1.0 + g_m))
    share.append(share[-1] * (1.0 + (g_m - renda_pc_proj)))

    debug_data.append({
        "Ano": ano,
        "Crescimento Médico (%)": g_m * 100,
        "HCCTR (%)": (g_m - renda_pc_proj) * 100,
        "Share PIB (%)": share[-2] * 100,
        "Motivo": motivo
    })

df = pd.DataFrame(debug_data)

###############################################################################
# EXIBIÇÃO DOS RESULTADOS NO STREAMLIT
###############################################################################

# Mostrar o valor estimado de crescimento pleno
st.markdown(
    f"<hr><p><strong>📌 Crescimento Médico Pleno estimado automaticamente:</strong> "
    f"<span style='color:darkblue'>{best_gmed:.4%}</span> ao ano</p>",
    unsafe_allow_html=True
)

# Tabela de projeção
st.subheader("📊 Tabela de Projeção")
st.dataframe(df, use_container_width=True)

# Cálculo de blocos de HCCTR
curto = np.mean(hcctr[:5]) * 100
medio = np.mean(hcctr[5:9]) * 100
longo = np.mean(hcctr[9:]) * 100

st.markdown(f"**HCCTR Curto Prazo (1–5 anos):** {curto:.2f}%")
st.markdown(f"**HCCTR Médio Prazo (6–9 anos):** {medio:.2f}%")
st.markdown(f"**HCCTR Longo Prazo (10+ anos):** {longo:.2f}%")

# Botão de download da tabela final em CSV
csv = df.to_csv(index=False).encode("utf-8")
st.download_button("📥 Baixar CSV", csv, "projecao_getzen.csv", "text/csv")

# Gráfico 1: Projeção do HCCTR
fig, ax = plt.subplots()
ax.plot(df["Ano"], df["HCCTR (%)"], label="HCCTR (%)", marker="o", color="#1f77b4")
ax.axhline(0, color="gray", linestyle="--")
ax.set_xlabel("Ano")
ax.set_ylabel("HCCTR (%)")
ax.set_title("Projeção do HCCTR")
ax.grid(True)
ax.legend()
st.pyplot(fig)

# Gráfico 2: Participação da Saúde no PIB
fig2, ax2 = plt.subplots()
ax2.plot(df["Ano"], df["Share PIB (%)"], color="#ff7f0e", label="Participação da Saúde no PIB", marker="s")
ax2.axhline(share_resistencia * 100, color="red", linestyle="--", label="Limite de Resistência")
ax2.set_xlabel("Ano")
ax2.set_ylabel("Participação no PIB (%)")
ax2.set_title("Participação da Saúde no PIB")
ax2.grid(True)
ax2.legend()
st.pyplot(fig2)

# Gráfico 3: Inflação Médica Acumulada (Fator acumulado do custo)
fig3, ax3 = plt.subplots()
ax3.plot(df["Ano"], [custo[i + 1] for i in range(len(anos))], color="#1f77b4", label="Inflação médica acumulada")
ax3.set_xlabel("Ano")
ax3.set_ylabel("Fator acumulado")
ax3.set_title("Inflação Médica Acumulada")
ax3.grid(True)
ax3.legend()
st.pyplot(fig3)
