-- The policy corpus for each pack (decision 0004): documents, and their sections with an embedding
-- for vector search and a text index for keyword search.

CREATE TABLE policy_documents (
    id text PRIMARY KEY,
    pack text NOT NULL CHECK (pack IN ('uk', 'uae')),
    title text NOT NULL,
    source text NOT NULL,
    version text NOT NULL,
    licence text NOT NULL,
    url text,
    loaded_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE policy_sections (
    id text PRIMARY KEY,
    document_id text NOT NULL REFERENCES policy_documents (id) ON DELETE CASCADE,
    pack text NOT NULL CHECK (pack IN ('uk', 'uae')),
    ref text NOT NULL,
    heading text NOT NULL,
    text text NOT NULL,
    position integer NOT NULL,
    checksum text NOT NULL,
    embedding vector(384) NOT NULL,
    search tsvector GENERATED ALWAYS AS (
        setweight(to_tsvector('english', ref || ' ' || heading), 'A')
            || setweight(to_tsvector('english', text), 'B')
    ) STORED
);
CREATE INDEX policy_sections_pack ON policy_sections (pack);
CREATE INDEX policy_sections_embedding ON policy_sections USING hnsw (embedding vector_cosine_ops);
CREATE INDEX policy_sections_search ON policy_sections USING gin (search);

-- Every signed-in user reads the corpus of their own packs and nothing else.
ALTER TABLE policy_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE policy_sections ENABLE ROW LEVEL SECURITY;
CREATE POLICY policy_documents_read ON policy_documents FOR SELECT TO lineage_app
    USING (pack = ANY (coalesce(lineage_user_packs(), '{}')));
CREATE POLICY policy_sections_read ON policy_sections FOR SELECT TO lineage_app
    USING (pack = ANY (coalesce(lineage_user_packs(), '{}')));
GRANT SELECT ON policy_documents, policy_sections TO lineage_app;
