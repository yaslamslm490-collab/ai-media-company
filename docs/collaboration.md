# التعاون المدمج في NADA AI

## التصميم

قاعدة NADA AI هي السجل الأساسي للمهام والحالة والنتائج. لا تُنشأ قاعدة بيانات أو خدمة Bridge جديدة: جدول المهام وسجل التحديثات وروابط Manus باقية داخل قاعدة التطبيق الحالية. خادم Python نفسه يخدم MCP على `POST /mcp` وManus callback على `/api/collaboration/manus/webhook`، ويخدم OAuth على نفس الأصل.

حقل البحث العام يرسل `GET /api/search?q=...` إلى خادم التطبيق بعد مهلة كتابة قصيرة. endpoint محمي بمصادقة المالك ويبحث فعليًا في المهام والموافقات والنشاط وفريق الذكاء الاصطناعي. تظهر حالة التحميل والنتائج الفارغة والأخطاء، ويظل البحث المحلي داخل الوحدات القائمة كما هو. لا يسجل سجل HTTP نص query.

أدوات MCP تشمل قراءة المهام وإنشاءها وتحديثها وحفظ النتائج وإرسالها إلى Manus ومزامنتها وإرسال رد متابعة وتسجيل Webhook. الوصول محمي بنطاقات منفصلة: `tasks:read` و`tasks:write` و`manus:execute`. تُفرض الصلاحية على كل استدعاء؛ يبدأ التفويض بالقراءة وتظهر صلاحيات الكتابة/Manus عند طلبها. أداة `create_and_send_task_to_manus` تنشئ سجلًا واحدًا في NADA AI ثم ترسل المهمة إلى Manus API الرسمي بخصوصية `private`؛ قد يبدأ ذلك عملًا خارجيًا ويستهلك حصة Manus. لا تُرسل مهمة حية دون طلب صريح من المالك.

## OAuth 2.1 المدمج

نقاط الخدمة:

- مورد MCP: `/mcp`
- بيانات المورد المحمي: `/.well-known/oauth-protected-resource` (وكذلك المسار المعرّف للمورد `/mcp`)
- بيانات خادم التفويض: `/.well-known/oauth-authorization-server`
- تسجيل عميل عام ديناميكي (DCR): `POST /oauth/register`
- التفويض وموافقة المالك: `/oauth/authorize`
- تبادل رمز التفويض وتجديده: `POST /oauth/token`
- إلغاء الرمز: `POST /oauth/revoke`

التدفق يدعم عميلًا عامًا بلا `client_secret`، وAuthorization Code مع PKCE S256، ومؤشر المورد OAuth، ومعلمة `iss` في ردود التفويض الآمنة بما فيها أخطاء الطلب الموثق، و`offline_access` مع تدوير Refresh Token. تُقبل عناوين تحويل HTTPS المطابقة تمامًا (ويُستثنى localhost للاختبار المحلي). صفحة الموافقة تطلب رمز المالك ولا تعرضه في الرد؛ وتطبق حدود محاولات مؤقتة. تُخزن بصمات SHA-256 للرموز فقط، لا قيمها الخام.

يتبع اختيار الصلاحيات مبدأ أقل امتياز: يبدأ المورد بنطاق `tasks:read` لعمل أدوات القراءة، وتطلب استدعاءات الكتابة أو Manus النطاقات الإضافية تدريجيًا في تحدي `WWW-Authenticate` فقط عند الحاجة. يسرد MCP الأدوات المعروفة، لكنه يتحقق من نطاق كل استدعاء ولا ينفذ كتابة دون موافقة OAuth المناسبة. يدعم الخادم DCR حاليًا، ويعلن `client_id_metadata_document_supported: false` كي لا يوحي بدعم Client ID Metadata Documents.

التهيئة المطلوبة على الخادم:

- `OWNER_API_TOKEN`: رمز دخول المالك، أدخله في مدير أسرار المضيف. يُنصح بقيمة مولدة عشوائيًا بطول 32 بايت على الأقل؛ لا تضعها في Git أو ChatGPT.
- `RENDER_EXTERNAL_URL`: يحقنه Render تلقائيًا. يستخدمه التطبيق لتكوين issuer HTTPS وعنوان Manus Webhook عندما لا تضبط نطاقًا مخصصًا.
- `PUBLIC_BASE_URL`: اختياري لتثبيت نطاق HTTPS مخصص (أصل فقط، بلا مسار أو شرطة أخيرة).
- `NADA_MCP_TOKEN`: مسار قديم متوافق مع العملاء الحاليين؛ لا يلزم عند استخدام OAuth.
- `MANUS_API_KEY`: مطلوب فقط لإرسال المهام/المتابعات أو مزامنتها مع Manus. يُضاف في مدير أسرار المضيف ويبقى في الخادم ولا يُرسل إلى ChatGPT.
- `MANUS_WEBHOOK_PUBLIC_KEY`: اختياري؛ تُجلب قيمة Manus العامة تلقائيًا عند الحاجة إن لم تُضبط.

لا تستخدم مفاتيح ChatGPT/OpenAI هنا. لا تنشئ Secrets داخل مستودع GitHub.

## Manus Webhook

نقطة الصحة `GET /api/collaboration/status` تفصل بين حالة التهيئة والاتصال الحي. لا تعني `CONFIGURED` أو `READY` وحدها نجاح تكامل خارجي. يمكن للمالك استدعاء `register_manus_webhook` مرة واحدة؛ تتحقق الخدمة من القائمة أولًا ولا تكرر تسجيل الرابط. Manus يوقّع الإشعارات ويُتحقق من توقيع RSA-SHA256 وعمره خلال خمس دقائق. إشعار التوقف يطلق مزامنة لاحقة؛ ولا تصبح المهمة `COMPLETED` إلا بعد أن يؤكد `task.detail` الحالة `stopped` و`has_running_background_jobs=false`.

## ChatGPT: الشروط والحالة

بعد نشر التطبيق على HTTPS، أضف عنوان `/mcp` بوصفه custom MCP app في ChatGPT، واختر OAuth. يكتشف ChatGPT بيانات المورد المحمي وخادم التفويض من نقاط `.well-known`؛ آلية التسجيل المدعومة هنا هي DCR لأن `client_id_metadata_document_supported` معلن كـ`false`. لا يرسل التطبيق مفاتيح Manus إلى ChatGPT.

المؤشر `mcp_client_activity = ONLINE` يعني أن الخادم سجّل طلب MCP OAuth ناجحًا من **عميل ما** فقط. لا يمكن إثبات أنه ChatGPT عبر `client_name` لأن اسم DCR معلومة يختارها العميل بنفسه؛ لذلك تبقى `chatgpt_connection = NOT_CHECKED` حتى تحقق مستقل من عميل ChatGPT الحقيقي. لا تُحوَّل جاهزية OAuth أو اختبار محلي إلى اتصال حي.

وفق [مركز مساعدة OpenAI](https://help.openai.com/en/articles/12584461-developer-mode-and-mcp-apps-in-chatgpt) الذي فُحص في 2026-10-11، أدوات MCP المخصصة مع الكتابة متاحة لخطط Business وEnterprise/Edu، بينما يستطيع مستخدم Pro استخدام القراءة/الجلب فقط في وضع المطور. لم يثبت دعم الكتابة على Free. يلزم التأكد من أهلية مساحة ChatGPT المستخدمة؛ لا تُعرض الحالة كأنها متصلة.

لا ترسل `MANUS_API_KEY` إلى ChatGPT. ChatGPT يحصل فقط على Bearer OAuth محدود الصلاحيات.

## حدود التبادل التلقائي وما يتطلبه التشغيل الحي

- **ChatGPT → NADA AI:** بعد أن يضيف مسؤول مساحة ChatGPT عنوان `/mcp` ويكمل OAuth، يستطيع ChatGPT قراءة/كتابة سجل NADA AI عبر أدوات MCP وفق الصلاحيات. الاستدعاء يبدأ من محادثة ChatGPT؛ MCP ليس قناة دفع خلفية ترسل كل تغيّر في NADA تلقائيًا إلى ChatGPT، ولا توجد حاليًا خدمة مستقلة تراقب محادثات ChatGPT.
- **NADA AI → Manus:** أدوات MCP ترسل المهمة إلى Manus API الرسمي عندما يطلب العميل صراحةً أداة الإرسال، مع نطاق `manus:execute` ووجود `MANUS_API_KEY` في أسرار الخادم. تخزين النتائج تلقائيًا يحتاج خدمة HTTPS عامة ومفتاح Manus وتسجيل Webhook؛ بعدها يؤكد callback الموقع الحدث ويطلق مزامنة الحالة والنتيجة إلى سجل NADA AI.
- **ما لا يمكن إثباته محليًا:** اختبارات localhost تثبت تدفق MCP/OAuth والكتابة إلى قاعدة اختبار مؤقتة، وتثبت توقيع Webhook عبر محاكاة آمنة. لا تثبت اتصال حساب ChatGPT أو Manus الحي، ولا تغني عن موافقة مالك مساحة ChatGPT، موافقة مالك Manus، نشر عنوان HTTPS، إدخال الأسرار لدى المضيف، وإجراء التفويض هناك.
- إعداد Render الحالي يوقف النشر التلقائي، ولم تُنشأ خدمة أو تُسجّل Webhook حية. لا تُعتبر حالة الإعداد `READY` اتصالًا خارجيًا؛ يلزم فحص حقيقي بعد تفعيل المالك.

## الاختبارات وحدودها

```bash
python3 -m unittest tests.test_collaboration tests.test_oauth -v
pnpm test
```

اختبارات OAuth تنشئ خادم HTTP وقاعدة SQLite مؤقتين، ثم تنفذ DCR وmetadata وPKCE وموافقة المالك وتبادل/تدوير الرموز وMCP scopes وطلب المهمة إلى قاعدة NADA AI محليًا. اختبار `mcp_client_activity = ONLINE` يخص عميلًا اختباريًا محليًا فقط؛ ويبقى `chatgpt_connection = NOT_CHECKED`. اختبارات البحث تتحقق من endpoint محمي ونتيجة موجودة/فارغة في قاعدة الاختبار. تكامل Manus API/Webhook محاكى؛ لم تُرسل مهمة أو تُسجّل Webhook حية.

انظر [دليل الاستضافة الدائمة](deployment.md) لخيار HTTPS وRender Blueprint. لا تُنشر الخدمة أو تُنشأ موارد مدفوعة تلقائيًا من هذه الاختبارات.

## Bridge القديم

يبقى مجلد `bridge/` مرجعًا متوافقًا فقط، وليس مسار التشغيل المعتمد، ولا ينبغي تشغيله بالتوازي. لم تُحذف ملفاته أو قواعد بياناته أو تُنقل بياناته. التعاون الجديد مدمج في الخادم وقاعدة البيانات الأصليين.

## مراجع رسمية

- [OpenAI: Developer mode وMCP apps في ChatGPT](https://help.openai.com/en/articles/12584461-developer-mode-and-mcp-apps-in-chatgpt)
- [MCP: OAuth 2.1 Authorization (latest)](https://modelcontextprotocol.io/specification/latest/basic/authorization)
- [Manus: Task API](https://open.manus.ai/docs/v2/task.create)
