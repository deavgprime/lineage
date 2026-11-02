-- Exports of a case's audit trail are recorded in the trail itself. Auditors otherwise write
-- nothing, so they may add exactly this one kind of row.
DROP POLICY audit_write ON audit_log;
CREATE POLICY audit_write ON audit_log FOR INSERT TO lineage_app
    WITH CHECK (
        (
            lineage_user_role() IN ('analyst', 'mlro')
            OR (lineage_user_role() = 'auditor' AND action = 'audit_export')
        )
        AND EXISTS (SELECT FROM cases c WHERE c.id = audit_log.case_id)
    );
