# -*- coding: utf-8 -*-
"""
Modelo Getzen Adaptado ao Brasil
--------------------------------
Script Streamlit autocontido. Lê séries oficiais (BCB/IBGE) quando
houver acesso à Internet; caso contrário, cai para modo manual ou
permite upload de CSV proprietário. Inclui tratamento de exceção para
URLError, paleta corporativa (azul & laranja) e download em CSV/XLSX.
"""

import io
from datetime import date
from urllib.error import URLError

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import requests
import streamlit as st

# ---------------------------------------------------------------------------
# Utilidades de dados oficiais
# ---------------------------------------------------------------------------

def serie_bcb(codigo: int) -> pd.DataFrame | None:
    """Retorna DataFrame com colunas ['data', 'valor'] da série SGS.
    Devolve None se não conseguir baixar."""
    url = (
        f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados?formato=json"
    )
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        df = pd.json_normalize(r.json())
        df["data"] = pd.to_datetime(df["data"], dayfirst=True)
        df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
        return df.dropna()
    except Exception:
        return None


def load_pib_pc_sidra() -> pd.DataFrame | None:
    """Tenta baixar PIB per capita real do SIDRA (tabela 5932).
    Devolve None se falhar."""
    url = (
        "https://api.sidra.ibge.gov.br/values/t/5932/n1/1/v/99/p/all?formato=csv"
    )
    try:
        df = pd.read_csv(url, sep=";")
        df["V"] = pd.to_numeric(df["V"], errors="coerce")
        df = df.dropna()
        return df
    except URLError:
        return None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Baixa séries oficiais se possível
# ---------------------------------------------------------------------------

ipca_df = serie_bcb(433)  # IPCA-15
ipca_long = (
    ipca_df["valor"].tail(120).mean() / 100 if ipca_df is not None else 0.035
)

pib_pc_df = load_pib_pc_sidra()
if pib_pc_df is None:
    # tenta BCB (PIB real per capita – série 20712)
    pib_pc_df = serie_bcb(20712)

if pib_pc_df is not None:
    pib_pc_df.sort_values("data", inplace=True)
    delta_pib_pc_real = pib_pc_df["valor"].pct_change(40).mean()
else:
    delta_pib_pc_real = 0.015  # fallback conservador

# ---------------------------------------------------------------------------
# Configura Streamlit
# ---------------------------------------------------------------------------

st.set_page_config(page_title="Modelo Getzen Brasil", layout="centered")
st.title("📊 Inflação Médica – Modelo Getzen Adaptado ao Brasil")

st.sidebar.header("Parâmetros de Entrada")

dados_oficiais_disponiveis = ipca_df is not None and pib_pc_df is not None
usar_oficiais = st.sidebar.checkbox(
    "Usar dados oficiais 🇧🇷", value=dados_oficiais_disponiveis
)

# Caso dados oficiais não estejam disponíveis, avisa o usuário
if usar_oficiais and not dados_oficiais_disponiveis:
    st.sidebar.warning(
        "Dados oficiais indisponíveis (sem Internet ou bloqueio).\n"
        "Alternando para modo manual."
    )
    usar_oficiais = False

# Upload opcional de CSV
upload = st.sidebar.file_uploader("📂 (Opcional) Carregar CSV PIB pc", type="csv")
if upload is not None:
    try:
        pib_pc_df = pd.read_csv(upload, sep=";")
        pib_pc_df["V"] = pd.to_numeric(pib_pc_df["V"], errors="coerce")
        pib_pc_df = pib_pc_df.dropna()
        delta_pib_pc_real = pib_pc_df["V"].pct_change(40).mean()
        usar_oficiais = False  # garante sliders editáveis
        st.sidebar.success("CSV carregado com sucesso.")
    except Exception as e:
        st.sidebar.error(f"Erro ao ler CSV: {e}")

# ---------------------------------------------------------------------------
# Defaults calibrados (ou genéricos se sem dados)
# ---------------------------------------------------------------------------

def g_med_final_default(pi: float, dy: float) -> float:
    """Excesso tecnológico de 3 p.p."""
    return pi + dy + 0.03

DEFAULTS = {
    "inflacao": round(ipca_long, 4),
    "renda_real": round(delta_pib_pc_real, 3),
    "share_ini": 0.096,
    "share_max": 0.15,
    "ano_limite": 2060,
    "ano_transicao_fim": 2030,
}

# ---------------------------------------------------------------------------
# Controles de input
# ---------------------------------------------------------------------------

inflacao = st.sidebar.number_input(
    "Inflação esperada (IPCA-15)",
    0.0,
    1.0,
    DEFAULTS["inflacao"] if usar_oficiais else 0.02,
    step=0.001,
    format="%.3f",
)

renda_real = st.sidebar.number_input(
    "Crescimento real da renda per capita",
    0.0,
    1.0,
    DEFAULTS["renda_real"] if usar_oficiais else 0.02,
    step=0.001,
    format="%.3f",
)

renda_pc = inflacao + renda_real

anos_proj = st.sidebar.slider("Anos de Projeção", 10, 100, 60)
ano_inicio = 2019
ano_limite = st.sidebar.number_input(
    "Ano‑limite para convergência (g_med = renda_pc)",
    2030,
    2100,
    DEFAULTS["ano_limite"],
)

# Crescimentos médicos iniciais (anos 1‑4)
initial_defaults = [0.151, 0.127, 0.112, 0.105] if usar_oficiais else [0.02] * 4
g_medico_manual = []
for i in range(4):
    g_medico_manual.append(
        st.sidebar.number_input(
            f"Ano {i + 1} – Crescimento Médico",
            0.0,
            1.0,
            initial_defaults[i],
            step=0.001,
            format="%.3f",
        )
    )

g_medico_final = st.sidebar.number_input(
    "Crescimento Médico Pleno (após transição)",
    0.0,
    1.0,
    g_med_final_default(inflacao, renda_real) if usar_oficiais else 0.061,
    step=0.001,
    format="%.3f",
)

ano_transicao_fim = DEFAULTS["ano_transicao_fim"]

share_inicial = st.sidebar.number_input(
    "Participação inicial da Saúde no PIB",
    0.0,
    1.0,
    DEFAULTS["share_ini"] if usar_oficiais else 0.20,
    step=0.001,
    format="%.3f",
)

share_resistencia = st.sidebar.number_input(
    "Limite de resistência (share máximo)",
    0.0,
    1.0,
    DEFAULTS["share_max"] if usar_oficiais else 0.25,
    step=0.001,
    format="%.3f",
)

# ---------------------------------------------------------------------------
# Funções auxiliares do modelo
# ---------------------------------------------------------------------------

def resistencia_sigmoide(share_atual: float, limite: float, k: float = 0.02) -> float:
    """Fator [0‑1] que reduz excesso tecnológico conforme share→limite."""
    return 1 / (1 + np.exp((share_atual - limite) / k))

# ---------------------------------------------------------------------------
# Projeção principal
# ---------------------------------------------------------------------------

anos = list(range(ano_inicio, ano_inicio + anos_proj))
crescimento_medico, hcctr, share, custo, debug_data = [], [], [share_inicial], [1.0], []

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

# ---------------------------------------------------------------------------
# Exibição
# ---------------------------------------------------------------------------

st.subheader("📊 Tabela de Projeção")
st.dataframe(df, use_container_width=True)

# Blocos de HCCTR
curto = np.mean(hcctr[:5]) * 100
medio = np.mean(hcctr[5:9]) * 100
longo = np.mean(hcctr[9:]) * 100

st.markdown(f"**HCCTR Curto Prazo (1–5 anos):** {curto:.2f}%")
st.markdown(f"**HCCTR Médio Prazo (6–9 anos):** {medio:.2f}%")
st.markdown(f"**HCCTR Longo Prazo (10+ anos):** {longo:.2f}%")

# Downloads
csv_bytes = df.to_csv(index=False).encode("utf-8")
st.download_button(
    "📥 Baixar CSV",
    csv_bytes,
    "projecao_getzen_brasil.csv",
    mime="text/csv",
)

output = io.BytesIO()
with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
    df.to_excel(writer, index=False)
excel_bytes = output.getvalue()

st.download_button(
    "📥 Baixar XLSX",
    excel_bytes,
    "projecao_getzen_brasil.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)

# ---------------------------------------------------------------------------
# Gráficos – paleta corporativa
# ---------------------------------------------------------------------------

azul = "#1f77b4"
laranja = "#ff7f0e"
plt.rcParams["axes.prop_cycle"] = plt.cycler(color=[azul, laranja])

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
