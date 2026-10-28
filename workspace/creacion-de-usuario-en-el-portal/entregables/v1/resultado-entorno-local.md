# Entorno local v1

Estado: **con_fallos**

- Frontend: http://localhost:8101
- API: http://localhost:8102/api/health
- Pruebas: 1 failed, 6 passed, 9 warnings in 0.79s

## construir_y_levantar (ok)
```
ing attestation manifest sha256:8abf19a8920102c316b60f33cf1c552ff90451a1cac61eb4c6eb990ac36e15bd 0.0s done
#28 exporting manifest list sha256:55d970a71c0f0df3b671acda6eb5e775dc79cedfab430fa20d2f59d8f55b90e9 0.0s done
#28 naming to docker.io/library/trama-creacion-de-usuario-en-el-portal-frontend:latest done
#28 unpacking to docker.io/library/trama-creacion-de-usuario-en-el-portal-frontend:latest 0.0s done
#28 DONE 0.1s

#29 [frontend] resolving provenance for metadata file
#29 DONE 0.0s
 Image trama-creacion-de-usuario-en-el-portal-backend Building 
 Image trama-creacion-de-usuario-en-el-portal-frontend Building 
 Image trama-creacion-de-usuario-en-el-portal-backend Built 
 Image trama-creacion-de-usuario-en-el-portal-frontend Built 
 Container trama-creacion-de-usuario-en-el-portal-db-1 Running 
 Container trama-creacion-de-usuario-en-el-portal-backend-1 Recreate 
 Container trama-creacion-de-usuario-en-el-portal-backend-1 Recreated 
 Container trama-creacion-de-usuario-en-el-portal-frontend-1 Recreate 
 Container trama-creacion-de-usuario-en-el-portal-frontend-1 Recreated 
 Container trama-creacion-de-usuario-en-el-portal-db-1 Waiting 
 Container trama-creacion-de-usuario-en-el-portal-db-1 Healthy 
 Container trama-creacion-de-usuario-en-el-portal-backend-1 Starting 
 Container trama-creacion-de-usuario-en-el-portal-backend-1 Started 
 Container trama-creacion-de-usuario-en-el-portal-frontend-1 Starting 
 Container trama-creacion-de-usuario-en-el-portal-frontend-1 Started 

```
## verificar_salud (ok)
```
API 200 · Frontend 200
```
## ejecutar_pruebas (falló)
```
yle `@field_validator` validators, see the migration guide for more details. Deprecated in Pydantic V2.0 to be removed in V3.0. See Pydantic V2 Migration Guide at https://errors.pydantic.dev/2.14/migration/
    @validator('fecha_nacimiento')

app/main.py:82
  /srv/app/main.py:82: PydanticDeprecatedSince20: Pydantic V1 style `@validator` validators are deprecated. You should migrate to Pydantic V2 style `@field_validator` validators, see the migration guide for more details. Deprecated in Pydantic V2.0 to be removed in V3.0. See Pydantic V2 Migration Guide at https://errors.pydantic.dev/2.14/migration/
    @validator('motivo_rechazo')

tests/test_solicitudes.py::test_PR_001_crear_solicitud_valida
tests/test_solicitudes.py::test_PR_004_obtener_solicitud_detallada
tests/test_solicitudes.py::test_PR_005_aprobar_solicitud
tests/test_solicitudes.py::test_PR_006_rechazar_solicitud_con_motivo
tests/test_solicitudes.py::test_PR_007_rechazar_solicitud_sin_motivo
  /srv/app/main.py:141: PydanticDeprecatedSince20: The `dict` method is deprecated; use `model_dump` instead. Deprecated in Pydantic V2.0 to be removed in V3.0. See Pydantic V2 Migration Guide at https://errors.pydantic.dev/2.14/migration/
    **solicitud.dict()

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED tests/test_solicitudes.py::test_PR_007_rechazar_solicitud_sin_motivo
1 failed, 6 passed, 9 warnings in 0.79s

```