import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import requests                    # ### NOVO

# ---------- utilidades -------------------------------------------------------- #
def serie_bcb(codigo):              # ### NOVO
    url = f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados?formato=json"
    df = pd.DataFrame(requests.get(url, timeout=30).json())
    df['data'] = pd.to_datetime(df['data'], dayfirst=True)
    df['valor'] = pd.to_numeric(df['valor'])
    return df

# IPCA-15 (433) – inflação - 12m, PIB per capita real (SIDRA 5932, coluna V)
ipca15 = serie_bcb(433)
ipca_long = ipca15['valor'].tail(120).mean() / 100         # média 10 anos

pib_pc = pd.read_csv(
    'https://api.sidra.ibge.gov.br/values/t/5932/n1/1/v/99/p/all?formato=csv',
    sep=';')
pib_pc['V'] = pd.to_numeric(pib_pc['V'], errors='coerce')
pib_pc = pib_pc.dropna()
delta_pib_pc_real = pib_pc['V'].pct_change(periods=10).mean()

DEFAULTS = {                                              # ### NOVO
    'inflacao': round(ipca_long, 4),
    'renda_real': round(delta_pib_pc_real, 3),
    'share_ini': 0.096,
    'share_max': 0.15,
    'ano_limite': 2060,
    'ano_transicao_fim': 2030,
}

# ---------- Streamlit set-up --------------------------------------------------- #
st.set_page_config(page_title="Modelo Getzen Brasil", layout="centered")
st.title("📊 Inflação Médica – Modelo Getzen Adaptado ao Brasil")

st.sidebar.header("Parâmetros de Entrada")

usar_oficiais = st.sidebar.checkbox("Usar dados oficiais 🇧🇷", value=True)

# --- sliders & inputs --------------------------------------------------------- #
inflacao = st.sidebar.number_input(
    "Inflação esperada (IPCA-15)", 0.0, 1.0,
    DEFAULTS['inflacao'] if usar_oficiais else 0.02, step=0.001, format="%.3f")

renda_real = st.sidebar.number_input(
    "Crescimento real da renda per capita", 0.0, 1.0,
    DEFAULTS['renda_real'] if usar_oficiais else 0.02, step=0.001, format="%.3f")

renda_pc = inflacao + renda_real

anos_proj = st.sidebar.slider("Anos de Projeção", 10, 100, 60)
ano_inicio = 2019
ano_limite = st.sidebar.number_input(
    "Ano-limite para convergência (g_med = renda_pc)",
    2030, 2100, DEFAULTS['ano_limite'])

# Crescimentos médicos iniciais
g_medico_manual = [
    st.sidebar.number_input("Ano 1 – Crescimento Médico", 0.0, 1.0, 0.151 if usar_oficiais else 0.02),
    st.sidebar.number_input("Ano 2 – Crescimento Médico", 0.0, 1.0, 0.127 if usar_oficiais else 0.02),
    st.sidebar.number_input("Ano 3 – Crescimento Médico", 0.0, 1.0, 0.112 if usar_oficiais else 0.02),
    st.sidebar.number_input("Ano 4 – Crescimento Médico", 0.0, 1.0, 0.105 if usar_oficiais else 0.02),
]

g_medico_final = st.sidebar.number_input(
    "Crescimento Médico Pleno (após transição)", 0.0, 1.0,
    renda_pc + 0.03 if usar_oficiais else 0.061, step=0.001, format="%.3f")

ano_transicao_fim = DEFAULTS['ano_transicao_fim']

share_inicial = st.sidebar.number_input(
    "Participação inicial da Saúde no PIB", 0.0, 1.0,
    DEFAULTS['share_ini'] if usar_oficiais else 0.20, step=0.001, format="%.3f")

share_resistencia = st.sidebar.number_input(
    "Limite de resistência (share máximo)", 0.0, 1.0,
    DEFAULTS['share_max'] if usar_oficiais else 0.25, step=0.001, format="%.3f")

# ---------- Projeção principal ------------------------------------------------ #
def resistencia(share_atual, limite, k=0.02):              # ### NOVO (sigmóide)
    return 1 / (1 + np.exp((share_atual - limite) / k))

anos = list(range(ano_inicio, ano_inicio + anos_proj))
crescimento_medico, hcctr, share, custo, debug_data = [], [], [share_inicial], [1.0], []

for i, ano in enumerate(anos):
    if i < 4:
        g_m = g_medico_manual[i]
        motivo = "Manual (2019-2022)"
    elif ano <= ano_transicao_fim:
        frac = (ano - 2022) / (ano_transicao_fim - 2022)
        g_m = g_medico_manual[-1] + (g_medico_final - g_medico_manual[-1]) * frac
        motivo = "Transição linear"
    elif ano >= ano_limite:
        g_m = renda_pc
        motivo = "Ano-limite: g_med = renda"
    else:
        # aplica resistência sigmoidal
        excesso = max(g_medico_final - renda_pc, 0)
        g_m = renda_pc + excesso * resistencia(share[-1], share_resistencia)
        motivo = "Resistência fiscal"

    crescimento_medico.append(g_m)
    hcctr.append(g_m - renda_pc)
    custo.append(custo[-1] * (1 + g_m))
    share.append(share[-1] * (1 + (g_m - renda_pc)))

    debug_data.append({
        "Ano": ano,
        "Crescimento Médico (%)": g_m * 100,
        "HCCTR (%)": (g_m - renda_pc) * 100,
        "Share PIB (%)": share[-2] * 100,
        "Motivo": motivo
    })

df = pd.DataFrame(debug_data)

# ---------- Exibição ---------------------------------------------------------- #
st.subheader("📊 Tabela de Projeção")
st.dataframe(df, use_container_width=True)

# HCCTR blocos
curto = np.mean(hcctr[:5]) * 100
medio = np.mean(hcctr[5:9]) * 100
longo = np.mean(hcctr[9:]) * 100
st.markdown(f"**HCCTR Curto Prazo (1–5 anos):** {curto:.2f}%")
st.markdown(f"**HCCTR Médio Prazo (6–9 anos):** {medio:.2f}%")
st.markdown(f"**HCCTR Longo Prazo (10+ anos):** {longo:.2f}%")

# Download CSV e XLSX
csv = df.to_csv(index=False).encode('utf-8')
st.download_button("📥 Baixar CSV", csv, "projecao_getzen_brasil.csv", "text/csv")

xlsx_path = "/tmp/projecao_getzen_brasil.xlsx"
df.to_excel(xlsx_path, index=False, engine='xlsxwriter')
with open(xlsx_path, "rb") as f:
    st.download_button("📥 Baixar XLSX", f.read(), "projecao_getzen_brasil.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ---------- Paleta corporativa ------------------------------------------------ #
azul = "#1f77b4"      # primário
laranja = "#ff7f0e"   # secundário
plt.rcParams['axes.prop_cycle'] = plt.cycler(color=[azul, laranja])

# Gráficos
st.subheader("📈 Gráficos")
fig1, ax1 = plt.subplots()
ax1.plot(df["Ano"], df["HCCTR (%)"], marker="o", label="HCCTR (%)")
ax1.axhline(0, linestyle="--", color="gray")
ax1.set_xlabel("Ano"); ax1.set_ylabel("HCCTR (%)"); ax1.set_title("Projeção do HCCTR")
ax1.grid(True); ax1.legend()
st.pyplot(fig1)

fig2, ax2 = plt.subplots()
ax2.plot(df["Ano"], df["Share PIB (%)"], marker="s", label="Saúde/PIB (%)")
ax2.axhline(share_resistencia * 100, color="red", linestyle="--", label="Limite resistência")
ax2.set_xlabel("Ano"); ax2.set_ylabel("Participação no PIB (%)"); ax2.set_title("Participação da Saúde no PIB")
ax2.grid(True); ax2.legend()
st.pyplot(fig2)

fig3, ax3 = plt.subplots()
ax3.plot(df["Ano"], [custo[i+1] for i in range(len(anos))], marker="d", label="Inflação médica acumulada")
ax3.set_xlabel("Ano"); ax3.set_ylabel("Fator acumulado"); ax3.set_title("Inflação Médica Acumulada")
ax3.grid(True); ax3.legend()
st.pyplot(fig3)
