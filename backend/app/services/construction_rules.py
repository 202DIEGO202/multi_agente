"""Validación determinista del producto: reglas que no necesitan modelo.

Cada hallazgo indica el agente responsable, de modo que la corrección sea dirigida. Las reglas
cubren los fallos típicos de la generación automática: contratos entre capas, separación entre
la aplicación del empleado y el panel administrativo, cobertura de pantallas y de criterios.
"""

import ast
import asyncio
import json
import posixpath
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

from app.config import ROOT
from app.services.roles import (  # noqa: F401  (reexportados)
    PRIVILEGED,
    is_privileged,
    norm,
    subject_is_privileged,
)

OWNER_PATHS = [
    ("db/", "desarrollador_datos"),
    ("backend/app/", "desarrollador_backend"),
    ("backend/tests/", "agente_pruebas"),
    ("portal/src/app/", "desarrollador_portal"),
    ("panel/src/app/", "desarrollador_panel"),
    ("infra/terraform/", "agente_iac"),
]
OWNER_BY_APP = {"portal": "desarrollador_portal", "panel": "desarrollador_panel"}
ADMIN = "/api/admin"
METHODS = {"get", "post", "put", "patch", "delete"}
ALLOWED_PY = {
    "fastapi",
    "pydantic",
    "email_validator",
    "psycopg",
    "starlette",
    "uvicorn",
    "httpx",
    "pytest",
    "app",
}
FRONT_IMPORTS = ("@angular/", "rxjs", "tslib", ".")
SECRET = re.compile(
    r"(?i)(password|passwd|secret|api[_-]?key|token)\s*[:=]\s*[\"'](?!\$\{)[^\"'\s]{6,}[\"']"
)
SCREEN_MIN = 0.6
LEAK_MIN = 0.75


def owner_of(path):
    return next(
        (agent for prefix, agent in OWNER_PATHS if path.startswith(prefix)), "validador_artefactos"
    )


def side_of_story(story, actors):
    """Panel si el actor es privilegiado o si el título describe una acción de aprobador o administrador.
    El actor del backlog a veces es incorrecto; el título es la otra señal confiable."""
    actor_id = (story.get("actor") or {}).get("id")
    actor = next((a for a in actors if a["id"] == actor_id), {})
    privileged_actor = is_privileged(f"{actor.get('nombre', '')} {actor.get('descripcion', '')}")
    return (
        "panel" if privileged_actor or subject_is_privileged(story.get("titulo", "")) else "portal"
    )


def aplicaciones(screens, stories, actors):
    """Decide qué aplicación presenta cada pantalla y cada historia, y si hace falta panel."""
    by_id = {h["id"]: h for h in stories}
    story_sides = {h["id"]: side_of_story(h, actors) for h in stories}
    screen_apps = {}
    for screen in screens:
        linked = [by_id[h] for h in screen.get("ids_historias", []) if h in by_id]
        panel = is_privileged(screen.get("titulo", "")) or any(
            side_of_story(h, actors) == "panel" for h in linked
        )
        screen_apps[screen["id"]] = "panel" if panel else "portal"
    has_panel = "panel" in set(screen_apps.values()) | set(story_sides.values())
    return screen_apps, story_sides, has_panel


def screen_labels(screen):
    return [
        c["etiqueta"]
        for c in screen.get("controles", [])
        if c.get("tipo") != "aviso" and c.get("etiqueta")
    ]


def coverage(labels, text):
    """Proporción de etiquetas del mockup que aparecen en el código (tolerante a tildes y mayúsculas)."""
    tokens = set(norm(text).split())
    counted = covered = 0
    for label in labels:
        words = [w for w in norm(label).split() if len(w) > 2]
        if not words:
            continue
        counted += 1
        if sum(w in tokens for w in words) / len(words) >= 0.6:
            covered += 1
    return covered / counted if counted else 1.0


def norm_path(path):
    return re.sub(r"\$\{[^}]*\}|\{[^}]*\}", "{}", path).split("?")[0].rstrip("/") or "/"


def _call_name(call):
    func = call.func
    return (
        func.id
        if isinstance(func, ast.Name)
        else func.attr
        if isinstance(func, ast.Attribute)
        else ""
    )


def _admin_dependency(node):
    """True si alguna dependencia Depends(...) del nodo tiene un nombre que indique administración."""
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call) and _call_name(sub) == "Depends":
            for name in ast.walk(sub):
                if isinstance(name, ast.Name) and "admin" in name.id.lower():
                    return True
    return False


def backend_routes(files):
    """Rutas FastAPI reales (método, ruta completa, si exige administrador) leídas con ast."""
    routes = []
    for path, content in files.items():
        if not (path.startswith("backend/app/") and path.endswith(".py")):
            continue
        try:
            tree = ast.parse(content)
        except SyntaxError:
            continue
        routers = {}
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Assign)
                and isinstance(node.value, ast.Call)
                and _call_name(node.value) == "APIRouter"
            ):
                prefix, protected = "", False
                for kw in node.value.keywords:
                    if (
                        kw.arg == "prefix"
                        and isinstance(kw.value, ast.Constant)
                        and isinstance(kw.value.value, str)
                    ):
                        prefix = kw.value.value
                    if kw.arg == "dependencies" and _admin_dependency(kw.value):
                        protected = True
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        routers[target.id] = (prefix, protected)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            defaults = [d for d in node.args.defaults + node.args.kw_defaults if d is not None]
            arg_protected = any(_admin_dependency(d) for d in defaults)
            for dec in node.decorator_list:
                if not (
                    isinstance(dec, ast.Call)
                    and isinstance(dec.func, ast.Attribute)
                    and dec.func.attr in METHODS
                    and dec.args
                    and isinstance(dec.args[0], ast.Constant)
                    and isinstance(dec.args[0].value, str)
                ):
                    continue
                owner = dec.func.value.id if isinstance(dec.func.value, ast.Name) else ""
                prefix, router_protected = routers.get(owner, ("", False))
                local = any(
                    kw.arg == "dependencies" and _admin_dependency(kw.value) for kw in dec.keywords
                )
                routes.append(
                    {
                        "metodo": dec.func.attr.upper(),
                        "ruta": prefix + dec.args[0].value,
                        "protegida": router_protected or local or arg_protected,
                        "archivo": path,
                    }
                )
    return routes


def _text(files, prefix):
    return "\n".join(content for path, content in files.items() if path.startswith(prefix))


def assess(files, ctx):
    """Reglas sin modelo. ctx: has_panel, criteria (IDs), screens (id, titulo, app, labels)."""
    findings = []
    has_panel = ctx["has_panel"]

    def add(agente, codigo, descripcion, archivo="", severidad="error"):
        findings.append(
            {
                "severidad": severidad,
                "codigo": codigo,
                "agente": agente,
                "descripcion": descripcion[:1500],
                "archivo": archivo,
            }
        )

    for path, content in files.items():
        if not path.endswith(".ts"):
            continue
        for imported in re.findall(r"(?:from\s*|import\s*\()\s*['\"](\.[^'\"]+)['\"]", content):
            destination = posixpath.normpath(posixpath.join(posixpath.dirname(path), imported))
            if not any(candidate in files for candidate in (destination, destination + ".ts", destination + "/index.ts")):
                add(owner_of(path), "IMPORT_LOCAL_AUSENTE", f"{path} importa {imported}, pero el componente no fue entregado. Devuelva todos los archivos de la aplicación, incluidas sus rutas.", path)

    required = [
        "db/init.sql",
        "backend/app/main.py",
        "portal/src/app/app.ts",
        "infra/terraform/main.tf",
    ]
    if has_panel:
        required.append("panel/src/app/app.ts")
    for path in required:
        if path not in files:
            add(owner_of(path), "ARCHIVO_FALTANTE", f"Falta {path}", path)

    tests = {p: c for p, c in files.items() if p.startswith("backend/tests/") and p.endswith(".py")}
    if not any(p.rsplit("/", 1)[-1].startswith("test_") for p in tests):
        add("agente_pruebas", "SIN_PRUEBAS", "No hay pruebas backend/tests/test_*.py")

    for path, content in files.items():
        if path.endswith(".env.example"):
            continue
        if "\x00" in content:
            add(
                owner_of(path),
                "CARACTER_NULO",
                "El archivo contiene caracteres nulos; no es código válido",
                path,
            )
        if SECRET.search(content):
            add(
                owner_of(path),
                "SECRETO_EN_CODIGO",
                "Credencial escrita en el código; use variables de entorno",
                path,
            )
        if path.endswith(".py") and path.startswith(("backend/app/", "backend/tests/")):
            agent = owner_of(path)
            try:
                tree = ast.parse(content)
            except SyntaxError as exc:
                add(agent, "SINTAXIS_PYTHON", f"Línea {exc.lineno}: {exc.msg}", path)
                continue
            for node in ast.walk(tree):
                modules = []
                if isinstance(node, ast.Import):
                    modules = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                    modules = [node.module]
                for module in modules:
                    top = module.split(".")[0]
                    if top not in ALLOWED_PY and top not in sys.stdlib_module_names:
                        add(
                            agent,
                            "DEPENDENCIA_NO_PERMITIDA",
                            f"Módulo fuera de requirements.txt: {top}",
                            path,
                        )
        if path.endswith((".ts",)) and path.startswith(("portal/", "panel/")):
            for spec in re.findall(r"from\s+['\"]([^'\"]+)['\"]", content):
                if not spec.startswith(FRONT_IMPORTS):
                    add(
                        owner_of(path),
                        "DEPENDENCIA_NO_PERMITIDA",
                        f"Importación fuera de Angular/rxjs: {spec}",
                        path,
                    )
        if path.endswith(".sql") and re.search(r"(?i)drop\s+database", content):
            add(
                "desarrollador_datos",
                "SQL_PELIGROSO",
                "El script no puede borrar bases de datos",
                path,
            )
        if path.endswith(".tf") and content.count("{") != content.count("}"):
            add("agente_iac", "TERRAFORM_INVALIDO", "Llaves desbalanceadas en Terraform", path)

    sql = files.get("db/init.sql", "")
    # A declared enum value must fit its own column; PostgreSQL accepts the DDL but rejects inserts.
    for match in re.finditer(r"\b(\w+)\s+(?:varchar|character\s+varying)\s*\(\s*(\d+)\s*\)[^,;]*?CHECK\s*\(\s*\1\s+IN\s*\(([^)]*)\)", sql, re.I):
        column, length, options = match.groups()
        values = [value.replace("''", "'") for value in re.findall(r"'((?:[^']|'')*)'", options)]
        if any(len(value) > int(length) for value in values):
            add("desarrollador_datos", "SQL_ENUM_TRUNCADO", f"La columna {column} limita a {length} caracteres pero sus valores CHECK exceden esa longitud. Amplíe el tipo sin alterar los estados del negocio.", "db/init.sql")
    if sql and not re.search(r"(?i)create\s+table", sql):
        add("desarrollador_datos", "SQL_SIN_TABLAS", "init.sql no crea tablas", "db/init.sql")

    backend_code = _text(files, "backend/app/")
    main = files.get("backend/app/main.py", "")
    if main and "FastAPI(" not in main:
        add(
            "desarrollador_backend",
            "MAIN_INCOMPLETO",
            "main.py debe crear app = FastAPI()",
            "backend/app/main.py",
        )
    if backend_code and "DATABASE_URL" not in backend_code:
        add(
            "desarrollador_backend",
            "SIN_DATABASE_URL",
            "La conexión debe leer la variable DATABASE_URL",
        )
    if re.search(r"\bField\([^)]*\bregex\s*=", backend_code):
        add(
            "desarrollador_backend",
            "PYDANTIC_V1",
            "Field(regex=...) es sintaxis de Pydantic v1; en Pydantic v2 use pattern=...",
            "backend/app",
        )
    if has_panel and backend_code and "ADMIN_API_TOKEN" not in backend_code:
        add(
            "desarrollador_backend",
            "SIN_TOKEN_ADMIN",
            "La API administrativa debe validar ADMIN_API_TOKEN",
        )

    routes = backend_routes(files)
    if not any(r["ruta"] == "/api/health" and r["metodo"] == "GET" for r in routes):
        add("desarrollador_backend", "SIN_HEALTH", "Falta GET /api/health")
    for r in routes:
        if r["ruta"].startswith(ADMIN) and not r["protegida"]:
            add(
                "desarrollador_backend",
                "ADMIN_SIN_PROTECCION",
                f"{r['metodo']} {r['ruta']} es administrativo y no exige autenticación (Depends(require_admin))",
                r["archivo"],
            )
    public_reads = {
        norm_path(r["ruta"])
        for r in routes
        if r["metodo"] == "GET" and not r["ruta"].startswith(ADMIN) and not r["protegida"]
    }
    for r in routes:
        if r["metodo"] == "GET" and r["ruta"].startswith(ADMIN):
            public = norm_path("/api" + r["ruta"][len(ADMIN) :])
            if public in public_reads:
                add(
                    "desarrollador_backend",
                    "LISTADO_PUBLICO_DUPLICADO",
                    f"{public} es público y expone los mismos datos que el administrativo {r['ruta']}",
                    r["archivo"],
                )

    portal_text = _text(files, "portal/src/app/")
    panel_text = _text(files, "panel/src/app/")
    if re.search(r"/api/admin|ADMIN|Bearer|Authorization", portal_text):
        add(
            OWNER_BY_APP["portal"],
            "ADMIN_EN_EMPLEADO",
            "La aplicación del empleado no debe llamar a la API administrativa ni manejar su token",
        )
    if has_panel:
        if "/api/admin" not in panel_text:
            add(
                OWNER_BY_APP["panel"],
                "PANEL_SIN_API_ADMIN",
                "El panel no consume /api/admin",
                "panel/src/app/app.ts",
            )
        if "Authorization" not in panel_text:
            add(
                OWNER_BY_APP["panel"],
                "PANEL_SIN_TOKEN",
                "El panel debe enviar Authorization: Bearer en sus llamadas",
                "panel/src/app/app.ts",
            )

    known = {norm_path(r["ruta"]) for r in routes}
    for app, text in (("portal", portal_text), ("panel", panel_text)):
        if app == "panel" and not has_panel:
            continue
        for raw in sorted(set(re.findall(r"/api/[^\s'\"`?#]*", text))):
            if norm_path(raw) not in known:
                add(
                    OWNER_BY_APP[app],
                    "ENDPOINT_INEXISTENTE",
                    f"La interfaz llama a {raw}, que no existe en el backend",
                )

    for app in ("portal", "panel"):
        if app == "panel" and not has_panel:
            continue
        shell = files.get(f"{app}/src/app/app.ts", "")
        if shell and not re.search(r"export\s+class\s+App\b", shell):
            add(
                OWNER_BY_APP[app],
                "APP_INCOMPLETA",
                "app.ts debe exportar la clase App",
                f"{app}/src/app/app.ts",
            )
        if not re.search(
            r"export\s+(const\s+routes|\{\s*routes)",
            files.get(f"{app}/src/app/routes.ts", "") + shell,
        ):
            add(
                OWNER_BY_APP[app],
                "RUTAS_INCOMPLETAS",
                "routes.ts debe exportar la constante routes",
                f"{app}/src/app/routes.ts",
            )

    for screen in ctx["screens"]:
        target = portal_text if screen["app"] == "portal" else panel_text
        cov = coverage(screen["labels"], target)
        if cov < SCREEN_MIN:
            add(
                OWNER_BY_APP[screen["app"]],
                "PANTALLA_INCOMPLETA",
                f"{screen['id']} · {screen['titulo']}: faltan campos o textos del mockup (cobertura {cov:.0%})",
            )
        if screen["app"] == "panel" and coverage(screen["labels"], portal_text) >= LEAK_MIN:
            add(
                OWNER_BY_APP["portal"],
                "PANTALLA_ADMIN_EN_EMPLEADO",
                f"{screen['id']} · {screen['titulo']} es una pantalla de aprobadores y aparece en la aplicación del empleado",
            )

    tests_text = norm(" ".join(tests.values()))
    untested = [c for c in ctx["criteria"] if norm(c) not in tests_text]
    if ctx["criteria"] and len(untested) == len(ctx["criteria"]):
        add(
            "agente_pruebas",
            "SIN_TRAZABILIDAD",
            "Ningún caso de prueba referencia un criterio de aceptación",
        )
    elif untested:
        add(
            "agente_pruebas",
            "CRITERIOS_SIN_PRUEBA",
            "Criterios sin caso de prueba: " + ", ".join(untested[:15]),
            severidad="advertencia",
        )
    if has_panel and not re.search(r"401|403", " ".join(tests.values())):
        add(
            "agente_pruebas",
            "SIN_PRUEBA_ACCESO_DENEGADO",
            "Falta una prueba que compruebe que la API administrativa rechaza las llamadas sin token",
        )

    compose_text = files.get("docker-compose.yml")
    if compose_text is None:
        add(
            "validador_artefactos",
            "ARCHIVO_FALTANTE",
            "Falta docker-compose.yml",
            "docker-compose.yml",
        )
    else:
        try:
            services = set(((yaml.safe_load(compose_text) or {}).get("services")) or {})
        except yaml.YAMLError as exc:
            add("validador_artefactos", "YAML_INVALIDO", str(exc)[:300], "docker-compose.yml")
            services = set()
        required_services = {"db", "backend", "portal", "edge"} | (
            {"panel"} if has_panel else set()
        )
        if services and required_services - services:
            add(
                "validador_artefactos",
                "COMPOSE_INCOMPLETO",
                "docker-compose.yml no define: " + ", ".join(sorted(required_services - services)),
                "docker-compose.yml",
            )

    tf = _text(files, "infra/terraform/")
    if tf and 'provider "aws"' not in tf:
        add(
            "agente_iac",
            "TERRAFORM_SIN_AWS",
            "Terraform debe declarar el proveedor aws",
            "infra/terraform/main.tf",
        )
    if tf and not re.search(r"(?i)\beks\b", tf):
        add(
            "agente_iac",
            "TERRAFORM_SIN_EKS",
            "Terraform debe crear el clúster EKS",
            "infra/terraform/main.tf",
        )
    return findings


async def typescript_findings(files):
    """Errores de sintaxis TypeScript con el compilador que ya usa Trama (sin instalar nada nuevo)."""
    compiler = ROOT / "frontend" / "node_modules" / "typescript" / "lib" / "typescript.js"
    sources = {
        p: c for p, c in files.items() if p.endswith(".ts") and p.startswith(("portal/", "panel/"))
    }
    if not sources or not compiler.exists():
        return []
    script = (
        "const ts=require(process.argv[1]);const files=JSON.parse(require('fs').readFileSync(0,'utf8'));"
        "const out={};for(const [name,text] of Object.entries(files)){"
        "const r=ts.transpileModule(text,{fileName:name,reportDiagnostics:true,compilerOptions:{experimentalDecorators:true,target:ts.ScriptTarget.ES2022}});"
        "const d=(r.diagnostics||[]).map(x=>{const p=x.file&&x.start!=null?x.file.getLineAndCharacterOfPosition(x.start).line+1:0;return 'línea '+p+': '+ts.flattenDiagnosticMessageText(x.messageText,' ')});"
        "if(d.length)out[name]=d.slice(0,3);}process.stdout.write(JSON.stringify(out));"
    )
    try:
        result = await asyncio.to_thread(
            subprocess.run,
            ["node", "-e", script, str(compiler)],
            input=json.dumps(sources).encode(),
            capture_output=True,
            timeout=60,
        )
        errors = json.loads(result.stdout or b"{}")
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return []
    return [
        {
            "severidad": "error",
            "codigo": "SINTAXIS_TYPESCRIPT",
            "agente": owner_of(path),
            "descripcion": "; ".join(messages),
            "archivo": path,
        }
        for path, messages in errors.items()
    ]


# Análisis estático del backend generado con ruff (ya presente en el entorno de Trama):
# errores que rompen en ejecución y reglas de seguridad tipo Bandit.
STATIC_RULES = {
    "E9": "Error de sintaxis o de compilación",
    "F63": "Comparación inválida",
    "F7": "Sentencia fuera de contexto",
    "F82": "Nombre no definido",
    "S102": "Uso de exec",
    "S105": "Contraseña escrita en el código",
    "S106": "Contraseña escrita en el código",
    "S307": "Uso de eval",
    "S608": "SQL construido con texto (riesgo de inyección); use parámetros",
}
TEST_ALLOWED = {"S105", "S106"}  # Las pruebas usan credenciales ficticias por diseño.


async def static_findings(files):
    sources = {p: c for p, c in files.items() if p.endswith(".py") and p.startswith("backend/")}
    if not sources:
        return []
    with tempfile.TemporaryDirectory() as tmp:
        for path, content in sources.items():
            target = Path(tmp, path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content.replace("\x00", ""), encoding="utf-8")
        command = [
            sys.executable,
            "-m",
            "ruff",
            "check",
            "--isolated",
            "--no-cache",
            "--output-format",
            "json",
            "--select",
            ",".join(STATIC_RULES),
            tmp,
        ]
        try:
            result = await asyncio.to_thread(
                subprocess.run, command, capture_output=True, timeout=120
            )
            issues = json.loads(result.stdout or b"[]")
        except (OSError, ValueError, subprocess.TimeoutExpired):
            return [
                {
                    "severidad": "advertencia",
                    "codigo": "ANALISIS_ESTATICO_NO_DISPONIBLE",
                    "agente": "validador_artefactos",
                    "descripcion": "No se pudo ejecutar el análisis estático (ruff)",
                    "archivo": "",
                }
            ]
    findings = []
    for issue in issues:
        path = Path(issue["filename"]).resolve().as_posix()
        relative = next((p for p in sources if path.endswith("/" + p)), "")
        code = issue.get("code") or "E9"
        if relative.startswith("backend/tests/") and code in TEST_ALLOWED:
            continue
        label = next(
            (text for prefix, text in STATIC_RULES.items() if code.startswith(prefix)),
            "Análisis estático",
        )
        line = (issue.get("location") or {}).get("row", 0)
        findings.append(
            {
                "severidad": "error",
                "codigo": f"ESTATICO_{code}",
                "agente": owner_of(relative) if relative else "desarrollador_backend",
                "descripcion": f"{label} (línea {line}): {issue.get('message', '')}"[:600],
                "archivo": relative,
            }
        )
    return findings


async def validate(files, ctx):
    return assess(files, ctx) + await typescript_findings(files) + await static_findings(files)


def errors_of(findings):
    return [f for f in findings if f.get("severidad") == "error"]
