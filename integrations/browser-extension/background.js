const BASE = 'http://127.0.0.1:8765';

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.removeAll(() => {
    chrome.contextMenus.create({
      id: 'save-to-memory-box',
      title: '保存选中内容到 Memory Box',
      contexts: ['selection']
    });
    chrome.contextMenus.create({
      id: 'save-page-to-memory-box',
      title: '保存当前 AI 对话到 Memory Box',
      contexts: ['page']
    });
  });
});

function agentFromUrl(url) {
  try {
    const h = new URL(url).hostname.toLowerCase();
    if (h.includes('chatgpt.com')) return 'ChatGPT Web';
    if (h.includes('kimi.com') || h.includes('kimi.ai')) return 'Kimi Web';
    if (h.includes('deepseek.com')) return 'DeepSeek Web';
    if (h.includes('doubao.com')) return 'Doubao Web';
    if (h.includes('yuanbao.tencent.com')) return 'Tencent Yuanbao Web';
    if (h.includes('claude.ai')) return 'Claude Web';
    if (h.includes('gemini.google.com')) return 'Gemini Web';
    return h || 'browser';
  } catch {
    return 'browser';
  }
}

async function api(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, options);
  let payload = null;
  try { payload = await res.json(); } catch { payload = {}; }
  if (!res.ok) throw new Error(payload.error || `HTTP ${res.status}`);
  return payload;
}

async function activeTab() {
  const [tab] = await chrome.tabs.query({active: true, currentWindow: true});
  return tab;
}

async function readSelection(tabId) {
  const out = await chrome.scripting.executeScript({
    target: {tabId},
    func: () => window.getSelection()?.toString()?.trim() || ''
  });
  return out?.[0]?.result || '';
}

async function readConversation(tabId) {
  const out = await chrome.scripting.executeScript({
    target: {tabId},
    func: () => {
      const selected = window.getSelection()?.toString()?.trim();
      if (selected) return selected;
      const candidates = [
        document.querySelector('main'),
        document.querySelector('[role="main"]'),
        document.querySelector('[data-testid*="conversation"]'),
        document.querySelector('[class*="conversation"]'),
        document.querySelector('[class*="chat"]')
      ].filter(Boolean);
      const root = candidates.sort((a,b) => (b.innerText || '').length - (a.innerText || '').length)[0] || document.body;
      const text = (root.innerText || '').replace(/\n{4,}/g, '\n\n').trim();
      return text.slice(-60000);
    }
  });
  return out?.[0]?.result || '';
}

async function saveText(text, tab, extraTags = []) {
  if (!text || !text.trim()) throw new Error('没有可保存的对话内容');
  return api('/api/quick-save', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      text,
      title: tab?.title || null,
      category: 'auto',
      tags: ['browser-bridge', ...extraTags],
      agent: agentFromUrl(tab?.url || ''),
      url: tab?.url || ''
    })
  });
}

async function injectText(tabId, text) {
  const out = await chrome.scripting.executeScript({
    target: {tabId},
    args: [text],
    func: (value) => {
      const visible = el => {
        const r = el.getBoundingClientRect();
        const s = getComputedStyle(el);
        return r.width > 10 && r.height > 10 && s.visibility !== 'hidden' && s.display !== 'none';
      };
      const candidates = [
        ...document.querySelectorAll('textarea'),
        ...document.querySelectorAll('[contenteditable="true"]'),
        ...document.querySelectorAll('[role="textbox"]')
      ].filter(visible);
      let el = document.activeElement;
      if (!el || !candidates.includes(el)) el = candidates[candidates.length - 1];
      if (!el) return {ok:false, reason:'未找到聊天输入框'};
      el.focus();
      if (el instanceof HTMLTextAreaElement || el instanceof HTMLInputElement) {
        const proto = el instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
        const setter = Object.getOwnPropertyDescriptor(proto, 'value')?.set;
        if (setter) setter.call(el, value); else el.value = value;
        el.dispatchEvent(new Event('input', {bubbles:true}));
        el.dispatchEvent(new Event('change', {bubbles:true}));
      } else {
        el.textContent = value;
        el.dispatchEvent(new InputEvent('input', {bubbles:true, inputType:'insertText', data:value}));
      }
      return {ok:true};
    }
  });
  return out?.[0]?.result || {ok:false, reason:'注入失败'};
}

async function notify(title, message) {
  await chrome.notifications.create({
    type: 'basic',
    iconUrl: 'icon128.png',
    title,
    message
  });
}

async function saveSelectionFromActiveTab() {
  const tab = await activeTab();
  if (!tab?.id) throw new Error('未找到当前标签页');
  const text = await readSelection(tab.id);
  const card = await saveText(text, tab, ['browser-selection']);
  await notify('Memory Box 已保存', `[${card.memory_id}] ${card.title}`);
  return card;
}

async function saveConversationFromActiveTab() {
  const tab = await activeTab();
  if (!tab?.id) throw new Error('未找到当前标签页');
  const text = await readConversation(tab.id);
  const card = await saveText(text, tab, ['browser-conversation']);
  await notify('Memory Box 已保存当前聊天', `[${card.memory_id}] ${card.title}`);
  return card;
}

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  try {
    if (info.menuItemId === 'save-to-memory-box') {
      const card = await saveText(info.selectionText || '', tab, ['browser-selection']);
      await notify('Memory Box 已保存', `[${card.memory_id}] ${card.title}`);
    } else if (info.menuItemId === 'save-page-to-memory-box' && tab?.id) {
      const text = await readConversation(tab.id);
      const card = await saveText(text, tab, ['browser-conversation']);
      await notify('Memory Box 已保存当前聊天', `[${card.memory_id}] ${card.title}`);
    }
  } catch (e) {
    await notify('Memory Box 操作失败', String(e.message || e));
  }
});

chrome.commands.onCommand.addListener(async command => {
  if (command !== 'save-selection') return;
  try { await saveSelectionFromActiveTab(); }
  catch (e) { await notify('Memory Box 操作失败', String(e.message || e)); }
});

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  (async () => {
    if (msg.type === 'health') return api('/api/health');
    if (msg.type === 'save-selection') return saveSelectionFromActiveTab();
    if (msg.type === 'save-conversation') return saveConversationFromActiveTab();
    if (msg.type === 'save-text') {
      const tab = await activeTab();
      return saveText(msg.text || '', tab, ['browser-manual']);
    }
    if (msg.type === 'memories') {
      const p = new URLSearchParams({limit: String(msg.limit || 30), category: msg.category || 'all', query: msg.query || ''});
      return api(`/api/memories?${p}`);
    }
    if (msg.type === 'categories') return api('/api/categories');
    if (msg.type === 'resume') {
      const r = await api('/api/resume', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({memory_ids: msg.memory_ids || []})
      });
      return r;
    }
    if (msg.type === 'resume-to-chat') {
      const r = await api('/api/resume', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({memory_ids: msg.memory_ids || []})
      });
      const tab = await activeTab();
      if (!tab?.id) throw new Error('未找到当前标签页');
      const injected = await injectText(tab.id, r.context);
      if (!injected.ok) throw new Error(injected.reason || '恢复上下文注入失败');
      return {ok:true, context:r.context};
    }
    throw new Error('未知操作');
  })().then(x => sendResponse({ok:true, data:x})).catch(e => sendResponse({ok:false, error:String(e.message || e)}));
  return true;
});
