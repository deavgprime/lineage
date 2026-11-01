# 0001: Redaction when names drive screening

Status: accepted, 31 October 2026. Closes the first open risk in [the decision log](../decisions.md).

## Problem

Screening and ownership tracing work on names: the name of the company, its officers and its owners.
The bank also requires that personal data never reaches an external model. Redacting everything
before the agent runs would make the tools useless, and redacting nothing would break the constraint.

## Decision

Redaction happens at one point only: the boundary between the agent core and any model outside the
bank. Everything before that point runs on real data inside the bank's trust boundary.

| Component | Sees real personal data | Why |
| --- | --- | --- |
| Screening tool | Yes | Matches names against sanctions and PEP lists loaded into the bank's own database. No name leaves the bank. |
| Registry and LEI tools | Company numbers and names only | Queries to Companies House and GLEIF use public company identifiers. Results with individuals are kept as register links. |
| Agent core | Yes | Holds tool results and builds model requests. |
| Redactor | Yes | Replaces personal data with placeholders and keeps the mapping. |
| External model | No | Receives placeholders only. |
| Self-hosted model | Configurable | Redaction stays on by default, and a pack can turn it off when the model runs inside the bank. |
| Audit log | Hashes | Stores the hash of each redacted prompt and of the mapping, never the mapping itself. |

### How the redactor works

1. **Known entities first.** The agent already knows the people in a case from tool results:
   officers, owners, screening hits. Each one gets a typed, stable placeholder for the life of the
   case, such as `[PERSON_3]`, matched on the normalised name and on every alias in the source
   records. This works the same way for Latin, Arabic and Cyrillic spellings, which a statistical
   recogniser handles poorly.
2. **Presidio second.** A Presidio pass catches what the tools did not supply: addresses, passport and
   national ID numbers including Emirates ID and UK passport formats, email addresses, phone numbers
   and account numbers. Each gets a placeholder of its type.
3. **Companies stay named.** Legal entity names are public and needed for reasoning about ownership,
   so they are not redacted. A sole trader trading under their own name is treated as a person.
4. **Mapping back.** Model output refers to placeholders. The agent replaces them with real values
   only after the response returns, before the analyst sees the file.
5. **Citations are checked after mapping back.** The citation check compares each quote, with real
   values restored, against the source record it cites.

### Failure handling

- If the model returns a placeholder that was not in the request, the response is rejected.
- If the redactor finds personal data after both passes have run, for example a name in a
  free-text field that matches a known entity in an unexpected spelling, the request is not sent.
- The mapping lives in memory for the duration of a case run and is stored encrypted with the case,
  so a reviewer can trace a placeholder to a person.

## Consequences

- The safety eval's personal data cases test the whole path: planted values must not appear in any
  request to an external model, which the harness checks on the recorded requests.
- Placeholders cost some quality on name-heavy reasoning, such as judging whether two spellings refer
  to the same person. That judgement is made by the screening tool on real data, not by the model.
- Presidio's recognisers need tuning for Arabic text. The known-entity pass carries most of the load,
  and the eval will show how much the Presidio pass adds.
