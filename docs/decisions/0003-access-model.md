# 0003: Who can see and sign off a case

Status: accepted, 2 November 2026. Closes #60.

## Problem

The agent drafts files, but a person decides. Before the API and console are built, the roles, what
each can see, and who can make a file final need to be fixed, so the database, the API and the
console all enforce the same rules.

## Decision

Users sign in through Keycloak. Each user has one role and one or more jurisdiction packs.

| Role | Sees | Can do |
| --- | --- | --- |
| Analyst | Cases assigned to them | Open a case, review the draft, clear alerts, sign off or override the rating with a reason |
| MLRO | Every case in their packs | Everything an analyst can, on any case in their packs, and the second sign-off on high-rated files |
| Auditor | Every case in their packs, read only | Read files and the audit log, verify the hash chain. Cannot change anything |

Sign-off rules:

1. Only the assigned analyst, or an MLRO in the same pack, can sign off a file.
2. Every weak screening alert must be cleared with a note before sign-off (decision 0002).
3. Changing the drafted rating is an override and needs a written reason.
4. A file needs a second sign-off by an MLRO who is not the first signer when it was drafted high,
   a strong screening match set its minimum rating to high, it is signed off as high, or the first
   signer lowered the rating. Until then it stays in review. Lowering a rating is the riskier
   direction, so it is never one person's decision (changed 3 November 2026, #140: before, only the
   final rating counted, so one analyst could take a high file down to low alone).
5. Only the sign-off path can set a case to final. The agent cannot, and the database rejects any
   other change to final.

Access is enforced twice: the API checks every request, and Postgres row-level security applies the
same rules to every query, using the user and role the API sets for the transaction. Either layer on
its own stops one analyst reading another's case.

## Why

- Need to know: customer due diligence files hold personal data, and UK GDPR and the UAE data
  protection law both expect access limited to people who need it.
- Four eyes on high risk: the FCA and the CBUAE expect senior approval before taking on high-risk
  customers, and the MLRO is the accountable person for financial crime under SM&CR.
- Separate packs: UK and UAE teams work under different rules and may keep data in different
  regions, so a user only reaches the packs they are assigned.
- Two layers: an API bug or a direct database query should not be enough to leak a case.

## Consequences

- Every case has an assigned analyst from the moment it is opened.
- The audit log records every sign-off, override, alert decision and reason with the user's id.
- Assignment and reassignment by an MLRO are left for later; until then the analyst who opens a case
  is assigned to it.
