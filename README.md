# 🔭 Stack Radar
**PDF → PyMuPDF → RabbitMQ → WebSocket → Live UI**

Analisa currículos em PDF, detecta stacks tecnológicas e as processa via RabbitMQ em tempo real, exibindo exemplos de código ao vivo no browser.

---

## Arquitetura real (sem simulação)

```
Browser
  │  POST /upload (PDF)
  ▼
FastAPI (Python)
  │  PyMuPDF extrai texto
  │  detecta stacks
  │  retorna session_id
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
asyncio.run_coroutine_threadsafe
  │  envia evento para o loop principal
  ▼
FastAPI WebSocket (/ws/{session_id})
  │  envia JSON ao browser em tempo real
  ▼
Browser
  └── exibe stack processada + exemplo de código
```

---

## Rodar local (recomendado para testar)

### Pré-requisitos
- Docker + Docker Compose
- Python 3.12+

### 1. Subir tudo com Docker Compose

```bash
git clone https://github.com/seu-usuario/stack-radar
cd stack-radar
docker-compose up --build
```

Acesse: **http://localhost:8000**
Painel RabbitMQ: **http://localhost:15672** (guest/guest)

---

### 2. Rodar manualmente (sem Docker)

**RabbitMQ:**
```bash
docker run -d --name rabbit \
  -p 5672:5672 -p 15672:15672 \
  rabbitmq:3-management
```

**Backend:**
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

**Frontend:** abra `frontend/index.html` no browser
(ou configure o CORS para servir estático pelo FastAPI)

---

## Deploy na Railway (backend + RabbitMQ)

A Vercel **não** suporta WebSocket nem processos Python long-running.
Use a **Railway** para o backend (grátis, suporta Docker):

### Passo a passo

1. Crie conta em [railway.app](https://railway.app)

2. No Railway, crie um novo projeto:
   - **Adicione um serviço RabbitMQ** (plugin nativo da Railway)
   - Copie a `RABBITMQ_URL` gerada

3. **Deploy do backend:**
   ```bash
   # Instale o Railway CLI
   npm install -g @railway/cli
   railway login
   railway init
   railway up
   ```

4. **Defina a variável de ambiente:**
   ```
   RABBITMQ_URL=amqp://user:pass@host.railway.app:5672/
   ```

5. A Railway gera uma URL pública tipo:
   `https://stack-radar-api.up.railway.app`

6. No `frontend/index.html`, atualize a linha:
   ```js
   const API = 'https://stack-radar-api.up.railway.app';
   ```

7. **Frontend na Vercel:**
   ```bash
   npm install -g vercel
   cd frontend
   vercel --prod
   ```

---

## Variáveis de ambiente

| Variável       | Padrão                              | Descrição              |
|---------------|-------------------------------------|------------------------|
| `RABBITMQ_URL`| `amqp://guest:guest@localhost:5672/`| URL do broker AMQP     |

---

## Endpoints da API

| Método | Rota                    | Descrição                                    |
|--------|-------------------------|----------------------------------------------|
| GET    | `/health`               | Health check                                 |
| GET    | `/stacks`               | Lista todas as stacks no banco               |
| GET    | `/stack/{id}`           | Retorna exemplo completo de uma stack        |
| POST   | `/upload`               | Recebe PDF, detecta stacks, retorna session_id|
| POST   | `/processar/{session_id}`| Publica na fila e inicia consumer           |
| WS     | `/ws/{session_id}`      | WebSocket — recebe eventos em tempo real     |

---

## Stacks detectadas

Python · Flask · FastAPI · Django · React · Angular · TypeScript · JavaScript · Node.js · Docker · PostgreSQL · SQL · C# · .NET · RabbitMQ · Redis · Pandas

---

## Como funciona o RabbitMQ neste projeto

```python
# Producer — publica uma mensagem por stack detectada
ch.basic_publish(
    exchange="",
    routing_key="stack_radar",    # nome da fila
    body=json.dumps(mensagem),
    properties=pika.BasicProperties(delivery_mode=2),  # persistente
)

# Consumer — processa uma por vez (prefetch=1)
ch.basic_qos(prefetch_count=1)
ch.basic_consume(queue="stack_radar", on_message_callback=callback)

# Callback — envia ao WebSocket no loop asyncio
def callback(ch, method, properties, body):
    asyncio.run_coroutine_threadsafe(ws_manager.send(...), loop)
    ch.basic_ack(method.delivery_tag)    # ACK manual
```

**Por que isso é RabbitMQ real:**
- O broker AMQP recebe e armazena as mensagens (`durable=True`)
- O consumer usa `prefetch_count=1` — processa uma mensagem por vez
- O `basic_ack` é manual — se o consumer cair, a mensagem volta para a fila
- Producer e consumer rodam em contextos independentes (thread separada)

---

## Estrutura do projeto

```
stack-radar/
├── backend/
│   ├── main.py            ← FastAPI + RabbitMQ + WebSocket
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   └── index.html         ← UI completa (HTML + CSS + JS)
├── docker-compose.yml
└── README.md
```

---

Desenvolvido por **Marcos Silva** — [Portfólio](https://masilvaarcs.github.io/portfolio-hub) · [LinkedIn](https://www.linkedin.com/in/marcosprogramador)
