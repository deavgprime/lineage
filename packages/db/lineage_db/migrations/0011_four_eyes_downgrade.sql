-- A file needs the MLRO's second sign-off whenever it was drafted high, a strong screening match set
-- its minimum to high, it is signed off as high, or the first signer lowered the rating. Before
-- this, only the final rating counted, so one analyst could take a high file down to low alone.

CREATE FUNCTION lineage_rating_rank(rating text) RETURNS integer
    LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE rating WHEN 'low' THEN 1 WHEN 'medium' THEN 2 WHEN 'high' THEN 3 END
$$;

CREATE OR REPLACE FUNCTION cases_guard_status() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
    first_row sign_offs%ROWTYPE;
    floor text;
BEGIN
    IF OLD.status = 'final' THEN
        RAISE EXCEPTION 'case % is final and cannot change', OLD.id;
    END IF;
    IF NEW.status = OLD.status OR NEW.status NOT IN ('awaiting_mlro', 'final') THEN
        RETURN NEW;
    END IF;
    IF NOT EXISTS (
        SELECT FROM sign_offs
        WHERE case_id = NEW.id AND txid = txid_current() AND rating = NEW.rating
    ) THEN
        RAISE EXCEPTION 'case % can only be signed off through a sign-off', NEW.id;
    END IF;
    IF NEW.status = 'final' THEN
        SELECT * INTO first_row FROM sign_offs
        WHERE case_id = NEW.id AND stage = 'first' ORDER BY id DESC LIMIT 1;
        SELECT minimum_rating INTO floor FROM drafts WHERE id = first_row.draft_id;
        IF NEW.rating = 'high'
            OR first_row.drafted_rating = 'high'
            OR floor = 'high'
            OR lineage_rating_rank(first_row.rating) < lineage_rating_rank(first_row.drafted_rating)
        THEN
            IF NOT EXISTS (
                SELECT FROM sign_offs
                WHERE case_id = NEW.id AND stage = 'second' AND signer_role = 'mlro'
                    AND signer IS DISTINCT FROM first_row.signer AND txid = txid_current()
            ) THEN
                RAISE EXCEPTION 'this case needs a second sign-off by a different MLRO';
            END IF;
        END IF;
    END IF;
    RETURN NEW;
END;
$$;
