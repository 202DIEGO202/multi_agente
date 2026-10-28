import re
import threading
from collections import OrderedDict

from rank_bm25 import BM25Okapi


def tokenize(text: str):
    return re.findall(r"[\w]+(?:[-./][\w]+)*", text.casefold(), flags=re.UNICODE)


class BM25Search:
    """El contador transaccional invalida el índice al modificar o borrar documentos."""

    def __init__(self):
        self.cache = OrderedDict()
        self.lock = threading.Lock()

    def search(self, project_id, revision, rows, query, limit):
        if not rows:
            return []
        key = (str(project_id), revision)
        with self.lock:
            index = self.cache.get(key)
            if index is None:
                index = BM25Okapi([tokenize(r["contenido"]) or [""] for r in rows], epsilon=0.25)
                self.cache[key] = index
                while len(self.cache) > 16:
                    self.cache.popitem(last=False)
        scores = index.get_scores(tokenize(query))
        # BM25 puede dar IDF cero con corpus diminutos; conserva coincidencias reales.
        terms = set(tokenize(query))
        indices = sorted(
            range(len(rows)), key=lambda i: (-float(scores[i]), str(rows[i]["id_fragmento"]))
        )
        selected = [i for i in indices if terms.intersection(tokenize(rows[i]["contenido"]))][
            :limit
        ]
        return [
            {**rows[i], "puntuacion_bm25": float(scores[i]), "posicion_bm25": rank}
            for rank, i in enumerate(selected, 1)
        ]
