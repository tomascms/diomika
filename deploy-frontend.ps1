# Deploy Frontend para Cloudflare Pages
# Uso: .\deploy-frontend.ps1

param(
    [string]$Token = $env:CLOUDFLARE_PAGES_API_TOKEN,
    [string]$AccountId = $env:CLOUDFLARE_ACCOUNT_ID,
    [string]$ProjectName = "diomika-loja",
    [string]$Branch = "production"
)

if (-not $Token) {
    Write-Host "❌ Erro: CLOUDFLARE_PAGES_API_TOKEN não configurado" -ForegroundColor Red
    Write-Host "   Defina a variável de ambiente ou passe como parametro: -Token xxx" -ForegroundColor Yellow
    exit 1
}

if (-not $AccountId) {
    Write-Host "❌ Erro: CLOUDFLARE_ACCOUNT_ID não configurado" -ForegroundColor Red
    exit 1
}

$distPath = "$PSScriptRoot\frontend-web\dist"

if (-not (Test-Path $distPath)) {
    Write-Host "❌ Erro: Pasta dist não encontrada em $distPath" -ForegroundColor Red
    Write-Host "   Execute 'npm run build' em frontend-web primeiro" -ForegroundColor Yellow
    exit 1
}

Write-Host "🚀 Iniciando deploy do frontend..." -ForegroundColor Cyan
Write-Host "   Projeto: $ProjectName" -ForegroundColor Gray
Write-Host "   Branch: $Branch" -ForegroundColor Gray
Write-Host "   Arquivos: $(Get-ChildItem $distPath -Recurse -File | Measure-Object | Select-Object -ExpandProperty Count)" -ForegroundColor Gray

$env:CLOUDFLARE_API_TOKEN = $Token
$env:CLOUDFLARE_ACCOUNT_ID = $AccountId

cd $distPath

try {
    Write-Host "`n📤 Enviando arquivos..." -ForegroundColor Cyan
    npx wrangler pages deploy . `
        --project-name=$ProjectName `
        --branch=$Branch `
        --compatible-flags="nodejs_compat"

    Write-Host "`n✅ Deploy concluído com sucesso!" -ForegroundColor Green
    Write-Host "   URL: https://$ProjectName.pages.dev" -ForegroundColor Gray
} catch {
    Write-Host "`n❌ Erro durante o deploy:" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}
