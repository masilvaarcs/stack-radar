"""
Testes unitários do Stack Radar — backend.
Cobre: health, stacks, stack/{id}, upload, detecção de stacks, curiosity, STACK_DB, ATS.
"""
import sys
import os
import re
import json
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

# Stub pika antes de importar main (evita conexão real com RabbitMQ)
pika_mock = MagicMock()
sys.modules["pika"] = pika_mock

# Ajusta path
sys.path.insert(0, os.path.dirname(__file__))
from main import app, STACK_DB, KEYWORDS, ALL_STACKS, detectar_stacks, analisar_ats

client = TestClient(app)


# ─────────────────────────────────────────────────────────────
#  HEALTH
# ─────────────────────────────────────────────────────────────
class TestHealth:
    def test_health_ok(self):
        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert "timestamp" in data

    def test_health_has_timestamp(self):
        data = client.get("/health").json()
        assert len(data["timestamp"]) > 10  # ISO format

    def test_health_has_version(self):
        data = client.get("/health").json()
        assert "version" in data
        assert "released" in data
        assert re.match(r"^\d+\.\d+\.\d+$", data["version"])


# ─────────────────────────────────────────────────────────────
#  STACKS LIST
# ─────────────────────────────────────────────────────────────
class TestStacksList:
    def test_stacks_returns_all(self):
        r = client.get("/stacks")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == len(ALL_STACKS)
        assert len(data["stacks"]) == len(ALL_STACKS)

    def test_stacks_have_required_fields(self):
        data = client.get("/stacks").json()
        for s in data["stacks"]:
            assert "id" in s
            assert "name" in s
            assert "icon" in s
            assert "color" in s
            assert "category" in s

    def test_stacks_total_gt_100(self):
        data = client.get("/stacks").json()
        assert data["total"] >= 100, f"Expected 100+ stacks from taxonomy, got {data['total']}"


# ─────────────────────────────────────────────────────────────
#  SINGLE STACK — /stack/{id}
# ─────────────────────────────────────────────────────────────
class TestSingleStack:
    @pytest.mark.parametrize("stack_id", list(STACK_DB.keys()))
    def test_each_stack_returns_200(self, stack_id):
        r = client.get(f"/stack/{stack_id}")
        assert r.status_code == 200

    @pytest.mark.parametrize("stack_id", list(STACK_DB.keys()))
    def test_each_stack_has_example(self, stack_id):
        data = client.get(f"/stack/{stack_id}").json()
        assert "example" in data
        assert len(data["example"]) > 20, f"{stack_id} example too short"

    @pytest.mark.parametrize("stack_id", list(STACK_DB.keys()))
    def test_each_stack_has_curiosity(self, stack_id):
        data = client.get(f"/stack/{stack_id}").json()
        assert "curiosity" in data, f"{stack_id} missing curiosity"
        assert len(data["curiosity"]) > 30, f"{stack_id} curiosity too short"

    @pytest.mark.parametrize("stack_id", list(STACK_DB.keys()))
    def test_each_stack_has_color(self, stack_id):
        data = client.get(f"/stack/{stack_id}").json()
        assert "color" in data
        assert data["color"].startswith("#"), f"{stack_id} color invalid"

    def test_unknown_stack_returns_404(self):
        r = client.get("/stack/nonexistent_tech_xyz")
        assert r.status_code == 404

    def test_stack_name_matches_id(self):
        """Valida que o name é coerente com o id."""
        mapping = {
            "python": "Python", "flask": "Flask", "fastapi": "FastAPI",
            "django": "Django", "react": "React", "angular": "Angular",
            "typescript": "TypeScript", "javascript": "JavaScript",
            "node": "Node.js", "docker": "Docker", "postgresql": "PostgreSQL",
            "sql": "SQL", "csharp": "C#", "dotnet": ".NET",
            "rabbitmq": "RabbitMQ", "redis": "Redis", "pandas": "Pandas",
        }
        for sid, expected_name in mapping.items():
            data = client.get(f"/stack/{sid}").json()
            assert data["name"] == expected_name, f"{sid}: expected {expected_name}, got {data['name']}"


# ─────────────────────────────────────────────────────────────
#  STACK_DB INTEGRITY
# ─────────────────────────────────────────────────────────────
class TestStackDBIntegrity:
    REQUIRED_FIELDS = {"name", "icon", "color", "category", "description",
                       "curiosity", "example_title", "example"}

    @pytest.mark.parametrize("stack_id", list(STACK_DB.keys()))
    def test_all_fields_present(self, stack_id):
        stack = STACK_DB[stack_id]
        missing = self.REQUIRED_FIELDS - set(stack.keys())
        assert not missing, f"{stack_id} missing fields: {missing}"

    def test_no_empty_examples(self):
        for sid, s in STACK_DB.items():
            assert s["example"].strip(), f"{sid} has empty example"

    def test_no_empty_curiosities(self):
        for sid, s in STACK_DB.items():
            assert s["curiosity"].strip(), f"{sid} has empty curiosity"

    def test_colors_are_hex(self):
        import re
        for sid, s in STACK_DB.items():
            assert re.match(r"^#[0-9a-fA-F]{6}$", s["color"]), \
                f"{sid} color '{s['color']}' is not valid hex"

    def test_categories_are_known(self):
        known = {"Backend", "Frontend", "DevOps", "Database", "Messaging", "Cache", "Data Science"}
        for sid, s in STACK_DB.items():
            assert s["category"] in known, f"{sid} has unknown category '{s['category']}'"

    def test_no_empty_example_titles(self):
        for sid, s in STACK_DB.items():
            assert s["example_title"].strip(), f"{sid} has empty example_title"

    def test_example_title_not_generic(self):
        """example_title deve ser descritivo, não genérico."""
        generic = {"exemplo", "example", "código", "code", "test"}
        for sid, s in STACK_DB.items():
            title_lower = s["example_title"].lower()
            assert title_lower not in generic, \
                f"{sid} has generic example_title: '{s['example_title']}'"

    def test_examples_are_substantial(self):
        """Cada exemplo deve ter pelo menos 5 linhas de código."""
        for sid, s in STACK_DB.items():
            lines = [l for l in s["example"].split("\n") if l.strip()]
            assert len(lines) >= 5, \
                f"{sid} example too short ({len(lines)} lines)"


# ─────────────────────────────────────────────────────────────
#  STACK DETECTION
# ─────────────────────────────────────────────────────────────
class TestDetection:
    def test_detect_python(self):
        result = detectar_stacks("Experiência com Python e Django")
        ids = [s["id"] for s in result]
        assert "python" in ids
        assert "django" in ids

    def test_detect_react_typescript(self):
        result = detectar_stacks("Frontend em React com TypeScript")
        ids = [s["id"] for s in result]
        assert "react" in ids
        assert "typescript" in ids

    def test_detect_dotnet_csharp(self):
        result = detectar_stacks("Desenvolvimento em C# com .NET e ASP.NET")
        ids = [s["id"] for s in result]
        assert "csharp" in ids
        assert "dotnet" in ids

    def test_detect_docker_rabbitmq(self):
        result = detectar_stacks("Docker Compose, RabbitMQ, Redis")
        ids = [s["id"] for s in result]
        assert "docker" in ids
        assert "rabbitmq" in ids
        assert "redis" in ids

    def test_detect_nothing(self):
        result = detectar_stacks("abcdef ghijkl mnopqr stuvwx")
        assert len(result) == 0

    def test_all_keywords_have_stack(self):
        """Cada keyword em KEYWORDS deve mapear para um id existente no ALL_STACKS."""
        for keyword_id in KEYWORDS:
            assert keyword_id in ALL_STACKS, f"KEYWORDS '{keyword_id}' not in ALL_STACKS"

    def test_detect_returns_name_and_icon(self):
        result = detectar_stacks("Python")
        assert len(result) > 0
        s = result[0]
        assert "name" in s
        assert "icon" in s
        assert "color" in s

    def test_detect_taxonomy_saude(self):
        result = detectar_stacks("Experiência em Cardiologia e Telemedicina")
        ids = [s["id"] for s in result]
        assert "cardiologia" in ids
        assert "telemedicina" in ids

    def test_detect_taxonomy_marketing(self):
        result = detectar_stacks("Trabalho com SEO e Google Ads")
        ids = [s["id"] for s in result]
        assert "seo" in ids
        assert "google_ads" in ids

    def test_detect_taxonomy_cloud(self):
        result = detectar_stacks("Infraestrutura na AWS com Kubernetes")
        ids = [s["id"] for s in result]
        assert "aws" in ids
        assert "kubernetes" in ids

    def test_detect_taxonomy_design(self):
        result = detectar_stacks("UI design com Figma e Photoshop")
        ids = [s["id"] for s in result]
        assert "figma" in ids
        assert "photoshop" in ids

    def test_detect_taxonomy_finance(self):
        result = detectar_stacks("Excel avançado e SAP ERP")
        ids = [s["id"] for s in result]
        assert "excel" in ids
        assert "sap" in ids


# ─────────────────────────────────────────────────────────────
#  CURIOSITY x STACK COHERENCE
# ─────────────────────────────────────────────────────────────
class TestCuriosityCoherence:
    """Valida que a curiosity de cada stack menciona algo relacionado ao nome."""

    @pytest.mark.parametrize("stack_id,keyword", [
        ("python", "python"),
        ("flask", "flask"),
        ("fastapi", "fastapi"),
        ("django", "django"),
        ("react", "react"),
        ("angular", "angular"),
        ("typescript", "typescript"),
        ("javascript", "javascript"),
        ("node", "node"),
        ("docker", "docker"),
        ("postgresql", "postgres"),
        ("sql", "sql"),
        ("csharp", "c#"),
        ("dotnet", ".net"),
        ("rabbitmq", "rabbitmq"),
        ("redis", "redis"),
        ("pandas", "pandas"),
    ])
    def test_curiosity_mentions_stack(self, stack_id, keyword):
        curiosity = STACK_DB[stack_id]["curiosity"].lower()
        assert keyword.lower() in curiosity, \
            f"{stack_id} curiosity doesn't mention '{keyword}': {curiosity[:80]}..."


# ─────────────────────────────────────────────────────────────
#  UPLOAD (mock PDF)
# ─────────────────────────────────────────────────────────────
class TestUpload:
    def test_upload_no_file_returns_422(self):
        r = client.post("/upload")
        assert r.status_code == 422

    def test_upload_invalid_type_returns_400(self):
        r = client.post("/upload", files={"pdf": ("test.txt", b"hello", "text/plain")})
        assert r.status_code == 400


# ─────────────────────────────────────────────────────────────
#  SECURITY
# ─────────────────────────────────────────────────────────────
class TestSecurity:
    def test_security_headers_present(self):
        r = client.get("/health")
        assert r.headers["X-Content-Type-Options"] == "nosniff"
        assert r.headers["X-Frame-Options"] == "DENY"
        assert r.headers["X-XSS-Protection"] == "1; mode=block"
        assert r.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
        assert "Permissions-Policy" in r.headers

    def test_processar_invalid_session_id(self):
        r = client.post("/processar/not-a-uuid", json={"stacks": [{"id": "python", "name": "Python"}]})
        assert r.status_code == 400

    def test_processar_missing_stacks(self):
        import uuid as _uuid
        sid = str(_uuid.uuid4())
        r = client.post(f"/processar/{sid}", json={"stacks": []})
        assert r.status_code == 400

    def test_processar_invalid_stack_id(self):
        import uuid as _uuid
        sid = str(_uuid.uuid4())
        r = client.post(f"/processar/{sid}", json={"stacks": [{"id": "<script>alert(1)</script>", "name": "xss"}]})
        assert r.status_code == 422

    def test_processar_no_body(self):
        import uuid as _uuid
        sid = str(_uuid.uuid4())
        r = client.post(f"/processar/{sid}")
        assert r.status_code == 422

    def test_upload_no_filename_returns_error(self):
        r = client.post("/upload", files={"pdf": ("", b"data", "application/pdf")})
        assert r.status_code in (400, 422)

    def test_error_message_no_internal_leak(self):
        """Verifica que erros no consumer não vazam detalhes internos."""
        from main import consumer_thread
        # O consumer_thread envia "Erro interno no processamento" (não str(e))
        import inspect
        src = inspect.getsource(consumer_thread)
        assert "Erro interno no processamento" in src
        assert '"message": str(e)' not in src


# ─────────────────────────────────────────────────────────────
#  ATS ANALYSIS
# ─────────────────────────────────────────────────────────────
class TestATSAnalysis:
    SAMPLE_CV = """
    João Silva
    joao@email.com | (11) 99999-0000
    linkedin.com/in/joaosilva | github.com/joaosilva

    Resumo
    Desenvolvedor Full-Stack com 5 anos de experiência em Python, React e AWS.

    Experiência Profissional
    Desenvolveu APIs REST com FastAPI que processam 10.000 requests/dia.
    Liderou equipe de 8 pessoas em projeto de migração para microserviços.
    Otimizou consultas SQL reduzindo tempo de resposta em 40%.
    Implementou CI/CD com GitHub Actions e Docker.

    Formação Acadêmica
    Ciência da Computação - USP (2018)

    Competências
    Python, FastAPI, React, TypeScript, Docker, PostgreSQL, AWS, Redis

    Certificações
    AWS Solutions Architect Associate
    """

    def test_ats_returns_score(self):
        stacks = detectar_stacks(self.SAMPLE_CV)
        ats = analisar_ats(self.SAMPLE_CV, stacks)
        assert "score" in ats
        assert 0 <= ats["score"] <= 100

    def test_ats_returns_classificacao(self):
        stacks = detectar_stacks(self.SAMPLE_CV)
        ats = analisar_ats(self.SAMPLE_CV, stacks)
        assert ats["classificacao"] in ("Excelente", "Bom", "Regular", "Precisa Melhorar")
        assert ats["classificacao_cor"].startswith("#")

    def test_ats_detects_sections(self):
        stacks = detectar_stacks(self.SAMPLE_CV)
        ats = analisar_ats(self.SAMPLE_CV, stacks)
        secoes = ats["detalhes"]["secoes"]["encontradas"]
        assert secoes["summary"]["found"] is True
        assert secoes["experience"]["found"] is True
        assert secoes["education"]["found"] is True
        assert secoes["skills"]["found"] is True
        assert secoes["certifications"]["found"] is True

    def test_ats_detects_action_verbs(self):
        stacks = detectar_stacks(self.SAMPLE_CV)
        ats = analisar_ats(self.SAMPLE_CV, stacks)
        verbos = ats["detalhes"]["verbos_acao"]
        assert verbos["total"] >= 3
        assert "desenvolveu" in verbos["encontrados"] or "implementou" in verbos["encontrados"]

    def test_ats_detects_quantifiers(self):
        stacks = detectar_stacks(self.SAMPLE_CV)
        ats = analisar_ats(self.SAMPLE_CV, stacks)
        quant = ats["detalhes"]["metricas_quantificaveis"]
        assert quant["total"] >= 2

    def test_ats_detects_contact(self):
        stacks = detectar_stacks(self.SAMPLE_CV)
        ats = analisar_ats(self.SAMPLE_CV, stacks)
        contato = ats["detalhes"]["contato"]["encontrados"]
        assert contato["email"] is True
        assert contato["linkedin"] is True
        assert contato["github"] is True

    def test_ats_generates_suggestions(self):
        bad_cv = "João Silva. Trabalho com coisas."
        stacks = detectar_stacks(bad_cv)
        ats = analisar_ats(bad_cv, stacks)
        assert len(ats["sugestoes"]) >= 3
        assert ats["score"] < 40

    def test_ats_resumo_has_all_fields(self):
        stacks = detectar_stacks(self.SAMPLE_CV)
        ats = analisar_ats(self.SAMPLE_CV, stacks)
        resumo = ats["resumo"]
        assert "total_palavras" in resumo
        assert "stacks_detectadas" in resumo
        assert "secoes_encontradas" in resumo
        assert "verbos_acao" in resumo

    def test_ats_good_cv_scores_high(self):
        stacks = detectar_stacks(self.SAMPLE_CV)
        ats = analisar_ats(self.SAMPLE_CV, stacks)
        assert ats["score"] >= 50, f"Good CV scored only {ats['score']}"


# ─────────────────────────────────────────────────────────────
#  TAXONOMY INTEGRITY
# ─────────────────────────────────────────────────────────────
class TestTaxonomyIntegrity:
    def test_all_stacks_have_original_examples(self):
        """Os 17 stacks originais ainda têm exemplos de código."""
        for sid in STACK_DB:
            assert sid in ALL_STACKS, f"{sid} missing from ALL_STACKS"
            assert "example" in ALL_STACKS[sid], f"{sid} lost its example"

    def test_taxonomy_covers_multiple_areas(self):
        areas = set(s.get("area", "") for s in ALL_STACKS.values() if s.get("area"))
        assert len(areas) >= 5, f"Expected 5+ areas, got {len(areas)}: {areas}"

    def test_taxonomy_has_saude_stacks(self):
        saude = [s for s in ALL_STACKS.values() if s.get("area") == "Saúde"]
        assert len(saude) >= 10, f"Expected 10+ Saúde stacks, got {len(saude)}"

    def test_taxonomy_has_educacao_stacks(self):
        edu = [s for s in ALL_STACKS.values() if s.get("area") == "Educação"]
        assert len(edu) >= 8, f"Expected 8+ Educação stacks, got {len(edu)}"

    def test_taxonomy_stacks_have_min_fields(self):
        """Todas stacks da taxonomia devem ter name, icon, color, category."""
        for sid, info in ALL_STACKS.items():
            assert info.get("name"), f"{sid} missing name"
            assert info.get("icon"), f"{sid} missing icon"
            assert info.get("color"), f"{sid} missing color"
            assert info.get("category"), f"{sid} missing category"


# ─────────────────────────────────────────────────────────────
#  TESTES DE REGRESSÃO ATS — FORMATOS DE PDF REAIS
#  Cada classe simula o texto extraído de um formato real.
#  NUNCA liberar commit se algum destes falhar.
# ─────────────────────────────────────────────────────────────

class TestATSFormatoCVAtsHtml:
    """CV gerado de HTML otimizado para ATS — seções PT-BR, layout limpo."""

    CV = """
MARCOS SANTOS DA SILVA
Desenvolvedor Full Stack Sênior | .NET C# · Angular · Python | +20 anos de experiência

Gravataí / RS  |  (51) 98422-8067  |  masilva.arcs@gmail.com
LinkedIn: linkedin.com/in/marcosprogramador  |  Portfólio: masilvaarcs.github.io/portfolio-hub

RESUMO PROFISSIONAL

Desenvolvedor Full Stack Sênior com mais de 20 anos de experiência em sistemas críticos, ERP e WMS.
Especialista em .NET C#, Angular e Python, com aplicação consistente de arquitetura limpa, SOLID e Design Patterns.

COMPETÊNCIAS TÉCNICAS

Back-End: .NET, C#, ASP.NET Core, Web API, API RESTful, Microserviços, Entity Framework Core, LINQ, JWT, OAuth
Front-End: Angular, TypeScript, JavaScript, HTML5, CSS3, RxJS, React (básico)
Bancos de Dados: SQL Server, Oracle, PostgreSQL, MySQL, PL/SQL, Stored Procedures
DevOps e Cloud: Azure DevOps, Docker, CI/CD, Git, GitHub, GitLab, Pipelines
Automação e Scripts: Python, PowerShell, NSIS, Node.js
Qualidade e Arquitetura: SOLID, Clean Code, Design Patterns, Unit Testing, xUnit, NUnit, TDD
IA e Produtividade: GitHub Copilot, Claude AI
Metodologias: Scrum, Kanban, Agile

EXPERIÊNCIA PROFISSIONAL

Octafy LAD (operação Perto S.A.)                                       Dez 2024 - Mar 2026
Desenvolvedor .NET Sênior (C#) — promovido a Desenvolvedor Full Stack (Angular | .NET)

Desenvolvi e evoluí 25 componentes de pages em Angular (84% das rotas concluídas), integrados aos fluxos operacionais
Integrei frontend Angular, WebAPI RESTful (.NET C#), WebServices ASMX/SOAP, SQL Server e equipamentos TCR
Criei scripts Python para geração de dashboards de evolução, análise automatizada de commits
Prototipei POC em .NET MAUI reproduzindo operações do frontend Angular
Elaborei documentação técnica completa: relatórios de evolução, FAQ Técnico (v1.3.0)
Utilizei GitHub Copilot e Claude AI como ferramentas para análise de lógica complexa

FORMAÇÃO ACADÊMICA

Escola Estadual Marechal Mascarenhas de Moraes
Técnico em Processamento de Dados — Informática | 1997 – 1999

CERTIFICAÇÕES

SFPC — Scrum Foundation Professional Certificate (CertiProf)
DEPC — DevOps Essentials Professional Certificate (CertiProf)
KIKF — Kanban Foundation (CertiProf)

IDIOMAS

Português: Nativo
Inglês: Intermediário (leitura técnica)

Portfólio: masilvaarcs.github.io/portfolio-hub
https://github.com/masilvaarcs
    """

    def test_score_minimo_80(self):
        stacks = detectar_stacks(self.CV)
        ats = analisar_ats(self.CV, stacks)
        assert ats["score"] >= 80, f"CV ATS HTML scored {ats['score']}, expected >= 80"

    def test_classificacao_excelente(self):
        stacks = detectar_stacks(self.CV)
        ats = analisar_ats(self.CV, stacks)
        assert ats["classificacao"] == "Excelente", f"Got '{ats['classificacao']}'"

    def test_todas_7_secoes_detectadas(self):
        stacks = detectar_stacks(self.CV)
        ats = analisar_ats(self.CV, stacks)
        secoes = ats["detalhes"]["secoes"]["encontradas"]
        for sec_key in ["summary", "experience", "education", "skills", "certifications", "languages", "projects"]:
            assert secoes[sec_key]["found"], f"Seção '{sec_key}' não detectada no CV ATS HTML"

    def test_todos_5_contatos_detectados(self):
        stacks = detectar_stacks(self.CV)
        ats = analisar_ats(self.CV, stacks)
        contato = ats["detalhes"]["contato"]["encontrados"]
        for ct in ["email", "phone", "linkedin", "github", "portfolio"]:
            assert contato[ct], f"Contato '{ct}' não detectado no CV ATS HTML"

    def test_verbos_minimo_5(self):
        stacks = detectar_stacks(self.CV)
        ats = analisar_ats(self.CV, stacks)
        total = ats["detalhes"]["verbos_acao"]["total"]
        assert total >= 5, f"Apenas {total} verbos detectados, esperado >= 5"

    def test_metricas_minimo_2(self):
        stacks = detectar_stacks(self.CV)
        ats = analisar_ats(self.CV, stacks)
        total = ats["detalhes"]["metricas_quantificaveis"]["total"]
        assert total >= 2, f"Apenas {total} métricas detectadas, esperado >= 2"

    def test_stacks_minimo_30(self):
        stacks = detectar_stacks(self.CV)
        assert len(stacks) >= 30, f"Apenas {len(stacks)} stacks, esperado >= 30"

    def test_stacks_obrigatorias_presentes(self):
        stacks = detectar_stacks(self.CV)
        ids = {s["id"] for s in stacks}
        obrigatorias = {"python", "csharp", "angular", "dotnet", "docker", "sql", "postgresql", "github_copilot"}
        faltando = obrigatorias - ids
        assert not faltando, f"Stacks obrigatórias não detectadas: {faltando}"

    def test_secao_resumo_via_ptbr(self):
        """Garante que 'RESUMO PROFISSIONAL' mapeia para seção 'summary'."""
        stacks = detectar_stacks(self.CV)
        ats = analisar_ats(self.CV, stacks)
        assert ats["detalhes"]["secoes"]["encontradas"]["summary"]["found"]

    def test_secao_competencias_via_ptbr(self):
        """Garante que 'COMPETÊNCIAS TÉCNICAS' mapeia para seção 'skills'."""
        stacks = detectar_stacks(self.CV)
        ats = analisar_ats(self.CV, stacks)
        assert ats["detalhes"]["secoes"]["encontradas"]["skills"]["found"]


class TestATSFormatoVisualDesign:
    """CV visual com QR codes, badges, ícones, layout 2 colunas."""

    CV = """
Marcos Santos da Silva
Desenvolvedor Full Stack Sênior | .NET C# · Angular · Python | +20 anos de experiência

📍Gravataí / RS  📱(51) 98422-8067   ✉️masilva.arcs@gmail.com   🔗linkedin.com/in/marcosprogramador
🌐masilvaarcs.github.io/portfolio-hub

RESUMO PROFISSIONAL

Desenvolvedor Full Stack Sênior com mais de 20 anos de experiência em sistemas críticos, ERP e WMS.
Especialista em .NET C#, Angular e Python. Certificado em Scrum (SFPC®), DevOps (DEPC®) e Kanban (KIKF™).
Utilizo ferramentas de IA como GitHub Copilot e Claude AI como aliados estratégicos.

+20                            15+                 6                    Full Stack
ANOS DE EXPERIÊNCIA     EMPRESAS ATENDIDAS   CERTIFICAÇÕES      .NET · ANGULAR · PYTHON

STACK TÉCNICA

BACK-END                                              FRONT-END
.NET C# · ASP.NET Core · Web API · API RESTful ·      Angular · TypeScript · JavaScript · HTML5 · CSS3 · RxJS ·
Microserviços · Entity Framework Core · LINQ · JWT     React (básico)

BANCOS DE DADOS                                       DEVOPS & CLOUD
SQL Server · Oracle · PostgreSQL · MySQL · PL/SQL ·    Azure DevOps · Docker · CI/CD · Git · GitHub · GitLab ·
Stored Procedures                                      Pipelines

AUTOMAÇÃO & SCRIPTS                                   QUALIDADE & ARQUITETURA
Python · PowerShell · NSIS · Node.js                   SOLID · Clean Code · Design Patterns · Unit Testing · xUnit · NUnit · TDD

IA & PRODUTIVIDADE                                    METODOLOGIAS
GitHub Copilot · Claude AI · ChatGPT                   Scrum · Kanban · Agile · Sprints · Daily · Planning

EXPERIÊNCIA PROFISSIONAL

Octafy LAD (operação Perto S.A.)                                        Dez 2024 - Mar 2026
Desenvolvedor .NET Sênior (C#)  PROMOVIDO  Desenvolvedor Full Stack (Angular | .NET)

Desenvolvi e evoluí 25 componentes de pages em Angular (84% das rotas concluídas)
Integrei frontend Angular ↔ WebAPI RESTful (.NET C#) ↔ WebServices ASMX/SOAP ↔ SQL Server
Criei scripts Python para geração de dashboards de evolução
Prototipei POC em .NET MAUI reproduzindo operações do frontend Angular
Elaborei documentação técnica completa
Utilizei GitHub Copilot e Claude AI como ferramentas para análise de lógica complexa

CERTIFICAÇÕES

SFPC® — Scrum Foundation (CertiProf)
DEPC® — DevOps Essentials (CertiProf)
KIKF™ — Kanban Foundation (CertiProf)

IA & PRODUTIVIDADE
GitHub Copilot · Claude AI · Assistentes de IA Generativa

FORMAÇÃO ACADÊMICA                                    IDIOMAS
Escola Estadual Marechal Mascarenhas de Moraes        Português — Nativo
Técnico em Processamento de Dados — Informática       Inglês — Intermediário (leitura técnica)
1997 – 1999

LinkedIn: linkedin.com/in/marcosprogramador
Portfólio: masilvaarcs.github.io/portfolio-hub
GitHub: github.com/masilvaarcs
    """

    def test_score_minimo_75(self):
        stacks = detectar_stacks(self.CV)
        ats = analisar_ats(self.CV, stacks)
        assert ats["score"] >= 75, f"CV Visual scored {ats['score']}, expected >= 75"

    def test_classificacao_bom_ou_excelente(self):
        stacks = detectar_stacks(self.CV)
        ats = analisar_ats(self.CV, stacks)
        assert ats["classificacao"] in ("Excelente", "Bom"), f"Got '{ats['classificacao']}'"

    def test_todas_7_secoes_detectadas(self):
        stacks = detectar_stacks(self.CV)
        ats = analisar_ats(self.CV, stacks)
        secoes = ats["detalhes"]["secoes"]["encontradas"]
        for sec_key in ["summary", "experience", "education", "skills", "certifications", "languages", "projects"]:
            assert secoes[sec_key]["found"], f"Seção '{sec_key}' não detectada no CV Visual"

    def test_todos_5_contatos_detectados(self):
        stacks = detectar_stacks(self.CV)
        ats = analisar_ats(self.CV, stacks)
        contato = ats["detalhes"]["contato"]["encontrados"]
        for ct in ["email", "phone", "linkedin", "github", "portfolio"]:
            assert contato[ct], f"Contato '{ct}' não detectado no CV Visual"

    def test_emojis_nao_atrapalham_contato(self):
        """Emojis 📱✉️🔗🌐 não devem impedir detecção de contatos."""
        stacks = detectar_stacks(self.CV)
        ats = analisar_ats(self.CV, stacks)
        contato = ats["detalhes"]["contato"]["encontrados"]
        assert contato["email"], "Email com emoji ✉️ não detectado"
        assert contato["phone"], "Telefone com emoji 📱 não detectado"

    def test_layout_2_colunas_nao_perde_stacks(self):
        """Layout lado-a-lado não deve impedir detecção de stacks."""
        stacks = detectar_stacks(self.CV)
        ids = {s["id"] for s in stacks}
        essenciais = {"angular", "csharp", "dotnet", "python", "docker", "sql", "postgresql"}
        faltando = essenciais - ids
        assert not faltando, f"Layout 2 colunas perdeu stacks: {faltando}"

    def test_verbos_minimo_5(self):
        stacks = detectar_stacks(self.CV)
        ats = analisar_ats(self.CV, stacks)
        total = ats["detalhes"]["verbos_acao"]["total"]
        assert total >= 5, f"Apenas {total} verbos detectados"

    def test_metricas_minimo_2(self):
        stacks = detectar_stacks(self.CV)
        ats = analisar_ats(self.CV, stacks)
        total = ats["detalhes"]["metricas_quantificaveis"]["total"]
        assert total >= 2, f"Apenas {total} métricas detectadas"

    def test_stacks_minimo_30(self):
        stacks = detectar_stacks(self.CV)
        assert len(stacks) >= 30, f"Apenas {len(stacks)} stacks no CV Visual"


class TestATSFormatoPDFGupy:
    """PDF exportado pela plataforma Gupy — seções EN, labels diferentes."""

    CV = """
Marcos Santos da Silva
CPF: 80438407091
Rua Pereira Passos, 31 , Gravataí, Rio Grande do Sul, Brasil
Gravataí/RS - Zip Code: 94040-230
+5551984228067
masilva.arcs@gmail.com

Education
Vocational school (Complete)
Escola Estadual Marechal Mascarenhas de Moraes - Técnico em Processamento de Dados, Informática
3/1997 - 12/1999

Professional experience
Company: Octafy LAD (operação Perto S.A.)
Position: Desenvolvedor .NET Sênior (C#) — promovido a Desenvolvedor Full Stack (Angular | .NET) (12/2024 - 3/2026)
Main activities: Atuação inicialmente como Desenvolvedor .NET Sênior em sistemas críticos do setor financeiro.

Desenvolvi e evoluí 25 componentes de pages em Angular (84% das rotas concluídas)
Integrei frontend Angular, WebAPI RESTful (.NET C#), WebServices ASMX/SOAP, SQL Server
Criei scripts Python para geração de dashboards de evolução
Prototipei POC em .NET MAUI reproduzindo operações do frontend Angular
Elaborei documentação técnica completa
Utilizei GitHub Copilot e Claude AI como ferramentas para análise de lógica complexa

Tecnologias: Angular, .NET C#, ASP.NET Core, Web API, WebServices ASMX, SQL Server, Python, NSIS, PowerShell, IIS, .NET MAUI, GitHub Copilot, Claude AI, Scrum

Company: Grupo Apisul
Position: Desenvolvedor .NET (10/2023 - 7/2024)
Tecnologias: .NET, SQL Server, Azure DevOps, CI/CD, Unit Testing, HTML, CSS, JavaScript, Agile

Company: PRODATA MOBILITY BRASIL
Position: Desenvolvedor .NET (12/2021 - 5/2023)
Tecnologias: .NET, Angular, Node.js, Oracle, Crystal Reports

Company: Brazpine
Position: Desenvolvedor .NET | Visual Basic (5/2020 - 11/2021)
Tecnologias: .NET, Visual Basic, Oracle, PostgreSQL, Azure DevOps, ERP

Achievements
Achievement: Course
Title: JAVA JRE E JDK: COMPILE E EXECUTE O SEU PROGRAMA
Description: Alura (no período da BRAZPINE)
Carga horária: 8 horas

Achievement: Certificate
Title: IA na Prática
Description: Desenvolvimento de aplicação Python, integração com modelo GPT da OpenAI
Data de emissão: 22/08/2024

Achievement: Certificate
Title: Iniciando com ASP.NET Core
Carga horária: 02 horas
Conclusão: 27/05/2021

Languages
Language: Portuguese
Level: Native/Fluent
Language: English
Level: Intermediate

Social network profiles
LinkedIn: https://www.linkedin.com/in/marcosprogramador/
    """

    def test_score_minimo_65(self):
        stacks = detectar_stacks(self.CV)
        ats = analisar_ats(self.CV, stacks)
        assert ats["score"] >= 65, f"CV Gupy scored {ats['score']}, expected >= 65"

    def test_classificacao_bom_ou_superior(self):
        stacks = detectar_stacks(self.CV)
        ats = analisar_ats(self.CV, stacks)
        assert ats["classificacao"] in ("Excelente", "Bom"), f"Got '{ats['classificacao']}'"

    def test_secao_education_en(self):
        """Gupy usa 'Education' (EN) — deve mapear para 'education'."""
        stacks = detectar_stacks(self.CV)
        ats = analisar_ats(self.CV, stacks)
        assert ats["detalhes"]["secoes"]["encontradas"]["education"]["found"], "Seção 'Education' (EN) não reconhecida"

    def test_secao_professional_experience_en(self):
        """Gupy usa 'Professional experience' — deve mapear para 'experience'."""
        stacks = detectar_stacks(self.CV)
        ats = analisar_ats(self.CV, stacks)
        assert ats["detalhes"]["secoes"]["encontradas"]["experience"]["found"], "'Professional experience' não reconhecida"

    def test_secao_achievements_mapeia_projects(self):
        """Gupy usa 'Achievements' — deve mapear para 'projects'."""
        stacks = detectar_stacks(self.CV)
        ats = analisar_ats(self.CV, stacks)
        assert ats["detalhes"]["secoes"]["encontradas"]["projects"]["found"], "'Achievements' não mapeou para 'projects'"

    def test_secao_languages_en(self):
        """Gupy usa 'Languages' (EN) — deve mapear para 'languages'."""
        stacks = detectar_stacks(self.CV)
        ats = analisar_ats(self.CV, stacks)
        assert ats["detalhes"]["secoes"]["encontradas"]["languages"]["found"], "'Languages' (EN) não reconhecida"

    def test_minimo_5_secoes(self):
        """Gupy deve ter pelo menos 5 das 7 seções reconhecidas."""
        stacks = detectar_stacks(self.CV)
        ats = analisar_ats(self.CV, stacks)
        secoes = ats["detalhes"]["secoes"]["encontradas"]
        total = sum(1 for s in secoes.values() if s["found"])
        assert total >= 5, f"Apenas {total}/7 seções detectadas no formato Gupy"

    def test_email_detectado(self):
        stacks = detectar_stacks(self.CV)
        ats = analisar_ats(self.CV, stacks)
        assert ats["detalhes"]["contato"]["encontrados"]["email"], "Email não detectado no formato Gupy"

    def test_phone_detectado(self):
        """Telefone +5551984228067 (formato Gupy sem separadores) deve ser detectado."""
        stacks = detectar_stacks(self.CV)
        ats = analisar_ats(self.CV, stacks)
        assert ats["detalhes"]["contato"]["encontrados"]["phone"], "Telefone formato Gupy não detectado"

    def test_linkedin_detectado(self):
        stacks = detectar_stacks(self.CV)
        ats = analisar_ats(self.CV, stacks)
        assert ats["detalhes"]["contato"]["encontrados"]["linkedin"], "LinkedIn não detectado no formato Gupy"

    def test_verbos_minimo_5(self):
        stacks = detectar_stacks(self.CV)
        ats = analisar_ats(self.CV, stacks)
        total = ats["detalhes"]["verbos_acao"]["total"]
        assert total >= 5, f"Apenas {total} verbos no formato Gupy"

    def test_metricas_minimo_2(self):
        stacks = detectar_stacks(self.CV)
        ats = analisar_ats(self.CV, stacks)
        total = ats["detalhes"]["metricas_quantificaveis"]["total"]
        assert total >= 2, f"Apenas {total} métricas no formato Gupy"

    def test_stacks_minimo_20(self):
        stacks = detectar_stacks(self.CV)
        assert len(stacks) >= 20, f"Apenas {len(stacks)} stacks no formato Gupy"

    def test_stacks_core_presentes(self):
        stacks = detectar_stacks(self.CV)
        ids = {s["id"] for s in stacks}
        core = {"python", "csharp", "angular", "dotnet", "sql"}
        faltando = core - ids
        assert not faltando, f"Stacks core não detectadas no Gupy: {faltando}"


class TestATSFormatoLinkedIn:
    """PDF exportado pelo LinkedIn — seções EN, formato especial."""

    CV = """
Marcos Santos da Silva
Desenvolvedor Full Stack Sênior

Gravataí, Rio Grande do Sul, Brasil

Summary
Desenvolvedor Full Stack Sênior com mais de 20 anos de experiência em sistemas críticos.
Especialista em .NET C#, Angular e Python.

Top Skills
.NET, C#, Angular, Python, SQL Server, Docker, Azure DevOps

Experience
Octafy LAD (operação Perto S.A.)
Desenvolvedor Full Stack
Dec 2024 - Mar 2026

Desenvolvi e evoluí 25 componentes em Angular (84% concluídas)
Integrei frontend Angular, WebAPI RESTful (.NET C#), SQL Server
Criei scripts Python para dashboards
Implementei CI/CD pipelines com Azure DevOps

Grupo Apisul
Desenvolvedor .NET
Oct 2023 - Jul 2024

Education
Escola Estadual Marechal Mascarenhas de Moraes
Técnico em Processamento de Dados
1997 - 1999

Licenses & Certifications
SFPC — Scrum Foundation Professional Certificate - CertiProf
DEPC — DevOps Essentials Professional Certificate - CertiProf

Languages
Portuguese (Native or Bilingual)
English (Limited Working)

Contact
masilva.arcs@gmail.com
linkedin.com/in/marcosprogramador
    """

    def test_score_minimo_55(self):
        stacks = detectar_stacks(self.CV)
        ats = analisar_ats(self.CV, stacks)
        assert ats["score"] >= 55, f"CV LinkedIn scored {ats['score']}, expected >= 55"

    def test_secao_summary_en(self):
        stacks = detectar_stacks(self.CV)
        ats = analisar_ats(self.CV, stacks)
        assert ats["detalhes"]["secoes"]["encontradas"]["summary"]["found"], "'Summary' (LinkedIn EN) não reconhecida"

    def test_secao_experience_en(self):
        stacks = detectar_stacks(self.CV)
        ats = analisar_ats(self.CV, stacks)
        assert ats["detalhes"]["secoes"]["encontradas"]["experience"]["found"], "'Experience' (LinkedIn EN) não reconhecida"

    def test_secao_education_en(self):
        stacks = detectar_stacks(self.CV)
        ats = analisar_ats(self.CV, stacks)
        assert ats["detalhes"]["secoes"]["encontradas"]["education"]["found"], "'Education' (LinkedIn EN) não reconhecida"

    def test_secao_languages_en(self):
        stacks = detectar_stacks(self.CV)
        ats = analisar_ats(self.CV, stacks)
        assert ats["detalhes"]["secoes"]["encontradas"]["languages"]["found"], "'Languages' (LinkedIn EN) não reconhecida"

    def test_secao_licenses_certifications(self):
        """LinkedIn usa 'Licenses & Certifications' — deve mapear para 'certifications'."""
        stacks = detectar_stacks(self.CV)
        ats = analisar_ats(self.CV, stacks)
        assert ats["detalhes"]["secoes"]["encontradas"]["certifications"]["found"], "'Licenses & Certifications' não reconhecida"

    def test_secao_top_skills(self):
        """LinkedIn usa 'Top Skills' — deve mapear para 'skills'."""
        stacks = detectar_stacks(self.CV)
        ats = analisar_ats(self.CV, stacks)
        assert ats["detalhes"]["secoes"]["encontradas"]["skills"]["found"], "'Top Skills' (LinkedIn) não reconhecida"

    def test_email_detectado(self):
        stacks = detectar_stacks(self.CV)
        ats = analisar_ats(self.CV, stacks)
        assert ats["detalhes"]["contato"]["encontrados"]["email"]

    def test_linkedin_detectado(self):
        stacks = detectar_stacks(self.CV)
        ats = analisar_ats(self.CV, stacks)
        assert ats["detalhes"]["contato"]["encontrados"]["linkedin"]

    def test_stacks_core_presentes(self):
        stacks = detectar_stacks(self.CV)
        ids = {s["id"] for s in stacks}
        core = {"python", "csharp", "angular", "dotnet", "docker", "sql"}
        faltando = core - ids
        assert not faltando, f"Stacks core não detectadas no LinkedIn: {faltando}"


class TestATSFormatoCanva:
    """CV do Canva — layout 2 colunas, texto pode vir embaralhado."""

    CV = """
Maria Oliveira                                  Contato
Desenvolvedora Python Pleno                     maria@email.com
São Paulo, SP                                   (11) 91234-5678
                                                linkedin.com/in/maria-oliveira
                                                github.com/mariaoliveira

Sobre Mim                                       Habilidades
Desenvolvedora Python com 5 anos de             Python, Django, FastAPI,
experiência em APIs, automação e dados.          PostgreSQL, Docker, AWS,
                                                 Redis, CI/CD, Git

Experiência
TechCorp | Jan 2022 - Presente
Desenvolvi microsserviços em FastAPI que processam 50.000 requests/dia
Implementei pipelines de CI/CD com GitHub Actions e Docker
Otimizei queries PostgreSQL reduzindo tempo de resposta em 60%

StartupXYZ | Mar 2020 - Dez 2021
Criei sistema de automação em Python que reduziu custos operacionais em 30%

Formação
Bacharelado em Ciência da Computação - USP (2019)

Certificações
AWS Cloud Practitioner
Python Professional Certificate

Idiomas
Português: Nativo
Inglês: Avançado
    """

    def test_score_minimo_60(self):
        stacks = detectar_stacks(self.CV)
        ats = analisar_ats(self.CV, stacks)
        assert ats["score"] >= 60, f"CV Canva scored {ats['score']}, expected >= 60"

    def test_secao_sobre_mim_mapeia_summary(self):
        """'Sobre Mim' (Canva) deve mapear para 'summary'."""
        stacks = detectar_stacks(self.CV)
        ats = analisar_ats(self.CV, stacks)
        assert ats["detalhes"]["secoes"]["encontradas"]["summary"]["found"], "'Sobre Mim' não reconhecida"

    def test_secao_habilidades_mapeia_skills(self):
        stacks = detectar_stacks(self.CV)
        ats = analisar_ats(self.CV, stacks)
        assert ats["detalhes"]["secoes"]["encontradas"]["skills"]["found"], "'Habilidades' não reconhecida no Canva"

    def test_todos_contatos_2_colunas(self):
        """Contatos na coluna direita (Canva) devem ser detectados."""
        stacks = detectar_stacks(self.CV)
        ats = analisar_ats(self.CV, stacks)
        contato = ats["detalhes"]["contato"]["encontrados"]
        assert contato["email"], "Email em coluna direita não detectado"
        assert contato["phone"], "Telefone em coluna direita não detectado"
        assert contato["linkedin"], "LinkedIn em coluna direita não detectado"
        assert contato["github"], "GitHub em coluna direita não detectado"

    def test_verbos_acao_detectados(self):
        stacks = detectar_stacks(self.CV)
        ats = analisar_ats(self.CV, stacks)
        assert ats["detalhes"]["verbos_acao"]["total"] >= 3

    def test_metricas_quantificaveis(self):
        stacks = detectar_stacks(self.CV)
        ats = analisar_ats(self.CV, stacks)
        assert ats["detalhes"]["metricas_quantificaveis"]["total"] >= 2


class TestATSFormatoCVMinimo:
    """CV mínimo/ruim — deve pontuar baixo e gerar sugestões."""

    CV = "João Silva. Trabalho com tecnologia há bastante tempo."

    def test_score_abaixo_30(self):
        stacks = detectar_stacks(self.CV)
        ats = analisar_ats(self.CV, stacks)
        assert ats["score"] < 30, f"CV mínimo scored {ats['score']}, expected < 30"

    def test_classificacao_precisa_melhorar(self):
        stacks = detectar_stacks(self.CV)
        ats = analisar_ats(self.CV, stacks)
        assert ats["classificacao"] == "Precisa Melhorar"

    def test_gera_sugestoes(self):
        stacks = detectar_stacks(self.CV)
        ats = analisar_ats(self.CV, stacks)
        assert len(ats["sugestoes"]) >= 3, "CV ruim deve gerar pelo menos 3 sugestões"

    def test_nenhuma_secao_detectada(self):
        stacks = detectar_stacks(self.CV)
        ats = analisar_ats(self.CV, stacks)
        secoes = ats["detalhes"]["secoes"]["encontradas"]
        total = sum(1 for s in secoes.values() if s["found"])
        assert total == 0, f"CV mínimo não deveria ter seções, mas detectou {total}"


class TestATSConsistencia:
    """Testes de consistência e integridade do engine ATS."""

    def test_score_sempre_entre_0_100(self):
        for cv in ["", "a", "x" * 10000, "Python .NET Angular Docker"]:
            stacks = detectar_stacks(cv)
            ats = analisar_ats(cv, stacks)
            assert 0 <= ats["score"] <= 100, f"Score fora do range: {ats['score']}"

    def test_classificacao_sempre_valida(self):
        validas = {"Excelente", "Bom", "Regular", "Precisa Melhorar"}
        for cv in ["", "test", "Python developer with 10 years experience"]:
            stacks = detectar_stacks(cv)
            ats = analisar_ats(cv, stacks)
            assert ats["classificacao"] in validas, f"Classificação inválida: {ats['classificacao']}"

    def test_detalhes_sempre_presentes(self):
        stacks = detectar_stacks("qualquer texto")
        ats = analisar_ats("qualquer texto", stacks)
        assert "detalhes" in ats
        assert "secoes" in ats["detalhes"]
        assert "verbos_acao" in ats["detalhes"]
        assert "metricas_quantificaveis" in ats["detalhes"]
        assert "contato" in ats["detalhes"]
        assert "comprimento" in ats["detalhes"]
        assert "competencias" in ats["detalhes"]

    def test_resumo_sempre_presente(self):
        stacks = detectar_stacks("qualquer texto")
        ats = analisar_ats("qualquer texto", stacks)
        resumo = ats["resumo"]
        assert "total_palavras" in resumo
        assert "stacks_detectadas" in resumo
        assert "secoes_encontradas" in resumo

    def test_sugestoes_sempre_lista(self):
        stacks = detectar_stacks("qualquer texto")
        ats = analisar_ats("qualquer texto", stacks)
        assert isinstance(ats["sugestoes"], list)

    def test_7_secoes_sempre_avaliadas(self):
        stacks = detectar_stacks("qualquer texto")
        ats = analisar_ats("qualquer texto", stacks)
        secoes = ats["detalhes"]["secoes"]["encontradas"]
        esperadas = {"summary", "experience", "education", "skills", "certifications", "languages", "projects"}
        assert set(secoes.keys()) == esperadas, f"Seções avaliadas: {set(secoes.keys())}, esperado: {esperadas}"

    def test_5_contatos_sempre_avaliados(self):
        stacks = detectar_stacks("qualquer texto")
        ats = analisar_ats("qualquer texto", stacks)
        contato = ats["detalhes"]["contato"]["encontrados"]
        esperados = {"email", "phone", "linkedin", "github", "portfolio"}
        assert set(contato.keys()) == esperados, f"Contatos avaliados: {set(contato.keys())}, esperado: {esperados}"

    def test_score_cresce_com_conteudo(self):
        """CV vazio deve pontuar menos que CV com conteúdo."""
        stacks_vazio = detectar_stacks("")
        ats_vazio = analisar_ats("", stacks_vazio)
        cv_bom = """
        Resumo Profissional
        Desenvolvedor Python.
        Experiência Profissional
        Desenvolvi APIs REST que processam 10.000 requests.
        Formação
        Ciência da Computação
        Competências
        Python, Docker, AWS
        Certificações
        AWS Certificate
        email@test.com
        linkedin.com/in/test
        """
        stacks_bom = detectar_stacks(cv_bom)
        ats_bom = analisar_ats(cv_bom, stacks_bom)
        assert ats_bom["score"] > ats_vazio["score"], "CV com conteúdo deve pontuar mais que vazio"


# ─────────────────────────────────────────────────────────────
#  VALIDAÇÃO CRÍTICA: ATS_CONFIG CARREGADO
# ─────────────────────────────────────────────────────────────
class TestATSConfigCarregado:
    """Garante que o ats_config foi carregado do JSON — impede deploy quebrado."""

    def test_ats_config_nao_vazio(self):
        from main import ATS_CONFIG
        assert ATS_CONFIG, "ATS_CONFIG está vazio — tabelas/stacks_taxonomy.json não foi carregado!"

    def test_sections_expected_tem_7_secoes(self):
        from main import ATS_CONFIG
        secoes = ATS_CONFIG.get("sections_expected", {})
        assert len(secoes) == 7, f"Esperado 7 seções, encontrado {len(secoes)}"

    def test_action_verbs_minimo_80(self):
        from main import ATS_CONFIG
        verbos = ATS_CONFIG.get("action_verbs", [])
        assert len(verbos) >= 80, f"Esperado ≥80 verbos, encontrado {len(verbos)}"

    def test_contact_patterns_tem_5_grupos(self):
        from main import ATS_CONFIG
        contatos = ATS_CONFIG.get("contact_patterns", {})
        assert len(contatos) == 5, f"Esperado 5 grupos de contato, encontrado {len(contatos)}"

    def test_quantifiers_patterns_tem_10(self):
        from main import ATS_CONFIG
        quant = ATS_CONFIG.get("quantifiers_patterns", [])
        assert len(quant) >= 10, f"Esperado ≥10 padrões, encontrado {len(quant)}"

    def test_secoes_contem_chaves_esperadas(self):
        from main import ATS_CONFIG
        secoes = ATS_CONFIG.get("sections_expected", {})
        esperadas = {"summary", "experience", "education", "skills", "certifications", "languages", "projects"}
        assert set(secoes.keys()) == esperadas


# ─────────────────────────────────────────────────────────────
#  FORMATO LINKEDIN PDF REAL (9 páginas = formato exportado)
# ─────────────────────────────────────────────────────────────
class TestATSFormatoLinkedInPDFReal:
    """PDF exportado direto do LinkedIn — 9 páginas, seções em PT-BR misturadas com EN."""

    CV = """
Contato
Gravataí / RS
51984228067 (Mobile)
masilva.arcs@gmail.com
www.linkedin.com/in/marcosprogramador (LinkedIn)
masilvaarcs.github.io/portfolio-hub (Portfolio)

Principais competências
.NET Framework
Angular (Framework)
Microsoft SQL Server

Languages
Inglês (Limited Working)
Português (Native or Bilingual)

Certifications
Certificate of Completion: CSS Fundamentals course
Iniciando com ASP.NET Core
DevOps Essentials Professional Certificate (DEPC)

Honors-Awards
AGILE FUNDAMENTALS

Marcos Santos da Silva
Desenvolvedor Full Stack Sênior | .NET C# · Angular · Python +20 anos de experiência
Gravataí, Rio Grande do Sul, Brasil

Resumo
Desenvolvedor Full Stack Sênior com mais de 20 anos de experiência em sistemas críticos, ERP e WMS.
Especialista em .NET C# e Angular; aplico arquitetura limpa, SOLID e Design Patterns para entregar
soluções escaláveis e seguras. Liderei projetos complexos que integraram operações críticas.

Experiência
Octafy LAD
1 ano 4 meses
Desenvolvedor Full Stack (Angular | .NET)
maio de 2025 - março de 2026 (11 meses)
Gravataí, Rio Grande do Sul, Brasil

Desenvolvi e evoluí 25 componentes de pages em Angular (84% das rotas concluídas)
Integrei frontend Angular ↔ WebAPI RESTful (.NET C#) ↔ WebServices ASMX/SOAP
Criei scripts Python para geração de dashboards de evolução
Elaborei documentação técnica completa (relatórios de evolução, FAQ Técnico v1.3.0)
Utilizei GitHub Copilot e Claude AI para análise de lógica complexa

Grupo Apisul
Desenvolvedor .NET
outubro de 2023 - julho de 2024 (10 meses)
Desenvolvi novas funcionalidades e corrigi bugs em sistemas complexos com .NET e SQL
Executei testes de unidade de forma recorrente
Participei ativamente de rituais ágeis (daily, sprint planning)

Formação acadêmica
Escola Estadual Marechal Mascarenhas de Moraes
Técnico em Processamento de Dados, Informática
1997 - 1999
    """

    def test_score_minimo_60(self):
        stacks = detectar_stacks(self.CV)
        ats = analisar_ats(self.CV, stacks)
        assert ats["score"] >= 60, f"LinkedIn PDF real scored {ats['score']}, expected >= 60"

    def test_secao_resumo(self):
        stacks = detectar_stacks(self.CV)
        ats = analisar_ats(self.CV, stacks)
        assert ats["detalhes"]["secoes"]["encontradas"]["summary"]["found"], "Seção 'Resumo' do LinkedIn não reconhecida"

    def test_secao_experiencia(self):
        stacks = detectar_stacks(self.CV)
        ats = analisar_ats(self.CV, stacks)
        assert ats["detalhes"]["secoes"]["encontradas"]["experience"]["found"], "'Experiência' do LinkedIn não reconhecida"

    def test_secao_formacao_academica(self):
        stacks = detectar_stacks(self.CV)
        ats = analisar_ats(self.CV, stacks)
        assert ats["detalhes"]["secoes"]["encontradas"]["education"]["found"], "'Formação acadêmica' do LinkedIn não reconhecida"

    def test_secao_competencias(self):
        """LinkedIn usa 'Principais competências' — deve mapear para skills."""
        stacks = detectar_stacks(self.CV)
        ats = analisar_ats(self.CV, stacks)
        assert ats["detalhes"]["secoes"]["encontradas"]["skills"]["found"], "'Principais competências' do LinkedIn não reconhecida"

    def test_secao_certifications(self):
        stacks = detectar_stacks(self.CV)
        ats = analisar_ats(self.CV, stacks)
        assert ats["detalhes"]["secoes"]["encontradas"]["certifications"]["found"], "'Certifications' do LinkedIn não reconhecida"

    def test_secao_languages(self):
        stacks = detectar_stacks(self.CV)
        ats = analisar_ats(self.CV, stacks)
        assert ats["detalhes"]["secoes"]["encontradas"]["languages"]["found"], "'Languages' do LinkedIn não reconhecida"

    def test_secao_honors_awards(self):
        """LinkedIn usa 'Honors-Awards' — deve mapear para certifications ou projects."""
        stacks = detectar_stacks(self.CV)
        ats = analisar_ats(self.CV, stacks)
        # honors-awards mapeia para certifications
        certs = ats["detalhes"]["secoes"]["encontradas"]["certifications"]["found"]
        # Se não, pode mapear via projects (honors & awards)
        proj = ats["detalhes"]["secoes"]["encontradas"]["projects"]["found"]
        assert certs or proj, "'Honors-Awards' não reconhecido em nenhuma seção"

    def test_minimo_6_secoes(self):
        stacks = detectar_stacks(self.CV)
        ats = analisar_ats(self.CV, stacks)
        secoes = ats["detalhes"]["secoes"]["encontradas"]
        total = sum(1 for s in secoes.values() if s["found"])
        assert total >= 6, f"Apenas {total}/7 seções no LinkedIn PDF"

    def test_email_detectado(self):
        stacks = detectar_stacks(self.CV)
        ats = analisar_ats(self.CV, stacks)
        assert ats["detalhes"]["contato"]["encontrados"]["email"], "Email não detectado no LinkedIn PDF"

    def test_phone_detectado(self):
        stacks = detectar_stacks(self.CV)
        ats = analisar_ats(self.CV, stacks)
        assert ats["detalhes"]["contato"]["encontrados"]["phone"], "Telefone não detectado no LinkedIn PDF"

    def test_linkedin_detectado(self):
        stacks = detectar_stacks(self.CV)
        ats = analisar_ats(self.CV, stacks)
        assert ats["detalhes"]["contato"]["encontrados"]["linkedin"], "LinkedIn não detectado no LinkedIn PDF"

    def test_portfolio_detectado(self):
        stacks = detectar_stacks(self.CV)
        ats = analisar_ats(self.CV, stacks)
        assert ats["detalhes"]["contato"]["encontrados"]["portfolio"], "Portfolio não detectado no LinkedIn PDF"

    def test_verbos_minimo_5(self):
        stacks = detectar_stacks(self.CV)
        ats = analisar_ats(self.CV, stacks)
        total = ats["detalhes"]["verbos_acao"]["total"]
        assert total >= 5, f"Apenas {total} verbos no LinkedIn PDF"

    def test_metricas_minimo_2(self):
        stacks = detectar_stacks(self.CV)
        ats = analisar_ats(self.CV, stacks)
        total = ats["detalhes"]["metricas_quantificaveis"]["total"]
        assert total >= 2, f"Apenas {total} métricas no LinkedIn PDF"


# ─────────────────────────────────────────────────────────────
#  TESTE ANTI-REGRESSÃO: DOCKERFILE DEVE COPIAR tabelas/
# ─────────────────────────────────────────────────────────────
class TestDockerfileIntegridade:
    """Garante que o Dockerfile copia tabelas/ para o container."""

    def test_dockerfile_copia_tabelas(self):
        import pathlib
        dockerfile = pathlib.Path(__file__).parent.parent / "Dockerfile"
        if dockerfile.exists():
            conteudo = dockerfile.read_text(encoding="utf-8")
            assert "tabelas" in conteudo.lower(), (
                "Dockerfile NÃO copia tabelas/ — ATS ficará zerado em produção!"
            )
