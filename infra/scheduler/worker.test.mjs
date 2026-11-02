import test from "node:test";
import assert from "node:assert/strict";
import {plan, madrid, reconcile} from "./worker.mjs";

const cfg = {fecha_inicio: "2026-11-02", hora_reel: "15:00", hora_curiosidad: "17:00", hora_noticias: "19:00", reels: true, curiosidades: true, noticias: true};
const empty = {publicaciones: []};
test("Madrid uses winter and summer offsets", () => {
  assert.equal(madrid(new Date("2026-11-02T14:00Z")).minute, 900);
  assert.equal(madrid(new Date("2027-04-05T13:00Z")).minute, 900);
});
test("only due publications; no early dispatch", () => {
  assert.deepEqual(plan(cfg, empty, new Date("2026-11-02T13:59Z")), []);
  assert.equal(plan(cfg, empty, new Date("2026-11-02T14:00Z"))[0].type, "reel");
});
test("after 90 min report overdue instead of publishing late", () => {
  assert.equal(plan(cfg, empty, new Date("2026-11-02T15:30Z"))[0].overdue, true);
});
test("actual records count, test publications do not", () => {
  const state = {publicaciones: [{fecha: "2026-11-02", tipo: "reel", resultado: "publicado", prueba: true}]};
  assert.equal(plan(cfg, state, new Date("2026-11-02T14:00Z")).length, 1);
  state.publicaciones[0].prueba = false;
  assert.equal(plan(cfg, state, new Date("2026-11-02T14:00Z")).length, 0);
});
test("pause, weekdays, holidays and Sunday news respected", () => {
  assert.deepEqual(plan({...cfg, pausado: true}, empty, new Date("2026-11-02T14:00Z")), []);
  assert.equal(plan(cfg, empty, new Date("2026-11-08T14:00Z")).length, 0);
  assert.equal(plan({...cfg, dias_sin_publicar:["2026-11-02"]}, empty, new Date("2026-11-02T14:00Z")).length, 0);
});

test("dispatch carries target date; health checks never dispatch", async () => {
  const requests = [];
  const fetcher = async (url, init) => {
    requests.push([url, init]);
    if (url.includes("dispatches")) return new Response(null, {status: 204});
    const data = url.includes("calendario.json") ? {content:btoa(JSON.stringify(cfg))} : url.includes("publicaciones.json") ? {content:btoa(JSON.stringify(empty))} : {workflow_runs: []};
    return Response.json(data);
  };
  const opts = {now:new Date("2026-11-02T14:00Z"), fetcher};
  await reconcile({GITHUB_DISPATCH_TOKEN:"test"}, opts);
  assert.equal(requests.length, 2);
  const result = await reconcile({GITHUB_DISPATCH_TOKEN:"test"}, {...opts, dispatch:true});
  assert.equal(result[0].action,"dispatched");
  const body=JSON.parse(requests.at(-1)[1].body);
  assert.deepEqual(body.inputs,{dry_run:false,ignorar_hora:false,fecha_objetivo:"2026-11-02"});
});
