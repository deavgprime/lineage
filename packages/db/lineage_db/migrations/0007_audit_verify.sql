-- Check a case's audit rows against the hash chain.
--
-- For each row, recompute its hash the way the chain trigger did, and check that the hash it links
-- back to belongs to a row that still exists. An edited row fails the first check, and a deleted row
-- breaks the second for the row after it. Rows from other cases are read only to find the linked
-- hash and are never returned. The API checks the caller can see the case before calling this.

CREATE FUNCTION audit_verify(target uuid)
RETURNS TABLE (seq bigint, hash_ok boolean, link_ok boolean)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
    SELECT
        a.seq,
        encode(digest(
            a.prev_hash || coalesce(a.case_id::text, '') || a.at::text || a.actor || a.action
                || a.payload::text,
            'sha256'), 'hex') = a.row_hash,
        a.prev_hash = repeat('0', 64)
            OR EXISTS (SELECT FROM audit_log p WHERE p.row_hash = a.prev_hash AND p.seq <> a.seq)
    FROM audit_log a
    WHERE a.case_id = target
    ORDER BY a.seq
$$;

REVOKE ALL ON FUNCTION audit_verify(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION audit_verify(uuid) TO lineage_app;
