import {api} from './api.js';
import {formatDate, label, statusClass} from './status.js';

const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const lines = (value) => Array.isArray(value) ? value.join('\n') : (value || '');
const checked = (selected, value) => selected?.includes(value) ? 'selected' : '';
const checkedBox = (selected, value) => selected?.includes(value) ? 'checked' : '';
const badge = (value) => `<span class="status-pill ${statusClass(value)}">${esc(label(value))}</span>`;
const empty = (title, detail) => `<div class="empty-state"><strong>${esc(title)}</strong>${esc(detail)}</div>`;
const employeeUrl = (id) => `employee/${encodeURIComponent(id)}`;

export function isEmployeeRoute(page) {
  return /^employee\/[A-Za-z0-9_-]{1,80}$/.test(page);
}
export function isCompanyBuilderRoute(page) {
  return ['company-builder','departments','ai-team','company-structure','roles','workflows','tools','knowledge-sources'].includes(page) || isEmployeeRoute(page);
}

function sectionHeading(title, detail, actions = '') {
  return `<div class="panel-heading"><div><h2 class="panel-title">${esc(title)}</h2><div class="panel-caption">${esc(detail)}</div></div>${actions}</div>`;
}
function navLinks() {
  return `<div class="builder-tabs"><button class="button button-quiet small-button" data-page="departments">الأقسام</button><button class="button button-quiet small-button" data-page="ai-team">فريق AI</button><button class="button button-quiet small-button" data-page="company-structure">الهيكل</button><button class="button button-quiet small-button" data-page="roles">الأدوار والصلاحيات</button><button class="button button-quiet small-button" data-page="workflows">سير العمل</button><button class="button button-quiet small-button" data-page="tools">الأدوات</button><button class="button button-quiet small-button" data-page="knowledge-sources">المعرفة</button></div>`;
}

export async function renderCompanyPage(page, state) {
  if (isEmployeeRoute(page)) return renderEmployeeProfile(page.split('/')[1], state);
  if (page === 'company-builder') return renderBuilderHome();
  if (page === 'departments') return renderDepartments(state);
  if (page === 'ai-team') return renderEmployees(state);
  if (page === 'company-structure') return renderStructure(state);
  if (page === 'roles') return renderRoles(state);
  if (page === 'workflows') return renderWorkflows();
  if (page === 'tools') return renderTools();
  if (page === 'knowledge-sources') return renderKnowledge();
  return empty('الوحدة غير موجودة', 'ارجع إلى منشئ الشركة لاختيار وحدة متاحة.');
}

async function renderBuilderHome() {
  const [{summary}, structure] = await Promise.all([api.companyBuilderSummary(), api.companyStructure()]);
  const metrics = [
    ['إجمالي الأقسام',summary.total_departments,'▦'],['الأقسام النشطة',summary.active_departments,'✓'],
    ['مديرو AI',summary.total_managers,'⌘'],['موظفو AI',summary.total_ai_employees,'✣'],
    ['الموظفون النشطون',summary.active_employees,'●'],['المتوقفون مؤقتاً',summary.paused_employees,'Ⅱ'],
    ['العاملون',summary.total_workers,'⚙'],['سير العمل النشط',summary.active_workflows,'⟳'],
    ['الأدوات المسجلة',summary.registered_tools,'⌁'],['مصادر المعرفة',summary.knowledge_sources,'▤'],
  ];
  const cards=metrics.map(([title,value,icon])=>`<article class="kpi-card"><div class="kpi-top"><span>${esc(title)}</span><span class="kpi-icon green">${esc(icon)}</span></div><div class="kpi-value-row"><strong class="kpi-value">${Number(value)}</strong></div><div class="kpi-note">مصدر البيانات: SQLite</div></article>`).join('');
  const departmentRows=structure.departments.map((item)=>`<div class="setting-row"><div class="setting-copy"><strong>${esc(item.name)}</strong><small>${esc(item.code || 'بلا رمز')} · ${item.employees.length} موظف/موظفة أعلى الهرم</small></div>${badge(item.status)}</div>`).join('');
  return `${navLinks()}<section class="builder-summary-grid">${cards}</section><section class="panel">${sectionHeading('بناء الشركة من الداخل','كل المؤشرات مأخوذة من السجلات الفعلية، ويمكن تعديل الهيكل من الوحدات التالية.')}${navLinks()}</section><section class="panel">${sectionHeading('الأقسام والهيكل الحالي','معاينة مختصرة من قاعدة البيانات.')}${structure.departments.length?departmentRows:empty('لا توجد أقسام بعد.','اضغط «الأقسام» ثم «إنشاء قسم» للبدء.')}</section>`;
}

function multiSelect(name, title, items, selectedIds = [], textKey = 'name') {
  return `<label class="field-group"><span class="field-label">${esc(title)}</span><select class="text-field multi-select" name="${esc(name)}" multiple size="4">${items.map((item)=>`<option value="${esc(item.id)}" ${checked(selectedIds,item.id)}>${esc(item[textKey])}</option>`).join('')}</select><small class="field-hint">استخدم Ctrl/⌘ للاختيار المتعدد.</small></label>`;
}

function departmentForm(departments, employees, tools, knowledge, editing) {
  const item=editing||{};
  return `<section class="panel builder-form-section"><details class="builder-form-details" ${editing?'open':''}><summary>${editing?'تعديل القسم: '+esc(item.name):'＋ إنشاء قسم'}</summary><form data-company-form="department" data-id="${esc(item.id||'')}"><div class="form-grid"><label class="field-group"><span class="field-label">اسم القسم</span><input class="text-field" name="name" required maxlength="180" value="${esc(item.name||'')}" /></label><label class="field-group"><span class="field-label">رمز القسم</span><input class="text-field" name="code" required maxlength="32" pattern="[A-Za-z0-9_-]{2,32}" placeholder="CONTENT" value="${esc(item.code||'')}" /></label><label class="field-group field-span-2"><span class="field-label">الوصف</span><textarea class="text-field textarea-field" name="description" maxlength="4000">${esc(item.description||'')}</textarea></label><label class="field-group"><span class="field-label">مدير القسم</span><select class="text-field" name="manager_employee_id"><option value="">غير محدد</option>${employees.filter((x)=>x.employee_type==='MANAGER'&&x.status==='ACTIVE'&&x.department_id===item.id).map((x)=>`<option value="${esc(x.id)}" ${x.id===item.manager_employee_id?'selected':''}>${esc(x.name)} · ${esc(x.department)}</option>`).join('')}</select></label><label class="field-group"><span class="field-label">الحالة</span><select class="text-field" name="status"><option value="ACTIVE" ${item.status!=='INACTIVE'?'selected':''}>نشط</option><option value="INACTIVE" ${item.status==='INACTIVE'?'selected':''}>غير نشط</option></select></label><label class="field-group"><span class="field-label">الأولوية</span><select class="text-field" name="priority">${['LOW','NORMAL','HIGH','URGENT'].map((v)=>`<option value="${v}" ${(item.priority||'NORMAL')===v?'selected':''}>${esc(label(v))}</option>`).join('')}</select></label><label class="field-group"><span class="field-label">الأهداف (كل هدف في سطر)</span><textarea class="text-field textarea-field" name="goals">${esc(lines(item.goals))}</textarea></label><label class="field-group"><span class="field-label">مؤشرات الأداء KPIs (كل مؤشر في سطر)</span><textarea class="text-field textarea-field" name="kpis">${esc(lines(item.kpis))}</textarea></label>${multiSelect('allowed_tools','الأدوات المسموحة',tools,item.allowed_tools||[])}${multiSelect('knowledge_source_ids','مصادر المعرفة',knowledge,item.knowledge_source_ids||[])}</div><div class="form-error" data-form-error hidden></div><div class="form-actions"><button type="button" class="button button-quiet" data-company-action="cancel-department">إلغاء</button><button class="button button-primary">${editing?'حفظ التغييرات':'حفظ القسم'}</button></div></form></details></section>`;
}

async function renderDepartments(state) {
  const [{departments},{employees},{tools},{knowledge_sources:knowledge}]=await Promise.all([api.departments(),api.employees(),api.tools(),api.knowledgeSources()]);
  const editing=departments.find((item)=>item.id===state.editingDepartmentId)||null;
  const rows=departments.length?`<div class="table-wrap"><table class="content-table"><thead><tr><th>القسم</th><th>الرمز</th><th>المدير</th><th>الأولوية</th><th>الحالة</th><th>إجراءات</th></tr></thead><tbody>${departments.map((item)=>`<tr><td><strong>${esc(item.name)}</strong><div class="content-subtitle">${esc(item.description||'')}</div></td><td><code>${esc(item.code||'—')}</code></td><td>${esc(item.manager_name||'—')}</td><td>${badge(item.priority)}</td><td>${badge(item.status)}</td><td><button class="button button-quiet small-button" data-company-action="edit-department" data-id="${esc(item.id)}">تعديل</button> <button class="button button-quiet small-button danger-button" data-company-action="delete-department" data-id="${esc(item.id)}">حذف</button></td></tr>`).join('')}</tbody></table></div>`:empty('لا توجد أقسام بعد.','أنشئ القسم الأول؛ سيُحفظ في قاعدة البيانات ويظهر في الهيكل فوراً.');
  return `${navLinks()}${departmentForm(departments,employees,tools,knowledge,editing)}<section class="panel">${sectionHeading('الأقسام','سجلات قاعدة البيانات وعلاقاتها بالمديرين والأدوات والمعرفة.')}${rows}</section>`;
}

function employeeForm({employee=null,type='EMPLOYEE',departments=[],employees=[],roles=[],permissions=[],tools=[],knowledge=[],modules=[]}) {
  const item=employee||{}; const currentType=employee?.employee_type||type;
  const selectedRole=roles.find((r)=>r.id===item.role_id)||roles.find((r)=>r.code===({MANAGER:'AI_MANAGER',EMPLOYEE:'AI_EMPLOYEE',WORKER:'AI_WORKER'}[currentType]));
  const selectedPermissions=item.permissions||selectedRole?.permissions||[];
  const parentOptions=employees.filter((e)=>e.id!==item.id);
  const managerOptions=parentOptions.filter((e)=>e.employee_type==='MANAGER'&&e.status==='ACTIVE'&&(!item.department_id||e.department_id===item.department_id));
  return `<section class="panel builder-form-section"><h3 class="panel-title">${employee?'تعديل ملف الموظف':'إضافة '+label(currentType)}</h3><form data-company-form="employee" data-id="${esc(item.id||'')}"><input type="hidden" name="employee_type" value="${esc(currentType)}"/><div class="form-grid"><label class="field-group"><span class="field-label">الاسم</span><input class="text-field" name="name" required maxlength="180" value="${esc(item.name||'')}" /></label><label class="field-group"><span class="field-label">رمز الموظف</span><input class="text-field" name="employee_code" maxlength="32" pattern="[A-Za-z0-9_-]{2,32}" placeholder="يُنشأ تلقائياً إن تُرك فارغاً" value="${esc(item.employee_code||'')}" /></label><label class="field-group"><span class="field-label">الدور</span><select class="text-field" name="role_id">${roles.map((r)=>`<option value="${esc(r.id)}" ${r.id===selectedRole?.id?'selected':''}>${esc(r.name)}</option>`).join('')}</select></label><label class="field-group"><span class="field-label">القسم</span><select class="text-field" name="department_id" required><option value="">اختر قسماً</option>${departments.map((d)=>`<option value="${esc(d.id)}" ${d.id===item.department_id?'selected':''}>${esc(d.name)}</option>`).join('')}</select></label><label class="field-group"><span class="field-label">المدير المباشر</span><select class="text-field" name="manager_employee_id"><option value="">دون مدير مباشر</option>${managerOptions.map((e)=>`<option value="${esc(e.id)}" ${e.id===item.manager_employee_id?'selected':''}>${esc(e.name)}</option>`).join('')}</select></label><label class="field-group"><span class="field-label">الموظف الأعلى في الهيكل (اختياري)</span><select class="text-field" name="parent_employee_id"><option value="">لا يوجد</option>${parentOptions.map((e)=>`<option value="${esc(e.id)}" ${e.id===item.parent_employee_id?'selected':''}>${esc(e.name)} · ${esc(label(e.employee_type))}</option>`).join('')}</select></label><label class="field-group"><span class="field-label">المسمى الوظيفي</span><input class="text-field" name="role" maxlength="120" value="${esc(item.role||selectedRole?.name||'')}" /></label><label class="field-group"><span class="field-label">الأولوية</span><select class="text-field" name="priority">${['LOW','NORMAL','HIGH','URGENT'].map((v)=>`<option value="${v}" ${(item.priority||'NORMAL')===v?'selected':''}>${esc(label(v))}</option>`).join('')}</select></label><label class="field-group field-span-2"><span class="field-label">الوصف الوظيفي</span><textarea class="text-field textarea-field" name="job_description" maxlength="4000">${esc(item.job_description||item.description||'')}</textarea></label><label class="field-group"><span class="field-label">المسؤوليات (كل واحدة في سطر)</span><textarea class="text-field textarea-field" name="responsibilities">${esc(lines(item.responsibilities))}</textarea></label><label class="field-group"><span class="field-label">الأهداف</span><textarea class="text-field textarea-field" name="goals">${esc(lines(item.goals))}</textarea></label><label class="field-group"><span class="field-label">مؤشرات الأداء KPIs</span><textarea class="text-field textarea-field" name="kpis">${esc(lines(item.kpis))}</textarea></label><label class="field-group"><span class="field-label">المهارات</span><textarea class="text-field textarea-field" name="skills">${esc(lines(item.skills))}</textarea></label><label class="field-group field-span-2"><span class="field-label">System Prompt</span><textarea class="text-field textarea-field" name="system_prompt" maxlength="12000">${esc(item.system_prompt||'')}</textarea></label><label class="field-group"><span class="field-label">الشخصية</span><input class="text-field" name="personality" maxlength="2000" value="${esc(item.personality||'')}" /></label><label class="field-group"><span class="field-label">النموذج المفضل (اختياري، الافتراضي أول نموذج متاح)</span><input class="text-field" name="preferred_model" maxlength="120" value="${esc(item.preferred_model||'')}" /></label><label class="field-group"><span class="field-label">النموذج الاحتياطي</span><input class="text-field" name="fallback_model" maxlength="120" value="${esc(item.fallback_model||'')}" /></label><label class="field-group"><span class="field-label">حالة الموظف</span><select class="text-field" name="status">${['ACTIVE','PAUSED','INACTIVE'].map((v)=>`<option value="${v}" ${(item.status||'ACTIVE')===v?'selected':''}>${esc(label(v))}</option>`).join('')}</select></label><label class="field-group checkbox-field"><input type="checkbox" name="memory_enabled" ${item.memory_enabled!==false?'checked':''}/><span>تفعيل ذاكرة الموظف</span></label>${multiSelect('modules','الوحدات المصرح بها',modules.filter((module)=>module.employee_accessible),(item.modules||[]),'title')}${multiSelect('tools','الأدوات المصرح بها',tools,(item.tools||[]).map((x)=>typeof x==='string'?x:x.id))}${multiSelect('knowledge_source_ids','مصادر المعرفة المصرح بها',knowledge,(item.knowledge_sources||[]).map((x)=>typeof x==='string'?x:x.id))}<fieldset class="field-group field-span-2 permission-fieldset"><legend class="field-label">الصلاحيات الأولية (لا يختار الموظف صلاحياته بنفسه)</legend><div class="permission-check-grid">${permissions.map((p)=>`<label class="permission-check ${p.sensitive?'sensitive-permission':''}"><input type="checkbox" name="permissions" value="${esc(p.code)}" ${checkedBox(selectedPermissions,p.code)}/><span>${esc(p.name)}${p.sensitive?' · حساسة':''}</span></label>`).join('')}</div></fieldset></div><div class="form-error" data-form-error hidden></div><div class="form-actions"><button type="button" class="button button-quiet" data-company-action="cancel-employee-form">إلغاء</button><button class="button button-primary">${employee?'حفظ الملف':'إنشاء الموظف'}</button></div></form></section>`;
}

async function renderEmployees(state) {
  const [{employees},{departments},{roles},{permissions},{tools},{knowledge_sources:knowledge}]=await Promise.all([api.employees({q:state.search}),api.departments(),api.roles(),api.permissions(),api.tools(),api.knowledgeSources()]);
  const rows=employees.length?`<div class="table-wrap"><table class="content-table"><thead><tr><th>الموظف</th><th>النوع</th><th>القسم</th><th>المدير</th><th>الدور</th><th>الحالة</th><th>الملف</th></tr></thead><tbody>${employees.map((e)=>`<tr><td><strong>${esc(e.name)}</strong><div class="content-subtitle"><code>${esc(e.employee_code)}</code></div></td><td>${esc(label(e.employee_type))}</td><td>${esc(e.department||'—')}</td><td>${esc(e.manager_name||'—')}</td><td>${esc(e.role_name||e.role)}</td><td>${badge(e.status)}</td><td><button class="button button-quiet small-button" data-company-action="open-employee" data-id="${esc(e.id)}">فتح الملف</button></td></tr>`).join('')}</tbody></table></div>`:empty('لا يوجد موظفون بعد.','أنشئ مدير AI أو موظفاً أو عاملاً من النماذج أعلاه.');
  const form=state.showEmployeeForm?employeeForm({type:state.newEmployeeType,departments,employees,roles,permissions,tools,knowledge,modules:state.modules}):'';
  return `${navLinks()}<section class="panel">${sectionHeading('فريق الذكاء الاصطناعي','إنشاء المديرين والموظفين والعاملين وحفظ علاقاتهم وصلاحياتهم في قاعدة البيانات.',`<div class="action-wrap"><button class="button button-quiet" data-company-action="new-employee" data-type="MANAGER">＋ مدير AI</button><button class="button button-primary" data-company-action="new-employee" data-type="EMPLOYEE">＋ موظف AI</button><button class="button button-quiet" data-company-action="new-employee" data-type="WORKER">＋ عامل AI</button></div>`)}${form}${rows}</section>`;
}

function employeeTree(nodes) {
  if (!nodes?.length) return '';
  return `<ul class="org-children">${nodes.map((node)=>`<li><button class="org-node" data-company-action="open-employee" data-id="${esc(node.id)}"><span class="org-node-name">${esc(node.name)}</span><span>${esc(label(node.type))}</span>${badge(node.status)}</button>${employeeTree(node.children)}</li>`).join('')}</ul>`;
}
async function renderStructure(state) {
  const tree=await api.companyStructure();
  return `${navLinks()}<section class="panel">${sectionHeading('الهيكل التنظيمي','عرض مبني على علاقة الأقسام والمديرين والموظفين الحقيقية في SQLite.')}<div class="org-tree"><div class="org-owner">المالك · أعلى مستوى</div>${tree.departments.length?tree.departments.map((d)=>`<section class="org-department"><div class="org-department-head"><button class="org-department-button" data-company-action="open-department" data-id="${esc(d.id)}">${esc(d.name)}</button><span>${esc(d.code||'')}</span>${badge(d.status)}</div>${d.manager_name?`<div class="org-manager-label">مدير القسم: ${esc(d.manager_name)}</div>`:''}${employeeTree(d.employees)}</section>`).join(''):empty('لا توجد أقسام بعد.','أنشئ قسماً ثم أضف مديراً أو موظفاً لعرض الهيكل.')}</div></section>`;
}

async function renderRoles(state) {
  const [{roles},{permissions},{employees}]=await Promise.all([api.roles(),api.permissions(),api.employees()]);
  const editing=roles.find((role)=>role.id===state.editingRoleId)||null;
  const roleForm=(role=null)=>`<section class="panel builder-form-section"><details class="builder-form-details" ${role?'open':''}><summary>${role?'تعديل الدور: '+esc(role.name):'＋ إنشاء دور مخصص'}</summary><form data-company-form="role" data-id="${esc(role?.id||'')}"><div class="form-grid"><label class="field-group"><span class="field-label">اسم الدور</span><input class="text-field" name="name" required maxlength="120" value="${esc(role?.name||'')}"/></label><label class="field-group"><span class="field-label">رمز الدور</span><input class="text-field" name="code" required maxlength="32" pattern="[A-Za-z0-9_-]{2,32}" ${role?'readonly':''} value="${esc(role?.code||'')}"/></label><label class="field-group field-span-2"><span class="field-label">الوصف</span><textarea class="text-field textarea-field" name="description" maxlength="4000">${esc(role?.description||'')}</textarea></label><fieldset class="field-group field-span-2 permission-fieldset"><legend class="field-label">صلاحيات قالب الدور</legend><div class="permission-check-grid">${permissions.map((p)=>`<label class="permission-check ${p.sensitive?'sensitive-permission':''}"><input type="checkbox" name="permissions" value="${esc(p.code)}" ${checkedBox(role?.permissions||[],p.code)}/><span>${esc(p.name)}${p.sensitive?' · حساسة':''}</span></label>`).join('')}</div></fieldset></div><div class="form-error" data-form-error hidden></div><div class="form-actions"><button type="button" class="button button-quiet" data-company-action="cancel-role">إلغاء</button><button class="button button-primary">${role?'حفظ الدور':'إنشاء الدور'}</button></div></form></details></section>`;
  const matrix=roles.map((role)=>`<article class="panel role-card"><div class="entity-card-head"><strong>${esc(role.name)}</strong><span class="text-pill">${employees.filter((e)=>e.role_id===role.id).length} مستخدم</span></div><p class="panel-caption">${esc(role.description||'')}</p><div class="permission-chip-list">${role.permissions.map((code)=>{const p=permissions.find((x)=>x.code===code);return `<span class="permission-chip ${p?.sensitive?'sensitive-permission':''}">${esc(p?.name||code)}</span>`}).join('')}</div><div class="form-actions"><button class="button button-quiet small-button" data-company-action="edit-role" data-id="${esc(role.id)}">تعديل الصلاحيات</button>${role.is_system?'':'<button class="button button-quiet small-button danger-button" data-company-action="delete-role" data-id="'+esc(role.id)+'">حذف</button>'}</div></article>`).join('');
  return `${navLinks()}${roleForm(editing)}<section class="panel">${sectionHeading('الأدوار والصلاحيات','الأدوار قوالب محفوظة في SQLite؛ لكل موظف صلاحيات مستقلة قابلة للمراجعة. الحذف محمي إذا استُخدم الدور.')}${matrix||empty('لا توجد أدوار.','')}</section><section class="panel">${sectionHeading('سجل الصلاحيات','رموز صلاحية واضحة، مع تمييز ما يتطلب تفويض المالك.')}${permissions.length?`<div class="permission-list">${permissions.map((p)=>`<div class="setting-row"><div class="setting-copy"><strong>${esc(p.name)}</strong><small><code>${esc(p.code)}</code></small></div>${p.sensitive?'<span class="text-pill sensitive-tag">يتطلب المالك</span>':'<span class="text-pill">عادي</span>'}</div>`).join('')}</div>`:empty('لا توجد صلاحيات مسجلة.','')}</section>`;
}

async function renderWorkflows() {
  const {workflows}=await api.workflows();
  const rows=workflows.length?`<div class="workflow-list">${workflows.map((w)=>`<article class="workflow-card"><div class="entity-card-head"><strong>${esc(w.name)}</strong>${badge(w.status)}</div><p>${esc(w.description||'—')}</p><div class="workflow-steps">${w.steps.map((step)=>`<span class="workflow-step"><small>${step.position}</small>${esc(step.name)}</span>`).join('<span class="workflow-arrow">←</span>')}</div></article>`).join('')}</div>`:empty('لا توجد مسارات عمل بعد.','أضف مساراً وخطواته؛ هذا الأساس لا يشغّل أتمتة إنتاج تلقائية.');
  return `${navLinks()}<section class="panel">${sectionHeading('منشئ سير العمل','المرحلة الحالية تحفظ تعريف المسار والخطوات؛ لا تُشغّل إنتاجاً أو أتمتة خارجية.') }<details class="builder-form-details"><summary>＋ إنشاء سير عمل</summary><form data-company-form="workflow"><div class="form-grid"><label class="field-group"><span class="field-label">اسم سير العمل</span><input class="text-field" name="name" required maxlength="180"/></label><label class="field-group"><span class="field-label">الحالة</span><select class="text-field" name="status"><option value="DRAFT">مسودة</option><option value="ACTIVE">نشط</option><option value="PAUSED">متوقف</option></select></label><label class="field-group field-span-2"><span class="field-label">الوصف</span><textarea class="text-field textarea-field" name="description" maxlength="4000"></textarea></label><label class="field-group field-span-2"><span class="field-label">الخطوات (كل خطوة في سطر)</span><textarea class="text-field textarea-field" name="steps" required placeholder="فكرة\nبحث\nمراجعة\nموافقة"></textarea></label></div><div class="form-error" data-form-error hidden></div><div class="form-actions"><button class="button button-primary">حفظ المسار</button></div></form></details>${rows}</section>`;
}

async function renderTools() {
  const [{tools},{permissions},{employees}]=await Promise.all([api.tools(),api.permissions(),api.employees()]);
  const rows=tools.length?`<div class="table-wrap"><table class="content-table"><thead><tr><th>الأداة</th><th>النوع</th><th>المرجع</th><th>الصلاحية المطلوبة</th><th>الموظفون المصرح لهم</th><th>الحالة</th></tr></thead><tbody>${tools.map((t)=>`<tr><td><strong>${esc(t.name)}</strong><div class="content-subtitle">${esc(t.description||'')}</div></td><td>${esc(t.tool_type)}</td><td>${esc(t.endpoint_ref||'—')}</td><td><code>${esc(t.required_permission||'—')}</code></td><td>${esc(employees.filter((employee)=>employee.tools.some((assigned)=>assigned.id===t.id)).map((employee)=>employee.name).join('، ')||'—')}</td><td>${badge(t.status)}</td></tr>`).join('')}</tbody></table></div>`:empty('سجل الأدوات فارغ.','أضف مرجعاً وصفياً للأداة؛ لا تُحفظ مفاتيح API أو كلمات مرور هنا.');
  return `${navLinks()}<section class="panel">${sectionHeading('سجل الأدوات','السجلات تصف التكاملات فقط؛ الأسرار تبقى في إعداد الخادم الآمن.') }<details class="builder-form-details"><summary>＋ إضافة أداة</summary><form data-company-form="tool"><div class="form-grid"><label class="field-group"><span class="field-label">اسم الأداة</span><input class="text-field" name="name" required maxlength="160"/></label><label class="field-group"><span class="field-label">النوع</span><input class="text-field" name="tool_type" required maxlength="60" placeholder="API / MCP / internal"/></label><label class="field-group"><span class="field-label">رمز اختياري</span><input class="text-field" name="code" maxlength="32"/></label><label class="field-group"><span class="field-label">الصلاحية المطلوبة</span><select class="text-field" name="required_permission"><option value="">لا شيء</option>${permissions.map((p)=>`<option value="${esc(p.code)}">${esc(p.code)}</option>`).join('')}</select></label><label class="field-group field-span-2"><span class="field-label">الوصف</span><textarea class="text-field textarea-field" name="description" maxlength="4000"></textarea></label><label class="field-group field-span-2"><span class="field-label">مرجع تكامل (دون أسرار)</span><input class="text-field" name="endpoint_ref" maxlength="500" placeholder="اسم الموصل أو عنوان endpoint غير حساس"/></label></div><div class="form-error" data-form-error hidden></div><div class="form-actions"><button class="button button-primary">حفظ الأداة</button></div></form></details>${rows}</section>`;
}

async function renderKnowledge() {
  const {knowledge_sources:sources}=await api.knowledgeSources();
  const rows=sources.length?`<div class="content-list">${sources.map((s)=>`<article class="content-list-item"><span class="feature-icon">▤</span><div class="list-text"><strong>${esc(s.name)}</strong><p>${esc(s.source_type)} · ${esc(s.description||'')}</p><p>${esc(s.source_ref||'محتوى داخلي')}</p></div>${badge(s.status)}<span class="text-pill">المحتوى محمي</span></article>`).join('')}</div>`:empty('لا توجد مصادر معرفة.','أضف محتوى موثوقاً ثم امنح كل موظف حق الوصول من ملفه.');
  return `${navLinks()}<section class="panel">${sectionHeading('مصادر المعرفة','محتوى المصادر محفوظ بالخلفية ولا يُعرض في الفهرس؛ لا يصل الموظف إلا إلى المصادر الممنوحة له.') }<details class="builder-form-details"><summary>＋ إضافة مصدر معرفة</summary><form data-company-form="knowledge"><div class="form-grid"><label class="field-group"><span class="field-label">اسم المصدر</span><input class="text-field" name="name" required maxlength="180"/></label><label class="field-group"><span class="field-label">النوع</span><select class="text-field" name="source_type"><option>Company Knowledge</option><option>Character Bible</option><option>Project Document</option><option>Script</option><option>Policy</option><option>Research</option></select></label><label class="field-group field-span-2"><span class="field-label">الوصف</span><textarea class="text-field textarea-field" name="description" maxlength="4000"></textarea></label><label class="field-group field-span-2"><span class="field-label">مرجع اختياري</span><input class="text-field" name="source_ref" maxlength="500" placeholder="مرجع آمن أو اسم ملف فقط"/></label><label class="field-group field-span-2"><span class="field-label">النص المعرفي</span><textarea class="text-field textarea-field knowledge-content-field" name="content" maxlength="50000" placeholder="المحتوى سيُرسل إلى AI Router فقط عند اختبار موظف مُصرّح له بمصدر المعرفة هذا."></textarea></label></div><div class="form-error" data-form-error hidden></div><div class="form-actions"><button class="button button-primary">حفظ المصدر</button></div></form></details>${rows}</section>`;
}

function permissionForm(employee, permissions) {
  return `<form data-company-form="permissions" data-id="${esc(employee.id)}"><div class="permission-check-grid">${permissions.map((p)=>`<label class="permission-check ${p.sensitive?'sensitive-permission':''}"><input type="checkbox" name="permissions" value="${esc(p.code)}" ${checkedBox(employee.permissions,p.code)}/><span>${esc(p.name)}${p.sensitive?' · حساسة':''}</span></label>`).join('')}</div><div class="form-error" data-form-error hidden></div><div class="form-actions"><button class="button button-primary">حفظ الصلاحيات</button></div></form>`;
}
function employeeTaskForm(employee,projects=[]) {
  return `<form data-company-form="employee-task" data-id="${esc(employee.id)}"><div class="form-grid"><label class="field-group"><span class="field-label">اسم المهمة</span><input class="text-field" name="title" required maxlength="180"/></label><label class="field-group"><span class="field-label">الأولوية</span><select class="text-field" name="priority"><option value="NORMAL">عادية</option><option value="LOW">منخفضة</option><option value="HIGH">عالية</option><option value="URGENT">عاجلة</option></select></label><label class="field-group field-span-2"><span class="field-label">الوصف</span><textarea class="text-field textarea-field" name="description" maxlength="4000"></textarea></label><label class="field-group"><span class="field-label">المشروع</span><select class="text-field" name="project_id"><option value="">دون مشروع</option>${projects.map((project)=>`<option value="${esc(project.id)}">${esc(project.name)}</option>`).join('')}</select></label><label class="field-group"><span class="field-label">الموعد النهائي</span><input class="text-field" type="date" name="deadline"/></label><label class="field-group checkbox-field"><input type="checkbox" name="approval_required"/><span>تتطلب موافقة المالك</span></label></div><div class="form-error" data-form-error hidden></div><div class="form-actions"><button class="button button-primary">حفظ وتكليف</button></div></form>`;
}
async function renderEmployeeProfile(id, state) {
  const [{employee,tasks,activity},{permissions},{departments},{employees},{roles},{tools},{knowledge_sources:knowledge},{projects}]=await Promise.all([api.employee(id),api.permissions(),api.departments(),api.employees(),api.roles(),api.tools(),api.knowledgeSources(),api.company()]);
  const tabs=[['overview','نظرة عامة'],['job','الوظيفة'],['ai','إعداد AI'],['tools','الأدوات'],['modules','الوحدات'],['permissions','الصلاحيات'],['knowledge','المعرفة'],['tasks','المهام'],['activity','النشاط'],['settings','الإعدادات']];
  const active=state.employeeTab||'overview';
  const taskRows=tasks.length?`<div class="table-wrap"><table class="content-table"><thead><tr><th>المهمة</th><th>الحالة</th><th>الأولوية</th><th>الموعد</th></tr></thead><tbody>${tasks.map((t)=>`<tr><td>${esc(t.title)}</td><td>${badge(t.status)}</td><td>${badge(t.priority)}</td><td>${esc(formatDate(t.deadline,false))}</td></tr>`).join('')}</tbody></table></div>`:empty('لا توجد مهام مسندة.','يمكن إنشاء مهمة من هذا الملف.');
  const content={
    overview:`<div class="profile-overview-grid"><div class="setting-row"><div class="setting-copy"><strong>النوع</strong><small>${esc(label(employee.employee_type))}</small></div>${badge(employee.status)}</div><div class="setting-row"><div class="setting-copy"><strong>القسم</strong><small>${esc(employee.department||'—')}</small></div></div><div class="setting-row"><div class="setting-copy"><strong>المدير</strong><small>${esc(employee.manager_name||'—')}</small></div></div><div class="setting-row"><div class="setting-copy"><strong>الدور</strong><small>${esc(employee.role_name||employee.role)}</small></div></div></div><p>${esc(employee.description||employee.job_description||'لا يوجد وصف بعد.')}</p><section class="employee-test-area"><h3>اختبار الموظف</h3><p class="panel-caption">سيُرسل النص ومصادر المعرفة المصرح بها إلى AI Router المضبوط على الخادم. إذا لم يكن مهيأً فلن تُنشأ إجابة وهمية.</p><form data-company-form="employee-test" data-id="${esc(employee.id)}"><label class="field-group"><span class="field-label">رسالة الاختبار</span><textarea class="text-field textarea-field" name="message" required maxlength="4000" placeholder="اكتب طلباً لاختبار إعداد الموظف…"></textarea></label><div class="form-error" data-form-error hidden></div><div class="form-actions"><button class="button button-primary">🧪 اختبار الموظف</button></div></form>${state.aiTestResult?.employeeId===employee.id?`<div class="ai-test-result"><div class="entity-card-head"><strong>نتيجة AI Router</strong><span class="text-pill">${esc(state.aiTestResult.model||'')}</span></div><p>${esc(state.aiTestResult.response)}</p></div>`:''}</section>`,
    job:`<h3>الوصف الوظيفي</h3><p>${esc(employee.job_description||'—')}</p><div class="profile-overview-grid"><div><h4>المسؤوليات</h4>${employee.responsibilities?.length?`<ul>${employee.responsibilities.map((x)=>`<li>${esc(x)}</li>`).join('')}</ul>`:empty('لا توجد مسؤوليات مسجلة.','')}</div><div><h4>الأهداف</h4>${employee.goals?.length?`<ul>${employee.goals.map((x)=>`<li>${esc(x)}</li>`).join('')}</ul>`:empty('لا توجد أهداف مسجلة.','')}</div><div><h4>مؤشرات الأداء</h4>${employee.kpis?.length?`<ul>${employee.kpis.map((x)=>`<li>${esc(x)}</li>`).join('')}</ul>`:empty('لا توجد مؤشرات أداء.','')}</div></div>`,
    ai:`<div class="setting-row"><div class="setting-copy"><strong>النموذج المفضل</strong><small>${esc(employee.preferred_model||'أول نموذج متاح في AI Router')}</small></div></div><div class="setting-row"><div class="setting-copy"><strong>النموذج الاحتياطي</strong><small>${esc(employee.fallback_model||'غير محدد')}</small></div></div><div class="setting-row"><div class="setting-copy"><strong>الشخصية</strong><small>${esc(employee.personality||'غير محددة')}</small></div></div><div class="setting-row"><div class="setting-copy"><strong>الذاكرة</strong><small>${employee.memory_enabled?'مفعلة':'متوقفة'}</small></div></div><h4>System Prompt</h4><pre class="prompt-view">${esc(employee.system_prompt||'لا يوجد prompt مخصص.')}</pre><h4>المهارات</h4>${employee.skills?.length?employee.skills.map((x)=>`<span class="permission-chip">${esc(x)}</span>`).join(''):empty('لا توجد مهارات مسجلة.','')}`,
    tools:`${employee.tools?.length?`<div class="content-list">${employee.tools.map((t)=>`<div class="content-list-item"><span class="feature-icon">⌁</span><div class="list-text"><strong>${esc(t.name)}</strong><p>${esc(t.tool_type)}</p></div>${badge(t.status)}</div>`).join('')}</div>`:empty('لا توجد أدوات ممنوحة.','يمكن إضافة الأدوات من نموذج تعديل الموظف.')}`,
    modules:`${employee.modules?.length?`<div class="permission-chip-list">${employee.modules.map((id)=>{const module=state.modules.find((item)=>item.id===id);return `<span class="permission-chip">${esc(module?.title||id)}</span>`}).join('')}</div>`:empty('لا توجد وحدات ممنوحة.','يمكن تحديد الوحدات من نموذج تعديل الموظف.')}<div class="form-actions"><button class="button button-quiet" data-company-action="toggle-edit-employee">تعديل وحدات الوصول</button></div>`,
    permissions:permissionForm(employee,permissions),
    knowledge:`${employee.knowledge_sources?.length?`<div class="content-list">${employee.knowledge_sources.map((k)=>`<div class="content-list-item"><span class="feature-icon">▤</span><div class="list-text"><strong>${esc(k.name)}</strong><p>${esc(k.source_type)} · ${esc(k.description||'')}</p></div>${badge(k.status)}</div>`).join('')}</div>`:empty('لا توجد مصادر معرفة ممنوحة.','امنح الوصول من نموذج تعديل الموظف.')}`,
    tasks:taskRows,
    activity:activity.length?`<div class="table-wrap"><table class="content-table"><thead><tr><th>الإجراء</th><th>الوقت</th><th>الحالة</th><th>النتيجة</th></tr></thead><tbody>${activity.map((a)=>`<tr><td><code>${esc(a.action)}</code></td><td>${esc(formatDate(a.timestamp))}</td><td>${badge(a.status)}</td><td>${esc(a.result||a.error||'—')}</td></tr>`).join('')}</tbody></table></div>`:empty('لا يوجد نشاط لهذا الملف.','سيظهر هنا إنشاء الموظف والمهام والإجراءات.'),
    settings:`<div class="setting-row"><div class="setting-copy"><strong>الحالة</strong><small>${esc(label(employee.status))}</small></div>${badge(employee.status)}</div><div class="setting-row"><div class="setting-copy"><strong>رمز الموظف</strong><small><code>${esc(employee.employee_code)}</code></small></div></div><div class="form-actions"><button class="button button-quiet danger-button" data-company-action="delete-employee" data-id="${esc(employee.id)}">حذف ملف الموظف</button></div>`,
  };
  const editing=state.editingEmployee?employeeForm({employee,departments,employees,roles,permissions,tools,knowledge,modules:state.modules}):'';
  const taskForm=state.showEmployeeTaskForm?employeeTaskForm(employee,projects):'';
  const managerForm=state.showManagerForm?`<form data-company-form="manager" data-id="${esc(employee.id)}"><div class="form-grid"><label class="field-group"><span class="field-label">القسم</span><select class="text-field" name="department_id" required>${departments.map((d)=>`<option value="${esc(d.id)}" ${d.id===employee.department_id?'selected':''}>${esc(d.name)}</option>`).join('')}</select></label><label class="field-group"><span class="field-label">المدير المباشر</span><select class="text-field" name="manager_employee_id"><option value="">دون مدير</option>${employees.filter((e)=>e.employee_type==='MANAGER'&&e.status==='ACTIVE'&&e.id!==employee.id&&e.department_id===employee.department_id).map((e)=>`<option value="${esc(e.id)}" ${e.id===employee.manager_employee_id?'selected':''}>${esc(e.name)} · ${esc(e.department)}</option>`).join('')}</select></label><label class="field-group"><span class="field-label">الموظف الأعلى (اختياري)</span><select class="text-field" name="parent_employee_id"><option value="">لا يوجد</option>${employees.filter((e)=>e.id!==employee.id&&e.department_id===employee.department_id).map((e)=>`<option value="${esc(e.id)}" ${e.id===employee.parent_employee_id?'selected':''}>${esc(e.name)}</option>`).join('')}</select></label></div><div class="form-error" data-form-error hidden></div><div class="form-actions"><button class="button button-primary">حفظ التغيير</button></div></form>`:'';
  return `${navLinks()}<section class="panel employee-profile"><div class="panel-heading"><div><div class="eyebrow">${esc(employee.employee_code)} · ${esc(label(employee.employee_type))}</div><h2 class="panel-title">${esc(employee.name)}</h2><div class="panel-caption">${esc(employee.role_name||employee.role)} · ${esc(employee.department||'دون قسم')} · ${badge(employee.status)}</div></div><div class="action-wrap"><button class="button button-quiet" data-company-action="toggle-edit-employee">تعديل الملف</button><button class="button button-quiet" data-company-action="toggle-manager">تغيير المدير</button><button class="button button-quiet" data-company-action="toggle-employee-task">＋ تكليف بمهمة</button><button class="button ${employee.status==='ACTIVE'?'button-quiet':'button-primary'}" data-company-action="toggle-employee-status" data-id="${esc(employee.id)}" data-status="${employee.status==='ACTIVE'?'PAUSED':'ACTIVE'}">${employee.status==='ACTIVE'?'إيقاف مؤقت':'تفعيل'}</button></div></div>${editing}${managerForm?`<section class="panel nested-panel"><h3 class="panel-title">تغيير العلاقة التنظيمية</h3>${managerForm}</section>`:''}${taskForm?`<section class="panel nested-panel"><h3 class="panel-title">تكليف بمهمة</h3>${taskForm}</section>`:''}<div class="profile-tabs">${tabs.map(([key,title])=>`<button type="button" class="profile-tab ${active===key?'active':''}" data-profile-tab="${key}">${title}</button>`).join('')}</div><section class="panel profile-panel" data-profile-section="${active}">${content[active]||content.overview}</section></section>`;
}

function readPayload(form) {
  const data=new FormData(form); const payload={};
  for (const [key,value] of data.entries()) {
    const el=form.elements.namedItem(key);
    if (el instanceof HTMLSelectElement && el.multiple) { payload[key]=[...el.selectedOptions].map((o)=>o.value); continue; }
    if (el instanceof HTMLInputElement && el.type==='checkbox') continue;
    payload[key]=value;
  }
  for (const key of ['goals','kpis','responsibilities','skills','steps']) {
    if (form.elements.namedItem(key)) payload[key]=String(payload[key]||'').split(/\r?\n/).map((x)=>x.trim()).filter(Boolean);
  }
  for (const key of ['permissions','tools','knowledge_source_ids','allowed_tools','modules']) {
    const elements=form.querySelectorAll(`input[type="checkbox"][name="${key}"]:checked`);
    const controls=form.querySelectorAll(`select[multiple][name="${key}"]`);
    const checkboxes=form.querySelectorAll(`input[type="checkbox"][name="${key}"]`);
    if (controls.length) payload[key]=[...controls[0].selectedOptions].map((option)=>option.value);
    else if (checkboxes.length) payload[key]=[...elements].map((el)=>el.value);
  }
  for (const name of ['memory_enabled','approval_required']) {
    const el=form.elements.namedItem(name); if (el instanceof HTMLInputElement && el.type==='checkbox') payload[name]=el.checked;
  }
  return payload;
}
function showError(form,message) {
  const node=form.querySelector('[data-form-error]');
  if (node) { node.textContent=message; node.hidden=!message; }
}

export async function handleCompanyClick(event, state, renderPage, toast) {
  const tab=event.target.closest('[data-profile-tab]');
  if (tab) {
    state.employeeTab=tab.dataset.profileTab;
    const panel=event.currentTarget.querySelector('[data-profile-section]');
    const buttons=[...event.currentTarget.querySelectorAll('[data-profile-tab]')];
    // Re-render the selected section using the stored profile route; this also refreshes actions.
    await renderPage(state.page);
    return true;
  }
  const button=event.target.closest('[data-company-action]');
  if (!button) return false;
  const action=button.dataset.companyAction; const id=button.dataset.id;
  try {
    if (action==='new-employee') { state.showEmployeeForm=true; state.newEmployeeType=button.dataset.type||'EMPLOYEE'; await renderPage('ai-team'); }
    else if (action==='cancel-employee-form') { state.showEmployeeForm=false; await renderPage('ai-team'); }
    else if (action==='edit-role') { state.editingRoleId=id; await renderPage('roles'); }
    else if (action==='cancel-role') { state.editingRoleId=''; await renderPage('roles'); }
    else if (action==='delete-role') {
      if (!window.confirm('حذف الدور المخصص؟ سيُرفض الحذف إن كان مرتبطاً بموظف.')) return true;
      await api.deleteRole(id); state.editingRoleId=''; toast('حُذف الدور المخصص.'); await renderPage('roles');
    }
    else if (action==='open-department' || action==='edit-department') { state.editingDepartmentId=id; await renderPage('departments'); }
    else if (action==='cancel-department') { state.editingDepartmentId=''; await renderPage('departments'); }
    else if (action==='open-employee') { state.editingEmployee=false; state.employeeTab='overview'; state.aiTestResult=null; await renderPage(employeeUrl(id)); }
    else if (action==='toggle-edit-employee') { state.editingEmployee=!state.editingEmployee; await renderPage(state.page); }
    else if (action==='toggle-employee-task') { state.showEmployeeTaskForm=!state.showEmployeeTaskForm; await renderPage(state.page); }
    else if (action==='toggle-manager') { state.showManagerForm=!state.showManagerForm; await renderPage(state.page); }
    else if (action==='toggle-employee-status') { await api.updateEmployee(id,{status:button.dataset.status}); toast(button.dataset.status==='ACTIVE'?'تم تفعيل الموظف.':'أُوقف الموظف مؤقتاً.'); await renderPage(state.page); }
    else if (action==='delete-department') {
      if (!window.confirm('سيُحذف القسم إذا لم يرتبط بموظفين أو مهام. متابعة؟')) return true;
      await api.deleteDepartment(id); toast('حُذف القسم.'); state.editingDepartmentId=''; await renderPage('departments');
    } else if (action==='delete-employee') {
      if (!window.confirm('حذف ملف الموظف نهائياً؟ سيُرفض الحذف إن كانت له مهام أو تقارير مباشرة.')) return true;
      await api.deleteEmployee(id); toast('حُذف ملف الموظف.'); await renderPage('ai-team');
    }
  } catch (error) { toast(error.message||'تعذر تنفيذ الإجراء.','error'); }
  return true;
}

export async function handleCompanySubmit(event, state, renderPage, toast) {
  const form=event.target.closest('form[data-company-form]');
  if (!form) return false;
  event.preventDefault(); showError(form,''); const button=form.querySelector('button[type="submit"],button:not([type])'); if (button) button.disabled=true;
  const payload=readPayload(form); const id=form.dataset.id||''; const kind=form.dataset.companyForm;
  try {
    if (kind==='department') {
      if (id) await api.updateDepartment(id,payload); else await api.createDepartment(payload);
      state.editingDepartmentId=''; toast(id?'حُفظت تغييرات القسم.':'أُنشئ القسم وحُفظ في قاعدة البيانات.'); await renderPage('departments');
    } else if (kind==='employee') {
      if (id) await api.updateEmployee(id,payload); else await api.createEmployee(payload);
      state.showEmployeeForm=false; toast(id?'حُفظ ملف الموظف.':'أُنشئ ملف الموظف في قاعدة البيانات.');
      await renderPage(id?employeeUrl(id):'ai-team');
    } else if (kind==='permissions') {
      await api.setEmployeePermissions(id,payload.permissions||[]); toast('حُفظت صلاحيات الموظف.'); await renderPage(state.page);
    } else if (kind==='role') {
      if (id) await api.updateRole(id,payload); else await api.createRole(payload);
      state.editingRoleId=''; toast(id?'حُدّثت صلاحيات الدور.':'أُنشئ الدور المخصص.'); await renderPage('roles');
    } else if (kind==='workflow') {
      await api.createWorkflow(payload); toast('حُفظ سير العمل وخطواته.'); await renderPage('workflows');
    } else if (kind==='tool') {
      await api.createTool(payload); toast('أُضيفت الأداة إلى السجل.'); await renderPage('tools');
    } else if (kind==='knowledge') {
      await api.createKnowledgeSource(payload); toast('حُفظ مصدر المعرفة.'); await renderPage('knowledge-sources');
    } else if (kind==='employee-task') {
      await api.createEmployeeTask(id,payload); state.showEmployeeTaskForm=false; toast('حُفظت المهمة وربطت بالموظف.'); await renderPage(state.page);
    } else if (kind==='manager') {
      await api.updateEmployee(id,payload); state.showManagerForm=false; toast('حُدّثت العلاقة التنظيمية.'); await renderPage(state.page);
    } else if (kind==='employee-test') {
      const result=await api.testEmployee(id,payload.message); state.aiTestResult={employeeId:id,...result.result}; toast('وصلت الاستجابة الحقيقية من AI Router.'); await renderPage(state.page);
    }
  } catch (error) { showError(form,error.message||'تعذّر حفظ البيانات.'); }
  finally { if (button) button.disabled=false; }
  return true;
}
