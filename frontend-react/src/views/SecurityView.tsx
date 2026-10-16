import { useState } from 'react';
import { useApp } from '@/context/AppContext';
import type { UserRole } from '@/types';
import {
  Key,
  Download,
  Upload,
  RotateCcw,
  UserCheck,
  Activity,
} from 'lucide-react';

export function SecurityView() {
  const {
    currentRole,
    currentUser,
    switchRole,
    integrations,
    pingIntegration,
    exportStateToJson,
    importStateFromJson,
    resetToBlueprintDefaults,
    auditLogs,
  } = useApp();

  const [importJsonText, setImportJsonText] = useState('');
  const [importStatus, setImportStatus] = useState<string | null>(null);
  const [showExportModal, setShowExportModal] = useState(false);
  const [exportedJson, setExportedJson] = useState('');
  const [resetConfirmed, setResetConfirmed] = useState(false);

  const handleExport = () => {
    const jsonStr = exportStateToJson();
    setExportedJson(jsonStr);
    setShowExportModal(true);

    // Also trigger browser download
    try {
      const blob = new Blob([jsonStr], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `nada-ai-media-os-backup-${new Date().toISOString().slice(0, 10)}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      console.warn('Download fallback to modal copy');
    }
  };

  const handleImport = () => {
    if (!importJsonText.trim()) return;
    const success = importStateFromJson(importJsonText);
    if (success) {
      setImportStatus('تمت استعادة حالة النظام بنجاح!');
      setImportJsonText('');
      setTimeout(() => setImportStatus(null), 3000);
    } else {
      setImportStatus('خطأ: تنسيق JSON غير صالح أو به بيانات مفقودة.');
    }
  };

  return (
    <div className="space-y-6 animate-fade-up">
      {/* Header Banner */}
      <div className="card p-6 bg-gradient-to-l from-[var(--bg-card)] to-[var(--bg-elevated)] flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs px-2.5 py-0.5 rounded-full bg-accent/20 text-accent font-bold">
              القسم 11 & 14 — SECURITY & RECOVERY
            </span>
            <span className="text-xs text-muted">حماية الأسرار واستعادة البيانات</span>
          </div>
          <h1 className="font-display font-bold text-2xl text-primary mt-1">
            مركز الأمان والصلاحيات والنسخ الاحتياطي السيادي
          </h1>
          <p className="text-sm text-secondary">
            إدارة الصلاحيات (سيادة المالك)، فحص التكاملات الخارجية، والنسخ الاحتياطي المقاوم لانقطاع الحاوية.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={handleExport}
            className="px-4 py-2.5 rounded-xl bg-accent text-white text-xs font-bold hover:opacity-90 transition-opacity flex items-center gap-1.5 shadow"
          >
            <Download className="w-4 h-4" />
            <span>تصدير نسخة JSON فورية</span>
          </button>
        </div>
      </div>

      {/* Role Management Matrix (Section 4 & Section 2.2 Fix 4) */}
      <div className="card p-6 space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-default">
          <div className="flex items-center gap-2">
            <UserCheck className="w-5 h-5 text-accent" />
            <h3 className="font-display font-bold text-base text-primary">
              إدارة الأدوار والصلاحيات السيادية (Access Control Matrix)
            </h3>
          </div>
          <span className="text-xs text-muted">الدور النشط: {currentUser.name}</span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {(['OWNER', 'ADMIN', 'AGENT', 'GUEST'] as UserRole[]).map((role) => {
            const isSelected = currentRole === role;
            const titles: Record<UserRole, { label: string; desc: string; icon: string }> = {
              OWNER: { label: 'المالك (OWNER)', desc: 'القرار النهائي والسيادة المطلقة', icon: '👑' },
              ADMIN: { label: 'المدير العام (ADMIN)', desc: 'تنسيق الفرق وإدارة الأقسام', icon: '⚡' },
              AGENT: { label: 'وكيل الإنتاج (AGENT)', desc: 'توليد ومراجعة المحتوى والسكريبت', icon: '🤖' },
              GUEST: { label: 'المراجع (GUEST)', desc: 'صلاحيات قراءة وفحص جودة محدودة', icon: '🔍' },
            };
            const roleInfo = titles[role];

            return (
              <div
                key={role}
                onClick={() => switchRole(role)}
                className={`p-4 rounded-xl border cursor-pointer transition-all flex flex-col justify-between ${
                  isSelected
                    ? 'bg-accent/15 border-accent shadow-md'
                    : 'bg-elevated border-default hover:border-accent/40'
                }`}
              >
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-2xl">{roleInfo.icon}</span>
                    {isSelected && (
                      <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-accent text-white">
                        الجلسة الحالية
                      </span>
                    )}
                  </div>
                  <h4 className="font-bold text-sm text-primary">{roleInfo.label}</h4>
                  <p className="text-xs text-secondary mt-1">{roleInfo.desc}</p>
                </div>

                <div className="mt-3 pt-2 border-t border-default/50 text-[11px] space-y-1">
                  <div className="flex items-center justify-between text-muted">
                    <span>اعتماد القرارات الحساسة:</span>
                    <span className={role === 'OWNER' ? 'text-accent font-bold' : 'text-muted'}>
                      {role === 'OWNER' ? 'حصري للمالك' : 'محظور'}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-muted">
                    <span>الوصول لـ Sandbox 2350:</span>
                    <span className={role === 'OWNER' || role === 'ADMIN' ? 'text-accent' : 'text-muted'}>
                      {role === 'OWNER' || role === 'ADMIN' ? 'مسموح' : 'محظور'}
                    </span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* External Connectors & API Health (Section 2.2 Fix 7 & 9) */}
      <div className="card p-6 space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-default">
          <div className="flex items-center gap-2">
            <Key className="w-5 h-5 text-info" />
            <h3 className="font-display font-bold text-base text-primary">
              تكاملات الخدمات الخارجية وموصلات API (Connectors Health)
            </h3>
          </div>
          <span className="text-xs text-muted">فحص التوصيل والاعتماديات</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {integrations.map((int) => (
            <div
              key={int.id}
              className="p-4 rounded-xl bg-elevated border border-default flex flex-col justify-between"
            >
              <div>
                <div className="flex items-start justify-between gap-2 mb-1.5">
                  <h4 className="font-bold text-sm text-primary">{int.name}</h4>
                  <span
                    className={`text-[10px] px-2 py-0.5 rounded-full font-bold ${
                      int.status === 'connected'
                        ? 'bg-accent/15 text-accent'
                        : int.status === 'needs_keys'
                        ? 'bg-amber-500/15 text-warning'
                        : 'bg-red-500/15 text-error'
                    }`}
                  >
                    {int.status === 'connected' ? 'متصل' : 'بحاجة لإعداد'}
                  </span>
                </div>
                <p className="text-xs text-secondary mb-3">{int.provider}</p>
              </div>

              <div className="pt-2 border-t border-default/50 flex items-center justify-between text-xs">
                <span className="text-muted">استجابة: {int.latency}</span>
                <button
                  onClick={() => pingIntegration(int.id)}
                  className="text-xs text-accent hover:underline font-bold"
                >
                  فحص الاتصال (Ping)
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Backup & Disaster Recovery (Section 2.2 Fix 8 & Section 11.3) */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Restore from JSON */}
        <div className="card p-6 space-y-4">
          <div className="flex items-center gap-2 pb-2 border-b border-default">
            <Upload className="w-5 h-5 text-accent" />
            <h3 className="font-display font-bold text-sm text-primary">
              استعادة بيانات المنظومة من ملف JSON
            </h3>
          </div>
          <p className="text-xs text-secondary leading-relaxed">
            الصق بيانات الـ JSON المصدرة لاستعادة كامل قاعدة البيانات المحلية (الشخصيات، المشروعات، السكريبتات، الذاكرة):
          </p>

          <textarea
            rows={4}
            value={importJsonText}
            onChange={(e) => setImportJsonText(e.target.value)}
            placeholder="الصق نص الـ JSON الكامل هنا..."
            className="w-full p-3 rounded-xl bg-elevated border border-default text-xs text-primary font-mono outline-none focus:border-accent"
          />

          {importStatus && (
            <div
              className={`p-3 rounded-xl text-xs font-bold ${
                importStatus.includes('خطأ')
                  ? 'bg-red-500/10 text-error border border-red-500/20'
                  : 'bg-accent/10 text-accent border border-accent/20'
              }`}
            >
              {importStatus}
            </div>
          )}

          <button
            onClick={handleImport}
            disabled={!importJsonText.trim()}
            className="w-full py-2.5 rounded-xl bg-accent text-white text-xs font-bold disabled:opacity-40 hover:opacity-90 transition-opacity"
          >
            تطبيق واستعادة البيانات
          </button>
        </div>

        {/* Emergency Reset & Checkpoint */}
        <div className="card p-6 space-y-4 border border-red-500/20 bg-red-500/5">
          <div className="flex items-center gap-2 pb-2 border-b border-red-500/20">
            <RotateCcw className="w-5 h-5 text-error" />
            <h3 className="font-display font-bold text-sm text-error">
              نقطة الرجوع الآمنة وإعادة الضبط للافتراضي 3.0
            </h3>
          </div>
          <p className="text-xs text-secondary leading-relaxed">
            إذا حدث أي تعارض أو تكرار في البيانات، يمكنك استعادة حالة وثيقة المرجع الموحد النظيفة (الإصدار 3.0) وإعادة ضبط جميع الشخصيات الـ 11 والذاكرة.
          </p>

          {!resetConfirmed ? (
            <button
              onClick={() => setResetConfirmed(true)}
              className="w-full py-2.5 rounded-xl bg-elevated hover:bg-red-500/10 border border-red-500/30 text-error text-xs font-bold transition-colors"
            >
              طلب إعادة الضبط للنسخة المرجعية 3.0
            </button>
          ) : (
            <div className="p-3 rounded-xl bg-red-500/10 border border-red-500/30 space-y-2">
              <span className="text-xs text-error font-bold block">
                هل أنت متأكد؟ سيتم استعادة الإعدادات الافتراضية لوثيقة NADA Blueprint 3.0.
              </span>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => {
                    resetToBlueprintDefaults();
                    setResetConfirmed(false);
                  }}
                  className="flex-1 py-2 rounded-lg bg-error text-white text-xs font-bold"
                >
                  نعم، نفذ الاستعادة الآن
                </button>
                <button
                  onClick={() => setResetConfirmed(false)}
                  className="px-4 py-2 rounded-lg bg-elevated text-xs font-bold text-muted hover:text-primary"
                >
                  إلغاء
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Audit Log Table */}
      <div className="card p-6 space-y-4">
        <div className="flex items-center justify-between pb-2 border-b border-default">
          <div className="flex items-center gap-2">
            <Activity className="w-5 h-5 text-accent" />
            <h3 className="font-display font-bold text-base text-primary">
              سجل التدقيق الأمني والعمليات الحساسة (Audit Log)
            </h3>
          </div>
          <span className="text-xs text-muted">تسجيل غير قابل للتعديل</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-right text-xs">
            <thead>
              <tr className="border-b border-default text-muted">
                <th className="py-2.5 px-3">التوقيت</th>
                <th className="py-2.5 px-3">الفاعل</th>
                <th className="py-2.5 px-3">العملية</th>
                <th className="py-2.5 px-3">الوحدة</th>
                <th className="py-2.5 px-3">المستوى</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-default/40">
              {auditLogs.slice(0, 10).map((log) => (
                <tr key={log.id} className="hover:bg-elevated/40 transition-colors">
                  <td className="py-2.5 px-3 text-muted font-mono">{log.timestamp}</td>
                  <td className="py-2.5 px-3 font-bold text-primary">{log.actor}</td>
                  <td className="py-2.5 px-3 text-secondary">{log.action}</td>
                  <td className="py-2.5 px-3 text-muted">{log.module}</td>
                  <td className="py-2.5 px-3">
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                        log.level === 'critical' || log.level === 'security'
                          ? 'bg-red-500/20 text-error'
                          : log.level === 'warn'
                          ? 'bg-amber-500/20 text-warning'
                          : 'bg-accent/20 text-accent'
                      }`}
                    >
                      {log.level}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Export JSON Modal */}
      {showExportModal && (
        <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4">
          <div className="card p-6 max-w-xl w-full animate-fade-up space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-default">
              <h3 className="font-bold text-base text-primary">لقطة النسخ الاحتياطي (JSON Snapshot)</h3>
              <button
                onClick={() => setShowExportModal(false)}
                className="text-muted hover:text-primary font-bold px-2"
              >
                ✕
              </button>
            </div>

            <p className="text-xs text-secondary">
              تم تنزيل الملف تلقائياً. يمكنك أيضاً نسخ الـ JSON يدوياً وحفظه في مكان آمن:
            </p>

            <textarea
              rows={8}
              readOnly
              value={exportedJson}
              className="w-full p-3 rounded-xl bg-elevated border border-default text-xs text-primary font-mono outline-none"
            />

            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                onClick={() => {
                  navigator.clipboard.writeText(exportedJson);
                  alert('تم نسخ الـ JSON إلى الحافظة!');
                }}
                className="px-4 py-2 rounded-xl bg-accent text-white text-xs font-bold hover:opacity-90"
              >
                نسخ إلى الحافظة
              </button>
              <button
                onClick={() => setShowExportModal(false)}
                className="px-4 py-2 rounded-xl bg-elevated text-xs font-bold text-muted hover:text-primary"
              >
                إغلاق
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
