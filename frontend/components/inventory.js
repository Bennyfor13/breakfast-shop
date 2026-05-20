// Inventory Dashboard Component
// Depends on: Chart.js, fetchJSON(), showToast(), loadTab(), currentTab

let forecastResult = null;

async function renderInventory(el) {
  try {
    const [menu, stocks] = await Promise.all([
      fetchJSON(`${API}/menu`),
      fetchJSON(`${API}/inventory/stocks`),
    ]);
    const stockMap = {};
    stocks.forEach(s => { stockMap[s.name] = s; });

    let html = '<h2>备料预测</h2>';

    // Sales prediction form — grid of items × quantity
    html += '<div class="card"><h3>预测销量</h3>';
    html += '<div class="sales-grid">';
    menu.forEach(m => {
      html += `<div style="display:flex;align-items:center;gap:6px">
        <span style="flex:1;font-size:13px">${m.name}</span>
        <input type="number" class="sales-qty" data-id="${m.id}" value="0" min="0" max="999"
          style="width:60px;padding:4px 6px;font-size:13px;border:1px solid var(--border);border-radius:4px;text-align:center">
        <span style="font-size:11px;color:var(--muted)">份</span>
      </div>`;
    });
    html += '</div>';
    html += '<button class="btn" onclick="handleCalcForecast()" style="margin-top:12px">计算备料</button>';
    html += '</div>';

    // Results area
    html += '<div id="forecast-results"></div>';

    // Waste feedback
    html += '<h3 style="margin-top:16px">备料反馈</h3>';
    html += '<button id="waste-toggle" class="btn btn-sm btn-outline" onclick="showForm(\'waste-form\',\'waste-toggle\')" style="margin-bottom:12px">新增反馈</button>';
    html += '<div id="waste-form" class="card" style="display:none">';
    html += '<div class="form-group"><label>日期</label><input id="waste-date" type="date" value="' + getToday() + '"></div>';
    html += '<div class="form-group"><label>哪些备多了 (一行一个: 原料名 用量)</label><textarea id="waste-over" rows="3" placeholder="中筋面粉 500g"></textarea></div>';
    html += '<div class="form-group"><label>哪些不够 (一行一个: 原料名 用量)</label><textarea id="waste-under" rows="3" placeholder="猪前腿肉 200g"></textarea></div>';
    html += '<button class="btn btn-sm" onclick="handleSaveWaste()">保存反馈</button> ';
    html += '<button class="btn btn-sm btn-outline" onclick="hideForm(\'waste-form\',\'waste-toggle\')">取消</button>';
    html += '</div>';

    el.innerHTML = html;

  } catch (e) {
    el.innerHTML = `<div class="card"><p>加载失败: ${e.message}</p></div>`;
  }
}

async function handleCalcForecast() {
  const inputs = document.querySelectorAll('.sales-qty');
  const pairs = [];
  inputs.forEach(inp => {
    const qty = parseInt(inp.value) || 0;
    if (qty > 0) pairs.push(`${inp.dataset.id}:${qty}`);
  });
  if (pairs.length === 0) {
    showToast('请至少输入一个菜品的销量');
    return;
  }
  try {
    const data = await fetchJSON(`${API}/inventory/forecast?sales=${encodeURIComponent(pairs.join(','))}`);
    const [stocks] = await Promise.all([
      fetchJSON(`${API}/inventory/stocks`),
    ]);
    const stockMap = {};
    stocks.forEach(s => { stockMap[s.name] = s; });

    let html = '<div class="card"><h3>采购清单</h3>';
    html += '<table><tr><th>原料</th><th>库存</th><th>需求</th><th>需采购</th></tr>';

    const allNames = new Set([...Object.keys(data.needs), ...Object.keys(data.purchases)]);
    allNames.forEach(name => {
      const need = data.needs[name] || 0;
      const purchase = data.purchases[name] || 0;
      const stock = stockMap[name];
      const current = stock ? stock.current : 0;
      const rowStyle = purchase > 0 ? 'color:var(--danger);font-weight:600' : 'color:var(--good)';
      html += `<tr>
        <td>${name}</td>
        <td>${current}g</td>
        <td>${need}g</td>
        <td style="${rowStyle}">${purchase > 0 ? purchase + 'g' : '库存够'}</td>
      </tr>`;
    });
    html += '</table></div>';

    document.getElementById('forecast-results').innerHTML = html;
  } catch (e) {
    showToast('计算失败: ' + e.message);
  }
}

async function handleSaveWaste() {
  const date = document.getElementById('waste-date').value;
  const overRaw = document.getElementById('waste-over').value.trim();
  const underRaw = document.getElementById('waste-under').value.trim();

  const over_prepared = {};
  const under_prepared = {};

  function parseLines(text) {
    const result = {};
    if (!text) return result;
    for (const line of text.split(/[\n,，]+/)) {
      const m = line.trim().match(/^(.+?)\s+(\d+(?:\.\d+)?)\s*(g|kg|ml|个)?$/);
      if (m) {
        const name = m[1].trim();
        let val = parseFloat(m[2]);
        if (m[3] === 'kg') val *= 1000;
        result[name] = val;
      }
    }
    return result;
  }

  Object.assign(over_prepared, parseLines(overRaw));
  Object.assign(under_prepared, parseLines(underRaw));

  if (Object.keys(over_prepared).length === 0 && Object.keys(under_prepared).length === 0) {
    showToast('请输入至少一条反馈');
    return;
  }

  try {
    const res = await fetch(`${API}/waste`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ date, over_prepared, under_prepared }),
    });
    if (!res.ok) { const e = await res.json(); throw new Error(e.detail || '请求失败'); }
    showToast('反馈已保存');
    hideForm('waste-form', 'waste-toggle');
  } catch (e) {
    showToast('保存失败: ' + e.message);
  }
}
