# Instancia local de despliegue (simula una instancia EC2)

Este equipo funciona como una instancia EC2 de pruebas. Cada producto construido por la fase 5 se
despliega aquí como una **instancia independiente**, con sus componentes en orden, igual que lo haría
en AWS.

## Equivalencias

| En AWS | En este equipo |
|---|---|
| Instancia EC2 | Carpeta `instancias/<producto>-vN/` con su propio Docker Compose |
| Subred privada | Red interna de Docker: solo el balanceador publica puertos |
| Base de datos (RDS) | Contenedor `db` con volumen persistente |
| Servicio de backend | Contenedor `backend` (solo accesible desde la red interna) |
| Aplicaciones | Contenedores `portal` (empleado) y `panel` (aprobadores), en su propio puerto |
| Balanceador (ALB) | Contenedor `edge` (nginx): enruta `/api` al backend y el resto a cada aplicación |
| Secrets Manager | Archivo `.env` de la instancia, fuera del código |

## Orden de arranque

1. Preparar la instancia (red, secretos, configuración).
2. Base de datos, con su verificación de salud.
3. Backend, que solo arranca cuando la base de datos responde.
4. Aplicaciones (portal y, si existe, panel).
5. Balanceador, que solo arranca cuando el backend y las aplicaciones están listos.
6. Verificación HTTP de cada aplicación y de `/api/health`.
7. Pruebas del backend dentro de la instancia.

## Uso

Desde Trama: **Flujo de desarrollo › 6. Construcción › Instancia local › Desplegar en instancia local**.

Puertos: el portal del empleado se publica en `127.0.0.1:8100` y el panel en `127.0.0.1:8101`
(se asignan libres automáticamente si están ocupados). El token administrativo de cada instancia está en
su `.env` (variable `ADMIN_API_TOKEN`). No lo compartas ni lo subas a un repositorio.

Para detener una instancia: pestaña **Instancia local › Detener**, o dentro de su carpeta:

```bash
docker compose -p ec2-<producto>-vN -f compose.yaml down
```
