# Security policy

## Supported versions

Lineage has no stable release yet. Only the latest commit on `main` and `develop` receives fixes.

## Reporting a vulnerability

While the repository is private, tell the owner directly. Once it is public, use GitHub private
vulnerability reporting: open the **Security** tab of this repository and choose
**Report a vulnerability**. Please do not open a public issue.

Include what you found, how to reproduce it and what you think the impact is. You will get a reply
within 5 working days. Confirmed issues are fixed on a `hotfix/*` branch and disclosed in the release
notes once a fix is available.

The controls and standards the project follows are in [docs/security.md](docs/security.md).

## Scope

In scope: authentication and case access, the audit log, personal data handling and redaction, prompt
injection that changes agent behaviour, and secrets in the repository.

Out of scope: findings that need a compromised host, and the third-party services Lineage calls
(OpenSanctions, Companies House, GLEIF and the model providers).

## Handling of data

The project uses only public records and invented people in tests and demos. No real customer data
belongs in this repository. If you find some, report it as a vulnerability.
