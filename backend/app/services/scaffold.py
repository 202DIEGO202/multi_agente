"""Plantillas fijas del producto: builds, contenedores, balanceador y configuración base.

La infraestructura de la aplicación no la escribe un modelo: así cada producto arranca igual en
local y en la instancia. Los agentes solo escriben la lógica dentro de sus carpetas (ver
OWNER_PATHS en construction_rules).
"""

import hashlib
import html
import json
import re
import unicodedata

BASE_CSS = """*{box-sizing:border-box}
body{margin:0;font-family:system-ui,"Segoe UI",Arial,sans-serif;background:#f4f6f8;color:#1f2933;line-height:1.5}
nav,header.app-bar{display:flex;flex-wrap:wrap;gap:6px;align-items:center;padding:12px 24px;background:#0f4c5c;color:#fff}
nav a,header.app-bar a{color:#fff;text-decoration:none;padding:8px 12px;border-radius:8px}
nav a:hover,nav a.active,header.app-bar a.active{background:rgba(255,255,255,.16)}
main,.page{max-width:960px;margin:28px auto;padding:0 20px}
h1,h2{color:#0f4c5c;margin:0 0 16px}
.card,form{background:#fff;border:1px solid #dde3e8;border-radius:14px;padding:24px;box-shadow:0 6px 20px rgba(15,76,92,.06);margin-bottom:20px}
form{display:grid;gap:16px;max-width:620px}
.field,form label{display:grid;gap:6px;font-weight:600;font-size:14px}
input,select,textarea{width:100%;padding:10px 12px;border:1px solid #c5cfd6;border-radius:8px;font:inherit;background:#fff}
input:focus,select:focus,textarea:focus{outline:2px solid #2a9d8f;border-color:#2a9d8f}
.error,.text-danger,small.error{color:#b42318;font-size:13px;font-weight:500}
.success{background:#e7f6ee;color:#13653f;border:1px solid #b7e3c9;border-radius:8px;padding:10px 14px}
.alert{background:#fdecea;color:#8f1d14;border:1px solid #f5c2bd;border-radius:8px;padding:10px 14px}
button,.btn{display:inline-flex;align-items:center;justify-content:center;gap:6px;padding:10px 18px;border:0;border-radius:8px;background:#0f4c5c;color:#fff;font:inherit;font-weight:600;cursor:pointer}
button:hover,.btn:hover{background:#0b3a46}
button:disabled{background:#9fb3bb;cursor:not-allowed}
button.secondary{background:#fff;color:#0f4c5c;border:1px solid #0f4c5c}
button.danger{background:#b42318}
.actions{display:flex;gap:10px;flex-wrap:wrap}
table{width:100%;border-collapse:collapse;background:#fff;border-radius:12px;overflow:hidden}
th,td{text-align:left;padding:10px 12px;border-bottom:1px solid #e6ebef}
th{background:#eef3f5;font-size:13px;text-transform:uppercase;letter-spacing:.03em;color:#486170}
dl{display:grid;grid-template-columns:minmax(140px,30%) 1fr;gap:8px 16px}dt{font-weight:600;color:#486170}dd{margin:0}
.badge{display:inline-block;padding:2px 10px;border-radius:999px;background:#eef3f5;font-size:12px;font-weight:600}
"""

PORTAL, PANEL = "portal", "panel"
STACK = [
    "Python 3.12 + FastAPI (API en backend/app)",
    "PostgreSQL 16 con psycopg 3 (esquema en db/init.sql)",
    "Angular 21 standalone (portal del empleado y panel administrativo)",
    "Nginx como servidor estático y balanceador",
    "Docker Compose en local; AWS EKS en la nube",
]


def slug(text):
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", plain.lower()).strip("-")[:40] or "proyecto"


def project_key(name):
    """Nombre corto de proyecto Docker sin palabras del dominio (evita falsos positivos al leer logs)."""
    return "chk-" + hashlib.sha1(slug(name).encode()).hexdigest()[:10]


def frontend_app(key, title):
    """Aplicación Angular servida por Nginx. key = portal | panel."""
    deps = {
        f"@angular/{part}": "21.2.25"
        for part in ("common", "compiler", "core", "forms", "platform-browser", "router")
    }
    deps.update({"rxjs": "7.8.2", "tslib": "2.8.1", "zone.js": "0.15.1"})
    package = {
        "name": f"{key}-app",
        "private": True,
        "scripts": {"build": "ng build"},
        "dependencies": deps,
        "devDependencies": {
            "@angular/build": "21.2.28",
            "@angular/cli": "21.2.28",
            "@angular/compiler-cli": "21.2.25",
            "typescript": "5.9.3",
        },
    }
    angular = {
        "$schema": "./node_modules/@angular/cli/lib/config/schema.json",
        "version": 1,
        "cli": {"analytics": False},
        "projects": {
            "app": {
                "projectType": "application",
                "root": "",
                "sourceRoot": "src",
                "architect": {
                    "build": {
                        "builder": "@angular/build:application",
                        "options": {
                            "browser": "src/main.ts",
                            "index": "src/index.html",
                            "tsConfig": "tsconfig.json",
                            "polyfills": ["zone.js"],
                            "styles": ["src/styles.css"],
                            "outputPath": "dist/app",
                        },
                        "configurations": {"production": {"outputHashing": "all"}},
                        "defaultConfiguration": "production",
                    }
                },
            }
        },
    }
    tsconfig = {
        "compilerOptions": {
            "target": "ES2022",
            "module": "ES2022",
            "moduleResolution": "bundler",
            "lib": ["ES2022", "dom"],
            "strict": False,
            "experimentalDecorators": True,
            "skipLibCheck": True,
            "useDefineForClassFields": False,
            "isolatedModules": True,
        },
        "include": ["src/**/*.ts"],
        "exclude": ["node_modules"],
    }
    index = (
        '<!doctype html>\n<html lang="es">\n<head>\n  <meta charset="utf-8">\n'
        f"  <title>{html.escape(title)}</title>\n"
        '  <meta name="viewport" content="width=device-width, initial-scale=1">\n'
        "</head>\n<body>\n  <app-root></app-root>\n</body>\n</html>\n"
    )
    main = (
        "import { provideZoneChangeDetection } from '@angular/core';\n"
        "import { bootstrapApplication } from '@angular/platform-browser';\n"
        "import { provideRouter } from '@angular/router';\n"
        "import { provideHttpClient } from '@angular/common/http';\n"
        "import { App, routes } from './app/app';\n\n"
        "bootstrapApplication(App, {\n"
        "  providers: [provideZoneChangeDetection({ eventCoalescing: true }), provideRouter(routes), provideHttpClient()],\n"
        "}).catch(console.error);\n"
    )
    nginx = "server {\n  listen 80;\n  root /usr/share/nginx/html;\n  location / {\n    try_files $uri $uri/ /index.html;\n  }\n}\n"
    dockerfile = (
        "FROM node:22-alpine AS build\n"
        "WORKDIR /app\n"
        "COPY package.json ./\n"
        "RUN npm install --no-audit --no-fund --legacy-peer-deps\n"
        "COPY . .\n"
        "RUN npx ng build\n\n"
        "FROM nginx:1.27-alpine\n"
        "COPY nginx.conf /etc/nginx/conf.d/default.conf\n"
        "COPY --from=build /app/dist/app/browser /usr/share/nginx/html\n"
    )
    shell = (
        "import { Component } from '@angular/core';\n"
        "import { RouterLink, RouterOutlet } from '@angular/router';\n"
        "import { routes } from './routes';\n\n"
        "// Shell común generado por la plantilla: navegación a partir de las rutas y el router-outlet.\n"
        "@Component({\n"
        "  selector: 'app-root',\n"
        "  standalone: true,\n"
        "  imports: [RouterOutlet, RouterLink],\n"
        "  template: `\n"
        "    <nav>\n"
        "      @for (link of links; track link.path) {\n"
        '        <a [routerLink]="link.path">{{ link.label }}</a>\n'
        "      }\n"
        "    </nav>\n"
        "    <main><router-outlet /></main>\n"
        "  `,\n"
        "})\n"
        "export class App {\n"
        "  links = routes\n"
        "    .filter((r) => !!r.path && !r.path.includes(':') && !r.path.includes('**'))\n"
        "    .map((r) => ({ path: r.path as string, label: (r.data?.['label'] as string) ?? (r.path as string) }));\n"
        "}\n\n"
        "export { routes };\n"
    )
    routes_default = (
        "import { Routes } from '@angular/router';\n\nexport const routes: Routes = [];\n"
    )
    files = {
        "package.json": json.dumps(package, indent=2) + "\n",
        "angular.json": json.dumps(angular, indent=2) + "\n",
        "tsconfig.json": json.dumps(tsconfig, indent=2) + "\n",
        "src/index.html": index,
        "src/main.ts": main,
        "src/styles.css": BASE_CSS,
        "src/app/app.ts": shell,
        "src/app/routes.ts": routes_default,
        "nginx.conf": nginx,
        "Dockerfile": dockerfile,
        ".dockerignore": "node_modules\ndist\n.angular\n",
    }
    return {f"{key}/{path}": text for path, text in files.items()}


def backend_scaffold():
    return {
        "backend/Dockerfile": (
            "FROM python:3.12-slim\n"
            "ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1\n"
            "WORKDIR /srv\n"
            "COPY requirements.txt .\n"
            "RUN pip install --no-cache-dir -r requirements.txt\n"
            "COPY . .\n"
            "EXPOSE 8000\n"
            'CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]\n'
        ),
        "backend/requirements.txt": "fastapi>=0.115,<1\npydantic[email]>=2.8,<3\nuvicorn[standard]>=0.34,<1\npsycopg[binary]>=3.2,<4\npytest>=8,<9\nhttpx>=0.28,<1\n",
        "backend/.dockerignore": "__pycache__\n.pytest_cache\n",
        "backend/pytest.ini": "[pytest]\npythonpath = .\ntestpaths = tests\n",
        "backend/app/__init__.py": "",
        "backend/tests/__init__.py": "",
    }


def edge_conf(has_panel):
    """Balanceador: cada aplicación en su puerto y /api siempre hacia el backend privado.

    Usa un resolver dinámico (resolver + proxy_pass con variable) para que nginx no se
    caiga al iniciar si un upstream todavía no es resoluble (carrera de arranque típica
    de Docker Compose: nginx normalmente resuelve una sola vez al arrancar); así reintenta
    la resolución en cada petición en vez de morir con "host not found in upstream".
    """

    def server(port, frontend_name):
        return (
            "server {\n  listen " + str(port) + ";\n"
            "  resolver 127.0.0.11 valid=10s;\n"
            "  set $backend_upstream http://backend:8000;\n"
            "  set $frontend_upstream http://" + frontend_name + ":80;\n"
            "  location /api/ {\n    proxy_pass $backend_upstream;\n"
            "    proxy_set_header Host $host;\n    proxy_set_header Authorization $http_authorization;\n  }\n"
            "  location / {\n    proxy_pass $frontend_upstream;\n    proxy_set_header Host $host;\n  }\n}\n"
        )

    conf = server(8080, "portal")
    if has_panel:
        conf += "\n" + server(8081, "panel")
    return conf


def compose_file(project, has_panel, root=".", publish=False, bind_host="127.0.0.1"):
    """Compose del producto. root = ruta a la carpeta del producto desde el archivo generado."""
    frontends = [PORTAL] + ([PANEL] if has_panel else [])
    lines = [
        f"name: {project}",
        "services:",
        "  db:",
        "    image: postgres:16",
        "    environment:",
        "      POSTGRES_DB: app",
        "      POSTGRES_USER: app",
        "      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?Defina POSTGRES_PASSWORD en .env}",
        "    volumes:",
        f"      - {root}/db:/docker-entrypoint-initdb.d:ro",
        "      - db-data:/var/lib/postgresql/data",
        "    healthcheck:",
        '      test: ["CMD-SHELL", "pg_isready -U app -d app"]',
        "      interval: 5s",
        "      timeout: 5s",
        "      retries: 20",
        "  backend:",
        f"    build: {root}/backend",
        "    environment:",
        "      DATABASE_URL: postgresql://app:${POSTGRES_PASSWORD}@db:5432/app",
        "      ADMIN_API_TOKEN: ${ADMIN_API_TOKEN:?Defina ADMIN_API_TOKEN en .env}",
        "    depends_on:",
        "      db:",
        "        condition: service_healthy",
        "    healthcheck:",
        '      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen(\'http://localhost:8000/api/health\', timeout=3)"]',
        "      interval: 5s",
        "      timeout: 5s",
        "      retries: 20",
    ]
    for name in frontends:
        lines += [
            f"  {name}:",
            f"    build: {root}/{name}",
            "    healthcheck:",
            '      test: ["CMD", "wget", "-qO-", "http://127.0.0.1/"]',
            "      interval: 5s",
            "      timeout: 5s",
            "      retries: 20",
        ]
    lines += [
        "  edge:",
        "    image: nginx:1.27-alpine",
        "    volumes:",
        f"      - {root}/edge/nginx.conf:/etc/nginx/conf.d/default.conf:ro",
        "    depends_on:",
    ]
    for name in ["backend", *frontends]:
        lines += [f"      {name}:", "        condition: service_healthy"]
    if publish:
        lines.append("    ports:")
        lines.append(f'      - "{bind_host}:${{PORTAL_PORT:-8100}}:8080"')
        if has_panel:
            lines.append(f'      - "{bind_host}:${{PANEL_PORT:-8101}}:8081"')
    lines += [
        "    healthcheck:",
        '      test: ["CMD", "wget", "-qO-", "http://127.0.0.1:8080/api/health"]',
        "      interval: 5s",
        "      timeout: 5s",
        "      retries: 20",
        "volumes:",
        "  db-data:",
    ]
    return "\n".join(lines) + "\n"


def env_example(has_panel):
    lines = [
        "POSTGRES_PASSWORD=cambie-esto",
        "ADMIN_API_TOKEN=cambie-esto-tambien",
        "PORTAL_PORT=8100",
    ]
    if has_panel:
        lines.append("PANEL_PORT=8101")
    return "# Copie este archivo a .env y cambie los valores.\n" + "\n".join(lines) + "\n"


def scaffold_files(name, has_panel):
    """Todos los archivos que no escriben los agentes."""
    files = {}
    files.update(frontend_app(PORTAL, name))
    if has_panel:
        files.update(frontend_app(PANEL, f"{name} · panel administrativo"))
    files.update(backend_scaffold())
    files["edge/nginx.conf"] = edge_conf(has_panel)
    files["docker-compose.yml"] = compose_file(project_key(name), has_panel, ".", publish=True)
    files[".env.example"] = env_example(has_panel)
    return files


def readme_app(summary, version):
    lines = [
        f"# {summary['proyecto']} · aplicación v{version}",
        "",
        "Generada por Trama a partir de la arquitectura aprobada, las historias y los mockups.",
        "",
        "## Aplicaciones",
        "- `portal/`: aplicación del empleado. No tiene acceso a funciones administrativas.",
    ]
    if summary.get("tiene_panel"):
        lines.append(
            "- `panel/`: panel para aprobadores y administración. Requiere `ADMIN_API_TOKEN`."
        )
    lines += [
        "- `backend/`: API FastAPI. `db/`: esquema PostgreSQL. `infra/terraform/`: infraestructura AWS.",
        "",
        "## Ejecutar en local",
        "1. Copie `.env.example` a `.env` y defina `POSTGRES_PASSWORD` y `ADMIN_API_TOKEN`.",
        "2. `docker compose up -d --build`",
        "3. Portal: http://localhost:8100"
        + (" · Panel: http://localhost:8101" if summary.get("tiene_panel") else ""),
        "4. Pruebas: `docker compose exec backend pytest -q`",
        "",
        "## Endpoints",
        "| Método | Ruta | Acceso |",
        "|---|---|---|",
    ]
    lines += [
        f"| {e['metodo']} | `{e['ruta']}` | {e.get('acceso', 'publico')} |"
        for e in summary.get("endpoints", [])
    ]
    return "\n".join(lines) + "\n"
