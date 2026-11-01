-- Cases, source records and the hash-chained audit log.

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE cases (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    jurisdiction text NOT NULL CHECK (jurisdiction IN ('uk', 'uae')),
    subject text NOT NULL,
    company_number text,
    status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'in_review', 'final')),
    assigned_to text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE source_records (
    id text PRIMARY KEY,
    source text NOT NULL,
    dataset_version text NOT NULL,
    record jsonb NOT NULL,
    checksum text NOT NULL,
    loaded_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX source_records_source ON source_records (source);

-- Append only. Each row stores the hash of the row before it, so editing history breaks the chain.
CREATE TABLE audit_log (
    seq bigserial PRIMARY KEY,
    case_id uuid REFERENCES cases (id),
    at timestamptz NOT NULL DEFAULT now(),
    actor text NOT NULL,
    action text NOT NULL,
    payload jsonb NOT NULL,
    prev_hash text NOT NULL,
    row_hash text NOT NULL
);

CREATE FUNCTION audit_log_chain() RETURNS trigger AS $$
DECLARE
    last_hash text;
BEGIN
    -- Serialise writers so two rows never claim the same predecessor.
    PERFORM pg_advisory_xact_lock(hashtext('audit_log'));
    SELECT row_hash INTO last_hash FROM audit_log ORDER BY seq DESC LIMIT 1;
    NEW.prev_hash := coalesce(last_hash, repeat('0', 64));
    NEW.row_hash := encode(digest(
        NEW.prev_hash || coalesce(NEW.case_id::text, '') || NEW.at::text || NEW.actor
            || NEW.action || NEW.payload::text,
        'sha256'), 'hex');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER audit_log_chain BEFORE INSERT ON audit_log
    FOR EACH ROW EXECUTE FUNCTION audit_log_chain();

CREATE FUNCTION audit_log_reject_change() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'audit_log is append only';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER audit_log_append_only BEFORE UPDATE OR DELETE OR TRUNCATE ON audit_log
    FOR EACH STATEMENT EXECUTE FUNCTION audit_log_reject_change();
