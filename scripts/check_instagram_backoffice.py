import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from supplier_common import ROOT, now_iso, today_slug


REPORT_DIR = ROOT / "data" / "automacoes" / "instagram"
PREVIEW_DIR = ROOT / "previews" / "automacoes"


def env(name, fallback=""):
    return (os.getenv(name) or fallback or "").strip()


def read_public_supabase_config():
    config = ROOT / "supabase" / "config.js"
    if not config.exists():
        return {}
    text = config.read_text(encoding="utf-8", errors="ignore")
    values = {}
    for key in ["SCORSATTO_SUPABASE_URL", "SCORSATTO_SUPABASE_ANON_KEY"]:
        marker = f"window.{key}"
        if marker not in text:
            continue
        part = text.split(marker, 1)[1].split(";", 1)[0]
        if '"' in part:
            values[key] = part.split('"', 2)[1]
    return values


def supabase_get(path, key):
    public = read_public_supabase_config()
    url = env("SCORSATTO_SUPABASE_URL", env("SUPABASE_URL", public.get("SCORSATTO_SUPABASE_URL", ""))).rstrip("/")
    if not url:
        raise RuntimeError("Supabase URL ausente.")
    if not key:
        raise RuntimeError("Chave Supabase ausente.")
    req = Request(
        f"{url}/rest/v1/{path.lstrip('/')}",
        headers={
            "apikey": key,
            "authorization": f"Bearer {key}",
            "accept": "application/json",
        },
    )
    with urlopen(req, timeout=25) as response:
        body = response.read().decode("utf-8")
        return json.loads(body) if body else []


def latest_sync_report():
    if not REPORT_DIR.exists():
        return None
    reports = sorted(REPORT_DIR.glob("instagram-sync-*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
    if not reports:
        return None
    try:
        payload = json.loads(reports[0].read_text(encoding="utf-8"))
        payload["_path"] = str(reports[0])
        return payload
    except Exception:
        return {"_path": str(reports[0]), "ok": False, "warnings": ["Relatorio de sync invalido."]}


def status_label(ok):
    return "OK" if ok else "PENDENTE"


def is_instagram_login_token(token):
    return (token or "").strip().startswith("IG")


def write_preview(payload):
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    path = PREVIEW_DIR / f"diagnostico-instagram-backoffice-{today_slug()}.html"
    checks = payload["checks"]
    rows = "\n".join(
        f"<tr><td>{item['name']}</td><td><strong class='{ 'ok' if item['ok'] else 'bad' }'>{status_label(item['ok'])}</strong></td><td>{item['detail']}</td></tr>"
        for item in checks
    )
    leads = payload.get("sampleLeads") or []
    lead_rows = "\n".join(
        f"<tr><td>{lead.get('name') or '-'}</td><td>{lead.get('handle') or '-'}</td><td>{lead.get('source') or '-'}</td><td>{lead.get('score') or 0}</td><td>{lead.get('updated_at') or lead.get('last_interaction_at') or '-'}</td></tr>"
        for lead in leads
    ) or "<tr><td colspan='5'>Nenhum lead real retornado ainda.</td></tr>"
    html = f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Diagnostico Instagram SCORSATTO</title>
  <style>
    body {{ margin: 28px; font-family: Arial, sans-serif; color: #111; background: #f7f7f5; }}
    h1 {{ font-family: Georgia, serif; font-size: 44px; font-weight: 400; margin: 0 0 8px; }}
    section {{ background: #fff; border: 1px solid #ddd; padding: 16px; margin: 14px 0; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{ border-top: 1px solid #ddd; padding: 10px; text-align: left; vertical-align: top; }}
    th {{ font-size: 11px; letter-spacing: .08em; text-transform: uppercase; color: #666; }}
    .ok {{ color: #1c5b37; }}
    .bad {{ color: #8d2c22; }}
    code {{ background: #f1f1ee; padding: 2px 4px; }}
  </style>
</head>
<body>
  <h1>Instagram + Backoffice</h1>
  <p>Gerado em {payload["generatedAt"]}. Este painel separa o que esta pronto do que falta configurar.</p>
  <section>
    <h2>Status</h2>
    <table><thead><tr><th>Item</th><th>Status</th><th>Detalhe</th></tr></thead><tbody>{rows}</tbody></table>
  </section>
  <section>
    <h2>Amostra de leads reais</h2>
    <table><thead><tr><th>Nome</th><th>@</th><th>Origem</th><th>Score</th><th>Atualizado</th></tr></thead><tbody>{lead_rows}</tbody></table>
  </section>
  <section>
    <h2>Proximo passo</h2>
    <p>{payload["nextStep"]}</p>
  </section>
</body>
</html>"""
    path.write_text(html, encoding="utf-8")
    return path


def main():
    public = read_public_supabase_config()
    anon_key = public.get("SCORSATTO_SUPABASE_ANON_KEY", "")
    service_key = env("SCORSATTO_SUPABASE_SERVICE_ROLE_KEY", env("SUPABASE_SERVICE_ROLE_KEY"))
    meta_token = env("META_ACCESS_TOKEN")
    meta_ig = env("META_INSTAGRAM_BUSINESS_ID", env("META_IG_USER_ID"))
    meta_page = env("META_PAGE_ID")
    checks = []
    sample = []

    checks.append({"name": "Supabase publico no site", "ok": bool(public.get("SCORSATTO_SUPABASE_URL") and anon_key), "detail": public.get("SCORSATTO_SUPABASE_URL", "config.js sem URL")})
    checks.append({"name": "Token oficial Meta", "ok": bool(meta_token), "detail": "Configurado" if meta_token else "Falta META_ACCESS_TOKEN"})
    checks.append({"name": "Instagram Business ID", "ok": bool(meta_ig), "detail": meta_ig or "Falta META_INSTAGRAM_BUSINESS_ID"})
    page_optional = is_instagram_login_token(meta_token)
    checks.append({
        "name": "Pagina Facebook vinculada",
        "ok": bool(meta_page) or page_optional,
        "detail": meta_page or ("Opcional para comentarios com Instagram Login; necessario para DMs/webhook." if page_optional else "Falta META_PAGE_ID"),
    })
    checks.append({"name": "Service role para gravar leads", "ok": bool(service_key), "detail": "Configurado" if service_key else "Falta SCORSATTO_SUPABASE_SERVICE_ROLE_KEY"})

    db_key = service_key or anon_key
    try:
        sample = supabase_get("instagram_leads?select=name,handle,source,score,updated_at,last_interaction_at&order=updated_at.desc&limit=10", db_key)
        checks.append({"name": "Tabela instagram_leads", "ok": True, "detail": f"{len(sample)} lead(s) retornado(s) na amostra."})
    except HTTPError as exc:
        checks.append({"name": "Tabela instagram_leads", "ok": False, "detail": f"Erro HTTP {exc.code}. Rode supabase/backoffice-instagram-complete.sql no SQL Editor."})
    except (URLError, RuntimeError, Exception) as exc:
        checks.append({"name": "Tabela instagram_leads", "ok": False, "detail": str(exc)})

    sync = latest_sync_report()
    if sync:
        checks.append({"name": "Relatorio diario Instagram", "ok": bool(sync.get("ok")), "detail": f"{sync.get('_path')} | encontrados: {sync.get('found', 0)} | importados: {sync.get('imported', 0)} | avisos: {', '.join(sync.get('warnings', [])[:2])}"})
    else:
        checks.append({"name": "Relatorio diario Instagram", "ok": False, "detail": "Nenhum instagram-sync-AAAA-MM-DD.json encontrado."})

    all_ok = all(item["ok"] for item in checks[:6])
    has_token_and_ig = bool(meta_token and meta_ig)
    sync_found = int((sync or {}).get("found") or 0)
    if all_ok:
        next_step = "Tudo pronto: a rotina diaria deve alimentar a aba Instagram com leads reais."
    elif has_token_and_ig and sync_found:
        next_step = "Instagram conectado e leads reais encontrados. Falta configurar SCORSATTO_SUPABASE_SERVICE_ROLE_KEY para gravar automaticamente no backoffice."
    elif has_token_and_ig:
        next_step = "Instagram conectado. Rode scripts/run_daily_automation.ps1 para buscar comentarios recentes; configure SCORSATTO_SUPABASE_SERVICE_ROLE_KEY para gravar no backoffice."
    else:
        next_step = "Configure META_ACCESS_TOKEN e META_INSTAGRAM_BUSINESS_ID para gerar nomes/@ reais automaticamente."
    payload = {
        "generatedAt": now_iso(),
        "ok": all_ok,
        "checks": checks,
        "sampleLeads": sample,
        "nextStep": next_step,
    }
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report = REPORT_DIR / f"instagram-backoffice-check-{today_slug()}.json"
    report.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    preview = write_preview(payload)
    print(json.dumps({"report": str(report), "preview": str(preview), "ok": payload["ok"], "nextStep": next_step}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
