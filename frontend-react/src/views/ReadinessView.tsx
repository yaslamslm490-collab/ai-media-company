import { useApp } from '@/context/AppContext';
import {
  CheckCircle2,
} from 'lucide-react';

export function ReadinessView() {
  const { readinessItems } = useApp();

  return (
    <div className="space-y-6 animate-fade-up">
      {/* Header Banner */}
      <div className="card p-6 bg-gradient-to-l from-[var(--bg-card)] to-[var(--bg-elevated)] flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs px-2.5 py-0.5 rounded-full bg-accent/20 text-accent font-bold">
              القسم 5.19 — READINESS CENTER
            </span>
            <span className="text-xs text-muted">مركز الجاهزية والاعتماد قبل التنفيذ</span>
          </div>
          <h1 className="font-display font-bold text-2xl text-primary mt-1">
            مركز جاهزية الوحدات والأقسام (Pre-Implementation Center)
          </h1>
          <p className="text-sm text-secondary">
            تدقيق المتطلبات، التصميم المعماري، خطة الأمان، وخطة الاختبارات قبل تدشين أي ميزة على بيئة الإنتاج.
          </p>
        </div>

        <div className="text-left px-4 py-2 rounded-xl bg-elevated border border-default">
          <span className="text-xs text-muted block">الوحدات الجاهزة</span>
          <span className="text-sm font-bold text-accent">100% READY FOR IMPLEMENTATION</span>
        </div>
      </div>

      {/* Readiness Items List */}
      <div className="space-y-4">
        {readinessItems.map((item) => (
          <div key={item.id} className="card p-5 space-y-3 hover:border-accent/40 transition-all">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <div className="flex items-center gap-2.5">
                <span className="text-xs font-mono font-bold px-2 py-0.5 rounded bg-elevated border border-default text-accent">
                  {item.code}
                </span>
                <h3 className="font-bold text-base text-primary">{item.moduleName}</h3>
              </div>

              <span className="text-xs px-3 py-1 rounded-full bg-accent/20 text-accent font-bold self-start sm:self-auto flex items-center gap-1.5">
                <CheckCircle2 className="w-3.5 h-3.5" />
                {item.status}
              </span>
            </div>

            {/* Checklist Matrix */}
            <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 pt-2 border-t border-default/50 text-xs">
              <div className="p-2 rounded-lg bg-elevated/70 flex items-center gap-2">
                <span className="text-accent font-bold">✓</span>
                <span className="text-secondary text-[11px]">المتطلبات</span>
              </div>
              <div className="p-2 rounded-lg bg-elevated/70 flex items-center gap-2">
                <span className="text-accent font-bold">✓</span>
                <span className="text-secondary text-[11px]">التصميم المعماري</span>
              </div>
              <div className="p-2 rounded-lg bg-elevated/70 flex items-center gap-2">
                <span className="text-accent font-bold">✓</span>
                <span className="text-secondary text-[11px]">خطة الأمان</span>
              </div>
              <div className="p-2 rounded-lg bg-elevated/70 flex items-center gap-2">
                <span className="text-accent font-bold">✓</span>
                <span className="text-secondary text-[11px]">خطة الاختبارات</span>
              </div>
              <div className="p-2 rounded-lg bg-elevated/70 flex items-center gap-2">
                <span className="text-accent font-bold">✓</span>
                <span className="text-secondary text-[11px]">الرجوع الآمن</span>
              </div>
            </div>

            <div className="text-[11px] text-muted flex items-center justify-between pt-1">
              <span>تقدير التكلفة: {item.costEstimate}</span>
              <span className="text-accent">تم التحقق وفق معايير الجودة</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
