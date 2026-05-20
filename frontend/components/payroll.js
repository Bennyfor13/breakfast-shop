// Payroll Dashboard Component
// Depends on: Chart.js (global Chart), fetchJSON(), showToast(), loadTab(), currentTab

async function renderPayroll(el) {
  const ym = new Date().toISOString().slice(0, 7);
  try {
    const [data, staffList] = await Promise.all([
      fetchJSON(`${API}/payroll?year_month=${ym}`),
      fetchJSON(`${API}/staff`)
    ]);

    if (data.length === 0) {
      el.innerHTML = '<div class="card"><p>本月暂无排班数据，请先生成排班后再查询。</p></div>';
      return;
    }

    const totalPayroll = data.reduce((s, p) => s + p.total, 0);
    const avgPay = totalPayroll / data.length;
    const maxPay = Math.max(...data.map(p => p.total));
    const minPay = Math.min(...data.map(p => p.total));

    let html = `<h2>${ym} 工资单</h2>`;

    // Stat cards
    html += '<div class="stat-row">';
    html += `<div class="stat-card"><div class="stat-value">¥${totalPayroll.toFixed(0)}</div><div class="stat-label">工资总额</div></div>`;
    html += `<div class="stat-card"><div class="stat-value">¥${avgPay.toFixed(0)}</div><div class="stat-label">人均工资</div></div>`;
    html += '</div>';
    html += '<div class="stat-row">';
    html += `<div class="stat-card"><div class="stat-value">¥${maxPay.toFixed(0)}</div><div class="stat-label">最高</div></div>`;
    html += `<div class="stat-card"><div class="stat-value">¥${minPay.toFixed(0)}</div><div class="stat-label">最低</div></div>`;
    html += '</div>';

    // Bar chart
    html += '<div class="card"><h3>工资构成</h3><div class="chart-wrap"><canvas id="payrollChart"></canvas></div></div>';

    // Detail table
    html += '<div class="card"><h3>明细</h3><table><thead><tr>';
    html += '<th>姓名</th><th>早班</th><th>晚班</th><th>加班</th><th>绩效</th><th>基础</th><th>奖金</th><th class="sort-col" onclick="sortPayrollTable()">合计 ▼</th>';
    html += '</tr></thead><tbody id="payroll-tbody">';
    data.forEach(p => {
      html += `<tr>`;
      html += `<td><strong>${p.staff_name}</strong></td>`;
      html += `<td>${p.morning_shifts}×¥${p.morning_rate}</td>`;
      html += `<td>${p.evening_shifts}×¥${p.evening_rate}</td>`;
      html += `<td>${p.overtime_shifts || 0}</td>`;
      html += `<td>${p.performance_score}分</td>`;
      html += `<td>¥${p.base_pay.toFixed(0)}</td>`;
      html += `<td>¥${p.performance_bonus.toFixed(0)}</td>`;
      html += `<td><strong>¥${p.total.toFixed(0)}</strong></td>`;
      html += `</tr>`;
    });
    html += '</tbody></table></div>';

    // Performance scoring
    html += '<h3 style="margin-top:16px">绩效评分</h3>';
    html += '<div class="card">';
    html += '<div class="form-group"><label>员工</label><select id="perf-staff">';
    staffList.forEach(s => {
      html += `<option value="${s.id}">${s.name}</option>`;
    });
    html += '</select></div>';
    html += '<div class="form-group"><label>评分 <span id="perf-display">4.0</span></label>';
    html += '<input id="perf-score" type="range" min="1" max="5" step="0.5" value="4" oninput="document.getElementById(\'perf-display\').textContent=this.value">';
    html += '<div class="range-labels"><span>1</span><span>2</span><span>3</span><span>4</span><span>5</span></div></div>';
    html += '<button class="btn" onclick="handleSavePerformance()">保存评分</button>';
    html += '</div>';

    el.innerHTML = html;

    // Draw chart
    renderPayrollChart(data);

  } catch(e) {
    el.innerHTML = `<div class="card"><p>加载失败: ${e.message}</p></div>`;
  }
}

function renderPayrollChart(data) {
  const canvas = document.getElementById('payrollChart');
  if (!canvas) return;
  // Destroy any existing chart on this canvas
  if (canvas._chartInstance) canvas._chartInstance.destroy();

  const labels = data.map(p => p.staff_name);
  const baseData = data.map(p => p.base_pay);
  const bonusData = data.map(p => p.performance_bonus);

  canvas._chartInstance = new Chart(canvas, {
    type: 'bar',
    data: {
      labels,
      datasets: [
        { label: '基础工资', data: baseData, backgroundColor: '#ff6f00' },
        { label: '绩效奖金', data: bonusData, backgroundColor: '#ffab40' },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { position: 'bottom', labels: { font: { size: 12 } } } },
      scales: {
        x: { stacked: true, ticks: { font: { size: 11 } } },
        y: { stacked: true, ticks: { font: { size: 11 }, callback: v => '¥' + v } },
      },
    },
  });
}

async function handleSavePerformance() {
  const staffId = document.getElementById('perf-staff').value;
  const score = parseFloat(document.getElementById('perf-score').value);
  try {
    const res = await fetch(`${API}/performance`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ staff_id: staffId, score }),
    });
    if (!res.ok) { const e = await res.json(); throw new Error(e.detail || '请求失败'); }
    showToast('绩效已保存');
  } catch (e) {
    showToast('保存失败: ' + e.message);
  }
}

let payrollSortDesc = true;
function sortPayrollTable() {
  const tbody = document.getElementById('payroll-tbody');
  if (!tbody) return;
  const rows = [...tbody.querySelectorAll('tr')];
  rows.sort((a, b) => {
    const va = parseFloat(a.querySelector('td:last-child strong').textContent.replace('¥', ''));
    const vb = parseFloat(b.querySelector('td:last-child strong').textContent.replace('¥', ''));
    return payrollSortDesc ? vb - va : va - vb;
  });
  payrollSortDesc = !payrollSortDesc;
  tbody.innerHTML = '';
  rows.forEach(r => tbody.appendChild(r));
}
