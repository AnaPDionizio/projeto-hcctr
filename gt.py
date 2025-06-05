# -*- coding: utf-8 -*-
"""
Modelo Getzen – Versão Brasil (Streamlit / Offline)
--------------------------------------------------
* Projeção inicia em 2026 com base no histórico até 2024.
* Ano de 2025 estimado por regressão linear (2021–2024).
* Projeção futura suavizada até convergir ao crescimento médico pleno.
* 100% offline, exporta CSV e gera gráficos comparativos.
"""

import io
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
from sklearn.linear_model import LinearRegression

###############################################################################
# INTERFACE E ENTRADAS MANUAIS
###############################################################################

st.set_page_config(page_title="Modelo Getzen Brasil", layout="centered")
st.title("📊 Inflação Médica – Modelo Getzen Adaptado ao Brasil")

st.sidebar.header("Parâmetros de Entrada")

anos_proj = st.sidebar.slider("Anos de Projeção", 10, 100, 60, help="Defina o horizonte da projeção atuarial em anos. Ex: 60 anos para planos de longo prazo.")
ano_inicio = 2026
ano_limite = st.sidebar.number_input("Ano limite para convergência HCCTR = 0", 2035, 2100, 2060, help="Ano a partir do qual se assume que o crescimento médico = crescimento da renda per capita.")

inflacao = st.sidebar.number_input("Inflação esperada (CPI)", 0.0, 1.0, 0.035, step=0.000001, format="%.6f", help="Inflação média anual esperada. Ex: 0.035 representa 3,5%.")
renda_real = st.sidebar.number_input("Crescimento real da renda per capita", 0.0, 1.0, 0.015, step=0.000001, format="%.6f", help="Variação real da renda per capita além da inflação. Ex: 0.015 = 1,5%.")
renda_pc_padrao = inflacao + renda_real

uploaded_file = st.sidebar.file_uploader("📂 Carregar CSV PIB per capita (opcional)", type="csv", help="Deve conter colunas: Ano,Valor – onde Valor é o PIB per capita em R$")

if uploaded_file:
    try:
        pib_df = pd.read_csv(uploaded_file)
        if not {'Ano', 'Valor'}.issubset(pib_df.columns):
            raise ValueError("CSV deve conter as colunas 'Ano' e 'Valor'")
        pib_df['Valor'] = pd.to_numeric(pib_df['Valor'], errors='coerce')
        pib_df = pib_df.dropna()
        pib_df = pib_df.set_index('Ano')
        media_real = np.mean([(pib_df.loc[ano, 'Valor'] / pib_df.loc[ano - 1, 'Valor']) - 1 for ano in pib_df.index if ano - 1 in pib_df.index])
        renda_pc_proj = inflacao + media_real
        st.sidebar.markdown(f"<small>⏳ Crescimento real da renda estimado pela média histórica: <strong>{media_real:.4%}</strong></small>", unsafe_allow_html=True)
    except Exception as e:
        st.error(f"Erro ao ler CSV: {e}")
        renda_pc_proj = renda_pc_padrao
else:
    renda_pc_proj = renda_pc_padrao

ano_transicao_fim = 2030
share_inicial = st.sidebar.number_input("Participação inicial da Saúde no PIB", 0.0, 1.0, 0.096, step=0.000001, format="%.6f")
share_resistencia = st.sidebar.number_input("Limite de resistência (share máximo)", 0.0, 1.0, 0.15, step=0.000001, format="%.6f")

g_manual = [
    st.sidebar.number_input("Ano 1 – Crescimento Médico (2021)", 0.0, 1.0, 0.250, step=0.000001, format="%.6f"),
    st.sidebar.number_input("Ano 2 – Crescimento Médico (2022)", 0.0, 1.0, 0.230, step=0.000001, format="%.6f"),
    st.sidebar.number_input("Ano 3 – Crescimento Médico (2023)", 0.0, 1.0, 0.1425, step=0.000001, format="%.6f"),
    st.sidebar.number_input("Ano 4 – Crescimento Médico (2024)", 0.0, 1.0, 0.1425, step=0.000001, format="%.6f")
]

# Estimar g_2025 via regressão linear (anos 2021–2024)
anos_hist = np.array([2021, 2022, 2023, 2024]).reshape(-1, 1)
valores_hist = np.array(g_manual).reshape(-1, 1)
modelo = LinearRegression().fit(anos_hist, valores_hist)
g_2025 = float(modelo.predict([[2025]])[0][0])

###############################################################################
# SIMULAÇÃO COM OTIMIZAÇÃO DE G_MEDICO_FINAL
###############################################################################

def resistencia(share, limite, k=0.02):
    return 1 / (1 + np.exp((share - limite) / k))

def simular_projecao(g_medico_final):
    anos = list(range(ano_inicio, ano_inicio + anos_proj))
    crescimento_medico, hcctr, share, custo = [], [], [share_inicial], [1.0]
    for i, ano in enumerate(anos):
        if ano <= ano_transicao_fim:
            frac = (ano - 2025) / (ano_transicao_fim - 2025)
            frac = min(max(frac, 0), 1)
            g_m = g_2025 + (g_medico_final - g_2025) * frac
        elif ano >= ano_limite:
            g_m = renda_pc_proj
        else:
            excesso = max(g_medico_final - renda_pc_proj, 0)
            g_m = renda_pc_proj + excesso * resistencia(share[-1], share_resistencia)
        crescimento_medico.append(g_m)
        hcctr.append(g_m - renda_pc_proj)
        custo.append(custo[-1] * (1 + g_m))
        share.append(share[-1] * (1 + (g_m - renda_pc_proj)))
    return share, crescimento_medico, hcctr, custo

intervalo_testes = np.linspace(0.05, 0.12, 200)
best_gmed = renda_pc_proj
for g in intervalo_testes:
    s, _, _, _ = simular_projecao(g)
    if s[-1] >= share_resistencia:
        best_gmed = g
        break

anos = list(range(ano_inicio, ano_inicio + anos_proj))
crescimento_medico, hcctr, share, custo, debug_data = [], [], [share_inicial], [1.0], []
for ano in anos:
    if ano <= ano_transicao_fim:
        frac = (ano - 2025) / (ano_transicao_fim - 2025)
        frac = min(max(frac, 0), 1)
        g_m = g_2025 + (best_gmed - g_2025) * frac
        motivo = "Interpolação 2025–2030"
    elif ano >= ano_limite:
        g_m = renda_pc_proj
        motivo = "Ano limite: crescimento médico = renda"
    else:
        excesso = max(best_gmed - renda_pc_proj, 0)
        g_m = renda_pc_proj + excesso * resistencia(share[-1], share_resistencia)
        motivo = "Resistência aplicada"

    crescimento_medico.append(g_m)
    hcctr.append(g_m - renda_pc_proj)
    custo.append(custo[-1] * (1 + g_m))
    share.append(share[-1] * (1 + (g_m - renda_pc_proj)))

    debug_data.append({
        "Ano": ano,
        "Crescimento Médico (%)": g_m * 100,
        "HCCTR (%)": (g_m - renda_pc_proj) * 100,
        "Share PIB (%)": share[-2] * 100,
        "Motivo": motivo
    })

df = pd.DataFrame(debug_data)

st.markdown(f"<hr><p><strong>📌 Crescimento Médico Pleno estimado automaticamente:</strong> <span style='color:darkblue'>{best_gmed:.4%}</span> ao ano</p>", unsafe_allow_html=True)
st.subheader("📊 Tabela de Projeção")
st.dataframe(df, use_container_width=True)

curto = np.mean(hcctr[:5]) * 100
medio = np.mean(hcctr[5:9]) * 100
longo = np.mean(hcctr[9:]) * 100

st.markdown(f"**HCCTR Curto Prazo (1–5 anos):** {curto:.2f}%")
st.markdown(f"**HCCTR Médio Prazo (6–9 anos):** {medio:.2f}%")
st.markdown(f"**HCCTR Longo Prazo (10+ anos):** {longo:.2f}%")

csv = df.to_csv(index=False).encode('utf-8')
st.download_button("📥 Baixar CSV", csv, "projecao_getzen.csv", "text/csv")

fig, ax = plt.subplots()
ax.plot(df["Ano"], df["HCCTR (%)"], label="HCCTR (%)", marker="o")
ax.axhline(0, color="gray", linestyle="--")
ax.set_xlabel("Ano")
ax.set_ylabel("HCCTR (%)")
ax.set_title("Projeção do HCCTR")
ax.grid(True)
ax.legend()
st.pyplot(fig)

fig2, ax2 = plt.subplots()
ax2.plot(df["Ano"], df["Share PIB (%)"], color="orange", label="Participação da Saúde no PIB", marker="s")
ax2.axhline(share_resistencia * 100, color='red', linestyle='--', label='Limite de Resistência')
ax2.set_xlabel("Ano")
ax2.set_ylabel("Participação no PIB (%)")
ax2.set_title("Participação da Saúde no PIB")
ax2.grid(True)
ax2.legend()
st.pyplot(fig2)

fig3, ax3 = plt.subplots()
ax3.plot(df["Ano"], [custo[i+1] for i in range(len(anos))], color="blue", label="Inflação médica acumulada")
ax3.set_xlabel("Ano")
ax3.set_ylabel("Fator acumulado")
ax3.set_title("Inflação Médica Acumulada")
ax3.grid(True)
ax3.legend()
st.pyplot(fig3)
