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
            <p>角色: ${s.roles.join(' / ')} | 早班 ¥${s.morning_rate} / 晚班 ¥${s.evening_rate}</p>
            ${s.note ? `<p style="font-size:12px;color:var(--muted)">${s.note}</p>` : ''}
          </div>
          <div style="display:flex;gap:4px">
            <button class="btn btn-sm btn-outline" onclick="editStaff('${s.id}')">编辑</button>
            <button class="btn btn-sm" style="background:var(--danger);font-size:11px;padding:2px 8px" onclick="deleteStaff('${s.id}')">删除</button>
          </div>
        </div>
      </div>`;
    });
    el.innerHTML = html;
  } catch(e) {
    el.innerHTML = `<div class="card"><p>加载失败: ${e.message}</p></div>`;
  }
}

async function renderStaffPayroll() {
  const el = document.getElementById('staff-content');
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

    let html = `<h3 style="margin-top:12px">${ym} 工资单</h3>`;

    html += '<div class="stat-row">';
    html += `<div class="stat-card"><div class="stat-value">¥${totalPayroll.toFixed(0)}</div><div class="stat-label">工资总额</div></div>`;
    html += `<div class="stat-card"><div class="stat-value">¥${avgPay.toFixed(0)}</div><div class="stat-label">人均工资</div></div>`;
    html += '</div>';
    html += '<div class="stat-row">';
    html += `<div class="stat-card"><div class="stat-value">¥${maxPay.toFixed(0)}</div><div class="stat-label">最高</div></div>`;
    html += `<div class="stat-card"><div class="stat-value">¥${minPay.toFixed(0)}</div><div class="stat-label">最低</div></div>`;
    html += '</div>';

    html += '<div class="card"><h3>明细</h3><table><thead><tr>';
    html += '<th>姓名</th><th>早班</th><th>晚班</th><th>加班</th><th>绩效</th><th>基础</th><th>奖金</th><th>合计</th>';
    html += '</tr></thead><tbody>';
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

    el.innerHTML = html;
  } catch(e) {
    el.innerHTML = `<div class="card"><p>加载失败: ${e.message}</p></div>`;
  }
}

async function editStaff(id) {
  const staff = await fetchJSON(`${API}/staff`);
  const s = staff.find(p => p.id === id);
  if (!s) return;

  const name = prompt('姓名', s.name);
  if (!name) return;
  const morning = prompt('早班工资', s.morning_rate) || s.morning_rate;
  const evening = prompt('晚班工资', s.evening_rate) || s.evening_rate;
  const note = prompt('备注', s.note || '') || '';

  try {
    const res = await fetch(`${API}/staff/${id}`, {
      method: 'PUT',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({name, morning_rate: parseFloat(morning), evening_rate: parseFloat(evening), note}),
    });
    if (!res.ok) throw new Error('更新失败');
    showToast('员工已更新');
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
