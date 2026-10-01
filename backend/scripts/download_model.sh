#!/usr/bin/env bash
# Downloads the local, offline Vosk speech-to-text model used by
# VoskStreamingTranscriptionService, and unpacks it into backend/models/.
#
# Run once per machine/deployment. The model is intentionally not committed
# to git (large binary blob); this script makes fetching it reproducible.
set -euo pipefail

MODEL_NAME="vosk-model-en-us-0.22"
MODEL_URL="https://alphacephei.com/vosk/models/${MODEL_NAME}.zip"
DEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/models"

mkdir -p "${DEST_DIR}"

if [ -d "${DEST_DIR}/${MODEL_NAME}" ]; then
  echo "Model already present at ${DEST_DIR}/${MODEL_NAME}"
  exit 0
fi

TMP_ZIP="$(mktemp)"
echo "Downloading ${MODEL_URL} ..."
curl -L "${MODEL_URL}" -o "${TMP_ZIP}"

echo "Unzipping into ${DEST_DIR} ..."
unzip -q "${TMP_ZIP}" -d "${DEST_DIR}"
rm -f "${TMP_ZIP}"

echo "Model ready at ${DEST_DIR}/${MODEL_NAME}"
