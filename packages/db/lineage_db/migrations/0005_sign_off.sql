-- Analyst sign-off and the MLRO's second sign-off on high-rated files (decision 0003).
--
-- Only a sign-off moves a case to awaiting_mlro or final, and a final case never changes again.
-- The trigger below checks that a matching sign-off row was written in the same transaction, so the
-- agent, a script or a bug in the API cannot finish a file on its own.

ALTER TABLE cases ADD COLUMN rating text CHECK (rating IN ('low', 'medium', 'high'));

CREATE TABLE sign_offs (
    id bigserial PRIMARY KEY,
    case_id uuid NOT NULL REFERENCES cases (id),
    draft_id bigint NOT NULL REFERENCES drafts (id),
    at timestamptz NOT NULL DEFAULT now(),
    txid bigint NOT NULL DEFAULT txid_current(),
    signer text NOT NULL,
    signer_role text NOT NULL CHECK (signer_role IN ('analyst', 'mlro')),
    stage text NOT NULL CHECK (stage IN ('first', 'second')),
    drafted_rating text NOT NULL CHECK (drafted_rating IN ('low', 'medium', 'high')),
    rating text NOT NULL CHECK (rating IN ('low', 'medium', 'high')),
    reason text,
    alert_notes jsonb NOT NULL DEFAULT '{}',
    CHECK (rating = drafted_rating OR coalesce(length(trim(reason)), 0) > 0),
    CHECK (stage = 'first' OR signer_role = 'mlro')
);
CREATE UNIQUE INDEX sign_offs_one_per_stage ON sign_offs (case_id, draft_id, stage);

CREATE FUNCTION cases_guard_status() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
    first_signer text;
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
    IF NEW.status = 'final' AND NEW.rating = 'high' THEN
        SELECT signer INTO first_signer FROM sign_offs
        WHERE case_id = NEW.id AND stage = 'first' ORDER BY id DESC LIMIT 1;
        IF NOT EXISTS (
            SELECT FROM sign_offs
            WHERE case_id = NEW.id AND stage = 'second' AND signer_role = 'mlro'
                AND signer IS DISTINCT FROM first_signer AND txid = txid_current()
        ) THEN
            RAISE EXCEPTION 'a high-rated case needs a second sign-off by a different MLRO';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER cases_guard_status BEFORE UPDATE ON cases
    FOR EACH ROW EXECUTE FUNCTION cases_guard_status();

ALTER TABLE sign_offs ENABLE ROW LEVEL SECURITY;
CREATE POLICY sign_offs_read ON sign_offs FOR SELECT TO lineage_app
    USING (EXISTS (SELECT FROM cases c WHERE c.id = sign_offs.case_id));
CREATE POLICY sign_offs_write ON sign_offs FOR INSERT TO lineage_app
    WITH CHECK (
        signer = lineage_user_id()
        AND signer_role = lineage_user_role()
        AND EXISTS (SELECT FROM cases c WHERE c.id = sign_offs.case_id)
    );
GRANT SELECT, INSERT ON sign_offs TO lineage_app;
GRANT USAGE ON SEQUENCE sign_offs_id_seq TO lineage_app;
