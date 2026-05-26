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

function loadTab(tab, extra) {
  const content = document.getElementById('content');
  content.innerHTML = '<div class="loading">加载中...</div>';
  switch(tab) {
    case 'schedule': renderSchedule(content, extra); break;
    case 'inventory': renderInventory(content); break;
    case 'accounting': renderAccounting(); break;
    case 'pricing': renderPricing(content); break;
    case 'staff': renderStaff(content); break;
    case 'menu': renderMenu(content); break;
  }
}

// ═══════════════════════════════════════════════════════
//  1. Staff Tab — now in components/staff.js
// ═══════════════════════════════════════════════════════

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
