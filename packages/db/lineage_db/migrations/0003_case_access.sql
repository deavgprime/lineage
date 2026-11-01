-- Case access by role and pack (decision 0003), enforced in the database as well as the API.
--
-- The API connects as the owner and, inside every request's transaction, switches to lineage_app
-- and records who is asking. Row-level security on lineage_app then limits each query to the cases
-- that user may see. Jobs that run as the owner, such as ingestion and migrations, are unaffected.

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'lineage_app') THEN
        CREATE ROLE lineage_app NOLOGIN;
    END IF;
END
$$;
GRANT lineage_app TO CURRENT_USER;

ALTER TABLE cases ADD COLUMN opened_by text;

-- Who is asking, as set by the API for the current transaction. Unset means nobody.
CREATE FUNCTION lineage_user_id() RETURNS text
    LANGUAGE sql STABLE AS $$ SELECT nullif(current_setting('lineage.user_id', true), '') $$;
CREATE FUNCTION lineage_user_role() RETURNS text
    LANGUAGE sql STABLE AS $$ SELECT nullif(current_setting('lineage.role', true), '') $$;
CREATE FUNCTION lineage_user_packs() RETURNS text[]
    LANGUAGE sql STABLE
    AS $$ SELECT string_to_array(nullif(current_setting('lineage.packs', true), ''), ',') $$;

CREATE FUNCTION lineage_can_see(jurisdiction text, assigned_to text) RETURNS boolean
    LANGUAGE sql STABLE AS $$
    SELECT jurisdiction = ANY (coalesce(lineage_user_packs(), '{}'))
        AND (lineage_user_role() IN ('mlro', 'auditor') OR assigned_to = lineage_user_id())
$$;

ALTER TABLE cases ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;

CREATE POLICY cases_read ON cases FOR SELECT TO lineage_app
    USING (lineage_can_see(jurisdiction, assigned_to));
-- A case is opened by an analyst or MLRO in their own pack and assigned to whoever opens it.
CREATE POLICY cases_open ON cases FOR INSERT TO lineage_app
    WITH CHECK (
        lineage_user_role() IN ('analyst', 'mlro')
        AND jurisdiction = ANY (coalesce(lineage_user_packs(), '{}'))
        AND assigned_to = lineage_user_id()
        AND opened_by = lineage_user_id()
    );
CREATE POLICY cases_change ON cases FOR UPDATE TO lineage_app
    USING (lineage_user_role() IN ('analyst', 'mlro') AND lineage_can_see(jurisdiction, assigned_to))
    WITH CHECK (lineage_can_see(jurisdiction, assigned_to));

CREATE POLICY audit_read ON audit_log FOR SELECT TO lineage_app
    USING (EXISTS (SELECT FROM cases c WHERE c.id = audit_log.case_id));
CREATE POLICY audit_write ON audit_log FOR INSERT TO lineage_app
    WITH CHECK (
        lineage_user_role() IN ('analyst', 'mlro')
        AND EXISTS (SELECT FROM cases c WHERE c.id = audit_log.case_id)
    );

-- The chain must link to the newest row in the whole log, not the newest row this user can see.
ALTER FUNCTION audit_log_chain() SECURITY DEFINER;
ALTER FUNCTION audit_log_chain() SET search_path = public;

GRANT SELECT, INSERT, UPDATE ON cases TO lineage_app;
GRANT SELECT, INSERT ON audit_log TO lineage_app;
GRANT USAGE ON SEQUENCE audit_log_seq_seq TO lineage_app;
GRANT SELECT ON source_records, screening_names TO lineage_app;
