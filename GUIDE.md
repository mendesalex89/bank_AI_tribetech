# Guia de Utilização — Credit Risk IRB Platform

> **Para quem é este guia?** Para qualquer pessoa — técnica ou não — que queira perceber o que esta plataforma faz, como usá-la e o que significam os resultados.

---

## O que é esta plataforma?

É uma plataforma profissional de **análise de risco de crédito** que replica o que os bancos fazem internamente para decidir se concedem um empréstimo e quanto capital devem reservar para cobrir possíveis perdas.

Usa dados reais de **199.675 empréstimos** do Lending Club (2007–2018) e três modelos de machine learning treinados segundo as regras do regulador europeu (**EBA GL/2017/06**).

---

## Acesso

| Ambiente | URL |
|---|---|
| **Produção (online)** | https://tribetech-creditrisk.azurewebsites.net |
| **Local** | http://localhost:8080 |

---

## Estrutura da Plataforma

A plataforma tem **5 secções** acessíveis pelo menu lateral:

```
Home  →  Dashboard  →  Scoring (PD / LGD / EAD / Batch)  →  Reports  →  Chatbot
```

---

## 1. Home — Visão Geral do Projecto

**O que é:** A página de apresentação. Resume o projecto, a arquitectura técnica e as fases de desenvolvimento.

**O que encontra aqui:**

- **4 KPI cards no topo**
  - Nº de modelos IRB (3: PD, LGD, EAD)
  - Total de registos analisados (2,2M+ empréstimos Lending Club)
  - Nº de fases do projecto (9)
  - Conformidade regulatória (EBA GL/2017/06)

- **Diagrama de arquitectura** — mostra como os componentes comunicam: dados → ETL → modelos → API → dashboard → Azure

- **Tabela de fases** — cronograma das 9 fases de desenvolvimento (dados, modelos, API, dashboard, deploy, etc.)

- **Stack tecnológico** — Python, XGBoost, FastAPI, Django, PostgreSQL, Docker, Azure, MLflow

> Esta página serve para um recrutador ou gestor perceber rapidamente o âmbito e a maturidade do projecto.

---

## 2. Dashboard — Análise do Portfólio

**O que é:** O painel principal de análise. Mostra como o portfólio de 199.675 empréstimos se comporta em termos de risco.

**KPIs no topo (6 cartões):**

| KPI | O que significa |
|---|---|
| **Empréstimos** | Total de registos no portfólio |
| **Exposição** | Valor total emprestado (mil milhões €) |
| **Taxa de Default** | % de empréstimos que entraram em incumprimento |
| **FICO Médio** | Score de crédito médio dos mutuários (580–850) |
| **Perda Realizada** | Perdas efectivamente ocorridas (milhões €) |
| **Capital Mínimo** | Capital regulatório exigido pelo Basileia III (8% do RWA) |

**8 Gráficos interactivos:**

### Taxa de Default por Grade vs Expected Loss
- **Tipo:** Barras + linha
- **O que mostra:** Para cada grade (A a G), compara a taxa de incumprimento real com a perda esperada prevista pelo modelo
- **Como ler:** Grade A = risco mais baixo; Grade G = risco mais alto. A linha de Expected Loss deve aproximar-se das barras de perda realizada — se coincidir, o modelo está bem calibrado

### Distribuição por Grade
- **Tipo:** Doughnut (circular)
- **O que mostra:** Que percentagem do portfólio pertence a cada grade de risco (A–G)
- **Como ler:** Um portfólio saudável tem a maioria nos segmentos A, B, C; concentração em F e G é sinal de risco elevado

### Vintage — Taxa de Default por Ano
- **Tipo:** Barras + linha
- **O que mostra:** Como a taxa de default evoluiu ano a ano (2007–2018)
- **Como ler:** Picos em 2008–2009 reflectem a crise financeira global; estabilização após 2012 indica normalização do mercado

### Finalidade do Empréstimo
- **Tipo:** Barras horizontais
- **O que mostra:** As 8 finalidades mais comuns (consolidação de dívida, cartão de crédito, melhoria da habitação, etc.) e o volume de cada uma
- **Como ler:** "Debt consolidation" é sempre a finalidade dominante nos dados do Lending Club

### Distribuição FICO Score
- **Tipo:** Barras + linha
- **O que mostra:** Como se distribuem os FICO scores do portfólio e qual a taxa de default em cada intervalo
- **Como ler:** Quanto mais baixo o FICO, maior a taxa de default. A linha sobreposta confirma essa correlação

### FICO Médio vs Taxa de Default por Grade
- **Tipo:** Barras + linha
- **O que mostra:** A qualidade creditícia média (FICO) e a taxa de default por cada grade
- **Como ler:** Confirma que as grades mais baixas (E, F, G) têm FICO mais baixo e maior default — valida a consistência do sistema de rating

### Métricas dos Modelos IRB
- **Tipo:** Cards de validação (3 colunas)
- **O que mostra:** As métricas regulatórias de cada modelo (PD, LGD, EAD) comparadas com os limiares EBA
- **Como ler:** ✅ = aprovado pelo regulador; ❌ = abaixo do limiar mínimo

### Tabela — Resumo por Grade
- **O que mostra:** Para cada grade (A–G): nº de empréstimos, exposição total, taxa de default, FICO médio, perda esperada e nível de risco
- **Como ler:** Linha a linha, da grade mais segura (A) à mais arriscada (G)

---

## 3. Scoring — Análise de Risco Individual

Esta secção tem 4 sub-páginas, cada uma com um modelo diferente.

---

### 3a. PD — Probabilidade de Incumprimento

**O que é:** Dado um perfil de cliente e empréstimo, calcula a probabilidade de esse cliente entrar em incumprimento.

**Como usar:**

1. Ajuste os sliders do formulário à esquerda:

| Campo | O que é | Exemplo |
|---|---|---|
| **FICO Score** | Pontuação de crédito do cliente (580–850; maior = melhor) | 720 |
| **DTI (%)** | Dívida total ÷ rendimento mensal (0–50%; menor = melhor) | 18% |
| **Taxa de Juro (%)** | Taxa do empréstimo pedido (5–30%) | 12% |
| **Rendimento Anual** | Rendimento bruto anual do cliente | €60.000 |
| **Anos de Emprego** | Estabilidade laboral (0–10 anos) | 5 anos |
| **Finalidade** | Para que serve o empréstimo | Consolidação de dívida |
| **Habitação** | Situação habitacional do cliente | Hipoteca |

2. O resultado aparece automaticamente à direita:

| Resultado | O que significa |
|---|---|
| **Gauge de PD (%)** | Probabilidade de incumprimento (0% = sem risco; 100% = incumprimento certo) |
| **Scorecard** | Pontuação interna do banco (300–850; como o FICO mas calculado pelo modelo) |
| **Grade IRB** | Classificação de risco: A (melhor) → G (pior) |
| **Alerta** | Baixo / Moderado / Alto / Muito Alto Risco |

3. Dois gráficos adicionais:
   - **Factores de Risco:** quais as variáveis que mais influenciaram o resultado (ex: FICO teve peso de 40%)
   - **PD Observada vs Modelada:** compara a previsão com a realidade histórica por grade

> **Exemplo prático:** Um cliente com FICO 690, DTI 20%, rendimento €50.000, empréstimo para consolidação de dívida → PD ≈ 12%, Grade C, Risco Moderado.

---

### 3b. LGD — Perda Dado Incumprimento

**O que é:** Assumindo que o cliente já entrou em incumprimento, calcula quanto o banco vai perder efectivamente (depois de recuperações e garantias).

**Como usar:**

| Campo | O que é |
|---|---|
| **Montante do Empréstimo** | Capital em dívida no momento do incumprimento |
| **Valor da Garantia (Colateral)** | Valor de activos dados como garantia (ex: imóvel) |
| **Recuperações Estimadas** | Montante que o banco consegue recuperar |
| **Situação Habitacional** | Indica se existe imóvel como garantia implícita |
| **Tipo de Crédito** | Sem garantia / Com garantia / Hipotecário |

**Resultados:**

| Resultado | O que significa |
|---|---|
| **LGD (%)** | % do empréstimo que o banco perde (ex: LGD 45% = perde €4.500 em €10.000) |
| **Taxa de Recuperação (%)** | O inverso: % que o banco consegue recuperar (100% − LGD) |
| **Perda Esperada (€)** | Valor monetário da perda estimada |

> **Regra geral:** Crédito hipotecário tem LGD baixo (garantia real); crédito sem garantia tem LGD alto (nada a recuperar).

---

### 3c. EAD — Exposição no Incumprimento

**O que é:** Calcula qual o valor exacto em dívida no momento em que o cliente entrar em incumprimento — importante porque créditos rotativos (cartão de crédito, linhas de crédito) podem ter mais ou menos usado no momento do default.

**Como usar:**

| Campo | O que é |
|---|---|
| **Limite de Crédito Total** | Máximo que o banco disponibilizou |
| **Montante Comprometido** | Parte do limite já comprometida/aprovada |
| **Montante Utilizado** | Parte que o cliente efectivamente utilizou |
| **Tipo de Produto** | Crédito Rotativo / Prazo / Linha de Crédito |

**Resultados:**

| Resultado | O que significa |
|---|---|
| **EAD (€)** | Exposição estimada no momento do incumprimento |
| **CCF (%)** | Credit Conversion Factor — % do não utilizado que se espera que seja sacado antes do default |
| **Utilização (%)** | % do limite já utilizado actualmente |

> **Exemplo:** Limite €20.000, utilizado €8.000 → CCF 60% → EAD = €8.000 + 60% × €12.000 = €15.200

---

### 3d. Batch Scoring — Análise em Lote

**O que é:** Em vez de analisar um empréstimo de cada vez, permite fazer o upload de um ficheiro CSV com centenas ou milhares de empréstimos e obter os resultados de todos de uma vez.

**Como usar:**

1. Prepare um ficheiro CSV com estas colunas obrigatórias:
```
fico_score, dti, int_rate, annual_inc, loan_amnt, emp_length, purpose, home_ownership
```

2. Arraste o ficheiro para a zona de upload (ou clique para seleccionar)

3. Seleccione quais os modelos a executar: ✅ PD  ✅ LGD  ✅ EAD

4. Clique em **Executar Scoring em Lote**

5. A barra de progresso mostra o avanço (ex: "450 de 1.000 registos — 45%")

6. Na tabela de resultados, cada linha terá: FICO, DTI, PD (%), Grade, LGD (%), EAD (€), Perda Esperada (€)

7. Clique em **Exportar CSV** para descarregar os resultados

> **Uso típico:** Análise de uma carteira de crédito inteira; re-scoring periódico de clientes existentes; stress testing regulatório.

---

## 4. Reports — Relatórios Regulatórios

### 4a. Relatório EBA

**O que é:** Validação formal dos modelos segundo as normas do regulador europeu (EBA GL/2017/06). É o documento que um banco apresentaria ao Banco Central Europeu para provar que os seus modelos IRB são fiáveis.

**O que contém:**

Para cada modelo (PD, LGD, EAD), apresenta as métricas de validação com semáforo de aprovação:

**Modelo PD:**
| Métrica | O que mede | Limiar EBA | Resultado |
|---|---|---|---|
| **Gini** | Capacidade de separar bons de maus pagadores (0–100%; maior = melhor) | ≥ 20% | ✅ 62,1% |
| **KS (Kolmogorov-Smirnov)** | Distância máxima entre distribuições de bons e maus pagadores | ≥ 20% | ✅ 48,3% |
| **AUC-ROC** | Área sob a curva ROC — performance global do classificador (0,5–1,0) | ≥ 0,65 | ✅ 0,81 |
| **Brier Score** | Erro de calibração das probabilidades (0 = perfeito) | ≤ 0,25 | ✅ 0,094 |

**Modelos LGD e EAD (regressão):**
| Métrica | O que mede | Resultado |
|---|---|---|
| **R²** | % da variância explicada pelo modelo (1,0 = perfeito) | LGD: 0,43 / EAD: 0,87 |
| **RMSE** | Erro médio nas previsões | LGD: 0,119 / EAD: €412 |
| **MAE** | Erro absoluto médio | LGD: 0,082 |

**Dois gráficos por modelo:**
- **Curva ROC** — quanto mais a curva se afasta da diagonal, melhor o modelo discrimina
- **Curva KS** — ponto de máxima separação entre incumpridores e não incumpridores

**Referências regulatórias** — links para os artigos do CRR e orientações EBA aplicáveis.

---

### 4b. Monitorização de Modelos

**O que é:** Acompanhamento contínuo da performance dos modelos em produção — detecta se os modelos estão a degradar ao longo do tempo.

**Cards de Status dos Modelos:**

| Modelo | Versão | Gini/R² | PSI | Drift | Estado |
|---|---|---|---|---|---|
| PD | 3.0 | Gini actual | 0,042 | Baixo | 🟢 Estável |
| LGD | 2.0 | R² actual | 0,038 | Baixo | 🟢 Estável |
| EAD | 2.0 | R² actual | 0,018 | Baixo | 🟢 Estável |

**4 gráficos de monitorização:**

- **Evolução do Gini ao longo do tempo** — detecta degradação de performance mês a mês
- **PSI por modelo** — Population Stability Index: mede se a população de clientes mudou (PSI > 0,25 = alerta vermelho)
- **Distribuição de Scores** — compara a distribuição dos scores de treino vs produção actual
- **Backtesting** — compara PD prevista com PD observada por grade, trimestre a trimestre

> **O PSI é crítico:** Se a população de clientes mudar significativamente (ex: crise económica), o modelo treinado em dados históricos pode deixar de ser válido. PSI baixo = modelo ainda é aplicável.

---

### 4c. Exportar PDF

**O que é:** Gera um relatório PDF formal, pronto para ser entregue ao regulador ou à gestão de topo.

**Conteúdo do PDF:**
1. **Sumário Executivo** — contextualização dos modelos PD, LGD, EAD e dados utilizados
2. **Métricas de Validação** — tabela completa com Gini, KS, AUC-ROC, Brier Score, R², RMSE e status EBA
3. **Conformidade Regulatória** — referências aos artigos do CRR e orientações EBA aplicáveis

O documento é marcado **CONFIDENCIAL** e inclui data de geração e versão.

---

## 5. Chatbot — Assistente IRB com IA

**O que é:** Um assistente de inteligência artificial que responde a perguntas sobre risco de crédito em linguagem natural, com acesso directo aos dados reais do portfólio e aos modelos IRB.

**Como funciona (por baixo):**
- Motor: **DeepSeek v3.2** via OpenRouter
- Acesso a **2 ferramentas reais** (tool use):
  - `query_portfolio` → consulta SQL ao PostgreSQL com 199.675 empréstimos
  - `predict_credit_risk` → chama a API FastAPI para calcular PD/LGD/EAD em tempo real
- O modelo **nunca inventa valores** — todos os números vêm de dados reais ou modelos treinados

**Tipos de perguntas que pode fazer:**

**Sobre o portfólio:**
```
"Qual a grade com maior taxa de default?"
"Mostra a distribuição do portfólio por grade"
"Qual a exposição total do portfólio?"
"Qual o FICO médio dos clientes?"
"Que finalidade de empréstimo tem maior risco?"
```

**Sobre análise de risco individual:**
```
"Analisa empréstimo €15.000, FICO 690, DTI 20%"
"Qual o risco de um cliente com FICO 620 e DTI 35%?"
"Calcula PD, LGD e EAD para €25.000 a 15% de juro"
```

**Sobre conceitos IRB:**
```
"Como funciona o modelo PD?"
"O que é o Expected Loss?"
"Explica o que é o EBA GL/2017/06"
```

**Exemplo de resposta a "Qual a grade com maior taxa de default?":**
```
Com base nos dados reais do portfólio, a grade G apresenta
a maior taxa de default com 40,02%.

Grade A: 3,68% | Grade B: 8,68% | Grade C: 13,89%
Grade D: 20,50% | Grade E: 28,02% | Grade F: 36,79%
Grade G: 40,02% ← maior risco

A grade G tem 1.082 empréstimos com exposição de €22,4M
e FICO médio de 681.
```

---

## Glossário de Termos

| Termo | Significado |
|---|---|
| **IRB** | Internal Ratings-Based — abordagem de Basileia que permite aos bancos usar modelos internos para calcular requisitos de capital |
| **PD** | Probability of Default — probabilidade de o cliente não pagar |
| **LGD** | Loss Given Default — % do valor em dívida que o banco perde quando há incumprimento |
| **EAD** | Exposure at Default — valor exacto em dívida no momento do incumprimento |
| **Expected Loss** | PD × LGD × EAD — perda esperada total |
| **CCF** | Credit Conversion Factor — factor que converte compromissos não utilizados em exposição |
| **Grade** | Classificação de risco de A (melhor) a G (pior) |
| **FICO Score** | Pontuação de crédito americana (580–850); quanto maior, melhor o historial de crédito |
| **DTI** | Debt-to-Income Ratio — dívida mensal ÷ rendimento mensal; quanto menor, melhor |
| **Gini** | Métrica de discriminação dos modelos (%) — capacidade de separar bons de maus pagadores |
| **PSI** | Population Stability Index — mede se a população de clientes mudou (alerta se > 0,25) |
| **EBA** | European Banking Authority — regulador bancário europeu |
| **Basileia III** | Acordo internacional de regulação bancária que define os requisitos de capital |
| **RWA** | Risk-Weighted Assets — activos ponderados pelo risco; base para o cálculo de capital |
| **Backtesting** | Comparação de previsões do modelo com o que realmente aconteceu |
| **Vintage** | Análise por ano de emissão — como se comportaram os empréstimos concedidos em cada ano |

---

## Fluxo de Análise Típico

```
1. Dashboard
   └─ Ver KPIs gerais e distribuição do portfólio
   └─ Identificar grades / vintages com maior risco

2. Scoring → PD
   └─ Inserir perfil do cliente e empréstimo
   └─ Obter PD, Grade e Scorecard

3. Scoring → LGD
   └─ Inserir garantias e montante
   └─ Obter perda esperada em caso de incumprimento

4. Scoring → EAD
   └─ Calcular exposição no momento do default

5. Expected Loss = PD × LGD × EAD
   └─ Decisão: aprovar / rejeitar / pedir garantias adicionais

6. Reports → EBA
   └─ Validar que os modelos cumprem os requisitos regulatórios

7. Chatbot
   └─ Perguntas ad-hoc sobre portfólio ou empréstimos específicos
```

---

*Tribetech · Credit Risk IRB Platform · 2026*
