Param(
    [switch]$NoInstall
)

Write-Host "Starting Sanjaya AI backend and frontend (Windows)..."

Push-Location "backend"
if (-not $NoInstall) {
    Write-Host "Installing backend dependencies..."
    python -m pip install -r requirements.txt
}
if (-not (Test-Path ".env") -and (Test-Path ".env.example")) {
    Copy-Item ".env.example" ".env"
}
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd `"$PWD`"; uvicorn app.main:app --reload --port 8000"
Pop-Location

Start-Sleep -Seconds 3

Push-Location "frontend"
if (-not $NoInstall) {
    Write-Host "Installing frontend dependencies..."
    npm install
}
if (-not (Test-Path ".env.local") -and (Test-Path ".env.local.example")) {
    Copy-Item ".env.local.example" ".env.local"
}
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd `"$PWD`"; npm run dev"
Pop-Location

Write-Host "Backend on http://127.0.0.1:8000 and frontend on http://127.0.0.1:3000"

