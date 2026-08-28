#Requires -Version 5.1
<#
  Desbloqueia o pacote Windows, opcionalmente adiciona exclusão Defender,
  extrai o ZIP se necessário, e abre o Diomika Backoffice.
#>
$ErrorActionPreference = 'Continue'
$Root = $PSScriptRoot
Set-Location -LiteralPath $Root

function Write-Step([string]$msg) {
  Write-Host " - $msg"
}

Write-Host ''
Write-Host ' Diomika Backoffice'
Write-Host ' -------------------'

# 1) Remover marca "descarregado da Internet" (Zone.Identifier)
Write-Step 'A desbloquear ficheiros...'
Get-ChildItem -LiteralPath $Root -Recurse -File -ErrorAction SilentlyContinue |
  ForEach-Object {
    try { Unblock-File -LiteralPath $_.FullName -ErrorAction SilentlyContinue } catch {}
  }

# 2) Exclusão Microsoft Defender (melhor esforço; Admin ajuda)
$exclusionOk = $false
try {
  if (Get-Command Add-MpPreference -ErrorAction SilentlyContinue) {
    Add-MpPreference -ExclusionPath $Root -ErrorAction Stop
    $exclusionOk = $true
    Write-Step "Exclusao Defender: $Root"
  }
} catch {
  Write-Step 'Exclusao Defender automatica falhou (abra o .cmd como Administrador se o AV continuar a bloquear).'
}

# 3) Preferir pasta extraida do ZIP (sem .exe portatil auto-extraivel)
$zip = Get-ChildItem -LiteralPath $Root -Filter 'Diomika-Backoffice-*-windows.zip' -File -ErrorAction SilentlyContinue |
  Sort-Object LastWriteTime -Descending |
  Select-Object -First 1

$candidates = @(
  (Join-Path $Root 'Diomika Backoffice\Diomika Backoffice.exe'),
  (Join-Path $Root 'win-unpacked\Diomika Backoffice.exe'),
  (Join-Path $Root 'Diomika Backoffice.exe')
)

$appExe = $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1

if (-not $appExe -and $zip) {
  Write-Step "A extrair $($zip.Name)..."
  $extractTo = Join-Path $Root '_extract_tmp'
  if (Test-Path -LiteralPath $extractTo) {
    Remove-Item -LiteralPath $extractTo -Recurse -Force -ErrorAction SilentlyContinue
  }
  New-Item -ItemType Directory -Path $extractTo | Out-Null
  Expand-Archive -LiteralPath $zip.FullName -DestinationPath $extractTo -Force

  # electron-builder zip: ficheiros na raiz ou numa pasta
  $found = Get-ChildItem -LiteralPath $extractTo -Recurse -Filter 'Diomika Backoffice.exe' -File -ErrorAction SilentlyContinue |
    Select-Object -First 1
  if ($found) {
    $srcDir = $found.Directory.FullName
    $destDir = Join-Path $Root 'Diomika Backoffice'
    if (Test-Path -LiteralPath $destDir) {
      Remove-Item -LiteralPath $destDir -Recurse -Force -ErrorAction SilentlyContinue
    }
    Move-Item -LiteralPath $srcDir -Destination $destDir -Force
    $appExe = Join-Path $destDir 'Diomika Backoffice.exe'
  }
  Remove-Item -LiteralPath $extractTo -Recurse -Force -ErrorAction SilentlyContinue
}

if (-not $appExe) {
  # Fallback legado: .exe portatil (pior para AV)
  $portable = Get-ChildItem -LiteralPath $Root -Filter 'Diomika-Backoffice-*-windows.exe' -File -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1
  if ($portable) {
    Write-Step 'A usar .exe portatil antigo (pode ser bloqueado pelo antivirus)...'
    try { Unblock-File -LiteralPath $portable.FullName } catch {}
    Start-Process -FilePath $portable.FullName
    exit 0
  }
  Write-Host ''
  Write-Host ' ERRO: nao encontrei Diomika-Backoffice-*-windows.zip nem a pasta extraida.'
  Write-Host ' Coloque o ZIP nesta pasta e volte a correr Abrir-Windows.cmd'
  Write-Host ''
  exit 1
}

# 4) Desbloquear tambem a pasta da app
Get-ChildItem -LiteralPath (Split-Path $appExe -Parent) -Recurse -File -ErrorAction SilentlyContinue |
  ForEach-Object {
    try { Unblock-File -LiteralPath $_.FullName -ErrorAction SilentlyContinue } catch {}
  }

Write-Step "A abrir: $appExe"
if ($exclusionOk) {
  Write-Step 'Se ainda for bloqueado, confirme a exclusao em Defesa do Windows.'
}
Start-Process -FilePath $appExe
exit 0
