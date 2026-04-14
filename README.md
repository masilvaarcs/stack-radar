<div align="center">

# 🔭 Stack Radar

**Analisa currículos em PDF e detecta competências profissionais em tempo real**

`PDF` → `PyMuPDF` → `RabbitMQ` → `WebSocket` → `Live UI`

> Compatível com PDFs do LinkedIn, Word, Canva e qualquer plataforma — mapeia seções em PT-BR e EN.

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![RabbitMQ](https://img.shields.io/badge/RabbitMQ-3.13-FF6600?style=flat-square&logo=rabbitmq&logoColor=white)](https://rabbitmq.com)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=flat-square&logo=docker&logoColor=white)](https://docker.com)
[![Railway](https://img.shields.io/badge/Deploy-Railway-0B0D0E?style=flat-square&logo=railway&logoColor=white)](https://railway.com)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](LICENSE)

<br>

### 🚀 [Acesse o App ao Vivo →  https://heroic-renewal-linkedinrepo.up.railway.app/](https://heroic-renewal-linkedinrepo.up.railway.app/)

<br>

<table>
<tr>
<td align="center" width="120"><b>📄</b><br><sub>PDF Upload</sub></td>
<td align="center" width="40">→</td>
<td align="center" width="120"><b>⚙️</b><br><sub>PyMuPDF</sub></td>
<td align="center" width="40">→</td>
<td align="center" width="120"><b>🐇</b><br><sub>RabbitMQ</sub></td>
<td align="center" width="40">→</td>
<td align="center" width="120"><b>⚡</b><br><sub>WebSocket</sub></td>
<td align="center" width="40">→</td>
<td align="center" width="120"><b>💡</b><br><sub>Live UI</sub></td>
</tr>
</table>

</div>

---

## 💡 O que é?

Upload de currículo em PDF → extração de texto → detecção automática de **228 competências em 8 áreas profissionais** → processamento via **message broker real** → exibição de exemplos de código e curiosidades ao vivo no browser.

Cada stack detectada vira uma **mensagem AMQP** que é publicada, enfileirada, consumida e entregue via WebSocket — tudo visível em tempo real. Ao clicar em qualquer stack, um **code viewer** moderno exibe um exemplo de código real e uma **curiosidade** sobre a tecnologia.

Além da detecção de competências, o sistema inclui um **analisador ATS** que pontua o currículo em 6 dimensões (seções, verbos de ação, métricas, contato, extensão, competências) com score de 0 a 100 e sugestões de melhoria.

> **LinkedIn PDF vs CV otimizado:** O sistema reconhece tanto seções em PT-BR ("Experiência Profissional", "Stack Técnica") quanto seções em inglês do LinkedIn PDF ("Top Skills", "About", "Licenses & Certifications"). Os scores tendem a diferir — use o dashboard para comparar e otimizar.

---

## 🏗️ Arquitetura

```
Browser
  │  POST /upload (PDF)
  ▼
FastAPI (Python)
  │  PyMuPDF extrai texto
  │  detecta stacks → retorna session_id
  │
  │  POST /processar/{session_id}
  ▼
pika (Producer)
  │  publica 1 mensagem por stack
  ▼
RabbitMQ Broker
  │  fila: stack_radar  (durable=True)
  ▼
pika (Consumer — thread dedicada)
  │  basic_qos(prefetch=1) — uma por vez
  │  basic_ack manual após processar
  ▼
FastAPI WebSocket (/ws/{session_id})
  │  envia JSON ao browser em tempo real
  ▼
Browser
  └── exibe stack processada + exemplo de código
```

---

## 🛠️ Tech Stack

| Camada | Tecnologia | Papel |
|--------|-----------|-------|
| **Backend** | FastAPI + Uvicorn | API REST + WebSocket server |
| **Mensageria** | RabbitMQ + pika | Broker AMQP, producer/consumer |
| **Extração** | PyMuPDF (fitz) | Leitura e parsing de PDF |
| **Frontend** | HTML + CSS + JS | UI responsiva com terminal live |
| **Infra** | Docker Compose | Orquestração local |
| **Deploy** | Railway | Cloud com Dockerfile |

---

## 🚀 Quick Start

### 🌐 App Live (sem instalar nada)

> **https://heroic-renewal-linkedinrepo.up.railway.app/**
>
> Escolha um dos 5 demos ou faça upload do seu currículo em PDF.

### Com Docker Compose (recomendado)

```bash
git clone https://github.com/masilvaarcs/stack-radar.git
cd stack-radar
docker compose up --build
```

| Serviço | URL |
|---------|-----|
| **App** | http://localhost:8000 |
| **RabbitMQ UI** | http://localhost:15672 (guest/guest) |
| **API Docs** | http://localhost:8000/docs |

### Sem Docker

```bash
# 1. RabbitMQ
docker run -d --name rabbit -p 5672:5672 -p 15672:15672 rabbitmq:3-management

# 2. Backend
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

---

## 📡 API Endpoints

| Método | Rota | Descrição |
|--------|------|-----------|
| `GET` | `/health` | Health check |
| `GET` | `/stacks` | Lista todas as 228 competências |
| `GET` | `/stack/{id}` | Exemplo completo + curiosidade de uma stack |
| `POST` | `/upload` | Recebe PDF, detecta stacks |
| `POST` | `/processar/{session_id}` | Publica na fila e inicia consumer |
| `WS` | `/ws/{session_id}` | WebSocket — eventos em tempo real |

---

## 🎨 Features da UI

- **Pipeline visual** — diagrama animado mostra cada etapa em tempo real (PDF → PyMuPDF → RabbitMQ → WebSocket → UI)
- **Terminal live** — log completo do pipeline com timestamps e emojis coloridos
- **Stacks grid** — cards coloridos com filtro por categoria (Backend, Frontend, DevOps, Database...)
- **Code Viewer** — clique em qualquer stack para ver um exemplo de código real com syntax highlight
- **💡 Você sabia?** — curiosidade histórica/técnica sobre cada tecnologia
- **Modo demo** — funciona 100% offline, simulando o pipeline completo com stacks de exemplo
- **Dark/Light theme** — toggle com transição suave e persistência
- **Drag & drop** — arraste PDF diretamente na upload zone
- **Dashboard ATS** — score de 0-100 com 6 dimensões, sugestões priorizadas por impacto
- **Multi-formato** — reconhece seções em PT-BR e EN (incluindo PDFs exportados do LinkedIn)
- **5 demos interativos** — TI, Saúde, Design, Educação e Finanças, sem precisar de PDF

### 🎯 Demos Interativos (v2.2)

| Perfil | Área | Stacks | Tipo de Conteúdo |
|--------|------|--------|-----------------|
| 💻 Dev Full-Stack Sênior | TI | 17 | Código real (Python, React, Docker...) |
| 🏥 Profissional de Saúde | Saúde | 5 | Protocolos (SAE, NRS-2002, Biossegurança...) |
| 🎨 Designer / UX | Artes & Design | 5 | Frameworks (Design Tokens, WCAG, Wireframes...) |
| 📚 Professor / Educador | Educação | 5 | Metodologias (BNCC, PBL, Sala Invertida, PEI...) |
| 💰 Analista Financeiro | Finanças | 5 | Análises (DRE, DCF, Fluxo de Caixa, Tributário...) |

---

## 🐇 Como funciona o RabbitMQ

```python
# Producer — publica uma mensagem por stack detectada
ch.basic_publish(
    exchange="",
    routing_key="stack_radar",
    body=json.dumps(mensagem),
    properties=pika.BasicProperties(delivery_mode=2),  # persistente
)

# Consumer — processa uma por vez (prefetch=1)
ch.basic_qos(prefetch_count=1)
ch.basic_consume(queue="stack_radar", on_message_callback=callback)

# Callback — envia ao WebSocket no loop asyncio
def callback(ch, method, properties, body):
    asyncio.run_coroutine_threadsafe(ws_manager.send(...), loop)
    ch.basic_ack(method.delivery_tag)  # ACK manual
```

> **Por que é mensageria real?** O broker AMQP armazena mensagens (`durable=True`), o consumer usa `prefetch_count=1`, o ACK é manual, e producer/consumer rodam em threads independentes.

---

## 🎯 Competências Detectadas

228 competências em 8 áreas profissionais:

| Área | Qtd | Exemplos |
|------|-----|----------|
| ⚙️ TI | 127 | Python, React, Docker, AWS, SOLID, Design Patterns, GitHub Copilot |
| 🏥 Saúde | 25 | Enfermagem, Fisioterapia, Nutrição, Farmácia |
| 📚 Educação | 17 | Pedagogia, EAD, Alfabetização, Libras |
| 🎨 Artes e Design | 18 | UI/UX, Figma, Motion Design, Fotografia |
| 📣 Marketing | 12 | SEO, Tráfego Pago, Inbound, CRM |
| 💰 Finanças | 14 | Contabilidade, Auditoria, FP&A, Valuation |
| 🏗️ Engenharia | 9 | Civil, Mecânica, Elétrica, Automação |
| 📦 Logística | 6 | WMS, ERP, Supply Chain, Última Milha |

---

## ⚙️ Variáveis de Ambiente

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `RABBITMQ_URL` | `amqp://guest:guest@localhost:5672/` | URL do broker AMQP |
| `PORT` | `8000` | Porta do servidor (Railway define automaticamente) |

---

## 📁 Estrutura

```
stack-radar/
├── backend/
│   ├── main.py              ← FastAPI + RabbitMQ + WebSocket + ATS Engine
│   ├── test_main.py         ← 235 testes unitários (pytest)
│   ├── requirements.txt
│   └── Dockerfile           ← build local
├── tabelas/
│   └── stacks_taxonomy.json ← 228 competências em 8 áreas + config ATS
├── docs/
│   ├── SHOWCASE.html        ← Showcase visual do projeto (abra no browser)
│   ├── LINKEDIN_POST.md     ← Publicação LinkedIn pronta para uso
│   ├── card_config.json     ← config do evidence card
│   ├── evidencia-card.svg   ← card de evidência (README)
│   └── imagens/             ← 13 screenshots do app em ação
├── frontend/
│   └── index.html           ← UI completa (HTML + CSS + JS)
├── Dockerfile               ← build produção (Railway)
├── docker-compose.yml
├── railway.json
└── README.md
```

---

## ☁️ Deploy na Railway

1. Fork/clone este repositório no GitHub
2. Acesse [railway.com](https://railway.com) → **New Project** → **GitHub Repository**
3. Selecione `stack-radar`
4. Adicione um serviço **RabbitMQ** (Database → RabbitMQ)
5. Configure `RABBITMQ_URL` nas variáveis do backend
6. **Generate Domain** na aba Settings → Networking (porta **8000**)

---

## 📸 Evidências de Execução

<p align="center">
  <img src="docs/evidencia-card.svg" alt="Evidence Card" width="840"/>
</p>

### Screenshots do App

| Screenshot | Descrição |
|-----------|-----------|
| ![Header](docs/imagens/01-header-pipeline-visual.png) | Header com pipeline visual animado |
| ![5 Demos](docs/imagens/02-upload-zone-5-demos.png) | Upload zone + 5 cards de demo |
| ![ATS Dashboard](docs/imagens/04-demo-ti-ats-dashboard.png) | Dashboard ATS: score 72 + 6 dimensões |
| ![Stacks Grid](docs/imagens/06-demo-ti-stacks-grid-17.png) | Grid de 17 stacks TI com filtros |
| ![Code Viewer](docs/imagens/07-demo-ti-code-viewer-python.png) | Code Viewer Python + "Você Sabia?" |
| ![Educação](docs/imagens/10-demo-educacao-selecionado.png) | Demo Educação — multi-área |
| ![PDF Real](docs/imagens/09-upload-pdf-real-resultado.png) | Resultado de CV real: 10 stacks |

> Veja todas as 13 screenshots em [`docs/imagens/`](docs/imagens/)

---

<div align="center">

Desenvolvido por **Marcos Silva**

[![Portfolio](https://img.shields.io/badge/Portfólio-masilvaarcs-F59E0B?style=for-the-badge&logo=googlechrome&logoColor=white)](https://masilvaarcs.github.io/portfolio-hub)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-marcosprogramador-0A66C2?style=for-the-badge&logo=linkedin&logoColor=white)](https://www.linkedin.com/in/marcosprogramador)

<sub>stack-radar · fastapi · pika · rabbitmq · websocket · 2026</sub>

</div>
