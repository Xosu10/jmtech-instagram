"""Paquete para subir a TikTok a mano: vídeos con nombre ordenado + calendario HTML con las descripciones.

python -m jmtech.tiktok preparar --carpeta C:\\Users\\xosu1\\Documents\\TikTok --hasta 2027-01-31

Crea en la carpeta: calendario.html (se abre con doble clic), calendario.csv y la subcarpeta videos/ con un mp4 por día y tipo
(reel de las 15:00 y curiosidad de las 17:00). Si un vídeo ya existe, no se vuelve a crear.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import unicodedata
from datetime import date, datetime
from pathlib import Path

from .assets import cargar_catalogo, indice
from .base import RAIZ
from .calendario import cargar_config, planificar
from .contenido import indice_temas, pie_de_foto
from .curiosidad import CARPETA_ESPECS, cargar_cola, cargar_espec, construir_descripcion

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


# ---------- Textos ----------
def a_tiktok(texto: str) -> str:
    """Adapta un pie de Instagram a TikTok: allí no hay «MD», se escribe por mensaje directo."""
    return re.sub(r"\bMD\b", "mensaje directo", texto)


def slug(texto: str, largo: int = 48) -> str:
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:largo].strip("-")


# ---------- Entradas del calendario ----------
def _entradas_reels(hasta: date, cfg, catalogo, musica_dir):
    from .publicador import elegir_musica

    idx = indice(catalogo)
    temas = indice_temas()
    salida = []
    for p in planificar(hasta, cfg, catalogo=catalogo):
        if p.tipo == "campana":
            continue
        t = temas[p.tema_id]
        pista, inicio = elegir_musica(p.fecha, musica_dir)
        salida.append(dict(fecha=p.fecha.isoformat(), hora=cfg["hora_reel"], tipo="reel", titulo=f"Reel diario · {t['nombre']}",
                           base=f"{p.fecha.isoformat()}_{cfg['hora_reel'].replace(':', '')}_reel_{slug(p.tema_id)}",
                           descripcion=a_tiktok(pie_de_foto(t, p.variante)), tema=t, asset=idx.get(p.asset), pista=pista, inicio=inicio))
    return salida


def _entradas_publicadas_hoy(catalogo, musica_dir):
    """Los reels que se subieron a Instagram el 31 de octubre de 2026 (solo el último de cada servicio)."""
    from .estado import cargar
    from .publicador import elegir_musica

    idx = indice(catalogo)
    temas = indice_temas()
    por_tema = {}
    for p in cargar()["publicaciones"]:
        if p.get("tipo") == "reel" and p["fecha"] == "2026-10-31":
            por_tema[p["tema"]] = p                                  # el último pisa a los anteriores (pruebas repetidas)
    salida = []
    for n, (tema_id, p) in enumerate(sorted(por_tema.items(), key=lambda kv: kv[1].get("publicado_utc", ""))):
        t = temas[tema_id]
        pista, inicio = elegir_musica(date.fromordinal(date(2026, 10, 31).toordinal() + n), musica_dir)
        hora = datetime.strptime(p["publicado_utc"], "%Y-%m-%dT%H:%M:%SZ").strftime("%H%M")
        salida.append(dict(fecha="2026-10-31", hora="", tipo="reel_ya_en_instagram", titulo=f"Reel ya publicado en Instagram · {t['nombre']}",
                           base=f"2026-10-31_{hora}_reel-instagram_{slug(tema_id)}", descripcion=a_tiktok(pie_de_foto(t, 0)),
                           tema=t, asset=idx.get(p.get("asset")), pista=pista, inicio=inicio))
    return salida


def _entradas_curiosidades(cola_dir, cfg):
    plan = json.loads((RAIZ / "contenido" / "plan_curiosidades.json").read_text(encoding="utf-8"))["plan"]
    cola = {v["id"]: v for v in cargar_cola(cola_dir)}
    salida = []
    for p in plan:
        espec = cargar_espec(CARPETA_ESPECS / f"{p['id']}.json")
        v = cola.get(p["id"])
        salida.append(dict(fecha=p["fecha"], hora=cfg["hora_curiosidad"], tipo="curiosidad", titulo=f"Curiosidad · {espec['titulo']}",
                           base=f"{p['fecha']}_{cfg['hora_curiosidad'].replace(':', '')}_curiosidad_{slug(espec['titulo_pantalla'])}",
                           descripcion=a_tiktok(v["pie"] if v else construir_descripcion(espec)),
                           origen=(Path(cola_dir) / v["video"]) if v else None))
    return salida


# ---------- Creación de la carpeta ----------
def preparar(carpeta, hasta: date, cola_dir, musica_dir, avisar=print):
    from .reel import generar_reel

    carpeta = Path(carpeta)
    (carpeta / "videos").mkdir(parents=True, exist_ok=True)
    cfg = cargar_config()
    catalogo = cargar_catalogo()
    entradas = (_entradas_publicadas_hoy(catalogo, musica_dir) + _entradas_reels(hasta, cfg, catalogo, musica_dir)
                + [e for e in _entradas_curiosidades(cola_dir, cfg) if e["fecha"] <= hasta.isoformat()])
    datos = []
    for e in entradas:
        nombre = f"{e['base']}.mp4"
        destino = carpeta / "videos" / nombre
        listo = True
        if not destino.exists():
            if e["tipo"].startswith("reel"):
                avisar(f"Creando {nombre}")
                tmp = generar_reel(e["tema"], e["asset"], destino, musica=e["pista"], musica_inicio=e["inicio"])
                if Path(tmp) != destino:
                    shutil.move(str(tmp), destino)
            elif e["origen"] and Path(e["origen"]).exists():
                shutil.copy2(e["origen"], destino)
            else:
                listo = False
        datos.append(dict(id=e["base"], fecha=e["fecha"], hora=e["hora"], tipo=e["tipo"], titulo=e["titulo"], archivo=nombre,
                          ruta=str(destino), descripcion=e["descripcion"], listo=listo and destino.exists()))
    datos.sort(key=lambda d: (d["fecha"], d["hora"] or "00:00", d["tipo"]))
    (carpeta / "calendario.html").write_text(_HTML.replace("__DATOS__", json.dumps(
        {"generado": datetime.now().strftime("%d/%m/%Y %H:%M"), "entradas": datos}, ensure_ascii=False)), encoding="utf-8")
    with open(carpeta / "calendario.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["Fecha", "Día", "Hora", "Tipo", "Título", "Archivo", "Ruta", "Descripción"])
        for d in datos:
            f_ = date.fromisoformat(d["fecha"])
            w.writerow([d["fecha"], DIAS[f_.weekday()], d["hora"], d["tipo"], d["titulo"], d["archivo"] if d["listo"] else "(aún sin vídeo)",
                        d["ruta"] if d["listo"] else "", d["descripcion"]])
    return datos


_HTML = r"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Calendario TikTok · JM TECH</title>
<style>
:root{--bg:#f4f7fc;--panel:#fff;--ink:#101828;--muted:#5b6b86;--line:#dbe4f2;--azul:#007fff;--azul-bg:#e6f1ff;--naranja:#e8741a;--naranja-bg:#fff0e3;--verde:#12a150;--verde-bg:#e3f7ec;--rojo:#d92d4a;--rojo-bg:#fde8ec}
@media (prefers-color-scheme:dark){:root{--bg:#070d1c;--panel:#0e1830;--ink:#eef3ff;--muted:#9db0d0;--line:#1f3158;--azul-bg:#0f2a52;--naranja-bg:#3a2210;--verde-bg:#0f3322;--rojo-bg:#3d1520}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.45 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
header{position:sticky;top:0;z-index:5;background:var(--bg);border-bottom:1px solid var(--line);padding:14px 16px 10px}
.fila{max-width:980px;margin:0 auto;display:flex;flex-wrap:wrap;gap:8px;align-items:center}
h1{font-size:1.25rem;margin:0 8px 0 0}.sub{color:var(--muted);font-size:.85rem}
button,input[type=date]{font:inherit;border:1px solid var(--line);background:var(--panel);color:var(--ink);border-radius:10px;padding:8px 12px;cursor:pointer}
button:hover{border-color:var(--azul)}button.act{background:var(--azul);border-color:var(--azul);color:#fff}
main{max-width:980px;margin:0 auto;padding:16px}
.aviso{background:var(--rojo-bg);border:1px solid var(--rojo);border-radius:12px;padding:10px 14px;margin-bottom:14px}
.aviso button{margin-left:8px}
.dia{margin:22px 0 8px;display:flex;align-items:baseline;gap:10px;flex-wrap:wrap}.dia h2{font-size:1.15rem;margin:0;text-transform:capitalize}
.tag{font-size:.75rem;font-weight:700;border-radius:999px;padding:2px 10px;background:var(--azul);color:#fff}.tag.man{background:var(--naranja)}
.vacio{color:var(--muted);padding:18px;border:1px dashed var(--line);border-radius:12px}
.card{background:var(--panel);border:1px solid var(--line);border-left:6px solid var(--azul);border-radius:14px;padding:14px 16px;margin:10px 0}
.card.cur{border-left-color:var(--naranja)}.card.ya{border-left-color:var(--verde)}.card.hecho{opacity:.55}
.cab{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.badge{font-size:.75rem;font-weight:700;border-radius:8px;padding:2px 8px;background:var(--azul-bg);color:var(--azul)}
.cur .badge{background:var(--naranja-bg);color:var(--naranja)}.ya .badge{background:var(--verde-bg);color:var(--verde)}
.hora{font-weight:700}.titulo{font-weight:700;font-size:1.05rem;margin:6px 0 8px}
.etq{font-size:.78rem;text-transform:uppercase;letter-spacing:.04em;color:var(--muted);margin:10px 0 4px}
.ruta{display:flex;gap:8px;flex-wrap:wrap;align-items:center}.ruta code{background:var(--bg);border:1px solid var(--line);border-radius:8px;padding:5px 8px;font-size:.85rem;word-break:break-all}
textarea{width:100%;min-height:150px;resize:vertical;border:1px solid var(--line);border-radius:10px;background:var(--bg);color:var(--ink);padding:10px;font:inherit;font-size:.92rem}
.acciones{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-top:8px}.acciones label{display:flex;gap:6px;align-items:center;cursor:pointer}
.principal{background:var(--azul);color:#fff;border-color:var(--azul);font-weight:700}.ok{background:var(--verde)!important;border-color:var(--verde)!important}
.nota{font-size:.82rem;color:var(--muted);margin-top:8px}.sinvideo{color:var(--naranja);font-weight:700}
a{color:var(--azul)}
@media (max-width:600px){header{padding:10px}main{padding:10px}}
</style>
</head>
<body>
<header><div class="fila"><h1>Calendario TikTok · JM TECH</h1><span class="sub" id="gen"></span></div>
<div class="fila" style="margin-top:8px">
<button id="b-hoy" class="act">Hoy</button><button id="b-man">Mañana</button><button id="b-sem">Esta semana</button><button id="b-pend">Pendientes</button><button id="b-todo">Todo</button>
<span style="flex:1"></span><button id="ant" title="Día anterior">‹</button><input type="date" id="fecha"><button id="sig" title="Día siguiente">›</button>
</div></header>
<main id="app"></main>
<script>
const DATOS=__DATOS__;
const E=DATOS.entradas;
const iso=d=>{const z=n=>String(n).padStart(2,'0');return d.getFullYear()+'-'+z(d.getMonth()+1)+'-'+z(d.getDate())};
const sumar=(s,n)=>{const d=new Date(s+'T12:00:00');d.setDate(d.getDate()+n);return iso(d)};
const HOY=iso(new Date());
let vista='hoy',sel=HOY,hechos=new Set();
try{hechos=new Set(JSON.parse(localStorage.getItem('jmtech_tiktok_hechos')||'[]'))}catch(e){}
const guardar=()=>{try{localStorage.setItem('jmtech_tiktok_hechos',JSON.stringify([...hechos]))}catch(e){}};
const fmt=s=>new Date(s+'T12:00:00').toLocaleDateString('es-ES',{weekday:'long',day:'numeric',month:'long',year:'numeric'});
const esc=t=>t.replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
document.getElementById('gen').textContent='Actualizado '+DATOS.generado+' · '+E.length+' vídeos';
function copiar(texto,btn){
  const fin=()=>{const o=btn.textContent;btn.textContent='¡Copiado!';btn.classList.add('ok');setTimeout(()=>{btn.textContent=o;btn.classList.remove('ok')},1500)};
  if(navigator.clipboard&&window.isSecureContext){navigator.clipboard.writeText(texto).then(fin,()=>viejo(texto,fin))}else viejo(texto,fin);
}
function viejo(t,fin){const a=document.createElement('textarea');a.value=t;document.body.appendChild(a);a.select();try{document.execCommand('copy')}catch(e){}a.remove();fin()}
function tarjeta(e){
  const cls=e.tipo==='curiosidad'?'cur':(e.tipo==='reel_ya_en_instagram'?'ya':'');
  const nombre={reel:'Reel diario',curiosidad:'Curiosidad',reel_ya_en_instagram:'Ya en Instagram'}[e.tipo];
  const d=document.createElement('div');d.className='card '+cls+(hechos.has(e.id)?' hecho':'');
  const hora=e.hora?('<span class="hora">'+e.hora+'</span>'):'';
  d.innerHTML='<div class="cab"><span class="badge">'+nombre+'</span>'+hora+'</div><div class="titulo">'+esc(e.titulo)+'</div>'+
  (e.listo?'<div class="etq">Vídeo (carpeta videos)</div><div class="ruta"><code>'+esc(e.archivo)+'</code><button data-c="ruta">Copiar ruta</button><a href="videos/'+encodeURI(e.archivo)+'" target="_blank">Ver vídeo</a></div>'
          :'<div class="etq">Vídeo</div><div class="sinvideo">Aún sin vídeo: esperando imágenes. Se avisará cuando esté listo.</div>')+
  '<div class="etq">Descripción para TikTok</div><textarea readonly></textarea>'+
  '<div class="acciones"><button class="principal" data-c="desc">Copiar descripción</button><label><input type="checkbox"'+(hechos.has(e.id)?' checked':'')+'> Ya subido a TikTok</label></div>'+
  '<div class="nota">En TikTok Studio: activa «Contenido generado por IA» (la voz y las imágenes son sintéticas)'+(e.hora?'. Hora sugerida: '+e.hora:'')+'.</div>';
  d.querySelector('textarea').value=e.descripcion;
  d.querySelectorAll('button[data-c]').forEach(b=>b.onclick=()=>copiar(b.dataset.c==='ruta'?e.ruta:e.descripcion,b));
  d.querySelector('input').onchange=ev=>{ev.target.checked?hechos.add(e.id):hechos.delete(e.id);guardar();render()};
  return d;
}
const esYa=e=>e.tipo==='reel_ya_en_instagram';
function lista(entradas){
  const app=document.getElementById('app');app.innerHTML='';
  const ya=entradas.filter(esYa),resto=entradas.filter(e=>!esYa(e));
  if(!ya.length&&!resto.length){app.innerHTML='<div class="vacio">No hay vídeos en esta vista.</div>';return}
  if(ya.length){
    const h=document.createElement('div');h.className='dia';
    h.innerHTML='<h2>Ya publicados hoy en Instagram</h2><span class="tag">SÚBELOS TAMBIÉN A TIKTOK</span>';
    app.appendChild(h);ya.forEach(e=>app.appendChild(tarjeta(e)));
  }
  const dias=[...new Set(resto.map(e=>e.fecha))].sort();
  dias.forEach(f=>{
    const h=document.createElement('div');h.className='dia';
    h.innerHTML='<h2>'+fmt(f)+'</h2>'+(f===HOY?'<span class="tag">HOY</span>':'')+(f===sumar(HOY,1)?'<span class="tag man">MAÑANA</span>':'');
    app.appendChild(h);
    resto.filter(e=>e.fecha===f).forEach(e=>app.appendChild(tarjeta(e)));
  });
}
function render(){
  document.getElementById('fecha').value=sel;
  ['hoy','man','sem','pend','todo'].forEach(k=>document.getElementById('b-'+k).classList.toggle('act',k===vista));
  const atras=E.filter(e=>e.fecha<HOY&&!hechos.has(e.id)&&e.listo&&!esYa(e));
  let r;
  if(vista==='hoy'){r=E.filter(e=>e.fecha===sel);if(sel===HOY)r=r.concat(E.filter(e=>esYa(e)&&e.fecha!==sel&&!hechos.has(e.id)))}
  else if(vista==='man')r=E.filter(e=>e.fecha===sumar(HOY,1));
  else if(vista==='sem'){const d=new Date(sel+'T12:00:00');const lun=sumar(sel,-((d.getDay()+6)%7));r=E.filter(e=>e.fecha>=lun&&e.fecha<=sumar(lun,6))}
  else if(vista==='pend')r=atras;
  else r=E.filter(e=>e.fecha>=HOY||!hechos.has(e.id));
  lista(r);
  if(vista!=='pend'&&atras.length&&vista!=='todo'){
    const a=document.createElement('div');a.className='aviso';
    a.innerHTML='Tienes <b>'+atras.length+'</b> vídeo(s) de días anteriores sin marcar como subidos.<button>Verlos</button>';
    a.querySelector('button').onclick=()=>{vista='pend';render()};
    document.getElementById('app').prepend(a);
  }
}
document.getElementById('b-hoy').onclick=()=>{vista='hoy';sel=HOY;render()};
document.getElementById('b-man').onclick=()=>{vista='man';render()};
document.getElementById('b-sem').onclick=()=>{vista='sem';sel=HOY;render()};
document.getElementById('b-pend').onclick=()=>{vista='pend';render()};
document.getElementById('b-todo').onclick=()=>{vista='todo';render()};
document.getElementById('ant').onclick=()=>{vista='hoy';sel=sumar(sel,-1);render()};
document.getElementById('sig').onclick=()=>{vista='hoy';sel=sumar(sel,1);render()};
document.getElementById('fecha').onchange=ev=>{if(ev.target.value){vista='hoy';sel=ev.target.value;render()}};
render();
</script>
</body>
</html>
"""


def main():
    p = argparse.ArgumentParser(prog="jmtech.tiktok")
    p.add_argument("orden", choices=["preparar"])
    p.add_argument("--carpeta", required=True)
    p.add_argument("--hasta", required=True, help="última fecha (AAAA-MM-DD) hasta la que se preparan reels diarios")
    p.add_argument("--cola", default=r"C:\Users\xosu1\jmtech-musica\curiosidades")
    p.add_argument("--musica-dir", default=r"C:\Users\xosu1\jmtech-musica")
    a = p.parse_args()
    datos = preparar(a.carpeta, date.fromisoformat(a.hasta), a.cola, a.musica_dir)
    print(f"Calendario listo: {len(datos)} entradas ({sum(1 for d in datos if d['listo'])} con vídeo) en {a.carpeta}")


if __name__ == "__main__":
    main()
