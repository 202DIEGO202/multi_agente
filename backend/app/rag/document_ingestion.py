import asyncio
import hashlib
import io
import re
import unicodedata
from pathlib import Path
from uuid import NAMESPACE_URL, uuid4, uuid5

import numpy as np
from pypdf import PdfReader


def extract_pages(content: bytes, filename: str) -> list[tuple[int, str]]:
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        if not content.lstrip().startswith(b"%PDF-"):
            raise ValueError("El contenido no corresponde a un PDF")
        reader = PdfReader(io.BytesIO(content))
        if reader.is_encrypted:
            raise ValueError("No se admiten PDF cifrados")
        pages = [(n + 1, p.extract_text() or "") for n, p in enumerate(reader.pages)]
    elif suffix in {".txt", ".md"}:
        pages = [(1, content.decode("utf-8-sig"))]
    else:
        raise ValueError("Tipos admitidos: PDF, TXT y Markdown")
    normalized = [
        (
            page,
            re.sub(r"[ \t]+", " ", unicodedata.normalize("NFKC", text)).replace("\x00", "").strip(),
        )
        for page, text in pages
    ]
    if not any(text for _, text in normalized):
        raise ValueError("Documento sin texto extraíble; requiere OCR antes de la carga")
    return normalized


def split_pages(pages, document_id: str, content_hash: str, size: int, overlap: int):
    chunks = []
    for page, text in pages:
        start = 0
        while start < len(text):
            end = min(start + size, len(text))
            if end < len(text):
                boundary = text.rfind(" ", start + size // 2, end)
                if boundary > start:
                    end = boundary
            fragment = text[start:end].strip()
            if fragment:
                chunks.append(
                    {
                        "id": str(
                            uuid5(
                                NAMESPACE_URL,
                                f"{document_id}:{content_hash}:{page}:{start}:{size}:{overlap}",
                            )
                        ),
                        "page": page,
                        "position": start,
                        "content": fragment,
                    }
                )
            if end == len(text):
                break
            start = max(start + 1, end - overlap)
    return chunks


class DocumentIngestion:
    def __init__(self, db, models, settings, events):
        self.db, self.models, self.settings, self.events = db, models, settings, events

    async def ingest(
        self,
        project_id: str,
        filename: str,
        content: bytes,
        run_id: str,
        category: str = "documentacion",
        force=False,
    ):
        if not self.settings.embedding_model:
            raise ValueError("Configure la API de embeddings antes de indexar documentos.")
        name = Path(filename.replace("\\", "/")).name
        if not name or len(name) > 255 or len(content) > self.settings.max_upload_mb * 1024**2:
            raise ValueError("Nombre inválido o documento demasiado grande")
        digest = hashlib.sha256(content).hexdigest()
        doc_id = str(uuid5(NAMESPACE_URL, f"{project_id}:{name.casefold()}"))
        if not force:
            reusable = await self.db.one(
                "SELECT id FROM project_knowledge_documents WHERE consumer_project_id=%s AND lower(name)=lower(%s) "
                "AND content_hash=%s AND status='indexado' AND embedding_signature=%s LIMIT 1",
                (project_id, name, digest, self.settings.embedding_signature),
            )
            if reusable:
                await self.events.emit(
                    run_id,
                    "ingesta",
                    "reutilizar",
                    "completado",
                    f"Sin cambios: {name}; se reutilizó la indexación existente",
                    {"id_documento": str(reusable["id"]), "sin_inferencia": True},
                )
                return str(reusable["id"])
        await self.events.emit(run_id, "ingesta", "extraer", "ejecutando", f"Procesando {name}")
        pages = await asyncio.to_thread(extract_pages, content, name)
        chunks = split_pages(
            pages, doc_id, digest, self.settings.chunk_size, self.settings.chunk_overlap
        )
        existing = await self.db.one("SELECT * FROM documents WHERE id=%s", (doc_id,))
        if (
            existing
            and existing["status"] == "indexado"
            and existing["content_hash"] == digest
            and existing["embedding_signature"] == self.settings.embedding_signature
            and not force
        ):
            await self.events.emit(
                run_id,
                "ingesta",
                "indexar",
                "omitido",
                "Documento ya vigente",
                {"id_documento": doc_id},
            )
            return doc_id
        vectors = []
        for start in range(0, len(chunks), 16):
            vectors.extend(
                await self.models.embed([c["content"] for c in chunks[start : start + 16]])
            )
        directory = self.settings.storage_dir / str(project_id)
        directory.mkdir(parents=True, exist_ok=True)
        destination = directory / (digest + Path(name).suffix.lower())
        await asyncio.to_thread(destination.write_bytes, content)
        async with self.db.pool.connection() as conn, conn.transaction():
            # Serializa modificaciones documentales y revisiones del mismo proyecto.
            await conn.execute("SELECT id FROM projects WHERE id=%s FOR UPDATE", (project_id,))
            current = await (
                await conn.execute("SELECT * FROM documents WHERE id=%s", (doc_id,))
            ).fetchone()
            if (
                current
                and current["status"] == "indexado"
                and current["content_hash"] == digest
                and not force
                and current["embedding_signature"] == self.settings.embedding_signature
            ):
                return doc_id
            media = "application/pdf" if name.lower().endswith(".pdf") else "text/plain"
            await conn.execute(
                "INSERT INTO documents(id,project_id,name,media_type,category,content_hash,status,"
                "embedding_signature,storage_path) VALUES(%s,%s,%s,%s,%s,%s,'indexado',%s,%s) "
                "ON CONFLICT(id) DO UPDATE SET content_hash=excluded.content_hash,"
                "version=CASE WHEN documents.status='error' THEN documents.version ELSE documents.version+1 END,"
                "status='indexado',last_error=NULL,"
                "embedding_signature=excluded.embedding_signature,storage_path=excluded.storage_path,"
                "updated_at=now()",
                (
                    doc_id,
                    project_id,
                    name,
                    media,
                    category,
                    digest,
                    self.settings.embedding_signature,
                    str(destination),
                ),
            )
            await conn.execute(
                "INSERT INTO document_versions(document_id,version,storage_path,content_hash,name,media_type) "
                "SELECT id,version,storage_path,content_hash,name,media_type FROM documents WHERE id=%s "
                "ON CONFLICT DO NOTHING",
                (doc_id,),
            )
            await conn.execute("DELETE FROM chunks WHERE document_id=%s", (doc_id,))
            async with conn.cursor() as cursor:
                await cursor.executemany(
                    "INSERT INTO chunks(id,document_id,page,position,content,embedding) "
                    "VALUES(%s,%s,%s,%s,%s,%s)",
                    [
                        (
                            c["id"],
                            doc_id,
                            c["page"],
                            c["position"],
                            c["content"],
                            np.array(v, dtype=np.float32),
                        )
                        for c, v in zip(chunks, vectors, strict=True)
                    ],
                )
            await conn.execute(
                "UPDATE projects SET knowledge_revision=knowledge_revision+1 WHERE id=%s",
                (project_id,),
            )
        await self.events.emit(
            run_id,
            "ingesta",
            "indexar",
            "completado",
            f"Indexado: {name}",
            {"id_documento": doc_id, "fragmentos": len(chunks), "paginas": len(pages)},
        )
        return doc_id

    async def record_failure(self, project_id, filename, content, category, message):
        name = Path(filename.replace("\\", "/")).name
        digest = hashlib.sha256(content).hexdigest()
        doc_id = str(uuid5(NAMESPACE_URL, f"{project_id}:{name.casefold()}"))
        directory = self.settings.storage_dir / str(project_id)
        directory.mkdir(parents=True, exist_ok=True)
        destination = directory / (digest + Path(name).suffix.lower())
        await asyncio.to_thread(destination.write_bytes, content)
        async with self.db.pool.connection() as conn, conn.transaction():
            await conn.execute("SELECT id FROM projects WHERE id=%s FOR UPDATE", (project_id,))
            await conn.execute(
                "INSERT INTO documents(id,project_id,name,media_type,category,content_hash,status,"
                "embedding_signature,storage_path,last_error) VALUES(%s,%s,%s,%s,%s,%s,'error',%s,%s,%s) "
                "ON CONFLICT(id) DO UPDATE SET last_error=excluded.last_error",
                (
                    doc_id,
                    project_id,
                    name,
                    "application/pdf" if name.lower().endswith(".pdf") else "text/plain",
                    category,
                    digest,
                    self.settings.embedding_signature,
                    str(destination),
                    message,
                ),
            )

    async def delete(self, project_id, doc_id):
        async with self.db.pool.connection() as conn, conn.transaction():
            await conn.execute("SELECT id FROM projects WHERE id=%s FOR UPDATE", (project_id,))
            linked = await conn.execute(
                "DELETE FROM project_document_links WHERE project_id=%s AND document_id=%s",
                (project_id, doc_id),
            )
            if linked.rowcount:
                run_id = str(uuid4())
                await conn.execute(
                    "INSERT INTO executions(id,project_id,kind,status,input,finished_at) VALUES(%s,%s,'conocimiento','completado','{}',now())",
                    (run_id, project_id),
                )
                await conn.execute(
                    "INSERT INTO events(execution_id,component,operation,status,description,data) VALUES(%s,'conocimiento','desvincular_documento','completado','Documento desvinculado; el original se conserva',jsonb_build_object('id_documento',%s::text))",
                    (run_id, str(doc_id)),
                )
                return True
            owned = await (
                await conn.execute(
                    "SELECT id FROM documents WHERE project_id=%s AND id=%s", (project_id, doc_id)
                )
            ).fetchone()
            if not owned:
                return False
            consumers = await (
                await conn.execute(
                    "SELECT 1 FROM project_document_links WHERE document_id=%s LIMIT 1", (doc_id,)
                )
            ).fetchone()
            if consumers:
                raise ValueError(
                    "Este documento se usa en otros proyectos. Desvincúlalo de ellos antes de eliminar el original."
                )
            result = await conn.execute(
                "DELETE FROM documents WHERE project_id=%s AND id=%s", (project_id, doc_id)
            )
            if result.rowcount:
                await conn.execute(
                    "UPDATE projects SET knowledge_revision=knowledge_revision+1 WHERE id=%s",
                    (project_id,),
                )
            return bool(result.rowcount)
