// Schedule Dashboard Component
// Depends on: Chart.js, fetchJSON(), showToast(), loadTab(), currentTab

let schedData = null;   // current schedule data
let staffMap = {};      // id → staff object
let staffList = [];     // all staff
let _cellShifts = {};   // cellId → [staff_id, ...]
let _weekStart = null;  // currently displayed week (YYYY-MM-DD, Monday)
let _viewMode = 'week'; // 'week' | 'month'
let _monthYear = null;  // YYYY-MM for month view

async function renderSchedule(el, weekStart) {
  if (weekStart) _weekStart = weekStart;
  if (!_weekStart) _weekStart = getMonday(new Date());
  if (!_monthYear) _monthYear = _weekStart.slice(0, 7);

  if (_viewMode === 'month') {
    return renderMonthView(el);
  }
  return renderWeekView(el);
}

// ═══════════════════════════════════════════════
//  Week View
// ═══════════════════════════════════════════════

async function renderWeekView(el) {
  try {
    [schedData, staffList] = await Promise.all([
      fetchJSON(`${API}/schedule?week_start=${_weekStart}`),
      fetchJSON(`${API}/staff`)
    ]);
    staffMap = {};
    staffList.forEach(s => { staffMap[s.id] = s; });

    const today = getToday();
    const byKey = {};
    schedData.shifts.forEach(s => {
      const key = `${s.date}|${s.period}`;
      if (!byKey[key]) byKey[key] = [];
      byKey[key].push(s);
    });

    // View toggle + week navigation
    const prevWeek = _offsetWeek(_weekStart, -1);
    const nextWeek = _offsetWeek(_weekStart, 1);
    let html = `<div class="week-nav">
      <button class="btn btn-sm btn-outline" onclick="navigateWeek('${prevWeek}')">◀ 上一周</button>
      <span class="week-label">${_weekStart} 周</span>
      <button class="btn btn-sm btn-outline" onclick="navigateWeek('${nextWeek}')">下一周 ▶</button>
    </div>`;
    html += `<div class="view-toggle">
      <button class="btn btn-sm btn-outline active">周</button>
      <button class="btn btn-sm btn-outline" onclick="switchToMonth()">月</button>
    </div>`;

    // Calendar grid
    html += '<div class="card" style="overflow-x:auto">';
    html += '<div class="sched-grid">';
    html += '<div class="sched-header"></div>';
    for (let i = 0; i < 7; i++) {
      const d = new Date(_weekStart);
      d.setDate(d.getDate() + i);
      const dateStr = d.toISOString().slice(0, 10);
      const dayNames = ['日','一','二','三','四','五','六'];
      const isToday = dateStr === today;
      html += `<div class="sched-header" style="${isToday ? 'background:#388e3c;' : ''}">${dateStr.slice(5)}<br>周${dayNames[d.getDay()]}</div>`;
    }
    for (const period of ['早班', '晚班']) {
      html += `<div class="sched-label">${period}</div>`;
      for (let i = 0; i < 7; i++) {
        const d = new Date(_weekStart);
        d.setDate(d.getDate() + i);
        const dateStr = d.toISOString().slice(0, 10);
        const key = `${dateStr}|${period}`;
        const shifts = byKey[key] || [];
        const cellId = `cell-${dateStr}-${period}`;
        _cellShifts[cellId] = shifts.map(s => s.staff_id);
        if (shifts.length > 0) {
          const chips = shifts.map(s => {
            const staff = staffMap[s.staff_id];
            const name = staff ? staff.name : s.staff_id;
            const hours = s.hours || (staff ? staff.full_day_hours || 11 : 11);
            const hoursLabel = hours >= (staff ? staff.full_day_hours || 11 : 11) ? '全天' : `${hours}h`;
            return `<span class="staff-chip" title="${name} ${hoursLabel}"
              style="background:${staffColor(s.staff_id)};color:#fff;padding:2px 5px;border-radius:3px;margin:1px;display:inline-block;font-size:11px;white-space:nowrap"
              >${name} ${hoursLabel}</span>`;
          }).join('');
          html += `<div class="sched-cell" id="${cellId}" onclick="showEditPanel('${cellId}')">${chips}</div>`;
        } else {
          html += `<div class="sched-cell sched-empty" id="${cellId}" onclick="showEditPanel('${cellId}')">—</div>`;
        }
      }
    }
    html += '</div></div>';

    // Edit panel
    html += `<div class="card" id="edit-panel">
      <h3>修改排班</h3>
      <p id="edit-title" style="color:var(--muted);font-size:13px;margin-bottom:12px">点击上方格子选择要编辑的日期和时段</p>
      <div id="edit-rows"></div>
      <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:12px">
        <button class="btn btn-sm" onclick="saveEdit()">保存</button>
      </div>
    </div>`;

    // Monthly chart
    const yearMonth = _weekStart.slice(0, 7);
    html += '<div class="card"><h3>本月出勤统计</h3><div class="chart-wrap"><canvas id="shiftChart"></canvas></div></div>';

    el.innerHTML = html;
    renderMonthlyChart(yearMonth);

  } catch(e) {
    el.innerHTML = `<div class="card"><p>加载失败: ${e.message}</p><p>请先确认服务器已启动并运行种子数据。</p></div>`;
  }
}

// ═══════════════════════════════════════════════
//  Month View
// ═══════════════════════════════════════════════

async function renderMonthView(el) {
  try {
    const data = await fetchJSON(`${API}/schedule/month?year_month=${_monthYear}`);

    // Build lookup: date → {早班: [names], 晚班: [names]}
    const staffLookup = {};
    (data.staff || []).forEach(s => { staffLookup[s.id] = s.name; });

    const byDate = {};
    (data.shifts || []).forEach(s => {
      if (!byDate[s.date]) byDate[s.date] = { '早班': [], '晚班': [] };
      const name = staffLookup[s.staff_id] || s.staff_id;
      byDate[s.date][s.period].push(name);
    });

    // Month navigation
    const [y, m] = _monthYear.split('-').map(Number);
    const prevMonth = m === 1 ? `${y-1}-12` : `${y}-${String(m-1).padStart(2,'0')}`;
    const nextMonth = m === 12 ? `${y+1}-01` : `${y}-${String(m+1).padStart(2,'0')}`;

    let html = `<div class="week-nav">
      <button class="btn btn-sm btn-outline" onclick="navigateMonth('${prevMonth}')">◀ 上月</button>
      <span class="week-label">${y}年${m}月</span>
      <button class="btn btn-sm btn-outline" onclick="navigateMonth('${nextMonth}')">下月 ▶</button>
    </div>`;
    html += `<div class="view-toggle">
      <button class="btn btn-sm btn-outline" onclick="switchToWeek()">周</button>
      <button class="btn btn-sm btn-outline active">月</button>
    </div>`;

    // Month calendar grid
    const firstDay = new Date(y, m-1, 1);
    const lastDay = new Date(y, m, 0);
    const daysInMonth = lastDay.getDate();
    // Day of week: 0=Sun, 1=Mon, ... 6=Sat → we want Mon=0
    const startDow = firstDay.getDay() === 0 ? 6 : firstDay.getDay() - 1;
    const today = getToday();

    html += '<div class="card" style="overflow-x:auto">';
    html += '<div class="month-grid">';
    // Header
    for (const d of ['一','二','三','四','五','六','日']) {
      html += `<div class="month-header">${d}</div>`;
    }
    // Cells
    let cellIdx = 0;
    const totalCells = startDow + daysInMonth;
    const rows = Math.ceil(totalCells / 7);
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < 7; c++) {
        const dayNum = cellIdx - startDow + 1;
        if (dayNum < 1 || dayNum > daysInMonth) {
          html += '<div class="month-cell month-empty"></div>';
        } else {
          const dateStr = `${y}-${String(m).padStart(2,'0')}-${String(dayNum).padStart(2,'0')}`;
          const shifts = byDate[dateStr] || { '早班': [], '晚班': [] };
          const morningCount = shifts['早班'].length;
          const eveningCount = shifts['晚班'].length;
          const isToday = dateStr === today;
          const dayOfWeek = new Date(y, m-1, dayNum).getDay();
          const isSunday = dayOfWeek === 0;

          let cellClass = 'month-cell';
          if (isToday) cellClass += ' month-today';
          if (isSunday) cellClass += ' month-sunday';

          html += `<div class="${cellClass}" onclick="goToWeek('${dateStr}')">
            <div class="month-daynum">${dayNum}</div>
            <div class="month-period">早 ${morningCount}人</div>
            <div class="month-period">晚 ${eveningCount}人</div>
          </div>`;
        }
        cellIdx++;
      }
    }
    html += '</div></div>';

    // Monthly summary table
    const summary = data.summary || [];
    if (summary.length > 0) {
      let totalMorning = 0, totalEvening = 0, totalPay = 0;
      html += '<div class="card"><h3>本月汇总</h3>';
      html += '<div style="overflow-x:auto"><table><thead><tr>';
      html += '<th>员工</th><th>早班</th><th>晚班</th><th>预计工资</th>';
      html += '</tr></thead><tbody>';
      summary.forEach(s => {
        totalMorning += s.morning_shifts;
        totalEvening += s.evening_shifts;
        totalPay += s.estimated_pay;
        html += `<tr>
          <td>${s.staff_name}</td>
          <td>${s.morning_shifts}</td>
          <td>${s.evening_shifts}</td>
          <td>¥${s.estimated_pay}</td>
        </tr>`;
      });
      html += `<tr style="font-weight:700;border-top:2px solid var(--primary)">
        <td>合计</td><td>${totalMorning}</td><td>${totalEvening}</td><td>¥${totalPay}</td>
      </tr>`;
      html += '</tbody></table></div></div>';
    }

    el.innerHTML = html;

  } catch(e) {
    el.innerHTML = `<div class="card"><p>加载失败: ${e.message}</p></div>`;
  }
}

function switchToMonth() {
  _viewMode = 'month';
  _monthYear = _weekStart.slice(0, 7);
  loadTab('schedule');
}

function switchToWeek() {
  _viewMode = 'week';
  // Derive week start from current month view
  if (_monthYear) {
    const now = new Date();
    const curYm = `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}`;
    if (_monthYear === curYm) {
      _weekStart = getMonday(new Date());
    } else {
      const [y, m] = _monthYear.split('-').map(Number);
      _weekStart = getMonday(new Date(y, m-1, 1));
    }
  }
  loadTab('schedule');
}

function navigateMonth(yearMonth) {
  _monthYear = yearMonth;
  _viewMode = 'month';
  // Also set _weekStart to first Monday of month for consistency
  const [y, m] = yearMonth.split('-').map(Number);
  _weekStart = getMonday(new Date(y, m-1, 1));
  _cellShifts = {};
  loadTab('schedule');
}

function goToWeek(dateStr) {
  const d = new Date(dateStr);
  _weekStart = getMonday(d);
  _monthYear = dateStr.slice(0, 7);
  _viewMode = 'week';
  _cellShifts = {};
  loadTab('schedule');
}

// ═══════════════════════════════════════════════
//  Shared helpers
// ═══════════════════════════════════════════════

function navigateWeek(weekStart) {
  _viewMode = 'week';
  _cellShifts = {};
  loadTab('schedule', weekStart);
}

function _offsetWeek(weekStart, delta) {
  const d = new Date(weekStart);
  d.setDate(d.getDate() + delta * 7);
  return d.toISOString().slice(0, 10);
}

function staffColor(id) {
  const colors = ['#1976d2','#388e3c','#e64a19','#7b1fa2','#c2185b','#00796b','#f57c00','#795548','#607d8b'];
  const idx = (id || '').charCodeAt(0) || 0;
  return colors[idx % colors.length];
}

async function renderMonthlyChart(yearMonth) {
  const canvas = document.getElementById('shiftChart');
  if (!canvas) return;
  if (canvas._chartInstance) canvas._chartInstance.destroy();

  try {
    const payroll = await fetchJSON(`${API}/payroll?year_month=${yearMonth}`);
    const labels = payroll.map(p => p.staff_name);
    const morning = payroll.map(p => p.morning_shifts);
    const evening = payroll.map(p => p.evening_shifts);

    canvas._chartInstance = new Chart(canvas, {
      type: 'bar',
      data: {
        labels,
        datasets: [
          { label: '早班', data: morning, backgroundColor: '#ff6f00' },
          { label: '晚班', data: evening, backgroundColor: '#ffab40' },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { position: 'bottom', labels: { font: { size: 11 } } } },
        scales: {
          x: { stacked: true, ticks: { font: { size: 11 } } },
          y: { stacked: true, ticks: { stepSize: 2, font: { size: 11 } } },
        },
      },
    });
  } catch(e) {
    canvas._chartInstance = new Chart(canvas, {
      type: 'bar',
      data: { labels: [], datasets: [] },
      options: { responsive: true, maintainAspectRatio: false },
    });
  }
}

// ═══════════════════════════════════════════════
//  Edit panel
// ═══════════════════════════════════════════════

let _editingCell = null;

function showEditPanel(cellId) {
  _editingCell = cellId;
  const rest = cellId.substring(5);
  const dashIdx = rest.lastIndexOf('-');
  const date = rest.substring(0, dashIdx);
  const period = rest.substring(dashIdx + 1);
  const existingIds = new Set(_cellShifts[cellId] || []);

  document.getElementById('edit-title').textContent = `${date} ${dayName(date)} ${period}`;

  let rowsHtml = '';
  staffList.forEach(st => {
    const checked = existingIds.has(st.id) ? 'checked' : '';
    const defaultHours = st.full_day_hours || 11;
    rowsHtml += `<div class="edit-row">
      <label class="cb-label" style="flex:1">
        <input type="checkbox" class="edit-check" data-staff="${st.id}" ${checked}>
        ${st.name}
      </label>
      <input type="number" class="edit-hours" data-staff="${st.id}" value="${defaultHours}"
        min="0" max="24" step="0.5"
        style="width:50px;padding:4px;border:1px solid var(--border);border-radius:4px;text-align:center;font-size:13px">
      <span style="font-size:11px;color:var(--muted);margin-left:2px">h</span>
    </div>`;
  });
  document.getElementById('edit-rows').innerHTML = rowsHtml;
  document.getElementById('edit-panel').scrollIntoView({ behavior: 'smooth' });
}

async function saveEdit() {
  if (!_editingCell) return;
  const rest = _editingCell.substring(5);
  const dashIdx = rest.lastIndexOf('-');
  const date = rest.substring(0, dashIdx);
  const period = rest.substring(dashIdx + 1);

  const checks = document.querySelectorAll('.edit-check:checked');
  const staffShifts = Array.from(checks).map(cb => {
    const hoursInput = document.querySelector(`.edit-hours[data-staff="${cb.dataset.staff}"]`);
    const hours = hoursInput ? parseFloat(hoursInput.value) || 11 : 11;
    return { staff_id: cb.dataset.staff, hours };
  });

  try {
    const res = await fetch(`${API}/schedule/cell`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ date, period, staff_shifts: staffShifts }),
    });
    if (!res.ok) { const e = await res.json(); throw new Error(e.detail || '请求失败'); }
    _cellShifts = {};
    showToast('排班已更新');
    _editingCell = null;
    loadTab(currentTab, _weekStart);
  } catch (e) {
    showToast('保存失败: ' + e.message);
  }
}
