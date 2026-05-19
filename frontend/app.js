const API = '/api';

async function fetchJSON(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

document.querySelectorAll('nav button').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('nav button').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    loadTab(btn.dataset.tab);
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

async function renderSchedule(el) {
  const weekStart = getMonday(new Date());
  try {
    const data = await fetchJSON(`${API}/schedule?week_start=${weekStart}`);
    const byDate = {};
    data.shifts.forEach(s => {
      byDate[s.date] = byDate[s.date] || {早班: [], 晚班: []};
      byDate[s.date][s.period].push(s);
    });

    let html = '<h2>本周排班 (' + weekStart + ')</h2>';
    for (const [date, periods] of Object.entries(byDate).sort()) {
      html += `<div class="card"><h3>${date} ${dayName(date)}</h3>`;
      for (const [period, shifts] of Object.entries(periods)) {
        html += `<p><strong>${period}:</strong> `;
        html += shifts.map(s => `${s.staff_id}(${s.role})`).join(' / ') || '—';
        html += '</p>';
      }
      html += '</div>';
    }
    el.innerHTML = html;
  } catch(e) {
    el.innerHTML = `<div class="card"><p>加载失败: ${e.message}</p><p>请先确认服务器已启动并运行种子数据。</p></div>`;
  }
}

async function renderInventory(el) {
  const sales = prompt("输入预测销量 (格式: m1:100,m2:50):", "m1:100,m2:50,m3:80,m4:60,m5:40");
  if (!sales) { el.innerHTML = '<div class="card"><p>已取消</p></div>'; return; }
  try {
    const data = await fetchJSON(`${API}/inventory/forecast?sales=${encodeURIComponent(sales)}`);
    let html = '<h2>备料预测</h2>';
    html += '<div class="card"><h3>原料需求</h3><table><tr><th>原料</th><th>用量</th><th>需采购</th></tr>';
    for (const [name, need] of Object.entries(data.needs)) {
      const purchase = data.purchases[name] || 0;
      html += `<tr><td>${name}</td><td>${need}g</td><td style="color:${purchase > 0 ? 'var(--warn)' : 'var(--good)'}">${purchase > 0 ? purchase + 'g' : '库存够'}</td></tr>`;
    }
    html += '</table></div>';
    el.innerHTML = html;
  } catch(e) {
    el.innerHTML = `<div class="card"><p>加载失败: ${e.message}</p></div>`;
  }
}

async function renderPricing(el) {
  const vols = prompt("输入月销量 (格式: m1:3000,m2:2000,m3:1500):", "m1:3000,m2:2000,m3:1500,m4:1000,m5:800");
  if (!vols) { el.innerHTML = '<div class="card"><p>已取消</p></div>'; return; }
  try {
    const data = await fetchJSON(`${API}/pricing/analysis?sales_volumes=${encodeURIComponent(vols)}`);
    let html = '<h2>利润分析</h2>';
    const badgeMap = {明星: 'star', 金牛: 'cow', 引流款: 'traffic', 考虑砍掉: 'cut'};
    data.forEach(item => {
      html += `<div class="card"><h3>${item.item_name} <span class="badge badge-${badgeMap[item.quadrant]}">${item.quadrant}</span></h3>`;
      html += `<p>售价 ¥${item.selling_price} | 成本 ¥${item.total_cost} | 毛利 ¥${item.gross_profit} (${item.margin_pct}%)</p>`;
      html += `<p style="font-size:12px;color:var(--muted)">月销 ${item.sales_volume} 份</p></div>`;
    });
    el.innerHTML = html;
  } catch(e) {
    el.innerHTML = `<div class="card"><p>加载失败: ${e.message}</p></div>`;
  }
}

async function renderPayroll(el) {
  const ym = new Date().toISOString().slice(0, 7);
  try {
    const data = await fetchJSON(`${API}/payroll?year_month=${ym}`);
    let html = `<h2>${ym} 工资单</h2>`;
    data.forEach(p => {
      html += `<div class="card"><h3>${p.staff_name}</h3>`;
      html += `<p>早班 ${p.morning_shifts}次 x ¥${p.morning_rate} + 晚班 ${p.evening_shifts}次 x ¥${p.evening_rate}</p>`;
      html += `<p>基础 ¥${p.base_pay} + 绩效 ¥${p.performance_bonus} (${p.performance_score}分) = <strong>¥${p.total}</strong></p></div>`;
    });
    if (data.length === 0) html += '<p>本月暂无排班数据，请先生成排班。</p>';
    el.innerHTML = html;
  } catch(e) {
    el.innerHTML = `<div class="card"><p>加载失败: ${e.message}</p></div>`;
  }
}

async function renderStaff(el) {
  try {
    const data = await fetchJSON(`${API}/staff`);
    let html = '<h2>员工管理</h2>';
    data.forEach(s => {
      html += `<div class="card"><h3>${s.name}</h3>`;
      html += `<p>角色: ${s.roles.join(' / ')} | 早班 ¥${s.morning_rate} / 晚班 ¥${s.evening_rate}</p>`;
      if (s.note) html += `<p style="font-size:12px;color:var(--muted)">${s.note}</p>`;
      html += '</div>';
    });
    el.innerHTML = html;
  } catch(e) {
    el.innerHTML = `<div class="card"><p>加载失败: ${e.message}</p></div>`;
  }
}

async function renderMenu(el) {
  try {
    const data = await fetchJSON(`${API}/menu`);
    let html = '<h2>菜单管理</h2>';
    data.forEach(m => {
      html += `<div class="card"><h3>${m.name} — ¥${m.price}</h3>`;
      html += '<p style="font-size:12px;color:var(--muted)">原料: ';
      html += m.bom.map(i => `${i.name} ${i.amount}${i.unit}`).join(', ');
      html += '</p></div>';
    });
    el.innerHTML = html;
  } catch(e) {
    el.innerHTML = `<div class="card"><p>加载失败: ${e.message}</p></div>`;
  }
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

loadTab('schedule');
