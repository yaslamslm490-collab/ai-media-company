import {api, ApiError} from './api.js';
import {formatDate, label, statusClass} from './status.js';
import {handleCompanyClick, handleCompanySubmit, isCompanyBuilderRoute, isEmployeeRoute, renderCompanyPage} from './company-builder.js';
import {renderAccountResults, renderAccountSearch} from './account-browser.js';
import {VoiceEngine} from './voice-engine.js';

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[char]));
const state = {
  page: location.hash.slice(1) || 'dashboard',
  modules: [],
  builder: [],
  health: null,
  authorized: false,
  dashboard: null,
  search: '',
  taskStatus: '',
  approvalStatus: '',
  activityStatus: '',
  busy: false,
  renderRevision: 0,
  newEmployeeType: 'EMPLOYEE',
  editingDepartmentId: '',
  editingEmployee: false,
  employeeTab: 'overview',
  showEmployeeTaskForm: false,
  showManagerForm: false,
  aiTestResult: null,
  editingRoleId: '',
  integrationSearch: '',
  integrationProblemsOnly: false,
  integrationPage: null,
  integrationSearchTimer: null,
  integrationRequestRevision: 0,
};
const pageContent = $('#page-content');
const titles = new Map();

async function refreshIntegrationAccountList() {
  const host = $('#integration-account-results', pageContent);
  if (!host) return;
  const revision = ++state.integrationRequestRevision;
  host.setAttribute('aria-busy', 'true');
  try {
    const data = await api.externalIntegrations({
      limit: 5,
      offset: 0,
      q: state.integrationSearch,
      issues: state.integrationProblemsOnly ? '1' : '',
    });
    if (revision !== state.integrationRequestRevision || !host.isConnected) return;
    data.search = state.integrationSearch;
    data.problems = state.integrationProblemsOnly;
    state.integrationPage = data;
    host.innerHTML = renderAccountResults(data);
  } catch (error) {
    if (revision === state.integrationRequestRevision && host.isConnected) {
      host.innerHTML = '<div class="empty-state">تعذر تحميل الحسابات. تحقق من الاتصال وحاول مجدداً.</div>';
      toast(apiFailure(error), 'error');
    }
  } finally {
    if (host.isConnected) host.removeAttribute('aria-busy');
  }
}

function statusBadge(value) {
  return `<span class="status-pill ${statusClass(value)}">${esc(label(value))}</span>`;
}
function toast(message, type = 'success') {
  const item = document.createElement('div');
  item.className = `toast ${type === 'error' ? 'toast-error' : ''}`;
  item.textContent = message;
  $('#toast-region').append(item);
  setTimeout(() => item.remove(), 3600);
}
function openModal(id) {
  const modal = document.getElementById(id);
  if (!modal) return;
  modal.hidden = false;
  modal.querySelector('input:not([type=hidden]), textarea')?.focus();
}
function closeModal(id) {
  const modal = document.getElementById(id);
  if (modal) modal.hidden = true;
}
function showFormError(id, message = '') {
  const node = document.getElementById(id);
  if (!node) return;
  node.textContent = message;
  node.hidden = !message;
}
function apiFailure(error) {
  if (error instanceof ApiError && ['authentication_required', 'invalid_token', 'auth_not_configured'].includes(error.code)) {
    state.authorized = false;
    if (error.code === 'invalid_token') api.clearToken();
    updateAuthUI();
  }
  return error instanceof ApiError ? error.message : 'حدث خطأ غير متوقع أثناء الاتصال بالخادم.';
}
function updateAuthUI() {
  $('#auth-button-label').textContent = state.authorized ? 'إنهاء الجلسة' : 'دخول المالك';
  $('#auth-button-icon').textContent = state.authorized ? '✓' : '◇';
  $('#auth-state-label').textContent = state.authorized ? 'جلسة مالك موثقة' : (state.health?.checks?.authentication === 'NOT_CONFIGURED' ? 'المصادقة غير مهيأة' : 'يلزم دخول المالك');
  $('#workspace-state').textContent = state.authorized ? 'موثّق' : 'مقيّد';
  $('#workspace-state').className = `workspace-state ${state.authorized ? 'online' : 'unconfigured'}`;
}
function renderNavigation() {
  const nav = $('#sidebar-navigation');
  const groups = new Map();
  state.modules.forEach((module) => {
    if (!groups.has(module.group)) groups.set(module.group, []);
    groups.get(module.group).push(module);
    titles.set(module.id, module.title);
  });
  nav.innerHTML = [...groups.entries()].map(([group, modules]) => `<section class="nav-group"><h2 class="nav-label">${esc(group)}</h2>${modules.map((module) => `<button type="button" class="nav-item ${state.page === module.id || (isEmployeeRoute(state.page) && module.id === 'ai-team') ? 'active' : ''}" data-page="${esc(module.id)}"><span class="nav-icon">${esc(module.icon)}</span><span>${esc(module.title)}</span>${module.state === 'NOT_CONFIGURED' ? '<span class="nav-state" title="غير مهيأ">·</span>' : ''}</button>`).join('')}</section>`).join('');
}
function renderHealth() {
  const health = state.health;
  if (!health) return;
  const allChecks = [
    ['الخادم الخلفي', health.checks.backend], ['قاعدة البيانات', health.checks.database],
    ['المصادقة', health.checks.authentication], ['موجّه النماذج', health.checks.ai_router],
    ['Manus', health.checks.manus], ['GitHub', health.checks.github],
  ];
  const integrations = health.checks.external_integrations;
  if (integrations && typeof integrations === 'object') Object.entries(integrations).forEach(([name, status]) => allChecks.push([name, status]));
  $('#overall-health-badge').textContent = label(health.overall);
  $('#overall-health-badge').className = `usage-badge ${statusClass(health.overall)}`;
  $('#sidebar-health').innerHTML = allChecks.slice(0, 4).map(([name, status]) => `<div class="health-mini-row"><span>${esc(name)}</span>${statusBadge(status)}</div>`).join('');
  const footer = $('#footer-health');
  footer.innerHTML = `<i class="live-dot ${statusClass(health.overall)}"></i> فُحص النظام ${esc(formatDate(health.checked_at))} · ${esc(label(health.overall))}`;
  $('#page-status-dot').className = `eyebrow-dot ${statusClass(health.overall)}`;
}
function healthCards(health) {
  if (!health) return '<div class="empty-state"><strong>حالة الصحة غير متاحة</strong>تعذّر الحصول على نتيجة الفحص.</div>';
  const names = {backend: 'الخادم الخلفي', database: 'قاعدة البيانات', authentication: 'مصادقة المالك', media_vault: 'خزنة مفاتيح الوسائط', object_storage: 'التخزين الدائم', ai_router: 'AI Router', manus: 'Manus', github: 'GitHub', external_integrations: 'التكاملات الخارجية'};
  const entries = Object.entries(health.checks).filter(([key]) => key !== 'database_engine').flatMap(([key, value]) => value && typeof value === 'object' ? Object.entries(value).map(([name, status]) => [`${names[key]} · ${name}`, status]) : [[names[key] || key, value]]);
  return `<div class="health-grid">${entries.map(([name, status]) => `<article class="panel health-card"><div class="health-card-top"><span class="health-indicator ${statusClass(status)}"></span><span class="health-card-name">${esc(name)}</span>${statusBadge(status)}</div><p>${esc(status === 'ONLINE' ? 'نجح الفحص الفعلي لهذا المكوّن.' : status === 'OFFLINE' ? 'فشل الاتصال عند آخر فحص.' : status === 'ERROR' ? 'أبلغ الفحص عن خطأ.' : 'لا يوجد إعداد أو تكامل لهذا المكوّن حتى الآن.')}</p></article>`).join('')}</div><p class="panel-caption health-timestamp">آخر فحص: ${esc(formatDate(health.checked_at))}</p>`;
}
function emptyState(title, detail) {
  return `<div class="empty-state"><strong>${esc(title)}</strong>${esc(detail)}</div>`;
}
function accessPanel(error = null) {
  const configured = state.health?.checks?.authentication === 'ONLINE';
  const title = configured ? 'سجّل دخول المالك لعرض بيانات الشركة' : 'المصادقة غير مهيأة';
  const detail = error || (configured ? 'بيانات المهام والموافقات خاصة. أدخل كلمة مرور المالك لضمان عدم كشفها.' : 'الخادم الخلفي وقاعدة البيانات جاهزان، لكن كلمة مرور المالك لم تُضبط بعد. عيّن OWNER_MASTER_PASSWORD على الخادم لفتح بيانات الشركة وتفعيل التعديلات.');
  return `<section class="panel access-panel"><div class="access-icon">◇</div><div><span class="eyebrow">وضع الوصول المحمي</span><h2>${esc(title)}</h2><p>${esc(detail)}</p><button class="button button-primary" data-open-auth>تهيئة أو إدخال كلمة مرور المالك</button></div></section><section class="panel health-embed"><div class="panel-heading"><div><h2 class="panel-title">صحة الأنظمة المتاحة للفحص العام</h2><div class="panel-caption">البيانات الخاصة تبقى مغلقة حتى التحقق.</div></div></div>${healthCards(state.health)}</section>`;
}
function metricCard(name, metric, icon) {
  if (metric?.status === 'NOT_CONFIGURED' || metric?.value === null || metric?.value === undefined) {
    return `<article class="kpi-card"><div class="kpi-top"><span>${esc(name)}</span><span class="kpi-icon violet">${esc(icon)}</span></div><div class="kpi-value-row"><strong class="kpi-value metric-unavailable">—</strong></div><div class="kpi-note">${statusBadge('NOT_CONFIGURED')}</div></article>`;
  }
  return `<article class="kpi-card"><div class="kpi-top"><span>${esc(name)}</span><span class="kpi-icon green">${esc(icon)}</span></div><div class="kpi-value-row"><strong class="kpi-value">${Number(metric.value)}</strong></div><div class="kpi-note">مصدر البيانات: قاعدة البيانات</div></article>`;
}
function taskStatusChart(counts) {
  const statuses = ['TODO', 'IN_PROGRESS', 'WAITING_APPROVAL', 'COMPLETED', 'CANCELLED', 'FAILED'];
  const max = Math.max(1, ...statuses.map((status) => Number(counts[status] || 0)));
  return `<div class="task-chart" role="img" aria-label="مخطط حي لتوزيع حالات المهام">${statuses.map((status) => {
    const amount = Number(counts[status] || 0);
    const width = Math.round((amount / max) * 100);
    return `<div class="task-chart-row"><span>${esc(label(status))}</span><div class="task-chart-track"><div class="task-chart-fill ${statusClass(status)}" style="width:${width}%"></div></div><strong>${amount}</strong></div>`;
  }).join('')}</div>`;
}
function renderSystemList(health) {
  const entries = Object.entries(health?.checks || {});
  return entries.map(([key, value]) => {
    const title = ({backend: 'Backend', database: 'Database', authentication: 'Authentication', ai_router: 'AI Router', manus: 'Manus', github: 'GitHub', external_integrations: 'External integrations'})[key] || key;
    if (value && typeof value === 'object') return Object.entries(value).map(([name, status]) => `<div class="setting-row"><div class="setting-copy"><strong>${esc(title)} · ${esc(name)}</strong><small>نتيجة فحص اتصال حقيقي</small></div>${statusBadge(status)}</div>`).join('');
    return `<div class="setting-row"><div class="setting-copy"><strong>${esc(title)}</strong><small>نتيجة فحص اتصال حقيقي</small></div>${statusBadge(value)}</div>`;
  }).join('');
}
function activityRows(items) {
  if (!items.length) return emptyState('لا يوجد نشاط مسجل', 'سيُسجّل إنشاء المهام وتحديثها وقرارات الموافقة هنا.');
  return `<div class="table-wrap"><table class="content-table activity-table"><thead><tr><th>المستخدم</th><th>الإجراء</th><th>الوحدة</th><th>العنصر</th><th>الوقت</th><th>الحالة</th><th>النتيجة / الخطأ</th></tr></thead><tbody>${items.map((item) => `<tr><td>${esc(item.actor)}</td><td><code>${esc(item.action)}</code></td><td>${esc(item.module)}</td><td>${esc(item.object_type)} · ${esc(item.object_id.slice(0, 8))}</td><td>${esc(formatDate(item.timestamp))}</td><td>${statusBadge(item.status)}</td><td>${esc(item.error || item.result || '—')}</td></tr>`).join('')}</tbody></table></div>`;
}
function taskTable(items) {
  if (!items.length) return emptyState('لا توجد مهام', 'أضف مهمة للبدء؛ ستُحفظ في SQLite وتظهر في سجل النشاط.');
  const statuses = ['TODO', 'IN_PROGRESS', 'WAITING_APPROVAL', 'COMPLETED', 'CANCELLED', 'FAILED'];
  return `<div class="table-wrap"><table class="content-table task-table"><thead><tr><th>ID</th><th>المهمة</th><th>المالك</th><th>موظف AI</th><th>القسم</th><th>الأولوية</th><th>الحالة</th><th>أُنشئت</th><th>حُدّثت</th></tr></thead><tbody>${items.map((task) => `<tr><td><code title="${esc(task.id)}">${esc(task.id.slice(0, 8))}</code></td><td><div class="content-main-title">${esc(task.title)}</div><div class="content-subtitle">${esc(task.description || '—')}</div></td><td>${esc(task.owner)}</td><td>${esc(task.assigned_employee || '—')}</td><td>${esc(task.department || '—')}</td><td>${statusBadge(task.priority)}</td><td><select class="select-pill task-status-select" data-task-id="${esc(task.id)}">${statuses.map((status) => `<option value="${status}" ${task.status === status ? 'selected' : ''}>${esc(label(status))}</option>`).join('')}</select></td><td>${esc(formatDate(task.created_at, false))}</td><td>${esc(formatDate(task.updated_at, false))}</td></tr>`).join('')}</tbody></table></div>`;
}
function approvalList(items) {
  if (!items.length) return emptyState('لا توجد طلبات موافقة', 'عند إنشاء طلبات المراجعة أو ربط وحدة الإنتاج ستظهر هنا.');
  return `<div class="content-list">${items.map((approval) => `<article class="content-list-item approval-item"><span class="feature-icon">✓</span><div class="list-text"><strong>${esc(approval.title)}</strong><p>${esc(approval.description || 'لا توجد تفاصيل')} · من ${esc(approval.submitted_by)} · ${esc(formatDate(approval.created_at))}</p>${approval.decision_note ? `<p class="decision-note">ملاحظة القرار: ${esc(approval.decision_note)}</p>` : ''}</div>${statusBadge(approval.status)}${approval.status === 'WAITING_APPROVAL' ? `<div class="approval-actions"><button class="button button-primary small-button" data-approval-decision="APPROVE" data-approval-id="${esc(approval.id)}">موافقة</button><button class="button button-quiet small-button" data-approval-decision="REJECT" data-approval-id="${esc(approval.id)}">رفض</button><button class="button button-quiet small-button" data-approval-decision="REQUEST_CHANGES" data-approval-id="${esc(approval.id)}">طلب تعديلات</button></div>` : ''}</article>`).join('')}</div>`;
}
function renderDashboard(data) {
  const company = data.company;
  const counts = company.task_counts;
  const metrics = [
    ['الأقسام النشطة', company.active_departments, '▦'],
    ['موظفو AI النشطون', company.active_ai_employees, '✣'],
    ['الشخصيات النشطة', company.active_characters, '◉'],
    ['المشاريع النشطة', company.active_projects, '▧'],
    ['المهام قيد التنفيذ', company.running_tasks, '▶'],
    ['موافقات تنتظر المالك', company.waiting_approvals, '✓'],
    ['مهام الإنتاج', company.production_jobs, '◷'],
    ['محتوى منشور', company.published_content, '↗'],
    ['إجمالي سجل النشاط', {status: 'ONLINE', value: company.activity_count}, '≋'],
    ['مديرو AI', {status: 'ONLINE', value: data.company_builder.total_managers}, '⌘'],
    ['العاملون', {status: 'ONLINE', value: data.company_builder.total_workers}, '⚙'],
    ['سير العمل النشط', {status: 'ONLINE', value: data.company_builder.active_workflows}, '⟳'],
    ['الأدوات المسجلة', {status: 'ONLINE', value: data.company_builder.registered_tools}, '⌁'],
    ['مصادر المعرفة', {status: 'ONLINE', value: data.company_builder.knowledge_sources}, '▤'],
  ];
  const inProgress = data.recent_tasks.filter((item) => item.status === 'IN_PROGRESS');
  return `<section class="kpi-grid">${metrics.map((metric) => metricCard(...metric)).join('')}</section>
  <section class="dashboard-grid"><article class="panel"><div class="panel-heading"><div><h2 class="panel-title">حالة الشركة</h2><div class="panel-caption">قيم من قاعدة البيانات الحالية؛ غير المتاح موسوم صراحة.</div></div>${statusBadge(data.health.overall)}</div><div class="status-count-grid">${['TODO','IN_PROGRESS','WAITING_APPROVAL','COMPLETED','CANCELLED','FAILED'].map((status) => `<div class="status-count"><span>${esc(label(status))}</span><strong>${counts[status] ?? 0}</strong></div>`).join('')}</div>${taskStatusChart(counts)}<div class="section-top"><h3>صحة الأنظمة</h3><button class="text-link" data-page="security">التفاصيل ←</button></div>${renderSystemList(data.health)}</article>
  <article class="panel"><div class="panel-heading"><div><h2 class="panel-title">ما يحتاج انتباهك</h2><div class="panel-caption">المهام الجارية والموافقات المعلّقة فقط</div></div></div><div class="section-top compact-section"><h3>مهام جارية (${inProgress.length})</h3><button class="text-link" data-page="tasks">كل المهام ←</button></div>${inProgress.length ? `<div class="task-list">${inProgress.map((task) => `<div class="task-row"><span class="task-priority high"></span><div class="task-content"><strong>${esc(task.title)}</strong><span>${esc(task.owner)} · ${esc(task.department || 'دون قسم')}</span></div>${statusBadge(task.status)}</div>`).join('')}</div>` : emptyState('لا توجد مهام جارية', 'لا توجد سجلات بحالة IN_PROGRESS.')}
  <div class="section-top compact-section"><h3>موافقات معلّقة (${data.pending_approvals.length})</h3><button class="text-link" data-page="approvals">مركز الموافقات ←</button></div>${data.pending_approvals.length ? approvalList(data.pending_approvals.slice(0, 4)) : emptyState('لا توجد موافقات معلّقة', 'لم تُنشأ طلبات تنتظر المالك بعد.')}</article></section>
  <section class="panel"><div class="panel-heading"><div><h2 class="panel-title">آخر النشاط</h2><div class="panel-caption">أحداث محفوظة في سجل التدقيق.</div></div><button class="text-link" data-page="activity">فتح السجل ←</button></div>${activityRows(data.recent_activity)}</section>`;
}
async function renderTasksPage() {
  const response = await api.tasks({status: state.taskStatus, q: state.search});
  return `<section class="panel"><div class="panel-heading"><div><h2 class="panel-title">مركز المهام <span class="text-pill">${response.tasks.length} نتيجة</span></h2><div class="panel-caption">ست حالات معرّفة، والبيانات تُقرأ وتُحفظ عبر REST API وSQLite.</div></div><button class="button button-primary" id="new-task-button">＋ مهمة جديدة</button></div><div class="filter-row"><label class="field-group"><span class="field-label">تصفية حسب الحالة</span><select class="select-pill" id="task-status-filter"><option value="">كل الحالات</option>${response.statuses.map((status) => `<option value="${status}" ${state.taskStatus === status ? 'selected' : ''}>${esc(label(status))}</option>`).join('')}</select></label><span class="panel-caption">المهمة تتضمن ID والعنوان والوصف والمالك والموظف والقسم والأولوية والحالة وتواريخ الإنشاء والتحديث.</span></div>${taskTable(response.tasks)}</section>`;
}
async function renderApprovalsPage() {
  const response = await api.approvals({status: state.approvalStatus, q: state.search});
  return `<section class="panel"><div class="panel-heading"><div><h2 class="panel-title">مركز الموافقات <span class="text-pill">${response.approvals.length} طلب</span></h2><div class="panel-caption">تُحفظ القرارات وسجل القرار والفاعل والتوقيت مع كل إجراء.</div></div><button class="button button-primary" id="new-approval-button">＋ طلب موافقة</button></div><div class="filter-row"><label class="field-group"><span class="field-label">تصفية حسب الحالة</span><select class="select-pill" id="approval-status-filter"><option value="">كل الحالات</option>${[['WAITING_APPROVAL','بانتظار المالك'],['APPROVED','تمت الموافقة'],['REJECTED','مرفوض'],['CHANGES_REQUESTED','مطلوب تعديل']].map(([value, title]) => `<option value="${value}" ${state.approvalStatus === value ? 'selected' : ''}>${title}</option>`).join('')}</select></label></div>${approvalList(response.approvals)}</section>`;
}
async function renderActivityPage() {
  const response = await api.activity({status: state.activityStatus, q: state.search});
  return `<section class="panel"><div class="panel-heading"><div><h2 class="panel-title">سجل النشاط</h2><div class="panel-caption">كل تعديل مهم يضيف فعلاً ووقتاً ونتيجة أو خطأ.</div></div><select class="select-pill" id="activity-status-filter"><option value="">كل الحالات</option><option value="SUCCESS" ${state.activityStatus === 'SUCCESS' ? 'selected' : ''}>ناجح</option><option value="FAILURE" ${state.activityStatus === 'FAILURE' ? 'selected' : ''}>فشل</option></select></div>${activityRows(response.activity)}</section>`;
}
function entityCards(items, detail, emptyTitle) {
  if (!items.length) return emptyState(emptyTitle, 'لا توجد سجلات مطابقة في قاعدة البيانات.');
  return `<div class="entity-grid">${items.map((item) => `<article class="panel entity-card"><div class="entity-card-head"><strong>${esc(item.name)}</strong>${statusBadge(item.status)}</div><p>${esc(detail(item) || '—')}</p></article>`).join('')}</div>`;
}
async function entityPage(id) {
  const company = await api.company();
  const config = {
    characters: ['الشخصيات الرقمية', company.characters, (item) => `${item.role} · ${item.description}`],
    projects: ['المشاريع', company.projects, (item) => item.description],
  }[id];
  return `<section class="panel"><div class="panel-heading"><div><h2 class="panel-title">${esc(config[0])}</h2><div class="panel-caption">سجلات فعلية محفوظة في قاعدة البيانات.</div></div></div>${entityCards(config[1], config[2], 'لا توجد سجلات بعد.')}</section>`;
}
function integrationPage(module) {
  const key = {'ai-router': 'ai_router', manus: 'manus', github: 'github'}[module.id];
  const status = state.health?.checks?.[key] || 'NOT_CONFIGURED';
  const detail = module.id === 'manus'
    ? 'يفحص الخادم واجهة Manus API عبر GET /v2/task.list?limit=1 باستخدام مفتاح الخادم؛ لا تُعرض بيانات المهام أو المفتاح في اللوحة.'
    : module.id === 'ai-router'
      ? 'يُظهر الفحص نتيجة نقطة /models لموجّه OpenAI-compatible، عند توفر اعتمادات الخادم.'
      : 'يُظهر الفحص حالة GitHub API باستخدام اعتماد المضيف المهيأ دون كشف رمز الوصول.';
  return `<section class="panel integration-page"><div class="panel-heading"><div><h2 class="panel-title">${esc(module.title)}</h2><div class="panel-caption">حالة اتصال فعلية من الخلفية.</div></div>${statusBadge(status)}</div><p>${esc(detail)}</p><p class="panel-caption">آخر فحص: ${esc(formatDate(state.health?.checked_at))}</p></section>`;
}
async function externalIntegrationsPage() {
  const revision = ++state.integrationRequestRevision;
  const search = state.integrationSearch || '';
  const problems = Boolean(state.integrationProblemsOnly);
  const data = await api.externalIntegrations({limit: 5, offset: 0, q: search, issues: problems ? '1' : ''});
  if (revision !== state.integrationRequestRevision) return '<section class="panel"><p>جار تحديث النتائج…</p></section>';
  data.search = search;
  data.problems = problems;
  state.integrationPage = data;
  const accounts = data.accounts || [];
  const generations = data.generations || [];
  const summary = data.summary || {total_accounts: 0, active_accounts: 0, active_by_service: {VIDEO: 0, AUDIO: 0}, providers: []};
  const adapters = data.generation_adapters || {};
  const canPipeline = adapters.VIDEO === 'READY' && adapters.AUDIO === 'READY';
  const providerSummary = data.provider_summary || [];
  const rotationCards = providerSummary.map((item) => {
    const provider = item.provider;
    const actions = ['VIDEO', 'AUDIO'].map((service) => {
      const count = Number(service === 'VIDEO' ? item.active_video : item.active_audio) || 0;
      return count ? `<button class="button button-quiet" type="button" data-integration-action="rotate" data-provider="${esc(provider)}" data-service="${service}">اختيار حساب ${service === 'VIDEO' ? 'الفيديو' : 'الصوت'} التالي · ${count}</button>` : '';
    }).join('');
    const providerStatus = Number(item.online_count) > 0 ? 'ONLINE' : 'NOT_CONFIGURED';
    return `<article class="panel integration-provider-card"><div class="panel-heading"><div><h3 class="panel-title">${esc(provider)}</h3><div class="panel-caption">${Number(item.total) || 0} حساباً · نشط: فيديو ${Number(item.active_video) || 0} / صوت ${Number(item.active_audio) || 0}</div></div>${statusBadge(providerStatus)}</div><div class="integration-row-actions">${actions || '<span class="panel-caption">لا توجد حسابات نشطة قابلة للتدوير.</span>'}</div></article>`;
  }).join('');
  const adapterCards = [['VIDEO', 'Kling · فيديو'], ['AUDIO', 'ElevenLabs · صوت']].map(([key, title]) => `<div class="integration-metric"><span>${title}</span>${statusBadge(adapters[key] || 'NOT_CONFIGURED')}</div>`).join('');
  const generationRows = generations.length ? generations.map((job) => {
    const paused = (job.paused_accounts || []).map((item) => `${esc(item.label)} (${esc(label(item.reason))})`).join('، ');
    const controls = [job.audio_url ? `<button class="button button-quiet small-button" type="button" data-generation-action="audio" data-generation-id="${esc(job.id)}">تشغيل الصوت</button>` : '', job.output_url ? `<button class="button button-quiet small-button" type="button" data-generation-action="media" data-generation-id="${esc(job.id)}">معاينة الملف النهائي</button>` : '', job.video_url ? `<a class="button button-quiet small-button" href="${esc(job.video_url)}" target="_blank" rel="noopener noreferrer">رابط Kling المؤقت</a>` : '', job.status === 'PROCESSING' ? `<button class="button button-quiet small-button" type="button" data-generation-action="poll" data-generation-id="${esc(job.id)}">فحص حالة Kling</button>` : ''].join('');
    return `<article class="generation-row"><div class="generation-job-heading"><div><strong>${esc(job.kind === 'PIPELINE' ? 'أنبوب صوت + فيديو' : job.kind === 'AUDIO' ? 'توليد صوت' : 'توليد فيديو')}</strong><div class="content-subtitle">${esc(job.id.slice(0, 8))} · ${esc(formatDate(job.created_at))}</div></div>${statusBadge(job.status)}</div><p class="generation-prompt">${esc(job.prompt || '')}</p>${job.error_message ? `<p class="generation-error">${esc(job.error_message)}</p>` : ''}${paused ? `<p class="generation-notice">أُوقف تلقائياً وتم التدوير: ${paused}</p>` : ''}<div class="integration-row-actions">${controls}</div><div class="generation-player" data-generation-player="${esc(job.id)}"></div></article>`;
  }).join('') : emptyState('لا توجد عمليات توليد بعد', 'ستظهر هنا المهام الفعلية وحالة كل حساب ومخرجاته.');
  return `<section class="panel"><div class="panel-heading"><div><h2 class="panel-title">مولدات الوسائط والحسابات</h2><div class="panel-caption">تكاملات Kling للفيديو وElevenLabs للصوت · قائمة الحسابات تُحمّل تدريجياً.</div></div>${statusBadge(summary.total_accounts ? 'READY' : 'NOT_CONFIGURED')}</div><div class="integration-metrics">${adapterCards}<div class="integration-metric"><span>إجمالي الحسابات</span><strong>${Number(summary.total_accounts) || 0}</strong></div><div class="integration-metric"><span>نشطة للفيديو / الصوت</span><strong>${Number(summary.active_by_service?.VIDEO) || 0} / ${Number(summary.active_by_service?.AUDIO) || 0}</strong></div></div><div class="integration-notice"><strong>العرض المحمي:</strong> تُعرض خمس بطاقات مقنّعة أولاً؛ استخدم البحث بالكود أو «عرض المزيد». لا تعود مفاتيح API إلى المتصفح. لا يُرسل طلب توليد إلا عند إرسال النموذج. عند نفاد رصيد صريح أو رفض الاعتماد، يُوقف الحساب ويُجرّب كل بديل نشط مرة واحدة كحد أقصى. يعمل التدوير الآلي لمهام الصوت والفيديو عبر المزودين المهيئين.</div></section><section class="panel"><div class="panel-heading"><div><h2 class="panel-title">إنشاء صوت + فيديو</h2><div class="panel-caption">أنبوب تنفيذي متسلسل: ElevenLabs أولاً، ثم Kling، ثم دمج الصوت مع الفيديو محلياً.</div></div></div><form class="generation-form" data-generation-form="pipeline"><label class="field-group"><span class="field-label">معرّف صوت ElevenLabs</span><input name="voice_id" maxlength="120" required placeholder="Voice ID من مكتبة ElevenLabs"></label><label class="field-group"><span class="field-label">نموذج الصوت</span><input name="model_id" maxlength="100" value="eleven_multilingual_v2" required></label><label class="field-group generation-wide"><span class="field-label">النص المنطوق</span><textarea name="script_text" maxlength="5000" required rows="5" placeholder="النص الذي سيُحوّل إلى تعليق صوتي"></textarea></label><label class="field-group generation-wide"><span class="field-label">وصف المشهد المرئي لـ Kling (حتى 3072 محرفاً)</span><textarea name="visual_prompt" maxlength="3072" required rows="4" placeholder="صف المشهد والحركة والأسلوب والكاميرا"></textarea></label><label class="field-group"><span class="field-label">مدة الفيديو المولّد</span><select name="duration"><option value="5">5 ثوانٍ</option><option value="10">10 ثوانٍ</option><option value="15">15 ثانية</option></select></label><label class="field-group"><span class="field-label">الدقة</span><select name="resolution"><option value="720p">720p</option><option value="1080p">1080p</option><option value="4k">4K</option></select></label><label class="field-group"><span class="field-label">نسبة الأبعاد</span><select name="aspect_ratio"><option value="16:9">16:9 أفقي</option><option value="9:16">9:16 عمودي</option><option value="1:1">1:1 مربع</option></select></label><div class="generation-warning generation-wide">قد يستهلك الطلب رصيداً من ElevenLabs وKling. إذا كان الصوت أطول من الفيديو، يمدد الدمج آخر إطار ثابتاً حتى نهاية التعليق. لا توجد مزامنة شفاه تلقائية. ${canPipeline ? '' : 'أضف حساباً نشطاً مهيأً لكل من ElevenLabs وKling لتفعيل النموذج.'}</div><div class="integration-form-actions generation-wide"><button class="button button-primary" type="submit" ${canPipeline ? '' : 'disabled'}>إنشاء الأنبوب</button><span class="panel-caption">سيظهر الحساب الموقوف وسبب التدوير في سجل الإنتاج.</span></div></form></section><section class="panel"><div class="panel-heading"><div><h2 class="panel-title">سجل الإنتاج</h2><div class="panel-caption">المهام محفوظة في قاعدة البيانات؛ ملفات النشر في التخزين الدائم.</div></div></div><div class="generation-list">${generationRows}</div></section><section class="panel"><div class="panel-heading"><div><h2 class="panel-title">إضافة حساب</h2><div class="panel-caption">أدخل مفتاح API مرة واحدة؛ يُشفّر ولا يُعرض بعد الحفظ.</div></div><span class="text-pill">${Number(summary.total_accounts) || 0} حساباً</span></div><form class="integration-account-form" data-integration-form="create"><label class="field-group"><span class="field-label">اسم تعريفي</span><input name="label" maxlength="120" autocomplete="off" required placeholder="مثال: حساب إنتاج 01"></label><label class="field-group"><span class="field-label">مزود الخدمة</span><select name="provider" required data-provider-choice><option value="Kling">Kling</option><option value="ElevenLabs">ElevenLabs</option></select></label><label class="field-group"><span class="field-label">نوع الخدمة</span><input type="hidden" name="service" value="VIDEO"><span class="text-pill provider-service-label" data-provider-service-label>فيديو</span></label><label class="field-group"><span class="field-label">بادئة رمز الحساب (اختياري)</span><input name="prefix" minlength="2" maxlength="8" pattern="[A-Za-z0-9]{2,8}" autocomplete="off" placeholder="KL أو EL"></label><label class="field-group"><span class="field-label">منطقة الوجهة</span><select name="region_code"><option value="UN">🌐 غير محدد</option><option value="US">🇺🇸 أمريكا</option><option value="EU">🇪🇺 أوروبا</option><option value="TR">🇹🇷 تركيا</option><option value="RU">🇷🇺 روسيا</option><option value="EG">🇪🇬 مصر</option></select></label><label class="field-group integration-secret-field"><span class="field-label">مفتاح API (يُرسل إلى مزوده الرسمي فقط)</span><input type="password" name="credential" minlength="8" maxlength="8192" autocomplete="new-password" required placeholder="لن يُعرض بعد الحفظ"></label><div class="integration-form-actions"><button class="button button-primary" type="submit">＋ حفظ الحساب مشفراً</button><span class="panel-caption">استخدم مفاتيح تملكها أو لديك تصريح باستخدامها.</span></div></form></section><section class="panel"><div class="panel-heading"><div><h2 class="panel-title">الحسابات المحفوظة</h2><div class="panel-caption">تظهر الرموز وحالة الخدمة فقط؛ افتح التفاصيل عند الحاجة. مفاتيح API لا تُعرض.</div></div></div>${renderAccountSearch(search, problems)}<div id="integration-account-results">${renderAccountResults(data)}</div></section>${rotationCards ? `<section class="panel"><div class="panel-heading"><div><h2 class="panel-title">اختيار الحساب التالي يدوياً</h2><div class="panel-caption">يحدّث مؤشر Round-robin فقط؛ لا يرسل طلب توليد.</div></div></div><div class="integration-provider-grid">${rotationCards}</div></section>` : ''}`;
}
function securityPage() {
  return `<section class="panel"><div class="panel-heading"><div><h2 class="panel-title">الأمان والوصول</h2><div class="panel-caption">صلاحية واحدة للمالك في هذه المرحلة؛ لا توجد حسابات أعضاء أو أدوار متعددة.</div></div>${statusBadge(state.health?.checks?.authentication || 'ERROR')}</div><div class="security-callout"><strong>${state.health?.checks?.authentication === 'ONLINE' ? 'كلمة مرور المالك مضبوطة على الخادم.' : 'كلمة مرور المالك غير مهيأة.'}</strong><p>الواجهات الخاصة تتطلب OWNER_MASTER_PASSWORD (أو OWNER_API_TOKEN للتوافق) عبر ترويسة X-Owner-Token. السر لا يُضمّن في الملفات ولا يُرسل إلى سجل النشاط. يخزنه المتصفح في sessionStorage للجلسة الحالية فقط.</p>${state.authorized ? '<button class="button button-quiet" id="logout-button">إنهاء جلسة المالك</button>' : '<button class="button button-primary" data-open-auth>إدخال كلمة مرور المالك</button>'}</div></section><section class="panel health-embed"><div class="panel-heading"><div><h2 class="panel-title">حالة النظام الفعلية</h2><div class="panel-caption">الاتصال بالخادم وقاعدة البيانات مفحوص عند الطلب.</div></div><button class="button button-quiet" id="refresh-health">إعادة الفحص</button></div>${healthCards(state.health)}</section>`;
}
function settingsPage() {
  const checks = Object.entries(state.health?.checks || {}).filter(([key]) => !['backend', 'database', 'database_engine', 'authentication'].includes(key));
  const externalRows = checks.map(([key, value]) => `<div class="setting-row"><div class="setting-copy"><strong>${esc(key)}</strong><small>قراءة آلية من بيئة الخادم</small></div>${typeof value === 'string' ? statusBadge(value) : statusBadge('NOT_CONFIGURED')}</div>`).join('');
  const services = state.serviceIntegrations || [];
  const serviceRows = services.map((item) => `<article class="integration-source-card"><div><strong>${esc(item.label)}</strong><small>مصدر آلي: ${esc(label(item.automatic_status))} · يدوي: ${esc(label(item.manual_status))}</small></div><span class="source-badge ${item.source === 'manual' ? 'manual' : 'automatic'}">مصدر: ${item.source === 'manual' ? 'مدخل يدوي' : 'الخادم آلياً'}</span><button class="button button-quiet small-button" type="button" data-manage-service="${esc(item.key)}">إدارة / إضافة يدوي</button></article>`).join('');
  return `<section class="panel password-settings-panel"><div class="panel-heading"><div><h2 class="panel-title">تغيير كلمة السر</h2><div class="panel-caption">يتطلب الرمز الحالي والرمز الجديد وتأكيده؛ يُحفظ التغيير بشكل دائم على الخادم.</div></div><span class="security-lock">⌁</span></div><form id="owner-password-form" class="compact-form"><label class="field-label">كلمة السر الحالية</label><input class="text-field" name="current_password" type="password" inputmode="numeric" pattern="[0-9]{6}" maxlength="6" autocomplete="current-password" required /><label class="field-label">كلمة السر الجديدة</label><input class="text-field" name="new_password" type="password" inputmode="numeric" pattern="[0-9]{6}" maxlength="6" autocomplete="new-password" required /><label class="field-label">تأكيد كلمة السر الجديدة</label><input class="text-field" name="confirm_password" type="password" inputmode="numeric" pattern="[0-9]{6}" maxlength="6" autocomplete="new-password" required /><div id="owner-password-error" class="form-error" hidden></div><div class="form-actions"><button class="button button-primary" type="submit">حفظ كلمة السر بشكل دائم</button></div></form></section><section class="panel"><div class="panel-heading"><div><h2 class="panel-title">إعدادات التشغيل والتكاملات</h2><div class="panel-caption">كل خدمة تُقرأ آلياً من بيئة الخادم، ويمكن إضافة إعداد يدوي مشفّر عند الحاجة.</div></div><button class="button button-primary" type="button" id="add-integration-button">＋ إضافة تكامل</button></div><div class="integration-source-list">${serviceRows || emptyState('جار تحميل التكاملات', 'أعد فتح الإعدادات بعد لحظات.')}</div><div class="panel-divider"></div><div class="setting-row"><div class="setting-copy"><strong>Backend API</strong><small>نفس المصدر · /api</small></div>${statusBadge(state.health?.checks?.backend || 'ERROR')}</div><div class="setting-row"><div class="setting-copy"><strong>قاعدة البيانات</strong><small>${esc(state.health?.checks?.database_engine || 'محرك غير معروف')}</small></div>${statusBadge(state.health?.checks?.database || 'ERROR')}</div><div class="setting-row"><div class="setting-copy"><strong>المصادقة</strong><small>OWNER_MASTER_PASSWORD من بيئة الخادم</small></div>${statusBadge(state.health?.checks?.authentication || 'NOT_CONFIGURED')}</div>${externalRows}<p class="panel-caption">المفاتيح اليدوية لا تعود إلى المتصفح بعد الحفظ؛ زر العين يبدّل إظهار الحقل قبل الإرسال فقط. يتطلب حفظ الأسرار مفتاح AI_MEDIA_VAULT_KEY مهيأً على الخادم.</p></section>`;
}
function openServiceModal(key = 'manus') {
  const modal = $('#service-integration-overlay');
  if (!modal) return;
  modal.querySelector('[name="service_key"]').value = key;
  modal.querySelector('[name="label"]').value = key.replaceAll('_', ' ');
  openModal('service-integration-overlay');
}
async function loadServiceIntegrations() {
  if (!state.authorized) return;
  try { state.serviceIntegrations = (await api.serviceIntegrations()).integrations || []; } catch (error) { toast(apiFailure(error), 'error'); }
}
let recorder = null;
let recordedChunks = [];
let inlineAttachment = null;
let voiceEngine = null;
function setVoiceState(stateName) {
  const labels = {ready: '🔵 جاهز', listening: '🎙️ يستمع', processing: '🧠 يعالج', speaking: '🔊 يتحدث'};
  const node = $('#voice-status'); if (node) { node.textContent = labels[stateName] || labels.ready; node.className = `voice-status ${stateName}`; }
  const wave = $('#voice-waveform'); if (wave) wave.hidden = stateName !== 'speaking';
  const mute = $('#voice-mute'); if (mute) mute.hidden = !voiceEngine?.running;
  const toggle = $('#voice-live-toggle'); if (toggle) { toggle.classList.toggle('voice-active', Boolean(voiceEngine?.running)); toggle.title = voiceEngine?.running ? 'إيقاف المحادثة الصوتية الحرة' : 'بدء المحادثة الصوتية الحرة'; }
}
async function handleLiveVoiceTranscript(text) {
  setVoiceState('processing');
  try {
    const result = await sendCommand(text, 'live-voice');
    if (voiceEngine?.running) voiceEngine.speak(result?.page ? result.message : (result?.response || result?.message || 'تم تنفيذ الأمر.'));
  } catch (error) { voiceEngine?.completeProcessing(); toast(apiFailure(error), 'error'); }
}
function installVoiceConversation() {
  voiceEngine = new VoiceEngine({onState: setVoiceState, onTranscript: handleLiveVoiceTranscript, onError: (message) => toast(message, 'error')});
  $('#voice-live-toggle').addEventListener('click', async () => {
    if (!state.authorized) return openModal('auth-overlay');
    if (voiceEngine.running) { voiceEngine.stop(); toast('تم إيقاف المحادثة الصوتية الحرة.'); return; }
    try { await voiceEngine.start(); toast('المحادثة الصوتية مفعلة؛ تحدث الآن.'); }
    catch (error) { setVoiceState('ready'); toast(error.message || 'تعذر تفعيل المحادثة الصوتية.', 'error'); }
  });
  $('#voice-mute').addEventListener('click', () => { voiceEngine.mute(); toast('تم كتم الرد الصوتي؛ سيستمر الاستماع.'); });
  setVoiceState('ready');
}
function commandValue() { return $('#command-input')?.value.trim() || ''; }
function setCommandMeta(id, text) { const node = $(`#${id}`); if (node) node.textContent = text; }
function executionDuration(report) { return report.duration_ms ? `${Math.max(1, Math.round(report.duration_ms / 1000))}s` : '—'; }
function renderExecutionReport(report) {
  const host = $('#execution-reports'); if (!host || !report) return;
  const tests = (report.tests || []).map((test) => `<li class="test-${esc(test.status)}"><b>${esc(test.name)}</b><span>${esc(test.status === 'PASS' ? 'PASS' : test.status === 'NOT_TESTED' ? 'لم يتم الاختبار' : test.status)}</span><small>${esc(test.detail || '')}</small></li>`).join('');
  const steps = (report.steps || []).map((step) => `<li><span class="step-status">${step.status === 'COMPLETED' ? '✓' : '…'}</span><div><b>${esc(step.label)}</b><small>${esc(step.description || '')}</small><time>${esc(step.finished_at || '')}</time></div></li>`).join('');
  const changes = (report.changes || []).map((change) => `<li><b>${esc(change.target)}</b> — ${esc(change.description)}</li>`).join('') || '<li>لا توجد تغييرات مسجلة.</li>';
  const snapshot = report.snapshot?.id ? `<div class="snapshot-line">Snapshot: <code>${esc(report.snapshot.id)}</code> · ${esc(report.snapshot.created_at)}</div><button type="button" class="button button-quiet report-restore" title="استعادة قاعدة SQLite من هذه النسخة">استعادة Snapshot</button>` : '<div class="snapshot-line">لم يتم إنشاء Snapshot لهذه العملية.</div>';
  const preview = report.preview_url || window.location.origin;
  const card = document.createElement('article'); card.className = `execution-report-card ${report.status === 'SUCCESS' ? 'success' : 'failed'}`;
  card.innerHTML = `<div class="execution-report-head"><div><span class="report-kicker">Execution ID: ${esc(report.id)}</span><h3>${report.status === 'SUCCESS' ? '🟢 التنفيذ مكتمل' : '🔴 فشل التنفيذ'} — ${esc(executionDuration(report))}</h3><p>${esc(report.command)}</p></div><button class="icon-button report-speak" type="button" title="قراءة التقرير صوتياً" aria-label="قراءة التقرير صوتياً">🔊</button></div><div class="report-meta"><span>المستخدم: ${esc(report.actor)}</span><span>بدأ: ${esc(report.started_at)}</span><span>انتهى: ${esc(report.finished_at || 'قيد التنفيذ')}</span></div><details open><summary>ما تم تنفيذه فعلياً</summary><ol class="execution-steps">${steps}</ol><ul class="execution-changes">${changes}</ul></details><details><summary>الاختبارات والنتائج الحقيقية</summary><ul class="execution-tests">${tests || '<li>لم يتم الاختبار.</li>'}</ul></details><details><summary>النسخ الاحتياطية</summary>${snapshot}</details><a class="button button-quiet report-preview-link" href="${esc(preview)}" target="_blank" rel="noopener">🔗 فتح المعاينة الفعلية</a>`;
  card.querySelector('.report-speak').addEventListener('click', () => voiceEngine?.speak(`تقرير التنفيذ: ${report.status === 'SUCCESS' ? 'نجح' : 'فشل'}. ${report.command}. ${report.steps?.map((step) => step.label).join('، ') || ''}`));
  card.querySelector('.report-restore')?.addEventListener('click', async () => { if (!window.confirm('استعادة Snapshot ستستبدل قاعدة SQLite الحالية. هل تريد المتابعة؟')) return; try { await api.restoreExecutionReport(report.id); toast('تمت استعادة Snapshot. أعد تحميل اللوحة للتحقق.'); } catch (error) { toast(apiFailure(error), 'error'); } });
  host.prepend(card);
}
function renderPendingExecution(command) {
  const host = $('#execution-reports'); if (!host) return null;
  const card = document.createElement('article'); card.className = 'execution-report-card running';
  card.innerHTML = `<div class="execution-report-head"><div><span class="report-kicker">Execution ID: قيد الإنشاء</span><h3>🟡 قيد التنفيذ</h3><p>${esc(command)}</p></div><span class="loader"></span></div><div class="live-report-steps">🟡 تحليل الأمر…<br>🔵 تحديد المكونات المتأثرة…<br>🔵 تشغيل التنفيذ والاختبارات…<br>🔵 حفظ التقرير وSnapshot…</div>`;
  host.prepend(card); return card;
}
async function sendCommand(command, source = 'text', audioBase64 = '', attachment = null) {
  if (!command && !audioBase64 && !attachment) return toast('اكتب أمراً أو أضف مرفقاً أولاً.', 'error');
  if (!state.authorized) return openModal('auth-overlay');
  const button = $('#command-send'); if (button) button.disabled = true;
  setCommandMeta('command-execution-state', 'جار تنفيذ الأمر…');
  const pendingCard = renderPendingExecution(command || 'مرفق صوتي أو وسائط');
  try {
    const body = {command, source};
    if (audioBase64) body.audio_base64 = audioBase64;
    if (attachment) Object.assign(body, {attachment_base64: attachment.data, attachment_name: attachment.name, attachment_type: attachment.type});
    const result = await api.sendCommand(body);
    pendingCard?.remove(); if (result.report) renderExecutionReport(result.report);
    $('#command-input').value = ''; inlineAttachment = null; setCommandMeta('command-attachment-name', 'لا توجد مرفقات');
    if (result.stages?.length) setCommandMeta('command-execution-state', result.stages.map((stage) => `${stage.status === 'COMPLETED' ? '✓' : '…'} ${stage.label}`).join(' · '));
    else setCommandMeta('command-execution-state', 'تم الاستلام');
    toast(result.page ? `${result.message} (#${result.page.slug})` : (result.message || 'تم استلام الأمر.'));
    return result;
  } catch (error) { if (pendingCard) { pendingCard.classList.add('failed'); pendingCard.querySelector('h3').textContent = '🔴 فشل التنفيذ'; } toast(apiFailure(error), 'error'); if (source === 'live-voice') throw error; }
  finally { if (button) button.disabled = false; }
}
function autosizeCommand() { const input = $('#command-input'); if (input) { input.style.height = 'auto'; input.style.height = `${Math.min(input.scrollHeight, 150)}px`; } }
function installCommandBar() {
  $('#command-send').addEventListener('click', () => sendCommand(commandValue(), 'text', '', inlineAttachment));
  $('#command-input').addEventListener('input', autosizeCommand);
  $('#command-input').addEventListener('keydown', (event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); sendCommand(commandValue(), 'text', '', inlineAttachment); } });
  $('#command-attach').addEventListener('click', () => $('#command-file').click());
  $('#command-file').addEventListener('change', () => {
    const file = $('#command-file').files?.[0]; if (!file) return;
    const reader = new FileReader(); reader.onload = () => { inlineAttachment = {name: file.name, type: file.type, data: reader.result}; setCommandMeta('command-attachment-name', `مرفق: ${file.name}`); }; reader.readAsDataURL(file);
  });
  $('#command-mic').addEventListener('click', () => {
    const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!Recognition) return toast('الإدخال الصوتي المباشر غير مدعوم؛ استخدم زر التسجيل الاحتياطي.', 'error');
    const recognition = new Recognition(); recognition.lang = 'ar-SA'; recognition.interimResults = true; recognition.continuous = false; let finalText = '';
    recognition.onstart = () => { $('#command-mic').classList.add('is-listening'); setCommandMeta('command-recording-state', 'يستمع بالعربية…'); };
    recognition.onresult = (event) => { finalText = [...event.results].map((result) => result[0].transcript).join(''); $('#command-input').value = finalText; autosizeCommand(); };
    recognition.onerror = () => toast('تعذر التعرف الصوتي؛ استخدم التسجيل الاحتياطي.', 'error');
    recognition.onend = () => { $('#command-mic').classList.remove('is-listening'); setCommandMeta('command-recording-state', 'جاهز'); if (finalText.trim()) sendCommand(finalText, 'stt'); };
    recognition.start();
  });
}
function installRecorder() {
  $('#command-record').addEventListener('click', async () => {
    if (recorder?.state === 'recording') { recorder.stop(); return; }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({audio: true});
      recorder = new MediaRecorder(stream); recordedChunks = [];
      recorder.ondataavailable = (event) => event.data.size && recordedChunks.push(event.data);
      recorder.onstop = () => { stream.getTracks().forEach((track) => track.stop()); $('#command-record').classList.remove('is-recording'); setCommandMeta('command-recording-state', 'تسجيل جاهز للإرسال'); const blob = new Blob(recordedChunks, {type: recorder.mimeType || 'audio/webm'}); const reader = new FileReader(); reader.onloadend = () => sendCommand('', 'audio-recorder', reader.result); reader.readAsDataURL(blob); };
      recorder.start(); $('#command-record').classList.add('is-recording'); setCommandMeta('command-recording-state', 'جار التسجيل… اضغط ● للإيقاف');
    } catch (error) { toast('تعذر الوصول إلى الميكروفون؛ تحقق من إذن المتصفح.', 'error'); }
  });
}

function responseText(card) {
  const clone = card.cloneNode(true);
  clone.querySelectorAll('.response-action-toolbar, .response-share-menu').forEach((node) => node.remove());
  return clone.innerText.trim();
}
function closeResponseMenus(except = null) {
  $$('.response-share-menu').forEach((menu) => { if (menu !== except) menu.remove(); });
}
function createResponseToolbar(card) {
  if (card.classList.contains('loading-state') || card.classList.contains('error-state') || card.querySelector('.response-action-toolbar')) return;
  card.classList.add('response-card');
  const toolbar = document.createElement('div'); toolbar.className = 'response-action-toolbar';
  toolbar.innerHTML = `<button type="button" data-response-action="copy" title="نسخ التقرير">📋</button><button type="button" data-response-action="share" title="مشاركة أو تصدير">📤</button><button type="button" data-response-action="speak" title="قراءة صوتية">🔊</button><span class="response-toolbar-divider"></span><button type="button" data-response-action="up" title="تقييم إيجابي" aria-label="تقييم إيجابي">👍</button><button type="button" data-response-action="down" title="تقييم سلبي" aria-label="تقييم سلبي">👎</button><button type="button" data-response-action="more" title="خيارات إضافية">⋮</button>`;
  card.append(toolbar);
}
function enhanceResponseToolbars() {
  $$('#page-content .panel').forEach(createResponseToolbar);
}
function showResponseShareMenu(card, button) {
  closeResponseMenus();
  const menu = document.createElement('div'); menu.className = 'response-share-menu';
  menu.innerHTML = '<button type="button" data-share-action="native">مشاركة…</button><button type="button" data-share-action="copy">نسخ النص</button><button type="button" data-share-action="export">تصدير TXT</button>';
  card.append(menu);
  menu.querySelector('[data-share-action="native"]').addEventListener('click', async () => { const text = responseText(card); if (navigator.share) { try { await navigator.share({title: 'AI Media OS', text}); } catch {} } else { await navigator.clipboard?.writeText(text); toast('تم نسخ التقرير للمشاركة.'); } closeResponseMenus(); });
  menu.querySelector('[data-share-action="copy"]').addEventListener('click', async () => { await navigator.clipboard?.writeText(responseText(card)); toast('تم نسخ التقرير.'); closeResponseMenus(); });
  menu.querySelector('[data-share-action="export"]').addEventListener('click', () => { const blob = new Blob([responseText(card)], {type: 'text/plain;charset=utf-8'}); const link = document.createElement('a'); link.href = URL.createObjectURL(blob); link.download = 'ai-media-report.txt'; link.click(); URL.revokeObjectURL(link.href); toast('تم تصدير التقرير كملف TXT.'); closeResponseMenus(); });
}
function installResponseActions() {
  document.addEventListener('click', async (event) => {
    const action = event.target.closest('[data-response-action]');
    if (!action) { if (!event.target.closest('.response-share-menu')) closeResponseMenus(); return; }
    const card = action.closest('.response-card'); if (!card) return;
    const value = responseText(card);
    if (action.dataset.responseAction === 'copy') { await navigator.clipboard?.writeText(value); toast('تم نسخ مخرجات البطاقة.'); }
    if (action.dataset.responseAction === 'share') showResponseShareMenu(card, action);
    if (action.dataset.responseAction === 'speak') { if (!('speechSynthesis' in window)) return toast('القراءة الصوتية غير مدعومة في هذا المتصفح.', 'error'); window.speechSynthesis.cancel(); const utterance = new SpeechSynthesisUtterance(value.slice(0, 6000)); utterance.lang = 'ar-SA'; window.speechSynthesis.speak(utterance); toast('بدأت القراءة الصوتية.'); }
    if (['up','down'].includes(action.dataset.responseAction)) { action.classList.toggle('selected'); toast(action.dataset.responseAction === 'up' ? 'تم تسجيل التقييم الإيجابي.' : 'تم تسجيل ملاحظة التقييم السلبي.'); }
    if (action.dataset.responseAction === 'more') { const input = $('#command-input'); if (input) { input.value = `أعد توليد هذا الرد:\n${value.slice(0, 1200)}`; autosizeCommand(); input.focus(); toast('تم تجهيز طلب إعادة التوليد في شريط المحادثة.'); } }
  });
}

async function modulePage(module) {
  if (isCompanyBuilderRoute(module.id)) return renderCompanyPage(module.id, state);
  if (['ai-team', 'characters', 'projects'].includes(module.id)) return entityPage(module.id);
  if (['ai-router', 'manus', 'github'].includes(module.id)) return integrationPage(module);
  if (module.id === 'external-integrations') return externalIntegrationsPage();
  if (module.id === 'security') return securityPage();
  if (module.id === 'settings') return settingsPage();
  const stateCode = module.state || 'NOT_CONFIGURED';
  const explanation = stateCode === 'COMING_SOON'
    ? 'هذه الوحدة مدرجة في خارطة المرحلة التالية، ولم يُبنَ لها سلوك تنفيذي في المرحلة الأولى.'
    : 'لم يُعثر على Backend أو قاعدة بيانات أو اعتماد موثق لهذه الوحدة. لم تُعرض بيانات افتراضية أو أزرار شكلية.';
  return `<section class="panel module-placeholder"><div class="placeholder-symbol">${esc(module.icon)}</div><div>${statusBadge(stateCode)}<h2>${esc(module.title)}</h2><p>${esc(explanation)}</p><p class="panel-caption">ستظهر الوحدة هنا عند تسجيلها مع API ومصدر بيانات حقيقي.</p></div></section>`;
}
function setHeader(page) {
  const routePage = isEmployeeRoute(page) ? 'ai-team' : page;
  const current = state.modules.find((item) => item.id === routePage);
  const title = isEmployeeRoute(page) ? 'ملف موظف الذكاء الاصطناعي' : (current?.title || 'لوحة التحكم');
  $('#breadcrumb-current').textContent = title;
  $('#page-title').textContent = title;
  $('#page-subtitle').textContent = page === 'dashboard' ? 'ما الذي يحدث داخل الشركة الآن؟ حالة الأنظمة والمهام والقرارات من مصادر موثوقة.' : (page === 'tasks' ? 'كل حالات التنفيذ والملكية والأولوية في مكان واحد.' : page === 'approvals' ? 'قرارات المالك محفوظة ومؤرخة ويمكن تدقيقها.' : page === 'activity' ? 'سجل أحداث فعلي قابل للبحث والتصفية.' : current?.state === 'NOT_CONFIGURED' ? 'الوحدة ظاهرة بحالتها الحقيقية ولا تعرض محتوى وهمياً.' : 'مركز تشغيل معياري قابل للتوسعة تدريجياً.');
  renderNavigation();
  const actions = $('#heading-actions');
  actions.innerHTML = state.authorized && page === 'tasks' ? '<button class="button button-primary" id="new-task-header">＋ مهمة جديدة</button>' : state.authorized && page === 'approvals' ? '<button class="button button-primary" id="new-approval-header">＋ طلب موافقة</button>' : '';
}
async function renderPage(page = state.page) {
  state.page = state.modules.some((item) => item.id === page) || isEmployeeRoute(page) ? page : 'dashboard';
  const revision = ++state.renderRevision;
  history.replaceState(null, '', `#${state.page}`);
  setHeader(state.page);
  pageContent.innerHTML = '<div class="panel loading-state"><span class="loader"></span><strong>جار تحميل بيانات الوحدة…</strong></div>';
  if ((['dashboard','tasks','approvals','activity','characters','projects'].includes(state.page) || isCompanyBuilderRoute(state.page)) && !state.authorized) {
    pageContent.innerHTML = accessPanel();
    return;
  }
  try {
    let markup;
    if (isCompanyBuilderRoute(state.page)) {
      markup = await renderCompanyPage(state.page, state);
    } else if (state.page === 'dashboard') {
      state.dashboard = await api.dashboard();
      markup = renderDashboard(state.dashboard);
    } else if (state.page === 'tasks') {
      markup = await renderTasksPage();
    } else if (state.page === 'approvals') {
      markup = await renderApprovalsPage();
    } else if (state.page === 'activity') {
      markup = await renderActivityPage();
    } else {
      const module = state.modules.find((item) => item.id === state.page);
      markup = await modulePage(module || {id: state.page, title: 'لوحة التحكم', state: 'NOT_CONFIGURED'});
    }
    if (revision !== state.renderRevision) return;
    pageContent.innerHTML = markup;
    enhanceResponseToolbars();
    bindPageEvents();
  } catch (error) {
    if (revision !== state.renderRevision) return;
    const message = apiFailure(error);
    if (!state.authorized && ['authentication_required','invalid_token','auth_not_configured'].includes(error.code)) {
      pageContent.innerHTML = accessPanel(message);
    } else {
      pageContent.innerHTML = `<div class="panel error-state"><strong>تعذّر تحميل الوحدة</strong><p>${esc(message)}</p><button class="button button-quiet" id="retry-page">إعادة المحاولة</button></div>`;
      $('#retry-page')?.addEventListener('click', () => renderPage(state.page));
    }
  }
  renderNavigation();
}
function bindPageEvents() {
  $('#new-task-button')?.addEventListener('click', () => openModal('task-overlay'));
  $('#new-task-header')?.addEventListener('click', () => openModal('task-overlay'));
  $('#new-approval-button')?.addEventListener('click', () => openModal('approval-overlay'));
  $('#new-approval-header')?.addEventListener('click', () => openModal('approval-overlay'));
  $('#task-status-filter')?.addEventListener('change', (event) => { state.taskStatus = event.target.value; renderPage('tasks'); });
  $('#approval-status-filter')?.addEventListener('change', (event) => { state.approvalStatus = event.target.value; renderPage('approvals'); });
  $('#activity-status-filter')?.addEventListener('change', (event) => { state.activityStatus = event.target.value; renderPage('activity'); });
  $$('.task-status-select').forEach((select) => select.addEventListener('change', async () => {
    select.disabled = true;
    try { await api.updateTask(select.dataset.taskId, {status: select.value}); toast('تم حفظ حالة المهمة في قاعدة البيانات.'); if (state.page === 'tasks') await renderPage('tasks'); else if (state.page === 'dashboard') await renderPage('dashboard'); }
    catch (error) { toast(apiFailure(error), 'error'); if (state.page === 'tasks') await renderPage('tasks'); }
  }));
  $$('[data-approval-decision]').forEach((button) => button.addEventListener('click', () => {
    const decision = button.dataset.approvalDecision;
    const id = button.dataset.approvalId;
    if (decision === 'REQUEST_CHANGES') {
      $('#decision-form').elements.approvalId.value = id;
      $('#decision-form').dataset.decision = decision;
      $('#decision-title').textContent = 'طلب تعديلات';
      openModal('decision-overlay');
    } else {
      decideApproval(id, decision, '');
    }
  }));
  $$('[data-open-auth]').forEach((button) => button.addEventListener('click', () => openModal('auth-overlay')));
  $('#logout-button')?.addEventListener('click', logout);
  $('#refresh-health')?.addEventListener('click', refreshHealth);
  $('#add-integration-button')?.addEventListener('click', () => openServiceModal());
  $$('[data-manage-service]').forEach((button) => button.addEventListener('click', () => openServiceModal(button.dataset.manageService)));
}
async function decideApproval(id, decision, note) {
  try {
    await api.decideApproval(id, {decision, note});
    closeModal('decision-overlay');
    toast(decision === 'APPROVE' ? 'تم حفظ الموافقة.' : decision === 'REJECT' ? 'تم حفظ الرفض.' : 'تم حفظ طلب التعديلات.');
    await refreshHealth();
    await renderPage(state.page);
  } catch (error) { showFormError('decision-error', apiFailure(error)); }
}
async function refreshHealth() {
  try { state.health = await api.health(); renderHealth(); updateAuthUI(); if (state.page === 'security') await renderPage('security'); }
  catch (error) { toast(apiFailure(error), 'error'); }
}
function logout() {
  api.clearToken();
  state.authorized = false;
  state.dashboard = null;
  updateAuthUI();
  toast('انتهت جلسة المالك.');
  renderPage('dashboard');
}
function formObject(form) { return Object.fromEntries(new FormData(form).entries()); }

$('#auth-button').addEventListener('click', () => state.authorized ? logout() : openModal('auth-overlay'));
$('#owner-profile').addEventListener('click', () => openModal('auth-overlay'));
$('#back-btn')?.addEventListener('click', () => {
  if (location.hash && location.hash !== '#dashboard' && window.history.length > 1) {
    window.history.back();
  } else {
    location.hash = '#dashboard';
  }
});
$('#sidebar-navigation').addEventListener('click', (event) => {
  const button = event.target.closest('[data-page]');
  if (!button) return;
  $('#sidebar').classList.remove('open'); $('#mobile-scrim').classList.remove('active');
  renderPage(button.dataset.page);
});
$('#page-content').addEventListener('click', async (event) => {
  const generationAction = event.target.closest('[data-generation-action]');
  if (generationAction) {
    const id = generationAction.dataset.generationId;
    const action = generationAction.dataset.generationAction;
    generationAction.disabled = true;
    try {
      if (action === 'poll') {
        const result = await api.pollMediaGeneration(id);
        toast(result.status === 'COMPLETED' ? 'اكتملت المهمة وحُفظ ملف الإنتاج.' : result.status === 'FAILED' ? (result.error_message || 'فشلت المهمة.') : 'ما زالت مهمة Kling قيد التنفيذ.');
        await renderPage(state.page);
      } else if (action === 'audio' || action === 'media') {
        const blob = await api.mediaBlob(id, action);
        const playerHost = generationAction.closest('.generation-row')?.querySelector('.generation-player');
        if (!playerHost) return;
        if (playerHost.dataset.objectUrl) URL.revokeObjectURL(playerHost.dataset.objectUrl);
        const objectUrl = URL.createObjectURL(blob);
        playerHost.dataset.objectUrl = objectUrl;
        playerHost.replaceChildren();
        const player = document.createElement(action === 'media' ? 'video' : 'audio');
        player.controls = true;
        player.preload = 'metadata';
        if (action === 'media') player.playsInline = true;
        player.src = objectUrl;
        player.className = 'generation-media-player';
        playerHost.append(player);
      }
    } catch (error) {
      toast(apiFailure(error), 'error');
      if (error.details?.paused_accounts?.length) await renderPage(state.page);
    } finally { generationAction.disabled = false; }
    return;
  }
  const integrationAction = event.target.closest('[data-integration-action]');
  if (integrationAction) {
    const action = integrationAction.dataset.integrationAction;
    if (action === 'more') {
      const current = state.integrationPage;
      if (!current || !current.pagination?.has_more) return;
      const revision = state.integrationRequestRevision;
      integrationAction.disabled = true;
      try {
        const next = await api.externalIntegrations({limit: 5, offset: current.accounts.length, q: current.search || '', issues: current.problems ? '1' : ''});
        if (state.integrationPage !== current || revision !== state.integrationRequestRevision) return;
        current.accounts.push(...(next.accounts || []));
        current.pagination = next.pagination;
        const results = $('#integration-account-results', pageContent);
        if (results) results.innerHTML = renderAccountResults(current);
      } catch (error) { toast(apiFailure(error), 'error'); }
      finally { integrationAction.disabled = false; }
      return;
    }
    if (action === 'delete' && !window.confirm('سيُحذف سجل الحساب ومفتاحه المشفر. هل تريد المتابعة؟')) return;
    integrationAction.disabled = true;
    try {
      if (action === 'rotate') {
        const result = await api.rotateExternalAccount({provider: integrationAction.dataset.provider, service: integrationAction.dataset.service});
        toast(`اختير الحساب التالي: ${result.account.label} · ${result.account.provider}. لم يُرسل طلب توليد.`);
      } else if (action === 'test') {
        const result = await api.testExternalAccount(integrationAction.dataset.accountId);
        toast(`${label(result.connection.status)} — ${result.connection.message}`);
      } else if (action === 'toggle') {
        await api.updateExternalAccount(integrationAction.dataset.accountId, {status: integrationAction.dataset.status});
        toast(integrationAction.dataset.status === 'ACTIVE' ? 'تم تفعيل الحساب.' : 'تم إيقاف الحساب.');
      } else if (action === 'delete') {
        await api.deleteExternalAccount(integrationAction.dataset.accountId);
        toast('حُذف الحساب ومفتاحه المشفر.');
      }
      await renderPage(state.page);
    } catch (error) { toast(apiFailure(error), 'error'); }
    finally { integrationAction.disabled = false; }
    return;
  }
  const companyAction = await handleCompanyClick(event, state, renderPage, toast);
  if (companyAction) return;
  const button = event.target.closest('[data-page]');
  if (button) renderPage(button.dataset.page);
  if (event.target.closest('[data-open-auth]')) openModal('auth-overlay');
});
$('#page-content').addEventListener('input', (event) => {
  const search = event.target.closest('[data-account-search]');
  if (!search) return;
  state.integrationSearch = search.value;
  window.clearTimeout(state.integrationSearchTimer);
  state.integrationSearchTimer = window.setTimeout(() => refreshIntegrationAccountList(), 180);
});
$('#page-content').addEventListener('change', (event) => {
  const issues = event.target.closest('[data-account-issues]');
  if (issues) {
    state.integrationProblemsOnly = issues.checked;
    refreshIntegrationAccountList();
    return;
  }
  const provider = event.target.closest('[data-provider-choice]');
  if (!provider) return;
  const form = provider.closest('form');
  const service = provider.value === 'Kling' ? 'VIDEO' : 'AUDIO';
  form.querySelector('[name="service"]').value = service;
  form.querySelector('[data-provider-service-label]').textContent = service === 'VIDEO' ? 'فيديو' : 'صوت';
});
$('#page-content').addEventListener('submit', async (event) => {
  const generationForm = event.target.closest('[data-generation-form]');
  if (generationForm) {
    event.preventDefault();
    const values = formObject(generationForm);
    const confirmation = `سيُرسل النص التالي إلى ElevenLabs لتوليد الصوت، ثم يُرسل وصف المشهد إلى Kling لتوليد الفيديو. قد يستهلك ذلك رصيداً من الحسابين.\n\nالنص الصوتي:\n${values.script_text}\n\nوصف الفيديو:\n${values.visual_prompt}\n\nالمدة: ${values.duration} ثوانٍ · الدقة: ${values.resolution} · النسبة: ${values.aspect_ratio}\n\nهل تريد بدء التوليد الآن؟`;
    if (!window.confirm(confirmation)) return;
    const button = generationForm.querySelector('button[type="submit"]');
    if (button) button.disabled = true;
    try {
      const result = await api.executeMediaPipeline(values);
      const paused = result.generation?.paused_accounts || [];
      const pausedLabels = paused.map((item) => `${item.label} (${label(item.reason)})`).join('، ');
      toast(paused.length ? `بدأ الإنتاج بعد إيقاف مؤقت: ${pausedLabels}.` : 'بدأ توليد الصوت والفيديو؛ يمكنك فحص حالة Kling من سجل الإنتاج.');
      generationForm.reset();
      await renderPage(state.page);
    } catch (error) {
      const paused = error.details?.paused_accounts || [];
      if (paused.length) toast(`${apiFailure(error)} الحسابات الموقوفة: ${paused.map((item) => `${item.label} (${label(item.reason)})`).join('، ')}`, 'error');
      else toast(apiFailure(error), 'error');
      if (error.details?.paused_accounts?.length || error.details?.generation_id) await renderPage(state.page);
    } finally { if (button) button.disabled = false; }
    return;
  }
  const form = event.target.closest('[data-integration-form]');
  if (!form) { handleCompanySubmit(event, state, renderPage, toast); return; }
  event.preventDefault();
  const button = form.querySelector('button[type="submit"]');
  const secretFields = [...form.querySelectorAll('input[type="password"]')];
  if (button) button.disabled = true;
  try {
    const values = formObject(form);
    if (form.dataset.integrationForm === 'create') {
      await api.createExternalAccount(values);
      toast('أُضيف الحساب وخُزّن مفتاحه مشفراً.');
    } else {
      await api.updateExternalAccount(form.dataset.accountId, {credential: values.credential});
      toast('استُبدل مفتاح الحساب؛ لن يُعرض المفتاح السابق أو الجديد.');
    }
    form.reset();
    await renderPage(state.page);
  } catch (error) { toast(apiFailure(error), 'error'); }
  finally {
    secretFields.forEach((field) => { field.value = ''; });
    if (button) button.disabled = false;
  }
});
$('#service-integration-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const form = event.currentTarget; const button = event.submitter; if (button) button.disabled = true;
  try { await api.saveServiceIntegration(formObject(form)); toast('تم حفظ التكامل اليدوي مشفراً.'); closeModal('service-integration-overlay'); form.reset(); await loadServiceIntegrations(); if (state.page === 'settings') await renderPage('settings'); }
  catch (error) { showFormError('service-integration-error', apiFailure(error)); }
  finally { if (button) button.disabled = false; }
});
$('#forgot-password-toggle').addEventListener('click', () => { $('#auth-form').hidden = true; $('#recovery-form').hidden = false; });
$('#back-to-login').addEventListener('click', () => { $('#recovery-form').hidden = true; $('#auth-form').hidden = false; showFormError('recovery-error'); });
$('#recovery-form').addEventListener('submit', async (event) => {
  event.preventDefault(); showFormError('recovery-error');
  const form = event.currentTarget; const button = event.submitter; if (button) button.disabled = true;
  try { const values = formObject(form); await api.resetOwnerPassword(values); api.setToken(values.new_password); form.reset(); $('#recovery-form').hidden = true; $('#auth-form').hidden = false; closeModal('auth-overlay'); state.authorized = true; updateAuthUI(); toast('تمت استعادة رمز المالك وحفظه على الخادم.'); await renderPage(state.page); }
  catch (error) { showFormError('recovery-error', apiFailure(error)); }
  finally { if (button) button.disabled = false; }
});
$('#auth-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  showFormError('auth-error');
  api.setToken($('#owner-token-input').value);
  try {
    state.dashboard = await api.dashboard();
    state.authorized = true;
    await loadServiceIntegrations();
    updateAuthUI();
    closeModal('auth-overlay');
    $('#owner-token-input').value = '';
    toast('تم التحقق من صلاحية المالك.');
    await renderPage(state.page);
  } catch (error) {
    api.clearToken();
    state.authorized = false;
    updateAuthUI();
    showFormError('auth-error', apiFailure(error));
  }
});
$('#clear-token-button').addEventListener('click', () => { api.clearToken(); state.authorized = false; updateAuthUI(); $('#owner-token-input').value = ''; showFormError('auth-error'); toast('تم مسح رمز الجلسة.'); });
document.addEventListener('submit', async (event) => {
  if (event.target.id !== 'owner-password-form') return;
  event.preventDefault();
  showFormError('owner-password-error');
  const form = event.target;
  const button = event.submitter;
  if (button) button.disabled = true;
  try {
    const newPassword = form.elements.new_password.value;
    const confirmPassword = form.elements.confirm_password.value;
    if (newPassword !== confirmPassword) throw new Error('تأكيد كلمة السر الجديدة غير مطابق.');
    await api.changeOwnerPassword(formObject(form));
    api.setToken(newPassword);
    form.reset();
    toast('تم تغيير رمز المالك بنجاح.');
  } catch (error) {
    showFormError('owner-password-error', apiFailure(error));
  } finally {
    if (button) button.disabled = false;
  }
});
$('#task-form').addEventListener('submit', async (event) => {
  event.preventDefault(); showFormError('task-error');
  const form = event.currentTarget;
  const payload = formObject(form);
  const button = event.submitter; if (button) button.disabled = true;
  try {
    await api.createTask(payload);
    closeModal('task-overlay'); form.reset();
    toast('حُفظت المهمة وأضيفت إلى سجل النشاط.'); await renderPage(state.page);
  } catch (error) { showFormError('task-error', apiFailure(error)); }
  finally { if (button) button.disabled = false; }
});
$('#approval-form').addEventListener('submit', async (event) => {
  event.preventDefault(); showFormError('approval-error');
  const form = event.currentTarget;
  try {
    await api.createApproval(formObject(form));
    closeModal('approval-overlay'); form.reset();
    toast('أُضيف طلب الموافقة إلى قاعدة البيانات.'); await renderPage(state.page);
  } catch (error) { showFormError('approval-error', apiFailure(error)); }
});
$('#decision-form').addEventListener('submit', async (event) => {
  event.preventDefault(); showFormError('decision-error');
  const form = event.currentTarget;
  const values = formObject(form);
  const decision = form.dataset.decision;
  await decideApproval(values.approvalId, decision, values.note || '');
  form.reset();
});
$$('[data-close]').forEach((button) => button.addEventListener('click', () => closeModal(button.dataset.close)));
$$('.overlay').forEach((overlay) => overlay.addEventListener('click', (event) => { if (event.target === overlay) closeModal(overlay.id); }));
document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape') $$('.overlay:not([hidden])').forEach((modal) => closeModal(modal.id));
  if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') { event.preventDefault(); $('#global-search').focus(); }
});
$('#global-search').addEventListener('input', () => {
  clearTimeout(state.searchTimer);
  state.searchTimer = setTimeout(() => {
    state.search = $('#global-search').value.trim();
    if (['tasks','approvals','activity','ai-team','departments'].includes(state.page) && state.authorized) renderPage(state.page);
  }, 250);
});
$('#mobile-menu').addEventListener('click', () => { $('#sidebar').classList.toggle('open'); $('#mobile-scrim').classList.toggle('active', $('#sidebar').classList.contains('open')); });
$('#mobile-scrim').addEventListener('click', () => { $('#sidebar').classList.remove('open'); $('#mobile-scrim').classList.remove('active'); });

installCommandBar();
installRecorder();
installVoiceConversation();
installResponseActions();

async function boot() {
  updateAuthUI();
  try {
    const [modules, health] = await Promise.all([api.modules(), api.health()]);
    state.modules = modules.modules;
    state.builder = modules.builder_capabilities;
    state.health = health;
    renderNavigation(); renderHealth(); updateAuthUI();
  } catch (error) {
    $('#global-message').hidden = false;
    $('#global-message').textContent = `تعذّر الوصول إلى API: ${apiFailure(error)}`;
  }
  if (api.hasToken) {
    try { state.dashboard = await api.dashboard(); state.authorized = true; await loadServiceIntegrations(); const reports = (await api.executionReports()).reports || []; reports.slice(0, 5).reverse().forEach(renderExecutionReport); }
    catch (error) { api.clearToken(); state.authorized = false; if (error.code !== 'auth_not_configured') toast(apiFailure(error), 'error'); }
  }
  updateAuthUI();
  await renderPage(state.page);
  setInterval(async () => {
    try { state.health = await api.health(); renderHealth(); updateAuthUI(); }
    catch { /* A failed scheduled refresh is visible through the next explicit request. */ }
  }, 30000);
}

boot();


function installPasswordToggles() {
  const sensitiveSelector = 'input[type="password"], input[data-secret], input[name*="password" i], input[name*="token" i], input[name*="secret" i], input[name*="credential" i], input[name*="api_key" i]';
  const showIcon = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12Z"></path><circle cx="12" cy="12" r="3"></circle></svg>';
  const hideIcon = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 3l18 18M10.6 10.6a2 2 0 0 0 2.8 2.8"></path><path d="M9.9 5.2A11 11 0 0 1 12 5c6.4 0 10 7 10 7a16 16 0 0 1-3 3.7M6.2 6.2C3.5 8 2 12 2 12s3.6 7 10 7c1.3 0 2.4-.3 3.4-.8"></path></svg>';
  const enhance = (input) => {
    if (!(input instanceof HTMLInputElement) || input.dataset.passwordToggleAttached) return;
    input.dataset.passwordToggleAttached = 'true';
    if (input.type !== 'password') input.type = 'password';
    const wrapper = document.createElement('span');
    wrapper.className = 'password-input-wrap';
    input.before(wrapper);
    wrapper.append(input);
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'password-visibility-toggle';
    button.setAttribute('aria-label', 'إظهار كلمة المرور');
    button.setAttribute('aria-pressed', 'false');
    button.title = 'إظهار كلمة المرور';
    button.innerHTML = showIcon;
    button.addEventListener('click', () => {
      const reveal = input.type === 'password';
      input.type = reveal ? 'text' : 'password';
      button.setAttribute('aria-pressed', String(reveal));
      button.setAttribute('aria-label', reveal ? 'إخفاء كلمة المرور' : 'إظهار كلمة المرور');
      button.title = reveal ? 'إخفاء كلمة المرور' : 'إظهار كلمة المرور';
      button.innerHTML = reveal ? hideIcon : showIcon;
    });
    wrapper.append(button);
  };
  const scan = (root) => {
    if (root instanceof HTMLInputElement && root.matches(sensitiveSelector)) enhance(root);
    root.querySelectorAll?.(sensitiveSelector).forEach(enhance);
  };
  const start = () => {
    scan(document);
    const observer = new MutationObserver((mutations) => {
      mutations.forEach((mutation) => mutation.addedNodes.forEach((node) => {
        if (node instanceof Element) scan(node);
      }));
    });
    observer.observe(document.body, { childList: true, subtree: true });
  };
  if (document.body) start();
  else document.addEventListener('DOMContentLoaded', start, { once: true });
}

installPasswordToggles();
