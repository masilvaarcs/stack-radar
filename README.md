<div align="center">

# 🔭 Stack Radar

**Analisa currículos em PDF e detecta stacks tecnológicas em tempo real**

`PDF` → `PyMuPDF` → `RabbitMQ` → `WebSocket` → `Live UI`

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![RabbitMQ](https://img.shields.io/badge/RabbitMQ-3.13-FF6600?style=flat-square&logo=rabbitmq&logoColor=white)](https://rabbitmq.com)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=flat-square&logo=docker&logoColor=white)](https://docker.com)
[![Railway](https://img.shields.io/badge/Deploy-Railway-0B0D0E?style=flat-square&logo=railway&logoColor=white)](https://railway.com)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](LICENSE)

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

Upload de currículo em PDF → extração de texto → detecção automática de stacks → processamento via **message broker real** → exibição de exemplos de código ao vivo no browser.

Cada stack detectada vira uma **mensagem AMQP** que é publicada, enfileirada, consumida e entregue via WebSocket — tudo visível em tempo real.

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
| `GET` | `/stacks` | Lista todas as 17 stacks |
| `GET` | `/stack/{id}` | Exemplo completo de uma stack |
| `POST` | `/upload` | Recebe PDF, detecta stacks |
| `POST` | `/processar/{session_id}` | Publica na fila e inicia consumer |
| `WS` | `/ws/{session_id}` | WebSocket — eventos em tempo real |

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

## 🎯 Stacks Detectadas

<div align="center">

`Python` · `Flask` · `FastAPI` · `Django` · `React` · `Angular` · `TypeScript` · `JavaScript` · `Node.js` · `Docker` · `PostgreSQL` · `SQL` · `C#` · `.NET` · `RabbitMQ` · `Redis` · `Pandas`

</div>

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
│   ├── main.py              ← FastAPI + RabbitMQ + WebSocket
│   ├── requirements.txt
│   └── Dockerfile           ← build local
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

<div align="center">

Desenvolvido por **Marcos Silva**

[![Portfolio](https://img.shields.io/badge/Portfólio-masilvaarcs-F59E0B?style=for-the-badge&logo=googlechrome&logoColor=white)](https://masilvaarcs.github.io/portfolio-hub)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-marcosprogramador-0A66C2?style=for-the-badge&logo=linkedin&logoColor=white)](https://www.linkedin.com/in/marcosprogramador)

<sub>stack-radar · fastapi · pika · rabbitmq · websocket · 2025</sub>

</div>
