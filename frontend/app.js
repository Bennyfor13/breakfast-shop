const API = '/api';
let currentTab = 'schedule';

// ── helpers ──────────────────────────────────────────

async function fetchJSON(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

function getMonday(d) {
  const day = d.getDay();
  const diff = d.getDate() - day + (day === 0 ? -6 : 1);
  const monday = new Date(d.setDate(diff));
  return monday.toISOString().slice(0, 10);
}

function dayName(dateStr) {
  const d = new Date(dateStr);
  return ['周日','周一','周二','周三','周四','周五','周六'][d.getDay()];
}

function getToday() {
  return new Date().toISOString().slice(0, 10);
}

function showToast(msg) {
  const old = document.getElementById('toast');
  if (old) old.remove();
  const t = document.createElement('div');
  t.id = 'toast';
  t.style.cssText = 'position:fixed;bottom:24px;left:50%;transform:translateX(-50%);background:#333;color:#fff;padding:10px 24px;border-radius:20px;font-size:14px;z-index:999;white-space:nowrap;';
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 2500);
}

function showForm(formId, btnId) {
  document.getElementById(formId).style.display = 'block';
  document.getElementById(btnId).style.display = 'none';
}

function hideForm(formId, btnId) {
  document.getElementById(formId).style.display = 'none';
  document.getElementById(btnId).style.display = 'inline-block';
}

// ── navigation ───────────────────────────────────────

document.querySelectorAll('nav button').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('nav button').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    currentTab = btn.dataset.tab;
    loadTab(currentTab);
  });
});

function loadTab(tab) {
  const content = document.getElementById('content');
  content.innerHTML = '<div class="loading">加载中...</div>';
  switch(tab) {
    case 'schedule': renderSchedule(content); break;
    case 'inventory': renderInventory(content); break;
    case 'pricing': renderPricing(content); break;
    case 'payroll': renderPayroll(content); break;
    case 'staff': renderStaff(content); break;
    case 'menu': renderMenu(content); break;
  }
}

// ═══════════════════════════════════════════════════════
//  1. Staff Tab — list + create form
// ═══════════════════════════════════════════════════════

async function renderStaff(el) {
  try {
    const data = await fetchJSON(`${API}/staff`);
    let html = '<h2>员工管理</h2>';

    html += `<button id="staff-toggle" class="btn btn-sm btn-outline" onclick="showForm('staff-form','staff-toggle')" style="margin-bottom:12px">➕ 新增员工</button>`;
    html += `<div id="staff-form" class="card" style="display:none">`;
    html += `<div class="form-group"><label>姓名</label><input id="staff-name" placeholder="姓名"></div>`;
    html += `<div class="form-group"><label>角色</label>`;
    html += `<label class="cb-label"><input type="checkbox" value="后厨" class="staff-role"> 后厨</label>`;
    html += `<label class="cb-label"><input type="checkbox" value="传菜" class="staff-role"> 传菜</label>`;
    html += `<label class="cb-label"><input type="checkbox" value="收银" class="staff-role"> 收银</label>`;
    html += `</div>`;
    html += `<div class="form-group"><label>早班工资</label><input id="staff-morning" type="number" value="80"></div>`;
    html += `<div class="form-group"><label>晚班工资</label><input id="staff-evening" type="number" value="60"></div>`;
    html += `<div class="form-group"><label>备注</label><input id="staff-note" placeholder="可选"></div>`;
    html += `<button class="btn btn-sm" onclick="handleCreateStaff()">保存</button> `;
    html += `<button class="btn btn-sm btn-outline" onclick="hideForm('staff-form','staff-toggle')">取消</button>`;
    html += `</div>`;

    data.forEach(s => {
      html += `<div class="card"><h3>${s.name}</h3>`;
      html += `<p>角色: ${s.roles.join(' / ')} | 早班 ¥${s.morning_rate} / 晚班 ¥${s.evening_rate}</p>`;
      if (s.note) html += `<p style="font-size:12px;color:var(--muted)">${s.note}</p>`;
      html += '</div>';
    });
    el.innerHTML = html;
  } catch(e) {
    el.innerHTML = `<div class="card"><p>加载失败: ${e.message}</p><p>请先确认服务器已启动并运行种子数据。</p></div>`;
  }
}

async function handleCreateStaff() {
  const name = document.getElementById('staff-name').value.trim();
  if (!name) { showToast('请输入姓名'); return; }
  const roles = [...document.querySelectorAll('.staff-role:checked')].map(cb => cb.value);
  if (roles.length === 0) { showToast('请选择角色'); return; }
  const morning = document.getElementById('staff-morning').value || '80';
  const evening = document.getElementById('staff-evening').value || '60';
  const note = document.getElementById('staff-note').value;

  const params = new URLSearchParams({name, morning_rate: morning, evening_rate: evening, note});
  roles.forEach(r => params.append('roles', r));

  try {
    const res = await fetch(`${API}/staff?${params}`, {method: 'POST'});
    if (!res.ok) { const e = await res.json(); throw new Error(e.detail || '请求失败'); }
    showToast('员工已添加');
    loadTab(currentTab);
  } catch(e) {
    showToast('保存失败: ' + e.message);
  }
}

// ═══════════════════════════════════════════════════════
//  2. Menu Tab — now in components/menu.js
// ═══════════════════════════════════════════════════════

// ═══════════════════════════════════════════════════════
//  3. Schedule Tab — now in components/schedule.js
// ═══════════════════════════════════════════════════════

// ═══════════════════════════════════════════════════════
//  4. Inventory Tab — now in components/inventory.js
// ═══════════════════════════════════════════════════════

// ═══════════════════════════════════════════════════════
//  5. Pricing Tab — now in components/pricing.js
// ═══════════════════════════════════════════════════════

// ═══════════════════════════════════════════════════════
//  6. Payroll Tab — now in components/payroll.js
// ═══════════════════════════════════════════════════════

// ── initial load ─────────────────────────────────────

const initialTab = window.INITIAL_TAB || 'schedule';
document.querySelector(`nav button[data-tab="${initialTab}"]`)?.classList.add('active');
loadTab(initialTab);
