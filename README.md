# 🏃‍♂️ Sistema de Gestão de Treino e Saúde IA (Health Tracker Template)

Este repositório contém um ecossistema automatizado para monitoramento de saúde e planejamento dinâmico de treinos esportivos (Corrida, Ciclismo, Natação, Força), integrado ao **Intervals.icu** e potencializado pelo **Google Gemini IA**.

O sistema foi estruturado de forma modular e inteligente, cruzando dados de carga real com marcadores fisiológicos (HRV e Sono) para periodizar treinos de forma dinâmica e automatizada.

---

## 🛠️ Arquitetura do Sistema

O sistema é composto pelos seguintes módulos em Python:

### 📁 Estrutura de Arquivos
- `health_tracker/`
  - `config.py`: Centraliza a leitura das chaves de API, baselines de saúde (HRV/Sono) e configurações globais a partir do arquivo de variáveis de ambiente.
  - `intervals_client.py`: Cliente de API unificado para comunicação com a plataforma Intervals.icu.
  - `utils.py`: Funções utilitárias para análise nutricional de treinos, cálculo de status de fadiga (TSB) e disparo de notificações via ntfy.sh.
  - `pms_daily_report.py`: Script para o **Relatório Matinal** (Saúde do dia + Carga acumulada + Detalhe dos treinos prescritos + Análise de hidratação/nutrição).
  - `pms_nightly_report.py`: Script para o **Relatório Noturno** (Fechamento do dia + Execução real vs. Planejado + Análise de overtraining/fadiga).
  - `pms_weekly_planner.py`: Script para o **Planejador Semanal** dinâmico via Gemini IA, integrando o histórico fisiológico real e cálculo preditivo de carga.
- `INSTRUCOES_TREINO_TEMPLATE.md`: O arquivo de referência que serve como "cérebro" fisiológico para a IA, contendo o catálogo de sessões estruturadas, zonas de pace/frequência cardíaca e regras de periodização.
- `MODELO_REVISAO_SEMANAL_TEMPLATE.md`: Modelo utilizado para o log semanal de desempenho.
- `test_weekly_planner.py`: Suite de simulação local do planejador semanal (gera a proposta da IA e simula comutações, enviando apenas notificações de teste sem alterar os treinos no Intervals.icu).
- `simulate_tomorrow.py`: Script auxiliar para simular o comportamento do relatório diário do dia seguinte.
- `generate_report.py`: Script utilitário para gerar relatórios consolidados de carga anual em formato Markdown e gráfico SVG.

---

## 💡 Recursos Inteligentes Implementados

### 1. Modelo Preditivo de Carga (TSB - Form)
*   **Algoritmo MPC:** O planejador semanal utiliza fórmulas de decaimento exponencial de CTL (Fitness - 42 dias) e ATL (Fadiga - 7 dias) para simular o impacto de estresse físico.
*   **Carga Alvo Dinâmica:** O sistema calcula de forma reversa (busca binária) a carga semanal exata necessária para atingir um TSB (Forma) alvo de **-15.0** (prontidão ideal para evolução fisiológica) na segunda-feira seguinte, injetando esse valor como meta para a IA.

### 2. Análise Dinâmica e Estatística de HRV
*   **Média Móvel de 30 Dias:** O sistema calcula a média do HRV do último mês a partir da API.
*   **Classificação Estatística:** O HRV médio da semana passada é comparado com as faixas de normalidade definidas no `.env` do atleta, classificando a prontidão fisiológica como **ABAIXO**, **NA MÉDIA** ou **ACIMA** para guiar a periodização (semana regenerativa ou de intensidade) de forma assertiva.

### 3. Logística de Comutação Ativa (Bike)
*   **Comutação Inteligente:** Para dias em que há treinos de natação, o script insere automaticamente um pedal de ida utilitário para deslocamento (ex: 35 min Z1/Z2).
*   **Mesclagem de Treinos:** Se a IA planejar uma sessão principal de ciclismo de qualidade no mesmo dia, o script **mescla automaticamente** o treino de qualidade com a comutação de volta, evitando treinos triplos ou duplicidade de atividades no Intervals.icu.

---

## ⚙️ Instalação e Configuração Técnica

### Passo 1: Clonar o Repositório e Instalar Dependências
1. Clone este repositório para sua máquina local.
2. Instale as dependências necessárias utilizando o `pip`:
   ```bash
   pip install requests python-dotenv google-generativeai
   ```

### Passo 2: Configurar Variáveis de Ambiente (`.env`)
Copie o arquivo `.env.example` para `.env` e preencha as variáveis correspondentes com suas credenciais:
```bash
cp .env.example .env
```

**Variáveis obrigatórias:**
*   `INTERVALS_API_KEY`: Sua chave de API do Intervals.icu (obtida em *Settings -> API keys*).
*   `INTERVALS_ATHLETE_ID`: Seu ID de atleta (o código com 'i' no link do seu perfil, ex: `i12345`).
*   `GEMINI_API_KEY`: Sua chave do Google Gemini (obtida no Google AI Studio).
*   `NTFY_TOPIC`: Um tópico único e aleatório para receber notificações no aplicativo **ntfy.sh** (disponível para Android/iOS e Web).
*   `ATHLETE_NAME`: Seu nome (para personalização dos cabeçalhos dos relatórios).
*   `BASELINE_HRV`: Sua média padrão de HRV (Variabilidade Cardíaca).
*   `BASELINE_HRV_MIN` / `BASELINE_HRV_MAX`: A faixa de normalidade estatística do seu HRV.
*   `GOAL_SLEEP`: Meta diária de horas de sono.

### Passo 3: Configurar as Instruções de Treino
Crie o arquivo de instruções real copiando o template:
```bash
cp INSTRUCOES_TREINO_TEMPLATE.md INSTRUCOES_TREINO.md
```
Abra o arquivo `INSTRUCOES_TREINO.md` e preencha com:
1. Seu ID de atleta.
2. Suas zonas de intensidade atuais (ritmos de pace para corrida e natação, zonas de batimento cardíaco para bike).
3. Seu calendário de metas e provas alvo.

---

## 🚀 Execução Local

Você pode rodar os scripts localmente para validar a configuração:

1.  **Validar Proposta de Treino (Sem Upload):**
    Rode o script de teste para ver a análise da IA e as sugestões de planilha (com envio de notificação via ntfy.sh):
    ```bash
    python -X utf8 test_weekly_planner.py
    ```
2.  **Enviar Relatório Matinal:**
    ```bash
    python -m health_tracker.pms_daily_report
    ```
3.  **Enviar Relatório Noturno:**
    ```bash
    python -m health_tracker.pms_nightly_report
    ```
4.  **Executar Planejador Semanal em Produção (Cria os treinos no Intervals.icu):**
    ```bash
    python -m health_tracker.pms_weekly_planner
    ```
5.  **Gerar Relatório de Carga Consolidado:**
    ```bash
    # Gera o relatório do ano corrente
    python generate_report.py
    
    # Gera o relatório de um ano específico
    python generate_report.py --ano 2026
    ```
    Os relatórios em Markdown e os gráficos SVG serão salvos na pasta local `reports/`.

---

## ☁️ Automação via GitHub Actions

O ecossistema está pronto para ser executado de forma totalmente serverless utilizando os workflows do GitHub Actions configurados na pasta `.github/workflows/`:

*   **Relatório Matinal:** Executado diariamente às 06:30 BRT.
*   **Relatório Noturno:** Executado diariamente às 20:30 BRT.
*   **Planejador Semanal:** Executado aos domingos às 18:00 BRT.

### Como configurar no GitHub:
1. No seu repositório no GitHub, acesse **Settings > Secrets and variables > Actions**.
2. Crie os seguintes **Repository Secrets**:
   *   `INTERVALS_API_KEY`
   *   `INTERVALS_ATHLETE_ID`
   *   `GEMINI_API_KEY`
   *   `NTFY_TOPIC`
   *   `ATHLETE_NAME`
   *   `BASELINE_HRV`
   *   `BASELINE_HRV_MIN`
   *   `BASELINE_HRV_MAX`
   *   `GOAL_SLEEP`
   *   `GEMINI_MODEL` (opcional, padrão: `gemini-2.5-flash`)
   *   `TIMEZONE` (opcional, padrão: `America/Sao_Paulo`)

*Os fluxos usarão essas variáveis automaticamente nas execuções cron.*
