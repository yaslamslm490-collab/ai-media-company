import { useState } from 'react';
import { useApp } from '@/context/AppContext';
import type { Project } from '@/types';
import {
  Plus,
  Calendar,
} from 'lucide-react';

export function ProjectsView() {
  const { projects, addProject } = useApp();
  const [showAddModal, setShowAddModal] = useState(false);

  // New Project Form State
  const [title, setTitle] = useState('');
  const [department, setDepartment] = useState('قسم الإنتاج السينمائي');
  const [budgetAllocated, setBudgetAllocated] = useState(15000);
  const [deadline, setDeadline] = useState('2026-12-15');
  const [riskLevel, setRiskLevel] = useState<'low' | 'medium' | 'high'>('low');

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault();
    const created: Project = {
      id: 'prj-' + Date.now(),
      title: title || 'مشروع جديد',
      code: 'PRJ-' + Math.floor(1000 + Math.random() * 9000),
      department,
      manager: 'AI Company Orchestrator',
      progress: 10,
      budgetAllocated,
      budgetSpent: 1200,
      deadline,
      riskLevel,
      status: 'in_progress',
      dependencies: ['تجهيز السكريبتات', 'اعتماد المالك'],
    };
    addProject(created);
    setShowAddModal(false);
    setTitle('');
  };

  const totalAllocated = projects.reduce((acc, p) => acc + p.budgetAllocated, 0);
  const totalSpent = projects.reduce((acc, p) => acc + p.budgetSpent, 0);

  return (
    <div className="space-y-6 animate-fade-up">
      {/* Header Banner */}
      <div className="card p-6 bg-gradient-to-l from-[var(--bg-card)] to-[var(--bg-elevated)] flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs px-2.5 py-0.5 rounded-full bg-accent/20 text-accent font-bold">
              القسم 5.7 — PROJECTS & BUDGETS
            </span>
            <span className="text-xs text-muted">إدارة المشروعات والمهام والمخاطر</span>
          </div>
          <h1 className="font-display font-bold text-2xl text-primary mt-1">
            إدارة المشروعات والمراحل والميزانيات
          </h1>
          <p className="text-sm text-secondary">
            متابعة نسب الإنجاز، تكاليف الإنتاج، المواعيد النهائية، والاعتماديات بين الفرق والوكلاء.
          </p>
        </div>

        <button
          onClick={() => setShowAddModal(true)}
          className="px-4 py-2.5 rounded-xl bg-accent text-white text-xs font-bold hover:opacity-90 transition-opacity flex items-center gap-2 self-start md:self-auto shadow"
        >
          <Plus className="w-4 h-4" />
          <span>إضافة مشروع جديد</span>
        </button>
      </div>

      {/* KPI Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="card p-5">
          <p className="text-xs text-muted mb-1">إجمالي الميزانية المرصودة</p>
          <p className="font-display font-bold text-2xl text-primary">${totalAllocated.toLocaleString()}</p>
          <p className="text-xs text-secondary mt-1">موزعة على {projects.length} مشاريع</p>
        </div>

        <div className="card p-5">
          <p className="text-xs text-muted mb-1">المصروف الفعلي حتى الآن</p>
          <p className="font-display font-bold text-2xl text-accent">${totalSpent.toLocaleString()}</p>
          <p className="text-xs text-accent mt-1">وفر مالي 30% من الميزانية التقديرية</p>
        </div>

        <div className="card p-5">
          <p className="text-xs text-muted mb-1">متوسط نسبة الإنجاز</p>
          <p className="font-display font-bold text-2xl text-info">
            {Math.round(projects.reduce((acc, p) => acc + p.progress, 0) / (projects.length || 1))}%
          </p>
          <p className="text-xs text-secondary mt-1">وفق الجداول الزمنية المحددة</p>
        </div>
      </div>

      {/* Projects Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {projects.map((prj) => (
          <div
            key={prj.id}
            className="card p-5 hover:border-accent/40 transition-all flex flex-col justify-between"
          >
            <div>
              <div className="flex items-start justify-between gap-2 mb-2">
                <div>
                  <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-elevated border border-default text-accent">
                    {prj.code}
                  </span>
                  <h3 className="font-bold text-base text-primary mt-1">{prj.title}</h3>
                </div>
                <span
                  className={`text-xs px-2.5 py-0.5 rounded-full font-bold ${
                    prj.riskLevel === 'high'
                      ? 'bg-red-500/15 text-error'
                      : prj.riskLevel === 'medium'
                      ? 'bg-amber-500/15 text-warning'
                      : 'bg-accent/15 text-accent'
                  }`}
                >
                  {prj.riskLevel === 'high' ? 'مخاطر عالية' : prj.riskLevel === 'medium' ? 'مخاطر متوسطة' : 'آمن'}
                </span>
              </div>

              <p className="text-xs text-muted mb-4">
                القسم: {prj.department} • المدير: {prj.manager}
              </p>

              {/* Progress */}
              <div className="mb-4">
                <div className="flex items-center justify-between text-xs mb-1">
                  <span className="text-muted">نسبة الإنجاز:</span>
                  <span className="font-bold text-primary">{prj.progress}%</span>
                </div>
                <div className="progress-bar">
                  <div className="progress-fill" style={{ width: `${prj.progress}%` }} />
                </div>
              </div>

              {/* Budget Details */}
              <div className="grid grid-cols-2 gap-2 text-xs p-3 rounded-xl bg-elevated border border-default mb-4">
                <div>
                  <span className="text-muted block text-[10px]">الميزانية:</span>
                  <span className="font-bold text-primary">${prj.budgetAllocated.toLocaleString()}</span>
                </div>
                <div>
                  <span className="text-muted block text-[10px]">المصروف:</span>
                  <span className="font-bold text-accent">${prj.budgetSpent.toLocaleString()}</span>
                </div>
              </div>

              {/* Dependencies */}
              <div>
                <span className="text-[11px] text-muted block mb-1.5 font-semibold">
                  الاعتماديات والمهام المرتبطة:
                </span>
                <div className="flex flex-wrap gap-1.5">
                  {prj.dependencies.map((dep, idx) => (
                    <span
                      key={idx}
                      className="text-[10px] px-2 py-0.5 rounded bg-[var(--bg-card)] border border-default text-secondary"
                    >
                      ✓ {dep}
                    </span>
                  ))}
                </div>
              </div>
            </div>

            <div className="pt-3 mt-4 border-t border-default/50 flex items-center justify-between text-xs text-muted">
              <span className="flex items-center gap-1">
                <Calendar className="w-3.5 h-3.5" />
                الموعد النهائي: {prj.deadline}
              </span>
              <span className="capitalize px-2 py-0.5 rounded bg-elevated text-secondary">
                {prj.status}
              </span>
            </div>
          </div>
        ))}
      </div>

      {/* Add Project Modal */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4">
          <form
            onSubmit={handleCreate}
            className="card p-6 max-w-md w-full animate-fade-up space-y-4"
          >
            <div className="flex items-center justify-between pb-3 border-b border-default">
              <h3 className="font-bold text-base text-primary">إضافة مشروع استراتيجي جديد</h3>
              <button
                type="button"
                onClick={() => setShowAddModal(false)}
                className="text-muted hover:text-primary font-bold px-2"
              >
                ✕
              </button>
            </div>

            <div>
              <label className="text-xs text-muted block mb-1">عنوان المشروع:</label>
              <input
                type="text"
                required
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="عنوان المشروع..."
                className="w-full p-2.5 rounded-xl bg-elevated border border-default text-xs text-primary outline-none focus:border-accent"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-muted block mb-1">الميزانية المرصودة ($):</label>
                <input
                  type="number"
                  value={budgetAllocated}
                  onChange={(e) => setBudgetAllocated(Number(e.target.value))}
                  className="w-full p-2.5 rounded-xl bg-elevated border border-default text-xs text-primary outline-none focus:border-accent"
                />
              </div>

              <div>
                <label className="text-xs text-muted block mb-1">الموعد النهائي:</label>
                <input
                  type="date"
                  value={deadline}
                  onChange={(e) => setDeadline(e.target.value)}
                  className="w-full p-2.5 rounded-xl bg-elevated border border-default text-xs text-primary outline-none focus:border-accent"
                />
              </div>
            </div>

            <div>
              <label className="text-xs text-muted block mb-1">القسم المسؤول:</label>
              <input
                type="text"
                value={department}
                onChange={(e) => setDepartment(e.target.value)}
                className="w-full p-2.5 rounded-xl bg-elevated border border-default text-xs text-primary outline-none focus:border-accent"
              />
            </div>

            <div>
              <label className="text-xs text-muted block mb-1">مستوى المخاطرة:</label>
              <select
                value={riskLevel}
                onChange={(e) => setRiskLevel(e.target.value as 'low' | 'medium' | 'high')}
                className="w-full p-2.5 rounded-xl bg-elevated border border-default text-xs text-primary outline-none focus:border-accent"
              >
                <option value="low">منخفض (Low Risk)</option>
                <option value="medium">متوسط (Medium Risk)</option>
                <option value="high">مرتفع (High Risk)</option>
              </select>
            </div>

            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setShowAddModal(false)}
                className="px-4 py-2 rounded-xl bg-elevated text-xs font-bold text-muted hover:text-primary"
              >
                إلغاء
              </button>
              <button
                type="submit"
                className="px-5 py-2 rounded-xl bg-accent text-white text-xs font-bold hover:opacity-90"
              >
                إنشاء المشروع
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
