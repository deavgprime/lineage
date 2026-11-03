-- Cases left drafting by a stopped API process (#149). Drafting runs in the API process, so a
-- restart mid-draft used to leave the case drafting forever, and since #154 it also held drafting
-- capacity. Any case drafting for longer than the limit is failed here, with an audit row.

CREATE FUNCTION lineage_fail_stale_drafts(older_than_seconds integer) RETURNS integer
    LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
    stale uuid;
    n integer := 0;
BEGIN
    FOR stale IN
        SELECT id FROM cases
        WHERE status = 'drafting'
          -- Never less than ten minutes, whatever the caller asks, so this cannot be used to fail
          -- cases that are still drafting.
          AND updated_at < now() - make_interval(secs => greatest(older_than_seconds, 600))
        FOR UPDATE SKIP LOCKED
    LOOP
        UPDATE cases SET status = 'failed', updated_at = now() WHERE id = stale;
        INSERT INTO audit_log (case_id, actor, action, payload, prev_hash, row_hash)
        VALUES (stale, 'system', 'drafting_timed_out',
                jsonb_build_object('after_seconds', older_than_seconds), '', '');
        n := n + 1;
    END LOOP;
    RETURN n;
END;
$$;

REVOKE ALL ON FUNCTION lineage_fail_stale_drafts(integer) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION lineage_fail_stale_drafts(integer) TO lineage_app;
