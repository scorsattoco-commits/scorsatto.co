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


def change_rows(sizes):
    rows = []
    for change in (sizes or {}).get("changes") or []:
        rows.append(
            "<tr>"
            f"<td><strong>{html.escape(str(change.get('name') or change.get('id') or 'Peça sem nome'))}</strong></td>"
            f"<td>{html.escape(', '.join(change.get('oldSizes') or []) or 'Sem tamanho')}</td>"
            f"<td>{html.escape(', '.join(change.get('newSizes') or []) or 'Indisponível')}</td>"
            f"<td><a href=\"{html.escape(str(change.get('url') or '#'))}\" target=\"_blank\" rel=\"noreferrer\">Fornecedor ↗</a></td>"
            "</tr>"
        )
    return "".join(rows) or '<tr><td colspan="4" class="empty">Nenhuma alteração de tamanho nesta execução.</td></tr>'


def main():
    AUTOMATIONS.mkdir(parents=True, exist_ok=True)
    _, sizes = latest(SIZES, "atualizacao-tamanhos-*.json")
    scan_path, scan = latest(SCANS, "varredura-fornecedor-agrupada-*.json")
    checked = int((sizes or {}).get("checked") or 0)
    changed = int((sizes or {}).get("changed") or 0)
    failures = len((sizes or {}).get("failures") or [])
    groups = int((scan or {}).get("groupCount") or 0)
    high_confidence = int((scan or {}).get("highConfidenceGroupCount") or 0)
    individual = int((scan or {}).get("individualCount") or 0)

    scan_link = '<span class="button disabled">Relatório disponível após a primeira varredura</span>'
    if scan_path:
        day = scan_path.stem.replace("varredura-fornecedor-agrupada-", "")
        candidate = ROOT / "previews" / "fornecedor-varreduras" / f"aprovacao-fornecedor-agrupado-{day}.html"
        if candidate.exists():
            scan_link = f'<a class="button" href="../{html.escape(relative_preview(candidate))}">Analisar e decidir peças <span>→</span></a>'

    html_page = f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>SCORSATTO | Central de automações</title><style>
:root{{--ink:#151515;--paper:#f2efe9;--line:#ded9cf;--muted:#79756d;--green:#55d995;--gold:#d9b46a;--surface:#fff;}}*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font:15px Arial,sans-serif}}.top{{background:#111;color:#fff;border-bottom:1px solid #343434}}.top-inner,main{{max-width:1240px;margin:auto;padding-left:28px;padding-right:28px}}.top-inner{{height:76px;display:flex;justify-content:space-between;align-items:center}}.brand{{display:flex;align-items:center;gap:12px;font-family:Georgia,serif;font-size:21px;letter-spacing:.12em}}.mark{{display:grid;place-items:center;width:31px;height:31px;border:1px solid #d6c29a;border-radius:50%;font:600 11px Arial;letter-spacing:0}}.live{{font-size:11px;font-weight:bold;letter-spacing:.12em;color:#c8c4bc}}.live i{{display:inline-block;width:7px;height:7px;border-radius:50%;background:var(--green);margin-right:7px;box-shadow:0 0 12px var(--green)}}main{{padding-top:38px;padding-bottom:56px}}.eyebrow{{margin:0 0 11px;color:#6d685e;font-size:11px;font-weight:bold;letter-spacing:.14em}}h1{{font:400 clamp(34px,5vw,58px)/1.02 Georgia,serif;margin:0;letter-spacing:-.04em}}.lead{{max-width:660px;margin:18px 0 32px;color:var(--muted);font-size:17px;line-height:1.55}}.metrics{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:26px}}.metric{{background:var(--surface);border:1px solid var(--line);padding:18px;min-height:106px}}.metric strong{{display:block;font:400 37px/1 Georgia,serif}}.metric span{{display:block;margin-top:10px;color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:.07em}}.grid{{display:grid;grid-template-columns:1.4fr .9fr;gap:18px}}.panel{{background:var(--surface);border:1px solid var(--line)}}.panel-head{{padding:23px 24px;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;gap:15px;align-items:start}}.number{{color:#8b8478;font-size:11px;font-weight:bold;letter-spacing:.14em}}h2{{font:400 29px/1.1 Georgia,serif;margin:7px 0 0}}.status{{white-space:nowrap;border:1px solid #bde9d0;background:#effbf4;color:#1a7345;padding:7px 9px;font-size:10px;font-weight:bold;letter-spacing:.08em}}.body{{padding:23px 24px}}.rule{{margin:0 0 20px;color:var(--muted);line-height:1.5}}table{{width:100%;border-collapse:collapse;font-size:13px}}th{{text-align:left;padding:0 10px 10px 0;color:#817b70;font-size:10px;letter-spacing:.1em;text-transform:uppercase}}td{{border-top:1px solid #ece9e2;padding:13px 10px 13px 0;vertical-align:top;color:#555148}}td strong{{color:var(--ink)}}td a{{color:var(--ink);font-weight:bold}}.empty{{color:var(--muted);text-align:center;padding:30px 0}}.action{{background:#171716;color:#fff;padding:28px;display:flex;flex-direction:column;min-height:100%}}.action .number{{color:#bbb4a8}}.action h2{{font-size:32px}}.action p{{color:#cbc7be;line-height:1.55;margin:16px 0 20px}}.queue{{display:grid;grid-template-columns:repeat(3,1fr);gap:9px;margin:5px 0 22px}}.queue div{{border:1px solid #4d4b47;padding:13px 9px}}.queue strong{{display:block;font:400 28px Georgia,serif;color:#fff}}.queue span{{display:block;margin-top:5px;color:#bcb7ac;font-size:9px;font-weight:bold;letter-spacing:.08em;text-transform:uppercase}}.button{{display:flex;justify-content:space-between;align-items:center;margin-top:auto;background:#e8d4a8;color:#171716;padding:15px;text-decoration:none;font-weight:bold}}.button span{{font-size:21px;line-height:0}}.button.disabled{{background:#363532;color:#aaa59d;font-size:12px;cursor:not-allowed}}.footnote{{margin:15px 0 0;color:#858077;font-size:11px;line-height:1.45}}@media(max-width:800px){{.top-inner,main{{padding-left:18px;padding-right:18px}}.metrics,.grid{{grid-template-columns:1fr 1fr}}.grid .panel:first-child{{grid-column:1/-1}}.panel-head{{padding:19px}}.body{{padding:19px}}}}@media(max-width:500px){{.metrics,.grid{{grid-template-columns:1fr}}.grid .panel:first-child{{grid-column:auto}}.live{{display:none}}.brand{{font-size:18px}}}}
</style></head><body><header class="top"><div class="top-inner"><div class="brand"><span class="mark">SC</span>SCORSATTO</div><div class="live"><i></i>ROTINAS EM NUVEM</div></div></header><main>
<p class="eyebrow">CENTRAL DE INTELIGÊNCIA DE CATÁLOGO · {today_slug()}</p><h1>Seu catálogo, sob controle.</h1><p class="lead">Visão diária de estoque e curadoria. A rotina de tamanhos opera com segurança; novas peças aguardam exclusivamente a sua decisão.</p>
<section class="metrics"><div class="metric"><strong>{checked}</strong><span>Peças consultadas</span></div><div class="metric"><strong>{changed}</strong><span>Alterações de tamanho</span></div><div class="metric"><strong>{groups}</strong><span>Grupos para curadoria</span></div><div class="metric"><strong>{high_confidence}</strong><span>Alta afinidade SCORSATTO</span></div></section>
<section class="grid"><article class="panel"><header class="panel-head"><div><div class="number">01 · TAMANHOS & ESTOQUE</div><h2>O que mudou hoje</h2></div><span class="status">{('ATENÇÃO' if failures else 'ATUALIZADO')}</span></header><div class="body"><p class="rule">{checked} peças verificadas, {changed} atualizações aplicadas e {failures} falhas de consulta. A automação só pode alterar tamanhos, estoque e data de conferência.</p><table><thead><tr><th>Peça</th><th>Antes</th><th>Agora</th><th>Origem</th></tr></thead><tbody>{change_rows(sizes)}</tbody></table></div></article>
<article class="action"><div class="number">02 · NOVAS PEÇAS</div><h2>Curadoria que precisa da sua assinatura.</h2><p>As peças encontradas jamais entram no catálogo sozinhas. Abra a seleção, analise imagens, marca, modelo, tecido e variações; então aprove ou recuse.</p><div class="queue"><div><strong>{groups}</strong><span>Grupos</span></div><div><strong>{high_confidence}</strong><span>Prioridade</span></div><div><strong>{individual}</strong><span>Individuais</span></div></div>{scan_link}<p class="footnote">A aprovação no relatório é uma decisão de curadoria. Nenhuma publicação é feita automaticamente.</p></article></section>
</main></body></html>"""
    (AUTOMATIONS / "painel-relatorios-diarios.html").write_text(html_page, encoding="utf-8")
    print("Painel diário atualizado.")


if __name__ == "__main__":
    main()
