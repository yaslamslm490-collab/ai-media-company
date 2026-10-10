# NADA AI — جسر ChatGPT ↔ Manus

هذه خدمة وسيطة صغيرة تربط **ChatGPT Actions** بـ **Manus API v2**. تستقبل المهمة من ChatGPT عبر HTTPS مع Bearer token خاص بالجسر، تنشئ مهمة Manus خاصة، وتحفظ النتيجة الواردة عبر Manus Webhooks بعد التحقق من توقيع RSA-SHA256. تبقى `MANUS_API_KEY` على الخادم فقط؛ لا توضع في ChatGPT أو ملفات Git.

**الحالة الحالية:** الملفات جاهزة للاختبار محليًا، لكن الربط الحي لم يكتمل. لم يتوفر `MANUS_API_KEY` في بيئة البناء، ولم يُنشر هذا الجسر بعد على عنوان HTTPS دائم؛ لذلك لم نسجل Webhook أو ننشئ مهمة حية.

## ما الذي يفعله الجسر

- `POST /v1/tasks`: يتحقق من مدخل المهمة، ثم ينشئ مهمة خاصة عبر `POST https://api.manus.ai/v2/task.create`.
- `GET /v1/tasks/{task_id}`: يعيد الحالة والنتيجة والمرفقات التي وصلت عبر Webhook. عند `task_stopped` بحالة `finish`، يفحص الجسر `task.detail` قبل إعلان الاكتمال؛ إذا لم يصرح Manus بأن المهام الخلفية انتهت، تبقى الحالة غير محسومة ولا تُعرض كنجاح.
- `POST /v1/tasks/{task_id}/messages`: يرسل رسالة متابعة عادية أو جوابًا لسؤال من الوكيل. لا يوافق هذا المسار تلقائيًا على إجراءات الأدوات.
- `POST /webhooks/manus`: يتحقق من `X-Webhook-Signature` و`X-Webhook-Timestamp`، ويرفض التوقيعات القديمة لأكثر من خمس دقائق، ويمنع معالجة الحدث مرتين.
- `GET /health`: يعرض مؤشرات إعداد عامة فقط، ولا يعرض أي قيمة سرية.

يُضبط موصل GitHub في Manus عبر `MANUS_CONNECTOR_IDS` اختياريًا. عند تركه فارغًا، تستخدم Manus الموصلات الافتراضية المفعّلة للحساب. المعرّف المعروف لموصل GitHub هو `bbb0df76-66bd-4a24-ae4f-2aac4750d90b`، لكن يجب أن يكون الموصل موصولًا ومصرّحًا له فعليًا في حساب Manus.

## المتطلبات

- Python 3.11+ و`cryptography` (موجودة ضمن تبعيات جذر المستودع).
- Manus API key صالح من إعدادات المطور في Manus. لا ترسله في المحادثة.
- عنوان عام **HTTPS** ثابت للجسر حتى تستطيع Manus إرسال Webhooks.
- تخزين دائم لـSQLite (`/data` في صورة Docker) أو بديل قاعدة بيانات دائم عند تشغيل عدة نسخ.
- حساب ChatGPT وخطة تسمح بإنشاء GPT/Actions أو تطبيق مخصص مناسب. وثائق OpenAI الحالية تجعل إنشاء GPTs مخصصًا لمساحات Business/Enterprise/Edu؛ توافر أدوات MCP ذات الكتابة يعتمد كذلك على الخطة وإعدادات مساحة العمل.

## إعداد محلي

من جذر المستودع:

```bash
cp bridge/.env.example bridge/.env
python3 -m pip install -r requirements.txt
python3 -c 'import secrets; print(secrets.token_urlsafe(32))'
```

ضع ناتج الأمر في `BRIDGE_API_TOKEN` داخل `bridge/.env`. ضع مفتاح Manus API في `MANUS_API_KEY` **داخل إعداد البيئة الآمن للخادم** أو في ملف `.env` محلي مستثنى من Git. لا تضع أي مفتاح حقيقي في `.env.example` أو GitHub.

بعد ضبط `BRIDGE_PUBLIC_URL` على العنوان العام HTTPS للجسر، شغّل:

```bash
python3 -m bridge.server
```

ثم تحقق من حالة الخدمة:

```bash
curl -fsS http://127.0.0.1:8123/health
```

لإنشاء مهمة اختبار، استخدم `BRIDGE_API_TOKEN` في ترويسة الجسر فقط:

```bash
curl -X POST http://127.0.0.1:8123/v1/tasks \
  -H 'Authorization: Bearer <BRIDGE_API_TOKEN>' \
  -H 'Content-Type: application/json' \
  -d '{"title":"اختبار ربط NADA AI","prompt":"تحقق من حالة مشروع NADA AI وقدّم ملخصًا دون تعديل الملفات."}'
```

هذا الطلب ينشئ مهمة فعلية وقد يستخدم حصة Manus؛ نفّذه فقط عندما تكون مستعدًا لاستهلاك الاستخدام المعتاد للحساب.

## تشغيل Docker

أنشئ صورة من جذر المستودع:

```bash
docker build -f bridge/Dockerfile -t nada-manus-bridge .
```

شغّلها مع مخزن دائم وإعدادات سرية من ملف محلي أو secret manager:

```bash
docker volume create nada-manus-bridge-data
docker run -d --name nada-manus-bridge --restart unless-stopped \
  --env-file bridge/.env \
  -p 8123:8123 \
  -v nada-manus-bridge-data:/data \
  nada-manus-bridge
```

ضع reverse proxy أمام المنفذ مع TLS صحيح، ثم حدّث `BRIDGE_PUBLIC_URL` إلى أصل HTTPS. لا تعرض منفذ HTTP الخام مباشرة إلى الإنترنت. لا تشغّل عدة نسخ تستخدم SQLite محليًا مشتركًا؛ استخدم قاعدة بيانات مناسبة أو نسخة واحدة مع حجم دائم.

## تسجيل Webhook Manus

بعد نشر الجسر على عنوان HTTPS، تأكد أن `/health` يعيد `database_ready: true`، ثم نفّذ مرة واحدة من بيئة آمنة لديها `MANUS_API_KEY` و`BRIDGE_PUBLIC_URL`:

```bash
python3 -m bridge.register_webhook
```

السكربت يفحص أولًا `GET /v2/webhook.list` حتى لا يسجّل العنوان نفسه مرتين، ثم يستخدم `POST /v2/webhook.create`. Manus يرسل طلب تحقق إلى endpoint ويجب أن يعيد الجسر استجابة 2xx. تأكد أن reverse proxy لا يغيّر المسار أو جسم الطلب، لأن التوقيع محسوب على URL الكامل وجسم HTTP الخام.

## ربط ChatGPT

1. انشر الجسر على HTTPS، واستبدل `https://bridge.example.com` في `integrations/manus-bridge-openapi.yaml` بعنوانك الفعلي.
2. في مساحة ChatGPT التي تسمح بإنشاء GPT/Actions، أنشئ Action من ملف OpenAPI أعلاه.
3. اختر مصادقة Bearer، وأدخل **قيمة `BRIDGE_API_TOKEN` فقط**. لا تدخل `MANUS_API_KEY` في ChatGPT.
4. جرّب `submitManusTask` بطلب اختبار غير تعديلي. احتفظ بـ`task_id`، ثم استدعِ `getManusTaskResult` حتى تصبح الحالة `completed` أو `waiting_for_input`.
5. عند سؤال عادي من Manus، استخدم `sendManusFollowup`. إذا طلب Manus تأكيد إجراء أداة حساسًا، راجع الإجراء في Manus بنفسك؛ الجسر لا ينفذ الموافقة.

موصل GitHub المدمج في ChatGPT يتيح قراءة المستودعات المصرّح بها فقط. لا يستطيع وحده إرسال مهمة أو دفع تعديلات. أداة ChatGPT التي تستدعي هذا الجسر هي قناة الكتابة؛ وموصل GitHub في Manus هو قناة وصول الوكيل إلى المستودع. صلاحيات ChatGPT والخطط لا يمكن فحصها من جلسة Manus، ويجب اختبار ظهور خيار Actions/MCP داخل حسابك.

## توصيل backend الخاص بـNADA AI

يمكن لخادم NADA AI استدعاء الجسر دون كشف `BRIDGE_API_TOKEN` للمتصفح. أضف على خادم NADA فقط متغيري البيئة `MANUS_BRIDGE_URL` (أصل HTTPS للجسر) و`MANUS_BRIDGE_TOKEN` (نفس قيمة `BRIDGE_API_TOKEN` المخزنة في الجسر). لا تضعهما في مستودع Git أو ملفات JavaScript.

بعد ذلك تستخدم الواجهة أو الخدمات الداخلية المسارات المحمية برمز المالك:

- `POST /api/manus/tasks` بجسم `{ "prompt": "...", "title": "..." }` لإنشاء مهمة خاصة.
- `GET /api/manus/tasks/{task_id}` لقراءة الحالة والنتيجة والمرفقات التي وصلت إلى الجسر عبر Webhook.
- `POST /api/manus/tasks/{task_id}/messages` بجسم `{ "content": "..." }` لإرسال متابعة عادية.

الجسر يستقبل Webhooks الموقعة من Manus ويحفظ الحدث قبل أن يقرأ NADA النتيجة. يستطيع backend والواجهة متابعة النتيجة عبر `GET`؛ لا يدعم ChatGPT Actions إشعارات واردة غير مطلوبة إلى المحادثة، لذا يجب على GPT استدعاء أداة القراءة بعد إرسال المهمة أو عند المتابعة. فحص `/api/health` يؤكد قابلية الوصول وإعداد الجسر، لكنه لا يثبت صلاحية مفتاح Manus أو نجاح تسجيل Webhook؛ ذلك يتطلب اختبارًا حيًا بعد الإعداد.

## حماية الأسرار والبيانات

- لا تضع `MANUS_API_KEY` أو `BRIDGE_API_TOKEN` في المستودع أو ملفات Actions أو مطالبات ChatGPT.
- خزّن السرّين في secret manager على الخادم. لا تُفعّل مشاركة ملفات `.env` أو سجلّات البيئة.
- استخدم HTTPS، وقيّد الوصول إلى الجسر، ودوّر `BRIDGE_API_TOKEN` عند الحاجة.
- Webhooks موقّعة من Manus بمفتاح RSA-SHA256؛ يجلب الجسر المفتاح العام من `webhook.publicKey` ويخزّنه مؤقتًا لمدة ساعة.
- SQLite يخزّن نص المهمة والنتائج والمرفقات الوصفية محليًا. استخدم حجمًا مشفّرًا وسياسة احتفاظ مناسبة، ولا تستخدمه كمخزن متعدد المستأجرين.
- الأداة لا تنفذ `task.confirmAction` ولا توافق على نشر أو حذف أو أي إجراء حساس تلقائيًا.

## الاختبارات

من جذر المشروع:

```bash
python3 -m unittest tests.test_manus_bridge -v
```

هذه الاختبارات محلية وبلا اتصال خارجي: تتحقق من التوقيع والتوقيت ومنع الإعادة، والمصادقة، وتخزين Webhooks، وصيغة إنشاء المهمة. الاختبار الحي يتطلب عنوان HTTPS منشورًا ومفتاح Manus API، ولم يُنفذ بعد.
