// Dashboard Component
// Depends on: Chart.js, fetchJSON(), loadTab(), currentTab

async function renderDashboard(el) {
  const today = getToday();
  const yearMonth = today.slice(0, 7);
  const dayNames = ['日','一','二','三','四','五','六'];
  const dayLabel = `周${dayNames[new Date(today).getDay()]}`;

  // Show skeleton immediately
  el.innerHTML = `
    <h2>🥟 小胖包子王</h2>
    <p style="font-size:13px;color:var(--muted);margin-top:-8px;margin-bottom:16px">${today} ${dayLabel}</p>
    <div class="stat-row">
      <div class="stat-card"><div class="stat-value" style="color:var(--good)">—</div><div class="stat-label">本月收入</div></div>
      <div class="stat-card"><div class="stat-value" style="color:var(--warn)">—</div><div class="stat-label">本月支出</div></div>
      <div class="stat-card"><div class="stat-value">—</div><div class="stat-label">本月利润</div></div>
    </div>
    <div class="card"><p style="text-align:center;color:var(--muted);padding:20px 0">加载中...</p></div>
  `;

  try {
    const data = await fetchJSON(`${API}/dashboard`);
    const { today_staff, staff, accounting, total_wages } = data;
    const staffMap = {};
    staff.forEach(s => { staffMap[s.id] = s; });

    const todayStaff = today_staff.map(s => {
      const st = staffMap[s.staff_id];
      return { name: st ? st.name : s.staff_id, hours: s.hours || 11 };
    });

    const totalIncome = accounting.total_income || 0;
    const totalExpense = accounting.total_expense || 0;
    const netProfit = totalIncome - totalExpense;
    const profitRate = totalIncome > 0 ? (netProfit / totalIncome * 100).toFixed(1) : 0;

    // Build income by platform
    const incomeEntries = Object.entries(accounting.income || {}).sort((a, b) => b[1] - a[1]);
    const totalIncomeSum = incomeEntries.reduce((s, [, v]) => s + v, 0);

    // Build expense breakdown
    const expenseEntries = Object.entries(accounting.expense || {}).sort((a, b) => b[1] - a[1]);
    const totalExpenseSum = expenseEntries.reduce((s, [, v]) => s + v, 0);

    // Build daily income data for chart
    const dailyChartData = [];
    const daysInMonth = new Date(parseInt(yearMonth), parseInt(yearMonth.split('-')[1]), 0).getDate();
    // Fetch each day's data (or use monthly API which might have daily breakdown)
    // For now, we'll show what we have from the monthly data

    const dayNames = ['日','一','二','三','四','五','六'];
    const todayObj = new Date(today);
    const dayLabel = `周${dayNames[todayObj.getDay()]}`;

    let html = `
      <h2>🥟 小胖包子王</h2>
      <p style="font-size:13px;color:var(--muted);margin-top:-8px;margin-bottom:16px">${today} ${dayLabel}</p>

      <div class="stat-row">
        <div class="stat-card">
          <div class="stat-value" style="color:var(--good)">¥${totalIncome.toFixed(0)}</div>
          <div class="stat-label">本月收入</div>
        </div>
        <div class="stat-card">
          <div class="stat-value" style="color:var(--warn)">¥${totalExpense.toFixed(0)}</div>
          <div class="stat-label">本月支出</div>
        </div>
        <div class="stat-card">
          <div class="stat-value" style="color:${netProfit >= 0 ? 'var(--good)' : 'var(--danger)'}">¥${netProfit.toFixed(0)}</div>
          <div class="stat-label">本月利润</div>
        </div>
      </div>

      <div class="card">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
          <h3 style="margin:0">🏆 利润率</h3>
          <span style="font-size:22px;font-weight:700;color:${netProfit >= 0 ? 'var(--good)' : 'var(--danger)'}">${profitRate}%</span>
        </div>
        <div style="display:flex;justify-content:space-between;font-size:13px;color:var(--muted)">
          <span>👥 今日上班 ${todayStaff.length}人</span>
          ${totalWages > 0 ? `<span>本月工资 ¥${totalWages.toFixed(0)}</span>` : ''}
        </div>
        ${todayStaff.length > 0
          ? `<div style="display:flex;flex-wrap:wrap;gap:6px;margin-top:10px">
              ${todayStaff.map(st => `<span style="background:var(--primary-light);color:var(--primary);padding:4px 10px;border-radius:12px;font-size:13px;font-weight:600">${st.name} ${st.hours}h</span>`).join('')}
             </div>`
          : '<p style="color:var(--muted);font-size:13px;padding:8px 0 0 0">今日暂无排班</p>'
        }
      </div>
    `;

    // Income by platform
    if (incomeEntries.length > 0) {
      const maxIncome = incomeEntries[0][1];
      let incomeHtml = incomeEntries.map(([k, v]) => {
        const pct = totalIncomeSum > 0 ? (v / totalIncomeSum * 100).toFixed(0) : 0;
        const barWidth = maxIncome > 0 ? (v / maxIncome * 100) : 0;
        return `<div style="margin-bottom:10px">
          <div style="display:flex;justify-content:space-between;font-size:13px;margin-bottom:4px">
            <span>${k}</span>
            <strong>¥${v.toFixed(0)}</strong>
          </div>
          <div style="height:6px;background:var(--border);border-radius:3px;overflow:hidden">
            <div style="height:100%;width:${barWidth}%;background:var(--primary);border-radius:3px;transition:width 0.3s"></div>
          </div>
          <div style="font-size:11px;color:var(--muted);margin-top:2px">占比 ${pct}%</div>
        </div>`;
      }).join('');
      html += `<div class="card"><h3>📈 各平台收入</h3>${incomeHtml}</div>`;
    }

    // Expense breakdown
    if (expenseEntries.length > 0) {
      let expenseHtml = expenseEntries.map(([k, v]) => {
        const pct = totalExpenseSum > 0 ? (v / totalExpenseSum * 100).toFixed(0) : 0;
        return `<div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid var(--border)">
          <span>${k}</span>
          <strong style="color:var(--warn)">¥${v.toFixed(0)} (${pct}%)</strong>
        </div>`;
      }).join('');
      html += `<div class="card"><h3>💸 本月支出</h3>${expenseHtml}</div>`;
    }

    // Daily income chart
    html += '<div class="card"><h3>📅 本月每日收入</h3><div class="chart-wrap"><canvas id="dashboardChart"></canvas></div></div>';

    // Bottom nav buttons
    html += `
      <div class="card" style="margin-top:16px">
        <div style="display:flex;gap:8px">
          <button class="btn" onclick="loadTab('schedule')" style="flex:1">📋 排班</button>
          <button class="btn btn-outline" onclick="loadTab('accounting')" style="flex:1">💰 记账</button>
          <button class="btn btn-outline" onclick="loadTab('staff')" style="flex:1">👤 工资</button>
        </div>
      </div>
    `;

    el.innerHTML = html;

    // Render chart
    renderDailyChart(yearMonth);

  } catch(e) {
    el.innerHTML = `<div class="card"><p style="color:var(--danger)">加载失败: ${e.message}</p></div>`;
  }
}

async function renderDailyChart(yearMonth) {
  const canvas = document.getElementById('dashboardChart');
  if (!canvas) return;
  if (canvas._chartInstance) canvas._chartInstance.destroy();

  try {
    const monthlyData = await fetchJSON(`${API}/accounting/monthly?year_month=${yearMonth}`);
    const labels = ['收入', '支出', '利润'];
    const income = monthlyData.total_income || 0;
    const expense = monthlyData.total_expense || 0;
    const profit = income - expense;

    canvas._chartInstance = new Chart(canvas, {
      type: 'bar',
      data: {
        labels,
        datasets: [{
          label: '金额 (¥)',
          data: [income, expense, profit],
          backgroundColor: ['var(--good)', 'var(--warn)', 'var(--primary)'],
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          y: { beginAtZero: true, ticks: { font: { size: 11 } } },
        },
      },
    });
  } catch(e) {
    // silent fail
  }
}
