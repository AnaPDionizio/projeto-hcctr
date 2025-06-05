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

anos_proj = st.sidebar.slider("Anos de Projeção", 10, 100, 60, help="Horizonte da projeção (ex: 60 anos para planos de longo prazo)")
ano_inicio = 2026
ano_limite = st.sidebar.number_input("Ano limite para convergência HCCTR = 0", 2035, 2100, 2060, help="Ano a partir do qual se assume que g_médico = crescimento da renda")

inflacao = st.sidebar.number_input("Inflação esperada (CPI)", 0.0, 1.0, 0.035, step=0.000001, format="%.6f", help="Inflação anual esperada, ex: 0.035 para 3,5%")
renda_real = st.sidebar.number_input("Crescimento real da renda per capita", 0.0, 1.0, 0.015, step=0.000001, format="%.6f", help="Crescimento acima da inflação, ex: 0.015 para 1,5%")
renda_pc = inflacao + renda_real

g_medico_manual = [
    st.sidebar.number_input("Ano 1 – Crescimento Médico", 0.0, 1.0, 0.151, step=0.000001, format="%.6f", help="Ano 1: ex. 0.151 baseado em VCMH"),
    st.sidebar.number_input("Ano 2 – Crescimento Médico", 0.0, 1.0, 0.127, step=0.000001, format="%.6f", help="Ano 2: ex. 0.127 baseado em VCMH"),
    st.sidebar.number_input("Ano 3 – Crescimento Médico", 0.0, 1.0, 0.112, step=0.000001, format="%.6f", help="Ano 3: ex. 0.112 baseado em VCMH"),
    st.sidebar.number_input("Ano 4 – Crescimento Médico", 0.0, 1.0, 0.105, step=0.000001, format="%.6f", help="Ano 4: ex. 0.105 baseado em VCMH"),
]

g_medico_final = st.sidebar.number_input("Crescimento Médico Pleno (após transição)", 0.0, 1.0, 0.080, step=0.000001, format="%.6f", help="Crescimento médico de longo prazo após transição")
ano_transicao_fim = 2030

share_inicial = st.sidebar.number_input("Participação inicial da Saúde no PIB", 0.0, 1.0, 0.096, step=0.000001, format="%.6f")
share_resistencia = st.sidebar.number_input("Limite de resistência (share máximo)", 0.0, 1.0, 0.15, step=0.000001, format="%.6f")

uploaded_file = st.sidebar.file_uploader("📂 Carregar CSV PIB per capita (opcional)", type="csv")

if uploaded_file:
    try:
        pib_df = pd.read_csv(uploaded_file)
        if not {'Ano', 'Valor'}.issubset(pib_df.columns):
            raise ValueError("CSV deve conter as colunas 'Ano' e 'Valor'")
        pib_df['Valor'] = pd.to_numeric(pib_df['Valor'], errors='coerce')
        pib_df = pib_df.dropna()
        pib_df = pib_df.set_index('Ano')
        def get_renda_pc(ano):
            if ano in pib_df.index and ano - 1 in pib_df.index:
                return (pib_df.loc[ano, 'Valor'] / pib_df.loc[ano - 1, 'Valor']) - 1 + inflacao
            return renda_pc
    except Exception as e:
        st.error(f"Erro ao ler CSV: {e}")
        get_renda_pc = lambda ano: renda_pc
else:
    get_renda_pc = lambda ano: renda_pc

###############################################################################
# PROJEÇÃO PRINCIPAL
###############################################################################

def resistencia(share, limite, k=0.02):
    return 1 / (1 + np.exp((share - limite) / k))

anos = list(range(ano_inicio, ano_inicio + anos_proj))
crescimento_medico, hcctr, share, custo, debug_data = [], [], [share_inicial], [1.0], []

for i, ano in enumerate(anos):
    renda_ano = get_renda_pc(ano)
    if i < 4:
        g_m = g_medico_manual[i]
        motivo = "Manual (2019–2022)"
    elif ano <= ano_transicao_fim:
        frac = (ano - 2022) / (ano_transicao_fim - 2022)
        g_m = g_medico_manual[-1] + (g_medico_final - g_medico_manual[-1]) * frac
        motivo = "Transição Linear"
    elif ano >= ano_limite:
        g_m = renda_ano
        motivo = "Ano limite: crescimento médico = renda"
    else:
        excesso = max(g_medico_final - renda_ano, 0)
        g_m = renda_ano + excesso * resistencia(share[-1], share_resistencia)
        motivo = "Resistência aplicada"

    crescimento_medico.append(g_m)
    hcctr.append(g_m - renda_ano)
    custo.append(custo[-1] * (1 + g_m))
    share.append(share[-1] * (1 + (g_m - renda_ano)))

    debug_data.append({
        "Ano": ano,
        "Crescimento Médico (%)": g_m * 100,
        "HCCTR (%)": (g_m - renda_ano) * 100,
        "Share PIB (%)": share[-2] * 100,
        "Motivo": motivo
    })

df = pd.DataFrame(debug_data)

###############################################################################
# RESULTADOS E EXPORTAÇÃO
###############################################################################

st.subheader("📊 Tabela de Projeção")
st.dataframe(df.style.format({
    "Crescimento Médico (%)": "{:.4f}",
    "HCCTR (%)": "{:.4f}",
    "Share PIB (%)": "{:.4f}"
}), use_container_width=True)

curto = np.mean(hcctr[:5]) * 100
medio = np.mean(hcctr[5:9]) * 100
longo = np.mean(hcctr[9:]) * 100

st.markdown(f"**HCCTR Curto Prazo (1–5 anos):** {curto:.4f}%")
st.markdown(f"**HCCTR Médio Prazo (6–9 anos):** {medio:.4f}%")
st.markdown(f"**HCCTR Longo Prazo (10+ anos):** {longo:.4f}%")

csv = df.to_csv(index=False).encode('utf-8')
st.download_button("📥 Baixar CSV", csv, "projecao_getzen_brasil.csv", "text/csv")

xlsx_buffer = io.BytesIO()
try:
    with pd.ExcelWriter(xlsx_buffer, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False)
except ModuleNotFoundError:
    with pd.ExcelWriter(xlsx_buffer) as writer:
        df.to_excel(writer, index=False)
xlsx_buffer.seek(0)
st.download_button("📥 Baixar XLSX", xlsx_buffer, file_name="projecao_getzen_brasil.xlsx")

###############################################################################
# PALETA DE CORES E GRÁFICOS
###############################################################################

plt.rcParams["axes.prop_cycle"] = plt.cycler(color=["#1f77b4", "#ff7f0e"])

st.subheader("📈 Gráficos")

fig1, ax1 = plt.subplots()
ax1.plot(df["Ano"], df["HCCTR (%)"], marker="o", label="HCCTR (%)")
ax1.axhline(0, linestyle="--", color="gray")
ax1.set_xlabel("Ano")
ax1.set_ylabel("HCCTR (%)")
ax1.set_title("Projeção do HCCTR")
ax1.grid(True)
ax1.legend()
st.pyplot(fig1)

fig2, ax2 = plt.subplots()
ax2.plot(df["Ano"], df["Share PIB (%)"], marker="s", label="Participação Saúde no PIB")
ax2.axhline(share_resistencia * 100, color="red", linestyle="--", label="Limite resistência")
ax2.set_xlabel("Ano")
ax2.set_ylabel("Participação no PIB (%)")
ax2.set_title("Participação da Saúde no PIB")
ax2.grid(True)
ax2.legend()
st.pyplot(fig2)

fig3, ax3 = plt.subplots()
ax3.plot(df["Ano"], [custo[i + 1] for i in range(len(anos))], marker="d", label="Inflação Médica Acumulada")
ax3.set_xlabel("Ano")
ax3.set_ylabel("Fator acumulado")
ax3.set_title("Inflação Médica Acumulada")
ax3.grid(True)
ax3.legend()
st.pyplot(fig3)
