// Schedule Dashboard Component
// Depends on: Chart.js, fetchJSON(), showToast(), loadTab(), currentTab

let schedData = null;   // current schedule data
let staffMap = {};      // id → staff object
let staffList = [];     // all staff

async function renderSchedule(el) {
  const weekStart = getMonday(new Date());
  try {
    [schedData, staffList] = await Promise.all([
      fetchJSON(`${API}/schedule?week_start=${weekStart}`),
      fetchJSON(`${API}/staff`)
    ]);
    staffMap = {};
    staffList.forEach(s => { staffMap[s.id] = s; });

    const today = getToday();
    const byKey = {};  // "2026-05-19|早班" → [{staff_id, role}, ...]
    schedData.shifts.forEach(s => {
      const key = `${s.date}|${s.period}`;
      if (!byKey[key]) byKey[key] = [];
      byKey[key].push(s);
    });

    let html = `<h2>本周排班 (${weekStart})</h2>`;

    // Calendar grid
    html += '<div class="card" style="overflow-x:auto">';
    html += '<div class="sched-grid">';
    html += '<div class="sched-header"></div>';
    for (let i = 0; i < 7; i++) {
      const d = new Date(weekStart);
      d.setDate(d.getDate() + i);
      const dateStr = d.toISOString().slice(0, 10);
      const dayNames = ['日','一','二','三','四','五','六'];
      const isToday = dateStr === today;
      html += `<div class="sched-header" style="${isToday ? 'background:#388e3c;' : ''}">${dateStr.slice(5)}<br>周${dayNames[d.getDay()]}</div>`;
    }
    for (const period of ['早班', '晚班']) {
      html += `<div class="sched-label">${period}</div>`;
      for (let i = 0; i < 7; i++) {
        const d = new Date(weekStart);
        d.setDate(d.getDate() + i);
        const dateStr = d.toISOString().slice(0, 10);
        const key = `${dateStr}|${period}`;
        const shifts = byKey[key] || [];
        const cellId = `cell-${dateStr}-${period}`;
        if (shifts.length > 0) {
          const names = shifts.map(s => {
            const staff = staffMap[s.staff_id];
            return staff ? `<span style="background:${staffColor(staff.id)};color:#fff;padding:1px 4px;border-radius:3px;margin:1px;display:inline-block;font-size:10px">${staff.name}(${s.role})</span>` : s.staff_id;
          }).join('<br>');
          html += `<div class="sched-cell" id="${cellId}" onclick="openShiftEdit('${dateStr}','${period}',${JSON.stringify(shifts.map(s => ({staff_id:s.staff_id,role:s.role})))})">${names}</div>`;
        } else {
          html += `<div class="sched-cell sched-empty" id="${cellId}">—</div>`;
        }
      }
    }
    html += '</div></div>';

    // Weekly stats
    html += '<div class="card"><h3>本周统计</h3><div class="chart-wrap"><canvas id="shiftChart"></canvas></div></div>';

    // Attendance quick-mark
    html += '<div class="card"><h3>今日考勤 (快速标记)</h3>';
    html += '<div class="form-group"><label>日期</label><input id="att-date" type="date" value="' + today + '"></div>';
    html += '<div class="form-group"><label>缺勤</label>';
    staffList.forEach(s => {
      html += `<label class="cb-label"><input type="checkbox" value="${s.id}" class="att-absent" onchange="onAbsentChange()"> ${s.name}</label>`;
    });
    html += '</div>';
    html += '<div id="replacement-hints" style="font-size:12px;color:var(--primary);margin-bottom:8px"></div>';
    html += '<div class="form-group"><label>替班 (格式: 缺勤者→替班者，如 张三→李四)</label><input id="att-sub" placeholder="可选"></div>';
    html += '<div class="form-group"><label>加班</label>';
    staffList.forEach(s => {
      html += `<label class="cb-label"><input type="checkbox" value="${s.id}" class="att-overtime"> ${s.name}</label>`;
    });
    html += '</div>';
    html += '<button class="btn" onclick="handleSaveAttendance()">保存考勤</button>';
    html += '</div>';

    el.innerHTML = html;

    // Draw weekly shift distribution chart
    renderShiftChart(byKey, weekStart);

  } catch(e) {
    el.innerHTML = `<div class="card"><p>加载失败: ${e.message}</p><p>请先确认服务器已启动并运行种子数据。</p></div>`;
  }
}

function staffColor(id) {
  const colors = ['#1976d2','#388e3c','#e64a19','#7b1fa2','#c2185b','#00796b','#f57c00'];
  const idx = (id || '').charCodeAt(0) || 0;
  return colors[idx % colors.length];
}

function renderShiftChart(byKey, weekStart) {
  const canvas = document.getElementById('shiftChart');
  if (!canvas) return;
  if (canvas._chartInstance) canvas._chartInstance.destroy();

  const counts = {};
  staffList.forEach(s => { counts[s.name] = 0; });
  Object.values(byKey).forEach(shifts => {
    shifts.forEach(s => {
      const staff = staffMap[s.staff_id];
      if (staff) counts[staff.name] = (counts[staff.name] || 0) + 1;
    });
  });

  canvas._chartInstance = new Chart(canvas, {
    type: 'bar',
    data: {
      labels: Object.keys(counts),
      datasets: [{ label: '本周班次', data: Object.values(counts), backgroundColor: '#ff6f00' }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        y: { ticks: { stepSize: 1, font: { size: 11 } } },
        x: { ticks: { font: { size: 11 } } },
      },
    },
  });
}

function onAbsentChange() {
  const absentIds = [...document.querySelectorAll('.att-absent:checked')].map(cb => cb.value);
  const hintsDiv = document.getElementById('replacement-hints');
  if (!hintsDiv || absentIds.length === 0) {
    if (hintsDiv) hintsDiv.innerHTML = '';
    return;
  }
  // Find candidates for each absent staff
  let hintsHtml = '';
  absentIds.forEach(id => {
    const absentStaff = staffMap[id];
    if (!absentStaff) return;
    const candidates = staffList.filter(s => {
      if (s.id === id) return false;
      return absentStaff.roles.some(r => s.roles.includes(r));
    });
    if (candidates.length > 0) {
      hintsHtml += `<div style="margin:4px 0">${absentStaff.name}缺勤 → 推荐替班：${candidates.map(c => c.name).join(' / ')}</div>`;
    } else {
      hintsHtml += `<div style="margin:4px 0;color:var(--danger)">${absentStaff.name}缺勤 → 无合适替班人选</div>`;
    }
  });
  hintsDiv.innerHTML = hintsHtml;
}

async function handleSaveAttendance() {
  const date = document.getElementById('att-date').value;
  const absent = [...document.querySelectorAll('.att-absent:checked')].map(cb => cb.value);
  const overtime = [...document.querySelectorAll('.att-overtime:checked')].map(cb => cb.value);
  const subRaw = document.getElementById('att-sub').value.trim();

  const substitute = {};
  if (subRaw) {
    for (const pair of subRaw.split(/[,，\s]+/)) {
      const parts = pair.split(/[→→>]/);
      if (parts.length === 2) {
        const fromStaff = staffList.find(s => s.name === parts[0].trim());
        const toStaff = staffList.find(s => s.name === parts[1].trim());
        if (fromStaff && toStaff) substitute[fromStaff.id] = toStaff.id;
      }
    }
  }

  try {
    const res = await fetch(`${API}/attendance`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ date, absent, substitute, overtime }),
    });
    if (!res.ok) { const e = await res.json(); throw new Error(e.detail || '请求失败'); }
    showToast('考勤已保存');
  } catch (e) {
    showToast('保存失败: ' + e.message);
  }
}

async function openShiftEdit(date, period, shifts) {
  // Remove any existing modal
  const old = document.querySelector('.modal-overlay');
  if (old) old.remove();

  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay';
  overlay.innerHTML = `<div class="modal-box">
    <h3>编辑 ${date} ${period}</h3>
    <div id="edit-shifts-list"></div>
    <button class="btn btn-sm" id="add-shift-btn">➕ 添加员工</button>
    <div style="margin-top:12px;text-align:right">
      <button class="btn btn-sm btn-outline" onclick="document.querySelector('.modal-overlay').remove()">关闭</button>
    </div>
  </div>`;
  document.body.appendChild(overlay);

  const listDiv = overlay.querySelector('#edit-shifts-list');
  shifts.forEach((s, idx) => {
    const staff = staffMap[s.staff_id];
    listDiv.innerHTML += `<div style="margin:4px 0;display:flex;align-items:center;gap:8px">
      <span style="flex:1">${staff ? staff.name : s.staff_id} (${s.role})</span>
      <select class="edit-role-select" style="width:80px">
        <option value="后厨" ${s.role==='后厨'?'selected':''}>后厨</option>
        <option value="传菜" ${s.role==='传菜'?'selected':''}>传菜</option>
        <option value="收银" ${s.role==='收银'?'selected':''}>收银</option>
      </select>
      <select class="edit-staff-select" style="width:100px">
        ${staffList.map(st => `<option value="${st.id}" ${st.id===s.staff_id?'selected':''}>${st.name}</option>`).join('')}
      </select>
      <button class="btn btn-sm" style="background:var(--danger);font-size:11px;padding:2px 6px" onclick="this.closest('div').remove();">✕</button>
    </div>`;
  });

  overlay.querySelector('#add-shift-btn').onclick = () => {
    listDiv.innerHTML += `<div style="margin:4px 0;display:flex;align-items:center;gap:8px">
      <select class="edit-staff-select" style="width:100px">${staffList.map(s => `<option value="${s.id}">${s.name}</option>`).join('')}</select>
      <select class="edit-role-select" style="width:80px"><option>后厨</option><option>传菜</option><option>收银</option></select>
      <button class="btn btn-sm" style="background:var(--danger);font-size:11px;padding:2px 6px" onclick="this.closest('div').remove();">✕</button>
    </div>`;
  };

  // Save button
  const saveBtn = document.createElement('button');
  saveBtn.className = 'btn';
  saveBtn.textContent = '保存更改';
  saveBtn.style.marginRight = '8px';
  saveBtn.onclick = async () => {
    const rows = listDiv.querySelectorAll('div[style]');
    const newShifts = [];
    rows.forEach(row => {
      const staffSelect = row.querySelector('.edit-staff-select');
      const roleSelect = row.querySelector('.edit-role-select');
      if (staffSelect && roleSelect) {
        newShifts.push({ staff_id: staffSelect.value, role: roleSelect.value });
      }
    });

    try {
      // For each original position, update if staff changed
      for (let i = 0; i < Math.min(shifts.length, newShifts.length); i++) {
        if (shifts[i].staff_id !== newShifts[i].staff_id) {
          const res = await fetch(`${API}/schedule/edit`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              date, period,
              old_staff_id: shifts[i].staff_id,
              new_staff_id: newShifts[i].staff_id,
            }),
          });
          if (!res.ok) { const e = await res.json(); throw new Error(e.detail || '请求失败'); }
        }
      }
      showToast('排班已更新');
      document.querySelector('.modal-overlay').remove();
      loadTab(currentTab);
    } catch (e) {
      showToast('保存失败: ' + e.message);
    }
  };
  overlay.querySelector('.modal-box').insertBefore(saveBtn, overlay.querySelector('.modal-box').lastElementChild);
}
