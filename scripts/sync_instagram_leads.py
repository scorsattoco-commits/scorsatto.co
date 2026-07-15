import datetime as dt
import json
import os
import re
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from supplier_common import ROOT, today_slug


GRAPH_VERSION = os.getenv("META_GRAPH_VERSION", "v21.0")
GRAPH_BASE = f"https://graph.facebook.com/{GRAPH_VERSION}"
REPORT_DIR = ROOT / "data" / "automacoes" / "instagram"


def clean(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def now_iso():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def env(name, fallback=""):
    return clean(os.getenv(name) or fallback)


def graph_get(path, token, params=None):
    query = {"access_token": token, **(params or {})}
    url = f"{GRAPH_BASE}/{path.lstrip('/')}?{urlencode(query)}"
    req = Request(url, headers={"User-Agent": "SCORSATTO Instagram Sync"})
    with urlopen(req, timeout=35) as response:
        return json.loads(response.read().decode("utf-8"))


def supabase_request(path, service_key, method="GET", body=None):
    supabase_url = env("SCORSATTO_SUPABASE_URL", env("SUPABASE_URL")).rstrip("/")
    if not supabase_url or not service_key:
        raise RuntimeError("Supabase URL/service role key ausentes.")
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = Request(
        f"{supabase_url}/rest/v1/{path.lstrip('/')}",
        data=data,
        method=method,
        headers={
            "apikey": service_key,
            "authorization": f"Bearer {service_key}",
            "content-type": "application/json",
            "prefer": "resolution=merge-duplicates,return=representation",
        },
    )
    with urlopen(req, timeout=35) as response:
        text = response.read().decode("utf-8")
        return json.loads(text) if text else []


def score_lead(item):
    score = 20
    text = " ".join([item.get("city", ""), item.get("source", ""), item.get("context", ""), item.get("note", "")]).lower()
    if any(city in text for city in ["serafina", "marau", "casca"]):
        score += 25
    if any(word in text for word in ["preco", "preço", "valor", "tamanho", "comprar", "disponivel", "disponível"]):
        score += 35
    if any(word in text for word in ["story", "dm", "mensagem", "coment"]):
        score += 15
    return min(score, 100)


def normalize_handle(value):
    value = clean(value).replace("@", "")
    return f"@{value}" if value else ""


def lead_from_comment(media, comment):
    username = clean(comment.get("username"))
    text = clean(comment.get("text"))
    external_id = f"ig-comment:{comment.get('id') or username or media.get('id')}"
    return {
        "external_id": external_id,
        "handle": normalize_handle(username),
        "name": username,
        "city": "",
        "source": "comentou no Instagram",
        "origin": "graph_media_comments",
        "context": text,
        "note": f"Comentario em post: {text}" if text else "Comentario em post da SCORSATTO.",
        "status": "Novo",
        "raw": {"media": media, "comment": comment},
        "last_interaction_at": comment.get("timestamp") or media.get("timestamp") or now_iso(),
        "updated_at": now_iso(),
    }


def lead_from_conversation(conversation):
    participants = conversation.get("participants", {}).get("data", [])
    messages = conversation.get("messages", {}).get("data", [])
    person = next((item for item in participants if clean(item.get("username") or item.get("name"))), {})
    message = messages[0] if messages else {}
    text = clean(message.get("message"))
    handle = normalize_handle(person.get("username"))
    external_id = f"ig-dm:{conversation.get('id') or handle or person.get('id')}"
    return {
        "external_id": external_id,
        "handle": handle,
        "name": clean(person.get("name") or person.get("username")),
        "city": "",
        "source": "mandou DM no Instagram",
        "origin": "graph_conversations",
        "context": text,
        "note": text or "Conversa aberta no Instagram.",
        "status": "Novo",
        "raw": {"conversation": conversation},
        "last_interaction_at": conversation.get("updated_time") or message.get("created_time") or now_iso(),
        "updated_at": now_iso(),
    }


def fetch_comment_leads(token, ig_user_id):
    if not ig_user_id:
        return [], ["META_INSTAGRAM_BUSINESS_ID nao configurado; comentarios nao sincronizados."]
    media_payload = graph_get(
        f"{ig_user_id}/media",
        token,
        {"fields": "id,caption,comments_count,like_count,timestamp,permalink", "limit": "12"},
    )
    leads = []
    warnings = []
    for media in media_payload.get("data", []):
        if int(media.get("comments_count") or 0) <= 0:
            continue
        try:
            comments = graph_get(
                f"{media['id']}/comments",
                token,
                {"fields": "id,text,username,timestamp,like_count", "limit": "50"},
            )
            leads.extend(lead_from_comment(media, comment) for comment in comments.get("data", []))
        except Exception as exc:
            warnings.append(f"Falha ao ler comentarios da midia {media.get('id')}: {exc}")
    return leads, warnings


def fetch_conversation_leads(token, page_id):
    if not page_id:
        return [], ["META_PAGE_ID nao configurado; conversas Instagram nao sincronizadas."]
    payload = graph_get(
        f"{page_id}/conversations",
        token,
        {
            "platform": "instagram",
            "fields": "id,updated_time,participants,messages.limit(3){message,from,created_time}",
            "limit": "25",
        },
    )
    return [lead_from_conversation(item) for item in payload.get("data", [])], []


def merge_by_external_id(rows):
    merged = {}
    for row in rows:
        key = row.get("external_id")
        if not key:
            continue
        row["score"] = score_lead(row)
        merged[key] = {**merged.get(key, {}), **row}
    return list(merged.values())


def write_report(payload):
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / f"instagram-sync-{today_slug()}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def main():
    token = env("META_ACCESS_TOKEN")
    page_id = env("META_PAGE_ID")
    ig_user_id = env("META_INSTAGRAM_BUSINESS_ID", env("META_IG_USER_ID"))
    service_key = env("SCORSATTO_SUPABASE_SERVICE_ROLE_KEY", env("SUPABASE_SERVICE_ROLE_KEY"))
    warnings = []
    if not token:
        payload = {
            "ok": False,
            "generatedAt": now_iso(),
            "imported": 0,
            "warnings": ["META_ACCESS_TOKEN nao configurado. Nao da para puxar nomes/@ reais da Meta sem token oficial."],
            "requiredEnv": ["META_ACCESS_TOKEN", "META_INSTAGRAM_BUSINESS_ID", "META_PAGE_ID", "SCORSATTO_SUPABASE_SERVICE_ROLE_KEY"],
        }
        path = write_report(payload)
        print(json.dumps({"report": str(path), **payload}, ensure_ascii=False, indent=2))
        return 0

    leads = []
    comment_leads, comment_warnings = fetch_comment_leads(token, ig_user_id)
    conversation_leads, conversation_warnings = fetch_conversation_leads(token, page_id)
    warnings.extend(comment_warnings)
    warnings.extend(conversation_warnings)
    leads = merge_by_external_id([*comment_leads, *conversation_leads])

    if leads and service_key:
        supabase_request("instagram_leads?on_conflict=external_id", service_key, method="POST", body=leads)
    elif leads:
        warnings.append("SCORSATTO_SUPABASE_SERVICE_ROLE_KEY ausente; leads encontrados, mas nao gravados no Supabase.")

    payload = {
        "ok": True,
        "generatedAt": now_iso(),
        "imported": len(leads) if service_key else 0,
        "found": len(leads),
        "comments": len(comment_leads),
        "conversations": len(conversation_leads),
        "warnings": warnings,
        "sample": leads[:10],
    }
    path = write_report(payload)
    print(json.dumps({"report": str(path), **payload}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
