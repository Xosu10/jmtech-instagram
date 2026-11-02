// No Instagram credentials or private media belong in this service.
const REPO = "Xosu10/jmtech-instagram";
const TYPES = [
  ["reel", "reels", "hora_reel", "publicar-reel.yml"],
  ["curiosidad", "curiosidades", "hora_curiosidad", "publicar-curiosidad.yml"],
  ["noticias", "noticias", "hora_noticias", "publicar-noticias.yml"],
];

export function madrid(now) {
  const parts = Object.fromEntries(new Intl.DateTimeFormat("en-CA", {
    timeZone: "Europe/Madrid", year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", hourCycle: "h23",
  }).formatToParts(now).map(p => [p.type, p.value]));
  const date = `${parts.year}-${parts.month}-${parts.day}`;
  return {date, minute: Number(parts.hour) * 60 + Number(parts.minute),
    weekday: new Date(`${date}T12:00:00Z`).getUTCDay()};
}

export function plan(config, state, now) {
  const local = madrid(now);
  if (config.pausado) return [];
  return TYPES.flatMap(([type, enabled, time, workflow]) => {
    if (config[enabled] === false) return [];
    if (type === "reel" && (local.weekday === 0 || local.weekday === 6 ||
      local.date < config.fecha_inicio || config.dias_sin_publicar?.includes(local.date))) return [];
    if (type === "noticias" && local.weekday !== 0) return [];
    if (state.publicaciones.some(p => p.fecha === local.date && p.tipo === type &&
      p.resultado === "publicado" && !p.prueba)) return [];
    const [hour, minute] = config[time].split(":").map(Number);
    const late = local.minute - hour * 60 - minute;
    if (late < 0) return [];
    return [{type, workflow, date: local.date, late, overdue: late >= 90}];
  });
}

async function github(env, path, init = {}, fetcher = fetch) {
  const response = await fetcher(`https://api.github.com/repos/${REPO}/${path}`, {
    ...init,
    headers: {Authorization: `Bearer ${env.GITHUB_DISPATCH_TOKEN}`,
      "User-Agent": "jmtech-scheduler", Accept: "application/vnd.github+json",
      "Content-Type": "application/json", ...init.headers},
    redirect: "manual", signal: AbortSignal.timeout(15000),
  });
  if (!response.ok) throw new Error(`GitHub HTTP ${response.status}`);
  return response.status === 204 ? null : response.json();
}

async function file(env, path, fetcher) {
  const data = await github(env, `contents/${path}?ref=main`, {}, fetcher);
  const bytes = Uint8Array.from(atob(data.content.replace(/\s/g, "")), c => c.charCodeAt(0));
  return JSON.parse(new TextDecoder().decode(bytes));
}

export async function reconcile(env, {dispatch = false, now = new Date(), fetcher = fetch} = {}) {
  if (!env.GITHUB_DISPATCH_TOKEN) throw new Error("Missing GitHub dispatch credential");
  const [config, state] = await Promise.all([
    file(env, "config/calendario.json", fetcher), file(env, "estado/publicaciones.json", fetcher),
  ]);
  const results = plan(config, state, now);
  for (const item of results) {
    if (item.overdue || !dispatch) continue;
    const data = await github(env, `actions/workflows/${item.workflow}/runs?per_page=100`, {}, fetcher);
    // Suppress duplicate dispatches while a run is queued/running, and allow
    // retries of failed/empty runs after ten minutes. The workflow also has
    // a per-type concurrency lock and rechecks persisted publication state.
    const active = data.workflow_runs.some(r => r.head_branch === "main" &&
      ["schedule", "workflow_dispatch"].includes(r.event) &&
      new Date(r.created_at).getTime() >= now.getTime() - 86400000 &&
      (r.status !== "completed" || new Date(r.created_at).getTime() > now.getTime() - 600000));
    if (active) { item.action = "waiting"; continue; }
    await github(env, `actions/workflows/${item.workflow}/dispatches`, {
      method: "POST", body: JSON.stringify({ref: "main", inputs: {
        dry_run: false, ignorar_hora: false, fecha_objetivo: item.date,
      }}),
    }, fetcher);
    item.action = "dispatched";
  }
  return results;
}

export default {
  async scheduled(event, env, ctx) {
    if (env.ENABLED !== "1") return;
    const results = await reconcile(env, {dispatch: true});
    console.log(JSON.stringify({checked: new Date().toISOString(), results}));
    if (results.some(r => r.overdue)) throw new Error("Missing expected Instagram publication; inspect /health");
  },
  async fetch(request, env) {
    if (new URL(request.url).pathname !== "/health" || request.method !== "GET")
      return new Response("Not found", {status: 404});
    if (env.ENABLED !== "1") return Response.json({status: "disabled"}, {status: 503});
    try {
      const pending = await reconcile(env);
      return Response.json({status: pending.some(r => r.overdue) ? "missing_publication" : "ok", pending},
        {status: pending.some(r => r.overdue) ? 503 : 200, headers: {"Cache-Control": "no-store"}});
    } catch (e) {
      console.error("health check failed", e && e.stack || String(e));
      return Response.json({status: "check_failed"}, {status: 503, headers: {"Cache-Control": "no-store"}});
    }
  },
};
