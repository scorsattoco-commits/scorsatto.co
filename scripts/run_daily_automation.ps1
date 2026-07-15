$ErrorActionPreference = "Continue"

$Root = "C:\Users\aliss\OneDrive\Documentos\SCORSATTO\site-scorsatto"
$Python = "C:\Users\aliss\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$LogDir = Join-Path $Root "data\automacoes\logs"
$Date = Get-Date -Format "yyyy-MM-dd"
$Log = Join-Path $LogDir "rotina-diaria-$Date.log"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

function Write-Log($Message) {
  $Line = "$(Get-Date -Format s) $Message"
  Add-Content -Path $Log -Value $Line -Encoding UTF8
  Write-Output $Line
}

Set-Location $Root
Write-Log "Iniciando rotina diaria SCORSATTO. Nada sera publicado automaticamente."

Write-Log "Criando backup critico."
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\scripts\backup_site_critical.ps1" *> "$LogDir\backup-critico-$Date.out"
Write-Log "Backup critico finalizado. Saida: $LogDir\backup-critico-$Date.out"

Write-Log "Conferindo tamanhos do fornecedor."
& $Python ".\scripts\update_supplier_sizes.py" "--workers" "16" *> "$LogDir\fornecedor-tamanhos-$Date.out"
Write-Log "Relatorio de fornecedor finalizado. Saida: $LogDir\fornecedor-tamanhos-$Date.out"

Write-Log "Sincronizando leads reais do Instagram via Meta."
& $Python ".\scripts\sync_instagram_leads.py" *> "$LogDir\instagram-leads-$Date.out"
Write-Log "Sincronizacao Instagram finalizada. Saida: $LogDir\instagram-leads-$Date.out"

Write-Log "Diagnosticando backoffice e Instagram."
& $Python ".\scripts\check_instagram_backoffice.py" *> "$LogDir\instagram-backoffice-check-$Date.out"
Write-Log "Diagnostico Instagram/backoffice finalizado. Saida: $LogDir\instagram-backoffice-check-$Date.out"

Write-Log "Gerando painel automatico."
& $Python ".\scripts\daily_automation_report.py" *> "$LogDir\painel-automatico-$Date.out"
Write-Log "Painel automatico finalizado. Saida: $LogDir\painel-automatico-$Date.out"

Write-Log "Rotina diaria concluida."
