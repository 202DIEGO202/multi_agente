# Revisión integral de calidad · 26/10/2026

## Alcance

Se revisaron la arquitectura, los contratos entre fases, el uso de modelos por API, la configuración de red,
el manejo de errores, la generación de aplicaciones, la documentación y las validaciones disponibles. La
plataforma ya implementa cinco fases: análisis y RAG, backlog, mockups, arquitectura y construcción.

## Cambios realizados

- El backend continúa enlazado a `127.0.0.1:8000` por defecto. `API_HOST` y `API_PORT` permiten configurar
  ese enlace de forma explícita.
- Si `API_HOST` no es loopback, la configuración exige `API_TOKEN` y rechaza `CORS_ORIGINS` con comodín
  o HTTP para orígenes externos. Esto evita publicar por accidente una API sin autenticación básica.
- Los errores HTTP no controlados devuelven `500` en vez de `503`, registran método, ruta y tipo de error
  sin incluir datos del usuario, y no filtran el detalle interno en la respuesta.
- Las pruebas de grafos usan el mismo tipo de bucle de eventos compatible con Windows que el arranque del
  backend.
- La guía principal documenta las variables de red y deja claro que un token compartido no sustituye
  inicio de sesión corporativo ni control de identidad por usuario.

## Comprobaciones ejecutadas

- `backend/tests/test_core.py`: 10 pruebas aprobadas, incluidas las nuevas reglas de configuración.
- Ruff sobre backend y pruebas modificadas: sin errores.
- Pruebas del frontend: 3 aprobadas.
- No se realizaron llamadas a Azure, ingestas ni generaciones; no se consumieron tokens ni se alteró la
  base de datos del proyecto.

## Límites de esta revisión

Actualización del 27/10/2026: las tres limitaciones de ejecución descritas a continuación
se resolvieron ejecutando las comprobaciones con los permisos necesarios. PostgreSQL, asyncio,
la compilación de Angular y Docker sí se pudieron verificar. No eran defectos confirmados del
runtime. La nueva revisión se documenta en `REVISION_CALIDAD_20261027.md`.

- Docker Desktop no aceptó conexión con su motor; por ello no se ejecutaron las pruebas de PostgreSQL ni
  la verificación de las aplicaciones generadas en contenedores.
- El runtime Python de este entorno se bloquea al crear el `socketpair` de asyncio en Windows. Por ello
  no se completó aquí la suite de grafos, aunque se alineó su inicialización con el bucle de eventos del
  arranque de la aplicación.
- El proceso de compilación de Angular terminó con una excepción nativa de Node en este entorno. Las
  pruebas del lector SSE sí pasaron, pero la compilación visual queda pendiente de repetir en un entorno
  de Node estable.
- La carpeta de trabajo no contiene metadatos de Git. Por tanto, aquí no hay historial local para revisar
  diffs, preparar una reversión o integrar cambios en CI.
- La autenticación de la plataforma sigue siendo un token compartido. Para operar con usuarios corporativos
  se necesita integrar OIDC/Entra ID, asignación de roles y sesiones seguras; esa decisión requiere el
  tenant y la aplicación de identidad de la organización.

## Siguiente orden de madurez

1. Incorporar esta carpeta al repositorio Git oficial y activar CI para Ruff, pruebas con PostgreSQL,
   `npm test` y compilación Angular.
2. Integrar OIDC/Entra ID y roles para sustituir el token compartido como identidad de operador.
3. Repetir las pruebas completas con Docker disponible y revisar la generación/despliegue de extremo a
   extremo antes de llamar empresarial a la fase 5.
4. Auditar dependencias Python y npm, y generar un SBOM por versión de aplicación construida.
5. Reducir el tiempo y el coste de construcción con imágenes base verificadas, límites de presupuesto por
   ejecución y caché de dependencias, conservando los controles de seguridad existentes.

## Criterio de calidad

No existe una forma responsable de garantizar código generado «100 % perfecto». La garantía práctica debe
ser una cadena de controles repetibles: contratos, trazabilidad, análisis estático, pruebas, compilación,
verificación de runtime y revisión humana. Una etapa solo debe publicarse cuando sus controles requeridos
pasen; una revisión pendiente debe identificarse claramente y conservar sus versiones previas.
