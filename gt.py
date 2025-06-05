import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

st.set_page_config(page_title="Modelo Getzen Brasil", layout="centered")
st.title("📊 Inflação Médica - Modelo Getzen Adaptado ao Brasil")

# Entradas de parâmetros
st.sidebar.header("Parâmetros de Entrada")

anos_proj = st.sidebar.slider("Anos de Projeção", 10, 100, 50)

modo_ipca = st.sidebar.radio("Entrada de inflação:", ["Junto com renda", "Separado: inflação + renda real"])
if modo_ipca == "Junto com renda":
    renda_pc_br = st.sidebar.number_input("Crescimento da renda per capita (com inflação)", 0.0, 1.0, 0.055)
    inflacao_br = 0.0
else:
    inflacao_br = st.sidebar.number_input("Inflação esperada (IPCA)", 0.0, 1.0, 0.04)
    renda_real_br = st.sidebar.number_input("Crescimento da renda per capita real", 0.0, 1.0, 0.015)
    renda_pc_br = inflacao_br + renda_real_br

excesso_inicial_br = st.sidebar.number_input("HCCTR inicial (excesso)", 0.0, 1.0, 0.012)
share_inicial = st.sidebar.number_input("Participação inicial da saúde no PIB", 0.0, 1.0, 0.094)
resistencia = st.sidebar.number_input("Nível de resistência do sistema", 0.0, 1.0, 0.20)
param_potencia = st.sidebar.slider("Potência da resistência (ex: 2)", 1.0, 5.0, 2.0)
ano_inicio = 2025
ano_limite = st.sidebar.number_input("Ano limite para convergência HCCTR = 0", ano_inicio + 10, ano_inicio + 100, ano_inicio + 50)

# Entrada manual dos 4 primeiros anos
st.sidebar.markdown("### HCCTR Manual (Anos 1 a 4)")
hcctr_manual = [
    st.sidebar.number_input("Ano 1", 0.0, 1.0, excesso_inicial_br),
    st.sidebar.number_input("Ano 2", 0.0, 1.0, excesso_inicial_br),
    st.sidebar.number_input("Ano 3", 0.0, 1.0, excesso_inicial_br),
    st.sidebar.number_input("Ano 4", 0.0, 1.0, excesso_inicial_br)
]

# Variáveis de projeção
crescimento_total = []
excesso_ajustado = []
share = [share_inicial]
custo = [1.0]
debug_data = []

# Loop de simulação
for t in range(anos_proj):
    ano_corrente = ano_inicio + t
    if t < 4:
        excesso_t = hcctr_manual[t]
        motivo = "Manual"
    elif 4 <= t < 8:
        frac = (t - 3) / 4
        excesso_t = excesso_inicial_br * (1 - frac)
        motivo = "Transição"
    elif ano_corrente >= ano_limite:
        excesso_t = 0
        motivo = "Ano limite"
    elif ano_corrente >= (ano_limite - 10):
        frac = (ano_corrente - (ano_limite - 10)) / 10
        excesso_t = excesso_inicial_br * (1 - frac)
        motivo = "Convergência final"
    elif share[-1] > resistencia:
        excesso_t = excesso_inicial_br * (1 - (share[-1] - resistencia) ** (1 / param_potencia))
        motivo = "Resistência"
    else:
        excesso_t = excesso_inicial_br
        motivo = "Excesso padrão"

    g_total = renda_pc_br + excesso_t
    crescimento_total.append(g_total)
    excesso_ajustado.append(excesso_t)
    custo.append(custo[-1] * (1 + g_total))
    share.append(share[-1] * (1 + excesso_t))

    debug_data.append({
        "Ano": ano_corrente,
        "Share PIB (%)": share[-2] * 100,
        "Excesso (%)": excesso_t * 100,
        "Motivo": motivo
    })

# Gerar DataFrame
anos = [ano_inicio + i for i in range(anos_proj)]
df = pd.DataFrame({
    "Ano": anos,
    "Inflação médica acumulada (fator)": custo[1:],
    "Participação da saúde no PIB (%)": [s * 100 for s in share[1:]],
    "HCCTR (%)": [v * 100 for v in excesso_ajustado],
    "Inflação médica total (%)": [100 * (renda_pc_br + v) for v in excesso_ajustado]
})

# Tabela de projeção
st.subheader("Tabela de Projeção")
st.dataframe(df, use_container_width=True)
csv = df.to_csv(index=False).encode('utf-8')
st.download_button("📥 Baixar CSV", csv, "projecao_getzen_brasil.csv", "text/csv")

# Blocos de HCCTR
curto = np.mean(excesso_ajustado[:5]) * 100
medio = np.mean(excesso_ajustado[5:9]) * 100
longo = np.mean(excesso_ajustado[9:]) * 100

st.markdown(f"**HCCTR Curto Prazo (1–5 anos):** {curto:.2f}%")
st.markdown(f"**HCCTR Médio Prazo (6–9 anos):** {medio:.2f}%")
st.markdown(f"**HCCTR Longo Prazo (10+ anos):** {longo:.2f}%")

# Detalhamento técnico
st.subheader("🔍 Detalhamento Interno do Cálculo de HCCTR")
debug_df = pd.DataFrame(debug_data)
st.dataframe(debug_df, use_container_width=True)

# Gráficos
st.subheader("Gráficos")

fig1, ax1 = plt.subplots()
ax1.plot(df["Ano"], df["HCCTR (%)"], label="HCCTR (%)")
ax1.axhline(y=excesso_inicial_br * 100, color='gray', linestyle='--', label='HCCTR inicial')
ax1.set_title("Projeção do HCCTR")
ax1.set_xlabel("Ano")
ax1.set_ylabel("% ao ano")
ax1.grid(True)
ax1.legend()
st.pyplot(fig1)

fig2, ax2 = plt.subplots()
ax2.plot(df["Ano"], df["Participação da saúde no PIB (%)"], color="orange", label="Participação da Saúde no PIB")
ax2.axhline(y=resistencia * 100, color='red', linestyle='--', label='Limite de Resistência')
ax2.set_title("Participação da Saúde no PIB")
ax2.set_xlabel("Ano")
ax2.set_ylabel("%")
ax2.grid(True)
ax2.legend()
st.pyplot(fig2)

fig3, ax3 = plt.subplots()
ax3.plot(df["Ano"], df["Inflação médica acumulada (fator)"], color="green")
ax3.set_title("Inflação Médica Acumulada")
ax3.set_xlabel("Ano")
ax3.set_ylabel("Fator acumulado")
ax3.grid(True)
st.pyplot(fig3)

# Comparação entre cenários de IPCA
st.subheader("Comparação de Cenários com IPCA diferentes")
cenarios = [0.03, 0.05, 0.07]
cores = ["blue", "purple", "red"]
fig4, ax4 = plt.subplots()

for ipca, cor in zip(cenarios, cores):
    custo_simulado = [1.0]
    share_sim = [share_inicial]
    for t in range(anos_proj):
        if t < 4:
            excesso_t = hcctr_manual[t]
        elif 4 <= t < 8:
            frac = (t - 3) / 4
            excesso_t = excesso_inicial_br * (1 - frac)
        elif ano_inicio + t >= ano_limite:
            excesso_t = 0
        elif ano_inicio + t >= (ano_limite - 10):
            frac = ((ano_inicio + t) - (ano_limite - 10)) / 10
            excesso_t = excesso_inicial_br * (1 - frac)
        elif share_sim[-1] > resistencia:
            excesso_t = excesso_inicial_br * (1 - (share_sim[-1] - resistencia) ** (1 / param_potencia))
        else:
            excesso_t = excesso_inicial_br

        g_total = ipca + renda_pc_br - inflacao_br + excesso_t
        custo_simulado.append(custo_simulado[-1] * (1 + g_total))
        share_sim.append(share_sim[-1] * (1 + excesso_t))

    ax4.plot(anos, custo_simulado[1:], label=f"IPCA {int(ipca*100)}%", color=cor)

ax4.set_title("Inflação médica acumulada por cenário de IPCA")
ax4.set_xlabel("Ano")
ax4.set_ylabel("Fator acumulado")
ax4.grid(True)
ax4.legend()
st.pyplot(fig4)
