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

# 1) Remover marca "descarregado da Internet" só no pacote e na app
Write-Step 'A desbloquear ficheiros do pacote...'
@(
  (Get-ChildItem -LiteralPath $Root -Filter 'Diomika-Backoffice-*-windows.zip' -File -ErrorAction SilentlyContinue)
  (Get-ChildItem -LiteralPath $Root -Filter 'Diomika-Backoffice-*-windows.exe' -File -ErrorAction SilentlyContinue)
) | ForEach-Object {
  if ($_) {
    try { Unblock-File -LiteralPath $_.FullName -ErrorAction SilentlyContinue } catch {}
  }
}

# 2) Exclusão Microsoft Defender (opcional; só se o utilizador correr este script)
# Não falha se não houver permissão — o objectivo é abrir a app.
$exclusionOk = $false
try {
  if (Get-Command Add-MpPreference -ErrorAction SilentlyContinue) {
    Add-MpPreference -ExclusionPath $Root -ErrorAction Stop
    $exclusionOk = $true
    Write-Step "Exclusao Defender: $Root"
  }
} catch {
  Write-Step 'Sem exclusao automatica (opcional). Se o AV bloquear: Definições → Exclusões → pasta cliente-backoffice.'
}

# 3) Preferir .exe portátil (1 clique, sem extrair)
$portable = Get-ChildItem -LiteralPath $Root -Filter 'Diomika-Backoffice-*-windows.exe' -File -ErrorAction SilentlyContinue |
  Sort-Object LastWriteTime -Descending |
  Select-Object -First 1

if ($portable) {
  Write-Step "A abrir $($portable.Name)..."
  try { Unblock-File -LiteralPath $portable.FullName -ErrorAction SilentlyContinue } catch {}
  Start-Process -FilePath $portable.FullName
  exit 0
}

# 4) Alternativa: extrair ZIP para pasta oculta .diomika
$zip = Get-ChildItem -LiteralPath $Root -Filter 'Diomika-Backoffice-*-windows.zip' -File -ErrorAction SilentlyContinue |
  Sort-Object LastWriteTime -Descending |
  Select-Object -First 1

$appDir = Join-Path $Root '.diomika'
$candidates = @(
  (Join-Path $appDir 'Diomika Backoffice.exe'),
  (Join-Path $appDir 'Diomika Backoffice\Diomika Backoffice.exe'),
  (Join-Path $Root 'Diomika Backoffice\Diomika Backoffice.exe'),
  (Join-Path $Root 'Diomika Backoffice.exe')
)

$appExe = $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1

if (-not $appExe -and $zip) {
  Write-Step "A extrair $($zip.Name) para .diomika (só na 1.a vez)..."
  $extractTo = Join-Path $Root '_extract_tmp'
  if (Test-Path -LiteralPath $extractTo) {
    Remove-Item -LiteralPath $extractTo -Recurse -Force -ErrorAction SilentlyContinue
  }
  if (Test-Path -LiteralPath $appDir) {
    Remove-Item -LiteralPath $appDir -Recurse -Force -ErrorAction SilentlyContinue
  }
  New-Item -ItemType Directory -Path $extractTo | Out-Null
  Expand-Archive -LiteralPath $zip.FullName -DestinationPath $extractTo -Force

  $found = Get-ChildItem -LiteralPath $extractTo -Recurse -Filter 'Diomika Backoffice.exe' -File -ErrorAction SilentlyContinue |
    Select-Object -First 1
  if ($found) {
    New-Item -ItemType Directory -Path $appDir -Force | Out-Null
    $srcDir = $found.Directory.FullName
    Copy-Item -LiteralPath $srcDir -Destination (Join-Path $appDir (Split-Path -Leaf $srcDir)) -Recurse -Force
    $appExe = Get-ChildItem -LiteralPath $appDir -Recurse -Filter 'Diomika Backoffice.exe' -File -ErrorAction SilentlyContinue |
      Select-Object -First 1 -ExpandProperty FullName
  }
  Remove-Item -LiteralPath $extractTo -Recurse -Force -ErrorAction SilentlyContinue
}

if (-not $appExe) {
  Write-Host ''
  Write-Host ' ERRO: nao encontrei Diomika-Backoffice-*-windows.exe nem .zip nesta pasta.'
  Write-Host ''
  exit 1
}

# 5) Desbloquear só o executável principal
try { Unblock-File -LiteralPath $appExe -ErrorAction SilentlyContinue } catch {}

Write-Step "A abrir: $appExe"
if ($exclusionOk) {
  Write-Step 'Se ainda for bloqueado, confirme a exclusao em Defesa do Windows.'
}
Start-Process -FilePath $appExe
exit 0
