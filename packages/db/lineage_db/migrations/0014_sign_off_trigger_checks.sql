-- The sign-off trigger also checks where a case is coming from and who signed (#148). Before, a
-- sign-off row in the same transaction was enough, so a direct update could finish a failed or
-- drafting case, or record a first sign-off by an analyst the case is not assigned to. The API
-- already refused both; now the database does too.

CREATE OR REPLACE FUNCTION cases_guard_status() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
    first_row sign_offs%ROWTYPE;
    this_row sign_offs%ROWTYPE;
    latest_draft bigint;
    floor text;
BEGIN
    IF OLD.status = 'final' THEN
        RAISE EXCEPTION 'case % is final and cannot change', OLD.id;
    END IF;
    IF NEW.status = OLD.status OR NEW.status NOT IN ('awaiting_mlro', 'final') THEN
        RETURN NEW;
    END IF;
    IF OLD.status NOT IN ('draft', 'awaiting_mlro') THEN
        RAISE EXCEPTION 'a % case cannot be signed off', OLD.status;
    END IF;

    SELECT * INTO this_row FROM sign_offs
    WHERE case_id = NEW.id AND txid = txid_current() AND rating = NEW.rating
    ORDER BY id DESC LIMIT 1;
    IF this_row.id IS NULL THEN
        RAISE EXCEPTION 'case % can only be signed off through a sign-off', NEW.id;
    END IF;
    SELECT id INTO latest_draft FROM drafts WHERE case_id = NEW.id ORDER BY id DESC LIMIT 1;
    IF this_row.draft_id IS DISTINCT FROM latest_draft THEN
        RAISE EXCEPTION 'a sign-off must be for the latest draft';
    END IF;
    IF OLD.status = 'draft' AND (
        this_row.stage <> 'first'
        OR (this_row.signer_role = 'analyst' AND this_row.signer IS DISTINCT FROM OLD.assigned_to)
    ) THEN
        RAISE EXCEPTION 'only the assigned analyst or an MLRO can give the first sign-off';
    END IF;
    IF OLD.status = 'awaiting_mlro' AND (this_row.stage <> 'second' OR this_row.signer_role <> 'mlro') THEN
        RAISE EXCEPTION 'a case awaiting an MLRO needs the second sign-off';
    END IF;

    IF NEW.status = 'final' THEN
        SELECT * INTO first_row FROM sign_offs
        WHERE case_id = NEW.id AND stage = 'first' AND draft_id = latest_draft
        ORDER BY id DESC LIMIT 1;
        SELECT minimum_rating INTO floor FROM drafts WHERE id = latest_draft;
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
