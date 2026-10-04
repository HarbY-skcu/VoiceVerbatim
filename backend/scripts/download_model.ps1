# Downloads the local, offline Vosk speech-to-text model used by
# VoskStreamingTranscriptionService, and unpacks it into backend/models/.
#
# Run once per machine/deployment. The model is intentionally not committed
# to git (large binary blob); this script makes fetching it reproducible.
#
# PowerShell equivalent of download_model.sh -- both are kept in sync and
# should exist side by side so Windows users aren't required to use Git
# Bash/WSL just to run this one setup step.

$ErrorActionPreference = "Stop"

$ModelName = "vosk-model-en-us-0.22"
$ModelUrl = "https://alphacephei.com/vosk/models/$ModelName.zip"
$DestDir = Join-Path $PSScriptRoot "..\models"
$ModelDir = Join-Path $DestDir $ModelName

if (Test-Path $ModelDir) {
    Write-Host "Model already present at $ModelDir"
    exit 0
}

New-Item -ItemType Directory -Force -Path $DestDir | Out-Null

$TmpZip = Join-Path ([System.IO.Path]::GetTempPath()) "$ModelName.zip"
Write-Host "Downloading $ModelUrl ..."
Invoke-WebRequest -Uri $ModelUrl -OutFile $TmpZip

Write-Host "Unzipping into $DestDir ..."
Expand-Archive -Path $TmpZip -DestinationPath $DestDir -Force
Remove-Item -Force $TmpZip

Write-Host "Model ready at $ModelDir"
