import { useState } from 'react';
import { useApp } from '@/context/AppContext';
import {
  ShieldAlert,
  CheckCircle2,
  FolderKanban,
  FileText,
  DollarSign,
  Activity,
  ArrowRight,
  Sparkles,
  Zap,
} from 'lucide-react';

export function OwnerCenterView({ onNavigate }: { onNavigate?: (key: string) => void }) {
  const {
    currentUser,
    currentRole,
    switchRole,
    approvals,
    projects,
    characters,
    dailyBudget,
    auditLogs,
    lastSaved,
  } = useApp();

  const [emergencyAlertDismissed, setEmergencyAlertDismissed] = useState(false);

  const pendingApprovals = approvals.filter((a) => a.status === 'pending');
  const urgentApprovals = pendingApprovals.filter((a) => a.priority === 'urgent' || a.requiresOwnerApproval);
  const activeProjects = projects.filter((p) => p.status === 'in_progress');
  const recentLogs = auditLogs.slice(0, 5);

  return (
    <div className="space-y-6 animate-fade-up">
      {/* Top Banner: Sovereign Authority & Status */}
      <div className="card p-6 border-l-4 border-l-accent bg-gradient-to-l from-[var(--bg-card)] to-[var(--bg-elevated)]">
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className="w-14 h-14 rounded-2xl bg-accent/20 border border-accent/40 flex items-center justify-center text-3xl shadow-lg">
              👑
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xs px-2.5 py-0.5 rounded-full bg-accent/20 text-accent font-semibold">
                  المرجع المعتمد 3.0 — Sovereign Authority
                </span>
                <span className="text-xs text-muted">حتى عام 2350</span>
              </div>
              <h1 className="font-display font-bold text-2xl text-primary mt-1">
                مركز المالك — Owner Command Center
              </h1>
              <p className="text-sm text-secondary">
                الجهة السيادية العليا لاتخاذ القرارات الحساسة، إدارة الميزانيات، وحماية استقرار منظومة NADA AI Media OS.
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <div className="text-left md:text-right px-4 py-2 rounded-xl bg-elevated border border-default">
              <span className="text-xs text-muted block">الجلسة الحالية</span>
              <span className="text-sm font-bold text-accent flex items-center gap-1.5">
                <span className="status-dot status-active" />
                {currentUser.name}
              </span>
            </div>
            {currentRole !== 'OWNER' && (
              <button
                onClick={() => switchRole('OWNER')}
                className="px-4 py-2 rounded-xl bg-accent text-white text-xs font-bold hover:opacity-90 transition-opacity flex items-center gap-1.5 shadow"
              >
                تفعيل صلاحية المالك (OWNER)
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Urgent Owner Decision Alert */}
      {!emergencyAlertDismissed && urgentApprovals.length > 0 && (
        <div className="card p-5 border border-red-500/30 bg-red-500/10 animate-pulse">
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-start gap-3">
              <ShieldAlert className="w-6 h-6 text-error flex-shrink-0 mt-0.5" />
              <div>
                <h4 className="font-bold text-primary text-sm">
                  موافقات سيادية عاجلة تتطلب قرار المالك الحصري ({urgentApprovals.length})
                </h4>
                <p className="text-xs text-secondary mt-1">
                  توجد عمليات حساسة (جدولة نشر، تغيير ميزانيات، أو ترقية نماذج) معلقة بانتظار توقيع صاحب القرار النهائي.
                </p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {urgentApprovals.map((item) => (
                    <span
                      key={item.id}
                      className="text-xs px-3 py-1 rounded-lg bg-red-500/20 text-error font-medium border border-red-500/30"
                    >
                      {item.title}
                    </span>
                  ))}
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2 flex-shrink-0">
              <button
                onClick={() => onNavigate?.('approvals')}
                className="px-4 py-1.5 rounded-lg bg-error text-white text-xs font-bold hover:opacity-90 transition-opacity"
              >
                فتح مركز الموافقات
              </button>
              <button
                onClick={() => setEmergencyAlertDismissed(true)}
                className="text-xs text-muted hover:text-primary px-2"
              >
                تجاهل مؤقت
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Sovereign KPI Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="card p-5">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs text-muted">حالة الاستقرار العام</span>
            <div className="w-8 h-8 rounded-lg bg-accent/15 flex items-center justify-center">
              <Activity className="w-4 h-4 text-accent" />
            </div>
          </div>
          <p className="font-display font-bold text-2xl text-primary">100% مستقر</p>
          <p className="text-xs text-accent mt-1 flex items-center gap-1">
            <CheckCircle2 className="w-3.5 h-3.5" /> جميع الوحدات الـ 20 تعمل محلياً
          </p>
        </div>

        <div className="card p-5">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs text-muted">ميزانية الذكاء اليومية</span>
            <div className="w-8 h-8 rounded-lg bg-blue-500/15 flex items-center justify-center">
              <DollarSign className="w-4 h-4 text-info" />
            </div>
          </div>
          <p className="font-display font-bold text-2xl text-primary">
            ${dailyBudget.used} <span className="text-xs font-normal text-muted">/ ${dailyBudget.max}</span>
          </p>
          <div className="w-full bg-elevated rounded-full h-1.5 mt-2 overflow-hidden">
            <div
              className="bg-info h-full rounded-full transition-all"
              style={{ width: `${(dailyBudget.used / dailyBudget.max) * 100}%` }}
            />
          </div>
          <p className="text-xs text-secondary mt-1">ترشيد التكاليف بنسبة 70% عبر OmniRoute</p>
        </div>

        <div className="card p-5">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs text-muted">كتالوج الشخصيات</span>
            <div className="w-8 h-8 rounded-lg bg-amber-500/15 flex items-center justify-center">
              <Sparkles className="w-4 h-4 text-warning" />
            </div>
          </div>
          <p className="font-display font-bold text-2xl text-primary">{characters.length} شخصيات</p>
          <p className="text-xs text-secondary mt-1">من CHAR-001 إلى CHAR-011 بملفات كاملة</p>
        </div>

        <div className="card p-5">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs text-muted">المشاريع التنفيذية</span>
            <div className="w-8 h-8 rounded-lg bg-purple-500/15 flex items-center justify-center">
              <FolderKanban className="w-4 h-4 text-purple-400" />
            </div>
          </div>
          <p className="font-display font-bold text-2xl text-primary">{activeProjects.length} جارية</p>
          <p className="text-xs text-secondary mt-1">من أصل {projects.length} مشاريع موثقة</p>
        </div>
      </div>

      {/* Main Two-Column Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Owner Action Dashboard */}
        <div className="lg:col-span-2 space-y-6">
          {/* Quick Sovereign Directives */}
          <div className="card p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-display font-bold text-base text-primary flex items-center gap-2">
                <Zap className="w-5 h-5 text-accent" />
                توجيهات المالك السريعة — Quick Sovereign Actions
              </h3>
              <span className="text-xs text-muted">آخر حفظ: {lastSaved}</span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <button
                onClick={() => onNavigate?.('assistant')}
                className="p-4 rounded-xl bg-elevated hover:bg-elevated/80 border border-default text-right transition-all group"
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-bold text-primary group-hover:text-accent transition-colors">
                    إصدار أمر للمساعد NADA
                  </span>
                  <ArrowRight className="w-4 h-4 text-muted group-hover:text-accent group-hover:-translate-x-1 transition-all" />
                </div>
                <p className="text-xs text-secondary">
                  محادثة صوتية أو نصية ذكية لاسترجاع سياق المنظومة وتنفيذ المهام التلقائية.
                </p>
              </button>

              <button
                onClick={() => onNavigate?.('approvals')}
                className="p-4 rounded-xl bg-elevated hover:bg-elevated/80 border border-default text-right transition-all group"
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-bold text-primary group-hover:text-accent transition-colors">
                    مراجعة القرارات الحساسة
                  </span>
                  <span className="text-xs px-2 py-0.5 rounded-full bg-accent/20 text-accent font-bold">
                    {pendingApprovals.length} معلق
                  </span>
                </div>
                <p className="text-xs text-secondary">
                  اعتماد، رفض، أو طلب تعديل الخطط والميزانيات وسكريبتات النشر.
                </p>
              </button>

              <button
                onClick={() => onNavigate?.('daily_report')}
                className="p-4 rounded-xl bg-elevated hover:bg-elevated/80 border border-default text-right transition-all group"
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-bold text-primary group-hover:text-accent transition-colors">
                    التقرير التشغيلي اليومي
                  </span>
                  <FileText className="w-4 h-4 text-muted group-hover:text-accent transition-colors" />
                </div>
                <p className="text-xs text-secondary">
                  ملخص تنفيذي كامل يتضمن المنجز، المعلق، التكاليف، والمخاطر مع إمكانية التصدير.
                </p>
              </button>

              <button
                onClick={() => onNavigate?.('security')}
                className="p-4 rounded-xl bg-elevated hover:bg-elevated/80 border border-default text-right transition-all group"
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-bold text-primary group-hover:text-accent transition-colors">
                    النسخ الاحتياطي والاستعادة
                  </span>
                  <CheckCircle2 className="w-4 h-4 text-muted group-hover:text-accent transition-colors" />
                </div>
                <p className="text-xs text-secondary">
                  تصدير لقطة الذاكرة بصيغة JSON، أو استرجاع نقطة أمان سابقة عند أي طارئ.
                </p>
              </button>
            </div>
          </div>

          {/* Active Strategic Projects */}
          <div className="card p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-display font-bold text-base text-primary flex items-center gap-2">
                <FolderKanban className="w-5 h-5 text-purple-400" />
                المشاريع الإستراتيجية النشطة
              </h3>
              <button
                onClick={() => onNavigate?.('projects')}
                className="text-xs text-accent hover:underline"
              >
                عرض كل المشروعات ({projects.length})
              </button>
            </div>

            <div className="space-y-3">
              {projects.map((prj) => (
                <div
                  key={prj.id}
                  className="p-4 rounded-xl bg-elevated border border-default flex flex-col sm:flex-row sm:items-center justify-between gap-3"
                >
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-mono font-bold text-accent">{prj.code}</span>
                      <h4 className="text-sm font-bold text-primary truncate">{prj.title}</h4>
                    </div>
                    <p className="text-xs text-muted mt-1">
                      المدير: {prj.manager} • الموعد النهائي: {prj.deadline}
                    </p>
                  </div>

                  <div className="flex items-center gap-4 flex-shrink-0">
                    <div className="text-left w-24">
                      <div className="flex items-center justify-between text-xs mb-1">
                        <span className="text-muted">الإنجاز</span>
                        <span className="font-bold text-primary">{prj.progress}%</span>
                      </div>
                      <div className="w-full bg-[var(--bg-card)] rounded-full h-1.5 overflow-hidden">
                        <div
                          className="bg-accent h-full rounded-full transition-all"
                          style={{ width: `${prj.progress}%` }}
                        />
                      </div>
                    </div>
                    <span
                      className={`text-xs px-2.5 py-1 rounded-lg font-medium ${
                        prj.riskLevel === 'high'
                          ? 'bg-red-500/10 text-error'
                          : prj.riskLevel === 'medium'
                          ? 'bg-amber-500/10 text-warning'
                          : 'bg-emerald-500/10 text-accent'
                      }`}
                    >
                      {prj.riskLevel === 'high' ? 'مخاطر عالية' : prj.riskLevel === 'medium' ? 'مخاطر متوسطة' : 'آمن'}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right Column: Audit Log & Sovereignty Guidelines */}
        <div className="space-y-6">
          {/* Sovereign Principles Reminder */}
          <div className="card p-5 bg-gradient-to-br from-[var(--bg-card)] to-[var(--bg-elevated)]">
            <h4 className="font-display font-bold text-sm text-primary mb-3 flex items-center gap-2">
              <ShieldAlert className="w-4 h-4 text-accent" />
              المبادئ الحاكمة للسيادة
            </h4>
            <ul className="text-xs text-secondary space-y-2 leading-relaxed">
              <li className="flex items-start gap-2">
                <span className="text-accent font-bold">1.</span>
                <span>المالك هو صاحب القرار النهائي في القرارات الحساسة والتغييرات الجوهرية.</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-accent font-bold">2.</span>
                <span>الفصل بين الحقيقة والخطة: لا تُعتبر أي ميزة عاملة بمجرد وجود واجهتها.</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-accent font-bold">3.</span>
                <span>التنفيذ القابل للتحقق: كل ميزة يجب أن يكون لها اختبار ونتيجة ودليل.</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-accent font-bold">4.</span>
                <span>الرجوع الآمن: الحفاظ الدائم على نقطة استعادة نقية خالية من الأخطاء.</span>
              </li>
            </ul>
          </div>

          {/* Recent Security & Operational Audit Log */}
          <div className="card p-5">
            <div className="flex items-center justify-between mb-3">
              <h4 className="font-display font-bold text-sm text-primary flex items-center gap-2">
                <Activity className="w-4 h-4 text-info" />
                سجل الرقابة والتدقيق الأخير
              </h4>
              <button
                onClick={() => onNavigate?.('security')}
                className="text-xs text-accent hover:underline"
              >
                الكل
              </button>
            </div>

            <div className="space-y-2.5">
              {recentLogs.map((log) => (
                <div key={log.id} className="p-2.5 rounded-lg bg-elevated/70 border border-default text-xs">
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-medium text-primary truncate">{log.action}</span>
                    <span
                      className={`text-[10px] px-1.5 py-0.5 rounded font-semibold ${
                        log.level === 'critical' || log.level === 'security'
                          ? 'bg-red-500/20 text-error'
                          : log.level === 'warn'
                          ? 'bg-amber-500/20 text-warning'
                          : 'bg-accent/20 text-accent'
                      }`}
                    >
                      {log.module}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-[11px] text-muted">
                    <span>{log.actor}</span>
                    <span>{log.timestamp}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Future Engineer 2350 Quick Glance */}
          <div className="card p-5 border border-purple-500/20 bg-purple-500/5">
            <div className="flex items-center gap-2 mb-2">
              <span className="text-lg">🚀</span>
              <h4 className="font-display font-bold text-sm text-purple-300">NADA Future Engineer 2350</h4>
            </div>
            <p className="text-xs text-secondary leading-relaxed mb-3">
              وحدة أبحاث مستقلة تعمل داخل Sandbox معزول تماماً عن الإنتاج، تبتكر حلولاً للمستقبل وتنتظر اعتماد المالك للترقية.
            </p>
            <button
              onClick={() => onNavigate?.('future_engineer')}
              className="w-full py-2 rounded-xl bg-purple-600/20 hover:bg-purple-600/30 text-purple-300 text-xs font-bold border border-purple-500/30 transition-colors"
            >
              دخول بيئة التجارب المعزولة (Sandbox)
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
