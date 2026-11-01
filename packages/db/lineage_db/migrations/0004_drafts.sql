-- Drafted files, and the case states a file moves through.

ALTER TABLE cases DROP CONSTRAINT cases_status_check;
UPDATE cases SET status = 'draft' WHERE status = 'in_review';
ALTER TABLE cases ADD CONSTRAINT cases_status_check
    CHECK (status IN ('drafting', 'draft', 'awaiting_mlro', 'final', 'failed'));

-- One row per agent run. The newest row is the file the analyst reviews.
CREATE TABLE drafts (
    id bigserial PRIMARY KEY,
    case_id uuid NOT NULL REFERENCES cases (id),
    created_at timestamptz NOT NULL DEFAULT now(),
    draft jsonb,
    evidence jsonb NOT NULL,
    alerts jsonb NOT NULL,
    minimum_rating text NOT NULL CHECK (minimum_rating IN ('low', 'medium', 'high')),
    attempts integer NOT NULL,
    citation_failures jsonb NOT NULL
);
CREATE INDEX drafts_case ON drafts (case_id, id DESC);

ALTER TABLE drafts ENABLE ROW LEVEL SECURITY;
CREATE POLICY drafts_read ON drafts FOR SELECT TO lineage_app
    USING (EXISTS (SELECT FROM cases c WHERE c.id = drafts.case_id));
CREATE POLICY drafts_write ON drafts FOR INSERT TO lineage_app
    WITH CHECK (
        lineage_user_role() IN ('analyst', 'mlro')
        AND EXISTS (SELECT FROM cases c WHERE c.id = drafts.case_id)
    );
GRANT SELECT, INSERT ON drafts TO lineage_app;
GRANT USAGE ON SEQUENCE drafts_id_seq TO lineage_app;
