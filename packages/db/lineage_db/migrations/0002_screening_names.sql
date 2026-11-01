-- One row per name or alias of a screening record, normalised for matching.

CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE screening_names (
    record_id text NOT NULL REFERENCES source_records (id) ON DELETE CASCADE,
    name text NOT NULL,
    name_norm text NOT NULL,
    name_tokens text NOT NULL,
    kind text NOT NULL CHECK (kind IN ('sanctions', 'pep')),
    jurisdictions text[] NOT NULL,
    PRIMARY KEY (record_id, name)
);
CREATE INDEX screening_names_norm ON screening_names (name_norm);
CREATE INDEX screening_names_tokens ON screening_names (name_tokens);
CREATE INDEX screening_names_trgm ON screening_names USING gin (name_norm gin_trgm_ops);
CREATE INDEX screening_names_packs ON screening_names USING gin (jurisdictions);
