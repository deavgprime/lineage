#!/usr/bin/env bash
# Install the chart on a fresh kind cluster and check it: migrations run, both deployments become
# ready, the API is healthy, and network policy lets the console reach the API but nothing else.
#   tests/helm/kind-test.sh        (needs docker, kind, kubectl and helm)
set -euo pipefail
cd "$(dirname "$0")/../.."
CLUSTER=lineage-chart
trap 'kind delete cluster --name "$CLUSTER" >/dev/null 2>&1 || true' EXIT

docker build -q -f apps/api/Dockerfile -t lineage/api:ci . >/dev/null
docker build -q -t lineage/console:ci apps/console >/dev/null
kind create cluster --name "$CLUSTER" --wait 120s >/dev/null
kind load docker-image --name "$CLUSTER" lineage/api:ci lineage/console:ci >/dev/null

kubectl apply -f tests/helm/postgres.yaml >/dev/null
kubectl rollout status deployment/postgres --timeout=180s >/dev/null
helm install t infra/helm/lineage -f infra/helm/lineage/ci-values.yaml --wait --timeout 6m >/dev/null
echo "installed; migrations ran before the pods started"

kubectl rollout status deployment/t-api --timeout=60s
kubectl rollout status deployment/t-console --timeout=60s
kubectl exec deploy/t-console -- node -e \
  'fetch("http://t-api:8000/health/ready").then(r=>r.text()).then(t=>{console.log("console -> api:",t)})'

# Any other pod is refused by the network policy.
if kubectl run probe --rm -i --restart=Never --image=lineage/console:ci --image-pull-policy=Never \
     --command -- node -e 'fetch("http://t-api:8000/health/live",{signal:AbortSignal.timeout(5000)}).then(()=>process.exit(0)).catch(()=>process.exit(3))' \
     >/dev/null 2>&1; then
  echo "FAIL: a pod outside the release reached the API" >&2
  exit 1
fi
echo "other pod -> api: refused"
