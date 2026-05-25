#!/usr/bin/env bash
set -euo pipefail

ENVIRONMENT="prod"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --env)
      ENVIRONMENT="$2"
      shift 2
      ;;
    *)
      echo "Unknown argument: $1"
      exit 1
      ;;
  esac
done

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TF_DIR="$ROOT_DIR/infra/terraform"

echo "Deploying AutoApply infrastructure for environment: $ENVIRONMENT"
terraform -chdir="$TF_DIR" init
terraform -chdir="$TF_DIR" apply -var="environment=$ENVIRONMENT"

