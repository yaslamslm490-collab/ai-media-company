import {formatDate, label, statusClass} from './status.js';

const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[char]));
const statusBadge = (value) => `<span class="status-pill ${statusClass(value)}">${esc(label(value))}</span>`;
const servicesText = (services) => (services || []).map((service) => service === 'VIDEO' ? 'فيديو' : 'صوت').join(' + ');
const regionLabels = {UN: ['🌐', 'غير محدد'], US: ['🇺🇸', 'أمريكا'], EU: ['🇪🇺', 'أوروبا'], TR: ['🇹🇷', 'تركيا'], RU: ['🇷🇺', 'روسيا'], EG: ['🇪🇬', 'مصر']};

function accountCard(account, query = '') {
  const code = account.account_code || '—';
  const [flag, regionName] = regionLabels[account.region_code] || regionLabels.UN;
  const providerMark = account.provider?.toLocaleUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 2) || 'AC';
  const showDetails = query.startsWith('#');
  const details = `<details class="integration-account-details" ${showDetails ? 'open' : ''}>
    <summary>تفاصيل الإدارة</summary>
    <dl class="integration-account-facts">
      <div><dt>الاسم التعريفي</dt><dd>${esc(account.label)}</dd></div>
      <div><dt>منطقة الوجهة</dt><dd>${flag} ${esc(regionName)}</dd></div>
      <div><dt>معرّف داخلي</dt><dd><code>${esc(account.id)}</code></dd></div>
      <div><dt>حالة الاتصال</dt><dd>${statusBadge(account.connection_status || 'NOT_CHECKED')}</dd></div>
      <div><dt>آخر رسالة</dt><dd>${esc(account.connection_message || '—')}</dd></div>
      <div><dt>آخر فحص</dt><dd>${esc(account.last_checked_at ? formatDate(account.last_checked_at) : 'لم يُفحص')}</dd></div>
      <div><dt>التدوير</dt><dd>فيديو: ${Number(account.rotation_count?.VIDEO || 0)} · صوت: ${Number(account.rotation_count?.AUDIO || 0)}</dd></div>
    </dl>
    ${account.pause_reason ? `<p class="integration-problem-note">${esc(label(account.pause_reason))}${account.pause_until ? ` · حتى ${esc(formatDate(account.pause_until))}` : ''}</p>` : ''}
    <form class="credential-rotation-form" data-integration-form="credential" data-account-id="${esc(account.id)}">
      <label class="field-group integration-secret-field"><span class="field-label">استبدال مفتاح API</span><input type="password" name="credential" minlength="8" maxlength="8192" autocomplete="new-password" aria-label="مفتاح جديد للحساب ${esc(code)}" placeholder="مفتاح جديد؛ لا يُعرض المفتاح المحفوظ" required></label>
      <button class="button button-quiet small-button" type="submit">حفظ المفتاح الجديد</button>
    </form>
    <div class="integration-row-actions">
      <button class="button button-quiet small-button" type="button" data-integration-action="test" data-account-id="${esc(account.id)}">فحص الاتصال</button>
      <button class="button button-quiet small-button" type="button" data-integration-action="toggle" data-account-id="${esc(account.id)}" data-status="${account.status === 'ACTIVE' ? 'PAUSED' : 'ACTIVE'}">${account.status === 'ACTIVE' ? 'إيقاف' : 'تفعيل'}</button>
      <button class="button button-quiet small-button danger-button" type="button" data-integration-action="delete" data-account-id="${esc(account.id)}">حذف الحساب</button>
    </div>
  </details>`;
  return `<article class="integration-account-card">
    <div class="integration-account-card-top">
      <div class="integration-account-identity"><div class="integration-account-mark"><span class="integration-account-icon" aria-hidden="true">${esc(providerMark)}</span><code class="integration-account-code">${esc(code)}</code><span class="integration-account-flag" title="${esc(regionName)}" aria-label="${esc(regionName)}">${flag}</span></div><div class="integration-account-type">${esc(account.provider)} · ${esc(servicesText(account.services))} · ${esc(regionName)}</div></div>
      ${statusBadge(account.status)}
    </div>
    <div class="integration-account-card-foot"><span>الحساب مقنّع · ${account.secret_configured ? 'مفتاح محفوظ مشفّراً' : 'لا يوجد مفتاح محفوظ'}</span>${details}</div>
  </article>`;
}

export function renderAccountResults(page) {
  const accounts = page.accounts || [];
  const pagination = page.pagination || {total: accounts.length, has_more: false};
  if (!accounts.length) {
    const title = page.search || page.problems ? 'لا توجد حسابات مطابقة' : 'لا توجد حسابات محفوظة';
    const detail = page.problems ? 'لا توجد حسابات متوقفة أو ذات اتصال غير سليم.' : page.search ? 'تحقق من رمز الحساب أو امسح البحث.' : 'أضف حساباً مصرحاً به لبدء إدارة المجموعة.';
    return `<div class="integration-account-results-meta">0 من ${Number(pagination.total || 0)} نتيجة</div><div class="empty-state"><strong>${esc(title)}</strong>${esc(detail)}</div>`;
  }
  const count = accounts.length;
  return `<div class="integration-account-results-meta">عرض ${count} من ${Number(pagination.total || 0)} حساب مطابق</div>
    <div class="integration-account-grid">${accounts.map((account) => accountCard(account, page.search || '')).join('')}</div>
    ${pagination.has_more ? `<div class="integration-load-more-wrap"><button class="button button-quiet" type="button" data-integration-action="more">عرض المزيد · ${Math.min(Number(pagination.limit || 5), Number(pagination.total || 0) - count)} إضافية</button></div>` : ''}`;
}

export function renderAccountSearch(search = '', problems = false) {
  return `<div class="integration-account-search">
    <label class="integration-search-field"><span aria-hidden="true">⌕</span><input type="search" data-account-search value="${esc(search)}" maxlength="120" placeholder="ابحث برمز مثل #KL-001 أو اسم الحساب" autocomplete="off" aria-label="البحث برمز الحساب أو اسمه"></label>
    <label class="integration-problems-filter"><input type="checkbox" data-account-issues ${problems ? 'checked' : ''}><span>المشكلات والأخطاء فقط</span></label>
  </div>`;
}
