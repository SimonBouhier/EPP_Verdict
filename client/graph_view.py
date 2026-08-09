"""
Visualisation du graphe épistémique — read path (Lot B, v0).

Lecture SEULE sur la SQLite existante. Une commande :

    python -m client.graph_view            # ouvre http://localhost:8766
    python -m client.graph_view --db data/epp_devnet.db --port 8766 --no-browser

Rend la topologie épistémique, pas un node-link générique :
- attestations = nœuds pleins, COULEUR = tier, taille = consensus ;
- concepts = nœuds creux discrets, reliés par les relations du graphe
  (épaisseur = poids, teinte = courbure κ) ;
- panneau latéral au clic : triplet, signature 5D en radar, votes, hash ;
- curseur temporel (fenêtre sur `timestamp`).

Rafraîchir le navigateur relit la base (le serveur requête à chaque hit).
Dépendance front : d3 v7 via CDN (v0 assumé, local-only).
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from client.findings import record_exception

REPO_ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------- data (RO)
def resolve_db_path(override: str | None) -> Path:
    if override:
        return Path(override)
    # Lecture directe de config.yaml : le read path ne doit pas exiger la
    # stack pipeline complète (config_loader importe database.engine).
    p = "data/epp.db"
    try:
        cfg = (REPO_ROOT / "config.yaml").read_text(encoding="utf-8")
        in_db = False
        for line in cfg.splitlines():
            if line.startswith("database:"):
                in_db = True
            elif in_db and line.strip().startswith("path:"):
                p = line.split(":", 1)[1].strip().strip('"\'')
                break
            elif in_db and line and not line[0].isspace():
                break
    except Exception as exc:
        record_exception("graph_view.config", exc)
    path = Path(p)
    return path if path.is_absolute() else REPO_ROOT / path


def load_graph(db_path: Path) -> dict:
    """Lit attestations + concepts + relations. Connexion read-only stricte."""
    conn = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        atts = [dict(r) for r in conn.execute(
            """SELECT attestation_id, claim_hash, subject, predicate, object,
                      consensus_score, models_consulted, models_agreeing,
                      sig_agreement, sig_semantic_consistency, sig_centrality,
                      sig_stability, sig_relation_diversity,
                      confidence_tier, epistemic_type, timestamp,
                      metrological_frame, source_anchor, validation_count
               FROM attestations ORDER BY timestamp""")]
        concepts = [dict(r) for r in conn.execute(
            "SELECT id, degree, rho_static, domain FROM concepts WHERE is_active=1")]
        relations = [dict(r) for r in conn.execute(
            """SELECT source, target, weight, kappa, relation_type, confidence
               FROM relations WHERE is_active=1""")]
    finally:
        conn.close()
    return {"attestations": atts, "concepts": concepts, "relations": relations,
            "db": str(db_path.name)}


# ------------------------------------------------------------------- HTML
HTML = r"""<!DOCTYPE html>
<html lang="fr"><head>
<meta charset="utf-8"><title>EPP — graphe épistémique</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.8.5/d3.min.js"></script>
<style>
:root{
  --bg:#0d1017; --panel:#141926; --ink:#c9d4e3; --muted:#5f6b80;
  --sandbox:#566073; --proposition:#d9a03f; --validated:#3fbf8f; --verified:#5ac8fa;
  --line:#232b3d;
}
*{box-sizing:border-box;margin:0}
body{background:var(--bg);color:var(--ink);font:14px/1.45 "Segoe UI",system-ui,sans-serif;overflow:hidden}
#wrap{display:flex;height:100vh}
#stage{flex:1;position:relative}
svg{width:100%;height:100%;display:block}
#side{width:340px;background:var(--panel);border-left:1px solid var(--line);
      padding:18px 20px;overflow-y:auto}
h1{font-size:15px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;color:var(--ink)}
h1 small{display:block;color:var(--muted);font-weight:400;letter-spacing:0;text-transform:none;margin-top:2px}
.legend{margin:14px 0 6px;display:flex;flex-wrap:wrap;gap:8px 14px;font-size:12px;color:var(--muted)}
.legend span{display:inline-flex;align-items:center;gap:6px}
.dot{width:9px;height:9px;border-radius:50%}
#detail{margin-top:16px;border-top:1px solid var(--line);padding-top:14px}
#detail .empty{color:var(--muted);font-size:13px}
.tierbadge{display:inline-block;padding:2px 9px;border-radius:3px;font-size:11px;
           font-weight:600;letter-spacing:.08em;text-transform:uppercase;color:#0d1017}
.claim{margin:10px 0;font-size:13.5px}
.claim b{color:#fff;font-weight:600}
.kv{font-size:12px;color:var(--muted);margin:2px 0}
.kv b{color:var(--ink);font-weight:500}
#radar{margin:12px auto;display:block}
#timebar{position:absolute;left:20px;bottom:16px;right:380px;display:flex;
         align-items:center;gap:12px;color:var(--muted);font-size:12px}
#timebar input{flex:1;accent-color:var(--validated)}
.hint{position:absolute;top:14px;left:20px;color:var(--muted);font-size:12px}
text.lbl{fill:var(--muted);font-size:9.5px;pointer-events:none}
text.albl{fill:var(--ink);font-size:10.5px;pointer-events:none}
</style></head><body>
<div id="wrap">
 <div id="stage">
  <div class="hint">molette : zoom · glisser : déplacer · clic nœud : détail</div>
  <svg id="svg"></svg>
  <div id="timebar"><span id="t0"></span><input type="range" id="tslider" min="0" max="100" value="100"><span id="t1"></span></div>
 </div>
 <div id="side">
  <h1>Graphe épistémique <small id="meta"></small></h1>
  <div class="legend">
    <span><i class="dot" style="background:var(--verified)"></i>verified</span>
    <span><i class="dot" style="background:var(--validated)"></i>validated</span>
    <span><i class="dot" style="background:var(--proposition)"></i>proposition</span>
    <span><i class="dot" style="background:var(--sandbox)"></i>sandbox</span>
    <span><i class="dot" style="background:none;border:1.5px solid var(--muted)"></i>concept</span>
  </div>
  <div id="detail"><div class="empty">Sélectionner un nœud.</div></div>
 </div>
</div>
<script>
const DATA = __DATA__;
const TIER = {sandbox:"#566073",proposition:"#d9a03f",validated:"#3fbf8f",verified:"#5ac8fa"};
const SIG = ["agreement","semantic_consistency","centrality","stability","relation_diversity"];
const SIGKEY = {agreement:"sig_agreement",semantic_consistency:"sig_semantic_consistency",
  centrality:"sig_centrality",stability:"sig_stability",relation_diversity:"sig_relation_diversity"};

// ---- build nodes/links: attestations (pleins) + concepts (creux)
const nodes=[], links=[], byId=new Map();
DATA.concepts.forEach(c=>{const n={id:"c:"+c.id,kind:"concept",label:c.id,deg:c.degree||1};nodes.push(n);byId.set(n.id,n);});
DATA.attestations.forEach(a=>{
  const n={id:"a:"+a.claim_hash+":"+a.attestation_id,kind:"att",a:a,
           label:a.subject.length>34?a.subject.slice(0,33)+"…":a.subject};
  nodes.push(n);byId.set(n.id,n);
  // liens attestation → concepts si présents dans le graphe
  const s="c:"+a.subject.toLowerCase(), o="c:"+a.object.toLowerCase();
  if(byId.has(s)) links.push({source:n.id,target:s,kind:"att",w:.8});
  if(byId.has(o)) links.push({source:n.id,target:o,kind:"att",w:.8});
});
DATA.relations.forEach(r=>{
  const s="c:"+r.source, t="c:"+r.target;
  if(byId.has(s)&&byId.has(t)) links.push({source:s,target:t,kind:"rel",w:r.weight||.3,kappa:r.kappa});
});

const svg=d3.select("#svg"), W=svg.node().clientWidth,H=svg.node().clientHeight;
const g=svg.append("g");
svg.call(d3.zoom().scaleExtent([.15,6]).on("zoom",e=>g.attr("transform",e.transform)));

const link=g.append("g").selectAll("line").data(links).join("line")
  .attr("stroke",d=>d.kind==="att"?"#3a4a68":d3.interpolateRgb("#2a3550","#5f4a7a")(d.kappa??.5))
  .attr("stroke-opacity",d=>d.kind==="att"?.55:.35)
  .attr("stroke-width",d=>d.kind==="att"?1.1:Math.max(.5,Math.min(2.5,d.w*2)));

const node=g.append("g").selectAll("g").data(nodes).join("g").style("cursor","pointer");
node.filter(d=>d.kind==="concept").append("circle")
  .attr("r",d=>3+Math.min(6,Math.sqrt(d.deg)))
  .attr("fill","none").attr("stroke","#5f6b80").attr("stroke-width",1.2);
node.filter(d=>d.kind==="att").append("circle")
  .attr("r",d=>5+d.a.consensus_score*7)
  .attr("fill",d=>TIER[d.a.confidence_tier]||"#888")
  .attr("fill-opacity",.92)
  .attr("stroke",d=>d3.color(TIER[d.a.confidence_tier]||"#888").brighter(.8))
  .attr("stroke-width",1);
node.filter(d=>d.kind==="att").append("text").attr("class","albl")
  .attr("dx",10).attr("dy",3).text(d=>d.label);
node.filter(d=>d.kind==="concept").append("text").attr("class","lbl")
  .attr("dx",8).attr("dy",3).text(d=>d.label.length>22?d.label.slice(0,21)+"…":d.label);

const sim=d3.forceSimulation(nodes)
  .force("link",d3.forceLink(links).id(d=>d.id).distance(d=>d.kind==="att"?55:70).strength(d=>d.kind==="att"?.5:.25))
  .force("charge",d3.forceManyBody().strength(d=>d.kind==="att"?-220:-90))
  .force("center",d3.forceCenter(W/2,H/2))
  .force("collide",d3.forceCollide(16));
sim.on("tick",()=>{
  link.attr("x1",d=>d.source.x).attr("y1",d=>d.source.y).attr("x2",d=>d.target.x).attr("y2",d=>d.target.y);
  node.attr("transform",d=>`translate(${d.x},${d.y})`);
});
node.call(d3.drag()
  .on("start",(e,d)=>{if(!e.active)sim.alphaTarget(.25).restart();d.fx=d.x;d.fy=d.y;})
  .on("drag",(e,d)=>{d.fx=e.x;d.fy=e.y;})
  .on("end",(e,d)=>{if(!e.active)sim.alphaTarget(0);d.fx=null;d.fy=null;}));

// ---- détail + radar 5D
function radar(a){
  const R=62,cx=85,cy=78,n=SIG.length;
  const pt=(i,v)=>{const ang=-Math.PI/2+i*2*Math.PI/n;return[cx+Math.cos(ang)*R*v,cy+Math.sin(ang)*R*v];};
  let grid="";[0.33,0.66,1].forEach(l=>{grid+=`<polygon points="${SIG.map((_,i)=>pt(i,l).join(",")).join(" ")}" fill="none" stroke="#232b3d"/>`;});
  const vals=SIG.map((s,i)=>pt(i,a[SIGKEY[s]]??0));
  const axes=SIG.map((s,i)=>{const[e1,e2]=pt(i,1.18);
    return `<text x="${e1}" y="${e2}" fill="#5f6b80" font-size="8.5" text-anchor="middle">${s.replace("semantic_consistency","sem.consist.").replace("relation_diversity","rel.divers.")}</text>`;}).join("");
  const col=TIER[a.confidence_tier]||"#888";
  return `<svg id="radar" width="180" height="160" viewBox="0 0 170 156">${grid}
    <polygon points="${vals.map(v=>v.join(",")).join(" ")}" fill="${col}" fill-opacity=".25" stroke="${col}" stroke-width="1.5"/>
    ${vals.map(v=>`<circle cx="${v[0]}" cy="${v[1]}" r="2" fill="${col}"/>`).join("")}${axes}</svg>`;
}
node.on("click",(e,d)=>{
  const el=document.getElementById("detail");
  if(d.kind==="concept"){
    el.innerHTML=`<div class="claim"><b>${d.label}</b></div>
      <div class="kv">concept du graphe · degré <b>${d.deg}</b></div>`;
    return;
  }
  const a=d.a, col=TIER[a.confidence_tier]||"#888";
  const date=new Date(a.timestamp*1000).toISOString().replace("T"," ").slice(0,19);
  el.innerHTML=`<span class="tierbadge" style="background:${col}">${a.confidence_tier}</span>
    <div class="claim"><b>${a.subject}</b><br>—&nbsp;${a.predicate}&nbsp;→&nbsp;<b>${a.object}</b></div>
    ${radar(a)}
    <div class="kv">consensus <b>${(a.consensus_score*100).toFixed(1)}%</b> · <b>${a.models_agreeing}/${a.models_consulted}</b> modèles · type <b>${a.epistemic_type}</b></div>
    <div class="kv">frame <b>${a.metrological_frame||"—"}</b> · validations <b>${a.validation_count}</b></div>
    <div class="kv">source_anchor <b>${a.source_anchor?a.source_anchor.slice(0,12)+"…":"—"}</b></div>
    <div class="kv">${date}</div>
    <div class="kv" style="word-break:break-all">hash <b>${a.claim_hash}</b></div>`;
});

// ---- fenêtre temporelle
const ts=DATA.attestations.map(a=>a.timestamp);
if(ts.length){
  const tmin=Math.min(...ts),tmax=Math.max(...ts),fmt=t=>new Date(t*1000).toISOString().slice(0,10);
  document.getElementById("t0").textContent=fmt(tmin);
  document.getElementById("t1").textContent=fmt(tmax);
  document.getElementById("tslider").addEventListener("input",e=>{
    const cut=tmin+(tmax-tmin)*(+e.target.value/100);
    node.filter(d=>d.kind==="att").attr("opacity",d=>d.a.timestamp<=cut?1:.08);
    link.attr("opacity",l=>{
      const src=l.source, a=(src.kind==="att"&&src.a)||(l.target.kind==="att"&&l.target.a);
      return a&&a.timestamp>cut?.05:1;});
  });
}
document.getElementById("meta").textContent=
  `${DATA.attestations.length} attestations · ${DATA.concepts.length} concepts · ${DATA.relations.length} relations · ${DATA.db} (lecture seule)`;
</script></body></html>
"""


# ------------------------------------------------------------------ server
class Handler(BaseHTTPRequestHandler):
    db_path: Path = None  # injecté par main()

    def do_GET(self):
        try:
            data = load_graph(self.db_path)
            page = HTML.replace("__DATA__", json.dumps(data, ensure_ascii=False))
            body = page.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception as exc:
            msg = record_exception("graph_view.serve", exc)
            self.send_response(500)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(msg.encode("utf-8"))

    def log_message(self, *args):  # journal HTTP silencieux
        pass


def main() -> None:
    ap = argparse.ArgumentParser(description="EPP — visualisation du graphe (lecture seule)")
    ap.add_argument("--db", default=None, help="chemin SQLite (défaut : config.yaml database.path)")
    ap.add_argument("--port", type=int, default=8766)
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()

    db_path = resolve_db_path(args.db)
    if not db_path.exists():
        print(f"Base introuvable : {db_path}", file=sys.stderr)
        sys.exit(1)

    Handler.db_path = db_path
    server = HTTPServer(("127.0.0.1", args.port), Handler)
    url = f"http://127.0.0.1:{args.port}/"
    print(f"Graphe épistémique : {url}  (base {db_path.name}, lecture seule — Ctrl+C pour arrêter)")
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\narrêt.")


if __name__ == "__main__":
    main()
