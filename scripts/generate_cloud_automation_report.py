"""Generate the public SCORSATTO automation hub from daily machine-readable reports."""

import html
import json
from pathlib import Path

from supplier_common import ROOT, today_slug


AUTOMATIONS = ROOT / "previews" / "automacoes"
SIZES = ROOT / "data" / "fornecedor-tamanhos"
SCANS = ROOT / "data" / "fornecedor-varreduras"


def latest(folder, pattern):
    files = sorted(folder.glob(pattern), key=lambda path: path.stat().st_mtime, reverse=True)
    if not files:
        return None, None
    path = files[0]
    return path, json.loads(path.read_text(encoding="utf-8"))


def relative_preview(path):
    return path.relative_to(ROOT / "previews").as_posix()


def main():
    AUTOMATIONS.mkdir(parents=True, exist_ok=True)
    size_path, sizes = latest(SIZES, "atualizacao-tamanhos-*.json")
    scan_path, scan = latest(SCANS, "varredura-fornecedor-agrupada-*.json")

    size_summary = "Ainda não há execução de tamanhos registrada."
    if sizes:
        size_summary = (
            f"{sizes.get('checked', 0)} peças consultadas; "
            f"{sizes.get('changed', 0)} com alteração; "
            f"{len(sizes.get('failures') or [])} falhas."
        )

    scan_summary = "Ainda não há varredura de novas peças registrada."
    scan_link = ""
    if scan:
        scan_summary = (
            f"{scan.get('groupCount', 0)} grupos, "
            f"{scan.get('highConfidenceGroupCount', 0)} com alta confiança e "
            f"{scan.get('individualCount', 0)} peças para análise individual."
        )
        day = scan_path.stem.replace("varredura-fornecedor-agrupada-", "")
        candidate = ROOT / "previews" / "fornecedor-varreduras" / f"aprovacao-fornecedor-agrupado-{day}.html"
        if candidate.exists():
            scan_link = f'<a class="button" href="../{html.escape(relative_preview(candidate))}">Abrir relatório para aprovação</a>'

    html_page = f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>SCORSATTO — Painel diário</title><style>
body{{margin:0;background:#f5f2ec;color:#191816;font:16px Arial,sans-serif}}main{{max-width:940px;margin:0 auto;padding:52px 22px}}h1{{font:400 46px Georgia,serif;margin:0 0 8px}}.sub{{color:#69645c;margin-bottom:32px}}section{{background:#fff;border:1px solid #ded8cf;padding:26px;margin:16px 0}}h2{{font:400 28px Georgia,serif;margin:0 0 10px}}.tag{{font-size:12px;font-weight:bold;letter-spacing:.08em}}.ok{{color:#21633b}}.wait{{color:#895a12}}.button{{display:inline-block;margin-top:12px;background:#191816;color:#fff;padding:12px 16px;text-decoration:none;font-weight:bold}}small{{color:#69645c}}
</style></head><body><main>
<h1>Painel diário SCORSATTO</h1><p class="sub">Atualizado em {today_slug()}. Central exclusiva de automações internas.</p>
<section><div class="tag ok">01 · TAMANHOS E ESTOQUE</div><h2>Atualização automática segura</h2><p>{html.escape(size_summary)}</p><small>Somente sizes, stock e lastCheckedAt podem ser publicados automaticamente.</small></section>
<section><div class="tag wait">02 · NOVAS PEÇAS</div><h2>Curadoria aguardando sua aprovação</h2><p>{html.escape(scan_summary)}</p><small>Nenhuma peça é incluída no catálogo por esta rotina. Use o relatório para aprovar ou recusar candidatos.</small>{scan_link}</section>
</main></body></html>"""
    (AUTOMATIONS / "painel-relatorios-diarios.html").write_text(html_page, encoding="utf-8")
    print("Painel diário atualizado.")


if __name__ == "__main__":
    main()
