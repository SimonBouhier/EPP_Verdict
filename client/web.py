"""
Interface web locale du shim conversationnel (Lot A, front navigateur).

Même vase que client/shim.py — mêmes frontières, même chemin d'escalade,
même journal de findings — servi dans le navigateur par défaut (Brave) au
lieu de la console.

Lancement :
    python -m client.web            # ouvre http://127.0.0.1:8767
    python -m client.web --port 8767 --no-browser

Architecture : un thread asyncio dédié porte le rotator et le pipeline ;
le serveur HTTP (stdlib) lui soumet les coroutines. L'escalade reste UNIQUE
(ADR-003) : lancée en tâche de fond, suivie par polling /api/progress,
les logs INFO du pipeline servent d'indicateur de progression.
Aucun chemin d'ancrage on-chain. Local uniquement (bind 127.0.0.1).
"""

from __future__ import annotations

import argparse
import asyncio
import collections
import json
import logging
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Optional

from client.findings import record_exception, warning_capture
from client.shim import ShimParams, SYSTEM_PROMPT

logger = logging.getLogger("client.web")


# ---------------------------------------------------------------- core
class ProgressHandler(logging.Handler):
    """Capture les INFO+ des modules internes pendant une escalade."""

    def __init__(self, sink: collections.deque):
        super().__init__(level=logging.INFO)
        self.sink = sink

    def emit(self, rec: logging.LogRecord) -> None:
        try:
            if rec.name.startswith(("services", "database", "esmm")):
                self.sink.append(f"{rec.levelname[:4]} {rec.name.split('.')[-1]}: {rec.getMessage()}"[:220])
        except Exception:
            pass


class Core:
    """État partagé + opérations async. Vit dans le thread asyncio."""

    def __init__(self):
        self.params = ShimParams()
        self.history: list[dict] = []          # [{"role","content","model","ms"}]
        self.available_models: list[str] = []
        self.connected = False
        self.rotator = None
        # escalade (ADR-003 : une seule à la fois)
        self.esc_active = False
        self.esc_claim: Optional[str] = None
        self.esc_log: collections.deque = collections.deque(maxlen=300)
        self.esc_result: Optional[dict] = None
        self.esc_error: Optional[str] = None

    async def setup(self) -> None:
        from services.providers.ollama import OllamaProvider
        from services.esmm.multi_provider_rotator import MultiProviderRotator
        from services.config_loader import get_section

        esmm_cfg = get_section("esmm", {}) or {}
        models = esmm_cfg.get("models", ["mistral:latest"])
        self.params.escalade_models = models[: esmm_cfg.get("default_models", 3)]
        self.params.chat_model = models[0]

        provider = OllamaProvider(model=self.params.chat_model)
        self.rotator = MultiProviderRotator(providers={"ollama": provider})
        health = await provider.health_check()
        self.connected = health.get("connected", False)
        self.available_models = health.get("models", [])
        if self.connected and self.params.chat_model not in self.available_models and self.available_models:
            self.params.chat_model = self.available_models[0]

    async def chat(self, text: str) -> dict:
        self.history.append({"role": "user", "content": text})
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + \
                   [{"role": m["role"], "content": m["content"]} for m in self.history[-12:]]
        provider = self.rotator.providers["ollama"]
        provider.model = self.params.chat_model
        with warning_capture("web.chat"):
            resp = await self.rotator.generate_single(
                provider_id="ollama",
                messages=messages,
                temperature=self.params.temperature,
                max_tokens=self.params.max_tokens,
                unload_after=False,
            )
        if not resp.success:
            self.history.pop()
            raise RuntimeError(f"génération échouée : {resp.error}")
        msg = {"role": "assistant", "content": resp.text.strip(),
               "model": resp.model, "ms": round(resp.latency_ms)}
        self.history.append(msg)
        return msg

    async def escalate(self, claim: str) -> None:
        """Tâche de fond — une seule (ADR-003). Chemin pipeline inchangé."""
        from database.engine import get_db
        from services.esmm.pipeline import run_pipeline, PipelineConfig
        from services.esmm.orchestrator import ESMMRunConfig

        self.esc_active = True
        self.esc_claim = claim
        self.esc_log.clear()
        self.esc_result = None
        self.esc_error = None
        self.esc_log.append(f"⇪ escalade : {claim[:120]}")
        self.esc_log.append(f"  modèles : {', '.join(self.params.escalade_models)}")

        prog = ProgressHandler(self.esc_log)
        logging.getLogger().addHandler(prog)
        saved = {n: logging.getLogger(n).level for n in ("services", "esmm")}
        for n in saved:
            logging.getLogger(n).setLevel(logging.INFO)
        try:
            with warning_capture("web.escalate"):
                db = await get_db()
                esmm_config = ESMMRunConfig(
                    models=list(self.params.escalade_models),
                    input_mode="verify",
                    original_claim=claim,
                    max_questions_per_cycle=self.params.max_questions_per_cycle,
                )
                result = await run_pipeline(
                    question=claim,
                    db=db,
                    config=PipelineConfig(metrological_frame=self.params.frame),
                    esmm_config=esmm_config,
                )
            self.esc_result = {
                "duration_ms": round(result.duration_ms),
                "extracted": result.triplets_extracted,
                "attested": result.triplets_attested,
                "injected": result.triplets_injected,
                "errors": result.errors,
                "attestations": [{
                    "subject": a.subject, "predicate": a.predicate, "object": a.object,
                    "tier": a.confidence_tier, "consensus": a.consensus_score,
                    "agreeing": a.models_agreeing, "consulted": a.models_consulted,
                    "hash": a.claim_hash,
                } for a in result.attestations],
            }
            self.esc_log.append(f"── terminé ({result.duration_ms:.0f} ms) — "
                                f"{result.triplets_attested} attestation(s), local/SQLite, pas d'ancrage on-chain")
        except Exception as exc:
            self.esc_error = record_exception("web.escalate", exc)
            self.esc_log.append(f"✗ {self.esc_error}")
        finally:
            logging.getLogger().removeHandler(prog)
            for n, lvl in saved.items():
                logging.getLogger(n).setLevel(lvl)
            self.esc_active = False


# --------------------------------------------------------------- bridge
class Bridge:
    """Thread asyncio dédié ; le serveur HTTP lui soumet les coroutines."""

    def __init__(self):
        self.loop = asyncio.new_event_loop()
        self.core = Core()
        t = threading.Thread(target=self.loop.run_forever, daemon=True)
        t.start()

    def run(self, coro, timeout: float = 600.0):
        return asyncio.run_coroutine_threadsafe(coro, self.loop).result(timeout)

    def spawn(self, coro) -> None:
        asyncio.run_coroutine_threadsafe(coro, self.loop)


BRIDGE: Optional[Bridge] = None


# ------------------------------------------------------------------ HTML
HTML = r"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8"><title>EPP — nœud personnel</title>
<style>
:root{--bg:#0d1017;--panel:#141926;--bub:#1a2133;--ink:#c9d4e3;--muted:#5f6b80;
 --line:#232b3d;--sandbox:#566073;--proposition:#d9a03f;--validated:#3fbf8f;--verified:#5ac8fa;}
*{box-sizing:border-box;margin:0}
body{background:var(--bg);color:var(--ink);font:14.5px/1.5 "Segoe UI",system-ui,sans-serif;height:100vh;display:flex}
#chatcol{flex:1;display:flex;flex-direction:column;min-width:0}
#head{padding:12px 22px;border-bottom:1px solid var(--line);display:flex;align-items:baseline;gap:12px}
#head h1{font-size:14px;letter-spacing:.08em;text-transform:uppercase}
#head .st{font-size:12px;color:var(--muted)}
#head .st b{color:var(--validated);font-weight:600}
#head a{color:var(--muted);font-size:12px;margin-left:auto}
#msgs{flex:1;overflow-y:auto;padding:20px 22px;display:flex;flex-direction:column;gap:14px}
.msg{max-width:76%;padding:10px 14px;border-radius:10px;white-space:pre-wrap;word-wrap:break-word}
.user{align-self:flex-end;background:#243050;border-bottom-right-radius:3px}
.assistant{align-self:flex-start;background:var(--bub);border-bottom-left-radius:3px}
.meta{font-size:11px;color:var(--muted);margin-top:6px;display:flex;gap:10px;align-items:center}
.esc-btn{background:none;border:1px solid var(--line);color:var(--muted);border-radius:4px;
 padding:2px 8px;font-size:11px;cursor:pointer}
.esc-btn:hover{color:var(--verified);border-color:var(--verified)}
#inbar{display:flex;gap:10px;padding:14px 22px;border-top:1px solid var(--line)}
#inp{flex:1;background:var(--panel);border:1px solid var(--line);border-radius:8px;color:var(--ink);
 padding:10px 14px;font:inherit;resize:none;height:48px}
#inp:focus{outline:none;border-color:#3a4a68}
#send{background:#243050;border:none;color:var(--ink);border-radius:8px;padding:0 22px;cursor:pointer;font:inherit}
#send:disabled{opacity:.4;cursor:default}
#side{width:330px;background:var(--panel);border-left:1px solid var(--line);padding:16px;
 display:flex;flex-direction:column;gap:14px;overflow-y:auto}
#side h2{font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted)}
select,input[type=text],input[type=number]{width:100%;background:var(--bg);border:1px solid var(--line);
 border-radius:6px;color:var(--ink);padding:6px 9px;font:13px "Segoe UI",sans-serif}
.prow{display:flex;align-items:center;gap:8px;font-size:12px;color:var(--muted)}
.prow label{width:118px;flex-shrink:0}
#esclog{background:var(--bg);border:1px solid var(--line);border-radius:6px;padding:8px 10px;
 font:11px/1.5 Consolas,monospace;color:var(--muted);height:180px;overflow-y:auto;white-space:pre-wrap}
.att{border:1px solid var(--line);border-left:3px solid var(--muted);border-radius:5px;padding:8px 10px;font-size:12px}
.att b{color:#fff}.att .h{color:var(--muted);font-size:10.5px;word-break:break-all}
.tier{display:inline-block;padding:1px 7px;border-radius:3px;font-size:10px;font-weight:600;
 letter-spacing:.07em;text-transform:uppercase;color:#0d1017;margin-bottom:4px}
#escstate{font-size:12px;color:var(--muted)}
.spin{display:inline-block;width:10px;height:10px;border:2px solid var(--line);
 border-top-color:var(--verified);border-radius:50%;animation:r 0.9s linear infinite;vertical-align:-1px}
@keyframes r{to{transform:rotate(360deg)}}
</style></head><body>
<div id="chatcol">
  <div id="head"><h1>EPP · nœud personnel</h1><span class="st" id="status">…</span>
    <a href="http://127.0.0.1:8766/" target="_blank">graphe ↗</a></div>
  <div id="msgs"></div>
  <div id="inbar">
    <textarea id="inp" placeholder="Message… (Entrée pour envoyer, Maj+Entrée : nouvelle ligne)"></textarea>
    <button id="send">Envoyer</button>
  </div>
</div>
<div id="side">
  <div><h2>Modèle de conversation</h2><select id="model"></select></div>
  <div><h2>Paramètres de cycle</h2>
    <div class="prow"><label>temperature</label><input type="number" id="p_temperature" step="0.1" min="0" max="2"></div>
    <div class="prow"><label>max_tokens</label><input type="number" id="p_max_tokens" step="128" min="64"></div>
    <div class="prow"><label>questions/cycle</label><input type="number" id="p_max_questions_per_cycle" min="1" max="50"></div>
    <div class="prow"><label>frame</label><input type="text" id="p_frame"></div>
  </div>
  <div><h2>Escalade ESMM <span id="escspin"></span></h2>
    <div id="escstate">aucune escalade. Bouton ⇪ sous une réponse, ou sélection de texte puis ⇪.</div>
    <div id="esclog" hidden></div>
    <div id="atts" style="display:flex;flex-direction:column;gap:8px"></div>
  </div>
</div>
<script>
const TIER={sandbox:"#566073",proposition:"#d9a03f",validated:"#3fbf8f",verified:"#5ac8fa"};
const $=id=>document.getElementById(id);
let escPolling=null;

async function api(path,body){
  const r=await fetch(path,body?{method:"POST",headers:{"Content-Type":"application/json"},
    body:JSON.stringify(body)}:undefined);
  const j=await r.json();
  if(j.error) throw new Error(j.error);
  return j;
}
function addMsg(m){
  const d=document.createElement("div");d.className="msg "+m.role;
  d.textContent=m.content;
  if(m.role==="assistant"){
    const meta=document.createElement("div");meta.className="meta";
    meta.innerHTML=`<span>${m.model||""}${m.ms?" · "+m.ms+" ms":""}</span>`;
    const b=document.createElement("button");b.className="esc-btn";b.textContent="⇪ escalader";
    b.onclick=()=>escalate(window.getSelection().toString().trim()||m.content);
    meta.appendChild(b);d.appendChild(meta);
  }
  $("msgs").appendChild(d);$("msgs").scrollTop=$("msgs").scrollHeight;
}
async function refresh(){
  const s=await api("/api/state");
  $("status").innerHTML=s.connected?`Ollama <b>connecté</b> · escalade : ${s.escalade_models.join(", ")}`
    :"⚠ Ollama injoignable sur localhost:11434";
  const sel=$("model");sel.innerHTML="";
  (s.models.length?s.models:[s.params.chat_model]).forEach(m=>{
    const o=document.createElement("option");o.value=o.textContent=m;
    if(m===s.params.chat_model)o.selected=true;sel.appendChild(o);});
  ["temperature","max_tokens","max_questions_per_cycle","frame"].forEach(k=>$("p_"+k).value=s.params[k]);
  $("msgs").innerHTML="";s.history.forEach(addMsg);
  if(s.escalating) startEscPoll();
}
$("model").onchange=e=>api("/api/params",{key:"chat_model",value:e.target.value});
["temperature","max_tokens","max_questions_per_cycle","frame"].forEach(k=>{
  $("p_"+k).onchange=e=>api("/api/params",{key:k,value:e.target.value}).catch(e=>alert(e.message));});

async function send(){
  const t=$("inp").value.trim();if(!t)return;
  $("inp").value="";$("send").disabled=true;
  addMsg({role:"user",content:t});
  const wait=document.createElement("div");wait.className="msg assistant";
  wait.innerHTML='<span class="spin"></span>';$("msgs").appendChild(wait);
  try{const m=await api("/api/chat",{text:t});wait.remove();addMsg(m);}
  catch(e){wait.remove();addMsg({role:"assistant",content:"✗ "+e.message,model:"erreur"});}
  finally{$("send").disabled=false;$("inp").focus();}
}
$("send").onclick=send;
$("inp").addEventListener("keydown",e=>{if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();send();}});

async function escalate(claim){
  if(!claim)return;
  try{await api("/api/escalate",{claim});}catch(e){alert(e.message);return;}
  $("atts").innerHTML="";startEscPoll();
}
function startEscPoll(){
  if(escPolling)return;
  $("esclog").hidden=false;$("escspin").innerHTML='<span class="spin"></span>';
  $("escstate").textContent="run ESMM en cours (bloquant, ADR-003 : un seul à la fois)…";
  escPolling=setInterval(async()=>{
    const p=await api("/api/progress");
    $("esclog").textContent=p.log.join("\n");$("esclog").scrollTop=$("esclog").scrollHeight;
    if(!p.active){
      clearInterval(escPolling);escPolling=null;$("escspin").innerHTML="";
      $("escstate").textContent=p.error?("échec — journalisé dans SHIM_FINDINGS.md"):
        `terminé : ${p.result.extracted} extraits → ${p.result.attested} attestés → ${p.result.injected} injectés`;
      if(p.result) p.result.attestations.forEach(a=>{
        const d=document.createElement("div");d.className="att";
        d.style.borderLeftColor=TIER[a.tier]||"#888";
        d.innerHTML=`<span class="tier" style="background:${TIER[a.tier]||'#888'}">${a.tier}</span><br>
          <b>${a.subject}</b> —${a.predicate}→ <b>${a.object}</b><br>
          consensus ${(a.consensus*100).toFixed(1)}% · ${a.agreeing}/${a.consulted} modèles<br>
          <span class="h">${a.hash}</span>`;
        $("atts").appendChild(d);});
    }
  },1000);
}
refresh();
</script></body></html>
"""


# ------------------------------------------------------------------ server
class Handler(BaseHTTPRequestHandler):
    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(n) or b"{}")

    def do_GET(self):
        try:
            core = BRIDGE.core
            if self.path == "/":
                body = HTML.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif self.path == "/api/state":
                self._json({
                    "connected": core.connected,
                    "models": core.available_models,
                    "escalade_models": core.params.escalade_models,
                    "params": {k: getattr(core.params, k) for k in
                               ("chat_model", "temperature", "max_tokens",
                                "max_questions_per_cycle", "frame")},
                    "history": core.history,
                    "escalating": core.esc_active,
                })
            elif self.path == "/api/progress":
                self._json({"active": core.esc_active, "log": list(core.esc_log),
                            "result": core.esc_result, "error": core.esc_error})
            else:
                self._json({"error": "not found"}, 404)
        except Exception as exc:
            self._json({"error": record_exception("web.get", exc)}, 500)

    def do_POST(self):
        try:
            core = BRIDGE.core
            data = self._body()
            if self.path == "/api/chat":
                msg = BRIDGE.run(core.chat(str(data.get("text", ""))[:8000]))
                self._json(msg)
            elif self.path == "/api/escalate":
                if core.esc_active:
                    self._json({"error": "Un run ESMM est déjà en cours (ADR-003)."}, 409)
                    return
                claim = str(data.get("claim", "")).strip()[:4900]
                if not claim:
                    self._json({"error": "Aucune affirmation désignée."}, 400)
                    return
                BRIDGE.spawn(core.escalate(claim))
                self._json({"started": True})
            elif self.path == "/api/params":
                out = core.params.set(str(data.get("key")), str(data.get("value")))
                if "non exposé" in out or "invalide" in out:
                    self._json({"error": out}, 400)
                else:
                    self._json({"ok": out})
            else:
                self._json({"error": "not found"}, 404)
        except Exception as exc:
            # Frontière d'erreurs : attraper, renvoyer proprement, journaliser.
            self._json({"error": record_exception("web.post", exc)}, 500)

    def log_message(self, *args):
        pass


def main() -> None:
    global BRIDGE
    ap = argparse.ArgumentParser(description="EPP — shim conversationnel (web)")
    ap.add_argument("--port", type=int, default=8767)
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    BRIDGE = Bridge()
    try:
        BRIDGE.run(BRIDGE.core.setup(), timeout=30)
    except Exception as exc:
        print(f"⚠ setup : {record_exception('web.setup', exc)}")

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    url = f"http://127.0.0.1:{args.port}/"
    print(f"EPP web : {url}  (local uniquement — Ctrl+C pour arrêter)")
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\narrêt.")


if __name__ == "__main__":
    main()
