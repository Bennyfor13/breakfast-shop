// Pricing & P&L Dashboard Component
// Depends on: Chart.js, fetchJSON(), showToast()

let pricingData = null;

async function renderPricing(el) {
  try {
    const menu = await fetchJSON(`${API}/menu`);

    let html = '<h2>利润分析</h2>';

    // Sales volume form
    html += '<div class="card"><h3>月销量输入</h3>';
    html += '<div class="sales-grid">';
    menu.forEach(m => {
      html += `<div style="display:flex;align-items:center;gap:6px">
        <span style="flex:1;font-size:13px">${m.name}</span>
        <input type="number" class="pricing-vol" data-id="${m.id}" value="${m.id === 'm1' ? 3000 : m.id === 'm2' ? 2000 : m.id === 'm3' ? 1500 : m.id === 'm4' ? 1000 : 800}" min="0" max="99999"
          style="width:70px;padding:4px 6px;font-size:13px;border:1px solid var(--border);border-radius:4px;text-align:center">
        <span style="font-size:11px;color:var(--muted)">份</span>
      </div>`;
    });
    html += '</div>';
    html += '<button class="btn" onclick="handleCalcPricing()" style="margin-top:12px">计算利润</button>';
    html += '</div>';

    // Results area
    html += '<div id="pricing-results"></div>';

    el.innerHTML = html;

  } catch (e) {
    el.innerHTML = `<div class="card"><p>加载失败: ${e.message}</p></div>`;
  }
}

async function handleCalcPricing() {
  const inputs = document.querySelectorAll('.pricing-vol');
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
    pricingData = await fetchJSON(`${API}/pricing/analysis?sales_volumes=${encodeURIComponent(pairs.join(','))}`);

    const totalProfit = pricingData.reduce((s, i) => s + i.gross_profit * i.sales_volume, 0);
    const avgMargin = pricingData.length > 0
      ? pricingData.reduce((s, i) => s + i.margin_pct, 0) / pricingData.length
      : 0;
    const starCount = pricingData.filter(i => i.quadrant === '明星').length;
    const cutCount = pricingData.filter(i => i.quadrant === '考虑砍掉').length;

    let html = '';

    // Summary cards
    html += '<div class="stat-row">';
    html += `<div class="stat-card"><div class="stat-value">¥${totalProfit.toFixed(0)}</div><div class="stat-label">月度毛利</div></div>`;
    html += `<div class="stat-card"><div class="stat-value">${avgMargin.toFixed(1)}%</div><div class="stat-label">平均利润率</div></div>`;
    html += '</div>';
    html += '<div class="stat-row">';
    html += `<div class="stat-card"><div class="stat-value">${starCount}</div><div class="stat-label">明星产品</div></div>`;
    html += `<div class="stat-card"><div class="stat-value">${cutCount}</div><div class="stat-label">需关注</div></div>`;
    html += '</div>';

    // Quadrant scatter chart
    html += '<div class="card"><h3>产品象限</h3><div class="chart-wrap"><canvas id="quadrantChart"></canvas></div></div>';

    // Item detail cards
    const badgeMap = { '明星': 'star', '金牛': 'cow', '引流款': 'traffic', '考虑砍掉': 'cut' };
    pricingData.forEach(item => {
      html += `<div class="card">
        <h3>${item.item_name} <span class="badge badge-${badgeMap[item.quadrant]}">${item.quadrant}</span></h3>
        <p>售价 ¥${item.selling_price} | 成本 ¥${item.total_cost} | 毛利 ¥${item.gross_profit} (${item.margin_pct}%)</p>
        <p style="font-size:12px;color:var(--muted)">月销 ${item.sales_volume} 份 | 利润贡献 ¥${(item.gross_profit * item.sales_volume).toFixed(0)}</p>
      </div>`;
    });

    document.getElementById('pricing-results').innerHTML = html;

    // Draw quadrant chart
    renderQuadrantChart();

  } catch (e) {
    showToast('计算失败: ' + e.message);
  }
}

function renderQuadrantChart() {
  const canvas = document.getElementById('quadrantChart');
  if (!canvas || !pricingData) return;
  if (canvas._chartInstance) canvas._chartInstance.destroy();

  const quadColors = { '明星': '#2e7d32', '金牛': '#1565c0', '引流款': '#e65100', '考虑砍掉': '#c62828' };

  const datasets = {};
  pricingData.forEach(item => {
    const q = item.quadrant;
    if (!datasets[q]) datasets[q] = { label: q, data: [], backgroundColor: quadColors[q] + '99', borderColor: quadColors[q], borderWidth: 1 };
    datasets[q].data.push({ x: item.sales_volume, y: item.margin_pct, name: item.item_name });
  });

  canvas._chartInstance = new Chart(canvas, {
    type: 'scatter',
    data: { datasets: Object.values(datasets) },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: 'bottom', labels: { font: { size: 11 } } },
        tooltip: {
          callbacks: {
            label: ctx => {
              const p = ctx.raw;
              return `${p.name}: 销量${p.x}, 利润率${p.y}%`;
            },
          },
        },
      },
      scales: {
        x: { title: { text: '月销量(份)', display: true, font: { size: 11 } } },
        y: { title: { text: '利润率(%)', display: true, font: { size: 11 } } },
      },
    },
  });
}
