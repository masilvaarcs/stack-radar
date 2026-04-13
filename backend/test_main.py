"""
Testes unitários do Stack Radar — backend.
Cobre: health, stacks, stack/{id}, upload, detecção de stacks, curiosity, STACK_DB.
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
from main import app, STACK_DB, KEYWORDS, detectar_stacks

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
        assert data["total"] == len(STACK_DB)
        assert len(data["stacks"]) == len(STACK_DB)

    def test_stacks_have_required_fields(self):
        data = client.get("/stacks").json()
        for s in data["stacks"]:
            assert "id" in s
            assert "name" in s
            assert "icon" in s
            assert "color" in s
            assert "category" in s

    def test_stacks_total_is_17(self):
        data = client.get("/stacks").json()
        assert data["total"] == 17


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
        result = detectar_stacks("Sou formado em administração de empresas")
        assert len(result) == 0

    def test_all_keywords_have_stack(self):
        """Cada keyword em KEYWORDS deve mapear para um id existente no STACK_DB."""
        for keyword_id in KEYWORDS:
            assert keyword_id in STACK_DB, f"KEYWORDS '{keyword_id}' not in STACK_DB"

    def test_detect_returns_name_and_icon(self):
        result = detectar_stacks("Python")
        assert len(result) > 0
        s = result[0]
        assert "name" in s
        assert "icon" in s
        assert "color" in s


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
