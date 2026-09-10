const $ = s => document.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));

function call(message) {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage(message, r => {
      if (chrome.runtime.lastError) return reject(chrome.runtime.lastError);
      if (!r?.ok) return reject(new Error(r?.error || 'Memory Box 操作失败'));
      resolve(r.data);
    });
  });
}


async function fileToBase64(file) {
  if (file.size > 48 * 1024 * 1024) throw new Error(`${file.name} 超过扩展单附件 48MB 限制，请使用 Memory Box 本地程序或 MCP 附加。`);
  const bytes = new Uint8Array(await file.arrayBuffer());
  let bin = '';
  for (let i=0;i<bytes.length;i+=0x8000) bin += String.fromCharCode(...bytes.subarray(i,i+0x8000));
  return btoa(bin);
}

async function uploadPickedFiles(memoryId) {
  const files = Array.from($('#chatFiles')?.files || []);
  for (const f of files) {
    const data_base64 = await fileToBase64(f);
    const r = await fetch(`http://127.0.0.1:8765/api/memories/${encodeURIComponent(memoryId)}/attachments`, {
      method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify({filename:f.name,mime_type:f.type||'application/octet-stream',data_base64})
    });
    const j = await r.json().catch(()=>({}));
    if (!r.ok) throw new Error(j.error || `附件上传失败: ${f.name}`);
  }
  return files.length;
}

function toast(text) {
  const t = $('#toast'); t.textContent = text; t.style.display = 'block';
  setTimeout(() => t.style.display = 'none', 3200);
}

async function health() {
  try {
    const h = await call({type:'health'});
    $('#status').textContent = `● 已连接 v${h.version}`; $('#status').className = 'status ok';
  } catch {
    $('#status').textContent = '○ 未连接'; $('#status').className = 'status bad';
  }
}

function renderMemories(items) {
  const box = $('#list');
  if (!items?.length) { box.innerHTML = '<div class="empty">没有找到记忆</div>'; return; }
  box.innerHTML = items.map(m => `<div class="memory">
    <div class="meta">${m.pinned?'📌 ':''}${m.favorite?'⭐ ':''}${esc(m.memory_id)} · ${esc(m.category_label)} · ${esc(m.source_agent)}</div>
    <div class="title">${esc(m.title)}</div>
    <div class="summary">${esc(m.summary)}</div>
    <div class="actions">
      <button class="btn small soft" data-copy="${m.memory_id}">复制恢复上下文</button>
      <button class="btn small dark" data-inject="${m.memory_id}">恢复到当前聊天</button>
    </div>
  </div>`).join('');
  box.querySelectorAll('[data-copy]').forEach(b => b.onclick = async () => {
    const r = await call({type:'resume', memory_ids:[b.dataset.copy]});
    await navigator.clipboard.writeText(r.context); toast(`已复制 ${b.dataset.copy}`);
  });
  box.querySelectorAll('[data-inject]').forEach(b => b.onclick = async () => {
    await call({type:'resume-to-chat', memory_ids:[b.dataset.inject]});
    toast(`已把 ${b.dataset.inject} 填入当前聊天输入框`);
  });
}

async function load() {
  try { renderMemories(await call({type:'memories', query:$('#q').value.trim(), limit:30})); }
  catch (e) { $('#list').innerHTML = `<div class="empty">${esc(e.message)}</div>`; }
}

$('#saveSel').onclick = async () => {
  try { const c = await call({type:'save-selection'}); const n=await uploadPickedFiles(c.memory_id); toast(`已保存 ${c.memory_id} · ${c.category_label}${n?` · ${n} 个附件`:''}`); await load(); }
  catch (e) { toast(e.message); }
};
$('#saveChat').onclick = async () => {
  try { const c = await call({type:'save-conversation'}); const n=await uploadPickedFiles(c.memory_id); toast(`已保存 ${c.memory_id} · ${c.category_label}${n?` · ${n} 个附件`:''}`); await load(); }
  catch (e) { toast(e.message); }
};
$('#search').onclick = load;
$('#q').addEventListener('keydown', e => { if (e.key === 'Enter') load(); });
$('#saveManual').onclick = async () => {
  try { const c = await call({type:'save-text', text:$('#manualText').value}); $('#manualText').value=''; toast(`已保存 ${c.memory_id}`); await load(); }
  catch (e) { toast(e.message); }
};
document.querySelectorAll('[data-tab]').forEach(b => b.onclick = () => {
  const tab = b.dataset.tab;
  $('#memories').style.display = tab === 'memories' ? '' : 'none';
  $('#manual').style.display = tab === 'manual' ? '' : 'none';
  document.querySelectorAll('[data-tab]').forEach(x => x.className = `btn ${x===b?'dark':'soft'}`);
});
health(); load();
