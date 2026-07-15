import { serve } from "https://deno.land/std@0.224.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const supabaseUrl = Deno.env.get("SUPABASE_URL") || "";
const serviceRoleKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";
const verifyToken = Deno.env.get("META_WEBHOOK_VERIFY_TOKEN") || "";

const db = createClient(supabaseUrl, serviceRoleKey);

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function leadFromChange(entry: any, change: any) {
  const value = change?.value || {};
  const from = value.from || value.sender || value.user || {};
  const externalId = String(from.id || value.id || entry.id || crypto.randomUUID());
  const username = from.username || value.username || "";
  const text = value.text || value.message || value.comment || value.caption || "";
  const field = change?.field || "instagram";
  const source = field.includes("comment") ? "comentou" : field.includes("message") ? "mandou DM" : "interagiu";
  return {
    external_id: externalId,
    handle: username ? `@${String(username).replace(/^@/, "")}` : "",
    name: from.name || "",
    source,
    origin: field,
    context: text,
    note: text,
    raw: { entry, change },
    last_interaction_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  };
}

function leadFromMessaging(entry: any, event: any) {
  const sender = event?.sender || event?.from || {};
  const message = event?.message || event?.postback || event?.referral || {};
  const externalId = String(sender.id || event?.id || crypto.randomUUID());
  const text = message.text || message.title || message.ref || "";
  return {
    external_id: externalId,
    handle: sender.username ? `@${String(sender.username).replace(/^@/, "")}` : "",
    name: sender.name || "",
    source: "mandou DM",
    origin: "messages",
    context: text,
    note: text,
    raw: { entry, messaging: event },
    last_interaction_at: new Date(Number(event?.timestamp) || Date.now()).toISOString(),
    updated_at: new Date().toISOString(),
  };
}

serve(async (req) => {
  const url = new URL(req.url);

  if (req.method === "GET") {
    const mode = url.searchParams.get("hub.mode");
    const token = url.searchParams.get("hub.verify_token");
    const challenge = url.searchParams.get("hub.challenge");
    if (mode === "subscribe" && token === verifyToken && challenge) {
      return new Response(challenge, { status: 200 });
    }
    return new Response("Forbidden", { status: 403 });
  }

  if (req.method !== "POST") return json({ error: "method_not_allowed" }, 405);

  const payload = await req.json().catch(() => null);
  if (!payload?.entry?.length) return json({ ok: true, ignored: true });

  const leads = payload.entry.flatMap((entry: any) => [
    ...(entry.changes || []).map((change: any) => leadFromChange(entry, change)),
    ...(entry.messaging || []).map((event: any) => leadFromMessaging(entry, event)),
  ]);

  if (leads.length) {
    const { error } = await db
      .from("instagram_leads")
      .upsert(leads, { onConflict: "external_id" });
    if (error) return json({ error: error.message }, 500);
  }

  return json({ ok: true, imported: leads.length });
});
