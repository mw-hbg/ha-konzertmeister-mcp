"""Styles and scripts of the app page (kept apart from the page logic)."""

CSS = """
:root{--bg:#f6f7f9;--card:#fff;--text:#1c1c1c;--muted:#5f6368;--accent:#0d47a1;--border:#e0e3e7;--ok:#1b7f3b;--err:#b3261e;--warn:#8a5a00}
@media (prefers-color-scheme:dark){:root{--bg:#111418;--card:#1c2026;--text:#e8eaed;--muted:#9aa0a6;--accent:#8ab4f8;--border:#2f343b;--ok:#81c995;--err:#f28b82;--warn:#fdd663}}
*{box-sizing:border-box}body{margin:0;font:15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;background:var(--bg);color:var(--text)}
main{max-width:760px;margin:0 auto;padding:24px 16px}h1{font-size:22px;margin:0 0 16px}h2{font-size:17px;margin:0 0 12px}
.card{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:18px 20px;margin-bottom:16px}
.muted{color:var(--muted)}.ok{color:var(--ok)}.err{color:var(--err)}.warn{color:var(--warn)}
label{display:block;font-size:13px;color:var(--muted);margin:10px 0 4px}
input,textarea{width:100%;padding:9px 11px;border:1px solid var(--border);border-radius:8px;background:transparent;color:var(--text);font-size:15px}
button{margin-top:14px;padding:9px 16px;border:0;border-radius:8px;background:var(--accent);color:#fff;font-size:14px;cursor:pointer}
@media (prefers-color-scheme:dark){button{color:#111}}
button.secondary{background:transparent;color:var(--accent);border:1px solid var(--border)}
button.danger{color:var(--err)}
select{padding:8px 10px;border:1px solid var(--border);border-radius:8px;background:transparent;color:var(--text);font-size:15px}
label.check{display:inline-flex;gap:6px;align-items:center;color:var(--text);font-size:14px;margin:6px 14px 0 0}
label.check input{width:auto}
textarea{font:13px/1.4 ui-monospace,Menlo,monospace;min-height:84px}
.tools-list label.check{display:flex;margin:6px 0}
details.rename summary{list-style:none;font-weight:normal;padding:0 4px}
details.rename summary::-webkit-details-marker{display:none}
.row{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.row button{margin-top:0}
code{display:block;padding:9px 11px;border-radius:8px;border:1px solid var(--border);word-break:break-all;font-size:13px;flex:1;min-width:0}
h3{font-size:15px;margin:18px 0 8px}
.cats td{padding:4px 14px 4px 0}.num{color:var(--muted);white-space:nowrap}
.badge{display:inline-block;font-size:11px;padding:1px 7px;border-radius:10px;margin-right:4px;border:1px solid}
.badge.read{color:var(--ok);border-color:var(--ok)}.badge.create{color:var(--accent);border-color:var(--accent)}.badge.change{color:var(--err);border-color:var(--err)}
a.btn{display:inline-block;margin-top:14px;padding:9px 16px;border-radius:8px;background:var(--accent);color:#fff;text-decoration:none;font-size:14px}
a.btn.secondary{background:transparent;color:var(--accent);border:1px solid var(--border)}
@media (prefers-color-scheme:dark){a.btn{color:#111}a.btn.secondary{color:var(--accent)}}
.links{gap:10px}
.toolbar{position:sticky;top:0;background:var(--bg);padding:10px 0;z-index:2}
.tool{display:flex;gap:10px;align-items:flex-start;padding:8px 0;border-top:1px solid var(--border)}
.tool input{width:auto;margin-top:3px}.tool .txt{flex:1}.tool code{display:inline;border:0;padding:0;font-size:12px;color:var(--muted)}
.info{background:none;border:1px solid var(--border);color:var(--accent);border-radius:50%;width:24px;height:24px;padding:0;margin:0;font-size:13px;line-height:22px;flex:none}
.infobox{display:none;margin-top:6px;padding:8px 10px;border-radius:8px;border:1px solid var(--border);font-size:13px}
.infobox.open{display:block}
summary{cursor:pointer;font-weight:600;padding:6px 0}
.savebar{position:sticky;bottom:0;background:var(--bg);padding:10px 0;display:flex;gap:10px;flex-wrap:wrap;align-items:center}
.footer{text-align:center;font-size:12px;margin-top:8px}
.badge.new{color:var(--warn);border-color:var(--warn)}
.busy-note{display:none;margin-top:10px}button:disabled{opacity:.6;cursor:wait}
.banner{padding:14px 16px;border-radius:12px;margin-bottom:16px;border:2px solid var(--warn)}
.flash{padding:10px 14px;border-radius:8px;margin-bottom:16px;border:1px solid var(--border)}
table{border-collapse:collapse}td{padding:3px 16px 3px 0;vertical-align:top}
"""

JS = """
function toggle(id,btn){const el=document.getElementById(id);const hidden=el.dataset.hidden!=='0';
el.textContent=hidden?el.dataset.value:el.dataset.mask;el.dataset.hidden=hidden?'0':'1';btn.textContent=hidden?btn.dataset.hide:btn.dataset.show}
function busy(form){const b=form.querySelector('button[type=submit]');if(form.dataset.busy){return false}
form.dataset.busy='1';if(b){b.disabled=true;b.textContent=b.dataset.busy||b.textContent}
const n=form.querySelector('.busy-note');if(n){n.style.display='block'}return true}
function copyVal(id,btn){navigator.clipboard.writeText(document.getElementById(id).dataset.value).then(()=>{const t=btn.textContent;btn.textContent=btn.dataset.done;setTimeout(()=>btn.textContent=t,1500)})}
"""

STATUS_POLL_JS = """
(function(){
  // SHOWN: the status this page was rendered with (same format as status.json "state")
  function busyTyping(){
    const a=document.activeElement;
    if(a&&(a.tagName==='INPUT'||a.tagName==='TEXTAREA'||a.tagName==='SELECT'))return true;
    return Array.from(document.querySelectorAll('input:not([type=hidden]):not([type=checkbox]):not([name=name])')).some(i=>i.value);
  }
  async function poll(){
    try{
      const r=await fetch('status.json',{cache:'no-store'});
      const s=await r.json();
      if(s.state!==SHOWN&&!busyTyping()&&!document.querySelector('form[data-busy]')){location.reload();return}
    }catch(e){}
    setTimeout(poll,5000);
  }
  setTimeout(poll,3000);
})();
"""

PRESET_JS = """
function preset(btn,kinds){btn.closest('details').querySelectorAll('input[name=tool]').forEach(c=>c.checked=kinds.includes(c.dataset.kind))}
"""
