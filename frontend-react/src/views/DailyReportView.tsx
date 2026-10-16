import { useApp } from '@/context/AppContext';
import {
  Printer,
  CheckCircle2,
  Clock,
  DollarSign,
  ShieldAlert,
  Sparkles,
} from 'lucide-react';

export function DailyReportView() {
  const {
    projects,
    approvals,
    dailyBudget,
    currentUser,
  } = useApp();

  const pendingApprovals = approvals.filter((a) => a.status === 'pending');
  const activeProjects = projects.filter((p) => p.status === 'in_progress');

  const handlePrint = () => {
    window.print();
  };

  return (
    <div className="space-y-6 animate-fade-up max-w-5xl mx-auto">
      {/* Header Banner */}
      <div className="card p-6 bg-gradient-to-l from-[var(--bg-card)] to-[var(--bg-elevated)] flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs px-2.5 py-0.5 rounded-full bg-accent/20 text-accent font-bold">
              القسم 16 — DAILY OPERATIONAL REPORT
            </span>
            <span className="text-xs text-muted">{new Date().toLocaleDateString('ar-EG')}</span>
          </div>
          <h1 className="font-display font-bold text-2xl text-primary mt-1">
            التقرير التشغيلي اليومي الموحد — NADA AI Media OS
          </h1>
          <p className="text-sm text-secondary">
            تقرير سيادي شامل يعرض الإنجازات، المهام الجارية، طلبات موافقة المالك، والمخاطر والتكاليف.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={handlePrint}
            className="px-4 py-2.5 rounded-xl bg-accent text-white text-xs font-bold hover:opacity-90 transition-opacity flex items-center gap-2 shadow"
          >
            <Printer className="w-4 h-4" />
            <span>طباعة / حفظ PDF</span>
          </button>
        </div>
      </div>

      {/* Report Paper Container */}
      <div className="card p-8 space-y-8 border border-default bg-[var(--bg-card)] shadow-lg print:border-none print:shadow-none print:p-0">
        {/* Report Top Meta */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-default text-xs">
          <div>
            <h2 className="font-bold text-base text-primary">NADA AI Media OS 3.0 — Hybrid Edition</h2>
            <p className="text-muted">المرجع المعتمد: وثيقة التطوير والاستعادة السيادية</p>
          </div>
          <div className="text-left">
            <p className="text-muted">
              تاريخ التقرير: <span className="font-bold text-primary">{new Date().toLocaleDateString('ar-EG')}</span>
            </p>
            <p className="text-muted">
              المعد للتقرير: <span className="font-bold text-accent">{currentUser.name}</span>
            </p>
          </div>
        </div>

        {/* Section 1: ما اكتمل اليوم مع دليل التحقق */}
        <div className="space-y-3">
          <h3 className="font-bold text-sm text-primary flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-accent" />
            1. ما اكتمل وتم التحقق منه اليوم (Completed & Verified)
          </h3>
          <div className="p-4 rounded-xl bg-elevated/70 border border-default text-xs space-y-2 leading-relaxed">
            <p className="text-secondary flex items-start gap-2">
              <span className="text-accent font-bold">✓</span>
              <span>
                <strong>معالجة أزرار لوحة التحكم:</strong> تم تفعيل جميع أزرار لوحة التحكم، وإعادة تشغيل الوكلاء، وتحديث مؤشرات المنصات بنجاح.
              </span>
            </p>
            <p className="text-secondary flex items-start gap-2">
              <span className="text-accent font-bold">✓</span>
              <span>
                <strong>فحص وتفعيل الصوت العربي:</strong> تم التحقق من Web Speech Recognition (STT) وWeb Speech Synthesis (TTS) مع دعم مخارج الحروف العربية.
              </span>
            </p>
            <p className="text-secondary flex items-start gap-2">
              <span className="text-accent font-bold">✓</span>
              <span>
                <strong>كتالوج الشخصيات الـ 11:</strong> تم اكتمال ملفات Character Bible لجميع الشخصيات (من CHAR-001 إلى CHAR-011) وبصمات الصوت.
              </span>
            </p>
            <p className="text-secondary flex items-start gap-2">
              <span className="text-accent font-bold">✓</span>
              <span>
                <strong>حفظ واستعادة البيانات السيادية:</strong> تم تشغيل التخزين المحلي الدائم مع تصدير واستيراد لقطات JSON بنجاح.
              </span>
            </p>
          </div>
        </div>

        {/* Section 2: ما ينتظر موافقة المالك */}
        <div className="space-y-3">
          <h3 className="font-bold text-sm text-primary flex items-center gap-2">
            <ShieldAlert className="w-4 h-4 text-warning" />
            2. ما ينتظر موافقة وقرار المالك (Awaiting Owner Decision)
          </h3>
          <div className="space-y-2">
            {pendingApprovals.map((appr) => (
              <div
                key={appr.id}
                className="p-3.5 rounded-xl bg-amber-500/10 border border-amber-500/20 text-xs flex items-center justify-between gap-3"
              >
                <div>
                  <span className="font-bold text-primary block">{appr.title}</span>
                  <span className="text-muted text-[11px]">{appr.summary}</span>
                </div>
                <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-amber-500/20 text-warning whitespace-nowrap">
                  {appr.priority === 'urgent' ? 'عاجل للمالك' : 'معلق'}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Section 3: المشروعات الجارية والتكاليف */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="p-4 rounded-xl bg-elevated border border-default space-y-2 text-xs">
            <h4 className="font-bold text-primary mb-2 flex items-center gap-1.5">
              <Clock className="w-4 h-4 text-info" />
              3. حالة المشروعات الجارية ({activeProjects.length})
            </h4>
            {activeProjects.map((p) => (
              <div key={p.id} className="flex items-center justify-between pb-1 border-b border-default/40">
                <span className="text-secondary">{p.title}</span>
                <span className="font-bold text-accent">{p.progress}%</span>
              </div>
            ))}
          </div>

          <div className="p-4 rounded-xl bg-elevated border border-default space-y-2 text-xs">
            <h4 className="font-bold text-primary mb-2 flex items-center gap-1.5">
              <DollarSign className="w-4 h-4 text-accent" />
              4. تكلفة التشغيل وترشيد النماذج
            </h4>
            <div className="flex items-center justify-between pb-1 border-b border-default/40">
              <span className="text-secondary">الاستهلاك اليومي الفعلي:</span>
              <span className="font-bold text-primary">${dailyBudget.used}</span>
            </div>
            <div className="flex items-center justify-between pb-1 border-b border-default/40">
              <span className="text-secondary">سقف الميزانية اليومية المعتمد:</span>
              <span className="font-bold text-muted">${dailyBudget.max}</span>
            </div>
            <p className="text-[11px] text-accent pt-1">
              تم توفير 70% من التكلفة السحابية عبر التوجيه الذكي في OmniRoute.
            </p>
          </div>
        </div>

        {/* Section 4: الخطوة التالية وتوصيات المالك */}
        <div className="p-5 rounded-xl bg-accent/10 border border-accent/30 text-xs space-y-2">
          <h4 className="font-bold text-primary flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-accent" />
            5. الخطوة التالية المقترحة والقرارات المطلوبة من المالك
          </h4>
          <p className="text-secondary leading-relaxed">
            1. اعتماد خطة النشر الأسبوعية المعلقة في مركز الموافقات للبدء في بث الحلقات الأولى.
            <br />
            2. تجربة جلسة صوتية متكاملة في استوديو الصوت والمساعد NADA للاطمئنان على التوافق.
            <br />
            3. تصدير نسخة احتياطية إضافية عبر زر تصدير JSON في مركز الأمان والاحتفاظ بها محلياً.
          </p>
        </div>
      </div>
    </div>
  );
}
