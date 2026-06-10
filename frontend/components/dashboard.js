// Dashboard Component
// Depends on: Chart.js, fetchJSON(), loadTab(), currentTab

async function renderDashboard(el) {
  try {
    const today = getToday();
    const yearMonth = today.slice(0, 7);
    const ymShort = today.slice(0, 7);

    // Fetch all data in parallel
    const [schedData, staffList, dailyData, monthlyData, costs, payroll] = await Promise.all([
      fetchJSON(`${API}/schedule?week_start=${getMonday(new Date())}`),
      fetchJSON(`${API}/staff`),
      fetchJSON(`${API}/accounting/daily?date=${today}`),
      fetchJSON(`${API}/accounting/monthly?year_month=${ymShort}`),
      fetchJSON(`${API}/accounting/fixed-costs?month=${ymShort}`),
      fetchJSON(`${API}/payroll?year_month=${ymShort}`).catch(() => []),
    ]);

    const staffMap = {};
    staffList.forEach(s => { staffMap[s.id] = s; });

    // Get today's shifts
    const todayShifts = schedData.shifts.filter(s => s.date === today);
    const todayStaff = todayShifts.map(s => {
      const st = staffMap[s.staff_id];
      return { name: st ? st.name : s.staff_id, hours: s.hours || 11 };
    });

    // Stats
    const totalIncome = monthlyData.total_income || 0;
    const totalExpense = monthlyData.total_expense || 0;
    const netProfit = totalIncome - totalExpense;
    const profitRate = totalIncome > 0 ? (netProfit / totalIncome * 100).toFixed(1) : 0;
    const totalWages = payroll.reduce((s, p) => s + (p.total || 0), 0);

    // Build income by platform
    const incomeEntries = Object.entries(monthlyData.income || {}).sort((a, b) => b[1] - a[1]);
    const totalIncomeSum = incomeEntries.reduce((s, [, v]) => s + v, 0);

    // Build expense breakdown
    const expenseEntries = Object.entries(monthlyData.expense || {}).sort((a, b) => b[1] - a[1]);
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
      <div style="padding:0 0 16px 0">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
          <div>
            <h2 style="margin:0;font-size:20px">🥟 小胖包子王</h2>
            <div style="font-size:13px;color:var(--muted);margin-top:4px">${today} ${dayLabel}</div>
          </div>
        </div>

        <!-- Stat cards -->
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

        <!-- Profit rate -->
        <div style="background:var(--primary-light);border-radius:8px;padding:12px 16px;margin-bottom:16px;display:flex;justify-content:space-between;align-items:center">
          <span style="font-size:14px;font-weight:600">🏆 利润率</span>
          <span style="font-size:22px;font-weight:700;color:${netProfit >= 0 ? 'var(--good)' : 'var(--danger)'}">${profitRate}%</span>
        </div>

        <!-- Today's staff -->
        <div class="card">
          <h3>👥 今日上班</h3>
          ${todayStaff.length > 0
            ? `<div style="display:flex;flex-wrap:wrap;gap:6px;margin-top:8px">
                ${todayStaff.map(st => `<span style="background:var(--primary-light);color:var(--primary);padding:4px 10px;border-radius:12px;font-size:13px;font-weight:600">${st.name} ${st.hours}h</span>`).join('')}
               </div>`
            : '<p style="color:var(--muted);font-size:13px;padding:8px 0">今日暂无排班</p>'
          }
          ${totalWages > 0 ? `<div style="font-size:12px;color:var(--muted);margin-top:8px">本月工资合计：¥${totalWages.toFixed(0)}</div>` : ''}
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
        <div style="display:flex;gap:8px;margin-top:16px">
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
    // Get daily breakdown from backend
    const monthlyData = await fetchJSON(`${API}/accounting/monthly?year_month=${yearMonth}`);

    // Since we don't have daily breakdown from monthly endpoint, show income/expense comparison
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
