# 0004: What policy questions are answered from, and how passages are found

Status: accepted, 2 November 2026. Closes #95.

## Problem

Analysts ask policy questions, such as when a beneficial owner must be verified or when enhanced due
diligence applies, and the answer has to cite the text it rests on. That needs a corpus each pack can
store and quote, and a way to find the right passages. Decision 5 named Cohere Rerank, but the
project has no Cohere key, the same way it has no Anthropic API key.

## Decision

### Corpus

A source goes in the corpus only if its terms allow storing and quoting it. Everything else is cited
by name and reference, never stored.

| Source | Pack | Terms | In the corpus |
| --- | --- | --- | --- |
| The bank's UK KYC policy, written for this project | UK | Apache-2.0, this repository | Yes |
| The bank's UAE KYC policy, written for this project | UAE | Apache-2.0, this repository | Yes |
| The Money Laundering, Terrorist Financing and Transfer of Funds (Information on the Payer) Regulations 2017 (SI 2017/692), from legislation.gov.uk | UK | Crown copyright, Open Government Licence v3.0, with attribution | Yes, the parts on customer due diligence, beneficial ownership, PEPs, enhanced due diligence and record keeping |
| FCA Handbook and Financial Crime Guide | UK | Reproduction needs an FCA licence | No. The bank's policy refers to it by section |
| JMLSG guidance | UK | JMLSG copyright | No. Referred to by part and paragraph |
| CBUAE Rulebook and AML/CFT guidance | UAE | No reuse terms published | No. The bank's UAE policy refers to it by section |
| UAE Federal Decree-Law and Cabinet Decision on AML/CFT | UAE | No reuse terms published | No. Referred to by article |

The two bank policies say in their own words what the bank requires and point to the regulation each
rule comes from. They are the main corpus, as they would be in a real bank, where analysts work from
the bank's procedures rather than the raw regulation.

### Finding passages

- Documents are split into sections that keep their heading and paragraph number, so a citation names
  a place a person can find.
- Retrieval combines vector search in pgvector with Postgres full-text search, within the user's pack.
- Embeddings: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (Apache-2.0, 384
  dimensions), so Arabic questions reach English passages.
- Reranking: `BAAI/bge-reranker-v2-m3` in its int8 build (Apache-2.0, multilingual), in place of
  Cohere Rerank.
- Both run locally on CPU through `fastembed`, with its version pinned in the lock file. Model files
  are downloaded once into a cache, and CI caches them between runs.
- Claude Opus 5.5 at medium effort writes the answer from the reranked passages only, and every
  statement is citation-checked the same way as a drafted file.

## Why

- A bank can only put into a retrieval system what it has the right to copy. Recording the terms per
  source keeps the corpus defensible, and the same table is the starting point for a real bank's
  licences.
- Local models keep policy text and questions inside the bank's environment and need no extra
  supplier contract. At a few hundred passages, CPU inference is fast enough.
- Keyword search catches exact terms such as regulation numbers that embeddings blur. Embeddings catch
  paraphrase and the other language.

## Consequences

- The bank policies need maintaining like any procedure document. They carry a version and an owner.
- A bank that licenses JMLSG, the FCA Handbook or the CBUAE Rulebook can add them as new sources
  without changing the design.
- Decision 5 changes from Cohere Rerank to a local reranker.
