export const STATUS_LABELS = {
  ONLINE: 'متصل', OFFLINE: 'غير متصل', NOT_CONFIGURED: 'غير مهيأ', ERROR: 'خطأ',
  NOT_CHECKED: 'لم يُفحص', AUTH_ERROR: 'اعتماد مرفوض', RATE_LIMITED: 'مقيّد مؤقتاً', CREDITS_EXHAUSTED: 'نفاد الرصيد',
  NETWORK_ERROR: 'خطأ اتصال', UPSTREAM_ERROR: 'خطأ من المزود',
  COMING_SOON: 'قريباً', READY: 'جاهز', FOUNDATION: 'الأساس متاح',
  TODO: 'قيد الانتظار', IN_PROGRESS: 'قيد التنفيذ', WAITING_APPROVAL: 'بانتظار الموافقة',
  COMPLETED: 'مكتمل', CANCELLED: 'ملغى', FAILED: 'فشل', APPROVED: 'تمت الموافقة',
  REJECTED: 'مرفوض', CHANGES_REQUESTED: 'مطلوب تعديل', LOW: 'منخفضة', NORMAL: 'عادية',
  HIGH: 'عالية', URGENT: 'عاجلة', SUCCESS: 'ناجح', FAILURE: 'فشل',
  ACTIVE: 'نشط', INACTIVE: 'غير نشط', PAUSED: 'متوقف مؤقتاً', ON_HOLD: 'متوقف مؤقتاً',
  MANAGER: 'مدير AI', EMPLOYEE: 'موظف AI', WORKER: 'عامل AI', OWNER: 'المالك',
  DRAFT: 'مسودة', ARCHIVED: 'مؤرشف', PUBLISH: 'نشر',
};

export function label(value) {
  return STATUS_LABELS[value] || value || '—';
}

export function statusClass(value) {
  return String(value || 'unknown').toLowerCase().replaceAll('_', '-');
}

export function formatDate(value, withTime = true) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat('ar', withTime
    ? {dateStyle: 'medium', timeStyle: 'short'}
    : {dateStyle: 'medium'}).format(date);
}
