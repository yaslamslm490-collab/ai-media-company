import { useCallback, useEffect, useState } from 'react';

export type HealthPayload = {
  overall: string;
  checks: Record<string, string | Record<string, string>>;
  checked_at?: string;
};

export async function getHealth(): Promise<HealthPayload> {
  const response = await fetch('/api/health', { credentials: 'same-origin' });
  if (!response.ok) throw new Error(`health_${response.status}`);
  return response.json();
}

export async function getSession(): Promise<boolean> {
  const response = await fetch('/api/auth/session', { credentials: 'same-origin' });
  if (!response.ok) return false;
  const body = await response.json();
  return Boolean(body.authenticated);
}

export async function loginOwner(token: string): Promise<void> {
  const response = await fetch('/api/auth/login', {
    method: 'POST',
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token }),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body?.error?.message || 'تعذر تسجيل الدخول.');
  }
}

export async function logoutOwner(): Promise<void> {
  await fetch('/api/auth/logout', {
    method: 'POST',
    credentials: 'same-origin',
    headers: { Origin: window.location.origin },
  });
}

export async function sendNadCommand(command: string): Promise<{ response: string; message: string; status: string }> {
  const response = await fetch('/api/commands', {
    method: 'POST',
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json', Origin: window.location.origin },
    body: JSON.stringify({ command, source: 'react-assistant' }),
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body?.error?.message || 'تعذر إرسال الأمر إلى الخادم.');
  return body;
}

export function useBackendStatus() {
  const [health, setHealth] = useState<HealthPayload | null>(null);
  const [authenticated, setAuthenticated] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const [healthPayload, session] = await Promise.all([getHealth(), getSession()]);
      setHealth(healthPayload);
      setAuthenticated(session);
      setError('');
    } catch {
      setError('الخادم غير متاح حالياً.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return { health, authenticated, setAuthenticated, loading, error, refresh };
}

export function BackendStatusBar({ health, authenticated, loading, error }: {
  health: HealthPayload | null;
  authenticated: boolean;
  loading: boolean;
  error: string;
}) {
  const text = (value: string | Record<string, string> | undefined, fallback: string) => typeof value === 'string' ? value : fallback;
  const backend = text(health?.checks?.backend, 'غير متاح');
  const database = text(health?.checks?.database, 'غير متاح');
  const aiRouter = text(health?.checks?.ai_router, 'غير مهيأ');
  const gemini = text(health?.checks?.gemini, 'غير مهيأ');
  return (
    <div className="mx-4 mt-3 sm:mx-6 lg:mx-8 rounded-2xl border border-default bg-card/80 px-3 py-2 text-[11px] text-secondary flex flex-wrap items-center gap-x-4 gap-y-2">
      <span className="font-bold text-primary">الحالة الفعلية</span>
      <span className="flex items-center gap-1.5"><i className={`status-dot ${backend === 'ONLINE' ? 'status-active' : 'status-error'}`} />Backend: {loading ? 'جار الفحص' : backend}</span>
      <span>SQLite: {database}</span>
      <span>AI Router: {aiRouter}</span>
      <span>Gemini: {gemini}</span>
      <span className={authenticated ? 'text-accent' : 'text-warning'}>{authenticated ? 'جلسة المالك موثقة' : 'تصفح عام — يلزم دخول للبيانات الخاصة'}</span>
      {error && <span className="text-error">{error}</span>}
    </div>
  );
}

export function OwnerAuthDialog({ onAuthenticated, onClose }: { onAuthenticated: () => void; onClose: () => void }) {
  const [token, setToken] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const submit = async () => {
    if (!token.trim()) return;
    setBusy(true);
    setError('');
    try {
      await loginOwner(token.trim());
      onAuthenticated();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'تعذر تسجيل الدخول.');
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="fixed inset-0 z-[70] bg-black/70 backdrop-blur-sm flex items-center justify-center p-4" dir="rtl">
      <div className="card max-w-md w-full p-5 space-y-4 shadow-2xl">
        <div className="flex items-center justify-between"><div><h2 className="font-display font-bold text-lg text-primary">دخول المالك</h2><p className="text-xs text-muted mt-1">يُرسل الرمز إلى الخادم فقط ولا يُحفظ في الواجهة.</p></div><button onClick={onClose} className="text-muted hover:text-primary">×</button></div>
        <label className="block text-xs font-bold text-secondary">رمز أو كلمة مرور المالك<input autoFocus type="password" value={token} onChange={(event) => setToken(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter') void submit(); }} placeholder="أدخل الرمز المضبوط على الخادم" className="mt-2 w-full rounded-xl bg-elevated border border-default px-3 py-3 text-sm text-primary outline-none focus:border-accent" /></label>
        {error && <p className="rounded-xl bg-red-500/10 border border-red-500/30 px-3 py-2 text-xs text-error">{error}</p>}
        <button onClick={() => void submit()} disabled={busy || !token.trim()} className="w-full rounded-xl bg-accent px-4 py-3 text-sm font-bold text-white disabled:opacity-40">{busy ? 'جار التحقق…' : 'التحقق والدخول'}</button>
      </div>
    </div>
  );
}
