// Schedule Dashboard Component
// Depends on: Chart.js, fetchJSON(), showToast(), loadTab(), currentTab

let schedData = null;
let staffMap = {};
let staffList = [];
let _weekStart = null;
let _viewMode = 'week';
let _monthYear = null;
let _editingDate = null;

async function renderSchedule(el, weekStart) {
  if (weekStart) _weekStart = weekStart;
  if (!_weekStart) _weekStart = getMonday(new Date());
  if (!_monthYear) _monthYear = _weekStart.slice(0, 7);
  if (_viewMode === 'month') return renderMonthView(el);
  return renderWeekView(el);
}

// ═══════════════════════════════════════════════
//  Week View — Staff × Days grid
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
    const byStaff = {};
    schedData.shifts.forEach(s => {
      if (!byStaff[s.staff_id]) byStaff[s.staff_id] = {};
      const hours = s.hours || (staffMap[s.staff_id] ? staffMap[s.staff_id].full_day_hours || 11 : 11);
      byStaff[s.staff_id][s.date] = (byStaff[s.staff_id][s.date] || 0) + hours;
    });

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
      <button class="btn btn-sm" style="background:var(--danger);color:#fff;margin-left:8px" onclick="clearWeekSchedule()">清空本周</button>
    </div>`;

    // Staff × Days grid
    html += '<div class="card" style="overflow-x:auto">';
    html += '<div class="sched-grid">';

    // Header row
    html += '<div class="sched-header"></div>';
    for (let i = 0; i < 7; i++) {
      const d = new Date(_weekStart);
      d.setDate(d.getDate() + i);
      const dateStr = d.toISOString().slice(0, 10);
      const dayNames = ['日','一','二','三','四','五','六'];
      const isToday = dateStr === today;
      html += `<div class="sched-header" style="${isToday ? 'background:#388e3c;' : ''};cursor:pointer" onclick="openDayEditModal('${dateStr}')">
        ${dateStr.slice(5)}<br>周${dayNames[d.getDay()]}</div>`;
    }

    // One row per staff
    staffList.forEach(st => {
      html += `<div class="sched-staff-label" title="${st.name}">${st.name}</div>`;
      for (let i = 0; i < 7; i++) {
        const d = new Date(_weekStart);
        d.setDate(d.getDate() + i);
        const dateStr = d.toISOString().slice(0, 10);
        const totalHours = (byStaff[st.id] && byStaff[st.id][dateStr]) || 0;
        const fullDay = st.full_day_hours || 11;

        let display, cls;
        if (totalHours <= 0) { display = '—'; cls = 'sched-rest'; }
        else if (Math.abs(totalHours - fullDay) < 0.01) { display = '全天'; cls = 'sched-full'; }
        else { display = totalHours + 'h'; cls = 'sched-partial'; }

        html += `<div class="sched-cell ${cls}" onclick="openDayEditModal('${dateStr}')">${display}</div>`;
      }
    });
    html += '</div></div>';

    // Day edit modal
    html += `
      <div id="sched-day-modal" class="modal" style="display:none" onclick="closeModalOnBackdropSched(event)">
        <div class="modal-content-enhanced" onclick="event.stopPropagation()">
          <div class="modal-header">
            <h3 id="sched-modal-title">编辑排班</h3>
            <button class="modal-close" onclick="closeDayEditSched()">×</button>
          </div>
          <form id="sched-day-form">
            <div id="sched-modal-rows" style="max-height:50vh;overflow-y:auto"></div>
            <div class="modal-footer">
              <button type="button" class="btn btn-outline" onclick="closeDayEditSched()">取消</button>
              <button type="submit" class="btn">保存</button>
            </div>
          </form>
        </div>
      </div>`;

    // Chart
    const yearMonth = _weekStart.slice(0, 7);
    html += '<div class="card"><h3>本月工时统计</h3><div class="chart-wrap"><canvas id="shiftChart"></canvas></div></div>';

    el.innerHTML = html;
    renderMonthlyChart(yearMonth);
    document.getElementById('sched-day-form').addEventListener('submit', saveDayEditSched);

  } catch(e) {
    el.innerHTML = `<div class="card"><p>加载失败: ${e.message}</p></div>`;
  }
}

// ═══════════════════════════════════════════════
//  Day Edit Modal
// ═══════════════════════════════════════════════

function dayName(dateStr) {
  const names = ['日','一','二','三','四','五','六'];
  return '周' + names[new Date(dateStr).getDay()];
}

function openDayEditModal(dateStr) {
  _editingDate = dateStr;
  document.getElementById('sched-modal-title').textContent = `${dateStr} ${dayName(dateStr)} 排班`;

  // Get current hours for each staff on this date
  const currentHours = {};
  schedData.shifts.forEach(s => {
    if (s.date === dateStr) {
      const h = s.hours || (staffMap[s.staff_id] ? staffMap[s.staff_id].full_day_hours || 11 : 11);
      currentHours[s.staff_id] = (currentHours[s.staff_id] || 0) + h;
    }
  });

  const container = document.getElementById('sched-modal-rows');
  container.innerHTML = '';
  staffList.forEach(st => {
    const val = currentHours[st.id] || 0;
    const fd = st.full_day_hours || 11;
    const row = document.createElement('div');
    row.className = 'sched-modal-row';
    row.innerHTML = `
      <span class="sched-modal-name">${st.name}</span>
      <div class="sched-modal-quick">
        <button type="button" class="quick-btn" onclick="setHours(this, ${fd})">全天</button>
        <button type="button" class="quick-btn" onclick="setHours(this, 6)">6h</button>
        <button type="button" class="quick-btn" onclick="setHours(this, 5)">5h</button>
        <button type="button" class="quick-btn" onclick="setHours(this, 4)">4h</button>
        <button type="button" class="quick-btn" onclick="setHours(this, 0)">休</button>
      </div>
      <input type="number" class="sched-modal-input" data-staff="${st.id}"
        value="${val}" min="0" max="24" step="0.5">
      <span style="font-size:12px;color:var(--muted);width:16px">h</span>
    `;
    container.appendChild(row);
  });
  document.getElementById('sched-day-modal').style.display = 'flex';
}

function setHours(btn, val) {
  const input = btn.closest('.sched-modal-row').querySelector('.sched-modal-input');
  input.value = val;
}

function closeDayEditSched() {
  document.getElementById('sched-day-modal').style.display = 'none';
  _editingDate = null;
}

function closeModalOnBackdropSched(event) {
  if (event.target.id === 'sched-day-modal') closeDayEditSched();
}

async function saveDayEditSched(e) {
  e.preventDefault();
  if (!_editingDate) return;

  const inputs = document.querySelectorAll('.sched-modal-input');
  const staffShifts = [];
  inputs.forEach(inp => {
    const hours = parseFloat(inp.value) || 0;
    if (hours > 0) staffShifts.push({ staff_id: inp.dataset.staff, hours });
  });

  try {
    const res = await fetch(`${API}/schedule/day`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ date: _editingDate, staff_shifts: staffShifts }),
    });
    if (!res.ok) throw new Error('保存失败');
    showToast('排班已更新');
    closeDayEditSched();
    loadTab(currentTab, _weekStart);
  } catch(e) {
    showToast('保存失败: ' + e.message);
  }
}

// ═══════════════════════════════════════════════
//  Month View
// ═══════════════════════════════════════════════

async function renderMonthView(el) {
  try {
    const data = await fetchJSON(`${API}/schedule/month?year_month=${_monthYear}`);

    // Build per-date staff set
    const staffLookup = {};
    (data.staff || []).forEach(s => { staffLookup[s.id] = s.name; });

    const byDate = {};
    (data.shifts || []).forEach(s => {
      if (!byDate[s.date]) byDate[s.date] = new Set();
      byDate[s.date].add(s.staff_id);
    });

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
      <button class="btn btn-sm" style="background:var(--danger);color:#fff;margin-left:8px" onclick="clearMonthSchedule()">清空本月</button>
    </div>`;

    html += '<div class="card" style="overflow-x:auto">';
    html += '<div class="month-grid">';
    for (const d of ['一','二','三','四','五','六','日']) {
      html += `<div class="month-header">${d}</div>`;
    }
    const firstDay = new Date(y, m-1, 1);
    const lastDay = new Date(y, m, 0);
    const daysInMonth = lastDay.getDate();
    const startDow = firstDay.getDay() === 0 ? 6 : firstDay.getDay() - 1;
    const today = getToday();

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
          const count = byDate[dateStr] ? byDate[dateStr].size : 0;
          const isToday = dateStr === today;
          const dayOfWeek = new Date(y, m-1, dayNum).getDay();

          let cellClass = 'month-cell';
          if (isToday) cellClass += ' month-today';
          if (dayOfWeek === 0) cellClass += ' month-sunday';

          html += `<div class="${cellClass}" onclick="goToWeek('${dateStr}')">
            <div class="month-daynum">${dayNum}</div>
            <div class="month-period">共 ${count} 人</div>
          </div>`;
        }
        cellIdx++;
      }
    }
    html += '</div></div>';

    // Summary table
    if (data.summary && data.summary.length > 0) {
      let totalDays = 0, totalHours = 0, totalPay = 0;
      html += '<div class="card"><h3>本月汇总</h3>';
      html += '<div style="overflow-x:auto"><table><thead><tr>';
      html += '<th>员工</th><th>出勤</th><th>总工时</th><th>预计工资</th>';
      html += '</tr></thead><tbody>';
      data.summary.forEach(s => {
        totalDays += s.days_worked;
        totalHours += s.total_hours;
        totalPay += s.estimated_pay;
        html += `<tr>
          <td>${s.staff_name}</td>
          <td>${s.days_worked}天</td>
          <td>${s.total_hours.toFixed(1)}h</td>
          <td>¥${s.estimated_pay}</td>
        </tr>`;
      });
      html += `<tr style="font-weight:700;border-top:2px solid var(--primary)">
        <td>合计</td><td>${totalDays}</td><td>${totalHours.toFixed(1)}h</td><td>¥${totalPay}</td>
      </tr>`;
      html += '</tbody></table></div></div>';
    }

    // Day edit modal (shared with week view)
    html += `
      <div id="sched-day-modal" class="modal" style="display:none" onclick="closeModalOnBackdropSched(event)">
        <div class="modal-content-enhanced" onclick="event.stopPropagation()">
          <div class="modal-header">
            <h3 id="sched-modal-title">编辑排班</h3>
            <button class="modal-close" onclick="closeDayEditSched()">×</button>
          </div>
          <form id="sched-day-form">
            <div id="sched-modal-rows" style="max-height:50vh;overflow-y:auto"></div>
            <div class="modal-footer">
              <button type="button" class="btn btn-outline" onclick="closeDayEditSched()">取消</button>
              <button type="submit" class="btn">保存</button>
            </div>
          </form>
        </div>
      </div>`;

    el.innerHTML = html;
  } catch(e) {
    el.innerHTML = `<div class="card"><p>加载失败: ${e.message}</p></div>`;
  }
}

// ═══════════════════════════════════════════════
//  View switching
// ═══════════════════════════════════════════════

function switchToMonth() { _viewMode = 'month'; _monthYear = _weekStart.slice(0, 7); loadTab('schedule'); }
function switchToWeek() {
  _viewMode = 'week';
  if (_monthYear) {
    const now = new Date();
    const curYm = `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}`;
    _weekStart = _monthYear === curYm ? getMonday(new Date()) : getMonday(new Date(parseInt(_monthYear), parseInt(_monthYear.split('-')[1])-1, 1));
  }
  loadTab('schedule');
}
function navigateMonth(yearMonth) { _monthYear = yearMonth; _viewMode = 'month'; _weekStart = getMonday(new Date(parseInt(yearMonth), parseInt(yearMonth.split('-')[1])-1, 1)); loadTab('schedule'); }
function goToWeek(dateStr) { _viewMode = 'week'; _weekStart = getMonday(new Date(dateStr)); _monthYear = dateStr.slice(0, 7); loadTab('schedule'); }
async function clearMonthSchedule() {
  if (!_monthYear) return;
  const modal = document.getElementById('sched-day-modal');
  document.getElementById('sched-modal-title').textContent = `清空 ${_monthYear} 整月排班？`;
  const container = document.getElementById('sched-modal-rows');
  container.innerHTML = `<p style="padding:20px;text-align:center;color:var(--muted)">此操作不可撤销，确定要清空本月所有人排班吗？</p>`;
  const form = document.getElementById('sched-day-form');
  form.onsubmit = async (e) => {
    e.preventDefault();
    try {
      await fetch(`${API}/schedule/clear-month?year_month=${_monthYear}`, { method: 'POST' });
      showToast('本月排班已清空');
      closeDayEditSched();
      form.onsubmit = saveDayEditSched;
      loadTab(currentTab);
    } catch(e) { showToast('清空失败'); }
  };
  modal.style.display = 'flex';
}

async function clearWeekSchedule() {
  if (!_weekStart) return;
  const modal = document.getElementById('sched-day-modal');
  document.getElementById('sched-modal-title').textContent = `清空 ${_weekStart} 整周排班？`;
  const container = document.getElementById('sched-modal-rows');
  container.innerHTML = `<p style="padding:20px;text-align:center;color:var(--muted)">此操作不可撤销，确定要清空本周所有人排班吗？</p>`;

  // Replace modal footer with confirm/cancel
  const form = document.getElementById('sched-day-form');
  form.onsubmit = async (e) => {
    e.preventDefault();
    try {
      await fetch(`${API}/schedule/clear-week?week_start=${_weekStart}`, { method: 'POST' });
      showToast('本周排班已清空');
      closeDayEditSched();
      form.onsubmit = saveDayEditSched;
      loadTab(currentTab, _weekStart);
    } catch(e) {
      showToast('清空失败');
    }
  };
  modal.style.display = 'flex';
}

function navigateWeek(weekStart) { _viewMode = 'week'; loadTab('schedule', weekStart); }
function _offsetWeek(weekStart, delta) { const d = new Date(weekStart); d.setDate(d.getDate() + delta * 7); return d.toISOString().slice(0, 10); }
function getMonday(d) { const dt = new Date(d); const day = dt.getDay(); const diff = dt.getDate() - day + (day === 0 ? -6 : 1); dt.setDate(diff); return dt.toISOString().slice(0, 10); }
function getToday() { return new Date().toISOString().slice(0, 10); }

// ═══════════════════════════════════════════════
//  Chart
// ═══════════════════════════════════════════════

async function renderMonthlyChart(yearMonth) {
  const canvas = document.getElementById('shiftChart');
  if (!canvas) return;
  if (canvas._chartInstance) canvas._chartInstance.destroy();

  try {
    const payroll = await fetchJSON(`${API}/payroll?year_month=${yearMonth}`);
    const labels = payroll.map(p => p.staff_name);
    const totalHours = payroll.map(p => p.total_hours || 0);

    canvas._chartInstance = new Chart(canvas, {
      type: 'bar',
      data: {
        labels,
        datasets: [{ label: '总工时', data: totalHours, backgroundColor: '#ff6f00' }],
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
    canvas._chartInstance = new Chart(canvas, {
      type: 'bar', data: { labels: [], datasets: [] },
      options: { responsive: true, maintainAspectRatio: false },
    });
  }
}
