# Demo walkthrough

[lineage-walkthrough.webm](lineage-walkthrough.webm) is a 50-second recording of the full flow in the
console. GitHub does not play videos kept in a repository, so the README shows
[lineage-walkthrough.gif](lineage-walkthrough.gif), made from the same recording at one and a half
times speed.

![The walkthrough](lineage-walkthrough.gif)

The steps:

1. An analyst signs in through Keycloak and opens a case for a UK company.
2. The drafted file opens. A claim's source is opened, with the quoted passage highlighted in the
   register record.
3. The weak screening alert is cleared with a note, and the file is signed off.
4. The trace shows every step, and that the audit rows verify against the hash chain.
5. A high-rated case is signed off by the analyst and waits for an MLRO.
6. A different MLRO signs in and gives the second sign-off.
7. A policy question is answered from the bank's policy, with its source passage.

It runs against the local stack, with the API drafting from fixtures, so the drafted text is canned
while the console, sign-in, sign-off rules, audit chain and policy search are the real ones. The same
flow ran against a live GCP deployment, recorded with screenshots in [deployment](../deployment/README.md).

## Recording it again

```bash
docker compose -f compose.yaml -f compose.e2e.yaml up -d --build --wait db keycloak api console
uv run python -m lineage_ingest.policy --no-legislation --flat-embeddings
cd apps/console && npx playwright test -c demo
cp demo/output/*/video.webm ../../docs/demo/lineage-walkthrough.webm
mkdir -p /tmp/frames && ffmpeg -i ../../docs/demo/lineage-walkthrough.webm -r 4 /tmp/frames/%04d.png
cd ../.. && uv run python scripts/demo_gif.py /tmp/frames docs/demo/lineage-walkthrough.gif
```

The script is `apps/console/demo/walkthrough.spec.ts`.
