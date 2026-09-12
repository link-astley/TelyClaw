/* TelyClaw 前端逻辑（零依赖原生 JS） */

const $ = (s) => document.querySelector(s);
const $$ = (s) => Array.from(document.querySelectorAll(s));
const state = {
  accounts: [],
  settings: {},
  window: '24h',
  selected: new Set(),
  run: null,
  picks: [],            // [{topic_id, reason, recommended}]
  studioTopicId: null,
  angles: [],
  angle: null,
  drafts: [],
  draftId: null,
};

/* ------------------------------------------------------------ 工具 */
async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  });
  return res.json();
}

function toast(msg) {
  const t = $('#toast');
  t.textContent = msg;
  t.classList.remove('hidden');
  clearTimeout(t._timer);
  t._timer = setTimeout(() => t.classList.add('hidden'), 2600);
}

function escapeHtml(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, (c) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

function alertBox(kind, html, retryFn) {
  const id = 'a' + Math.random().toString(36).slice(2, 7);
  const btn = retryFn ? `<button class="btn tiny" data-retry="${id}">重试</button>` : '';
  const goSet = kind === 'nokey'
    ? `<button class="btn tiny" data-goset="${id}">去设置页填密钥</button>` : '';
  const box = `<div class="alert ${kind === 'nokey' ? 'warn' : 'err'}" id="${id}">
      <span>${html}</span>${btn}${goSet}</div>`;
  setTimeout(() => {
    if (retryFn) {
      const b = document.querySelector(`[data-retry="${id}"]`);
      if (b) b.onclick = retryFn;
    }
    const g = document.querySelector(`[data-goset="${id}"]`);
    if (g) g.onclick = () => switchTab('settings');
  }, 0);
  return box;
}

function safetyBanner(s) {
  s = s || { state: 'unchecked' };
  if (s.state === 'ok') {
    const n = s.risky_post_count || 0;
    const m = s.risky_topic_count || 0;
    return n
      ? `<div class="safety hit">✅ 已用 AI 检查 ${s.checked_count} 条帖子，标记出 <b>${n}</b> 条风险内容、涉及 <b>${m}</b> 个话题
         —— 话题保留在榜上并打上警告，跟不跟由你决定</div>`
      : `<div class="safety clean">✅ 已用 AI 检查 ${s.checked_count} 条帖子，未发现风险内容</div>`;
  }
  if (s.state === 'failed') {
    return `<div class="safety warn">⚠️ 安全检查未执行（${escapeHtml((s.message || '').replace('安全检查未执行：', '') || 'AI 调用失败')}）
      —— 本榜单<b>没有任何风险标记</b>，别直接拿去发帖</div>`;
  }
  return `<div class="safety warn">⚠️ <b>未执行安全检查</b>（${escapeHtml(s.message || '本次未启用 AI')}）
    —— 本榜单没有任何风险标记，别直接拿去发帖</div>`;
}

function aiErrorHtml(e) {
  const msg = (e && e.message) || 'AI 调用失败';
  const detail = e && e.detail ? `<br><span style="opacity:.7;font-size:11.5px">${escapeHtml(e.detail)}</span>` : '';
  return msg + detail;
}

function fmtNum(n) {
  n = Number(n || 0);
  return n >= 10000 ? (n / 10000).toFixed(1) + 'w' : String(n);
}

/* ------------------------------------------------------------ Tab */
function switchTab(name) {
  $$('.tab').forEach((t) => t.classList.toggle('active', t.dataset.tab === name));
  $$('.page').forEach((p) => p.classList.toggle('hidden', p.id !== 'page-' + name));
  if (name === 'records') loadRecords();
  if (name === 'studio') renderStudioTopics();
  if (name === 'settings') loadSettings();
  window.scrollTo({ top: 0, behavior: 'smooth' });
}
$$('.tab').forEach((t) => (t.onclick = () => switchTab(t.dataset.tab)));

function setStep(n) {
  $$('.step').forEach((s) => s.classList.toggle('done', Number(s.dataset.step) <= n));
}

/* ------------------------------------------------------------ 设置页 */
async function loadAccounts() {
  state.accounts = await api('/api/accounts');
  renderAccounts();
  // 默认勾选所有启用的账号
  if (state.selected.size === 0) {
    state.accounts.filter((a) => a.enabled).forEach((a) => state.selected.add(a.handle));
  }
  renderPicks();
}

function renderAccounts() {
  const box = $('#accountList');
  $('#accCount').textContent = `共 ${state.accounts.length} 个`;
  if (!state.accounts.length) {
    box.innerHTML = '<div class="empty">还没有账号，在上面添加一个。</div>';
    return;
  }
  box.innerHTML = state.accounts.map((a) => `
    <div class="acc ${a.enabled ? '' : 'off'}">
      <div class="avatar" style="background:${a.avatar_color}">${escapeHtml(a.initials)}</div>
      <div class="acc-main">
        <div class="acc-name">@${escapeHtml(a.handle)}
          ${a.display_name ? `<span class="hint"> · ${escapeHtml(a.display_name)}</span>` : ''}</div>
        <div class="acc-sub">${fmtNum(a.followers)} 粉丝 · ${a.enabled ? '已启用' : '已停用'}</div>
      </div>
      <button class="btn tiny" data-toggle="${a.handle}">${a.enabled ? '停用' : '启用'}</button>
      <button class="btn tiny" data-del="${a.handle}">删除</button>
    </div>`).join('');

  $$('[data-toggle]').forEach((b) => (b.onclick = async () => {
    await api(`/api/accounts/${b.dataset.toggle}/toggle`, { method: 'POST' });
    loadAccounts();
  }));
  $$('[data-del]').forEach((b) => (b.onclick = async () => {
    await api(`/api/accounts/${b.dataset.del}`, { method: 'DELETE' });
    state.selected.delete(b.dataset.del);
    loadAccounts();
  }));
}

$('#btnAddAccount').onclick = async () => {
  const handle = $('#newHandle').value.trim();
  const name = $('#newName').value.trim();
  $('#addErr').textContent = '';
  if (!handle) { $('#addErr').textContent = '请输入用户名'; return; }
  try {
    const r = await api('/api/accounts', {
      method: 'POST',
      body: JSON.stringify({ handle, display_name: name }),
    });
    if (!r.ok) throw new Error(r.detail || '添加失败');
    $('#newHandle').value = ''; $('#newName').value = '';
    state.selected.add(r.handle);
    toast(`已添加 @${r.handle}`);
    loadAccounts();
  } catch (e) {
    $('#addErr').textContent = e.message;
  }
};

async function loadSettings() {
  state.settings = await api('/api/settings');
  $('#setKey').value = '';
  $('#setKey').placeholder = state.settings.has_key ? '已填写（留空表示不修改）' : 'sk-...';
  $('#setPos').value = state.settings.positioning || '';
  const src = state.settings.source || 'mock';
  $$('input[name=src]').forEach((r) => (r.checked = r.value === src));
  $('#pasteBox').style.display = src === 'paste' ? 'block' : 'none';
  if (src === 'paste') $('#pasteRaw').value = state.settings.paste_raw || '';
  updateAiState();
}

function updateAiState() {
  const el = $('#aiState');
  if (state.settings.has_key) {
    el.innerHTML = 'AI 已就绪 · <b>DeepSeek</b>';
  } else {
    el.innerHTML = '<b>未填 AI 密钥</b> · 热点仍能出，但没有 AI 内容';
  }
}

$('#btnSaveSettings').onclick = async () => {
  const patch = { positioning: $('#setPos').value.trim() };
  const k = $('#setKey').value.trim();
  if (k) patch.deepseek_api_key = k;
  await api('/api/settings', { method: 'PUT', body: JSON.stringify(patch) });
  $('#setSaved').textContent = '已保存';
  setTimeout(() => ($('#setSaved').textContent = ''), 2000);
  loadSettings();
};

$$('input[name=src]').forEach((r) => (r.onchange = async () => {
  $('#pasteBox').style.display = r.value === 'paste' ? 'block' : 'none';
  await api('/api/settings', { method: 'PUT', body: JSON.stringify({ source: r.value }) });
  toast(r.value === 'x_api' ? '真实 X API 尚未接入，请先用模拟数据' : '数据源已切换');
}));

$('#btnImport').onclick = async () => {
  const r = await api('/api/import', {
    method: 'POST', body: JSON.stringify({ raw: $('#pasteRaw').value }),
  });
  if (!r.ok) { $('#importMsg').textContent = r.notice; $('#importMsg').style.color = '#dc2626'; return; }
  $('#importMsg').style.color = '#059669';
  $('#importMsg').textContent = `解析成功：${r.count} 条，涉及 ${r.authors.length} 个账号`;
  toast('导入成功');
};

/* ------------------------------------------------------------ 监控页 */
function renderPicks() {
  const box = $('#pickList');
  if (!state.accounts.length) {
    box.innerHTML = '<div class="empty">还没有账号，去设置页添加。</div>';
    return;
  }
  box.innerHTML = state.accounts.map((a) => `
    <div class="pick ${state.selected.has(a.handle) ? 'on' : ''}" data-h="${a.handle}">
      <div class="avatar" style="background:${a.avatar_color}">${escapeHtml(a.initials)}</div>
      <div>
        <div style="font-weight:600;font-size:13px">@${escapeHtml(a.handle)}</div>
        <div class="hint">${fmtNum(a.followers)} 粉丝</div>
      </div>
    </div>`).join('');
  $$('.pick').forEach((p) => (p.onclick = () => {
    const h = p.dataset.h;
    state.selected.has(h) ? state.selected.delete(h) : state.selected.add(h);
    p.classList.toggle('on');
    updatePickCount();
    setStep(state.selected.size ? 2 : 1);
  }));
  updatePickCount();
}

function updatePickCount() {
  $('#pickCount').textContent = `已选 ${state.selected.size} 个账号`;
}

$('#btnAll').onclick = () => { state.accounts.forEach((a) => state.selected.add(a.handle)); renderPicks(); setStep(2); };
$('#btnNone').onclick = () => { state.selected.clear(); renderPicks(); setStep(1); };

$$('.win').forEach((w) => (w.onclick = () => {
  $$('.win').forEach((x) => x.classList.remove('active'));
  w.classList.add('active');
  state.window = w.dataset.w;
  setStep(3);
}));

$('#btnReseed').onclick = async () => {
  await api('/api/reseed', { method: 'POST' });
  toast('已换一批模拟数据，点「立即检测」看新结果');
};

$('#btnScan').onclick = doScan;

async function doScan() {
  const btn = $('#btnScan');
  btn.disabled = true;
  const old = btn.innerHTML;
  btn.innerHTML = '<span class="spin"></span>检测中…';
  $('#scanResult').innerHTML = '<div class="card"><div class="empty">正在抓取并分析…</div></div>';
  try {
    const r = await api('/api/scan', {
      method: 'POST',
      body: JSON.stringify({
        handles: Array.from(state.selected),
        window: state.window,
        use_ai: $('#useAi').checked,
      }),
    });
    state.run = r;
    renderResult(r);
  } catch (e) {
    $('#scanResult').innerHTML = `<div class="card">${alertBox('err', '检测失败：' + e.message, doScan)}</div>`;
  } finally {
    btn.disabled = false;
    btn.innerHTML = old;
  }
}

function renderResult(r) {
  const box = $('#scanResult');
  if (!r.ok) {
    box.innerHTML = `<div class="card">${alertBox('err', escapeHtml(r.notice || '检测失败'), doScan)}</div>`;
    return;
  }
  setStep(4);
  if (!r.topics || !r.topics.length) {
    box.innerHTML = `<div class="card"><div class="empty">${escapeHtml(r.notice || '这个窗口里没有聚出话题，换个长一点的窗口试试')}</div></div>`;
    return;
  }

  // AI 错误提示
  let alerts = '';
  (r.ai?.errors || []).forEach((e) => {
    alerts += alertBox(e.code === 'no_key' ? 'nokey' : 'err',
      `<b>AI 环节未生效：</b>${aiErrorHtml(e)}`, e.retryable ? doScan : null);
  });

  const postsByTopic = r.posts_by_topic || {};
  const checked = r.safety && r.safety.checked;
  const topicsHtml = r.topics.map((t) => {
    const samples = (postsByTopic[t.id] || []).slice(0, 3).map((p) => {
      const rk = p.risk && p.risk.risky
        ? `<span class="risk-tag">⚠ ${escapeHtml((p.risk.categories || [])[0] || '风险')}</span>` : '';
      return `<div class="sample-post ${p.risk && p.risk.risky ? 'risky' : ''}">${rk}<b>@${escapeHtml(p.author_handle)}</b> · ${escapeHtml(p.text.slice(0, 140))}…</div>`;
    }).join('');

    const riskHtml = t.risk_count
      ? `<div class="risk">⚠️ 这个话题里有 <b>${t.risk_count}</b> 条被判为风险内容：${escapeHtml((t.risk_categories || []).join('、') || '未分类')} —— 话题保留在榜上，跟不跟由你决定</div>`
      : '';

    const hot = Number(t.velocity) >= 1.5;
    const aiDims = (t.meme != null)
      ? `<span class="dim">玩梗 <b>${t.meme}</b></span>
         <span class="dim">搞笑 <b>${t.funny}</b></span>
         <span class="dim">Drama <b>${t.drama}</b></span>
         <span class="tag-ai">AI 打分</span>`
      : `<span class="dim muted">玩梗 / 搞笑 / Drama <b>未打分</b>（AI 未参与，按中性值处理，不影响本次排序）</span>`;

    return `
    <div class="topic ${t.risk_count ? 'has-risk' : ''}" data-tid="${t.id}">
      <div class="rank ${t.rank <= 3 ? 'r' + t.rank : ''}">${t.rank}</div>
      <div class="topic-main">
        ${riskHtml}
        <div class="topic-title">${escapeHtml(t.label)}
          ${t.named_by_ai ? '<span class="hint"> · AI 命名</span>' : '<span class="hint"> · 未接 AI，使用关键词命名</span>'}</div>
        ${t.summary ? `<div class="topic-sum">${escapeHtml(t.summary)}</div>` : ''}
        <div class="dims">
          <span class="dim">提及 <b>${t.post_count}</b> 条</span>
          <span class="dim">覆盖 <b>${t.author_count}</b> 个账号</span>
          <span class="dim">互动 <b>${fmtNum(t.engagement_total)}</b></span>
          <span class="dim">新鲜度 <b>${t.freshness}</b></span>
          <span class="dim ${hot ? 'hot' : ''}">${hot ? '🔥 ' : ''}升温 <b>${t.velocity}×</b></span>
          <span class="dim">未饱和 <b>${t.unsat}</b></span>
        </div>
        <div class="dims">${aiDims}</div>
        <div class="why"><b>为什么排第 ${t.rank}：</b>${escapeHtml(t.rank_reason)}</div>
        <div class="kw">${(t.keywords || []).slice(0, 6).map((k) => `<span>${escapeHtml(k)}</span>`).join('')}</div>
        ${samples ? `<div class="sample">${samples}</div>` : ''}
      </div>
      <div class="heat">
        <div class="heat-num">${t.heat}</div>
        <div class="heat-lab">热度分</div>
        <div class="bar"><span style="width:${Math.max(4, t.heat)}%"></span></div>
      </div>
    </div>`;
  }).join('');

  state.picks = (r.selection || []).map((s) => ({ ...s }));

  box.innerHTML = `
    <div class="card">
      ${alerts}
      ${safetyBanner(r.safety)}
      <div class="result-head">
        <h2 style="margin:0">④ 热点榜单</h2>
        <span class="badge">${escapeHtml(r.window_label)}</span>
        <span class="hint">抓到 ${r.post_count} 条帖子 · 聚出 ${r.topics.length} 个话题 ·
          分数仅在本窗口内可比</span>
      </div>
      <div class="formula">热度分 = 互动 20% + 账号 20% + 提及 15% + 新鲜度 15% + 升温 10%
        + 玩梗 5% + 搞笑 5% + Drama 5% + 未饱和 5%
        <span class="muted">（后三项由 AI 打分，前六项按窗口内数据归一化）</span></div>
      ${topicsHtml}
    </div>
    <div class="card">
      <h2 style="margin-bottom:4px">⑤ 最值得 TelyClaw 跟进</h2>
      <p class="desc">AI 推荐了 ${state.picks.length} 个。每个都可以下拉换成榜单上的其他热点 —— 人可以随时改 AI 的判断。</p>
      <div class="select-grid" id="selectGrid"></div>
    </div>`;
  renderSelection();
}

function renderSelection() {
  const grid = $('#selectGrid');
  if (!grid) return;
  const topics = state.run.topics || [];
  const used = new Set(state.picks.map((p) => p.topic_id));
  grid.innerHTML = state.picks.map((p, i) => {
    const t = topics.find((x) => x.id === p.topic_id) || {};
    const opts = topics.map((x) =>
      `<option value="${x.id}" ${x.id === p.topic_id ? 'selected' : ''}>${escapeHtml(x.label)}（热度 ${x.heat}）</option>`
    ).join('');
    return `
      <div class="sel ${p.recommended ? '' : 'manual'}">
        <div class="sel-head">
          <span class="sel-tag">${p.recommended ? 'AI 推荐' : '手动指定'}</span>
          <span class="sel-title">${escapeHtml(t.label || p.topic_id)}</span>
        </div>
        <div class="sel-reason">${escapeHtml(p.reason)}</div>
        <select data-idx="${i}">${opts}</select>
      </div>`;
  }).join('');

  $$('#selectGrid select').forEach((s) => (s.onchange = () => {
    const i = Number(s.dataset.idx);
    state.picks[i] = {
      topic_id: s.value,
      reason: '你手动换入的这个热点（不是 AI 推荐）',
      recommended: false,
    };
    renderSelection();
    toast('已更换');
  }));
  setStep(5);
}

/* ------------------------------------------------------------ 工作台 */
function renderStudioTopics() {
  const box = $('#studioTopics');
  const run = state.run;
  if (!run || !run.topics || !run.topics.length) {
    $('#studioEmpty').classList.remove('hidden');
    box.innerHTML = '';
    return;
  }
  $('#studioEmpty').classList.add('hidden');
  const list = state.picks.length
    ? state.picks.map((p) => run.topics.find((t) => t.id === p.topic_id)).filter(Boolean)
    : run.topics.slice(0, 5);
  box.innerHTML = list.map((t) =>
    `<div class="st ${state.studioTopicId === t.id ? 'on' : ''}" data-tid="${t.id}">
        ${escapeHtml(t.label)} <span class="hint">· 热度 ${t.heat}</span>
     </div>`).join('');
  $$('.st').forEach((el) => (el.onclick = () => {
    state.studioTopicId = el.dataset.tid;
    state.angle = null; state.draftId = null;
    renderStudioTopics();
    loadAngles();
  }));
}

async function loadAngles() {
  const card = $('#angleCard');
  card.classList.remove('hidden');
  const t = (state.run.topics || []).find((x) => x.id === state.studioTopicId);
  $('#angleTopicName').textContent = t ? t.label : '';
  $('#angleList').innerHTML = '<div class="empty">AI 正在生成 3 个内容角度…</div>';
  $('#draftCard').classList.add('hidden');
  $('#editorCard').classList.add('hidden');

  const r = await api('/api/angles', {
    method: 'POST', body: JSON.stringify({ topic_id: state.studioTopicId }),
  });
  if (!r.ok) {
    $('#angleList').innerHTML = alertBox(r.error?.code === 'no_key' ? 'nokey' : 'err',
      aiErrorHtml(r.error), r.error?.retryable ? loadAngles : null);
    return;
  }
  state.angles = r.angles;
  $('#angleList').innerHTML = r.angles.map((a, i) => `
    <div class="angle" data-i="${i}">
      <h4>${i + 1}. ${escapeHtml(a.title)}</h4>
      <p>${escapeHtml(a.rationale)}</p>
      ${a.hook ? `<div class="hook">开头钩子：${escapeHtml(a.hook)}</div>` : ''}
    </div>`).join('');
  $$('.angle').forEach((el) => (el.onclick = () => {
    $$('.angle').forEach((x) => x.classList.remove('on'));
    el.classList.add('on');
    state.angle = state.angles[Number(el.dataset.i)];
    generateDrafts();
  }));
}

async function generateDrafts() {
  const card = $('#draftCard');
  card.classList.remove('hidden');
  $('#draftAngleName').textContent = state.angle.title;
  $('#draftList').innerHTML = '<div class="empty">AI 正在按这个角度写 3 条帖子…</div>';
  $('#editorCard').classList.add('hidden');

  const r = await api('/api/drafts/generate', {
    method: 'POST',
    body: JSON.stringify({
      topic_id: state.studioTopicId,
      angle_id: state.angle.id,
      angle_title: state.angle.title,
    }),
  });
  if (!r.ok) {
    $('#draftList').innerHTML = alertBox(r.error?.code === 'no_key' ? 'nokey' : 'err',
      aiErrorHtml(r.error), r.error?.retryable ? generateDrafts : null);
    return;
  }
  state.drafts = r.drafts;
  $('#draftList').innerHTML = r.drafts.map((d, i) => `
    <div class="draft" data-i="${i}">
      <div class="style">${escapeHtml(d.style)}</div>
      <div class="txt">${escapeHtml(d.content)}</div>
    </div>`).join('');
  $$('.draft').forEach((el) => (el.onclick = () => {
    $$('.draft').forEach((x) => x.classList.remove('on'));
    el.classList.add('on');
    state.draftId = state.drafts[Number(el.dataset.i)].id;
    openEditor(state.drafts[Number(el.dataset.i)]);
  }));
}

function openEditor(d) {
  $('#editorCard').classList.remove('hidden');
  $('#editor').value = d.content;
  updateChars();
  $('#editorCard').scrollIntoView({ behavior: 'smooth', block: 'center' });
}

$('#editor').addEventListener('input', updateChars);
function updateChars() {
  const n = $('#editor').value.length;
  const el = $('#charCount');
  el.textContent = `${n} / 280`;
  el.classList.toggle('over', n > 280);
}

$('#btnSaveDraft').onclick = async () => {
  if (!state.draftId) return;
  await api(`/api/drafts/${state.draftId}`, {
    method: 'PUT', body: JSON.stringify({ content: $('#editor').value }),
  });
  toast('已保存修改');
};

$('#btnPublish').onclick = () => {
  if (!state.draftId) return;
  $('#pvText').textContent = $('#editor').value;
  $('#pvTime').textContent = new Date().toLocaleString('zh-CN');
  $('#publishModal').classList.remove('hidden');
};
$('#btnCancelPublish').onclick = () => $('#publishModal').classList.add('hidden');

$('#btnConfirmPublish').onclick = async () => {
  const content = $('#editor').value;
  await api(`/api/drafts/${state.draftId}`, { method: 'PUT', body: JSON.stringify({ content }) });
  const r = await api('/api/publish', {
    method: 'POST', body: JSON.stringify({ draft_id: state.draftId }),
  });
  $('#publishModal').classList.add('hidden');
  if (!r.ok) { toast('发布失败'); return; }
  copyText(content);
  toast('已发布 · 文案已复制到剪贴板');
  $('#editorCard').classList.add('hidden');
  state.draftId = null;
  loadRecords();
};

function copyText(t) {
  try {
    navigator.clipboard.writeText(t);
  } catch (e) {
    const ta = document.createElement('textarea');
    ta.value = t; document.body.appendChild(ta); ta.select();
    try { document.execCommand('copy'); } catch (_) {}
    document.body.removeChild(ta);
  }
}

/* ------------------------------------------------------------ 发布记录 */
async function loadRecords() {
  const pub = await api('/api/published');
  const dft = await api('/api/drafts');
  $('#pubEmpty').classList.toggle('hidden', pub.length > 0);
  $('#draftEmpty').classList.toggle('hidden', dft.length > 0);
  const render = (list, isPub) => list.map((d) => `
    <div class="record">
      <div class="meta">
        <span class="tag ${isPub ? 'pub' : 'dft'}">${isPub ? '已发布' : '草稿'}</span>
        ${d.topic_label ? `<span>热点：${escapeHtml(d.topic_label)}</span>` : ''}
        ${d.angle_title ? `<span>角度：${escapeHtml(d.angle_title)}</span>` : ''}
        ${d.style ? `<span>风格：${escapeHtml(d.style)}</span>` : ''}
        <span>${escapeHtml(d.published_at || d.created_at || '')}</span>
        ${d.edited ? '<span>已编辑</span>' : ''}
      </div>
      <div class="txt">${escapeHtml(d.content)}</div>
    </div>`).join('');
  $('#publishedList').innerHTML = render(pub, true);
  $('#draftBox').innerHTML = render(dft, false);
}

/* ------------------------------------------------------------ 启动 */
(async function init() {
  await loadAccounts();
  await loadSettings();
  state.run = await api('/api/last_run');
  if (state.run && state.run.topics && state.run.topics.length) {
    renderResult(state.run);
  }
  setStep(2);
})();
