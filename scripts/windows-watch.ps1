Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Windows.Forms, System.Drawing
$bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$bitmap = New-Object System.Drawing.Bitmap $bounds.Width, $bounds.Height
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$graphics.CopyFromScreen($bounds.Location, [System.Drawing.Point]::Empty, $bounds.Size)
$path = "C:\Users\steep\sts2-tas-qstar\models\screen.png"
$bitmap.Save($path, [System.Drawing.Imaging.ImageFormat]::Png)
$graphics.Dispose()
$bitmap.Dispose()
Write-Output "screen=$path"
$log = "C:\Users\steep\AppData\Roaming\SlayTheSpire2\logs\godot.log"
if (Test-Path $log) {
    Write-Output "=== last clicks ==="
    Select-String -Path $log -Pattern "Sts2TasMod (clicked|waiting)" | Select-Object -Last 8 | ForEach-Object { $_.Line }
}
$jsonl = "C:\Users\steep\sts2-tas-qstar\models\qstar-live.jsonl"
if (Test-Path $jsonl) {
    Write-Output "=== last snapshot keys ==="
    $line = Get-Content $jsonl -Tail 1
    if ($line -match '"screen_id": "([^"]+)"') { Write-Output ("screen_id=" + $Matches[1]) }
    if ($line -match '"phase": "([^"]+)"') { Write-Output ("phase=" + $Matches[1]) }
    if ($line -match '"loading": (true|false)') { Write-Output ("loading=" + $Matches[1]) }
    if ($line -match '"floor": ([0-9]+)') { Write-Output ("floor=" + $Matches[1]) }
}
Get-Process SlayTheSpire2, python -ErrorAction SilentlyContinue | Format-Table Id, ProcessName, WS
