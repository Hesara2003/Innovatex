<#
Quick dev start for Windows (PowerShell): launches demo server and reads a few events.

Usage: .\scripts\dev_start.ps1
#>

$host = '127.0.0.1'
$port = 9999

Write-Host "Starting demo server on $host:$port"
Start-Process -NoNewWindow -FilePath python -ArgumentList 'scripts/demo_server.py', $host, $port, '200'
Start-Sleep -Seconds 1

Write-Host "Reading 10 events from the demo server using Python script"
python - <<'PY'
from src.io.stream_reader import read_stream
for i, obj in enumerate(read_stream('127.0.0.1', 9999, limit=10, reconnect=False)):
    print(i, obj)
PY

Write-Host "Done."
