# -*- coding: utf-8 -*-
"""
Modelo Getzen – Versão Brasil (Streamlit / Offline)
--------------------------------------------------
* 100% offline: sem dependência de internet ou chamadas a APIs.
* Usuário informa parâmetros manualmente ou faz upload do CSV.
* Paleta de cores corporativa (azul & laranja).
* Exporta CSV e XLSX.
* Compatível com Python 3.9+ e Streamlit 1.34+.
"""

import io
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt

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

# Upload opcional do PIB per capita
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

# Entradas fixas iniciais
ano_transicao_fim = 2030
share_inicial = st.sidebar.number_input("Participação inicial da Saúde no PIB", 0.0, 1.0, 0.096, step=0.000001, format="%.6f", help="Ex: 0.096 representa 9,6% do PIB total destinado à saúde no início da projeção")
share_resistencia = st.sidebar.number_input("Limite de resistência (share máximo)", 0.0, 1.0, 0.15, step=0.000001, format="%.6f", help="Ex: 0.15 representa 15% do PIB como teto político-fiscal para despesas com saúde")

g_medico_manual = [
    st.sidebar.number_input("Ano 1 – Crescimento Médico", 0.0, 1.0, 0.151, step=0.000001, format="%.6f", help="Crescimento dos custos médicos no 1º ano da projeção (ex: 0.151 = 15,1%)."),
    st.sidebar.number_input("Ano 2 – Crescimento Médico", 0.0, 1.0, 0.127, step=0.000001, format="%.6f", help="Crescimento dos custos médicos no 2º ano da projeção (ex: 0.127 = 12,7%)."),
    st.sidebar.number_input("Ano 3 – Crescimento Médico", 0.0, 1.0, 0.112, step=0.000001, format="%.6f", help="Crescimento dos custos médicos no 3º ano da projeção (ex: 0.112 = 11,2%)."),
    st.sidebar.number_input("Ano 4 – Crescimento Médico", 0.0, 1.0, 0.105, step=0.000001, format="%.6f", help="Crescimento dos custos médicos no 4º ano da projeção (ex: 0.105 = 10,5%)."),
]

###############################################################################
# PROJEÇÃO COM OTIMIZAÇÃO DO CRESCIMENTO MÉDICO PLENO
###############################################################################

def resistencia(share, limite, k=0.02):
    return 1 / (1 + np.exp((share - limite) / k))

def simular_projecao(g_medico_final):
    anos = list(range(ano_inicio, ano_inicio + anos_proj))
    crescimento_medico, hcctr, share, custo = [], [], [share_inicial], [1.0]
    for i, ano in enumerate(anos):
        if i < 4:
            g_m = g_medico_manual[i]
        elif ano <= ano_transicao_fim:
            frac = (ano - ano_inicio - 4) / (ano_transicao_fim - ano_inicio - 4)
            g_m = g_medico_manual[-1] + (g_medico_final - g_medico_manual[-1]) * frac
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
for i, ano in enumerate(anos):
    if i < 4:
        g_m = g_medico_manual[i]
        motivo = f"Manual ({ano_inicio}–{ano_inicio + 3})"
    elif ano <= ano_transicao_fim:
        frac = (ano - ano_inicio - 4) / (ano_transicao_fim - ano_inicio - 4)
        g_m = g_medico_manual[-1] + (best_gmed - g_medico_manual[-1]) * frac
        motivo = "Transição Linear"
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
