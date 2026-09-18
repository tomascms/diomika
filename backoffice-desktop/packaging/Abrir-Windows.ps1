#Requires -Version 5.1
<#
  Abre o Diomika Backoffice (.exe portátil).
  Procura o instalador na pasta actual e em locais habituais do repo (release/, cliente-backoffice/).
#>
$ErrorActionPreference = 'Continue'
$Root = $PSScriptRoot
Set-Location -LiteralPath $Root

function Write-Step([string]$msg) {
  Write-Host " - $msg"
}

function Join-MultiPath {
  param([string[]]$Parts)
  $p = $Parts[0]
  for ($i = 1; $i -lt $Parts.Count; $i++) {
    $p = Join-Path $p $Parts[$i]
  }
  return $p
}

function Find-PortableExe {
  $dirs = @(
    $Root
    (Join-MultiPath @($Root, '..'))
    (Join-MultiPath @($Root, '..', 'release'))
    (Join-MultiPath @($Root, '..', 'release-fresh'))
    (Join-MultiPath @($Root, '..', '..', 'cliente-backoffice'))
    (Join-MultiPath @($Root, '..', 'cliente-backoffice'))
  ) | ForEach-Object {
    try { (Resolve-Path -LiteralPath $_ -ErrorAction Stop).Path } catch { $null }
  } | Where-Object { $_ } | Select-Object -Unique

  $hits = @()
  foreach ($dir in $dirs) {
    $hits += Get-ChildItem -LiteralPath $dir -Filter 'Diomika-Backoffice-*-windows.exe' -File -ErrorAction SilentlyContinue
  }
  return $hits | Sort-Object LastWriteTime -Descending | Select-Object -First 1
}

function Find-Zip {
  $dirs = @(
    $Root
    (Join-MultiPath @($Root, '..'))
    (Join-MultiPath @($Root, '..', 'release'))
    (Join-MultiPath @($Root, '..', 'release-fresh'))
    (Join-MultiPath @($Root, '..', '..', 'cliente-backoffice'))
    (Join-MultiPath @($Root, '..', 'cliente-backoffice'))
  ) | ForEach-Object {
    try { (Resolve-Path -LiteralPath $_ -ErrorAction Stop).Path } catch { $null }
  } | Where-Object { $_ } | Select-Object -Unique

  $hits = @()
  foreach ($dir in $dirs) {
    $hits += Get-ChildItem -LiteralPath $dir -Filter 'Diomika-Backoffice-*-windows.zip' -File -ErrorAction SilentlyContinue
  }
  return $hits | Sort-Object LastWriteTime -Descending | Select-Object -First 1
}

Write-Host ''
Write-Host ' Diomika Backoffice'
Write-Host ' -------------------'

Write-Step 'A desbloquear ficheiros do pacote...'
@(
  (Find-Zip)
  (Find-PortableExe)
) | Where-Object { $_ } | ForEach-Object {
  try { Unblock-File -LiteralPath $_.FullName -ErrorAction SilentlyContinue } catch {}
}

$portable = Find-PortableExe

$exclusionOk = $false
$exDirs = @($Root)
if ($portable) { $exDirs += $portable.DirectoryName }
foreach ($exDir in ($exDirs | Select-Object -Unique)) {
  if (-not $exDir -or -not (Test-Path -LiteralPath $exDir)) { continue }
  try {
    if (Get-Command Add-MpPreference -ErrorAction SilentlyContinue) {
      Add-MpPreference -ExclusionPath $exDir -ErrorAction Stop
      $exclusionOk = $true
      Write-Step "Exclusao Defender: $exDir"
    }
  } catch {
    # opcional
  }
}
if (-not $exclusionOk) {
  Write-Step 'Sem exclusao automatica (opcional). Se o AV bloquear: adicione a pasta do .exe as exclusoes.'
}
if ($portable) {
  Write-Step "A abrir $($portable.Name)..."
  Write-Step "Local: $($portable.DirectoryName)"
  try { Unblock-File -LiteralPath $portable.FullName -ErrorAction SilentlyContinue } catch {}
  Start-Process -FilePath $portable.FullName
  exit 0
}

$zip = Find-Zip
$appDir = Join-Path $Root '.diomika'
$candidates = @(
  (Join-Path $appDir 'Diomika Backoffice.exe'),
  (Join-Path $appDir 'Diomika Backoffice\Diomika Backoffice.exe'),
  (Join-Path $Root 'Diomika Backoffice\Diomika Backoffice.exe'),
  (Join-Path $Root 'Diomika Backoffice.exe')
)
$appExe = $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1

if (-not $appExe -and $zip) {
  Write-Step "A extrair $($zip.Name) para .diomika (so na 1.a vez)..."
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
  Write-Host ' ERRO: nao encontrei Diomika-Backoffice-*-windows.exe.'
  Write-Host ''
  Write-Host ' Construa primeiro:  cd backoffice-desktop  &&  npm run dist:cliente'
  Write-Host ' Ou abra de:         cliente-backoffice\Abrir-Windows.cmd'
  Write-Host ''
  exit 1
}

try { Unblock-File -LiteralPath $appExe -ErrorAction SilentlyContinue } catch {}
Write-Step "A abrir: $appExe"
Start-Process -FilePath $appExe
exit 0
