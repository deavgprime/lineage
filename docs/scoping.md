# Scoping

## In scope
- Input: company name or registration number.
- Output: resolved entity, ownership chain to UBOs, sanctions and PEP hits for every person and entity in the chain, adverse-media notes, risk rating with reasons. Every claim cites a source record.
- Analyst approve or override, with a recorded reason. Hash-chained audit log of every tool call, model call and decision.
- Data: OpenSanctions, UK Companies House, GLEIF, loaded into Postgres by ingestion jobs.
- Policy Q&A over KYC policy, FCA and JMLSG guidance and CBUAE guidance, with citations.
- Jurisdiction as configuration: a UK pack and a UAE pack, each with its own lists, registry source and policy corpus.
- Analyst console (queue, file review, trace viewer) and an MCP server over the same tools.

## Out of scope
- Real customer data, real onboarding decisions, transaction monitoring.
- Ownership data outside the three sources. There is no open UAE registry, so UAE cases rely on GLEIF and analyst-supplied documents.
- GPU training, model fine-tuning.
- People leadership, customer-site travel (shown in interviews, not in code).

## Assumptions
- The customer is a bank operating in the UK and the UAE, sponsored by its MLRO.
- Sanctions and PEP matching uses the OpenSanctions dataset as the only list.
- Adverse media comes from a small hand-built corpus plus fetched text treated as untrusted data.

## Success criteria
See the release gates in [brief.md](brief.md). Each eval case runs 8 times.

## First-week deliverables (2 to 8 Nov)
- [ ] Brief and this scoping doc (done once reviewed)
- [ ] 200 labelled names, split into UK and UAE packs, with Cyrillic, Arabic and Latin variants
- [ ] 30 UK companies with known controlling-person chains
- [ ] CI runs tests
