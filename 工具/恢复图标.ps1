#Requires -Version 5.1
<#
.SYNOPSIS
从首次备份恢复原始文件图标，也可指定某次应用前的会话备份。
#>
[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = 'Medium')]
param([string]$BackupPath)
$ErrorActionPreference = 'Stop'
$packRoot = Split-Path -Parent $PSScriptRoot
Import-Module (Join-Path $PSScriptRoot 'IconRegistry.psm1') -Force
if (-not $BackupPath) { $BackupPath = Join-Path $packRoot '本地备份\original-icons.json' }
if (-not (Test-Path -LiteralPath $BackupPath -PathType Leaf)) { throw ('找不到图标备份：' + $BackupPath) }
$backup = Read-ArchiveBackup $BackupPath
$entries = @($backup.Entries)
foreach ($entry in $entries) {
    if ($PSCmdlet.ShouldProcess(('HKCU\' + $entry.SubKey), '恢复备份中的图标配置')) {
        Restore-ArchiveDefaultSnapshot $entry
    }
}
if ($WhatIfPreference) { Write-Host '恢复预览完成：未修改注册表。'; return }
try { Send-ArchiveIconRefresh } catch { Write-Warning '配置已恢复；请重新打开文件夹或注销后登录以刷新显示。' }
Write-Host ('已按备份恢复图标：' + $BackupPath)
