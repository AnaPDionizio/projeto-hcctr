
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

st.set_page_config(page_title="Modelo Getzen Brasil", layout="centered")
st.title("📊 Inflação Médica - Modelo Getzen Adaptado ao Brasil")

# Parâmetros fixos conforme planilha SOA v2019_b
st.sidebar.header("Parâmetros de Entrada")

anos_proj = st.sidebar.slider("Anos de Projeção", 10, 100, 60)
ano_inicio = 2019
ano_limite = st.sidebar.number_input("Ano limite para convergência HCCTR = 0", 2050, 2100, 2075)

# Entradas fixas
inflacao = st.sidebar.number_input("Inflação esperada (CPI)", 0.0, 1.0, 0.02)
renda_real = st.sidebar.number_input("Crescimento real da renda per capita", 0.0, 1.0, 0.02)
renda_pc = inflacao + renda_real

g_medico_manual = [
    st.sidebar.number_input("Ano 1 - Crescimento Médico", 0.0, 1.0, 0.02),
    st.sidebar.number_input("Ano 2 - Crescimento Médico", 0.0, 1.0, 0.02),
    st.sidebar.number_input("Ano 3 - Crescimento Médico", 0.0, 1.0, 0.02),
    st.sidebar.number_input("Ano 4 - Crescimento Médico", 0.0, 1.0, 0.02)
]

g_medico_final = st.sidebar.number_input("Crescimento Médico Pleno (após transição)", 0.0, 1.0, 0.061)
ano_transicao_fim = 2027

share_inicial = st.sidebar.number_input("Participação inicial da saúde no PIB", 0.0, 1.0, 0.20)
share_resistencia = st.sidebar.number_input("Limite de resistência (share máximo)", 0.0, 1.0, 0.25)

# Inicialização
anos = list(range(ano_inicio, ano_inicio + anos_proj))
crescimento_medico = []
hcctr = []
share = [share_inicial]
custo = [1.0]
debug_data = []

# Loop principal
for i, ano in enumerate(anos):
    if i < 4:
        g_m = g_medico_manual[i]
        motivo = "Manual (2019–2022)"
    elif ano <= ano_transicao_fim:
        frac = (ano - 2022) / (ano_transicao_fim - 2022)
        g_m = g_medico_manual[-1] + (g_medico_final - g_medico_manual[-1]) * frac
        motivo = "Transição Linear"
    elif ano >= ano_limite:
        g_m = renda_pc
        motivo = "Ano limite: crescimento médico = renda"
    elif share[-1] > share_resistencia:
        excesso = g_medico_final - renda_pc
        ajuste = (share[-1] - share_resistencia)
        g_m = renda_pc + excesso * (1 - ajuste * 10)
        g_m = max(g_m, renda_pc)
        motivo = "Resistência aplicada"
    else:
        g_m = g_medico_final
        motivo = "Crescimento médico pleno"

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

# Exibição da tabela
st.subheader("📊 Tabela de Projeção")
st.dataframe(df, use_container_width=True)

# Blocos de HCCTR
curto = np.mean(hcctr[:5]) * 100
medio = np.mean(hcctr[5:9]) * 100
longo = np.mean(hcctr[9:]) * 100

st.markdown(f"**HCCTR Curto Prazo (1–5 anos):** {curto:.2f}%")
st.markdown(f"**HCCTR Médio Prazo (6–9 anos):** {medio:.2f}%")
st.markdown(f"**HCCTR Longo Prazo (10+ anos):** {longo:.2f}%")

# Download
csv = df.to_csv(index=False).encode('utf-8')
st.download_button("📥 Baixar CSV", csv, "projecao_getzen_ajustada.csv", "text/csv")

# Gráficos
st.subheader("📈 Gráficos")
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
ax3.plot(df["Ano"], [custo[i+1] for i in range(len(anos))], color="green", label="Inflação médica acumulada")
ax3.set_xlabel("Ano")
ax3.set_ylabel("Fator acumulado")
ax3.set_title("Inflação Médica Acumulada")
ax3.grid(True)
ax3.legend()
st.pyplot(fig3)
