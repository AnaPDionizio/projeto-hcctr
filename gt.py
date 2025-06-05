# -*- coding: utf-8 -*-
"""
Modelo Getzen – Versão Brasil (Streamlit)
----------------------------------------
* Autocontido: roda tanto online (consumindo APIs BCB/IBGE) quanto
  offline (modo manual ou upload de CSV).
* Tratamento explícito de URLError / falha de rede.
* Paleta de cores corporativa (azul & laranja).
* Exporta CSV e XLSX.
* Compatível com Python 3.9+ e Streamlit 1.34+.
"""

from __future__ import annotations

import io
from pathlib import Path
from urllib.error import URLError

import numpy as np
import pandas as pd
import requests
import streamlit as st
import matplotlib.pyplot as plt

###############################################################################
# UTILIDADES DE SÉRIE TEMPORAL
###############################################################################

def serie_bcb(codigo: int, timeout: int = 30) -> pd.DataFrame:
    """Retorna série SGS do Banco Central (formato JSON)."""
    url = f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados?formato=json"
    r = requests.get(url, timeout=timeout)
    r.raise_for_status()
    df = pd.json_normalize(r.json())
    df["data"] = pd.to_datetime(df["data"], dayfirst=True)
    df["valor"] = pd.to_numeric(df["valor"])
    return df.sort_values("data").reset_index(drop=True)


def load_ipca15() -> float | None:
    try:
        ipca = serie_bcb(433)
        return ipca["valor"].tail(120).mean() / 100  # média 10 anos
    except Exception:
        return None


def load_pib_pc() -> pd.DataFrame | None:
    """Tenta baixar PIB per capita real (SIDRA 5932)."""
    url = (
        "https://api.sidra.ibge.gov.br/values/" "t/5932/n1/1/v/99/p/all?formato=csv"
    )
    try:
        df = pd.read_csv(url, sep=";")
        df["V"] = pd.to_numeric(df["V"], errors="coerce")
        return df.dropna()
    except URLError:
        return None
    except Exception:
        return None

###############################################################################
# CONFIGURAÇÕES STREAMLIT
###############################################################################

st.set_page_config(page_title="Modelo Getzen Brasil", layout="centered")
st.title("📊 Inflação Médica – Modelo Getzen Adaptado ao Brasil")

st.sidebar.header("Parâmetros de Entrada")

###############################################################################
# CARREGAMENTO DE DADOS OFICIAIS (OU FALLBACK)
###############################################################################

ipca_long = load_ipca15()
pib_df = load_pib_pc()

defaul_infl = round(ipca_long, 4) if ipca_long else 0.035
if pib_df is not None and not pib_df.empty:
    delta_pib_pc = pib_df["V"].pct_change(periods=10).mean()
else:
    delta_pib_pc = 0.015  # fallback média histórica

defaul_renda = round(delta_pib_pc, 3)

usar_oficiais_default = bool(ipca_long and pib_df is not None)

usar_oficiais = st.sidebar.checkbox("Usar dados oficiais 🇧🇷", value=usar_oficiais_default)

###############################################################################
# ENTRADAS DO USUÁRIO
###############################################################################

inflacao = st.sidebar.number_input(
    "Inflação esperada (IPCA‑15)",
    0.0,
    1.0,
    value=defaul_infl if usar_oficiais else 0.02,
    step=0.001,
    format="%.3f",
)

renda_real = st.sidebar.number_input(
    "Crescimento real da renda per capita",
    0.0,
    1.0,
    value=defaul_renda if usar_oficiais else 0.02,
    step=0.001,
    format="%.3f",
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
            f"Ano {i+1} – Crescimento Médico",
            0.0,
            1.0,
            value=vc_defaults[i] if usar_oficiais else 0.02,
            step=0.001,
            format="%.3f",
        )
    )

g_medico_final = st.sidebar.number_input(
    "Crescimento Médico Pleno (após transição)",
    0.0,
    1.0,
    value=renda_pc + 0.03 if usar_oficiais else 0.061,
    step=0.001,
    format="%.3f",
)

ano_transicao_fim = 2030

share_inicial = st.sidebar.number_input(
    "Participação inicial da Saúde no PIB",
    0.0,
    1.0,
    value=0.096 if usar_oficiais else 0.20,
    step=0.001,
    format="%.3f",
)

share_resistencia = st.sidebar.number_input(
    "Limite de resistência (share máximo)",
    0.0,
    1.0,
    value=0.15 if usar_oficiais else 0.25,
    step=0.001,
    format="%.3f",
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
    """Fator entre 0 e 1 que reduz excesso quando share→limite."""
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
    writer.close()
st.download_button(
    "📥 Baixar XLSX",
    xlsx_buffer.getvalue(),
    "projecao_getzen_brasil.xlsx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)

###############################################################################
# PALETA DE CORES
###############################################################################

plt.rcParams["axes.prop_cycle"] = plt.cycler(color=["#1f77b4", "#ff7f0e"])  # azul & laranja

st.subheader("📈 Gráficos")

fig1, ax1 = plt.subplots()
ax1.plot(df["Ano"], df["HCCTR (%)"], marker="o", label="HCCTR (%)")
ax1.axhline(0, linestyle="--", color="gray")
ax1.set_xlabel("Ano")
ax1
