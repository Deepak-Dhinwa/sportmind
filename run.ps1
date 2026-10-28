$root = $PSScriptRoot
Write-Host "Backend  http://localhost:8000"
Write-Host "Frontend http://localhost:5173"
Write-Host "Neo4j and Weaviate need to be running already."
Start-Process powershell -ArgumentList "-NoExit","-Command","Set-Location '$root'; & '.\venv\Scripts\python.exe' -m backend.main"
Start-Process powershell -ArgumentList "-NoExit","-Command","Set-Location '$root\frontend'; npm run dev"
