# النشر الدائم لـ NADA AI على HTTPS

## التوصية المعدّة: Render Blueprint من المستودع الأصلي

أُضيف `render.yaml` في جذر **المستودع نفسه** (`yaslamslm490-collab/ai-media-company`) ويستهدف الفرع `main` وDockerfile الحالي. يعرّف خدمة واحدة باسم `nada-ai-media-os`، وHTTPS عبر عنوان `onrender.com` وشهادة TLS التي يديرها Render. لا يُنشئ مستودع GitHub أو تطبيقًا ثانيًا.

الإعداد المقترح يشغّل التطبيق وقاعدة SQLite الحالية على قرص Render دائم حجمه الابتدائي 10 GB، في المسار `/var/data`. الصور/الوسائط وبيانات المهام ورموز OAuth المخزّنة كبصمات تقع جميعًا تحت القرص نفسه، ولا يهاجر الملف إعدادًا أو بيانات قائمة من خدمة سابقة. جرى تجهيز مدخل Docker لإصلاح ملكية جذر القرص عند بدء الحاوية ثم تشغيل الخادم كمستخدم غير root. الخادم يكتشف `RENDER_EXTERNAL_URL` تلقائيًا؛ لا يلزم نسخ رابط يدوي إلى الكود. `PUBLIC_BASE_URL` يبقى اختياريًا إذا ربطت نطاقًا مخصصًا.

### السعر ولماذا لم أستخدم المجاني

هذا الإعداد **ليس مجانيًا**: خطة خدمة `1c-2g` تكلف حاليًا نحو **25 دولارًا/شهر**، وقرص SSD بحجم 10 GB يكلف **2.50 دولار/شهر** (الإجمالي التقريبي **27.50 دولارًا/شهر** قبل الضرائب أو تكاليف مساحة العمل/الاستخدام الإضافي). لم أنشئ خدمة ولم أشغّل فوترة أو أضف وسيلة دفع.

Render Free غير مناسب هنا: خدمة الويب تتوقف بعد 15 دقيقة خمول، ونظام ملفاتها مؤقت يفقد SQLite والوسائط عند إعادة التشغيل/النشر، ولا تقبل القرص الدائم؛ كما تنتهي قاعدة Free Postgres بعد 30 يومًا. لذلك لا أصفه كاستضافة دائمة تحفظ بيانات AI Media OS. راجع الوثائق الرسمية أدناه قبل الموافقة على أي تكلفة.

## الأسرار

- يدخل `OWNER_API_TOKEN` عند إنشاء Blueprint عندما يطلب Render قيم `sync: false`. ضع رمزًا عشوائيًا قويًا من مدير كلمات مرورك **مباشرة في Render**؛ لا ترسله في المحادثة ولا تضفه إلى GitHub.
- لا يحتوي Blueprint على `MANUS_API_KEY`. إذا أردت تشغيل الإرسال/المزامنة إلى Manus، أضف المفتاح بنفسك من **Render → الخدمة → Environment**. حتى ذلك الحين ستبقى Manus API غير مهيأة ولا تُعد المهمة قد أُرسلت.
- لا حاجة إلى `NADA_MCP_TOKEN` لاتصال OAuth؛ يُحتفظ به للتوافق مع عملاء MCP أقدم فقط.
- تحديث إعدادات Secrets يجري من مدير أسرار Render فقط، وليس من ملفات المستودع أو ChatGPT.

## ما لم يحدث بعد

لم يُستدعَ حساب Render ولم تُنشأ خدمة أو قرص ولم يحدث نشر؛ لا أملك نتيجة فحص حية لحساب Render أو أي خدمة موجودة فيه، لذلك لا أزعم أن الموقع منشور. ملف Blueprint هو تهيئة قابلة للمراجعة فقط. كذلك لا يوجد اتصال حي مع Manus API أو ChatGPT في هذه البيئة. بعد نشر HTTPS، يمكن فحص `GET /api/health` وبيانات OAuth ثم إضافة custom MCP app إلى مساحة ChatGPT مؤهلة. حساب Free الحالي لا يدعم MCP مخصصًا بكتابة كاملة حسب OpenAI؛ الربط الكتابي متاح لخطط Business وEnterprise/Edu، وPro للقراءة/الجلب فقط.

## خطوة المالك

افتح Render، أنشئ Blueprint من المستودع والفرع `main`، راجع السعر أعلاه، وأدخل `OWNER_API_TOKEN` في خانة السر ثم وافق على بدء الخدمة المدفوعة إذا رغبت. لا يمكن إتمام خطوة التكلفة من دون موافقتك. بعد ظهور عنوان `onrender.com`، اختبر `/api/health`؛ ثم أضف `MANUS_API_KEY` في مدير الأسرار فقط إذا كان متاحًا وتريد إرسال مهام حية.

## مراجع رسمية

- [Render: Free instances وحدودها](https://render.com/docs/free)
- [Render: Persistent Disks](https://render.com/docs/disks)
- [Render: الأسعار والحوسبة والتخزين](https://render.com/pricing)
- [Render: Blueprint Specification](https://render.com/docs/blueprint-spec)
- [Render: متغيرات البيئة الافتراضية ومنها `RENDER_EXTERNAL_URL`](https://render.com/docs/environment-variables)
- [OpenAI: Developer mode وMCP apps في ChatGPT](https://help.openai.com/en/articles/12584461-developer-mode-and-mcp-apps-in-chatgpt)
- [MCP: OAuth 2.1 Authorization](https://modelcontextprotocol.io/specification/2025-06-18/basic/authorization)
