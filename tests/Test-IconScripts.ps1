#Requires -Version 5.1
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$root = Split-Path -Parent $PSScriptRoot
Import-Module (Join-Path $root '工具\IconRegistry.psm1') -Force
function Assert-True { param([bool]$Condition, [string]$Message); if (-not $Condition) { throw $Message } }
$plan = @(Get-ArchiveIconPlan -PackRoot $root -Formats @('7z'))
foreach ($target in $plan) { Assert-True ($target.Format -eq '7Z') 'Format filtering returned an unexpected icon.' }
$id = [Guid]::NewGuid().ToString('N')
$class = 'Software\Classes\7-Zip.ArchiveMoeTest' + $id
$class2 = 'Software\Classes\7-Zip.ArchiveMoeTest' + $id + 'Second'
$subKey = $class + '\DefaultIcon'
$subKey2 = $class2 + '\DefaultIcon'
$absent = Get-ArchiveDefaultSnapshot $subKey
$absent2 = Get-ArchiveDefaultSnapshot $subKey2
Assert-True (-not $absent.KeyExisted) 'Temporary test class unexpectedly exists.'
$temporary = Join-Path ([IO.Path]::GetTempPath()) ('archive-moe-tests-' + $id)
[IO.Directory]::CreateDirectory($temporary) | Out-Null
$backupPath = Join-Path $temporary 'backup.json'
$foreignPath = Join-Path $temporary 'foreign.json'
try {
    Set-ArchiveDefaultIcon $subKey 'test.ico,0'
    Assert-True ((Get-ArchiveDefaultSnapshot $subKey).Value -eq 'test.ico,0') 'Icon write failed.'
    Restore-ArchiveDefaultSnapshot $absent
    Assert-True (-not (Get-ArchiveDefaultSnapshot $subKey).KeyExisted) 'Absent key was not restored.'

    $key = [Microsoft.Win32.Registry]::CurrentUser.CreateSubKey($subKey)
    try {
        $key.SetValue('', '%SystemRoot%\test.dll,4', [Microsoft.Win32.RegistryValueKind]::ExpandString)
        $key.SetValue('Keep', 'untouched')
    } finally { $key.Dispose() }
    $original = Get-ArchiveDefaultSnapshot $subKey
    Set-ArchiveDefaultIcon $subKey 'replacement.ico,0'
    Restore-ArchiveDefaultSnapshot $original
    $restored = Get-ArchiveDefaultSnapshot $subKey
    Assert-True ($restored.Kind -eq 'ExpandString' -and $restored.Value -eq '%SystemRoot%\test.dll,4') 'Value kind or unexpanded value was lost.'

    Merge-ArchiveOriginalBackup -Path $backupPath -NewEntries @($original)
    Set-ArchiveDefaultIcon $subKey 'changed-again.ico,0'
    Merge-ArchiveOriginalBackup -Path $backupPath -NewEntries @((Get-ArchiveDefaultSnapshot $subKey), $absent2)
    $saved = Read-ArchiveBackup $backupPath
    Assert-True (@($saved.Entries).Count -eq 2) 'New formats were not merged into the original backup.'
    Assert-True ($saved.Entries[0].Value -eq '%SystemRoot%\test.dll,4') 'Repeated application overwrote the first backup.'
    $saved.UserSid = 'invalid-user'
    Write-ArchiveBackup $saved $foreignPath
    $rejected = $false
    try { Read-ArchiveBackup $foreignPath | Out-Null } catch { $rejected = $true }
    Assert-True $rejected 'Backup from a different user was accepted.'

    $rejected = $false
    try { Set-ArchiveDefaultIcon 'Software\Microsoft\Windows\Run\DefaultIcon' 'bad.ico,0' } catch { $rejected = $true }
    Assert-True $rejected 'Registry path guard did not reject an unrelated target.'

    # Restoring a formerly absent override must preserve unrelated data added later.
    $child = [Microsoft.Win32.Registry]::CurrentUser.CreateSubKey($subKey + '\KeepChild')
    $child.Dispose()
    Restore-ArchiveDefaultSnapshot $absent
    $key = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey($subKey)
    try {
        Assert-True ($key.GetValue('Keep') -eq 'untouched') 'Unrelated named value was removed.'
        Assert-True ($key.GetSubKeyNames() -contains 'KeepChild') 'Unrelated child key was removed.'
        Assert-True (-not ($key.GetValueNames() -contains '')) 'Default value was not removed.'
    } finally { $key.Dispose() }
    Write-Host 'Registry write/restore, original-backup merge, user validation and path guards passed.'
} finally {
    # Only these fresh GUID-named test classes are ever cleaned up.
    foreach ($testKey in @($subKey, $subKey2)) {
        Assert-True ($testKey -like ('Software\Classes\7-Zip.ArchiveMoeTest' + $id + '*\DefaultIcon')) 'Unexpected cleanup target.'
        $key = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey($testKey, $true)
        if ($null -ne $key) {
            try { $key.DeleteValue('Keep', $false); $key.DeleteSubKey('KeepChild', $false) } finally { $key.Dispose() }
        }
    }
    Restore-ArchiveDefaultSnapshot $absent
    Restore-ArchiveDefaultSnapshot $absent2
    foreach ($file in @($backupPath, $foreignPath)) { if (Test-Path -LiteralPath $file) { Remove-Item -LiteralPath $file -Force } }
    if (Test-Path -LiteralPath $temporary) { Remove-Item -LiteralPath $temporary -Force }
}
