-- Policy questions and their answers, and audit rows that belong to no case.

CREATE TABLE policy_questions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    at timestamptz NOT NULL DEFAULT now(),
    asked_by text NOT NULL,
    asked_by_name text NOT NULL,
    pack text NOT NULL CHECK (pack IN ('uk', 'uae')),
    question text NOT NULL,
    answer jsonb,
    passages jsonb NOT NULL,
    attempts integer NOT NULL,
    citation_failures jsonb NOT NULL
);
CREATE INDEX policy_questions_asker ON policy_questions (asked_by, at DESC);

-- Users see their own questions. MLROs and auditors see every question in their packs.
ALTER TABLE policy_questions ENABLE ROW LEVEL SECURITY;
CREATE POLICY policy_questions_read ON policy_questions FOR SELECT TO lineage_app
    USING (
        pack = ANY (coalesce(lineage_user_packs(), '{}'))
        AND (asked_by = lineage_user_id() OR lineage_user_role() IN ('mlro', 'auditor'))
    );
CREATE POLICY policy_questions_write ON policy_questions FOR INSERT TO lineage_app
    WITH CHECK (
        asked_by = lineage_user_id() AND pack = ANY (coalesce(lineage_user_packs(), '{}'))
    );
GRANT SELECT, INSERT ON policy_questions TO lineage_app;

-- Audit rows with no case: a user writes them as themselves, and reads their own. MLROs and
-- auditors read them all. The chain trigger covers them like any other row.
DROP POLICY audit_read ON audit_log;
CREATE POLICY audit_read ON audit_log FOR SELECT TO lineage_app
    USING (
        EXISTS (SELECT FROM cases c WHERE c.id = audit_log.case_id)
        OR (
            audit_log.case_id IS NULL
            AND (actor = lineage_user_id() OR lineage_user_role() IN ('mlro', 'auditor'))
        )
    );
DROP POLICY audit_write ON audit_log;
CREATE POLICY audit_write ON audit_log FOR INSERT TO lineage_app
    WITH CHECK (
        (
            (
                lineage_user_role() IN ('analyst', 'mlro')
                OR (lineage_user_role() = 'auditor' AND action = 'audit_export')
            )
            AND EXISTS (SELECT FROM cases c WHERE c.id = audit_log.case_id)
        )
        OR (
            audit_log.case_id IS NULL
            AND actor IN (lineage_user_id(), 'agent')
            AND action IN ('policy_question', 'policy_search', 'model_call', 'policy_answer')
        )
    );
