#Requires -Version 5.1
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$root = Split-Path -Parent $PSScriptRoot
Import-Module (Join-Path $root '工具\IconRegistry.psm1') -Force
function Assert-True { param([bool]$Condition, [string]$Message); if (-not $Condition) { throw $Message } }
$id = [Guid]::NewGuid().ToString('N')
$temporary = Join-Path ([IO.Path]::GetTempPath()) ('archive-moe-cache-tests-' + $id)
$fixture = Join-Path $temporary 'fixture'
$extension = 'amt' + $id.Substring(0, 20)
$extensionKey = 'Software\Classes\.' + $extension
$className = '7-Zip.ArchiveMoeTest' + $id
$classKey = 'Software\Classes\' + $className + '\DefaultIcon'
$absent = Get-ArchiveDefaultSnapshot $classKey
$sourceDirectory = Join-Path $fixture '成品图标\ICO'
$paletteDirectory = Join-Path $fixture '配色方案'
$cacheDirectory = Join-Path $fixture '本地图标缓存'
Assert-True (-not $absent.KeyExisted) 'Temporary class already exists.'
Assert-True ($null -eq [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey($extensionKey)) 'Temporary extension already exists.'
try {
    [IO.Directory]::CreateDirectory($sourceDirectory) | Out-Null
    [IO.Directory]::CreateDirectory($paletteDirectory) | Out-Null
    $source = Join-Path $sourceDirectory 'sample.ico'
    [IO.File]::Copy((Join-Path $root '成品图标\ICO\7z.ico'), $source)
    $palette = @(@{ id = 'sample'; label = 'TEST'; extensions = @($extension) })
    ConvertTo-Json -InputObject $palette -Depth 4 | Set-Content -LiteralPath (Join-Path $paletteDirectory '默认配色.json') -Encoding UTF8
    $key = [Microsoft.Win32.Registry]::CurrentUser.CreateSubKey($extensionKey)
    try { $key.SetValue('', $className) } finally { $key.Dispose() }

    $first = @(Get-ArchiveIconPlan -PackRoot $fixture)
    Assert-True ($first.Count -eq 2) 'Expected a class and extension target.'
    Assert-True (-not (Test-Path -LiteralPath $cacheDirectory)) 'Planning created cache files.'
    Assert-True (-not (Get-ArchiveDefaultSnapshot $classKey).ValueExisted) 'Planning changed registry state.'
    Write-ArchiveCachedIcons -Targets $first
    $firstHash = (Get-FileHash -LiteralPath $first[0].IconPath -Algorithm SHA256).Hash
    Assert-True ($firstHash -eq $first[0].IconHash) 'Copied ICO does not match source hash.'
    $firstTime = (Get-Item -LiteralPath $first[0].IconPath).LastWriteTimeUtc
    Write-ArchiveCachedIcons -Targets $first
    Assert-True ((Get-Item -LiteralPath $first[0].IconPath).LastWriteTimeUtc -eq $firstTime) 'Repeated application overwrote an immutable icon.'

    # Replacing the source in place must produce a distinct Shell cache key.
    [IO.File]::Copy((Join-Path $root '成品图标\ICO\zip.ico'), $source, $true)
    $second = @(Get-ArchiveIconPlan -PackRoot $fixture)
    Assert-True ($second[0].IconValue -ne $first[0].IconValue) 'Updated content reused the old icon location.'
    $rejected = $false
    try { Write-ArchiveCachedIcons -Targets $first } catch { $rejected = $true }
    Assert-True $rejected 'A source modified after planning was accepted.'
    Write-ArchiveCachedIcons -Targets $second
    Assert-True ((Get-FileHash -LiteralPath $first[0].IconPath -Algorithm SHA256).Hash -eq $firstHash) 'An old cached icon was changed.'
    foreach ($target in $second) { Set-ArchiveDefaultIcon -SubKey $target.SubKey -IconValue $target.IconValue }
    Assert-True ((Get-ArchiveDefaultSnapshot $classKey).Value -eq $second[0].IconValue) 'Application did not use the cached icon location.'
    Assert-True ($second[0].IconValue.Contains('本地图标缓存')) 'Registry icon location did not use the cache.'
    Write-Host 'Content updates change the icon path; repeated application preserves cached files; source changes are rejected; planning is read-only.'
} finally {
    Restore-ArchiveDefaultSnapshot $absent
    # Only this fresh GUID-named extension and its empty DefaultIcon key are removed.
    $key = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey($extensionKey, $true)
    if ($null -ne $key) {
        try {
            $key.DeleteSubKey('DefaultIcon', $false)
            $key.DeleteValue('', $false)
            Assert-True ($key.ValueCount -eq 0 -and $key.SubKeyCount -eq 0) 'Unexpected data in temporary extension.'
        } finally { $key.Dispose() }
        [Microsoft.Win32.Registry]::CurrentUser.DeleteSubKey($extensionKey, $false)
    }
    if (Test-Path -LiteralPath $temporary) {
        $resolved = (Resolve-Path -LiteralPath $temporary).ProviderPath
        $expected = [IO.Path]::GetFullPath((Join-Path ([IO.Path]::GetTempPath()) ('archive-moe-cache-tests-' + $id)))
        Assert-True ($resolved -eq $expected -and (Split-Path -Leaf $resolved) -eq ('archive-moe-cache-tests-' + $id)) 'Unexpected fixture cleanup path.'
        Remove-Item -LiteralPath $resolved -Recurse -Force
    }
}
