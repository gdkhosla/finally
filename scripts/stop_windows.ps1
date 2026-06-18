# Stop and remove the FinAlly container. The data volume is preserved.

$Container = "finally"

$containerExists = docker container inspect $Container 2>$null
if ($containerExists) {
    Write-Host "Stopping container '$Container'..."
    docker rm -f $Container | Out-Null
    Write-Host "Container stopped. Data volume 'finally-data' is intact."
} else {
    Write-Host "Container '$Container' is not running."
}
