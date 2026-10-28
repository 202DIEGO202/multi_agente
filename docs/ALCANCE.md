# Ajuste de alcance: recuperación sin Neural Reranker

El usuario decidió retirar el Neural Reranker de la fase 1. Este ajuste sustituye los apartados de la especificación original que exigían Cross-Encoder y su visualización. La especificación original se conserva como referencia histórica.

El flujo vigente es:

**Consulta original → reformulación con IA → búsqueda vectorial y BM25 en paralelo → fusión RRF → selección de los primeros FINAL_K fragmentos → analista funcional.**

No se configura ni se invoca una API adicional de reranking. Se retiraron el adaptador, sus variables, los campos específicos del resultado y la pestaña correspondiente del frontend. El contrato de recuperación pasa a versión 1.1. Los contratos funcionales de líneas base conservan su versión 1.0.

Los eventos y resultados de ejecuciones anteriores se conservan como historial. El RAG por API se completó con embeddings Azure y la reindexación de los 98 documentos. La fase 2 se describe en FASE_2.md.
