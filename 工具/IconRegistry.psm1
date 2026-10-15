Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Assert-ArchiveIconSubKey {
    param([Parameter(Mandatory)][string]$SubKey)
    if ($SubKey -notmatch '^Software\\Classes\\(?:7-Zip\.[A-Za-z0-9._-]+|\.[A-Za-z0-9][A-Za-z0-9._-]{0,31})\\DefaultIcon$') {
        throw "Unsupported registry target: $SubKey"
    }
}

function Get-ArchiveDefaultSnapshot {
    param([Parameter(Mandatory)][string]$SubKey)
    Assert-ArchiveIconSubKey $SubKey
    $key = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey($SubKey)
    try {
        $exists = $null -ne $key
        $hasValue = $exists -and ($key.GetValueNames() -contains '')
        $kind = if ($hasValue) { $key.GetValueKind('').ToString() } else { $null }
        $value = if ($hasValue) { $key.GetValue('', $null, [Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames) } else { $null }
        [pscustomobject]@{ SubKey = $SubKey; KeyExisted = $exists; ValueExisted = $hasValue; Kind = $kind; Value = $value }
    } finally { if ($null -ne $key) { $key.Dispose() } }
}

function Set-ArchiveDefaultIcon {
    param([Parameter(Mandatory)][string]$SubKey, [Parameter(Mandatory)][string]$IconValue)
    Assert-ArchiveIconSubKey $SubKey
    $key = [Microsoft.Win32.Registry]::CurrentUser.CreateSubKey($SubKey)
    try { $key.SetValue('', $IconValue, [Microsoft.Win32.RegistryValueKind]::String) }
    finally { $key.Dispose() }
}

function Restore-ArchiveDefaultSnapshot {
    param([Parameter(Mandatory)]$Snapshot)
    $subKey = [string]$Snapshot.SubKey
    Assert-ArchiveIconSubKey $subKey
    if ($Snapshot.ValueExisted) {
        $kind = [Microsoft.Win32.RegistryValueKind]([Enum]::Parse([Microsoft.Win32.RegistryValueKind], [string]$Snapshot.Kind))
        $value = switch ($kind.ToString()) {
            'String' { [string]$Snapshot.Value }
            'ExpandString' { [string]$Snapshot.Value }
            'MultiString' { ,([string[]]$Snapshot.Value) }
            'Binary' { ,([byte[]]$Snapshot.Value) }
            'DWord' { [int]$Snapshot.Value }
            'QWord' { [long]$Snapshot.Value }
            default { throw "Unsupported backup value kind: $kind" }
        }
        $key = [Microsoft.Win32.Registry]::CurrentUser.CreateSubKey($subKey)
        try { $key.SetValue('', $value, $kind) } finally { $key.Dispose() }
        return
    }
    $key = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey($subKey, $true)
    if ($null -ne $key) {
        try { $key.DeleteValue('', $false) } finally { $key.Dispose() }
    }
    if ($Snapshot.KeyExisted) { return }
    # Delete only empty keys created by the override. Never recursively delete
    # a class or remove values another application may have added meanwhile.
    $cleanup = $subKey
    while ($cleanup -ne 'Software\Classes' -and $cleanup.StartsWith('Software\Classes\', [StringComparison]::OrdinalIgnoreCase)) {
        $key = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey($cleanup)
        if ($null -eq $key) { break }
        try { $empty = $key.ValueCount -eq 0 -and $key.SubKeyCount -eq 0 } finally { $key.Dispose() }
        if (-not $empty) { break }
        [Microsoft.Win32.Registry]::CurrentUser.DeleteSubKey($cleanup, $false)
        $cleanup = $cleanup.Substring(0, $cleanup.LastIndexOf('\'))
    }
}

function Get-ArchiveEffectiveProgId {
    param([Parameter(Mandatory)][string]$Extension)
    $choice = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey("Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\$Extension\UserChoice")
    try { if ($null -ne $choice) { $value = $choice.GetValue('ProgId'); if ($value) { return [string]$value } } }
    finally { if ($null -ne $choice) { $choice.Dispose() } }
    $key = [Microsoft.Win32.Registry]::ClassesRoot.OpenSubKey($Extension)
    try { if ($null -ne $key) { return [string]$key.GetValue('') } }
    finally { if ($null -ne $key) { $key.Dispose() } }
    return ''
}

function Get-ArchiveIconPlan {
    param([Parameter(Mandatory)][string]$PackRoot, [string]$IconDirectory, [string[]]$Formats)
    $palettePath = Join-Path $PackRoot '配色方案\默认配色.json'
    if (-not $IconDirectory) { $IconDirectory = Join-Path $PackRoot '成品图标\ICO' }
    $iconRoot = (Resolve-Path -LiteralPath $IconDirectory -ErrorAction Stop).ProviderPath
    $palette = Get-Content -LiteralPath $palettePath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($Formats) {
        $known = @($palette | ForEach-Object { [string]$_.id })
        foreach ($format in $Formats) { if ($known -notcontains $format) { throw "Unknown format: $format" } }
        $palette = @($palette | Where-Object { $Formats -contains $_.id })
    }
    $targets = [ordered]@{}
    foreach ($item in $palette) {
        if ([string]$item.id -notmatch '^[A-Za-z0-9][A-Za-z0-9_-]{0,29}$') { throw 'Invalid icon id in palette.' }
        $icon = Join-Path $iconRoot ($item.id + '.ico')
        if (-not (Test-Path -LiteralPath $icon -PathType Leaf)) { throw "Missing icon: $icon" }
        $header = [IO.File]::ReadAllBytes($icon)
        if ($header.Length -lt 6 -or $header[0] -ne 0 -or $header[1] -ne 0 -or $header[2] -ne 1 -or $header[3] -ne 0) { throw "Invalid ICO: $icon" }
        $iconValue = '"' + $icon + '",0'
        foreach ($suffix in $item.extensions) {
            $extension = '.' + [string]$suffix
            if ($extension -notmatch '^\.[A-Za-z0-9][A-Za-z0-9._-]{0,31}$') { throw "Invalid extension: $extension" }
            $progId = Get-ArchiveEffectiveProgId $extension
            if ($progId -notmatch '^7-Zip\.[A-Za-z0-9._-]+$') { continue }
            foreach ($subKey in @("Software\Classes\$progId\DefaultIcon", "Software\Classes\$extension\DefaultIcon")) {
                if ($targets.Contains($subKey)) {
                    if ($targets[$subKey].IconValue -ne $iconValue) { throw "Formats share a ProgID but need different icons: $progId" }
                    continue
                }
                $targets[$subKey] = [pscustomobject]@{ Format = [string]$item.label; Extension = $extension; ProgId = $progId; SubKey = $subKey; IconValue = $iconValue }
            }
        }
    }
    @($targets.Values)
}

function Get-ArchiveUserSid { [Security.Principal.WindowsIdentity]::GetCurrent().User.Value }

function New-ArchiveBackupDocument {
    param([Parameter(Mandatory)][AllowEmptyCollection()][object[]]$Entries)
    [pscustomobject]@{ SchemaVersion = 1; UserSid = Get-ArchiveUserSid; CreatedAtUtc = [DateTime]::UtcNow.ToString('o'); Entries = @($Entries) }
}

function Read-ArchiveBackup {
    param([Parameter(Mandatory)][string]$Path)
    $document = Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($document.SchemaVersion -ne 1 -or $document.UserSid -ne (Get-ArchiveUserSid)) { throw 'Backup schema or current Windows user does not match.' }
    foreach ($entry in @($document.Entries)) {
        Assert-ArchiveIconSubKey ([string]$entry.SubKey)
        if ($entry.ValueExisted -and [string]$entry.Kind -notin @('String','ExpandString','MultiString','Binary','DWord','QWord')) { throw 'Invalid backup value kind.' }
    }
    $document
}

function Write-ArchiveBackup {
    param([Parameter(Mandatory)]$Document, [Parameter(Mandatory)][string]$Path)
    $full = [IO.Path]::GetFullPath($Path)
    $directory = [IO.Path]::GetDirectoryName($full)
    [IO.Directory]::CreateDirectory($directory) | Out-Null
    $temporary = Join-Path $directory ([IO.Path]::GetFileName($full) + '.' + [Guid]::NewGuid().ToString('N') + '.tmp')
    try {
        $Document | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $temporary -Encoding UTF8
        Move-Item -LiteralPath $temporary -Destination $full -Force
    } finally { if (Test-Path -LiteralPath $temporary) { Remove-Item -LiteralPath $temporary -Force } }
}

function Merge-ArchiveOriginalBackup {
    param([Parameter(Mandatory)][string]$Path, [Parameter(Mandatory)][object[]]$NewEntries)
    $entries = [ordered]@{}
    if (Test-Path -LiteralPath $Path) {
        $existing = Read-ArchiveBackup $Path
        foreach ($entry in @($existing.Entries)) { $entries[$entry.SubKey] = $entry }
    }
    foreach ($entry in $NewEntries) { if (-not $entries.Contains($entry.SubKey)) { $entries[$entry.SubKey] = $entry } }
    Write-ArchiveBackup (New-ArchiveBackupDocument @($entries.Values)) $Path
}

function Send-ArchiveIconRefresh {
    if (-not ('ArchiveMoe.NativeShell' -as [type])) {
        Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
namespace ArchiveMoe {
    public static class NativeShell {
        [DllImport("shell32.dll")]
        public static extern void SHChangeNotify(int eventId, uint flags, IntPtr item1, IntPtr item2);
    }
}
'@
    }
    [ArchiveMoe.NativeShell]::SHChangeNotify(0x08000000, 0, [IntPtr]::Zero, [IntPtr]::Zero)
}

Export-ModuleMember -Function Get-ArchiveDefaultSnapshot, Set-ArchiveDefaultIcon, Restore-ArchiveDefaultSnapshot, Get-ArchiveEffectiveProgId, Get-ArchiveIconPlan, Get-ArchiveUserSid, New-ArchiveBackupDocument, Read-ArchiveBackup, Write-ArchiveBackup, Merge-ArchiveOriginalBackup, Send-ArchiveIconRefresh
