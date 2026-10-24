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
# Pre-workshop setup. Run this BEFORE the session starts - cluster creation
# and image pulls eat the one resource a 45-minute workshop doesn't have:
# time. Everything after this script is the live, hands-on part.

set -eo pipefail

CLUSTER_NAME=${CLUSTER_NAME:-"agent-sandbox-workshop"}
REGION=${REGION:-"us-central1"}
NAMESPACE="agent-sandbox-workshop"

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"

if gcloud container clusters describe "${CLUSTER_NAME}" --region "${REGION}" >/dev/null 2>&1; then
  echo "==> Reusing existing GKE cluster '${CLUSTER_NAME}' in ${REGION}..."
else
  echo "==> Creating GKE Autopilot cluster '${CLUSTER_NAME}' in ${REGION}..."
  echo "    (Autopilot needs no node pool setup to get gVisor isolation - that's why we use it here.)"
  gcloud container clusters create-auto "${CLUSTER_NAME}" --region "${REGION}"
fi

gcloud container clusters get-credentials "${CLUSTER_NAME}" --region "${REGION}"

echo "==> Installing the Agent Sandbox controller (core + extensions)..."
kubectl apply -f https://github.com/kubernetes-sigs/agent-sandbox/releases/latest/download/sandbox-with-extensions.yaml
kubectl wait --for=condition=Available deployment/agent-sandbox-controller -n agent-sandbox-system --timeout=180s

echo "==> Deploying the sandbox-router (published image, no build needed)..."
kubectl apply -f "${DIR}/manifests/00-sandbox-router.yaml"
ROUTER_TAG="$(kubectl get deploy agent-sandbox-controller -n agent-sandbox-system -o jsonpath='{.spec.template.spec.containers[0].image}' | cut -d: -f2)"
kubectl -n agent-sandbox-system set image deploy/sandbox-router \
  "sandbox-router=registry.k8s.io/agent-sandbox/sandbox-router-go:${ROUTER_TAG}"
kubectl -n agent-sandbox-system rollout status deploy/sandbox-router --timeout=180s

echo "==> Creating the workshop namespace..."
kubectl apply -f "${DIR}/manifests/00-namespace.yaml"
kubectl config set-context --current --namespace="${NAMESPACE}"

echo
echo "Setup complete! Verify before starting the workshop:"
echo "  kubectl get pods -n agent-sandbox-system"
echo
echo "Next: apply the SandboxTemplate + SandboxWarmPool and run the agent:"
echo "  kubectl apply -f manifests/01-sandboxtemplate.yaml"
echo "  kubectl apply -f manifests/02-sandboxwarmpool.yaml"
echo "  python3 workshop.py seed"


