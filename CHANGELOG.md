# Changelog

All notable changes to Lineage are listed here, newest first. Each release links to its full GitHub release notes. Versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

- build(deps-dev): update hatchling requirement from >=1.32.4 to >=1.33.0 in the python-dev-tools group (#164)
- build: move both base images to digests with the fixed apt (#166)
- ci(deps): bump docker/login-action from 4.6.0 to 4.7.0 in the github-actions group across 1 directory (#162)
- docs: welcome contributions and list the steps in the README (#165)
- fix(infra): keep Terraform state in an encrypted, versioned GCS bucket (#163)
- fix(console): allow scripts by per-request nonce instead of unsafe-inline (#161)
- build: pin base images by digest and let Dependabot update them (#159)
- fix(api): refuse fixture drafting outside a test or demo environment (#158)
- fix(infra): make the API private and turn off the admin console and API docs (#157)
- fix(api): check status, draft and signer in the sign-off trigger (#156)
- fix(api): fail cases left drafting by a stopped process and allow a retry (#155)
- fix(api): limit how often a user can start paid work (#154)
- fix(api): run migrations under an advisory lock (#153)
- fix(api): require a second MLRO sign-off when a high file is lowered (#152)

## [v0.8.1] - 2026-11-03

### Maintenance

- docs: show the demo as a GIF in the README (#138)

## [v0.8.0] - 2026-11-03

### Maintenance

- docs: show the measured results in the README from the baselines (#134)
- docs: add the playbook for taking Lineage into a bank (#135)
- docs: record a demo walkthrough (#136)

## [v0.7.2] - 2026-11-03

### Bug fixes

- fix: deploy once to GCP and fix what the live run found (#129)

## [v0.7.1] - 2026-11-03

### Features

- feat(console): build the console as a container image (#120)
- feat(api): trace requests, agent steps and model calls with OpenTelemetry (#121)
- feat(infra): describe the GCP deployment in Terraform (#122)
- feat(infra): package Lineage as a Helm chart (#123)

### Bug fixes

- fix(ci): publish the Helm chart with Helm 3 (#127)

### Maintenance

- build(deps): update hatchling requirement to >=1.32.4 (#105)
- build(deps): bump the console group across 1 directory with 4 updates (#88)
- ci: allow the deps-dev scope Dependabot uses for development updates (#113)
- ci: publish the images and the Helm chart with each release (#124)
- docs: add the deployment and operations guide (#125)

## [v0.6.0] - 2026-11-02

### Features

- feat(agent): add the Presidio pass for identifiers the agent does not know (#104)
- feat(evals): measure what the Presidio pass catches (#106)
- feat(api): verify the whole audit chain and export a case's trail (#107)
- feat(ingest): load the policy corpus into pgvector (#108)
- feat(agent): answer policy questions with cited passages (#109)
- feat(console): ask policy questions (#110)
- feat(evals): measure policy retrieval and answers (#111)

### Maintenance

- docs: decide the policy corpus and local retrieval models (#103)

## [v0.5.1] - 2026-11-01

### Features

- feat(api): add the FastAPI service with health checks and settings (#74)
- feat(infra): run Keycloak locally with the lineage realm and test users (#75)
- feat(api): verify Keycloak tokens and map roles and packs to the user (#76)
- feat(api): enforce case access with Postgres row-level security (#77)
- feat(api): open cases, run the agent and serve the drafted file (#78)
- feat(api): sign off or override a file with a recorded reason (#81)
- feat(console): add the Next.js console with Keycloak sign-in (#82)
- feat(console): show the case queue and open new cases (#83)
- feat(console): review a drafted file with its citations (#86)
- feat(console): sign off or override from the file view (#89)
- feat(console): show the trace of how a file was drafted (#90)

### Bug fixes

- fix(ci): skip the Keycloak tests when no Keycloak is configured (#93)

### Maintenance

- docs: decide the access model for cases and sign-off (#73)
- ci: scan for secrets, vulnerable dependencies and image issues (#80)
- ci: hold the console's TypeScript and ESLint majors in Dependabot (#87)
- test(console): run end-to-end tests of the console and API (#91)

## [v0.4.0] - 2026-11-01

### Features

- feat(agent): set a minimum rating from strong screening matches (#51)
- feat(evals): add screening cases with spellings that appear on no list (#52)
- feat(evals): run the screening eval in CI against pinned data (#53)
- feat(evals): check citations and judge faithfulness over 40 drafted files (#55)
- feat(evals): run the safety cases through the agent (#56)
- feat(evals): report time and cost per drafted file (#57)
- feat(evals): post eval scores next to the baselines on pull requests (#58)

### Maintenance

- ci(evals): run the ownership eval in every pull request (#54)

## [v0.3.0] - 2026-11-01

### Features

- feat(infra): run postgres with pgvector for development and tests (#34)
- feat(ingest): load opensanctions records for the uk and uae packs (#35)
- feat(ingest): add a companies house client with caching and rate limits (#36)
- feat(ingest): add gleif lei and parent lookups (#37)
- feat(agent): screen names against the loaded sanctions and pep records (#38)
- feat(agent): add the registry tool that traces ownership chains (#39)
- feat(agent): draft a cited file from the command line (#40)
- feat(agent): draft through claude code on the signed-in subscription (#41)

### Maintenance

- docs: decide where redaction happens when names drive screening (#33)

## [v0.2.0] - 2026-10-31

### Features

- feat(evals): add 200 labelled names for sanctions and pep screening (#18)
- feat(evals): split the screening set into uk and uae packs (#21)
- feat(evals): add ownership ground truth for 30 uk companies (#22)
- feat(evals): add 40 safety cases in english and arabic (#23)

### Maintenance

- docs: serve a bank operating in the UK and the UAE (#19)
- docs: trim the security note in the readme (#17)

## [v0.1.0] - 2026-10-31

### Bug fixes

- fix(ci): release tag check no longer needs credentials (#15)

### Maintenance

- ci: publish github releases from tags and group notes by label (#10)
- ci: disable dependency caching in the release workflow (#13)
- docs: remove internal style rules from public templates and guides (#14)
- docs: add security and compliance posture (#11)
- chore(release): bring main up to date with develop (#7)
- chore(release): v0.1.0 (#16)

### Other changes

- docs: explain what Lineage is for and how its architecture works (#8)
- ci: harden workflows and add secret and workflow scanning (#9)

[Unreleased]: https://github.com/deavgprime/lineage/compare/v0.8.1...develop
[v0.8.1]: https://github.com/deavgprime/lineage/releases/tag/v0.8.1
[v0.8.0]: https://github.com/deavgprime/lineage/releases/tag/v0.8.0
[v0.7.2]: https://github.com/deavgprime/lineage/releases/tag/v0.7.2
[v0.7.1]: https://github.com/deavgprime/lineage/releases/tag/v0.7.1
[v0.6.0]: https://github.com/deavgprime/lineage/releases/tag/v0.6.0
[v0.5.1]: https://github.com/deavgprime/lineage/releases/tag/v0.5.1
[v0.4.0]: https://github.com/deavgprime/lineage/releases/tag/v0.4.0
[v0.3.0]: https://github.com/deavgprime/lineage/releases/tag/v0.3.0
[v0.2.0]: https://github.com/deavgprime/lineage/releases/tag/v0.2.0
[v0.1.0]: https://github.com/deavgprime/lineage/releases/tag/v0.1.0
