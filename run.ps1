$root = $PSScriptRoot
Write-Host "Backend  http://localhost:8000"
Write-Host "Frontend http://localhost:5173"
Write-Host "This script does not start Neo4j or Weaviate."
Write-Host "With Docker Desktop open: docker start neo4j weaviate"
Start-Process powershell -ArgumentList "-NoExit","-Command","Set-Location '$root'; & '.\venv\Scripts\python.exe' -m backend.main"
Start-Process powershell -ArgumentList "-NoExit","-Command","Set-Location '$root\frontend'; npm run dev"
