$ErrorActionPreference = 'Stop'
$taskToolDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
$taskPythonCandidates = @()
if ($env:ARCHIVE_MOE_PYTHON) { $taskPythonCandidates += $env:ARCHIVE_MOE_PYTHON }
$taskPythonCandidates += @(Get-Command python,python3 -CommandType Application -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source)
if (Get-Command py -CommandType Application -ErrorAction SilentlyContinue) {
    try {
        $taskLauncherPython = & py -3 -c 'import sys; print(sys.executable)' 2>$null
        if ($LASTEXITCODE -eq 0 -and $taskLauncherPython) { $taskPythonCandidates += $taskLauncherPython.Trim() }
    } catch {}
}
$taskPythonCandidates = @($taskPythonCandidates | Select-Object -Unique)
foreach ($taskPythonExecutable in $taskPythonCandidates) {
    if (-not (Test-Path -LiteralPath $taskPythonExecutable -PathType Leaf)) { continue }
    if ($taskPythonExecutable -like '*\WindowsApps\*') { continue }
    try {
        & $taskPythonExecutable -c 'import PIL,numpy,tkinter' 2>$null
        $taskDependencyCheckPassed = $LASTEXITCODE -eq 0
    } catch { $taskDependencyCheckPassed = $false }
    if ($taskDependencyCheckPassed) {
        $taskPythonWindowless = Join-Path (Split-Path -Parent $taskPythonExecutable) 'pythonw.exe'
        if (Test-Path -LiteralPath $taskPythonWindowless -PathType Leaf) {
            # This is the user-invoked interactive window, not a background helper.
            Start-Process -FilePath $taskPythonWindowless -ArgumentList ('"' + (Join-Path $taskToolDirectory 'icon_customizer.py') + '"') -WorkingDirectory $taskToolDirectory -WindowStyle Normal
        } else {
            & $taskPythonExecutable (Join-Path $taskToolDirectory 'icon_customizer.py')
        }
        exit 0
    }
}
Write-Host 'No Python installation with Pillow, NumPy and Tkinter was found.'
Write-Host 'Run in the project directory: python -m pip install -r requirements.txt'
Read-Host 'Press Enter to close'
exit 1
