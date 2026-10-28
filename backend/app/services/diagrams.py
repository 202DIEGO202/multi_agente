"""Vistas y archivos derivados del modelo canónico de arquitectura.

Todo se calcula con código a partir del JSON aprobado: el diagrama nunca contradice el
modelo, no se gastan tokens y no se ejecuta contenido producido por IA.
"""

import json
import re
import unicodedata
from xml.sax.saxutils import escape

NODE_W, NODE_H, GAP_X, GAP_Y, MARGIN = 220, 88, 56, 110, 36

# Capa vertical de cada tipo: personas arriba, datos y sistemas externos abajo.
CONTAINER_LAYER = {
    "persona": 0,
    "aplicacion_web": 1,
    "api": 2,
    "base_datos": 3,
    "servicio_externo": 3,
}
COMPONENT_LAYER = {
    "modulo_ui": 0,
    "controlador": 1,
    "servicio": 2,
    "integracion": 3,
    "repositorio": 3,
    "esquema_datos": 4,
}
INFRA_LAYER = {
    "balanceador": 0,
    "contenedor": 1,
    "base_datos": 2,
    "secreto": 2,
    "registro_imagenes": 2,
    "monitoreo": 2,
    "servicio_externo": 2,
}


def slug(text):
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", plain.lower()).strip("-")[:40] or "servicio"


def layout(nodes):
    """Distribuye nodos por capas; devuelve ancho y alto del lienzo."""
    layers = {}
    for node in nodes:
        layers.setdefault(node["capa"], []).append(node)
    width = max((len(row) for row in layers.values()), default=1)
    canvas_w = MARGIN * 2 + width * NODE_W + (width - 1) * GAP_X
    for row_index, key in enumerate(sorted(layers)):
        row = layers[key]
        row_w = len(row) * NODE_W + (len(row) - 1) * GAP_X
        start = (canvas_w - row_w) / 2
        for i, node in enumerate(row):
            node.update(
                x=round(start + i * (NODE_W + GAP_X)),
                y=MARGIN + row_index * (NODE_H + GAP_Y),
                w=NODE_W,
                h=NODE_H,
            )
    rows = len(layers) or 1
    return canvas_w, MARGIN * 2 + rows * NODE_H + (rows - 1) * GAP_Y


def graph_view(view_id, title, explanation, nodes, edges):
    known = {n["id"] for n in nodes}
    edges = [e for e in edges if e["origen"] in known and e["destino"] in known]
    # Una sola flecha por par de nodos: varias etiquetas superpuestas no se pueden leer.
    merged = {}
    for e in edges:
        key = (e["origen"], e["destino"])
        if key in merged:
            merged[key]["extra"] += 1
        else:
            merged[key] = {**e, "extra": 0}
    unique = [
        {
            "origen": e["origen"],
            "destino": e["destino"],
            "etiqueta": e["etiqueta"] + (f" (+{e['extra']})" if e["extra"] else ""),
        }
        for e in merged.values()
    ]
    width, height = layout(nodes)
    return {
        "id": view_id,
        "tipo": "grafo",
        "titulo": title,
        "explicacion": explanation,
        "ancho": width,
        "alto": height,
        "nodos": nodes,
        "aristas": unique,
        "mermaid": mermaid_graph(nodes, unique),
    }


def mermaid_text(value):
    return value.replace('"', "'").replace("\n", " ")


def mermaid_id(value):
    return re.sub(r"[^A-Za-z0-9_]", "_", value)


def mermaid_graph(nodes, edges):
    lines = ["flowchart TD"]
    for n in nodes:
        lines.append(
            f'    {mermaid_id(n["id"])}["{mermaid_text(n["etiqueta"])}<br/>{mermaid_text(n["detalle"])}"]'
        )
    for e in edges:
        label = mermaid_text(e["etiqueta"])
        lines.append(f"    {mermaid_id(e['origen'])} -->|{label}| {mermaid_id(e['destino'])}")
    return "\n".join(lines)


def names(software, actors):
    result = {a["id"]: a["nombre"] for a in actors}
    result.update({c["id"]: c["nombre"] for c in software["contenedores"]})
    result.update({c["id"]: c["nombre"] for c in software["componentes"]})
    return result


def container_of(software):
    mapping = {c["id"]: c["id"] for c in software["contenedores"]}
    mapping.update({c["id"]: c["contenedor"] for c in software["componentes"]})
    return mapping


def context_view(project, software, actors):
    system = "SISTEMA"
    owner = container_of(software)
    external = {c["id"] for c in software["contenedores"] if c["tipo"] == "servicio_externo"}

    def target(ref):
        if ref in external or ref.startswith("ACT-"):
            return ref
        return system if ref in owner else None

    nodes = [
        {
            "id": a["id"],
            "etiqueta": a["nombre"],
            "detalle": "Persona",
            "grupo": "persona",
            "capa": 0,
        }
        for a in actors
    ]
    nodes.append(
        {
            "id": system,
            "etiqueta": project,
            "detalle": "Sistema a construir",
            "grupo": "sistema",
            "capa": 1,
        }
    )
    nodes += [
        {
            "id": c["id"],
            "etiqueta": c["nombre"],
            "detalle": "Sistema externo · " + c["tecnologia"],
            "grupo": "externo",
            "capa": 2,
        }
        for c in software["contenedores"]
        if c["id"] in external
    ]
    edges = []
    for r in software["relaciones"]:
        a, b = target(r["origen"]), target(r["destino"])
        if a and b and a != b:
            edges.append({"origen": a, "destino": b, "etiqueta": r["descripcion"]})
    return graph_view(
        "c4-contexto",
        "C4 · Nivel 1: contexto",
        "Quién usa el sistema y con qué sistemas externos se comunica.",
        nodes,
        edges,
    )


def containers_view(software, actors):
    owner = container_of(software)
    nodes = [
        {
            "id": a["id"],
            "etiqueta": a["nombre"],
            "detalle": "Persona",
            "grupo": "persona",
            "capa": 0,
        }
        for a in actors
    ]
    nodes += [
        {
            "id": c["id"],
            "etiqueta": c["nombre"],
            "detalle": c["tecnologia"],
            "grupo": c["tipo"],
            "capa": CONTAINER_LAYER[c["tipo"]],
        }
        for c in software["contenedores"]
    ]
    edges = []
    for r in software["relaciones"]:
        a = r["origen"] if r["origen"].startswith("ACT-") else owner.get(r["origen"])
        b = r["destino"] if r["destino"].startswith("ACT-") else owner.get(r["destino"])
        if a and b and a != b:
            edges.append({"origen": a, "destino": b, "etiqueta": r["protocolo"]})
    return graph_view(
        "c4-contenedores",
        "C4 · Nivel 2: contenedores",
        "Las piezas desplegables: frontend, API del monolito, base de datos y servicios externos.",
        nodes,
        edges,
    )


def components_view(software, actors):
    """Componentes del monolito y, en los bordes, los actores y contenedores con los que hablan.

    Las conexiones salen de las relaciones y de los pasos de secuencia: ambos son datos del
    modelo, así el diagrama muestra la colaboración real sin inventar dependencias.
    """
    containers = {c["id"]: c for c in software["contenedores"]}
    components = {c["id"] for c in software["componentes"]}
    nodes = [
        {
            "id": c["id"],
            "etiqueta": c["nombre"],
            "detalle": containers.get(c["contenedor"], {}).get("nombre", c["contenedor"]),
            "grupo": c["tipo"],
            "capa": COMPONENT_LAYER[c["tipo"]] + 1,
        }
        for c in software["componentes"]
    ]
    # Relaciones con su protocolo; los pasos de secuencia aportan quién llama a quién (sin la respuesta).
    pairs, seen = [], set()
    candidates = [(r["origen"], r["destino"], r["protocolo"]) for r in software["relaciones"]]
    candidates += [
        (st["de"], st["a"], "")
        for f in software["flujos"]
        for st in [*f["pasos"], *f["alternativa"]]
    ]
    for a, b, label in candidates:
        if a != b and frozenset((a, b)) not in seen:
            seen.add(frozenset((a, b)))
            pairs.append((a, b, label))
    pairs = [p for p in pairs if p[0] in components or p[1] in components]
    border = {ref for a, b, _ in pairs for ref in (a, b) if ref not in components}
    people = {a["id"]: a for a in actors}
    for ref in sorted(border):
        if ref in people:
            nodes.append(
                {
                    "id": ref,
                    "etiqueta": people[ref]["nombre"],
                    "detalle": "Persona",
                    "grupo": "persona",
                    "capa": 0,
                }
            )
        elif ref in containers:
            c = containers[ref]
            nodes.append(
                {
                    "id": ref,
                    "etiqueta": c["nombre"],
                    "detalle": c["tecnologia"],
                    "grupo": c["tipo"],
                    "capa": 0 if c["tipo"] == "aplicacion_web" else 6,
                }
            )
    edges = [{"origen": a, "destino": b, "etiqueta": text} for a, b, text in pairs if a != b]
    return graph_view(
        "c4-componentes",
        "C4 · Nivel 3: componentes",
        "Módulos internos del monolito y cómo colaboran entre sí.",
        nodes,
        edges,
    )


def deployment_view(infra, environment):
    nodes = [
        {
            "id": n["id"],
            "etiqueta": n["nombre"],
            "detalle": n["tecnologia"] + (f" · x{n['replicas']}" if n["replicas"] > 1 else ""),
            "grupo": n["tipo"],
            "capa": INFRA_LAYER[n["tipo"]],
        }
        for n in infra["nodos"]
        if n["entorno"] == environment
    ]
    edges = [
        {"origen": c["origen"], "destino": c["destino"], "etiqueta": c["protocolo"]}
        for c in infra["conexiones"]
    ]
    local = environment == "local"
    return graph_view(
        f"despliegue-{environment}",
        "Despliegue local (Docker Compose)" if local else "Despliegue en la nube (AWS EKS)",
        "Cómo se ejecuta en el equipo del desarrollador."
        if local
        else "Cómo se ejecuta en producción sobre Kubernetes administrado.",
        nodes,
        edges,
    )


def sequence_view(flow, labels):
    participants = []
    for step in [*flow["pasos"], *flow["alternativa"]]:
        for ref in (step["de"], step["a"]):
            if ref not in participants:
                participants.append(ref)
    lines = ["sequenceDiagram"]
    for p in participants:
        lines.append(f"    participant {mermaid_id(p)} as {mermaid_text(labels.get(p, p))}")
    cut = flow["paso_desvio"] or len(flow["pasos"])
    main, rest = flow["pasos"][:cut], flow["pasos"][cut:]

    def arrows(steps, indent="    "):
        return [
            f"{indent}{mermaid_id(s['de'])}->>{mermaid_id(s['a'])}: {mermaid_text(s['mensaje'])}"
            for s in steps
        ]

    lines += arrows(main)
    if flow["alternativa"]:
        lines.append(f"    alt {mermaid_text(flow['condicion_alternativa'] or 'Camino principal')}")
        lines += arrows(rest, "        ")
        lines.append("    else Alternativa")
        lines += arrows(flow["alternativa"], "        ")
        lines.append("    end")
    else:
        lines += arrows(rest)
    return {
        "id": flow["id"].lower(),
        "tipo": "secuencia",
        "titulo": f"{flow['id']} · {flow['titulo']}",
        "explicacion": "Historias: " + ", ".join(flow["ids_historias"]),
        "participantes": [{"id": p, "etiqueta": labels.get(p, p)} for p in participants],
        "pasos": [{**s, "alternativa": False} for s in main + rest]
        + [{**s, "alternativa": True} for s in flow["alternativa"]],
        "paso_desvio": cut,
        "condicion_alternativa": flow["condicion_alternativa"],
        "mermaid": "\n".join(lines),
    }


def flow_view(flow, labels):
    """Diagrama de flujo: pasos en cadena y una decisión donde inicia la alternativa."""
    nodes, edges = [], []
    cut = flow["paso_desvio"] or len(flow["pasos"])
    previous = None
    for i, step in enumerate(flow["pasos"], start=1):
        node_id = f"P{i}"
        if i == cut + 1 and flow["alternativa"]:
            nodes.append(
                {
                    "id": "D",
                    "etiqueta": flow["condicion_alternativa"] or "¿Continúa?",
                    "detalle": "Decisión",
                    "grupo": "decision",
                    "capa": i,
                }
            )
            edges.append({"origen": previous, "destino": "D", "etiqueta": ""})
            previous = "D"
        nodes.append(
            {
                "id": node_id,
                "etiqueta": step["mensaje"][:70],
                "detalle": f"{labels.get(step['de'], step['de'])} → {labels.get(step['a'], step['a'])}",
                "grupo": "paso",
                "capa": i + (1 if i > cut and flow["alternativa"] else 0),
            }
        )
        if previous:
            edges.append(
                {
                    "origen": previous,
                    "destino": node_id,
                    "etiqueta": "Sí" if previous == "D" else "",
                }
            )
        previous = node_id
    if flow["alternativa"]:
        if "D" not in {n["id"] for n in nodes}:
            nodes.append(
                {
                    "id": "D",
                    "etiqueta": flow["condicion_alternativa"] or "¿Continúa?",
                    "detalle": "Decisión",
                    "grupo": "decision",
                    "capa": cut + 1,
                }
            )
            edges.append({"origen": f"P{cut}", "destino": "D", "etiqueta": ""})
        prev = "D"
        for j, step in enumerate(flow["alternativa"], start=1):
            node_id = f"A{j}"
            nodes.append(
                {
                    "id": node_id,
                    "etiqueta": step["mensaje"][:70],
                    "detalle": "Alternativa",
                    "grupo": "alternativa",
                    "capa": cut + 1 + j,
                }
            )
            edges.append(
                {"origen": prev, "destino": node_id, "etiqueta": "No" if prev == "D" else ""}
            )
            prev = node_id
    return graph_view(
        f"flujo-{flow['id'].lower()}",
        f"Flujo · {flow['titulo']}",
        "Pasos del proceso y la decisión que lleva al camino alternativo.",
        nodes,
        edges,
    )


def build_views(project, actors, software, infra):
    labels = names(software, actors)
    views = [
        context_view(project, software, actors),
        containers_view(software, actors),
        components_view(software, actors),
        deployment_view(infra, "local"),
        deployment_view(infra, "nube"),
    ]
    for flow in software["flujos"]:
        views.append(sequence_view(flow, labels))
        views.append(flow_view(flow, labels))
    return views


def drawio(views):
    """Archivo .drawio (XML de diagrams.net) con una página por vista de grafo."""
    style = {
        "persona": "shape=umlActor;verticalLabelPosition=bottom;verticalAlign=top;html=1;",
        "decision": "rhombus;whiteSpace=wrap;html=1;fillColor=#fff2cc;strokeColor=#d6b656;",
        "externo": "rounded=1;whiteSpace=wrap;html=1;fillColor=#f5f5f5;strokeColor=#666666;",
        "servicio_externo": "rounded=1;whiteSpace=wrap;html=1;fillColor=#f5f5f5;strokeColor=#666666;",
        "base_datos": "shape=cylinder3;whiteSpace=wrap;html=1;fillColor=#dae8fc;strokeColor=#6c8ebf;",
        "alternativa": "rounded=1;whiteSpace=wrap;html=1;fillColor=#f8cecc;strokeColor=#b85450;",
    }
    default = "rounded=1;whiteSpace=wrap;html=1;fillColor=#d5e8d4;strokeColor=#82b366;"
    pages = []
    for view in views:
        if view["tipo"] != "grafo":
            continue
        cells = ['<mxCell id="0"/>', '<mxCell id="1" parent="0"/>']
        for n in view["nodos"]:
            label = escape(
                f"<b>{escape(n['etiqueta'])}</b><br>{escape(n['detalle'])}", {'"': "&quot;"}
            )
            cells.append(
                f'<mxCell id="{escape(n["id"])}" value="{label}" style="{style.get(n["grupo"], default)}" '
                f'vertex="1" parent="1"><mxGeometry x="{n["x"]}" y="{n["y"]}" width="{n["w"]}" '
                f'height="{n["h"]}" as="geometry"/></mxCell>'
            )
        for i, e in enumerate(view["aristas"]):
            cells.append(
                f'<mxCell id="e{i}" value="{escape(e["etiqueta"], {chr(34): "&quot;"})}" '
                'style="edgeStyle=orthogonalEdgeStyle;rounded=1;html=1;endArrow=block;" edge="1" '
                f'parent="1" source="{escape(e["origen"])}" target="{escape(e["destino"])}">'
                '<mxGeometry relative="1" as="geometry"/></mxCell>'
            )
        pages.append(
            f'<diagram id="{escape(view["id"])}" name="{escape(view["titulo"], {chr(34): "&quot;"})}">'
            f'<mxGraphModel dx="1200" dy="800" grid="1" gridSize="10" page="1" pageWidth="{view["ancho"]}" '
            f'pageHeight="{view["alto"]}"><root>{"".join(cells)}</root></mxGraphModel></diagram>'
        )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n<mxfile host="trama">'
        + "".join(pages)
        + "</mxfile>\n"
    )


def _hosted(node, containers):
    return [containers[c] for c in node["aloja"] if c in containers]


def _env_name(item):
    return re.sub(r"[^A-Z0-9_]", "_", item.split()[0].upper())


def compose(software, infra):
    """docker-compose.yml para ejecutar todo el sistema en el equipo del desarrollador."""
    containers = {c["id"]: c for c in software["contenedores"]}
    local = [n for n in infra["nodos"] if n["entorno"] == "local"]
    # Solo contenedores y bases de datos se ejecutan en Compose; los externos no son servicios.
    service = {
        n["id"]: slug(n["nombre"]) for n in local if n["tipo"] in {"contenedor", "base_datos"}
    }
    depends = {}
    for c in infra["conexiones"]:
        if c["origen"] in service and c["destino"] in service:
            depends.setdefault(c["origen"], []).append(service[c["destino"]])
    lines = [
        "# Generado por Trama a partir de la arquitectura aprobada.",
        "# Uso: copie .env.example a .env y ejecute `docker compose up --build`.",
        "services:",
    ]
    volumes = []
    for n in local:
        if n["tipo"] not in {"contenedor", "base_datos"}:
            continue
        name = service[n["id"]]
        hosted = _hosted(n, containers)
        kinds = {c["tipo"] for c in hosted}
        lines.append(f"  {name}:")
        if n["tipo"] == "base_datos" or "base_datos" in kinds:
            lines += [
                "    image: postgres:16",
                "    environment:",
                "      POSTGRES_DB: ${POSTGRES_DB:-app}",
                "      POSTGRES_USER: ${POSTGRES_USER:-app}",
                "      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?Defina POSTGRES_PASSWORD en .env}",
                "    volumes:",
                f"      - {name}-data:/var/lib/postgresql/data",
                "    healthcheck:",
                '      test: ["CMD-SHELL", "pg_isready -U $${POSTGRES_USER:-app}"]',
                "      interval: 5s",
                "      retries: 10",
            ]
            volumes.append(f"{name}-data")
        else:
            folder = "./frontend" if "aplicacion_web" in kinds else "./backend"
            lines += ["    build:", f"      context: {folder}"]
            env = [_env_name(item) for item in n["configuracion"]]
            if env:
                lines.append("    environment:")
                lines += [f"      {key}: ${{{key}}}" for key in dict.fromkeys(env)]
        if n["puerto"]:
            lines += ["    ports:", f'      - "{n["puerto"]}:{n["puerto"]}"']
        if depends.get(n["id"]):
            lines.append("    depends_on:")
            lines += [f"      - {d}" for d in dict.fromkeys(depends[n["id"]])]
    if volumes:
        lines.append("volumes:")
        lines += [f"  {v}:" for v in volumes]
    return "\n".join(lines) + "\n"


def env_example(infra):
    keys = {"POSTGRES_DB": "app", "POSTGRES_USER": "app", "POSTGRES_PASSWORD": "cambie-esto"}
    for n in infra["nodos"]:
        if n["entorno"] == "local":
            for item in n["configuracion"]:
                keys.setdefault(_env_name(item), "")
    return "# Valores locales de ejemplo. No suba este archivo con secretos reales.\n" + "".join(
        f"{k}={v}\n" for k, v in keys.items()
    )


def kubernetes(project, software, infra):
    """Manifiestos para AWS EKS. Las imágenes y secretos se referencian, nunca se incrustan."""
    containers = {c["id"]: c for c in software["contenedores"]}
    cloud = [n for n in infra["nodos"] if n["entorno"] == "nube"]
    namespace = slug(project)
    docs = [
        "# Generado por Trama. Aplicar con: kubectl apply -f k8s.yaml\n"
        "# Reemplace ${ECR_REGISTRY} y ${TAG}; cree el secreto app-secrets antes de aplicar.\n"
        f"apiVersion: v1\nkind: Namespace\nmetadata:\n  name: {namespace}",
    ]
    services = {}
    for n in cloud:
        if n["tipo"] != "contenedor":
            continue
        name = slug(n["nombre"])
        kinds = {c["tipo"] for c in _hosted(n, containers)}
        port = n["puerto"] or (80 if "aplicacion_web" in kinds else 8000)
        services[name] = (port, kinds)
        env = list(dict.fromkeys(_env_name(item) for item in n["configuracion"]))
        env_lines = "".join(
            f"\n            - name: {key}\n              valueFrom:\n                secretKeyRef:\n"
            f"                  name: app-secrets\n                  key: {key}"
            for key in env
        )
        docs.append(
            f"apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: {name}\n  namespace: {namespace}\n"
            f"spec:\n  replicas: {n['replicas']}\n  selector:\n    matchLabels:\n      app: {name}\n"
            f"  template:\n    metadata:\n      labels:\n        app: {name}\n    spec:\n      containers:\n"
            f"        - name: {name}\n          image: ${{ECR_REGISTRY}}/{name}:${{TAG}}\n"
            f"          ports:\n            - containerPort: {port}\n"
            f"          resources:\n            requests:\n              cpu: 100m\n              memory: 128Mi\n"
            f"            limits:\n              cpu: 500m\n              memory: 512Mi"
            + (f"\n          env:{env_lines}" if env else "")
        )
        docs.append(
            f"apiVersion: v1\nkind: Service\nmetadata:\n  name: {name}\n  namespace: {namespace}\n"
            f"spec:\n  selector:\n    app: {name}\n  ports:\n    - port: {port}\n      targetPort: {port}"
        )
    if any(n["tipo"] == "balanceador" for n in cloud) and services:
        paths = []
        for name, (port, kinds) in services.items():
            path = "/api" if "api" in kinds else "/"
            paths.append(
                f"          - path: {path}\n            pathType: Prefix\n            backend:\n"
                f"              service:\n                name: {name}\n                port:\n"
                f"                  number: {port}"
            )
        paths.sort(key=lambda p: "path: /\n" in p)  # /api antes que la ruta raíz
        docs.append(
            f"apiVersion: networking.k8s.io/v1\nkind: Ingress\nmetadata:\n  name: {namespace}\n"
            f"  namespace: {namespace}\n  annotations:\n    alb.ingress.kubernetes.io/scheme: internet-facing\n"
            "    alb.ingress.kubernetes.io/target-type: ip\nspec:\n  ingressClassName: alb\n  rules:\n"
            "    - http:\n        paths:\n" + "\n".join(paths)
        )
    return "\n---\n".join(docs) + "\n"


def readme(content):
    """Guía para el desarrollador: qué se construye, por qué y cómo ejecutarlo."""
    sw, infra, plan = content["software"], content["infraestructura"], content.get("plan")
    out = [
        f"# Arquitectura · {content['nombre_proyecto']} (v{content['version_arquitectura']})",
        "",
        f"Origen: backlog v{content['version_backlog_origen']} · línea base v{content['version_linea_base_origen']}.",
        "",
        "## 1. Visión general",
        sw["resumen"],
        "",
        f"Estilo: **{sw['estilo'].replace('_', ' ')}**.",
        "",
        "## 2. Atributos de calidad",
        "| ID | Atributo | Escenario | Medida | Prioridad | Requisitos |",
        "|---|---|---|---|---|---|",
    ]
    out += [
        f"| {a['id']} | {a['atributo']} | {a['escenario']} | {a['medida']} | {a['prioridad']} | {', '.join(a['ids_requisitos'])} |"
        for a in sw["atributos_calidad"]
    ]
    out += ["", "## 3. Decisiones y tradeoffs (ADR)"]
    for d in sw["decisiones"]:
        out += [
            f"### {d['id']} · {d['titulo']}",
            f"- **Contexto:** {d['contexto']}",
            f"- **Decisión:** {d['decision']}",
            f"- **Alternativas:** {'; '.join(d['alternativas'])}",
            f"- **A favor:** {'; '.join(d['ventajas'])}",
            f"- **En contra (tradeoff):** {'; '.join(d['desventajas'])}",
            f"- **Atributos:** {', '.join(d['ids_atributos'])}",
            "",
        ]
    out += [
        "## 4. Contenedores y componentes (C4)",
        "| ID | Nombre | Tipo | Tecnología | Responsabilidad |",
        "|---|---|---|---|---|",
    ]
    out += [
        f"| {c['id']} | {c['nombre']} | {c['tipo']} | {c['tecnologia']} | {c['responsabilidad']} |"
        for c in sw["contenedores"]
    ]
    out += [
        "",
        "| ID | Componente | Contenedor | Historias | Operaciones |",
        "|---|---|---|---|---|",
    ]
    out += [
        f"| {c['id']} | {c['nombre']} | {c['contenedor']} | {', '.join(c['ids_historias'])} | {'; '.join(c['operaciones'])} |"
        for c in sw["componentes"]
    ]
    out += [
        "",
        "## 5. Ejecutar en local",
        "1. Instale Docker Desktop.",
        "2. Copie `.env.example` a `.env` y defina las contraseñas.",
        "3. Ejecute `docker compose up --build`.",
    ]
    out += [
        f"   - {n['nombre']}: http://localhost:{n['puerto']}"
        for n in infra["nodos"]
        if n["entorno"] == "local" and n["puerto"] and n["tipo"] == "contenedor"
    ]
    out += [
        "",
        "## 6. Desplegar en la nube (AWS EKS)",
        infra["estrategia_despliegue"],
        "",
        "1. Construya y publique las imágenes en ECR: `docker build` + `docker push ${ECR_REGISTRY}/<servicio>:${TAG}`.",
        "2. Cree el secreto de la aplicación (valores desde AWS Secrets Manager):",
        "   `kubectl -n <namespace> create secret generic app-secrets --from-env-file=.env.produccion`",
        "3. Aplique los manifiestos: `kubectl apply -f k8s.yaml`.",
        "",
        f"**Seguridad:** {infra['seguridad']}",
        "",
        f"**Observabilidad:** {infra['observabilidad']}",
        "",
        "| Nodo | Entorno | Tecnología | Aloja | Explicación |",
        "|---|---|---|---|---|",
    ]
    out += [
        f"| {n['nombre']} | {n['entorno']} | {n['tecnologia']} | {', '.join(n['aloja'])} | {n['explicacion']} |"
        for n in infra["nodos"]
    ]
    if plan:
        out += ["", "## 7. Plan de implementación", plan["resumen"], ""]
        out += ["| Orden | ID | Tarea | Rol | Depende de | Esfuerzo |", "|---|---|---|---|---|---|"]
        out += [
            f"| {i} | {t['id']} | {t['titulo']} | {t['rol']} | {', '.join(t['depende_de']) or '—'} | {t['esfuerzo']} |"
            for i, t in enumerate(plan["tareas"], start=1)
        ]
    return "\n".join(out) + "\n"


def files(content):
    sw, infra = content["software"], content["infraestructura"]
    return {
        "README.md": readme(content),
        "arquitectura.drawio": drawio(content["vistas"]),
        "docker-compose.yml": compose(sw, infra),
        ".env.example": env_example(infra),
        "k8s.yaml": kubernetes(content["nombre_proyecto"], sw, infra),
        "arquitectura.json": json.dumps(
            {k: v for k, v in content.items() if k not in {"vistas", "actores"}},
            ensure_ascii=False,
            indent=2,
        ),
    }
