"""Generate the public SCORSATTO automation hub from daily machine-readable reports."""

import html
import json
from datetime import datetime, timedelta, timezone
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


def format_timestamp(value):
    if not value:
        return "Aguardando primeira execução"
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        local = parsed.astimezone(timezone(timedelta(hours=-3)))
        return local.strftime("%d/%m/%Y às %H:%M")
    except ValueError:
        return str(value)


def change_rows(sizes):
    rows = []
    state_labels = {"available": "Tamanhos alterados", "sold_out": "Esgotado confirmado", "removed": "Removido do fornecedor"}
    for change in (sizes or {}).get("changes") or []:
        rows.append(
            "<tr>"
            f"<td><strong>{html.escape(str(change.get('name') or change.get('id') or 'Peça sem nome'))}</strong></td>"
            f"<td>{html.escape(', '.join(change.get('oldSizes') or []) or 'Sem tamanho')}</td>"
            f"<td>{html.escape(', '.join(change.get('newSizes') or []) or 'Indisponível')}</td>"
            f"<td>{html.escape(state_labels.get(change.get('availabilityState'), 'Revisado'))}</td>"
            f"<td><a href=\"{html.escape(str(change.get('url') or '#'))}\" target=\"_blank\" rel=\"noreferrer\">Fornecedor ↗</a></td>"
            "</tr>"
        )
    return "".join(rows) or '<tr><td colspan="5" class="empty">Nenhuma alteração de tamanho nesta execução.</td></tr>'


def main():
    AUTOMATIONS.mkdir(parents=True, exist_ok=True)
    _, sizes = latest(SIZES, "atualizacao-tamanhos-*.json")
    scan_path, scan = latest(SCANS, "varredura-fornecedor-agrupada-*.json")
    checked = int((sizes or {}).get("checked") or 0)
    changed = int((sizes or {}).get("changed") or 0)
    failures = len((sizes or {}).get("failures") or [])
    applied = bool((sizes or {}).get("apply"))
    size_changes = (sizes or {}).get("changes") or []
    changed_sizes = sum(1 for item in size_changes if item.get("availabilityState") == "available")
    sold_out = sum(1 for item in size_changes if item.get("availabilityState") == "sold_out")
    removed = sum(1 for item in size_changes if item.get("availabilityState") == "removed")
    groups = int((scan or {}).get("groupCount") or 0)
    high_confidence = int((scan or {}).get("highConfidenceGroupCount") or 0)
    individual = int((scan or {}).get("individualCount") or 0)
    new_families = int((scan or {}).get("newFamilyCount") or 0)
    site_variations = int((scan or {}).get("existingFamilyVariationCount") or 0)
    new_on_site = len((scan or {}).get("newOnSite") or [])
    sizes_updated_at = format_timestamp((sizes or {}).get("generatedAt"))
    scan_updated_at = format_timestamp((scan or {}).get("generatedAt"))

    scan_link = '<span class="button disabled">Relatório disponível após a primeira varredura</span>'
    if scan_path:
        day = scan_path.stem.replace("varredura-fornecedor-agrupada-", "")
        candidate = ROOT / "previews" / "fornecedor-varreduras" / f"aprovacao-fornecedor-agrupado-{day}.html"
        if candidate.exists():
            scan_link = '<a class="button" href="../fornecedor-varreduras/">Analisar a varredura mais recente <span>→</span></a>'

    html_page = f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>SCORSATTO | Central de automações</title><style>
:root{{--ink:#151515;--paper:#f2efe9;--line:#ded9cf;--muted:#79756d;--green:#55d995;--gold:#d9b46a;--surface:#fff;}}*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font:15px Arial,sans-serif}}.top{{background:#111;color:#fff;border-bottom:1px solid #343434}}.top-inner,main{{max-width:1240px;margin:auto;padding-left:28px;padding-right:28px}}.top-inner{{height:76px;display:flex;justify-content:space-between;align-items:center}}.brand{{display:flex;align-items:center;gap:12px;font-family:Georgia,serif;font-size:21px;letter-spacing:.12em}}.mark{{display:grid;place-items:center;width:31px;height:31px;border:1px solid #d6c29a;border-radius:50%;font:600 11px Arial;letter-spacing:0}}.live{{font-size:11px;font-weight:bold;letter-spacing:.12em;color:#c8c4bc}}.live i{{display:inline-block;width:7px;height:7px;border-radius:50%;background:var(--green);margin-right:7px;box-shadow:0 0 12px var(--green)}}main{{padding-top:38px;padding-bottom:56px}}.eyebrow{{margin:0 0 11px;color:#6d685e;font-size:11px;font-weight:bold;letter-spacing:.14em}}h1{{font:400 clamp(34px,5vw,58px)/1.02 Georgia,serif;margin:0;letter-spacing:-.04em}}.lead{{max-width:660px;margin:18px 0 22px;color:var(--muted);font-size:17px;line-height:1.55}}.freshness{{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 28px}}.freshness span{{background:#e7e2d8;border:1px solid #d6d0c4;padding:9px 11px;color:#625e56;font-size:11px;font-weight:700;letter-spacing:.02em}}.metrics{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:26px}}.metric{{background:var(--surface);border:1px solid var(--line);padding:18px;min-height:106px}}.metric strong{{display:block;font:400 37px/1 Georgia,serif}}.metric span{{display:block;margin-top:10px;color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:.07em}}.grid{{display:grid;grid-template-columns:1.4fr .9fr;gap:18px;align-items:start}}.panel{{background:var(--surface);border:1px solid var(--line)}}.panel-head{{padding:23px 24px;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;gap:15px;align-items:start}}.number{{color:#8b8478;font-size:11px;font-weight:bold;letter-spacing:.14em}}h2{{font:400 29px/1.1 Georgia,serif;margin:7px 0 0}}.status{{white-space:nowrap;border:1px solid #bde9d0;background:#effbf4;color:#1a7345;padding:7px 9px;font-size:10px;font-weight:bold;letter-spacing:.08em}}.body{{padding:23px 24px}}.rule{{margin:0 0 20px;color:var(--muted);line-height:1.5}}.change-summary{{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:18px}}.change-summary div{{border:1px solid var(--line);padding:14px}}.change-summary strong{{display:block;font:400 28px/1 Georgia,serif}}.change-summary span{{display:block;margin-top:7px;color:var(--muted);font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.06em}}details{{border-top:1px solid var(--line);padding-top:16px}}summary{{cursor:pointer;font-weight:700;list-style:none}}summary::after{{content:'+';float:right;font-size:20px}}details[open] summary::after{{content:'–'}}.table-scroll{{overflow:auto;margin-top:18px;max-height:520px}}table{{width:100%;border-collapse:collapse;font-size:13px}}th{{text-align:left;padding:0 10px 10px 0;color:#817b70;font-size:10px;letter-spacing:.1em;text-transform:uppercase}}td{{border-top:1px solid #ece9e2;padding:13px 10px 13px 0;vertical-align:top;color:#555148}}td strong{{color:var(--ink)}}td a{{color:var(--ink);font-weight:bold}}.empty{{color:var(--muted);text-align:center;padding:30px 0}}.action{{background:#171716;color:#fff;padding:28px;display:flex;flex-direction:column;min-height:100%}}.action .number{{color:#bbb4a8}}.action h2{{font-size:32px}}.action p{{color:#cbc7be;line-height:1.55;margin:16px 0 20px}}.queue{{display:grid;grid-template-columns:repeat(3,1fr);gap:9px;margin:5px 0 22px}}.queue div{{border:1px solid #4d4b47;padding:13px 9px}}.queue strong{{display:block;font:400 28px Georgia,serif;color:#fff}}.queue span{{display:block;margin-top:5px;color:#bcb7ac;font-size:9px;font-weight:bold;letter-spacing:.08em;text-transform:uppercase}}.button{{display:flex;justify-content:space-between;align-items:center;margin-top:auto;background:#e8d4a8;color:#171716;padding:15px;text-decoration:none;font-weight:bold}}.button span{{font-size:21px;line-height:0}}.button.disabled{{background:#363532;color:#aaa59d;font-size:12px;cursor:not-allowed}}.footnote{{margin:15px 0 0;color:#858077;font-size:11px;line-height:1.45}}@media(max-width:800px){{.top-inner,main{{padding-left:18px;padding-right:18px}}.metrics,.grid{{grid-template-columns:1fr 1fr}}.grid .panel:first-child{{grid-column:1/-1}}.panel-head{{padding:19px}}.body{{padding:19px}}}}@media(max-width:500px){{.metrics,.grid,.change-summary{{grid-template-columns:1fr}}.grid .panel:first-child{{grid-column:auto}}.live{{display:none}}.brand{{font-size:18px}}}}
.metrics{{grid-template-columns:repeat(5,1fr)}}@media(max-width:1000px){{.metrics{{grid-template-columns:repeat(3,1fr)}}}}@media(max-width:800px){{.metrics{{grid-template-columns:1fr 1fr}}}}@media(max-width:500px){{.metrics{{grid-template-columns:1fr}}}}
</style></head><body><header class="top"><div class="top-inner"><div class="brand"><span class="mark">SC</span>SCORSATTO</div><div class="live"><i></i>ROTINAS EM NUVEM</div></div></header><main>
<p class="eyebrow">CENTRAL DE INTELIGÊNCIA DE CATÁLOGO · {today_slug()}</p><h1>Seu catálogo, sob controle.</h1><p class="lead">Visão diária de estoque e curadoria. A rotina de tamanhos opera com segurança; novas peças aguardam exclusivamente a sua decisão.</p><div class="freshness"><span>Todos os dias · tamanhos 07:30</span><span>Todos os dias · novas peças 08:00</span><span>Tamanhos: {sizes_updated_at}</span><span>Curadoria: {scan_updated_at}</span></div>
<section class="metrics"><div class="metric"><strong>{checked}</strong><span>Peças consultadas</span></div><div class="metric"><strong>{changed}</strong><span>Mudanças confirmadas</span></div><div class="metric"><strong>{new_on_site}</strong><span>Novidades publicadas</span></div><div class="metric"><strong>{new_families}</strong><span>Novas famílias</span></div><div class="metric"><strong>{site_variations}</strong><span>Variações do site</span></div></section>
<section class="grid"><article class="panel"><header class="panel-head"><div><div class="number">01 · TAMANHOS & ESTOQUE</div><h2>O que mudou hoje</h2></div><span class="status">{('AUDITORIA' if not applied else ('ATENÇÃO' if failures else 'ATUALIZADO'))}</span></header><div class="body"><p class="rule">{checked} peças verificadas, {changed} alterações {('aplicadas' if applied else 'detectadas e ainda não aplicadas')} e {failures} falhas de consulta. Toda mudança exige duas leituras iguais; estoque próprio fica fora desta rotina.</p><div class="change-summary"><div><strong>{changed_sizes}</strong><span>Tamanhos alterados</span></div><div><strong>{sold_out}</strong><span>Esgotados confirmados</span></div><div><strong>{removed}</strong><span>Removidos do fornecedor</span></div></div><details><summary>Ver as {changed} alterações peça por peça</summary><div class="table-scroll"><table><thead><tr><th>Peça</th><th>Antes</th><th>Agora</th><th>Situação</th><th>Origem</th></tr></thead><tbody>{change_rows(sizes)}</tbody></table></div></details></div></article>
<article class="action"><div class="number">02 · NOVAS PEÇAS</div><h2>Curadoria que precisa da sua assinatura.</h2><p>As peças encontradas jamais entram no catálogo sozinhas. Abra a seleção, analise imagens, marca, modelo, tecido e variações; então aprove ou recuse.</p><div class="queue"><div><strong>{groups}</strong><span>Grupos</span></div><div><strong>{high_confidence}</strong><span>Prioridade</span></div><div><strong>{individual}</strong><span>Individuais</span></div></div>{scan_link}<p class="footnote">A aprovação no relatório é uma decisão de curadoria. Nenhuma publicação é feita automaticamente.</p></article></section>
</main></body></html>"""
    (AUTOMATIONS / "painel-relatorios-diarios.html").write_text(html_page, encoding="utf-8")
    print("Painel diário atualizado.")


if __name__ == "__main__":
    main()
