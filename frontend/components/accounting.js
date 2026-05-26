// 记账模块
let currentDate = new Date().toISOString().split('T')[0];
let accountingTab = 'daily'; // 'daily' or 'monthly'
let currentMonth = new Date().toISOString().slice(0, 7); // "2026-05"

async function renderAccounting() {
  const content = document.getElementById('content');

  content.innerHTML = `
    <div class="accounting-page">
      <h2>📊 记账管理</h2>

      <div class="sub-tabs">
        <button class="sub-tab ${accountingTab === 'daily' ? 'active' : ''}" onclick="switchAccountingTab('daily')">日账</button>
        <button class="sub-tab ${accountingTab === 'monthly' ? 'active' : ''}" onclick="switchAccountingTab('monthly')">月报</button>
      </div>

      <div id="accounting-content"></div>

      <div id="income-modal" class="modal" style="display:none" onclick="closeModalOnBackdrop(event, 'income-modal')">
        <div class="modal-content-enhanced" onclick="event.stopPropagation()">
          <div class="modal-header">
            <h3>添加收入</h3>
            <button class="modal-close" onclick="closeIncomeModal()">×</button>
          </div>
          <form id="income-form">
            <div class="form-grid">
              <div class="form-group"><label>淘宝</label><input type="number" name="淘宝" step="0.01" placeholder="0.00"></div>
              <div class="form-group"><label>京东</label><input type="number" name="京东" step="0.01" placeholder="0.00"></div>
              <div class="form-group"><label>美团</label><input type="number" name="美团" step="0.01" placeholder="0.00"></div>
              <div class="form-group"><label>收钱吧</label><input type="number" name="收钱吧" step="0.01" placeholder="0.00"></div>
            </div>
            <div id="custom-income"></div>
            <button type="button" class="btn btn-outline" onclick="addCustomIncome()" style="width:100%;margin:12px 0">➕ 添加其他收入</button>
            <div class="modal-footer">
              <button type="button" class="btn btn-outline" onclick="closeIncomeModal()">取消</button>
              <button type="submit" class="btn">保存</button>
            </div>
          </form>
        </div>
      </div>

      <div id="expense-modal" class="modal" style="display:none" onclick="closeModalOnBackdrop(event, 'expense-modal')">
        <div class="modal-content-enhanced" onclick="event.stopPropagation()">
          <div class="modal-header">
            <h3>添加支出</h3>
            <button class="modal-close" onclick="closeExpenseModal()">×</button>
          </div>
          <form id="expense-form">
            <div class="form-grid">
              <div class="form-group"><label>快驴</label><input type="number" name="快驴" step="0.01" placeholder="0.00"></div>
              <div class="form-group"><label>美菜</label><input type="number" name="美菜" step="0.01" placeholder="0.00"></div>
              <div class="form-group"><label>现金</label><input type="number" name="现金" step="0.01" placeholder="0.00"></div>
              <div class="form-group"><label>其他</label><input type="number" name="其他" step="0.01" placeholder="0.00"></div>
            </div>
            <div id="custom-expense"></div>
            <button type="button" class="btn btn-outline" onclick="addCustomExpense()" style="width:100%;margin:12px 0">➕ 添加其他支出</button>
            <div class="modal-footer">
              <button type="button" class="btn btn-outline" onclick="closeExpenseModal()">取消</button>
              <button type="submit" class="btn">保存</button>
            </div>
          </form>
        </div>
      </div>
    </div>
  `;

  renderAccountingContent();

  setTimeout(() => {
    const incomeForm = document.getElementById('income-form');
    const expenseForm = document.getElementById('expense-form');
    if (incomeForm) incomeForm.addEventListener('submit', handleIncomeSubmit);
    if (expenseForm) expenseForm.addEventListener('submit', handleExpenseSubmit);
  }, 0);
}

function switchAccountingTab(tab) {
  accountingTab = tab;
  renderAccounting();
}

function renderAccountingContent() {
  const el = document.getElementById('accounting-content');
  if (accountingTab === 'daily') {
    el.innerHTML = `
      <div class="card" style="display:flex;justify-content:space-between;align-items:center">
        <input type="date" id="accounting-date" value="${currentDate}" onchange="onDateChange()"
               style="padding:8px 12px;border:1px solid var(--border);border-radius:6px;font-size:14px">
        <div style="display:flex;gap:8px">
          <button class="btn" onclick="showIncomeModal()">➕ 收入</button>
          <button class="btn btn-outline" onclick="showExpenseModal()">➖ 支出</button>
        </div>
      </div>
      <div id="daily-summary"></div>
      <div class="card"><h3>💰 收入明细</h3><div id="income-display">加载中...</div></div>
      <div class="card"><h3>💸 支出明细</h3><div id="expense-display">加载中...</div></div>
    `;
    loadDailyData(currentDate);
  } else {
    el.innerHTML = `
      <div class="card" style="display:flex;justify-content:space-between;align-items:center">
        <input type="month" id="accounting-month" value="${currentMonth}" onchange="onMonthChange()"
               style="padding:8px 12px;border:1px solid var(--border);border-radius:6px;font-size:14px">
      </div>
      <div id="monthly-report">加载中...</div>
    `;
    loadMonthlyData(currentMonth);
  }
}

async function handleIncomeSubmit(e) {
  e.preventDefault();
  const formData = new FormData(e.target);
  const income = {};

  for (const [key, value] of formData.entries()) {
    if (value && parseFloat(value) > 0) {
      income[key] = parseFloat(value);
    }
  }

  const customRows = document.querySelectorAll('#custom-income .custom-platform-row');
  customRows.forEach(row => {
    const name = row.querySelector('.custom-platform-name').value.trim();
    const amount = row.querySelector('.custom-platform-amount').value;
    if (name && amount && parseFloat(amount) > 0) {
      income[name] = parseFloat(amount);
    }
  });

  if (Object.keys(income).length === 0) {
    alert('请至少输入一项收入');
    return;
  }

  await fetch('/api/accounting/income', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({date: currentDate, income})
  });

  closeIncomeModal();
  e.target.reset();
  loadDailyData(currentDate);
}

async function handleExpenseSubmit(e) {
  e.preventDefault();
  const formData = new FormData(e.target);
  const expense = {};

  for (const [key, value] of formData.entries()) {
    if (value && parseFloat(value) > 0) {
      expense[key] = parseFloat(value);
    }
  }

  const customRows = document.querySelectorAll('#custom-expense .custom-platform-row');
  customRows.forEach(row => {
    const name = row.querySelector('.custom-platform-name').value.trim();
    const amount = row.querySelector('.custom-platform-amount').value;
    if (name && amount && parseFloat(amount) > 0) {
      expense[name] = parseFloat(amount);
    }
  });

  if (Object.keys(expense).length === 0) {
    alert('请至少输入一项支出');
    return;
  }

  await fetch('/api/accounting/expense', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({date: currentDate, expense})
  });

  closeExpenseModal();
  e.target.reset();
  loadDailyData(currentDate);
}

async function loadDailyData(date) {
  try {
    const resp = await fetch(`/api/accounting/daily?date=${date}`);
    const data = await resp.json();

    // 汇总统计
    const summaryEl = document.getElementById('daily-summary');
    const totalIncome = data.total_income || 0;
    const totalExpense = data.total_expense || 0;
    const netProfit = totalIncome - totalExpense;

    if (totalIncome > 0 || totalExpense > 0) {
      summaryEl.innerHTML = `
        <div class="stat-row">
          <div class="stat-card">
            <div class="stat-value" style="color:var(--good)">¥${totalIncome.toFixed(0)}</div>
            <div class="stat-label">总收入</div>
          </div>
          <div class="stat-card">
            <div class="stat-value" style="color:var(--warn)">¥${totalExpense.toFixed(0)}</div>
            <div class="stat-label">总支出</div>
          </div>
          <div class="stat-card">
            <div class="stat-value" style="color:${netProfit >= 0 ? 'var(--good)' : 'var(--danger)'}">¥${netProfit.toFixed(0)}</div>
            <div class="stat-label">净利润</div>
          </div>
        </div>
      `;
    } else {
      summaryEl.innerHTML = '';
    }

    // 收入明细
    const incomeDisplay = document.getElementById('income-display');
    if (data.income && Object.keys(data.income).length > 0) {
      const items = Object.entries(data.income)
        .map(([platform, amount]) =>
          `<div style="display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid var(--border)">
            <span>${platform}</span>
            <strong style="color:var(--good)">¥${amount.toFixed(2)}</strong>
          </div>`
        )
        .join('');
      incomeDisplay.innerHTML = items;
    } else {
      incomeDisplay.innerHTML = '<p style="color:var(--muted);text-align:center;padding:20px">暂无收入记录</p>';
    }

    // 支出明细
    const expenseDisplay = document.getElementById('expense-display');
    if (data.expense && Object.keys(data.expense).length > 0) {
      const items = Object.entries(data.expense)
        .map(([platform, amount]) =>
          `<div style="display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid var(--border)">
            <span>${platform}</span>
            <strong style="color:var(--warn)">¥${amount.toFixed(2)}</strong>
          </div>`
        )
        .join('');
      expenseDisplay.innerHTML = items;
    } else {
      expenseDisplay.innerHTML = '<p style="color:var(--muted);text-align:center;padding:20px">暂无支出记录</p>';
    }
  } catch (e) {
    document.getElementById('income-display').innerHTML = '<p style="color:var(--danger)">加载失败</p>';
    document.getElementById('expense-display').innerHTML = '<p style="color:var(--danger)">加载失败</p>';
    document.getElementById('daily-summary').innerHTML = '';
  }
}

function onDateChange() {
  const dateInput = document.getElementById('accounting-date');
  currentDate = dateInput.value;
  loadDailyData(currentDate);
}

function onMonthChange() {
  currentMonth = document.getElementById('accounting-month').value;
  loadMonthlyData(currentMonth);
}

async function loadMonthlyData(yearMonth) {
  try {
    const [data, costs, payroll] = await Promise.all([
      fetch(`/api/accounting/monthly?year_month=${yearMonth}`).then(r => r.json()),
      fetch(`/api/accounting/fixed-costs?month=${yearMonth}`).then(r => r.json()),
      fetch(`/api/payroll?year_month=${yearMonth}`).then(r => r.json()),
    ]);

    const totalWages = payroll.reduce((s, r) => s + (r.total || 0), 0);
    const rent = costs.rent || 0;
    const utilities = costs.utilities || 0;
    const otherFixed = costs.other || 0;
    const totalFixed = rent + utilities + otherFixed + totalWages;
    const netProfit = data.total_income - data.total_expense - totalFixed;
    const profitRate = data.total_income > 0 ? (netProfit / data.total_income * 100).toFixed(1) : 0;
    const profitColor = netProfit >= 0 ? 'var(--good)' : 'var(--danger)';

    const incomeRows = Object.entries(data.income || {})
      .map(([k, v]) => `<div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid var(--border)"><span>${k}</span><strong style="color:var(--good)">¥${v.toFixed(2)}</strong></div>`)
      .join('') || '<p style="color:var(--muted);padding:8px 0">暂无数据</p>';

    const expenseRows = Object.entries(data.expense || {})
      .map(([k, v]) => `<div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid var(--border)"><span>${k}</span><strong style="color:var(--warn)">¥${v.toFixed(2)}</strong></div>`)
      .join('') || '<p style="color:var(--muted);padding:8px 0">暂无数据</p>';

    document.getElementById('monthly-report').innerHTML = `
      <div class="stat-row">
        <div class="stat-card">
          <div class="stat-value" style="color:var(--good)">¥${data.total_income.toFixed(0)}</div>
          <div class="stat-label">月收入</div>
        </div>
        <div class="stat-card">
          <div class="stat-value" style="color:var(--warn)">¥${(data.total_expense + totalFixed).toFixed(0)}</div>
          <div class="stat-label">月支出</div>
        </div>
        <div class="stat-card">
          <div class="stat-value" style="color:${profitColor}">¥${netProfit.toFixed(0)}</div>
          <div class="stat-label">净利润</div>
        </div>
      </div>

      <div style="text-align:center;padding:12px;background:var(--primary-light);border-radius:8px;margin-bottom:12px">
        <div style="font-size:12px;color:var(--muted)">利润率</div>
        <div style="font-size:28px;font-weight:700;color:${profitColor}">${profitRate}%</div>
        <div style="font-size:12px;color:var(--muted);margin-top:4px">共 ${data.days_with_data} 天有记录</div>
      </div>

      <div class="card">
        <h3>🏠 固定成本</h3>
        <div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid var(--border)">
          <span>员工工资</span><strong style="color:var(--warn)">¥${totalWages.toFixed(0)}</strong>
        </div>
        <div style="display:flex;align-items:center;justify-content:space-between;padding:6px 0;border-bottom:1px solid var(--border)">
          <span>房租</span>
          <input type="number" id="input-rent" value="${rent}" step="1" placeholder="0"
            style="width:100px;padding:4px 8px;border:1px solid var(--border);border-radius:4px;text-align:right;font-size:14px">
        </div>
        <div style="display:flex;align-items:center;justify-content:space-between;padding:6px 0;border-bottom:1px solid var(--border)">
          <span>水电</span>
          <input type="number" id="input-utilities" value="${utilities}" step="1" placeholder="0"
            style="width:100px;padding:4px 8px;border:1px solid var(--border);border-radius:4px;text-align:right;font-size:14px">
        </div>
        <div style="display:flex;align-items:center;justify-content:space-between;padding:6px 0">
          <span>其他固定</span>
          <input type="number" id="input-other" value="${otherFixed}" step="1" placeholder="0"
            style="width:100px;padding:4px 8px;border:1px solid var(--border);border-radius:4px;text-align:right;font-size:14px">
        </div>
        <button class="btn" onclick="saveFixedCosts('${yearMonth}')" style="width:100%;margin-top:12px">保存固定成本</button>
      </div>

      <div class="card"><h3>💰 收入来源</h3>${incomeRows}</div>
      <div class="card"><h3>💸 采购支出</h3>${expenseRows}</div>
    `;
  } catch (e) {
    document.getElementById('monthly-report').innerHTML = '<p style="color:var(--danger)">加载失败</p>';
  }
}

async function saveFixedCosts(month) {
  const rent = parseFloat(document.getElementById('input-rent').value) || 0;
  const utilities = parseFloat(document.getElementById('input-utilities').value) || 0;
  const other = parseFloat(document.getElementById('input-other').value) || 0;
  await fetch('/api/accounting/fixed-costs', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({month, rent, utilities, other}),
  });
  loadMonthlyData(month);
}

function showIncomeModal() {
  document.getElementById('income-modal').style.display = 'flex';
}

function closeIncomeModal() {
  document.getElementById('income-modal').style.display = 'none';
  document.getElementById('custom-income').innerHTML = '';
}

function showExpenseModal() {
  document.getElementById('expense-modal').style.display = 'flex';
}

function closeExpenseModal() {
  document.getElementById('expense-modal').style.display = 'none';
  document.getElementById('custom-expense').innerHTML = '';
}

function closeModalOnBackdrop(event, modalId) {
  if (event.target.id === modalId) {
    if (modalId === 'income-modal') closeIncomeModal();
    if (modalId === 'expense-modal') closeExpenseModal();
  }
}

function addCustomIncome() {
  const container = document.getElementById('custom-income');
  const div = document.createElement('div');
  div.className = 'custom-platform-row';
  div.innerHTML = `
    <input type="text" placeholder="收入来源" class="custom-platform-name">
    <input type="number" step="0.01" placeholder="0.00" class="custom-platform-amount">
    <button type="button" onclick="this.parentElement.remove()" class="btn-remove">×</button>
  `;
  container.appendChild(div);
}

function addCustomExpense() {
  const container = document.getElementById('custom-expense');
  const div = document.createElement('div');
  div.className = 'custom-platform-row';
  div.innerHTML = `
    <input type="text" placeholder="支出项目" class="custom-platform-name">
    <input type="number" step="0.01" placeholder="0.00" class="custom-platform-amount">
    <button type="button" onclick="this.parentElement.remove()" class="btn-remove">×</button>
  `;
  container.appendChild(div);
}
