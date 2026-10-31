# Evaluation datasets

## screening.jsonl

200 labelled names for the sanctions and PEP screening eval, split into a UK pack and a UAE pack. The
release gate is recall of at least 98% on the cases that should match, reported for each pack, with
precision reported over all 200.

| Category | UK | UAE | Expected | What it checks |
| --- | --- | --- | --- | --- |
| `exact_name` | 25 | 25 | match | The primary name as listed, people and organisations |
| `latin_variant` | 15 | 15 | match | Another Latin spelling that the same record lists |
| `native_script` | 15 | 15 | match | The Cyrillic (UK) or Arabic (UAE) spelling that the record lists |
| `pep` | 15 | 15 | match | Politically exposed people linked to the UK or the UAE |
| `token_collision` | 30 shared | | no match | A given name from one listed person and a family name from another |
| `common_name` | 15 shared | | no match | Frequent given and family names in a pairing that is on no list |
| `invented_company` | 15 shared | | no match | Made-up trading names |

A case has the fields `id`, `query`, `script`, `entity_type`, `jurisdiction`, `category`, `expected`,
`expected_list` and `expected_entity_ids`. The entity IDs are OpenSanctions IDs, and a match is correct
if it returns any of them. Negative cases are checked against every name and alias in both source
lists after normalisation, so none of them is listed under that spelling.

Lists used: the UK Sanctions List for the UK pack, the UAE Local Terrorist List and the UN Security
Council list for the UAE pack, and the OpenSanctions PEP dataset filtered by country for each.
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
