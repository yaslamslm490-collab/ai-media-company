import { useState } from 'react';
import { useApp } from '@/context/AppContext';
import type { ApprovalItem } from '@/types';
import {
  CheckCircle2,
  XCircle,
  Clock,
  AlertTriangle,
  Check,
  X,
} from 'lucide-react';

const priorityStyles: Record<string, { bg: string; color: string }> = {
  low: { bg: 'rgba(100,116,139,0.1)', color: 'var(--text-muted)' },
  medium: { bg: 'rgba(96,165,250,0.1)', color: 'var(--info)' },
  high: { bg: 'rgba(251,191,36,0.1)', color: 'var(--warning)' },
  urgent: { bg: 'rgba(248,113,113,0.1)', color: 'var(--error)' },
};

const priorityLabels: Record<string, string> = {
  low: 'منخفضة',
  medium: 'متوسطة',
  high: 'عالية',
  urgent: 'عاجلة — تتطلب المالك',
};

const typeLabels: Record<string, string> = {
  content: 'محتوى مرئي',
  script: 'سيناريو معتمد',
  campaign: 'حملة إعلامية',
  character: 'تعديل شخصية',
  budget: 'ميزانية مالية',
  deployment: 'نشر سيادي',
};

export function ApprovalsView() {
  const { approvals, approveItem, rejectItem, currentUser, switchRole } = useApp();
  const [filter, setFilter] = useState<'all' | 'pending' | 'approved' | 'rejected'>('all');
  const [decisionModalItem, setDecisionModalItem] = useState<{
    item: ApprovalItem;
    action: 'approve' | 'reject';
  } | null>(null);
  const [decisionNotes, setDecisionNotes] = useState('');

  const filtered = approvals.filter((i) => filter === 'all' || i.status === filter);
  const pendingCount = approvals.filter((i) => i.status === 'pending').length;
  const approvedCount = approvals.filter((i) => i.status === 'approved').length;
  const rejectedCount = approvals.filter((i) => i.status === 'rejected').length;

  const handleOpenDecision = (item: ApprovalItem, action: 'approve' | 'reject') => {
    setDecisionNotes(
      action === 'approve'
        ? 'تمت المراجعة واعتماد العملية وفق معايير الجودة والميزانية المحددة.'
        : 'مرفوض لإعادة التدقيق ومعالجة الملاحظات.'
    );
    setDecisionModalItem({ item, action });
  };

  const handleConfirmDecision = () => {
    if (!decisionModalItem) return;
    if (decisionModalItem.action === 'approve') {
      approveItem(decisionModalItem.item.id, decisionNotes);
    } else {
      rejectItem(decisionModalItem.item.id, decisionNotes);
    }
    setDecisionModalItem(null);
  };

  return (
    <div className="space-y-6 animate-fade-up">
      {/* Header Banner */}
      <div className="card p-6 bg-gradient-to-l from-[var(--bg-card)] to-[var(--bg-elevated)] flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs px-2.5 py-0.5 rounded-full bg-accent/20 text-accent font-bold">
              القسم 5.14 & 14 — APPROVALS & GOVERNANCE
            </span>
            <span className="text-xs text-muted">سيادة المالك في العمليات الحساسة</span>
          </div>
          <h1 className="font-display font-bold text-2xl text-primary mt-1">
            مركز الموافقات والقرارات السيادية
          </h1>
          <p className="text-sm text-secondary">
            مراجعة طلبات النشر، تعديل الشخصيات، الميزانيات، وترقية النماذج مع تسجيل دائم لصاحب القرار وتاريخه.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="text-left px-4 py-2 rounded-xl bg-elevated border border-default">
            <span className="text-xs text-muted block">صلاحية التوقيع</span>
            <span className="text-xs font-bold text-accent">{currentUser.name}</span>
          </div>
        </div>
      </div>

      {/* Permission Warning if not Owner */}
      {!currentUser.canApprove && (
        <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/30 text-xs text-warning flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 flex-shrink-0" />
            <span>
              أنت مسجل حالياً بدور ({currentUser.role}). العمليات السيادية الحساسة تتطلب قرار المالك (OWNER).
            </span>
          </div>
          <button
            onClick={() => switchRole('OWNER')}
            className="px-3 py-1.5 rounded-lg bg-accent text-white font-bold hover:opacity-90 whitespace-nowrap shadow"
          >
            تفعيل دور المالك
          </button>
        </div>
      )}

      {/* KPI Counters */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div
          onClick={() => setFilter('pending')}
          className={`card p-5 cursor-pointer transition-all border ${
            filter === 'pending' ? 'border-amber-500' : 'hover:border-default'
          }`}
        >
          <div className="flex items-center gap-3">
            <div className="w-11 h-11 rounded-xl bg-amber-500/10 flex items-center justify-center">
              <Clock className="w-5 h-5 text-warning" />
            </div>
            <div>
              <p className="text-xs text-muted">بانتظار القرار</p>
              <p className="font-display font-bold text-2xl text-primary">{pendingCount}</p>
            </div>
          </div>
        </div>

        <div
          onClick={() => setFilter('approved')}
          className={`card p-5 cursor-pointer transition-all border ${
            filter === 'approved' ? 'border-accent' : 'hover:border-default'
          }`}
        >
          <div className="flex items-center gap-3">
            <div className="w-11 h-11 rounded-xl bg-accent-dim flex items-center justify-center">
              <CheckCircle2 className="w-5 h-5 text-accent" />
            </div>
            <div>
              <p className="text-xs text-muted">موافق عليها</p>
              <p className="font-display font-bold text-2xl text-primary">{approvedCount}</p>
            </div>
          </div>
        </div>

        <div
          onClick={() => setFilter('rejected')}
          className={`card p-5 cursor-pointer transition-all border ${
            filter === 'rejected' ? 'border-red-500' : 'hover:border-default'
          }`}
        >
          <div className="flex items-center gap-3">
            <div className="w-11 h-11 rounded-xl bg-red-500/10 flex items-center justify-center">
              <XCircle className="w-5 h-5 text-error" />
            </div>
            <div>
              <p className="text-xs text-muted">مرفوضة / للتعديل</p>
              <p className="font-display font-bold text-2xl text-primary">{rejectedCount}</p>
            </div>
          </div>
        </div>
      </div>

      {/* Filter Tabs */}
      <div className="flex items-center gap-2">
        {(['all', 'pending', 'approved', 'rejected'] as const).map((key) => {
          const labels = {
            all: `الكل (${approvals.length})`,
            pending: `بانتظار القرار (${pendingCount})`,
            approved: `موافق عليه (${approvedCount})`,
            rejected: `مرفوض (${rejectedCount})`,
          };
          return (
            <button
              key={key}
              onClick={() => setFilter(key)}
              className={`px-4 py-2 rounded-xl text-xs font-bold transition-colors ${
                filter === key
                  ? 'bg-accent text-white shadow'
                  : 'bg-elevated border border-default text-secondary hover:text-primary'
              }`}
            >
              {labels[key]}
            </button>
          );
        })}
      </div>

      {/* Approvals List */}
      <div className="space-y-3">
        {filtered.map((item) => {
          const prio = priorityStyles[item.priority] || priorityStyles.low;
          return (
            <div
              key={item.id}
              className="card p-5 hover:border-accent/40 transition-all flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4"
            >
              <div className="space-y-1.5 flex-1 min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <span
                    className="text-[10px] font-bold px-2.5 py-0.5 rounded-full"
                    style={{ backgroundColor: prio.bg, color: prio.color }}
                  >
                    {priorityLabels[item.priority]}
                  </span>
                  <span className="text-[10px] px-2 py-0.5 rounded bg-elevated border border-default text-muted">
                    {typeLabels[item.type] || item.type}
                  </span>
                  <span className="text-xs text-muted">• تم الرفع: {item.submittedAt} بواسطة {item.submittedBy}</span>
                </div>

                <h3 className="text-sm font-bold text-primary leading-snug">{item.title}</h3>
                <p className="text-xs text-secondary leading-relaxed">{item.summary}</p>

                {/* Decision History if already decided */}
                {item.decidedBy && (
                  <div className="pt-2 text-[11px] text-muted flex flex-wrap items-center gap-2">
                    <span className="font-semibold text-primary">صاحب القرار: {item.decidedBy}</span>
                    <span>• {item.decidedAt}</span>
                    {item.decisionNotes && <span>• ملاحظة: "{item.decisionNotes}"</span>}
                  </div>
                )}
              </div>

              {/* Action Buttons */}
              <div className="flex items-center gap-2 flex-shrink-0 self-end sm:self-center">
                {item.status === 'pending' ? (
                  <>
                    <button
                      onClick={() => handleOpenDecision(item, 'approve')}
                      className="px-4 py-2 rounded-xl bg-accent text-white text-xs font-bold hover:opacity-90 transition-opacity flex items-center gap-1.5 shadow"
                    >
                      <Check className="w-3.5 h-3.5" />
                      <span>اعتماد</span>
                    </button>
                    <button
                      onClick={() => handleOpenDecision(item, 'reject')}
                      className="px-4 py-2 rounded-xl bg-elevated border border-default text-error text-xs font-bold hover:bg-red-500/10 transition-colors flex items-center gap-1.5"
                    >
                      <X className="w-3.5 h-3.5" />
                      <span>رفض</span>
                    </button>
                  </>
                ) : (
                  <span
                    className={`px-3 py-1.5 rounded-xl text-xs font-bold ${
                      item.status === 'approved'
                        ? 'bg-accent/15 text-accent'
                        : 'bg-red-500/15 text-error'
                    }`}
                  >
                    {item.status === 'approved' ? 'تمت الموافقة' : 'مرفوض'}
                  </span>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Decision Notes Modal */}
      {decisionModalItem && (
        <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4">
          <div className="card p-6 max-w-md w-full animate-fade-up space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-default">
              <h3 className="font-bold text-base text-primary">
                {decisionModalItem.action === 'approve' ? 'اعتماد الطلب' : 'رفض الطلب'}
              </h3>
              <button
                onClick={() => setDecisionModalItem(null)}
                className="text-muted hover:text-primary font-bold px-2"
              >
                ✕
              </button>
            </div>

            <div>
              <span className="text-xs text-muted block mb-1">الطلب:</span>
              <p className="text-xs font-bold text-primary p-2.5 rounded-lg bg-elevated border border-default">
                {decisionModalItem.item.title}
              </p>
            </div>

            <div>
              <label className="text-xs text-muted block mb-1">
                ملاحظات وتوجيهات صاحب القرار (تُحفظ في Decision Memory):
              </label>
              <textarea
                rows={3}
                value={decisionNotes}
                onChange={(e) => setDecisionNotes(e.target.value)}
                className="w-full p-2.5 rounded-xl bg-elevated border border-default text-xs text-primary outline-none focus:border-accent"
              />
            </div>

            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                onClick={() => setDecisionModalItem(null)}
                className="px-4 py-2 rounded-xl bg-elevated text-xs font-bold text-muted hover:text-primary"
              >
                إلغاء
              </button>
              <button
                onClick={handleConfirmDecision}
                className={`px-5 py-2 rounded-xl text-xs font-bold text-white ${
                  decisionModalItem.action === 'approve'
                    ? 'bg-accent hover:opacity-90'
                    : 'bg-error hover:opacity-90'
                }`}
              >
                تأكيد التوقيع ({currentUser.name})
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
