#!/bin/bash
# Copyright 2026 The Kubernetes Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Cleanup. By default only deletes the workshop's Kubernetes resources, so
# you can keep iterating on the same cluster. Pass --full to also delete
# the GKE cluster itself.

set -eo pipefail

CLUSTER_NAME=${CLUSTER_NAME:-"agent-sandbox-workshop"}
REGION=${REGION:-"us-central1"}
NAMESPACE="agent-sandbox-workshop"

echo "==> Deleting workshop namespace (sandboxes, claims, warmpool, template)..."
kubectl delete namespace "${NAMESPACE}" --ignore-not-found
kubectl config set-context --current --namespace=default

if [[ "${1:-}" == "--full" ]]; then
  echo "==> Deleting the sandbox-router and controller..."
  DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
  kubectl delete -f "${DIR}/manifests/00-sandbox-router.yaml" --ignore-not-found
  kubectl delete -f https://github.com/kubernetes-sigs/agent-sandbox/releases/latest/download/sandbox-with-extensions.yaml --ignore-not-found

  echo "==> Deleting GKE cluster '${CLUSTER_NAME}'..."
  gcloud container clusters delete "${CLUSTER_NAME}" --region "${REGION}" --quiet
else
  echo "Cluster '${CLUSTER_NAME}' left running. Pass --full to delete it too."
fi
