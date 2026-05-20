// Menu Management Component
// Depends on: fetchJSON(), showToast(), loadTab(), currentTab

async function renderMenu(el) {
  try {
    const data = await fetchJSON(`${API}/menu`);
    let html = '<h2>菜单管理</h2>';

    // Create form
    html += `<button id="menu-toggle" class="btn btn-sm btn-outline" onclick="showForm('menu-form','menu-toggle')" style="margin-bottom:12px">新增菜品</button>`;
    html += `<div id="menu-form" class="card" style="display:none">`;
    html += `<div class="form-group"><label>品名</label><input id="menu-name" placeholder="品名"></div>`;
    html += `<div class="form-group"><label>售价</label><input id="menu-price" type="number" step="0.01" placeholder="售价"></div>`;
    html += '<div class="form-group"><label>原料 (BOM)</label>';
    html += '<div id="bom-rows"></div>';
    html += '<button class="btn btn-sm btn-outline" onclick="addBomRow()" style="margin-top:6px">+ 添加原料</button>';
    html += '</div>';
    html += `<button class="btn btn-sm" onclick="handleCreateMenu()">保存</button> `;
    html += `<button class="btn btn-sm btn-outline" onclick="hideForm('menu-form','menu-toggle')">取消</button>`;
    html += `</div>`;

    // Item list
    data.forEach(m => {
      const bomText = m.bom.length
        ? m.bom.map(i => `${i.name} ${i.amount}${i.unit}`).join(', ')
        : '(空)';
      html += `<div class="card" id="menu-card-${m.id}">
        <div style="display:flex;justify-content:space-between;align-items:center">
          <h3 style="margin:0">${m.name} — ¥${m.price}</h3>
          <div style="display:flex;gap:4px">
            <button class="btn btn-sm btn-outline" onclick="copyMenuItem('${m.id}')" title="复制">📋</button>
            <button class="btn btn-sm" style="background:var(--danger);font-size:11px;padding:2px 8px" onclick="handleDeleteMenu('${m.id}')">删除</button>
          </div>
        </div>
        <p style="font-size:12px;color:var(--muted);margin-top:4px">原料: ${bomText}</p>
      </div>`;
    });
    el.innerHTML = html;

    addBomRow(); // start with one empty row

  } catch (e) {
    el.innerHTML = `<div class="card"><p>加载失败: ${e.message}</p></div>`;
  }
}

function addBomRow() {
  const container = document.getElementById('bom-rows');
  if (!container) return;
  const row = document.createElement('div');
  row.style.cssText = 'display:flex;gap:6px;margin-top:4px;align-items:center';
  row.innerHTML = `
    <input placeholder="原料名" class="bom-name" style="flex:2;padding:6px 8px;border:1px solid var(--border);border-radius:4px;font-size:13px">
    <input placeholder="用量" class="bom-amount" type="number" step="0.1" style="flex:1;padding:6px 8px;border:1px solid var(--border);border-radius:4px;font-size:13px">
    <select class="bom-unit" style="width:55px;padding:6px 4px;border:1px solid var(--border);border-radius:4px;font-size:12px">
      <option>g</option><option>ml</option><option>个</option>
    </select>
    <button onclick="this.closest('div').remove()" style="background:none;border:none;color:var(--danger);cursor:pointer;font-size:16px">✕</button>`;
  container.appendChild(row);
}

async function handleCreateMenu() {
  const name = document.getElementById('menu-name').value.trim();
  const price = document.getElementById('menu-price').value;
  if (!name) { showToast('请输入品名'); return; }
  if (!price) { showToast('请输入售价'); return; }

  const bomRows = document.querySelectorAll('#bom-rows > div');
  const bom = [];
  bomRows.forEach(row => {
    const nameEl = row.querySelector('.bom-name');
    const amountEl = row.querySelector('.bom-amount');
    const unitEl = row.querySelector('.bom-unit');
    if (nameEl && amountEl && nameEl.value.trim() && amountEl.value) {
      bom.push({
        name: nameEl.value.trim(),
        amount: parseFloat(amountEl.value),
        unit: unitEl ? unitEl.value : 'g',
      });
    }
  });

  try {
    const params = new URLSearchParams({ name, price });
    const res = await fetch(`${API}/menu?${params}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(bom),
    });
    if (!res.ok) { const e = await res.json(); throw new Error(e.detail || '请求失败'); }
    showToast('菜品已添加');
    loadTab(currentTab);
  } catch (e) {
    showToast('保存失败: ' + e.message);
  }
}

async function copyMenuItem(id) {
  try {
    const menu = await fetchJSON(`${API}/menu`);
    const item = menu.find(m => m.id === id);
    if (!item) { showToast('菜品不存在'); return; }

    document.getElementById('menu-name').value = item.name + ' (副本)';
    document.getElementById('menu-price').value = item.price;

    // Clear existing BOM rows
    const container = document.getElementById('bom-rows');
    container.innerHTML = '';

    // Fill with copied BOM
    item.bom.forEach(ing => {
      addBomRow();
      const lastRow = container.lastElementChild;
      lastRow.querySelector('.bom-name').value = ing.name;
      lastRow.querySelector('.bom-amount').value = ing.amount;
      lastRow.querySelector('.bom-unit').value = ing.unit || 'g';
    });
    if (item.bom.length === 0) addBomRow();

    showForm('menu-form', 'menu-toggle');
    showToast('已复制，请修改后保存');
  } catch (e) {
    showToast('复制失败: ' + e.message);
  }
}

async function handleDeleteMenu(id) {
  try {
    const res = await fetch(`${API}/menu/${id}`, { method: 'DELETE' });
    if (!res.ok) throw new Error('删除失败');
    showToast('已删除');
    loadTab(currentTab);
  } catch (e) {
    showToast('删除失败: ' + e.message);
  }
}
