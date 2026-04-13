"""
Testes unitários do Stack Radar — backend.
Cobre: health, stacks, stack/{id}, upload, detecção de stacks, curiosity, STACK_DB, ATS.
"""
import sys
import os
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
