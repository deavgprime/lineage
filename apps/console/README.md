# Lineage console

The analyst console: sign-in through Keycloak, the case queue, file review, sign-off and the trace
of how each file was drafted.

Pages render on the server and call the API from there. The browser holds only an encrypted,
httpOnly session cookie, never a token.

```bash
docker compose up -d --build --wait api keycloak   # from the repository root
cp .env.example .env.local                         # then set SESSION_SECRET
npm ci
npm run dev
```

Open http://localhost:3000 and sign in as a test user from `infra/keycloak/lineage-realm.json`.

The API container has no model access of its own, so a case opened against it ends as failed. To
draft cases, run the API on a machine signed in to Claude Code
(`uv run uvicorn --factory lineage_api.app:create_app`), or set `LINEAGE_MODEL=api` and
`ANTHROPIC_API_KEY` for the container.

After an API change, regenerate the typed client:

```bash
uv run python -m lineage_api.openapi > openapi.json && npm run gen:api
```
