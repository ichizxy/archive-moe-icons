#Requires -Version 5.1
<#
.SYNOPSIS
为当前用户已关联到 7-Zip 的文件类型应用压缩包娘图标。
.EXAMPLE
.\应用图标.ps1 -WhatIf
.EXAMPLE
.\应用图标.ps1 -Formats 7z,zip,rar
#>
[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = 'Medium')]
param([string]$IconDirectory, [string[]]$Formats)
$ErrorActionPreference = 'Stop'
$packRoot = Split-Path -Parent $PSScriptRoot
Import-Module (Join-Path $PSScriptRoot 'IconRegistry.psm1') -Force
$plan = @(Get-ArchiveIconPlan -PackRoot $packRoot -IconDirectory $IconDirectory -Formats $Formats)
if ($plan.Count -eq 0) { Write-Warning '没有找到已关联到 7-Zip 的目标格式。请先在 7-Zip 的工具 → 选项 → 系统中设置关联。'; return }
$plan | Select-Object Format, Extension, ProgId, IconValue | Format-Table -AutoSize
if ($WhatIfPreference) {
    foreach ($target in $plan) { [void]$PSCmdlet.ShouldProcess(('HKCU\' + $target.SubKey), ('设置图标 ' + $target.IconValue)) }
    Write-Host '预览完成：未修改注册表，也未创建备份或输出文件。'
    return
}
$selected = @($plan | Where-Object { $PSCmdlet.ShouldProcess(('HKCU\' + $_.SubKey), '替换文件图标') })
if ($selected.Count -eq 0) { return }
Write-ArchiveCachedIcons -Targets $selected
$snapshots = @($selected | ForEach-Object { Get-ArchiveDefaultSnapshot $_.SubKey })
$backupRoot = Join-Path $packRoot '本地备份'
$sessionPath = Join-Path $backupRoot ('apply-' + [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss-fff') + '-' + [Guid]::NewGuid().ToString('N') + '.json')
Write-ArchiveBackup (New-ArchiveBackupDocument $snapshots) $sessionPath
Merge-ArchiveOriginalBackup -Path (Join-Path $backupRoot 'original-icons.json') -NewEntries $snapshots
try {
    foreach ($target in $selected) { Set-ArchiveDefaultIcon -SubKey $target.SubKey -IconValue $target.IconValue }
} catch {
    $applyError = $_
    $rollbackErrors = @()
    foreach ($snapshot in $snapshots) {
        try { Restore-ArchiveDefaultSnapshot $snapshot } catch { $rollbackErrors += $_.Exception.Message }
    }
    if ($rollbackErrors.Count -gt 0) { Write-Warning ('回滚未完全成功，请使用会话备份恢复：' + $sessionPath + '; ' + ($rollbackErrors -join '; ')) }
    throw $applyError
}
try { Send-ArchiveIconRefresh } catch { Write-Warning '图标配置已保存；请重新打开文件夹或注销后登录以刷新显示。' }
Write-Host ('已更新 ' + $selected.Count + ' 项图标配置。原始备份：' + (Join-Path $backupRoot 'original-icons.json'))
