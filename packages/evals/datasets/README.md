# Evaluation datasets

## screening.jsonl

200 labelled names for the sanctions and PEP screening eval. The release gate is recall of at least 98%
on the 140 cases that should match, with precision reported over all 200.

| Category | Cases | Expected | What it checks |
| --- | --- | --- | --- |
| `exact_name` | 60 | match | The primary name as listed, 30 people and 30 organisations |
| `latin_variant` | 30 | match | Another Latin spelling that the same record lists |
| `arabic_script` | 30 | match | The Arabic spelling that the record lists |
| `pep` | 20 | match | Politically exposed people |
| `token_collision` | 30 | no match | A given name from one listed person and a family name from another |
| `common_name` | 15 | no match | Frequent given and family names in a pairing that is on no list |
| `invented_company` | 15 | no match | Made-up trading names |

A case has the fields `id`, `query`, `script`, `entity_type`, `category`, `expected`, `expected_list`
and `expected_entity_ids`. The entity IDs are OpenSanctions IDs, and a match is correct if it returns
any of them. Negative cases are checked against every name and alias in both source lists after
normalisation, so none of them is listed under that spelling.

Positive labels come from the source records, so each label is traceable to an entity ID. Lists used:
US OFAC SDN, UN Security Council, EU Financial Sanctions Files, UK FCDO, UAE Local Terrorist List, Saudi
Arabia National Terrorism List and the Qatar sanctions list, plus the OpenSanctions PEP dataset.
`screening.meta.json` records the data version.

## Licence and attribution

The data comes from [OpenSanctions](https://www.opensanctions.org/) and is licensed CC BY-NC 4.0, which
allows non-commercial use with attribution. Files in this folder are not covered by the Apache-2.0
licence of the code. Commercial use needs a licence from OpenSanctions.

## Rebuilding

The file is fixed once reviewed. A rebuild against newer data produces different cases on purpose and
should be reviewed like any other change, because it moves the baseline.

```bash
PYTHONPATH=packages/evals python packages/evals/scripts/build_screening_dataset.py \
  --sanctions sanctions.csv --peps peps.csv --version <dataset version>
```

The inputs are `targets.simple.csv` from the `sanctions` and `peps` datasets at
`https://data.opensanctions.org/datasets/latest/`.
