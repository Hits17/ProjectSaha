-- Standalone, invite-only projects with external reference shortcuts.
BEGIN;
ALTER TABLE open_projects ALTER COLUMN resource_id DROP NOT NULL;
-- Existing project memberships are preserved. Never publish old project data.
UPDATE communities SET visibility = 'private' WHERE id IN (SELECT community_id FROM open_projects);
UPDATE posts SET visibility = 'community' WHERE community_id IN (SELECT community_id FROM open_projects);
CREATE TABLE IF NOT EXISTS project_references (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 project_id uuid NOT NULL REFERENCES open_projects(community_id) ON DELETE CASCADE,
 created_by uuid NOT NULL REFERENCES users(id),
 title varchar(180) NOT NULL,
 url varchar(2000) NOT NULL,
 description text,
 platform varchar(30) NOT NULL CHECK (platform IN ('website','google_drive','google_docs','google_sheets','google_slides','dropbox','onedrive','github','gitlab','figma','notion','youtube','zenodo','osf','other')),
 file_type varchar(30) NOT NULL CHECK (file_type IN ('document','spreadsheet','presentation','design','code','dataset','image','video','paper','folder','other')),
 pinned boolean NOT NULL DEFAULT false,
 version integer NOT NULL DEFAULT 1 CHECK (version > 0),
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_project_references_project_id ON project_references(project_id);
GRANT SELECT, INSERT, UPDATE, DELETE ON project_references TO saha;
COMMIT;
