CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS schema_versions (
    version integer PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS projects (
    id uuid PRIMARY KEY, name text NOT NULL, description text NOT NULL DEFAULT '',
    mode text NOT NULL CHECK (mode IN ('supervisado','automatico')),
    state_revision integer NOT NULL DEFAULT 0,
    knowledge_revision integer NOT NULL DEFAULT 0,
    counters jsonb NOT NULL DEFAULT '{}', created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS conversations (
    id uuid PRIMARY KEY, project_id uuid NOT NULL REFERENCES projects(id),
    title text NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS executions (
    id uuid PRIMARY KEY, project_id uuid NOT NULL REFERENCES projects(id),
    conversation_id uuid REFERENCES conversations(id), request_id uuid,
    kind text NOT NULL, status text NOT NULL DEFAULT 'pendiente',
    input jsonb NOT NULL DEFAULT '{}', output jsonb,
    created_at timestamptz NOT NULL DEFAULT now(), finished_at timestamptz,
    UNIQUE(conversation_id, request_id)
);
CREATE UNIQUE INDEX IF NOT EXISTS one_active_chat ON executions(conversation_id)
    WHERE status IN ('pendiente','ejecutando') AND kind='chat';
CREATE TABLE IF NOT EXISTS messages (
    id uuid PRIMARY KEY, conversation_id uuid NOT NULL REFERENCES conversations(id),
    execution_id uuid REFERENCES executions(id), role text NOT NULL,
    content text NOT NULL, sources jsonb NOT NULL DEFAULT '[]',
    created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(execution_id, role)
);
CREATE TABLE IF NOT EXISTS events (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    execution_id uuid NOT NULL REFERENCES executions(id), component text NOT NULL,
    operation text NOT NULL, status text NOT NULL, description text NOT NULL,
    data jsonb NOT NULL DEFAULT '{}', duration_ms double precision,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS events_execution ON events(execution_id,id);
CREATE TABLE IF NOT EXISTS development_workflows (
    id uuid PRIMARY KEY REFERENCES executions(id), project_id uuid NOT NULL REFERENCES projects(id),
    mode text NOT NULL CHECK (mode IN ('supervisado','automatico')),
    conversation_id uuid NOT NULL REFERENCES conversations(id),
    progress jsonb NOT NULL DEFAULT '{}', updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS workflow_request ON executions(project_id,request_id)
    WHERE kind='flujo_completo';
CREATE UNIQUE INDEX IF NOT EXISTS one_active_workflow ON executions(project_id)
    WHERE kind='flujo_completo' AND status IN ('pendiente','ejecutando');
CREATE TABLE IF NOT EXISTS functional_items (
    project_id uuid NOT NULL REFERENCES projects(id), id text NOT NULL,
    version integer NOT NULL, payload jsonb NOT NULL,
    PRIMARY KEY(project_id,id,version)
);
CREATE TABLE IF NOT EXISTS proposals (
    id uuid PRIMARY KEY, project_id uuid NOT NULL REFERENCES projects(id),
    execution_id uuid NOT NULL REFERENCES executions(id), message_id uuid NOT NULL,
    change jsonb NOT NULL, status text NOT NULL, validation jsonb NOT NULL DEFAULT '[]',
    resulting_id text, created_at timestamptz NOT NULL DEFAULT now(), reviewed_at timestamptz,
    UNIQUE(execution_id,change)
);
CREATE TABLE IF NOT EXISTS conflicts (
    id uuid PRIMARY KEY, project_id uuid NOT NULL REFERENCES projects(id),
    execution_id uuid NOT NULL REFERENCES executions(id), description text NOT NULL,
    resolution text, created_at timestamptz NOT NULL DEFAULT now(), resolved_at timestamptz,
    UNIQUE(execution_id,description)
);
CREATE TABLE IF NOT EXISTS baselines (
    project_id uuid NOT NULL REFERENCES projects(id), version integer NOT NULL,
    payload jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY(project_id,version)
);
CREATE TABLE IF NOT EXISTS documents (
    id uuid PRIMARY KEY, project_id uuid NOT NULL REFERENCES projects(id),
    name text NOT NULL, media_type text NOT NULL, category text NOT NULL,
    content_hash text NOT NULL, version integer NOT NULL DEFAULT 1,
    status text NOT NULL, embedding_signature text NOT NULL,
    storage_path text NOT NULL, last_error text,
    created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(project_id,name)
);
CREATE TABLE IF NOT EXISTS chunks (
    id uuid PRIMARY KEY, document_id uuid NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    page integer NOT NULL, position integer NOT NULL, content text NOT NULL,
    embedding vector NOT NULL
);
CREATE INDEX IF NOT EXISTS chunks_document ON chunks(document_id);
CREATE TABLE IF NOT EXISTS document_versions (
    document_id uuid NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    version integer NOT NULL, storage_path text NOT NULL, content_hash text NOT NULL,
    name text NOT NULL, media_type text NOT NULL,
    PRIMARY KEY(document_id,version)
);
INSERT INTO document_versions(document_id,version,storage_path,content_hash,name,media_type)
    SELECT id,version,storage_path,content_hash,name,media_type FROM documents WHERE status='indexado'
    ON CONFLICT DO NOTHING;
CREATE OR REPLACE FUNCTION protect_immutable_version() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'Las versiones publicadas son inmutables' USING ERRCODE='55000';
END;
$$;
CREATE OR REPLACE TRIGGER immutable_baselines BEFORE UPDATE OR DELETE ON baselines
    FOR EACH ROW EXECUTE FUNCTION protect_immutable_version();
CREATE OR REPLACE TRIGGER immutable_functional_versions BEFORE UPDATE OR DELETE ON functional_items
    FOR EACH ROW EXECUTE FUNCTION protect_immutable_version();
INSERT INTO schema_versions(version) VALUES(1) ON CONFLICT DO NOTHING;
INSERT INTO schema_versions(version) VALUES(2) ON CONFLICT DO NOTHING;
CREATE TABLE IF NOT EXISTS backlog_revisions (
    project_id uuid NOT NULL REFERENCES projects(id), version integer NOT NULL,
    baseline_version integer NOT NULL, execution_id uuid NOT NULL UNIQUE REFERENCES executions(id),
    parent_version integer, payload jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY(project_id,version),
    FOREIGN KEY(project_id,baseline_version) REFERENCES baselines(project_id,version)
);
CREATE TABLE IF NOT EXISTS backlog_decisions (
    id uuid PRIMARY KEY, project_id uuid NOT NULL, version integer NOT NULL,
    status text NOT NULL, note text NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(project_id,version), FOREIGN KEY(project_id,version) REFERENCES backlog_revisions(project_id,version)
);
CREATE TABLE IF NOT EXISTS backlog_publications (
    project_id uuid NOT NULL, version integer NOT NULL, payload jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(project_id,version),
    FOREIGN KEY(project_id,version) REFERENCES backlog_revisions(project_id,version)
);
CREATE UNIQUE INDEX IF NOT EXISTS one_active_backlog ON executions(project_id)
    WHERE kind='backlog' AND status IN ('pendiente','ejecutando');
CREATE UNIQUE INDEX IF NOT EXISTS backlog_request_id ON executions(project_id,request_id)
    WHERE kind='backlog';
CREATE OR REPLACE TRIGGER immutable_backlog_revisions BEFORE UPDATE OR DELETE ON backlog_revisions
    FOR EACH ROW EXECUTE FUNCTION protect_immutable_version();
CREATE OR REPLACE TRIGGER immutable_backlog_decisions BEFORE UPDATE OR DELETE ON backlog_decisions
    FOR EACH ROW EXECUTE FUNCTION protect_immutable_version();
CREATE OR REPLACE TRIGGER immutable_backlog_publications BEFORE UPDATE OR DELETE ON backlog_publications
    FOR EACH ROW EXECUTE FUNCTION protect_immutable_version();
INSERT INTO schema_versions(version) VALUES(3) ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS mockup_revisions (
 project_id uuid NOT NULL REFERENCES projects(id), version integer NOT NULL,
 backlog_version integer NOT NULL, execution_id uuid NOT NULL UNIQUE REFERENCES executions(id),
 payload jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(project_id,version),
 FOREIGN KEY(project_id,backlog_version) REFERENCES backlog_publications(project_id,version)
);
CREATE TABLE IF NOT EXISTS mockup_decisions (
 project_id uuid NOT NULL, version integer NOT NULL, status text NOT NULL,
 note text NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(project_id,version),
 FOREIGN KEY(project_id,version) REFERENCES mockup_revisions(project_id,version)
);
CREATE OR REPLACE TRIGGER immutable_mockups BEFORE UPDATE OR DELETE ON mockup_revisions
 FOR EACH ROW EXECUTE FUNCTION protect_immutable_version();
CREATE OR REPLACE TRIGGER immutable_mockup_decisions BEFORE UPDATE OR DELETE ON mockup_decisions
 FOR EACH ROW EXECUTE FUNCTION protect_immutable_version();
CREATE UNIQUE INDEX IF NOT EXISTS one_active_mockups ON executions(project_id)
 WHERE status IN ('pendiente','ejecutando') AND kind='mockups';
CREATE UNIQUE INDEX IF NOT EXISTS mockup_request ON executions(project_id,request_id) WHERE kind='mockups';
INSERT INTO schema_versions(version) VALUES(4) ON CONFLICT DO NOTHING;

ALTER TABLE projects ADD COLUMN IF NOT EXISTS deleted_at timestamptz;
CREATE TABLE IF NOT EXISTS project_lifecycle_events (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 project_id uuid NOT NULL REFERENCES projects(id),
 operation text NOT NULL CHECK(operation IN ('eliminar','restaurar')),
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE OR REPLACE TRIGGER immutable_project_lifecycle BEFORE UPDATE OR DELETE ON project_lifecycle_events
 FOR EACH ROW EXECUTE FUNCTION protect_immutable_version();
CREATE OR REPLACE FUNCTION guard_project_execution() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE archived timestamptz;
BEGIN
 SELECT deleted_at INTO archived FROM projects WHERE id=NEW.project_id FOR UPDATE;
 IF archived IS NOT NULL AND NEW.status IN ('pendiente','ejecutando') THEN
  RAISE EXCEPTION 'El proyecto está en la papelera; restáurelo para continuar'
    USING ERRCODE='23514', CONSTRAINT='project_in_trash';
 END IF;
 RETURN NEW;
END;
$$;
CREATE OR REPLACE TRIGGER active_project_execution BEFORE INSERT OR UPDATE OF status ON executions
 FOR EACH ROW EXECUTE FUNCTION guard_project_execution();
INSERT INTO schema_versions(version) VALUES(5) ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS project_document_links (
 project_id uuid NOT NULL REFERENCES projects(id), document_id uuid NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
 created_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(project_id,document_id)
);
CREATE OR REPLACE VIEW project_knowledge_documents AS
 SELECT d.*, d.project_id AS consumer_project_id, false AS compartido FROM documents d
 UNION ALL
 SELECT d.*, l.project_id AS consumer_project_id, true AS compartido FROM documents d
 JOIN project_document_links l ON l.document_id=d.id WHERE l.project_id<>d.project_id;
CREATE OR REPLACE FUNCTION bump_linked_knowledge() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_TABLE_NAME='project_document_links' THEN
  IF TG_OP='DELETE' THEN
   UPDATE projects SET knowledge_revision=knowledge_revision+1 WHERE id=OLD.project_id;
  ELSE
   UPDATE projects SET knowledge_revision=knowledge_revision+1 WHERE id=NEW.project_id;
  END IF;
 ELSE
  UPDATE projects SET knowledge_revision=knowledge_revision+1
   WHERE id IN (SELECT project_id FROM project_document_links WHERE document_id=NEW.id);
 END IF;
 RETURN NULL;
END;
$$;
CREATE OR REPLACE TRIGGER linked_knowledge_revision AFTER INSERT OR DELETE ON project_document_links
 FOR EACH ROW EXECUTE FUNCTION bump_linked_knowledge();
CREATE OR REPLACE TRIGGER shared_document_revision AFTER UPDATE OF version,status,content_hash,embedding_signature ON documents
 FOR EACH ROW EXECUTE FUNCTION bump_linked_knowledge();
INSERT INTO schema_versions(version) VALUES(6) ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS architecture_revisions (
 project_id uuid NOT NULL REFERENCES projects(id), version integer NOT NULL,
 backlog_version integer NOT NULL, execution_id uuid NOT NULL UNIQUE REFERENCES executions(id),
 payload jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(project_id,version),
 FOREIGN KEY(project_id,backlog_version) REFERENCES backlog_publications(project_id,version)
);
CREATE TABLE IF NOT EXISTS architecture_decisions (
 project_id uuid NOT NULL, version integer NOT NULL, status text NOT NULL,
 note text NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(project_id,version),
 FOREIGN KEY(project_id,version) REFERENCES architecture_revisions(project_id,version)
);
CREATE OR REPLACE TRIGGER immutable_architecture BEFORE UPDATE OR DELETE ON architecture_revisions
 FOR EACH ROW EXECUTE FUNCTION protect_immutable_version();
CREATE OR REPLACE TRIGGER immutable_architecture_decisions BEFORE UPDATE OR DELETE ON architecture_decisions
 FOR EACH ROW EXECUTE FUNCTION protect_immutable_version();
CREATE UNIQUE INDEX IF NOT EXISTS one_active_architecture ON executions(project_id)
 WHERE status IN ('pendiente','ejecutando') AND kind='arquitectura';
CREATE UNIQUE INDEX IF NOT EXISTS architecture_request ON executions(project_id,request_id) WHERE kind='arquitectura';
INSERT INTO schema_versions(version) VALUES(7) ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS construction_revisions (
 project_id uuid NOT NULL REFERENCES projects(id), version integer NOT NULL,
 architecture_version integer NOT NULL, execution_id uuid NOT NULL UNIQUE REFERENCES executions(id),
 payload jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(project_id,version),
 FOREIGN KEY(project_id,architecture_version) REFERENCES architecture_revisions(project_id,version)
);
CREATE TABLE IF NOT EXISTS construction_decisions (
 project_id uuid NOT NULL, version integer NOT NULL, status text NOT NULL,
 note text NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(project_id,version),
 FOREIGN KEY(project_id,version) REFERENCES construction_revisions(project_id,version)
);
CREATE OR REPLACE TRIGGER immutable_construction BEFORE UPDATE OR DELETE ON construction_revisions
 FOR EACH ROW EXECUTE FUNCTION protect_immutable_version();
CREATE OR REPLACE TRIGGER immutable_construction_decisions BEFORE UPDATE OR DELETE ON construction_decisions
 FOR EACH ROW EXECUTE FUNCTION protect_immutable_version();
CREATE TABLE IF NOT EXISTS deployments (
 project_id uuid NOT NULL, version integer NOT NULL, execution_id uuid REFERENCES executions(id),
 status text NOT NULL, ports jsonb NOT NULL DEFAULT '{}', result jsonb NOT NULL DEFAULT '{}',
 updated_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(project_id,version),
 FOREIGN KEY(project_id,version) REFERENCES construction_revisions(project_id,version)
);
CREATE UNIQUE INDEX IF NOT EXISTS deployment_request_id ON executions(project_id,request_id)
 WHERE kind='despliegue' AND request_id IS NOT NULL;
CREATE TABLE IF NOT EXISTS notifications (
 id bigserial PRIMARY KEY, project_id uuid NOT NULL REFERENCES projects(id),
 kind text NOT NULL, title text NOT NULL, message text NOT NULL, link text,
 execution_id uuid REFERENCES executions(id), read_at timestamptz,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS unread_notifications ON notifications(created_at DESC) WHERE read_at IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS one_active_construction ON executions(project_id)
 WHERE status IN ('pendiente','ejecutando') AND kind='construccion';
CREATE UNIQUE INDEX IF NOT EXISTS construction_request ON executions(project_id,request_id) WHERE kind='construccion';
CREATE UNIQUE INDEX IF NOT EXISTS one_active_deployment ON executions(project_id)
 WHERE status IN ('pendiente','ejecutando') AND kind='despliegue';
INSERT INTO schema_versions(version) VALUES(8) ON CONFLICT DO NOTHING;
