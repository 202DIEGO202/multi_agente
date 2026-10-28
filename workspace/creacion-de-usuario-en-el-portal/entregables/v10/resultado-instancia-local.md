# Instancia local v10

Estado: **completado**

- portal: http://localhost:8100
- api: http://localhost:8100/api/health
- panel: http://localhost:8103
- Pruebas: 7 passed, 1 warning in 0.60s
- Variables de administración: infraestructura-local/instancias/creacion-de-usuario-en-el-portal-v10/.env

## preparar_instancia (ok)
```
Instancia creacion-de-usuario-en-el-portal-v10 preparada en C:\Users\Equipo\Documents\Estudios\Javeriana cali\Topicos Avanzados\Entrega 2 Brayan\infraestructura-local\instancias\creacion-de-usuario-en-el-portal-v10
```
## base_de_datos (ok)
```
 Network ec2-creacion-de-usuario-en-el-portal-v10_default Creating 
 Volume ec2-creacion-de-usuario-en-el-portal-v10_db-data Creating 
 Network ec2-creacion-de-usuario-en-el-portal-v10_default Creating 
 Volume ec2-creacion-de-usuario-en-el-portal-v10_db-data Creating 
 Volume ec2-creacion-de-usuario-en-el-portal-v10_db-data Created 
 Volume ec2-creacion-de-usuario-en-el-portal-v10_db-data Created 
 Network ec2-creacion-de-usuario-en-el-portal-v10_default Created 
 Network ec2-creacion-de-usuario-en-el-portal-v10_default Created 
 Container ec2-creacion-de-usuario-en-el-portal-v10-db-1 Creating 
 Container ec2-creacion-de-usuario-en-el-portal-v10-db-1 Created 
 Container ec2-creacion-de-usuario-en-el-portal-v10-db-1 Starting 
 Container ec2-creacion-de-usuario-en-el-portal-v10-db-1 Started 
 Container ec2-creacion-de-usuario-en-el-portal-v10-db-1 Waiting 
 Container ec2-creacion-de-usuario-en-el-portal-v10-db-1 Healthy 

```
## backend (ok)
```
52756b08f7472a43
#11 exporting config sha256:3fcaca1df6cad048d1e3060cde077fea6e745f0429654aa752756b08f7472a43 0.0s done
#11 exporting attestation manifest sha256:648097734de5806bd73e153f8d41f3a3e5f99a7a2a7d1b88a2c7ca645eb1c0d3 0.0s done
#11 exporting manifest list sha256:3ab96a0894b0627ceddfb6ec043d8cfd6879cca6f4f3f5877a7356f2d6a4446b 0.0s done
#11 naming to docker.io/library/ec2-creacion-de-usuario-en-el-portal-v10-backend:latest done
#11 unpacking to docker.io/library/ec2-creacion-de-usuario-en-el-portal-v10-backend:latest 0.0s done
#11 DONE 0.1s

#12 resolving provenance for metadata file
#12 DONE 0.0s
 Image ec2-creacion-de-usuario-en-el-portal-v10-backend Building 
 Image ec2-creacion-de-usuario-en-el-portal-v10-backend Built 
 Container ec2-creacion-de-usuario-en-el-portal-v10-db-1 Running 
 Container ec2-creacion-de-usuario-en-el-portal-v10-backend-1 Creating 
 Container ec2-creacion-de-usuario-en-el-portal-v10-backend-1 Created 
 Container ec2-creacion-de-usuario-en-el-portal-v10-db-1 Waiting 
 Container ec2-creacion-de-usuario-en-el-portal-v10-db-1 Healthy 
 Container ec2-creacion-de-usuario-en-el-portal-v10-backend-1 Starting 
 Container ec2-creacion-de-usuario-en-el-portal-v10-backend-1 Started 
 Container ec2-creacion-de-usuario-en-el-portal-v10-db-1 Waiting 
 Container ec2-creacion-de-usuario-en-el-portal-v10-backend-1 Waiting 
 Container ec2-creacion-de-usuario-en-el-portal-v10-db-1 Healthy 
 Container ec2-creacion-de-usuario-en-el-portal-v10-backend-1 Healthy 

```
## aplicaciones (ok)
```
c664e269f8c296bbe8ce6932784ca0e29d10e3c3ae5adc883001c8c2d1fcbe 0.0s done
#26 naming to docker.io/library/ec2-creacion-de-usuario-en-el-portal-v10-panel:latest done
#26 unpacking to docker.io/library/ec2-creacion-de-usuario-en-el-portal-v10-panel:latest 0.0s done
#26 DONE 0.2s

#27 [portal] resolving provenance for metadata file
#27 DONE 0.0s

#28 [panel] resolving provenance for metadata file
#28 DONE 0.0s
 Image ec2-creacion-de-usuario-en-el-portal-v10-panel Building 
 Image ec2-creacion-de-usuario-en-el-portal-v10-portal Building 
 Image ec2-creacion-de-usuario-en-el-portal-v10-portal Built 
 Image ec2-creacion-de-usuario-en-el-portal-v10-panel Built 
 Container ec2-creacion-de-usuario-en-el-portal-v10-portal-1 Creating 
 Container ec2-creacion-de-usuario-en-el-portal-v10-panel-1 Creating 
 Container ec2-creacion-de-usuario-en-el-portal-v10-panel-1 Created 
 Container ec2-creacion-de-usuario-en-el-portal-v10-portal-1 Created 
 Container ec2-creacion-de-usuario-en-el-portal-v10-portal-1 Starting 
 Container ec2-creacion-de-usuario-en-el-portal-v10-panel-1 Starting 
 Container ec2-creacion-de-usuario-en-el-portal-v10-portal-1 Started 
 Container ec2-creacion-de-usuario-en-el-portal-v10-panel-1 Started 
 Container ec2-creacion-de-usuario-en-el-portal-v10-portal-1 Waiting 
 Container ec2-creacion-de-usuario-en-el-portal-v10-panel-1 Waiting 
 Container ec2-creacion-de-usuario-en-el-portal-v10-portal-1 Healthy 
 Container ec2-creacion-de-usuario-en-el-portal-v10-panel-1 Healthy 

```
## balanceador (ok)
```
-creacion-de-usuario-en-el-portal-v10-edge-1 Creating 
 Container ec2-creacion-de-usuario-en-el-portal-v10-edge-1 Created 
 Container ec2-creacion-de-usuario-en-el-portal-v10-db-1 Waiting 
 Container ec2-creacion-de-usuario-en-el-portal-v10-db-1 Healthy 
 Container ec2-creacion-de-usuario-en-el-portal-v10-portal-1 Waiting 
 Container ec2-creacion-de-usuario-en-el-portal-v10-panel-1 Waiting 
 Container ec2-creacion-de-usuario-en-el-portal-v10-backend-1 Waiting 
 Container ec2-creacion-de-usuario-en-el-portal-v10-portal-1 Healthy 
 Container ec2-creacion-de-usuario-en-el-portal-v10-backend-1 Healthy 
 Container ec2-creacion-de-usuario-en-el-portal-v10-panel-1 Healthy 
 Container ec2-creacion-de-usuario-en-el-portal-v10-edge-1 Starting 
 Container ec2-creacion-de-usuario-en-el-portal-v10-edge-1 Started 
 Container ec2-creacion-de-usuario-en-el-portal-v10-edge-1 Waiting 
 Container ec2-creacion-de-usuario-en-el-portal-v10-db-1 Waiting 
 Container ec2-creacion-de-usuario-en-el-portal-v10-backend-1 Waiting 
 Container ec2-creacion-de-usuario-en-el-portal-v10-portal-1 Waiting 
 Container ec2-creacion-de-usuario-en-el-portal-v10-panel-1 Waiting 
 Container ec2-creacion-de-usuario-en-el-portal-v10-backend-1 Healthy 
 Container ec2-creacion-de-usuario-en-el-portal-v10-db-1 Healthy 
 Container ec2-creacion-de-usuario-en-el-portal-v10-panel-1 Healthy 
 Container ec2-creacion-de-usuario-en-el-portal-v10-portal-1 Healthy 
 Container ec2-creacion-de-usuario-en-el-portal-v10-edge-1 Healthy 

```
## verificacion_http (ok)
```
http://127.0.0.1:8100/api/health → 200
http://127.0.0.1:8100/ → 200
http://127.0.0.1:8103/ → 200
```
## pruebas (ok)
```
.......                                                                  [100%]
=============================== warnings summary ===============================
../usr/local/lib/python3.12/site-packages/fastapi/testclient.py:1
  /usr/local/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
7 passed, 1 warning in 0.60s

```