# Desarrollo completo y verificación

El módulo **Desarrollo completo** permite iniciar una cadena persistente:

1. Consultar la documentación vinculada y analizar el objetivo.
2. Consolidar requisitos y publicar una línea base vigente.
3. Organizar épicas, features e historias comprobables.
4. Diseñar las pantallas y clasificar los criterios exclusivamente internos.
5. Definir arquitectura y plan de implementación.
6. Construir código, revisar contratos, compilar en Docker y ejecutar pruebas.
7. Revisar semánticamente los archivos producidos y guardar una versión.
8. Iniciar una instancia local solamente si se solicitó al comienzo.

## Dos modos

**Automático:** avanza cuando los controles de cada etapa lo permiten. No resuelve decisiones
de negocio inventando políticas. Preguntas, contradicciones, fallos y falta de verificación
real detienen la entrega.

**Manual:** prepara una etapa y espera revisión/aprobación. El analista puede editar sus
elementos, resolver preguntas y publicar nuevas versiones antes de continuar.

La aprobación automática se identifica como tal; nunca figura como aprobación humana.
La construcción con observaciones pendientes requiere revisión humana aunque las pruebas
pasen: una advertencia del modelo no demuestra que el incumplimiento sea opcional.
Cambiar el modo mientras el flujo está detenido se registra al continuar.

## Recuperación y trazabilidad

Cada flujo tiene su conversación, ejecución principal, ejecuciones por etapa, versiones y
fuentes. Un identificador de solicitud repetido no inicia otro trabajo. El avance persiste
en PostgreSQL y los agentes conservan sus puntos de recuperación en LangGraph.

**Continuar** recupera el avance. **Generar otro intento** repite la etapa seleccionada
cuando se corrigió la causa, conserva los intentos previos y consume API. En construcción,
si las fuentes no cambiaron, recupera el candidato anterior para corregirlo y volverlo a
verificar, sin regenerar todos los agentes desde cero. Cada ejecución mantiene límites de
corrección; no existe un bucle ilimitado de gasto.

Los criterios de persistencia y auditoría sin interacción no necesitan controles ficticios:
quedan declarados y justificados como internos, se revisan semánticamente y siguen siendo
obligatorios en la implementación y las pruebas. Un criterio visible no puede excluirse
válidamente de esa forma.

## Pruebas reproducibles

Desde `backend`, con el entorno virtual del proyecto:

```powershell
..\.venv\Scripts\python.exe scripts/quality_tests.py -m 'not live' -q
..\.venv\Scripts\python.exe scripts/validate_workflow_live.py returns
..\.venv\Scripts\python.exe scripts/validate_workflow_live.py conflict
..\.venv\Scripts\python.exe scripts/validate_workflow_live.py missing
..\.venv\Scripts\python.exe scripts/validate_workflow_live.py helpdesk
```

La primera orden usa `fabrica_test`, sin llamar al modelo. Las evaluaciones reales usan
`fabrica_test_e2e`, Azure y Docker. Copian documentos y vectores ya indexados sin reembeddings;
no modifican los proyectos originales. No ejecutar evaluaciones reales simultáneas en esa
misma base. Los informes se guardan en `output/quality/`.

Para un fallo transitorio: añadir `--resume`. Después de corregir la causa de una etapa
inválida: añadir `--resume --retry`. Estas órdenes conservan los informes e historial en
la base de pruebas; el archivo del escenario muestra la última ejecución.

## Alcance operativo

La plantilla soportada es FastAPI, PostgreSQL, Angular, Docker y Terraform para AWS.
La verificación local no acredita un despliegue productivo en AWS ni una integración real
con AD, pagos, correo o sistemas corporativos. Estas requieren configuración y validación
en el entorno destino. La autenticación de la plataforma necesita configuración antes de
exponerse fuera del equipo. Superar pruebas no demuestra perfección para cualquier dominio.
