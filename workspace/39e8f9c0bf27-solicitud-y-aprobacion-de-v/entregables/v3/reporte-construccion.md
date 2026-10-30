# Reporte de construcción v3

Aplicaciones: portal, panel. Arquitectura v4, backlog v1.

## Validación (reglas, ejecución real en Docker y revisión)
- **error** · desarrollador_portal · IMPORT_LOCAL_AUSENTE: portal/src/app/routes.ts importa ./solicitudes-ausencia.component, pero el componente no fue entregado. Devuelva todos los archivos de la aplicación, incluidas sus rutas. `portal/src/app/routes.ts`
- **error** · desarrollador_portal · IMPORT_LOCAL_AUSENTE: portal/src/app/routes.ts importa ./notificaciones-detalle-solicitud.component, pero el componente no fue entregado. Devuelva todos los archivos de la aplicación, incluidas sus rutas. `portal/src/app/routes.ts`
- **error** · desarrollador_portal · IMPORT_LOCAL_AUSENTE: portal/src/app/routes.ts importa ./validacion-talento-humano.component, pero el componente no fue entregado. Devuelva todos los archivos de la aplicación, incluidas sus rutas. `portal/src/app/routes.ts`
- **error** · desarrollador_portal · IMPORT_LOCAL_AUSENTE: portal/src/app/routes.ts importa ./administracion-tipos-ausencia.component, pero el componente no fue entregado. Devuelva todos los archivos de la aplicación, incluidas sus rutas. `portal/src/app/routes.ts`
- **error** · desarrollador_backend · LISTADO_PUBLICO_DUPLICADO: /api/tipos-ausencia es público y expone los mismos datos que el administrativo /api/admin/tipos-ausencia `backend/app/main.py`
- **error** · desarrollador_panel · ENDPOINT_INEXISTENTE: La interfaz llama a /api/admin${path}, que no existe en el backend 
- **error** · desarrollador_portal · PANTALLA_INCOMPLETA: PA-001 · Solicitudes de ausencia: faltan campos o textos del mockup (cobertura 0%) 
- **error** · desarrollador_portal · PANTALLA_INCOMPLETA: PA-002 · Notificaciones y detalle de solicitud: faltan campos o textos del mockup (cobertura 0%) 
- **error** · desarrollador_portal · PANTALLA_INCOMPLETA: PA-004 · Validación de Talento Humano: faltan campos o textos del mockup (cobertura 40%) 
- **error** · desarrollador_portal · PANTALLA_INCOMPLETA: PA-005 · Administración de tipos de ausencia: faltan campos o textos del mockup (cobertura 20%) 
- **advertencia** · agente_pruebas · CRITERIOS_SIN_PRUEBA: Criterios sin caso de prueba: HU-001-CA-01, HU-001-CA-02, HU-001-CA-03, HU-001-CA-04, HU-002-CA-01, HU-002-CA-02, HU-003-CA-04, HU-004-CA-01, HU-004-CA-02, HU-004-CA-03 

## Casos de prueba
| ID | Criterio | Archivo | Descripción |
|---|---|---|---|
| PR-001 | HU-005-CA-01 | `backend/tests/test_api_autorizacion_y_catalogo.py` | Verifica que /api/admin/tipos-ausencia rechaza sin token o con token inválido, y que el catálogo público difiere del administrativo en campos expuestos. |
| PR-002 | HU-005-CA-02 | `backend/tests/test_api_autorizacion_y_catalogo.py` | Crea y actualiza un tipo de ausencia con flujo de aprobación usando datos únicos y valida que la operación administrativa responde con éxito. |
| PR-003 | HU-005-CA-01 | `backend/tests/test_api_autorizacion_y_catalogo.py` | Comprueba que un código de tipo de ausencia duplicado es rechazado por la API administrativa. |
| PR-004 | HU-003-CA-01 | `backend/tests/test_aprobaciones_y_bandeja.py` | Verifica que la bandeja administrativa de pendientes exige autenticación y, con token correcto, responde con éxito y una lista. |
| PR-005 | HU-003-CA-02 | `backend/tests/test_aprobaciones_y_bandeja.py` | Valida que aprobar una solicitud exige observación y que una solicitud inexistente devuelve 404. |
| PR-006 | HU-003-CA-03 | `backend/tests/test_rechazo_y_validaciones.py` | Verifica que rechazar una solicitud exige autenticación y observación no vacía. |
| PR-007 | HU-003-CA-02 | `backend/tests/test_aprobaciones_y_bandeja.py` | Comprueba que una versión inválida en una decisión de aprobación provoca conflicto o no encontrado, según el estado del recurso. |

## Consumo por agente
| Agente | Llamadas | Tokens entrada | Tokens salida | Tiempo |
|---|---|---|---|---|
| desarrollador_datos | 1 | 7026 | 2432 | 10.3 s |
| desarrollador_backend | 3 | 34368 | 8356 | 33.2 s |
| desarrollador_portal | 3 | 30311 | 10986 | 41.0 s |
| agente_pruebas | 3 | 55351 | 13290 | 60.2 s |
| agente_iac | 1 | 1285 | 2252 | 13.9 s |
| desarrollador_panel | 3 | 20642 | 4783 | 20.9 s |
