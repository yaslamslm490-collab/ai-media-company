import { useState } from 'react';
import { useApp } from '@/context/AppContext';
import {
  Play,
  CheckCircle2,
  Lock,
  Terminal,
} from 'lucide-react';

export function FutureEngineerView() {
  const {
    sandboxExperiments,
    runSandboxExperiment,
    promoteSandboxExperiment,
    currentRole,
  } = useApp();

  const [selectedExperiment, setSelectedExperiment] = useState(sandboxExperiments[0]);

  return (
    <div className="space-y-6 animate-fade-up">
      {/* Header Banner */}
      <div className="card p-6 border-l-4 border-l-purple-500 bg-gradient-to-l from-[var(--bg-card)] to-[var(--bg-elevated)] flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs px-2.5 py-0.5 rounded-full bg-purple-500/20 text-purple-400 font-bold">
              القسم 10 — NADA FUTURE ENGINEER 2350
            </span>
            <span className="text-xs text-muted">بيئة البحث والتطوير المعزولة (Sandbox)</span>
          </div>
          <h1 className="font-display font-bold text-2xl text-primary mt-1">
            وحدة مهندس المستقبل 2350 (Sandbox R&D)
          </h1>
          <p className="text-sm text-secondary">
            مختبر تجارب مستقل يختبر أحدث نماذج وتقنيات الذكاء الاصطناعي في بيئة معزولة تماماً قبل ترقيتها للإنتاج.
          </p>
        </div>

        <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-purple-500/10 border border-purple-500/30 text-purple-300 text-xs font-bold">
          <Lock className="w-4 h-4" />
          <span>العزل الأمني مفعل: 100% Sandbox Isolation</span>
        </div>
      </div>

      {/* R&D Workflow Stages */}
      <div className="card p-4 overflow-x-auto">
        <h4 className="text-xs font-bold text-muted mb-2 px-2">دورة عمل مهندس المستقبل (11 خطوة):</h4>
        <div className="flex items-center gap-1.5 min-w-[750px] text-[11px] text-secondary px-2">
          {[
            'MONITOR',
            'VERIFY',
            'COMPARE',
            'PRIORITIZE',
            'PROTOTYPE',
            'TEST',
            'REVIEW',
            'APPROVAL',
            'DEPLOY',
            'MEASURE',
            'RECORD',
          ].map((step, idx) => (
            <span key={step} className="flex items-center gap-1">
              <span className="px-2 py-0.5 rounded bg-elevated border border-default font-mono font-bold text-purple-300">
                {step}
              </span>
              {idx < 10 && <span className="text-muted">←</span>}
            </span>
          ))}
        </div>
      </div>

      {/* Experiments Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        {sandboxExperiments.map((exp) => {
          const isSelected = selectedExperiment?.id === exp.id;
          return (
            <div
              key={exp.id}
              onClick={() => setSelectedExperiment(exp)}
              className={`card p-5 cursor-pointer transition-all border flex flex-col justify-between ${
                isSelected
                  ? 'border-purple-500 bg-purple-500/10 shadow-lg'
                  : 'hover:border-purple-500/40 bg-[var(--bg-card)]'
              }`}
            >
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-mono font-bold text-purple-400">{exp.code}</span>
                  <span
                    className={`text-[10px] px-2 py-0.5 rounded font-bold ${
                      exp.status === 'passed_benchmarks'
                        ? 'bg-accent/20 text-accent'
                        : 'bg-amber-500/20 text-warning'
                    }`}
                  >
                    {exp.status === 'passed_benchmarks' ? 'اجتاز الاختبارات' : 'قيد المحاكاة'}
                  </span>
                </div>

                <h3 className="font-bold text-sm text-primary mb-1">{exp.title}</h3>
                <p className="text-[11px] text-muted mb-2 font-mono">{exp.technology}</p>
                <p className="text-xs text-secondary leading-relaxed mb-4">
                  {exp.hypothesis}
                </p>
              </div>

              <div className="pt-3 border-t border-default/50 space-y-2 text-xs">
                <div className="flex items-center justify-between text-muted">
                  <span>جودة: {exp.metrics.qualityScore}%</span>
                  <span>كفاءة: {exp.metrics.costEfficiency}%</span>
                  <span>زمن: {exp.metrics.latencyMs}ms</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Experiment Execution Console */}
      {selectedExperiment && (
        <div className="card p-6 space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-default">
            <div>
              <span className="text-xs font-mono font-bold text-purple-400">
                {selectedExperiment.code}
              </span>
              <h3 className="font-display font-bold text-lg text-primary">
                {selectedExperiment.title} — كونسول المحاكاة المعزولة
              </h3>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={() => runSandboxExperiment(selectedExperiment.id)}
                className="px-4 py-2 rounded-xl bg-purple-600 text-white text-xs font-bold hover:bg-purple-700 transition-colors flex items-center gap-1.5 shadow"
              >
                <Play className="w-3.5 h-3.5" />
                <span>تشغيل المحاكاة التجريبية</span>
              </button>

              <button
                onClick={() => {
                  if (currentRole !== 'OWNER') {
                    alert('ترقية التجارب إلى الإنتاج تتطلب موافقة المالك (OWNER). يرجى تفعيل دور المالك أولاً.');
                    return;
                  }
                  promoteSandboxExperiment(selectedExperiment.id);
                  alert('تمت ترقية التجربة واعتمادها للإنتاج بنجاح!');
                }}
                className="px-4 py-2 rounded-xl bg-accent text-white text-xs font-bold hover:opacity-90 transition-opacity flex items-center gap-1.5 shadow"
              >
                <CheckCircle2 className="w-3.5 h-3.5" />
                <span>ترقية للإنتاج (قرار المالك)</span>
              </button>
            </div>
          </div>

          {/* Terminal Logs */}
          <div className="p-4 rounded-xl bg-black/80 border border-default text-xs font-mono text-emerald-400 space-y-1.5 min-h-[140px]">
            <div className="text-muted flex items-center gap-1 mb-2">
              <Terminal className="w-3.5 h-3.5" />
              <span>NADA 2350 Isolated Sandbox Log Output:</span>
            </div>
            {selectedExperiment.logs.map((log, idx) => (
              <div key={idx} className="leading-relaxed">
                &gt; {log}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
