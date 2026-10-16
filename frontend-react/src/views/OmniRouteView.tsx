import { useState } from 'react';
import { useApp } from '@/context/AppContext';
import {
  Network,
  Zap,
  RotateCcw,
} from 'lucide-react';

export function OmniRouteView() {
  const { routes, testRoute, dailyBudget } = useApp();
  const [testingId, setTestingId] = useState<string | null>(null);

  const handleTest = (routeId: string) => {
    setTestingId(routeId);
    setTimeout(() => {
      testRoute(routeId);
      setTestingId(null);
    }, 400);
  };

  return (
    <div className="space-y-6 animate-fade-up">
      {/* Header Banner */}
      <div className="card p-6 bg-gradient-to-l from-[var(--bg-card)] to-[var(--bg-elevated)] flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs px-2.5 py-0.5 rounded-full bg-accent/20 text-accent font-bold">
              القسم 5.16 & 9 — OMNIROUTE INTELLIGENT ROUTER
            </span>
            <span className="text-xs text-muted">توجيه الطلبات حسب الجودة والتكلفة</span>
          </div>
          <h1 className="font-display font-bold text-2xl text-primary mt-1">
            إدارة وتوجيه النماذج الذكية (OmniRoute Hub)
          </h1>
          <p className="text-sm text-secondary">
            بوابة توجيه ذكية متعددة النماذج (Gemini, Claude, GPT, Local) مع مراقبة حية لزمن الاستجابة والتكلفة.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="text-left px-4 py-2 rounded-xl bg-elevated border border-default">
            <span className="text-xs text-muted block">الميزانية اليومية للنماذج</span>
            <span className="text-sm font-bold text-accent">
              ${dailyBudget.used} / ${dailyBudget.max}
            </span>
          </div>
        </div>
      </div>

      {/* Routes Grid */}
      <div className="space-y-4">
        <h3 className="font-display font-bold text-base text-primary flex items-center gap-2">
          <Network className="w-5 h-5 text-accent" />
          المسارات النشطة وتوزيع الأحمال
        </h3>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {routes.map((route) => (
            <div
              key={route.id}
              className="card p-5 hover:border-accent/40 transition-all flex flex-col justify-between"
            >
              <div>
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <div className="w-8 h-8 rounded-lg bg-accent/15 flex items-center justify-center">
                      <Zap className="w-4 h-4 text-accent" />
                    </div>
                    <div>
                      <h4 className="font-bold text-sm text-primary">{route.name}</h4>
                      <span className="text-[10px] text-muted font-mono">{route.id}</span>
                    </div>
                  </div>
                  <span className="status-dot status-active" />
                </div>

                <div className="p-3 rounded-xl bg-elevated border border-default space-y-2 text-xs mb-3">
                  <div className="flex items-center justify-between">
                    <span className="text-muted">المصدر:</span>
                    <span className="font-medium text-secondary">{route.source}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-muted">الهدف (النموذج):</span>
                    <span className="font-bold text-accent">{route.destination}</span>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-2 text-xs mb-4">
                  <div className="p-2.5 rounded-lg bg-[var(--bg-card)] border border-default text-center">
                    <span className="text-muted block text-[10px]">معدل المعالجة</span>
                    <span className="font-bold text-primary font-mono">{route.throughput}</span>
                  </div>
                  <div className="p-2.5 rounded-lg bg-[var(--bg-card)] border border-default text-center">
                    <span className="text-muted block text-[10px]">زمن الاستجابة (Latency)</span>
                    <span className="font-bold text-accent font-mono">{route.latency}</span>
                  </div>
                </div>
              </div>

              <div className="pt-3 border-t border-default flex items-center justify-between">
                <span className="text-[11px] text-muted">
                  التكلفة: {route.costPer1kTokens || '$0.00015'} / 1K Tokens
                </span>
                <button
                  onClick={() => handleTest(route.id)}
                  disabled={testingId === route.id}
                  className="px-3.5 py-1.5 rounded-lg bg-accent/20 hover:bg-accent/30 text-accent text-xs font-bold transition-colors flex items-center gap-1.5"
                >
                  <RotateCcw className={`w-3.5 h-3.5 ${testingId === route.id ? 'animate-spin' : ''}`} />
                  <span>{testingId === route.id ? 'جارٍ الفحص...' : 'فحص المسار (Ping)'}</span>
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
