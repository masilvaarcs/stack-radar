"""
Stack Radar — Backend
FastAPI + WebSocket + RabbitMQ (pika) + PyMuPDF

Fluxo real:
  1. POST /upload  → recebe PDF, extrai texto, detecta stacks
  2. Producer      → publica cada stack na fila RabbitMQ
  3. Consumer      → lê da fila, envia via WebSocket ao browser
  4. Browser       → recebe eventos em tempo real e exibe
"""

import os, json, re, asyncio, threading, uuid, logging
from datetime import datetime
from pathlib import Path
from contextlib import asynccontextmanager

import fitz                         # PyMuPDF
import pika                         # RabbitMQ client
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("stack-radar")

# ─────────────────────────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────────────────────────
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
QUEUE_NAME   = "stack_radar"
MAX_PDF_MB   = 10

# ─────────────────────────────────────────────────────────────
#  BANCO DE STACKS COM EXEMPLOS REAIS
# ─────────────────────────────────────────────────────────────
STACK_DB: dict = {
    "python": {
        "name": "Python", "icon": "🐍", "color": "#3776AB", "category": "Backend",
        "description": "Linguagem versátil para backend, data science e automação.",
        "example_title": "API REST com Flask",
        "example": """\
from flask import Flask, jsonify, request

app = Flask(__name__)
tarefas = []

@app.route("/tarefas", methods=["GET"])
def listar():
    return jsonify(tarefas)

@app.route("/tarefas", methods=["POST"])
def criar():
    dado = request.get_json()
    tarefa = {"id": len(tarefas) + 1, "titulo": dado["titulo"], "feita": False}
    tarefas.append(tarefa)
    return jsonify(tarefa), 201

if __name__ == "__main__":
    app.run(debug=True)"""
    },
    "flask": {
        "name": "Flask", "icon": "🌶️", "color": "#44b78b", "category": "Backend",
        "description": "Microframework web leve e flexível para Python.",
        "example_title": "Blueprint com autenticação JWT",
        "example": """\
from flask import Flask, Blueprint, request, jsonify
from functools import wraps
import jwt, datetime

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")
SECRET  = "minha_chave"

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get("Authorization", "").removeprefix("Bearer ")
        if not token:
            return jsonify({"erro": "Token ausente"}), 401
        try:
            dados = jwt.decode(token, SECRET, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            return jsonify({"erro": "Token expirado"}), 401
        return f(dados, *args, **kwargs)
    return decorated

@auth_bp.route("/login", methods=["POST"])
def login():
    body = request.get_json()
    if body.get("senha") == "1234":
        token = jwt.encode(
            {"user": body["usuario"],
             "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=1)},
            SECRET
        )
        return jsonify({"token": token})
    return jsonify({"erro": "Credenciais inválidas"}), 401"""
    },
    "fastapi": {
        "name": "FastAPI", "icon": "⚡", "color": "#009688", "category": "Backend",
        "description": "Framework moderno e rápido para APIs com tipagem Python.",
        "example_title": "CRUD assíncrono com Pydantic",
        "example": """\
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional

app = FastAPI(title="Minha API", version="1.0.0")

class Item(BaseModel):
    nome: str
    preco: float
    disponivel: bool = True
    descricao: Optional[str] = None

db: dict[int, Item] = {}
_id = 0

@app.post("/items/", status_code=201)
async def criar(item: Item) -> Item:
    global _id; _id += 1
    db[_id] = item
    return item

@app.get("/items/{item_id}")
async def buscar(item_id: int) -> Item:
    if item_id not in db:
        raise HTTPException(404, "Não encontrado")
    return db[item_id]

@app.put("/items/{item_id}")
async def atualizar(item_id: int, item: Item):
    if item_id not in db:
        raise HTTPException(404, "Não encontrado")
    db[item_id] = item
    return {"status": "atualizado"}"""
    },
    "django": {
        "name": "Django", "icon": "🎸", "color": "#44B78B", "category": "Backend",
        "description": "Framework full-stack com ORM, admin e autenticação incluídos.",
        "example_title": "Model + View com Django ORM",
        "example": """\
# models.py
from django.db import models

class Produto(models.Model):
    class Categoria(models.TextChoices):
        ELETRONICO = "EL", "Eletrônico"
        VESTUARIO  = "VE", "Vestuário"

    nome      = models.CharField(max_length=200)
    preco     = models.DecimalField(max_digits=10, decimal_places=2)
    estoque   = models.IntegerField(default=0)
    categoria = models.CharField(max_length=2, choices=Categoria.choices)
    criado_em = models.DateTimeField(auto_now_add=True)

    @property
    def disponivel(self):
        return self.estoque > 0

# views.py
from django.http import JsonResponse
from django.views import View
from .models import Produto

class ProdutoView(View):
    def get(self, request, pk=None):
        if pk:
            try:
                p = Produto.objects.get(pk=pk)
                return JsonResponse({"nome": p.nome, "preco": str(p.preco)})
            except Produto.DoesNotExist:
                return JsonResponse({"erro": "Não encontrado"}, status=404)
        qs = list(Produto.objects.values("id","nome","preco","estoque"))
        return JsonResponse({"produtos": qs})"""
    },
    "react": {
        "name": "React", "icon": "⚛️", "color": "#61DAFB", "category": "Frontend",
        "description": "Biblioteca para construção de interfaces declarativas e reativas.",
        "example_title": "Hook useFetch + Context API",
        "example": """\
import { useState, useEffect, useCallback, createContext, useContext } from "react";

// Context de autenticação
const AuthCtx = createContext(null);

export function AuthProvider({ children }) {
    const [user, setUser] = useState(null);
    const login  = (u) => setUser(u);
    const logout = ()  => setUser(null);
    return <AuthCtx.Provider value={{ user, login, logout }}>{children}</AuthCtx.Provider>;
}
export const useAuth = () => useContext(AuthCtx);

// Hook de fetch reutilizável
export function useFetch(url) {
    const [dados, setDados]     = useState(null);
    const [loading, setLoading] = useState(true);
    const [erro, setErro]       = useState(null);

    const buscar = useCallback(async () => {
        setLoading(true); setErro(null);
        try {
            const res = await fetch(url);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            setDados(await res.json());
        } catch (e) { setErro(e.message); }
        finally { setLoading(false); }
    }, [url]);

    useEffect(() => { buscar(); }, [buscar]);
    return { dados, loading, erro, refetch: buscar };
}"""
    },
    "angular": {
        "name": "Angular", "icon": "🔺", "color": "#DD0031", "category": "Frontend",
        "description": "Framework completo com DI, RxJS e roteamento integrados.",
        "example_title": "Service + RxJS + Component",
        "example": """\
// produto.service.ts
import { Injectable } from "@angular/core";
import { HttpClient } from "@angular/common/http";
import { Observable, catchError, of, BehaviorSubject } from "rxjs";

export interface Produto { id: number; nome: string; preco: number; }

@Injectable({ providedIn: "root" })
export class ProdutoService {
    private readonly api = "https://api.exemplo.com";
    private _produtos$ = new BehaviorSubject<Produto[]>([]);
    readonly produtos$ = this._produtos$.asObservable();

    constructor(private http: HttpClient) {}

    carregar(): void {
        this.http.get<Produto[]>(`${this.api}/produtos`).pipe(
            catchError(() => of([]))
        ).subscribe(lista => this._produtos$.next(lista));
    }

    criar(produto: Omit<Produto, "id">): Observable<Produto> {
        return this.http.post<Produto>(`${this.api}/produtos`, produto);
    }
}"""
    },
    "typescript": {
        "name": "TypeScript", "icon": "🔷", "color": "#3178C6", "category": "Frontend",
        "description": "Superset tipado do JavaScript para projetos escaláveis.",
        "example_title": "Repositório genérico + Decorators",
        "example": """\
interface Entidade { id: number; }

class Repositorio<T extends Entidade> {
    private itens = new Map<number, T>();

    salvar(item: T): T {
        this.itens.set(item.id, item);
        return item;
    }
    buscarPorId(id: number): T | undefined {
        return this.itens.get(id);
    }
    listarTodos(): T[] {
        return [...this.itens.values()];
    }
    remover(id: number): boolean {
        return this.itens.delete(id);
    }
    filtrar(pred: (item: T) => boolean): T[] {
        return this.listarTodos().filter(pred);
    }
}

interface Usuario extends Entidade {
    nome: string; email: string; ativo: boolean;
}

const repo = new Repositorio<Usuario>();
repo.salvar({ id: 1, nome: "Marcos", email: "marcos@dev.com", ativo: true });
repo.salvar({ id: 2, nome: "Ana",    email: "ana@dev.com",    ativo: false });

const ativos = repo.filtrar(u => u.ativo);
console.log(ativos.map(u => u.nome)); // ["Marcos"]"""
    },
    "javascript": {
        "name": "JavaScript", "icon": "🟡", "color": "#F7DF1E", "category": "Frontend",
        "description": "Linguagem universal da web, client e server-side.",
        "example_title": "EventBus + Promise.all",
        "example": """\
// EventBus customizado com tipagem JSDoc
class EventBus {
    #handlers = new Map();

    on(evento, handler) {
        if (!this.#handlers.has(evento)) this.#handlers.set(evento, []);
        this.#handlers.get(evento).push(handler);
        return () => this.off(evento, handler); // retorna unsubscribe
    }
    off(evento, handler) {
        const lista = this.#handlers.get(evento) ?? [];
        this.#handlers.set(evento, lista.filter(h => h !== handler));
    }
    emit(evento, dados) {
        (this.#handlers.get(evento) ?? []).forEach(h => h(dados));
    }
}

// Busca paralela com Promise.all
async function carregarDashboard(userId) {
    const [usuario, pedidos, notifs] = await Promise.all([
        fetch(`/api/users/${userId}`).then(r => r.json()),
        fetch(`/api/orders?user=${userId}`).then(r => r.json()),
        fetch(`/api/notifs/${userId}`).then(r => r.json()),
    ]);
    return { usuario, pedidos, notifs };
}

const bus = new EventBus();
const unsub = bus.on("pedido:criado", e => console.log("Novo pedido:", e.id));
bus.emit("pedido:criado", { id: 42, valor: 149.90 });
unsub();"""
    },
    "node": {
        "name": "Node.js", "icon": "🟢", "color": "#339933", "category": "Backend",
        "description": "Runtime JavaScript server-side baseado no V8.",
        "example_title": "Express + Zod + Middleware",
        "example": """\
import express from "express";
import { z } from "zod";

const app = express();
app.use(express.json());

// Schema de validação
const ProdutoSchema = z.object({
    nome:      z.string().min(2).max(100),
    preco:     z.number().positive(),
    categoria: z.enum(["eletronico", "vestuario", "alimento"]),
    estoque:   z.number().int().nonnegative(),
});

// Middleware de validação genérico
const validar = (schema) => (req, res, next) => {
    const r = schema.safeParse(req.body);
    if (!r.success)
        return res.status(400).json({ erro: "Dados inválidos", detalhes: r.error.flatten() });
    req.body = r.data;
    next();
};

const produtos = new Map();
let nextId = 1;

app.get("/produtos", (req, res) => {
    const lista = [...produtos.values()];
    res.json({ total: lista.length, produtos: lista });
});

app.post("/produtos", validar(ProdutoSchema), (req, res) => {
    const p = { id: nextId++, ...req.body };
    produtos.set(p.id, p);
    res.status(201).json(p);
});

app.listen(3000, () => console.log("🚀 :3000"));"""
    },
    "docker": {
        "name": "Docker", "icon": "🐳", "color": "#2496ED", "category": "DevOps",
        "description": "Containerização de aplicações para ambientes reproduzíveis.",
        "example_title": "Dockerfile + docker-compose completo",
        "example": """\
# Dockerfile — imagem de produção otimizada
FROM python:3.12-slim AS base
WORKDIR /app

# Instala dependências (camada de cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN useradd -m appuser && chown -R appuser /app
USER appuser
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

---
# docker-compose.yml
version: "3.9"
services:
  api:
    build: .
    ports: ["8000:8000"]
    environment:
      RABBITMQ_URL: amqp://guest:guest@rabbitmq:5672/
      DATABASE_URL: postgresql://user:pass@db:5432/mydb
    depends_on: { rabbitmq: { condition: service_healthy }, db: { condition: service_healthy } }

  rabbitmq:
    image: rabbitmq:3-management
    ports: ["5672:5672", "15672:15672"]
    healthcheck:
      test: ["CMD", "rabbitmq-diagnostics", "ping"]
      interval: 10s; timeout: 5s; retries: 5

  db:
    image: postgres:16-alpine
    environment: { POSTGRES_USER: user, POSTGRES_PASSWORD: pass, POSTGRES_DB: mydb }
    volumes: [pgdata:/var/lib/postgresql/data]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U user"]
      interval: 5s; timeout: 3s; retries: 5

volumes:
  pgdata:"""
    },
    "postgresql": {
        "name": "PostgreSQL", "icon": "🐘", "color": "#336791", "category": "Database",
        "description": "Banco relacional robusto com suporte a JSON, window functions e CTEs.",
        "example_title": "Window Functions + CTE avançado",
        "example": """\
-- Ranking de vendas por mês com variação e quartil
WITH vendas AS (
    SELECT
        vendedor_id,
        DATE_TRUNC('month', data_venda) AS mes,
        SUM(valor_total)                AS total,
        COUNT(*)                        AS qtd
    FROM pedidos
    WHERE status = 'concluido'
    GROUP BY vendedor_id, DATE_TRUNC('month', data_venda)
),
ranked AS (
    SELECT
        v.nome,
        vm.mes,
        vm.total,
        vm.qtd,
        RANK()   OVER (PARTITION BY vm.mes ORDER BY vm.total DESC) AS pos,
        NTILE(4) OVER (PARTITION BY vm.mes ORDER BY vm.total DESC) AS quartil,
        LAG(vm.total) OVER (
            PARTITION BY vm.vendedor_id ORDER BY vm.mes
        ) AS total_anterior
    FROM vendas vm
    JOIN vendedores v ON v.id = vm.vendedor_id
)
SELECT
    nome, TO_CHAR(mes, 'MM/YYYY') AS mes,
    total, qtd, pos, quartil,
    ROUND((total - total_anterior) / NULLIF(total_anterior,0) * 100, 1) AS var_pct
FROM ranked
WHERE pos <= 5
ORDER BY mes DESC, pos;"""
    },
    "sql": {
        "name": "SQL", "icon": "🗄️", "color": "#E38C00", "category": "Database",
        "description": "Linguagem padrão para consulta e manipulação de bancos relacionais.",
        "example_title": "JOIN complexo com segmentação de clientes",
        "example": """\
-- Relatório de clientes com segmentação e recência
SELECT
    c.id, c.nome, c.email,
    COUNT(p.id)         AS total_pedidos,
    SUM(p.valor_total)  AS receita_total,
    AVG(p.valor_total)  AS ticket_medio,
    MAX(p.data_pedido)  AS ultimo_pedido,
    DATEDIFF(NOW(), MAX(p.data_pedido)) AS dias_sem_comprar,
    CASE
        WHEN COUNT(p.id) >= 10                           THEN 'VIP'
        WHEN COUNT(p.id) >=  5                           THEN 'Fiel'
        WHEN DATEDIFF(NOW(), MAX(p.data_pedido)) <= 30   THEN 'Recente'
        ELSE 'Em risco'
    END AS segmento
FROM clientes c
LEFT JOIN pedidos p
    ON  p.cliente_id = c.id
    AND p.status     != 'cancelado'
    AND p.data_pedido >= DATE_SUB(NOW(), INTERVAL 12 MONTH)
WHERE c.ativo = 1
GROUP BY c.id, c.nome, c.email
HAVING COUNT(p.id) > 0
ORDER BY receita_total DESC;"""
    },
    "csharp": {
        "name": "C#", "icon": "💜", "color": "#68217A", "category": "Backend",
        "description": "Linguagem orientada a objetos da Microsoft para .NET.",
        "example_title": "Repository Pattern + ASP.NET Core",
        "example": """\
// IRepository.cs — interface genérica
public interface IRepository<T> where T : class
{
    Task<IEnumerable<T>> GetAllAsync();
    Task<T?> GetByIdAsync(int id);
    Task<T>  CreateAsync(T entity);
    Task     DeleteAsync(int id);
}

// PedidoRepository.cs
public class PedidoRepository(AppDbContext ctx) : IRepository<Pedido>
{
    public async Task<IEnumerable<Pedido>> GetAllAsync() =>
        await ctx.Pedidos
            .Include(p => p.Cliente)
            .Include(p => p.Itens)
            .OrderByDescending(p => p.DataCriacao)
            .ToListAsync();

    public async Task<Pedido> CreateAsync(Pedido p)
    {
        p.DataCriacao = DateTime.UtcNow;
        ctx.Pedidos.Add(p);
        await ctx.SaveChangesAsync();
        return p;
    }
}

// PedidoController.cs
[ApiController, Route("api/[controller]")]
public class PedidoController(IRepository<Pedido> repo) : ControllerBase
{
    [HttpGet] public async Task<IActionResult> Get() => Ok(await repo.GetAllAsync());

    [HttpPost]
    public async Task<IActionResult> Post(Pedido p) =>
        CreatedAtAction(nameof(Get), await repo.CreateAsync(p));
}"""
    },
    "dotnet": {
        "name": ".NET", "icon": "🟣", "color": "#512BD4", "category": "Backend",
        "description": "Plataforma Microsoft para aplicações modernas e de alta performance.",
        "example_title": "Worker Service consumindo RabbitMQ",
        "example": """\
// PedidoWorker.cs — IHostedService com RabbitMQ
public sealed class PedidoWorker(
    ILogger<PedidoWorker> logger,
    IConfiguration config) : BackgroundService
{
    private IConnection? _conn;
    private IModel?      _ch;

    public override Task StartAsync(CancellationToken ct)
    {
        var factory = new ConnectionFactory
            { Uri = new Uri(config["RABBITMQ_URL"]!) };
        _conn = factory.CreateConnection();
        _ch   = _conn.CreateModel();
        _ch.QueueDeclare("pedidos", durable: true, exclusive: false, autoDelete: false);
        _ch.BasicQos(0, prefetchCount: 1, global: false);
        return base.StartAsync(ct);
    }

    protected override Task ExecuteAsync(CancellationToken ct)
    {
        var consumer = new EventingBasicConsumer(_ch);
        consumer.Received += async (_, ea) =>
        {
            var pedido = JsonSerializer.Deserialize<Pedido>(
                Encoding.UTF8.GetString(ea.Body.ToArray()));
            logger.LogInformation("Processando #{Id}", pedido?.Id);
            await ProcessarAsync(pedido!, ct);
            _ch!.BasicAck(ea.DeliveryTag, multiple: false);
        };
        _ch!.BasicConsume("pedidos", autoAck: false, consumer);
        return Task.CompletedTask;
    }

    private static Task ProcessarAsync(Pedido p, CancellationToken ct)
        => Task.Delay(300, ct); // lógica real aqui
}"""
    },
    "rabbitmq": {
        "name": "RabbitMQ", "icon": "🐇", "color": "#FF6600", "category": "Messaging",
        "description": "Message broker para comunicação assíncrona entre serviços.",
        "example_title": "Fanout Exchange — broadcast a múltiplos consumers",
        "example": """\
import pika, json
from datetime import datetime

AMQP_URL = "amqp://guest:guest@localhost:5672/"

# ── PRODUCER ──────────────────────────────────────────────────
def publicar(tipo: str, dados: dict) -> None:
    params = pika.URLParameters(AMQP_URL)
    with pika.BlockingConnection(params) as conn:
        ch = conn.channel()
        ch.exchange_declare(exchange="eventos", exchange_type="fanout", durable=True)
        ch.basic_publish(
            exchange="eventos",
            routing_key="",          # fanout ignora routing_key
            body=json.dumps({"tipo": tipo, "dados": dados,
                             "ts": datetime.utcnow().isoformat()}),
            properties=pika.BasicProperties(delivery_mode=2),  # persistente
        )
    print(f"📢 Publicado: {tipo}")

# ── CONSUMER ──────────────────────────────────────────────────
def consumir(servico: str, handler) -> None:
    params = pika.URLParameters(AMQP_URL)
    with pika.BlockingConnection(params) as conn:
        ch = conn.channel()
        ch.exchange_declare(exchange="eventos", exchange_type="fanout", durable=True)
        fila = ch.queue_declare("", exclusive=True).method.queue
        ch.queue_bind(exchange="eventos", queue=fila)
        ch.basic_qos(prefetch_count=1)

        def cb(ch, method, _, body):
            evento = json.loads(body)
            print(f"[{servico}] recebeu: {evento['tipo']}")
            handler(evento)
            ch.basic_ack(method.delivery_tag)

        ch.basic_consume(fila, cb)
        print(f"[{servico}] aguardando...")
        ch.start_consuming()

# Uso:
# publicar("pedido.criado", {"id": 123, "valor": 299.90})
# consumir("email-svc",    lambda e: print("Enviando email..."))
# consumir("estoque-svc",  lambda e: print("Baixando estoque..."))"""
    },
    "redis": {
        "name": "Redis", "icon": "🔴", "color": "#DC382D", "category": "Cache",
        "description": "Store in-memory ultrarrápido para cache, sessão e pub/sub.",
        "example_title": "Cache decorator + Pub/Sub assíncrono",
        "example": """\
import redis.asyncio as aioredis
import json, functools
from datetime import timedelta

redis = aioredis.from_url("redis://localhost:6379", decode_responses=True)

# ── DECORATOR DE CACHE ASYNC ──────────────────────────────────
def cache(ttl: int = 60):
    def dec(fn):
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            chave = f"{fn.__name__}:{args}:{sorted(kwargs.items())}"
            cached = await redis.get(chave)
            if cached:
                return json.loads(cached)
            resultado = await fn(*args, **kwargs)
            await redis.setex(chave, timedelta(seconds=ttl), json.dumps(resultado))
            return resultado
        return wrapper
    return dec

@cache(ttl=300)
async def buscar_produto(pid: int) -> dict:
    # Simula consulta ao banco
    await asyncio.sleep(0.2)
    return {"id": pid, "nome": "Produto X", "preco": 99.90}

# ── PUB/SUB ─────────────────────────────────────────────────
async def publicar(canal: str, msg: dict) -> None:
    await redis.publish(canal, json.dumps(msg))

async def assinar(canal: str) -> None:
    pubsub = redis.pubsub()
    await pubsub.subscribe(canal)
    async for msg in pubsub.listen():
        if msg["type"] == "message":
            print("📩", json.loads(msg["data"]))"""
    },
    "pandas": {
        "name": "Pandas", "icon": "🐼", "color": "#E70488", "category": "Data Science",
        "description": "Biblioteca Python para análise e manipulação de dados tabulares.",
        "example_title": "Análise exploratória + Pivot Table",
        "example": """\
import pandas as pd

df = pd.read_csv("vendas.csv", parse_dates=["data_venda"])

# ── LIMPEZA ──────────────────────────────────────────────────
df = df.dropna(subset=["valor_total", "produto_id"])
df["valor_total"] = pd.to_numeric(df["valor_total"], errors="coerce")
df["mes"]        = df["data_venda"].dt.to_period("M")
df["dia_semana"] = df["data_venda"].dt.day_name()

# ── RECEITA MENSAL ───────────────────────────────────────────
receita = (
    df.groupby("mes")["valor_total"]
      .agg(receita="sum", pedidos="count", ticket="mean")
      .round(2)
)
print(receita.tail(6))

# ── TOP 10 PRODUTOS ──────────────────────────────────────────
top = (
    df.groupby("produto_nome")
      .agg(qtd=("id","count"), receita=("valor_total","sum"))
      .sort_values("receita", ascending=False)
      .head(10)
)

# ── PIVOT: categoria × mês ───────────────────────────────────
pivot = pd.pivot_table(
    df, values="valor_total",
    index="categoria", columns="mes",
    aggfunc="sum", fill_value=0, margins=True
)
print(pivot)"""
    },
}

# ─────────────────────────────────────────────────────────────
#  DETECÇÃO DE STACKS
# ─────────────────────────────────────────────────────────────
KEYWORDS: dict[str, list[str]] = {
    "python":     ["python"],
    "flask":      ["flask"],
    "fastapi":    ["fastapi", "fast api"],
    "django":     ["django"],
    "react":      ["react", "reactjs", "react.js"],
    "angular":    ["angular"],
    "typescript": ["typescript"],
    "javascript": ["javascript"],
    "node":       ["node.js", "nodejs", "node js"],
    "docker":     ["docker", "dockerfile", "docker-compose", "container"],
    "postgresql": ["postgresql", "postgres"],
    "sql":        ["mysql", "sqlite", "sql server", "t-sql", " sql "],
    "csharp":     ["c#", "csharp", "c sharp"],
    "dotnet":     [".net", "asp.net", "dotnet"],
    "rabbitmq":   ["rabbitmq", "rabbit mq", "amqp"],
    "redis":      ["redis"],
    "pandas":     ["pandas", "numpy", "scikit-learn", "sklearn"],
}

def detectar_stacks(texto: str) -> list[dict]:
    texto_lower = texto.lower()
    encontradas, vistas = [], set()
    for stack_id, keywords in KEYWORDS.items():
        for kw in keywords:
            padrao = r'\b' + re.escape(kw) + r'\b'
            if re.search(padrao, texto_lower) and stack_id not in vistas:
                if stack_id in STACK_DB:
                    encontradas.append({"id": stack_id, **STACK_DB[stack_id]})
                    vistas.add(stack_id)
                    break
    return encontradas

def extrair_texto_pdf(conteudo: bytes) -> str:
    doc = fitz.open(stream=conteudo, filetype="pdf")
    texto = ""
    for pagina in doc:
        texto += pagina.get_text()
    doc.close()
    return texto

# ─────────────────────────────────────────────────────────────
#  CONEXÃO RABBITMQ
# ─────────────────────────────────────────────────────────────
def get_rabbitmq_connection():
    params = pika.URLParameters(RABBITMQ_URL)
    params.heartbeat = 60
    params.blocked_connection_timeout = 30
    return pika.BlockingConnection(params)

def publicar_stacks(stacks: list[dict], session_id: str) -> None:
    """Publica cada stack como mensagem individual na fila."""
    conn = get_rabbitmq_connection()
    ch = conn.channel()
    ch.queue_declare(queue=QUEUE_NAME, durable=True)

    for i, stack in enumerate(stacks):
        mensagem = json.dumps({
            "session_id": session_id,
            "stack_id":   stack["id"],
            "posicao":    i + 1,
            "total":      len(stacks),
            "timestamp":  datetime.utcnow().isoformat(),
        })
        ch.basic_publish(
            exchange="",
            routing_key=QUEUE_NAME,
            body=mensagem,
            properties=pika.BasicProperties(delivery_mode=2),
        )
        log.info(f"[PRODUCER] Publicou: {stack['name']} ({i+1}/{len(stacks)})")

    conn.close()

# ─────────────────────────────────────────────────────────────
#  WEBSOCKET MANAGER
# ─────────────────────────────────────────────────────────────
class WSManager:
    def __init__(self):
        # session_id → WebSocket
        self._connections: dict[str, WebSocket] = {}

    async def connect(self, session_id: str, ws: WebSocket):
        await ws.accept()
        self._connections[session_id] = ws
        log.info(f"[WS] Conectado: {session_id}")

    def disconnect(self, session_id: str):
        self._connections.pop(session_id, None)
        log.info(f"[WS] Desconectado: {session_id}")

    async def send(self, session_id: str, data: dict):
        ws = self._connections.get(session_id)
        if ws:
            try:
                await ws.send_json(data)
            except Exception as e:
                log.warning(f"[WS] Erro ao enviar para {session_id}: {e}")
                self.disconnect(session_id)

    def has(self, session_id: str) -> bool:
        return session_id in self._connections

ws_manager = WSManager()

# ─────────────────────────────────────────────────────────────
#  CONSUMER (roda em thread dedicada por sessão)
# ─────────────────────────────────────────────────────────────
def consumer_thread(session_id: str, total: int, loop: asyncio.AbstractEventLoop):
    """Thread que consome da fila RabbitMQ e envia via WebSocket."""
    processados = 0
    try:
        conn = get_rabbitmq_connection()
        ch = conn.channel()
        ch.queue_declare(queue=QUEUE_NAME, durable=True)
        ch.basic_qos(prefetch_count=1)

        def callback(ch, method, properties, body):
            nonlocal processados
            msg = json.loads(body)

            # Só processa mensagens desta sessão
            if msg.get("session_id") != session_id:
                ch.basic_nack(method.delivery_tag, requeue=True)
                return

            stack_id = msg["stack_id"]
            stack    = STACK_DB.get(stack_id, {})
            processados += 1

            evento = {
                "type":      "stack_processed",
                "stack_id":  stack_id,
                "name":      stack.get("name", stack_id),
                "icon":      stack.get("icon", "📦"),
                "color":     stack.get("color", "#888"),
                "category":  stack.get("category", ""),
                "posicao":   msg["posicao"],
                "total":     msg["total"],
                "timestamp": datetime.utcnow().isoformat(),
            }

            # Envia ao WebSocket no loop asyncio principal
            future = asyncio.run_coroutine_threadsafe(
                ws_manager.send(session_id, evento), loop
            )
            future.result(timeout=5)

            log.info(f"[CONSUMER] Processou: {stack.get('name')} ({processados}/{total})")
            ch.basic_ack(method.delivery_tag)

            # Encerra consumer após processar todos
            if processados >= total:
                asyncio.run_coroutine_threadsafe(
                    ws_manager.send(session_id, {"type": "done", "total": total}),
                    loop
                )
                ch.stop_consuming()

        ch.basic_consume(queue=QUEUE_NAME, on_message_callback=callback)
        ch.start_consuming()
        conn.close()

    except Exception as e:
        log.error(f"[CONSUMER] Erro na sessão {session_id}: {e}")
        asyncio.run_coroutine_threadsafe(
            ws_manager.send(session_id, {"type": "error", "message": str(e)}),
            loop
        )

# ─────────────────────────────────────────────────────────────
#  APP FASTAPI
# ─────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info(f"Stack Radar iniciando — RabbitMQ: {RABBITMQ_URL}")
    yield
    log.info("Stack Radar encerrando")

app = FastAPI(title="Stack Radar", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve o frontend estático (procura em ./frontend e ../frontend)
frontend_dir = Path(__file__).parent / "frontend"
if not frontend_dir.exists():
    frontend_dir = Path(__file__).parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")

@app.get("/")
async def index():
    index_file = frontend_dir / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {"status": "Stack Radar API", "docs": "/docs"}

@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}

@app.get("/stacks")
async def listar_stacks():
    """Retorna todas as stacks disponíveis no banco."""
    return {
        "total": len(STACK_DB),
        "stacks": [
            {"id": k, "name": v["name"], "icon": v["icon"],
             "color": v["color"], "category": v["category"],
             "description": v["description"]}
            for k, v in STACK_DB.items()
        ]
    }

@app.post("/upload")
async def upload_pdf(pdf: UploadFile = File(...)):
    """
    Recebe o PDF, extrai texto, detecta stacks e publica no RabbitMQ.
    Retorna session_id para o cliente se conectar via WebSocket.
    """
    if not pdf.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Apenas arquivos .pdf são aceitos")

    conteudo = await pdf.read()
    if len(conteudo) > MAX_PDF_MB * 1024 * 1024:
        raise HTTPException(413, f"PDF muito grande (máx {MAX_PDF_MB} MB)")

    # Extrai texto do PDF
    try:
        texto = extrair_texto_pdf(conteudo)
    except Exception as e:
        raise HTTPException(422, f"Erro ao ler o PDF: {e}")

    if len(texto.strip()) < 50:
        raise HTTPException(422, "PDF sem texto legível (pode ser imagem/escaneado)")

    # Detecta stacks
    stacks = detectar_stacks(texto)
    if not stacks:
        raise HTTPException(404, "Nenhuma stack tecnológica identificada no PDF")

    # Gera session_id único para esta análise
    session_id = str(uuid.uuid4())

    return {
        "session_id": session_id,
        "encontradas": len(stacks),
        "stacks": [{"id": s["id"], "name": s["name"], "icon": s["icon"]} for s in stacks],
    }

@app.post("/processar/{session_id}")
async def processar(session_id: str, payload: dict):
    """
    Dispara o pipeline RabbitMQ para uma sessão.
    Recebe as stacks detectadas, publica na fila e inicia o consumer em thread.
    """
    stacks = payload.get("stacks", [])
    if not stacks:
        raise HTTPException(400, "Nenhuma stack para processar")

    loop = asyncio.get_event_loop()

    # Publica na fila (em thread para não bloquear o event loop)
    await asyncio.to_thread(publicar_stacks, stacks, session_id)

    # Inicia consumer em thread separada
    t = threading.Thread(
        target=consumer_thread,
        args=(session_id, len(stacks), loop),
        daemon=True,
    )
    t.start()

    return {"status": "pipeline_iniciado", "session_id": session_id, "total": len(stacks)}

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket: browser conecta aqui para receber eventos em tempo real."""
    await ws_manager.connect(session_id, websocket)
    try:
        # Mantém a conexão viva até o cliente desconectar
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(session_id)

@app.get("/stack/{stack_id}")
async def get_stack(stack_id: str):
    """Retorna exemplo completo de uma stack específica."""
    if stack_id not in STACK_DB:
        raise HTTPException(404, "Stack não encontrada")
    return STACK_DB[stack_id]
