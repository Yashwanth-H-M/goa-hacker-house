$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

$tokenLine = Get-Content '.env' | Where-Object { $_ -like 'HF_TOKEN=*' } | Select-Object -First 1
if (-not $tokenLine) {
    throw 'HF_TOKEN is missing from the protected .env file.'
}
$token = $tokenLine.Substring('HF_TOKEN='.Length)
$targetRoot = Join-Path $projectRoot 'data\msmarco-xi\validation'
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
New-Item -ItemType Directory -Force -Path $targetRoot | Out-Null

$downloads = @(
    @{ File = 'kanval.parquet'; Language = 'kn'; ExpectedBytes = 482734885 },
    @{ File = 'telval.parquet'; Language = 'te'; ExpectedBytes = 474142748 }
)

foreach ($download in $downloads) {
    $destination = Join-Path $targetRoot $download.File
    $existingBytes = if (Test-Path $destination) { (Get-Item $destination).Length } else { 0 }
    if ($existingBytes -ne $download.ExpectedBytes) {
        $url = "https://huggingface.co/datasets/ai4bharat/MSMARCO-XI/resolve/main/validation/$($download.File)"
        $currentBytes = $existingBytes
        $attempt = 0
        while ($currentBytes -ne $download.ExpectedBytes -and $attempt -lt 30) {
            $attempt += 1
            Write-Output "Starting or resuming $($download.File), attempt $attempt, at $(Get-Date -Format o)"
            & curl.exe --fail --location --retry 5 --retry-delay 10 --continue-at - --header "Authorization: Bearer $token" --output $destination $url
            $curlExit = $LASTEXITCODE
            $currentBytes = if (Test-Path $destination) { (Get-Item $destination).Length } else { 0 }
            if ($currentBytes -ne $download.ExpectedBytes) {
                Write-Output "Partial transfer for $($download.File): curl exit $curlExit, $currentBytes of $($download.ExpectedBytes) bytes. Retrying."
                Start-Sleep -Seconds 8
            }
        }
        if ($currentBytes -ne $download.ExpectedBytes) {
            throw "Download failed for $($download.File) after $attempt attempts: $currentBytes of $($download.ExpectedBytes) bytes available."
        }
        Write-Output "Verified complete $($download.File)."
    } else {
        Write-Output "Verified existing complete $($download.File)."
    }

    & $python .\tools\validate_parquet.py $destination
    if ($LASTEXITCODE -ne 0) {
        throw "Parquet validation failed for $($download.File)."
    }

    Write-Output "Building $($download.Language) development index at $(Get-Date -Format o)"
    & $python -m src.ingest_multilingual --languages $download.Language --skip-existing --limit 1000 --output-root index\multilingual --chunking-strategy sentence
    if ($LASTEXITCODE -ne 0) {
        throw "Index build failed for $($download.Language) with exit code $LASTEXITCODE."
    }
}

Write-Output 'All remaining language parquet files and development indexes are present.'
