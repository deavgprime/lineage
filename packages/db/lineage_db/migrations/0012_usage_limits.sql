-- Counts the API checks before starting paid work (#142). Row-level security hides other users'
-- rows, so the counts that span everyone are read through these functions, which return numbers only.

CREATE FUNCTION lineage_drafting_now() RETURNS integer
    LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
    SELECT count(*)::integer FROM cases WHERE status = 'drafting'
$$;

CREATE FUNCTION lineage_user_usage(window_seconds integer)
RETURNS TABLE (cases_opened integer, drafting integer, questions integer)
    LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
    SELECT
        (SELECT count(*) FROM cases
         WHERE opened_by = lineage_user_id()
           AND created_at > now() - make_interval(secs => window_seconds))::integer,
        (SELECT count(*) FROM cases
         WHERE opened_by = lineage_user_id() AND status = 'drafting')::integer,
        (SELECT count(*) FROM policy_questions
         WHERE asked_by = lineage_user_id()
           AND at > now() - make_interval(secs => window_seconds))::integer
$$;

REVOKE ALL ON FUNCTION lineage_drafting_now() FROM PUBLIC;
REVOKE ALL ON FUNCTION lineage_user_usage(integer) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION lineage_drafting_now() TO lineage_app;
GRANT EXECUTE ON FUNCTION lineage_user_usage(integer) TO lineage_app;
