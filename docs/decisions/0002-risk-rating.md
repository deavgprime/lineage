# 0002: How screening candidates affect the risk rating

Status: accepted, 1 November 2026. Closes #43.

## Problem

Every sanctions or PEP candidate raised the rating to at least medium. Screening by name produces
many weak candidates: Tesco Stores rated medium because Tesco Holdings Limited came close to USM
Holdings Limited at a trigram score of 0.63. A rating that moves on unreviewed fuzzy matches tells the
analyst nothing, and it trains them to ignore it.

## Decision

The code, not the model, sets a minimum rating from the strength of each candidate.

| Candidate | Strength | Effect |
| --- | --- | --- |
| Same name after normalising, in any word order, on a sanctions list | Strong | Minimum rating high |
| Same name after normalising, in any word order, on a PEP list | Strong | Minimum rating medium |
| Any other candidate above the screening threshold | Weak | No change to the rating. It is an alert the analyst must clear before sign-off |

The model receives the minimum with the evidence. A draft rated below it goes back for another
attempt with the reason, in the same loop as a failed citation. Weak candidates are returned as
alerts on the result so the console can require a decision on each.

## Why

- Banks separate alert review from risk rating. A name alert is a question for an analyst, and the
  rating follows the answer.
- A strong match on a sanctions list must never produce a low rating, whatever the model writes, so
  the floor is enforced in code.
- A PEP is a reason for enhanced due diligence rather than a prohibition, so a strong PEP match sets
  medium, not high.

## Consequences

- Tesco Stores now rates on its facts, with the USM Holdings candidate listed as an alert.
- Strength uses only the screening rule. A later change may also weigh date of birth and country
  when the records carry them.
