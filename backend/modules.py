"""Registered product modules and their honest implementation state."""
MODULES = [
    {"id": "dashboard", "title": "لوحة التحكم", "group": "الرئيسية", "icon": "⌂", "state": "READY"},
    {"id": "tasks", "title": "مركز المهام", "group": "التشغيل", "icon": "☷", "state": "READY"},
    {"id": "approvals", "title": "مركز الموافقات", "group": "التشغيل", "icon": "✓", "state": "READY"},
    {"id": "activity", "title": "سجل النشاط", "group": "التشغيل", "icon": "◷", "state": "READY"},
    {"id": "projects", "title": "المشاريع", "group": "التخطيط والتنفيذ", "icon": "▧", "state": "NOT_CONFIGURED"},
    {"id": "ai-team", "title": "فريق الذكاء الاصطناعي", "group": "أنظمة الذكاء الاصطناعي", "icon": "✣", "state": "NOT_CONFIGURED"},
    {"id": "ai-router", "title": "موجّه النماذج", "group": "أنظمة الذكاء الاصطناعي", "icon": "⌘", "state": "NOT_CONFIGURED"},
    {"id": "manus", "title": "Manus", "group": "أنظمة الذكاء الاصطناعي", "icon": "M", "state": "NOT_CONFIGURED"},
    {"id": "github", "title": "GitHub", "group": "أنظمة الذكاء الاصطناعي", "icon": "⌘", "state": "NOT_CONFIGURED"},
    {"id": "characters", "title": "الشخصيات", "group": "الشخصيات والمحتوى", "icon": "◉", "state": "NOT_CONFIGURED"},
    {"id": "character-bibles", "title": "أدلة الشخصيات", "group": "الشخصيات والمحتوى", "icon": "▤", "state": "NOT_CONFIGURED"},
    {"id": "localization", "title": "التوطين", "group": "الشخصيات والمحتوى", "icon": "文", "state": "COMING_SOON"},
    {"id": "content", "title": "المحتوى", "group": "الإنتاج والنشر", "icon": "▧", "state": "NOT_CONFIGURED"},
    {"id": "production", "title": "الإنتاج", "group": "الإنتاج والنشر", "icon": "▶", "state": "NOT_CONFIGURED"},
    {"id": "media-vault", "title": "خزنة الوسائط", "group": "الإنتاج والنشر", "icon": "▣", "state": "NOT_CONFIGURED"},
    {"id": "publishing", "title": "النشر", "group": "الإنتاج والنشر", "icon": "↗", "state": "NOT_CONFIGURED"},
    {"id": "analytics", "title": "التحليلات", "group": "الإنتاج والنشر", "icon": "⌁", "state": "NOT_CONFIGURED"},
    {"id": "company-builder", "title": "منشئ الشركة", "group": "المنصة", "icon": "⊞", "state": "FOUNDATION"},
    {"id": "security", "title": "الأمان", "group": "المنصة", "icon": "◇", "state": "READY"},
    {"id": "settings", "title": "الإعدادات", "group": "المنصة", "icon": "⚙", "state": "READY"},
]

BUILDER_CAPABILITIES = [
    {"id": "department", "title": "إضافة قسم", "state": "COMING_SOON"},
    {"id": "manager", "title": "إضافة مدير ذكاء اصطناعي", "state": "COMING_SOON"},
    {"id": "employee", "title": "إضافة موظف ذكاء اصطناعي", "state": "COMING_SOON"},
    {"id": "character", "title": "إضافة شخصية", "state": "COMING_SOON"},
    {"id": "workflow", "title": "إضافة سير عمل", "state": "COMING_SOON"},
    {"id": "tool", "title": "إضافة أداة", "state": "COMING_SOON"},
    {"id": "model", "title": "إضافة نموذج ذكاء اصطناعي", "state": "COMING_SOON"},
    {"id": "integration", "title": "إضافة تكامل", "state": "COMING_SOON"},
]
