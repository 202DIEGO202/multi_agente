def reciprocal_rank_fusion(vector_results, bm25_results, k=60):
    fused = {}
    for label, results in (("vectorial", vector_results), ("bm25", bm25_results)):
        for position, item in enumerate(results, 1):
            key = str(item["id_fragmento"])
            record = fused.setdefault(key, {**item, "puntuacion_rrf": 0.0})
            record.update(item)
            record[f"posicion_{label}"] = position
            record["puntuacion_rrf"] += 1.0 / (k + position)
    ordered = sorted(fused.values(), key=lambda row: (-row["puntuacion_rrf"], row["id_fragmento"]))
    return [{**row, "posicion_rrf": rank} for rank, row in enumerate(ordered, 1)]
