// 员工管理模块（合并员工列表和工资单）

let staffSubTab = 'list'; // 'list' or 'payroll'

async function renderStaff(el) {
  el.innerHTML = `
    <h2>员工管理</h2>
    <div class="sub-tabs">
      <button class="sub-tab ${staffSubTab === 'list' ? 'active' : ''}" onclick="switchStaffTab('list')">员工列表</button>
      <button class="sub-tab ${staffSubTab === 'payroll' ? 'active' : ''}" onclick="switchStaffTab('payroll')">工资单</button>
    </div>
    <div id="staff-content"></div>
  `;

  if (staffSubTab === 'list') {
    await renderStaffList();
  } else {
    await renderStaffPayroll();
  }
}

function switchStaffTab(tab) {
  staffSubTab = tab;
  renderStaff(document.getElementById('content'));
}

async function renderStaffList() {
  const el = document.getElementById('staff-content');
  try {
    const data = await fetchJSON(`${API}/staff`);

    let html = `<button id="staff-toggle" class="btn btn-sm btn-outline" onclick="showForm('staff-form','staff-toggle')" style="margin-top:12px;margin-bottom:12px">➕ 新增员工</button>`;
    html += `<div id="staff-form" class="card" style="display:none">`;
    html += `<div class="form-group"><label>姓名</label><input id="staff-name" placeholder="姓名"></div>`;
    html += `<div class="form-group"><label>角色</label>`;
    html += `<label class="cb-label"><input type="checkbox" value="后厨" class="staff-role"> 后厨</label>`;
    html += `<label class="cb-label"><input type="checkbox" value="传菜" class="staff-role"> 传菜</label>`;
    html += `<label class="cb-label"><input type="checkbox" value="收银" class="staff-role"> 收银</label>`;
    html += `</div>`;
    html += `<div class="form-group"><label>早班工资</label><input id="staff-morning" type="number" value="80"></div>`;
    html += `<div class="form-group"><label>晚班工资</label><input id="staff-evening" type="number" value="60"></div>`;
    html += `<div class="form-group"><label>备注</label><input id="staff-note" placeholder="可选"></div>`;
    html += `<button class="btn btn-sm" onclick="handleCreateStaff()">保存</button> `;
    html += `<button class="btn btn-sm btn-outline" onclick="hideForm('staff-form','staff-toggle')">取消</button>`;
    html += `</div>`;

    data.forEach(s => {
      html += `<div class="card" id="staff-card-${s.id}">
        <div style="display:flex;justify-content:space-between;align-items:flex-start">
          <div>
            <h3>${s.name}</h3>
            <p>角色: ${s.roles.join(' / ')} | 时薪 ¥${s.hourly_wage || 15}/h | 全天 ${s.full_day_hours || 11}h${s.full_attendance_bonus ? ` | 全勤奖 ¥${s.full_attendance_bonus}` : ''}</p>
            ${s.note ? `<p style="font-size:12px;color:var(--muted)">${s.note}</p>` : ''}
          </div>
          <div style="display:flex;gap:4px">
            <button class="btn btn-sm btn-outline" onclick="showEditStaffModal('${s.id}')">编辑</button>
            <button class="btn btn-sm" style="background:var(--danger);font-size:11px;padding:2px 8px" onclick="deleteStaff('${s.id}')">删除</button>
          </div>
        </div>
      </div>`;
    });

    // Edit modal
    html += `
      <div id="edit-staff-modal" class="modal" style="display:none" onclick="closeModalOnBackdropStaff(event)">
        <div class="modal-content-enhanced" onclick="event.stopPropagation()">
          <div class="modal-header">
            <h3>编辑员工</h3>
            <button class="modal-close" onclick="closeEditStaffModal()">×</button>
          </div>
          <form id="edit-staff-form">
            <div class="form-grid">
              <div class="form-group">
                <label>姓名</label>
                <input type="text" id="edit-staff-name" placeholder="姓名">
              </div>
              <div class="form-group">
                <label>时薪（元/小时）</label>
                <input type="number" id="edit-staff-hourly" step="0.5" placeholder="15">
              </div>
              <div class="form-group">
                <label>全天工时（小时）</label>
                <input type="number" id="edit-staff-fullday" step="0.5" placeholder="11">
              </div>
              <div class="form-group">
                <label>备注</label>
                <input type="text" id="edit-staff-note" placeholder="可选">
              </div>
            </div>
            <div class="modal-footer">
              <button type="button" class="btn btn-outline" onclick="closeEditStaffModal()">取消</button>
              <button type="submit" class="btn">保存</button>
            </div>
          </form>
        </div>
      </div>`;

    el.innerHTML = html;

    // Bind submit
    document.getElementById('edit-staff-form').addEventListener('submit', handleEditStaffSubmit);
  } catch(e) {
    el.innerHTML = `<div class="card"><p>加载失败: ${e.message}</p></div>`;
  }
}

async function renderStaffPayroll() {
  const el = document.getElementById('staff-content');
  const ym = new Date().toISOString().slice(0, 7);
  try {
    const [data, staffList, fixedCosts] = await Promise.all([
      fetchJSON(`${API}/payroll?year_month=${ym}`),
      fetchJSON(`${API}/staff`),
      fetchJSON(`${API}/accounting/fixed-costs?month=${ym}`).catch(() => ({full_attendance_bonus: 0})),
    ]);
    const faBonus = fixedCosts.full_attendance_bonus || 0;

    if (data.length === 0) {
      el.innerHTML = '<div class="card"><p>本月暂无排班数据，请先生成排班后再查询。</p></div>';
      return;
    }

    const totalPayroll = data.reduce((s, p) => s + p.total, 0);
    const avgPay = totalPayroll / data.length;
    const maxPay = Math.max(...data.map(p => p.total));
    const minPay = Math.min(...data.map(p => p.total));

    let html = `<h3 style="margin-top:12px">${ym} 工资单</h3>`;

    // Full attendance info
    const faCount = data.filter(p => p.full_attendance).length;
    if (faCount > 0) {
      html += `<div class="card" style="display:flex;align-items:center;gap:8px;padding:12px;margin-bottom:12px;font-size:14px">
        <span>🏆 本月全勤 <strong>${faCount}</strong> 人</span>
      </div>`;
    }

    html += '<div class="stat-row">';
    html += `<div class="stat-card"><div class="stat-value">¥${totalPayroll.toFixed(0)}</div><div class="stat-label">工资总额</div></div>`;
    html += `<div class="stat-card"><div class="stat-value">¥${avgPay.toFixed(0)}</div><div class="stat-label">人均工资</div></div>`;
    html += '</div>';
    html += '<div class="stat-row">';
    html += `<div class="stat-card"><div class="stat-value">¥${maxPay.toFixed(0)}</div><div class="stat-label">最高</div></div>`;
    html += `<div class="stat-card"><div class="stat-value">¥${minPay.toFixed(0)}</div><div class="stat-label">最低</div></div>`;
    html += '</div>';

    html += '<div class="card"><h3>明细</h3><table><thead><tr>';
    html += '<th>姓名</th><th>出勤</th><th>工时</th><th>底薪</th><th>全勤奖</th><th>提成</th><th>合计</th>';
    html += '</tr></thead><tbody>';
    data.forEach(p => {
      const faBadge = p.full_attendance ? '🏆' : '';
      html += `<tr>`;
      html += `<td><strong>${p.staff_name} ${faBadge}</strong></td>`;
      html += `<td>${p.working_days || 0}天</td>`;
      html += `<td>${(p.total_hours || 0).toFixed(1)}h</td>`;
      html += `<td><input type="number" class="base-input" data-staff="${p.staff_id || ''}" data-ym="${ym}"
        value="${(p.base_pay || 0).toFixed(0)}" step="50" min="0"
        style="width:65px;padding:4px 6px;border:1px solid var(--border);border-radius:4px;text-align:right;font-size:13px"
        onchange="saveBasePay(this)"></td>`;
      html += `<td>
        <input type="number" class="fa-input" data-staff="${p.staff_id || ''}" data-ym="${ym}"
          value="${(p.full_attendance_bonus || 0).toFixed(0)}" step="50" min="0"
          style="width:55px;padding:4px 6px;border:1px solid var(--border);border-radius:4px;text-align:right;font-size:13px"
          onchange="saveFABonus(this)">
      </td>`;
      html += `<td>
        <input type="number" class="bonus-input" data-staff="${p.staff_id || ''}" data-ym="${ym}"
          value="${(p.commission || 0).toFixed(0)}" step="50" min="0"
          style="width:55px;padding:4px 6px;border:1px solid var(--border);border-radius:4px;text-align:right;font-size:13px"
          onchange="saveBonus(this)">
      </td>`;
      html += `<td><strong>¥${(p.total || 0).toFixed(0)}</strong></td>`;
      html += `</tr>`;
    });
    html += '</tbody></table></div>';

    el.innerHTML = html;
  } catch(e) {
    el.innerHTML = `<div class="card"><p>加载失败: ${e.message}</p></div>`;
  }
}

let editingStaffId = null;

async function showEditStaffModal(id) {
  editingStaffId = id;
  const staff = await fetchJSON(`${API}/staff`);
  const s = staff.find(p => p.id === id);
  if (!s) return;

  document.getElementById('edit-staff-name').value = s.name;
  document.getElementById('edit-staff-hourly').value = s.hourly_wage || 15;
  document.getElementById('edit-staff-fullday').value = s.full_day_hours || 11;
  document.getElementById('edit-staff-note').value = s.note || '';
  document.getElementById('edit-staff-modal').style.display = 'flex';
}

function closeEditStaffModal() {
  document.getElementById('edit-staff-modal').style.display = 'none';
  editingStaffId = null;
}

function closeModalOnBackdropStaff(event) {
  if (event.target.id === 'edit-staff-modal') closeEditStaffModal();
}

async function handleEditStaffSubmit(e) {
  e.preventDefault();
  if (!editingStaffId) return;
  const name = document.getElementById('edit-staff-name').value.trim();
  if (!name) { showToast('请输入姓名'); return; }
  const hourly = parseFloat(document.getElementById('edit-staff-hourly').value) || 15;
  const fullday = parseFloat(document.getElementById('edit-staff-fullday').value) || 11;
  const note = document.getElementById('edit-staff-note').value.trim() || '';

  try {
    const res = await fetch(`${API}/staff/${editingStaffId}`, {
      method: 'PUT',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({name, hourly_wage: hourly, full_day_hours: fullday, note}),
    });
    if (!res.ok) throw new Error('更新失败');
    showToast('员工已更新');
    closeEditStaffModal();
    loadTab(currentTab);
  } catch(e) {
    showToast('更新失败: ' + e.message);
  }
}

async function deleteStaff(id) {
  if (!confirm('确定要删除该员工吗？')) return;
  try {
    const res = await fetch(`${API}/staff/${id}`, {method: 'DELETE'});
    if (!res.ok) throw new Error('删除失败');
    showToast('员工已删除');
    loadTab(currentTab);
  } catch(e) {
    showToast('删除失败: ' + e.message);
  }
}

async function saveBasePay(input) {
  const staffId = input.dataset.staff;
  const yearMonth = input.dataset.ym;
  const val = parseFloat(input.value) || 0;
  try {
    await fetch('/api/payroll/bonus', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({staff_id: `${staffId}|base`, year_month: yearMonth, bonus: val}),
    });
    showToast('底薪已更新');
  } catch(e) { showToast('保存底薪失败'); }
}

async function saveFABonus(input) {
  const staffId = input.dataset.staff;
  const yearMonth = input.dataset.ym;
  const bonus = parseFloat(input.value) || 0;
  try {
    await fetch('/api/payroll/bonus', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({staff_id: `${staffId}|fa`, year_month: yearMonth, bonus}),
    });
  } catch(e) {
    showToast('保存全勤奖失败');
  }
}

async function saveBonus(input) {
  const staffId = input.dataset.staff;
  const yearMonth = input.dataset.ym;
  const bonus = parseFloat(input.value) || 0;
  try {
    await fetch('/api/payroll/bonus', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({staff_id: staffId, year_month: yearMonth, bonus}),
    });
  } catch(e) {
    showToast('保存奖金失败');
  }
}

async function handleCreateStaff() {
  const name = document.getElementById('staff-name').value.trim();
  if (!name) { showToast('请输入姓名'); return; }
  const roles = [...document.querySelectorAll('.staff-role:checked')].map(cb => cb.value);
  if (roles.length === 0) { showToast('请选择角色'); return; }
  const morning = document.getElementById('staff-morning').value || '80';
  const evening = document.getElementById('staff-evening').value || '60';
  const note = document.getElementById('staff-note').value;

  const params = new URLSearchParams({name, morning_rate: morning, evening_rate: evening, note});
  roles.forEach(r => params.append('roles', r));

  try {
    const res = await fetch(`${API}/staff?${params}`, {method: 'POST'});
    if (!res.ok) { const e = await res.json(); throw new Error(e.detail || '请求失败'); }
    showToast('员工已添加');
    loadTab(currentTab);
  } catch(e) {
    showToast('保存失败: ' + e.message);
  }
}
