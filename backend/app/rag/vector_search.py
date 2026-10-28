import numpy as np


async def vector_search(conn, project_id, vector, limit):
    rows = await (
        await conn.execute(
            "SELECT c.id AS id_fragmento,c.document_id AS id_documento,c.content AS contenido,"
            "c.page AS pagina,c.position AS posicion,d.name AS documento,d.version AS version_documento,"
            "d.category AS categoria,1-(c.embedding <=> %s) AS puntuacion_vectorial "
            "FROM chunks c JOIN project_knowledge_documents d ON d.id=c.document_id "
            "WHERE d.consumer_project_id=%s AND d.status='indexado' "
            "ORDER BY c.embedding <=> %s,c.id LIMIT %s",
            (
                np.array(vector, dtype=np.float32),
                project_id,
                np.array(vector, dtype=np.float32),
                limit,
            ),
        )
    ).fetchall()
    return [
        {
            **row,
            "id_fragmento": str(row["id_fragmento"]),
            "id_documento": str(row["id_documento"]),
            "posicion_vectorial": rank,
        }
        for rank, row in enumerate(rows, 1)
    ]
