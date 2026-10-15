const STORAGE_KEY = 'nada-runtime-settings-v1';
const DEFAULT_LOCAL_ORIGIN = 'http://127.0.0.1:8080';

const runtime = {
  active: 'cloud',
  cloudOrigin: window.location.origin,
  localOrigin: DEFAULT_LOCAL_ORIGIN,
  health: { cloud: null, local: null },
};

function readSettings() {
  try {
    const saved = JSON.parse(window.localStorage.getItem(STORAGE_KEY) || '{}');
    if (typeof saved.localOrigin === 'string' && saved.localOrigin.trim()) runtime.localOrigin = saved.localOrigin.trim();
    if (saved.active === 'cloud' || saved.active === 'local') runtime.active = saved.active;
  } catch { /* local settings are optional and never contain secrets */ }
}
function saveSettings() {
  try { window.localStorage.setItem(STORAGE_KEY, JSON.stringify({active: runtime.active, localOrigin: runtime.localOrigin})); } catch { /* storage can be unavailable in private mode */ }
}
function originFor(mode) { return mode === 'local' ? runtime.localOrigin : runtime.cloudOrigin; }
function apiRootFor(mode) { return `${originFor(mode).replace(/\/$/, '')}/api`; }
function healthUrl(mode) { return `${apiRootFor(mode)}/health`; }
function statusText(result) {
  if (!result) return 'لم يُفحص بعد';
  if (result.ok) return `متصل · ${result.overall || 'ONLINE'}`;
  return result.reason || 'غير متاح';
}
async function probe(mode) {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), 7000);
  try {
    const response = await fetch(healthUrl(mode), {method: 'GET', headers: {Accept: 'application/json'}, cache: 'no-store', credentials: originFor(mode) === window.location.origin ? 'same-origin' : 'omit', signal: controller.signal});
    const payload = await response.json().catch(() => ({}));
    const ok = response.ok && payload?.checks?.backend === 'ONLINE';
    runtime.health[mode] = {ok, overall: payload.overall, payload, reason: ok ? '' : `استجاب الخادم بحالة ${payload.overall || response.status}`};
  } catch (error) {
    runtime.health[mode] = {ok: false, reason: error.name === 'AbortError' ? 'انتهت مهلة الفحص' : 'لا يوجد خادم مستجيب على هذا العنوان'};
  } finally { window.clearTimeout(timer); }
  return runtime.health[mode];
}
function render() {
  const host = document.querySelector('#runtime-mode-panel');
  if (!host) return;
  const cloud = runtime.health.cloud;
  const local = runtime.health.local;
  const activeOrigin = originFor(runtime.active);
  const localUnavailable = !local?.ok;
  const activeLabel = runtime.active === 'local' ? 'محلي نشط' : runtime.active === 'cloud' ? 'سحابي نشط' : 'لا يوجد وضع نشط';
  host.innerHTML = `
    <section class="runtime-panel panel" aria-labelledby="runtime-mode-title">
      <div class="panel-heading runtime-panel-heading">
        <div><span class="eyebrow">تشغيل NADA</span><h2 class="panel-title" id="runtime-mode-title">الوضع النشط والاتصال</h2><p class="panel-caption">الـPWA ليست خادماً محلياً؛ الوضع المحلي يعمل فقط إذا كان خادم NADA يعمل فعلياً على الهاتف أو جهاز داخل الشبكة.</p></div>
        <span class="status-pill ${runtime.active === 'cloud' ? 'production' : runtime.active === 'local' ? 'scheduled' : 'draft'}">${activeLabel}</span>
      </div>
      <div class="runtime-cards">
        <article class="runtime-card ${runtime.active === 'cloud' ? 'active' : ''}"><div><strong>الوضع السحابي</strong><small>${cloud ? statusText(cloud) : 'اضغط فحص السحابي'}</small></div><span class="runtime-dot ${cloud?.ok ? 'online' : cloud ? 'offline' : 'unknown'}"></span><button class="button button-quiet small-button" type="button" data-runtime-probe="cloud">فحص السحابي</button><button class="button button-primary small-button" type="button" data-runtime-activate="cloud" ${cloud?.ok ? '' : 'disabled'}>تشغيل السحابي</button><button class="button button-quiet small-button" type="button" data-runtime-stop="cloud" ${runtime.active === 'cloud' ? '' : 'disabled'}>إيقاف استخدامه</button></article>
        <article class="runtime-card ${runtime.active === 'local' ? 'active' : ''}"><div><strong>الوضع المحلي</strong><small>${local ? statusText(local) : 'اضغط فحص المحلي'}</small></div><span class="runtime-dot ${local?.ok ? 'online' : local ? 'offline' : 'unknown'}"></span><button class="button button-quiet small-button" type="button" data-runtime-probe="local">فحص المحلي</button><button class="button button-primary small-button" type="button" data-runtime-activate="local" ${local?.ok ? '' : 'disabled'}>تشغيل المحلي</button><button class="button button-quiet small-button" type="button" data-runtime-stop="local" ${runtime.active === 'local' ? '' : 'disabled'}>إيقاف استخدامه</button></article>
      </div>
      <div class="runtime-controls"><label class="field-group"><span class="field-label">عنوان الخادم المحلي</span><input class="text-field" id="runtime-local-origin" inputmode="url" value="${runtime.localOrigin.replace(/&/g, '&amp;').replace(/\"/g, '&quot;')}" placeholder="http://127.0.0.1:8080" /></label><button class="button button-quiet small-button" type="button" data-runtime-save>حفظ العنوان وفحصه</button></div>
      <div class="runtime-capabilities"><strong>عند توقف السحابي:</strong> يمكن استخدام الواجهة المحلية المدعومة فقط بعد نجاح فحص خادم محلي فعلي. لا تُرسل مفاتيح Gemini إلى الهاتف؛ Gemini يعمل من خادم مؤمّن فقط. ${localUnavailable ? 'حالياً لا يوجد خادم محلي مثبت أو مستجيب.' : `الخادم المحلي مستجيب على ${activeOrigin}.`}</div>
    </section>`;
  host.querySelectorAll('[data-runtime-probe]').forEach((button) => button.addEventListener('click', async () => { button.disabled = true; await probe(button.dataset.runtimeProbe); render(); }));
  host.querySelectorAll('[data-runtime-activate]').forEach((button) => button.addEventListener('click', () => {
    const mode = button.dataset.runtimeActivate;
    if (!runtime.health[mode]?.ok) return;
    runtime.active = mode; saveSettings(); window.dispatchEvent(new CustomEvent('nada-runtime-changed', {detail: {mode, apiRoot: apiRootFor(mode)}})); render();
  }));
  host.querySelectorAll('[data-runtime-stop]').forEach((button) => button.addEventListener('click', () => {
    const mode = button.dataset.runtimeStop;
    if (runtime.active !== mode) return;
    runtime.active = runtime.health.cloud?.ok && mode !== 'cloud' ? 'cloud' : 'none';
    saveSettings();
    window.dispatchEvent(new CustomEvent('nada-runtime-changed', {detail: {mode: runtime.active, apiRoot: apiRootFor(runtime.active)}}));
    render();
  }));
  host.querySelector('[data-runtime-save]')?.addEventListener('click', async () => {
    const value = host.querySelector('#runtime-local-origin')?.value.trim();
    if (value) runtime.localOrigin = value.replace(/\/$/, '');
    saveSettings(); await probe('local'); render();
  });
}
export function initRuntimeModes({onChange} = {}) {
  readSettings();
  window.addEventListener('nada-runtime-changed', (event) => onChange?.(event.detail));
  render();
  void Promise.all([probe('cloud'), probe('local')]).then(render);
  return {get active() { return runtime.active; }, apiRootFor};
}
export function getRuntimeApiRoot(mode = runtime.active) { return apiRootFor(mode); }
