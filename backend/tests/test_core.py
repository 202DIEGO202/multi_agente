import pytest
from pydantic import ValidationError

from app.config import Settings
from app.models.schemas import Change
from app.rag.bm25_search import BM25Search
from app.rag.document_ingestion import extract_pages, split_pages
from app.rag.rank_fusion import reciprocal_rank_fusion
from app.services.events import clean
from app.services.project_service import validate_change


def test_rrf_deduplicates_and_preserves_explanations():
    a = {"id_fragmento": "a", "puntuacion_vectorial": 0.8}
    b = {"id_fragmento": "b", "puntuacion_vectorial": 0.7}
    result = reciprocal_rank_fusion([a, b], [{"id_fragmento": "b", "puntuacion_bm25": 4}])
    assert [r["id_fragmento"] for r in result] == ["b", "a"]
    assert result[0]["puntuacion_rrf"] == pytest.approx(1 / 62 + 1 / 61)
    assert result[0]["posicion_vectorial"] == 2
    assert result[0]["posicion_bm25"] == 1


def test_chunk_ids_are_stable_and_pages_remain_citable():
    pages = [(1, "Inicio " * 150), (2, "Final " * 150)]
    chunks = split_pages(pages, "doc", "hash", 200, 30)
    assert chunks == split_pages(pages, "doc", "hash", 200, 30)
    assert len({c["id"] for c in chunks}) == len(chunks)
    assert {c["page"] for c in chunks} == {1, 2}
    assert all(0 < len(c["content"]) <= 200 for c in chunks)
    assert chunks[0]["id"] != split_pages(pages, "doc", "nuevo", 200, 30)[0]["id"]


def test_ingestion_rejects_wrong_type_and_empty_files():
    with pytest.raises(ValueError):
        extract_pages(b"No es pdf", "archivo.pdf")
    with pytest.raises(ValueError):
        extract_pages(b"", "vacio.txt")
    assert (
        extract_pages("MFA: contraseña segura".encode(), "guia.txt")[0][1]
        == "MFA: contraseña segura"
    )


def test_bm25_revision_and_project_scope_invalidate_cache():
    search = BM25Search()
    rows = [
        {"id_fragmento": "a", "contenido": "VPN corporativa"},
        {"id_fragmento": "b", "contenido": "vacaciones y permisos"},
    ]
    assert search.search("p1", 1, rows, "VPN", 5)[0]["id_fragmento"] == "a"
    assert search.search("p1", 2, rows[1:], "VPN", 5) == []
    assert search.search("p2", 1, rows[1:], "VPN", 5) == []


def test_contract_requires_version_on_modification():
    with pytest.raises(ValidationError):
        Change(
            operacion="modificar",
            tipo="requisito_funcional",
            descripcion="Cambio",
            id_elemento="RF-001",
        )
    with pytest.raises(ValidationError):
        Change(
            operacion="crear", tipo="requisito_funcional", descripcion="Nuevo", id_elemento="RF-001"
        )


def test_functional_validation_blocks_duplicates_stale_versions_and_missing_refs():
    items = [
        {
            "id": "RF-001",
            "tipo": "requisito_funcional",
            "descripcion": "Registrar usuarios",
            "version": 2,
            "vigencia": "vigente",
        }
    ]
    duplicate = Change(
        operacion="crear", tipo="requisito_funcional", descripcion="Registrar USUARIOS."
    )
    assert "duplicada" in validate_change(duplicate, items)[0]
    stale = Change(
        operacion="modificar",
        tipo="requisito_funcional",
        descripcion="Cambio",
        id_elemento="RF-001",
        version_esperada=1,
        referencias=["DEC-404"],
    )
    assert len(validate_change(stale, items)) == 2


def test_sensitive_fields_are_not_exposed():
    value = clean(
        {
            "consulta": "hola",
            "nested": [{"api_key": "secreto", "thinking": "privado", "texto": "visible"}],
        }
    )
    assert value == {"consulta": "hola", "nested": [{"texto": "visible"}]}


def test_invalid_chunk_configuration_is_rejected():
    with pytest.raises(ValidationError):
        Settings(chunk_size=200, chunk_overlap=200)


def test_external_api_binding_requires_authentication():
    with pytest.raises(ValidationError, match="API_TOKEN es obligatorio"):
        Settings(_env_file=None, api_host="0.0.0.0")


def test_external_api_binding_rejects_insecure_cors_origins():
    with pytest.raises(ValidationError, match="CORS_ORIGINS debe usar HTTPS"):
        Settings(
            _env_file=None,
            api_host="0.0.0.0",
            api_token="test-token",
            cors_origins=["http://portal.example.com"],
        )
    settings = Settings(
        _env_file=None,
        api_host="0.0.0.0",
        api_token="test-token",
        cors_origins=["https://portal.example.com", "http://localhost:4200"],
    )
    assert settings.api_host == "0.0.0.0"
