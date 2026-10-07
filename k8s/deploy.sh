#!/usr/bin/env bash
# Deploys the Pet Adoption Portal to whatever Kubernetes cluster kubectl currently points at
# (minikube, kind, Docker Desktop, k3s, EKS ...).
set -euo pipefail
cd "$(dirname "$0")/.."

# 1. Namespace first, because the schema ConfigMap lives inside it
kubectl apply -f k8s/namespace.yaml

# 2. Turn the SQL file into a ConfigMap that the MySQL pod mounts and runs on first start
kubectl create configmap mysql-schema --from-file=schema.sql=app/backend/schema.sql \
  -n pet-portal --dry-run=client -o yaml | kubectl apply -f -

# 3. Everything else (config, secret, database, backend, frontend)
kubectl apply -k k8s/

# 4. Wait until every Deployment is fully rolled out
for d in mysql backend frontend; do
  kubectl rollout status deployment/$d -n pet-portal --timeout=300s
done

echo
echo "Deployed. Open the site with one of:"
echo "  kubectl port-forward -n pet-portal svc/frontend 8080:80   ->  http://localhost:8080"
echo "  minikube service frontend -n pet-portal --url"
