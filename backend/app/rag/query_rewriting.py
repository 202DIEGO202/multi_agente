import re

from pydantic import BaseModel, Field


class RewrittenQuery(BaseModel):
    consulta: str = Field(min_length=1, max_length=3000)


async def rewrite_query(models, original, context):
    result = await models.json(
        [
            {
                "role": "system",
                "content": (
                    "Optimiza la consulta para buscar documentación en español. Conserva intención, nombres, "
                    "códigos e identificadores exactos. No inventes datos ni contestes la consulta. "
                    "Si ya es precisa, consérvala. El contexto solo resuelve referencias."
                ),
            },
            {
                "role": "user",
                "content": f"Contexto: {context[-6000:]}\nConsulta original: {original}",
            },
        ],
        RewrittenQuery,
        rewrite=True,
    )
    protected = re.findall(
        r"\b[A-ZÁÉÍÓÚÑ]{2,}(?:[-_./][A-Za-z0-9]+)*\b|\b\w*\d\w*(?:[-_./]\w+)*", original
    )
    if any(term.casefold() not in result.consulta.casefold() for term in protected):
        raise ValueError("La reformulación omitió un identificador de la consulta")
    return result.consulta
