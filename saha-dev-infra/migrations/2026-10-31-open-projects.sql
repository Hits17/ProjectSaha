-- Requires 2026-10-31-open-collaboration.sql and the existing library schema.
BEGIN;
CREATE TABLE IF NOT EXISTS open_projects (
    community_id UUID PRIMARY KEY REFERENCES communities(id) ON DELETE CASCADE,
    resource_id UUID NOT NULL REFERENCES open_resources(id),
    goal TEXT NOT NULL,
    repository_url VARCHAR(1000),
    contribution_guide TEXT,
    skills_needed VARCHAR[] NOT NULL DEFAULT '{}',
    stage VARCHAR(20) NOT NULL DEFAULT 'idea' CHECK (stage IN ('idea', 'research', 'prototype', 'testing', 'released'))
);
CREATE INDEX IF NOT EXISTS ix_open_projects_resource_id ON open_projects(resource_id);
CREATE TABLE IF NOT EXISTS project_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES open_projects(community_id) ON DELETE CASCADE,
    created_by UUID NOT NULL REFERENCES users(id),
    title VARCHAR(240) NOT NULL,
    description TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'todo' CHECK (status IN ('todo','doing','done')),
    assigned_to UUID REFERENCES users(id),
    version INTEGER NOT NULL DEFAULT 1 CHECK (version >= 1),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_project_tasks_project_id ON project_tasks(project_id, created_at);
GRANT SELECT, INSERT, UPDATE, DELETE ON open_projects, project_tasks TO saha;
COMMIT;
