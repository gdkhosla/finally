# Start the FinAlly container. Pass -Build to force a fresh image build.
param(
    [switch]$Build
)

$Image     = "finally"
$Container = "finally"
$Volume    = "finally-data"
$Port      = "8000"
$Url       = "http://localhost:$Port"
$Root      = Split-Path -Parent $PSScriptRoot

# Build if image doesn't exist or -Build was requested
$imageExists = docker image inspect $Image 2>$null
if ($Build -or -not $imageExists) {
    Write-Host "Building image '$Image'..."
    docker build -t $Image $Root
}

# Remove any existing container with the same name
$containerExists = docker container inspect $Container 2>$null
if ($containerExists) {
    Write-Host "Removing existing container '$Container'..."
    docker rm -f $Container | Out-Null
}

Write-Host "Starting container '$Container'..."
docker run -d `
    --name $Container `
    -v "${Volume}:/app/db" `
    -p "${Port}:8000" `
    --env-file "$Root\.env" `
    $Image

Write-Host "FinAlly is running at $Url"

# Open browser
Start-Process $Url
