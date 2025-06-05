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
# CONFIGURAÇÕES STREAMLIT
###############################################################################

st.set_page_config(page_title="Modelo Getzen Brasil", layout="centered")
st.title("📊 Inflação Médica – Modelo Getzen Adaptado ao Brasil")

st.sidebar.header("Parâmetros de Entrada")

###############################################################################
# ENTRADAS DO USUÁRIO
###############################################################################

inflacao = st.sidebar.number_input(
    "Inflação esperada (IPCA‑15)", 0.0, 1.0, value=0.035, step=0.001, format="%.3f"
)

renda_real = st.sidebar.number_input(
    "Crescimento real da renda per capita", 0.0, 1.0, value=0.015, step=0.001, format="%.3f"
)

renda_pc = inflacao + renda_real

anos_proj = st.sidebar.slider("Anos de Projeção", 10, 100, 60)
ano_inicio = 2019

ano_limite = st.sidebar.number_input(
    "Ano‑limite para convergência (g_med = renda)", 2030, 2100, 2060
)

# Crescimentos médicos iniciais (VCMH 2021‑2024 como default)
vc_defaults = [0.151, 0.127, 0.112, 0.105]
g_medico_manual: list[float] = []
for i in range(4):
    g_medico_manual.append(
        st.sidebar.number_input(
            f"Ano {i+1} – Crescimento Médico", 0.0, 1.0, value=vc_defaults[i], step=0.001, format="%.3f"
        )
    )

g_medico_final = st.sidebar.number_input(
    "Crescimento Médico Pleno (após transição)", 0.0, 1.0, value=renda_pc + 0.03, step=0.001, format="%.3f"
)

ano_transicao_fim = 2030

share_inicial = st.sidebar.number_input(
    "Participação inicial da Saúde no PIB", 0.0, 1.0, value=0.096, step=0.001, format="%.3f"
)

share_resistencia = st.sidebar.number_input(
    "Limite de resistência (share máximo)", 0.0, 1.0, value=0.15, step=0.001, format="%.3f"
)

###############################################################################
# CARREGAR CSV DE PIB PER CAPITA (OPCIONAL)
###############################################################################

upload = st.sidebar.file_uploader("📂 Carregar CSV PIB per capita (opcional)")
if upload is not None:
    try:
        pib_df = pd.read_csv(upload, sep=";")
        pib_df["V"] = pd.to_numeric(pib_df["V"], errors="coerce")
        pib_df.dropna(inplace=True)
        delta_pib_pc = pib_df["V"].pct_change(periods=10).mean()
        renda_real = delta_pib_pc
        st.sidebar.success("CSV carregado – valores substituídos")
    except Exception as e:
        st.sidebar.error(f"Erro ao ler CSV: {e}")

###############################################################################
# FUNÇÕES DE CÁLCULO
###############################################################################

def resistencia_sigmoide(share_atual: float, limite: float, k: float = 0.02) -> float:
    return 1 / (1 + np.exp((share_atual - limite) / k))

###############################################################################
# LOOP DE PROJEÇÃO
###############################################################################

anos = list(range(ano_inicio, ano_inicio + anos_proj))
crescimento_medico: list[float] = []
hcctr: list[float] = []
share: list[float] = [share_inicial]
custo: list[float] = [1.0]
debug_data: list[dict[str, float | str]] = []

for i, ano in enumerate(anos):
    if i < 4:
        g_m = g_medico_manual[i]
        motivo = "Manual (2019‑2022)"
    elif ano <= ano_transicao_fim:
        frac = (ano - 2022) / (ano_transicao_fim - 2022)
        g_m = g_medico_manual[-1] + (g_medico_final - g_medico_manual[-1]) * frac
        motivo = "Transição linear"
    elif ano >= ano_limite:
        g_m = renda_pc
        motivo = "Ano‑limite: g_med = renda"
    else:
        excesso = max(g_medico_final - renda_pc, 0)
        g_m = renda_pc + excesso * resistencia_sigmoide(share[-1], share_resistencia)
        motivo = "Resistência fiscal"

    crescimento_medico.append(g_m)
    hcctr.append(g_m - renda_pc)
    custo.append(custo[-1] * (1 + g_m))
    share.append(share[-1] * (1 + (g_m - renda_pc)))

    debug_data.append(
        {
            "Ano": ano,
            "Crescimento Médico (%)": g_m * 100,
            "HCCTR (%)": (g_m - renda_pc) * 100,
            "Share PIB (%)": share[-2] * 100,
            "Motivo": motivo,
        }
    )

df = pd.DataFrame(debug_data)

###############################################################################
# EXIBIÇÃO
###############################################################################

st.subheader("📊 Tabela de Projeção")
st.dataframe(df, use_container_width=True)

curto = np.mean(hcctr[:5]) * 100
medio = np.mean(hcctr[5:9]) * 100
longo = np.mean(hcctr[9:]) * 100

st.markdown(f"**HCCTR Curto Prazo (1–5 anos):** {curto:.2f}%")
st.markdown(f"**HCCTR Médio Prazo (6–9 anos):** {medio:.2f}%")
st.markdown(f"**HCCTR Longo Prazo (10+ anos):** {longo:.2f}%")

# Downloads
csv = df.to_csv(index=False).encode("utf-8")
st.download_button("📥 Baixar CSV", csv, "projecao_getzen_brasil.csv", "text/csv")

xlsx_buffer = io.BytesIO()
with pd.ExcelWriter(xlsx_buffer, engine="xlsxwriter") as writer:
    df.to_excel(writer, index=False)
st.download_button(
    "📥 Baixar XLSX",
    xlsx_buffer.getvalue(),
    "projecao_getzen_brasil.xlsx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)

###############################################################################
# GRÁFICOS
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
ax2.plot(df["Ano"], df["Share PIB (%)"], marker="s", label="Saúde/PIB (%)")
ax2.axhline(share_resistencia * 100, color="red", linestyle="--", label="Limite resistência")
ax2.set_xlabel("Ano")
ax2.set_ylabel("Participação no PIB (%)")
ax2.set_title("Participação da Saúde no PIB")
ax2.grid(True)
ax2.legend()
st.pyplot(fig2)

fig3, ax3 = plt.subplots()
ax3.plot(df["Ano"], [custo[i + 1] for i in range(len(anos))], marker="d", label="Inflação médica acumulada")
ax3.set_xlabel("Ano")
ax3.set_ylabel("Fator acumulado")
ax3.set_title("Inflação Médica Acumulada")
ax3.grid(True)
ax3.legend()
st.pyplot(fig3)
