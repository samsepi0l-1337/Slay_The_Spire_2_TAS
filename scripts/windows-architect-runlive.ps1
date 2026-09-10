Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$env:PATH = "C:\Program Files\dotnet;C:\Users\steep\.local\bin;" + $env:PATH
Set-Location "C:\Users\steep\sts2-tas-qstar"
$env:PYTHONPATH = "src"
uv run --extra dev python -m sts2_tas.cli run-live `
    --transport pipe:sts2-tas `
    --model models\qstar-live.json `
    --output models\qstar-live.jsonl `
    --search-depth 1 `
    --max-steps 1000000 `
    --until-clear `
    --command-delay 0.25 `
    --execute
