# ملاحظات توثيق مزودي الوسائط

تمت المراجعة في 2026-10-07. تُستخدم هذه الملاحظات لتطبيق التكامل فقط؛ لم يُرسل أي طلب توليد مدفوع أثناء البحث أو التطوير.

## Kling

المصدر الرسمي: https://kling.ai/document-api/api/get-started/authentication

- نطاق API الموثق للمستخدمين خارج الصين هو `https://api-singapore.klingai.com`؛ صفحة التوثيق تنبه إلى أن النطاق تغيّر من `https://api.klingai.com`.
- المصادقة الحالية هي API Key في ترويسة `Authorization: Bearer <API_KEY>`. توثيق Kling يصف Access Key/Secret Key كمعيار legacy فقط، ولذلك يستخدم مخزن الحسابات قيمة سرية واحدة لحساب Kling.
- التوثيق يعد المفتاح شديد الحساسية ويوصي بحفظه في متغير بيئة وعدم كشفه.

المصدر الرسمي لمسار الفيديو: https://kling.ai/document-api/api/video/3-0-omni/text-to-video

- إنشاء مهمة Text-to-Video في Kling 3.0 Omni: `POST /text-to-video/kling-3.0`.
- الحقول الموثقة تشمل `prompt` (مطلوب، حد أقصى 3072 محرفاً) وكائن `settings` الاختياري؛ طول الفيديو 3–15 ثانية، والدقة 720p/1080p/4k، ونسب العرض 16:9 أو 9:16 أو 1:1.
- الاستجابة غير متزامنة وتتضمن `data.id` و`data.status` وحالات مثل submitted/processing/succeeded/failed.
- الاستعلام يتم عبر `GET /tasks?external_task_ids=<id>`، ويعيد قائمة `data` مع `status` و`outputs[].type=video` و`outputs[].url`. رابط الفيديو مؤقت ويُحذف بعد 30 يوماً؛ ينزله الخادم فور اكتمال المهمة عند تنفيذ الأنبوب.

## ElevenLabs

المصدر الرسمي للمصادقة: https://elevenlabs.io/docs/api-reference/authentication

- ترويسة المصادقة هي `xi-api-key: <API_KEY>`.
- المثال الرسمي يستخدم `GET https://api.elevenlabs.io/v1/models`، وهو فحص قراءة مناسب للتحقق من المفتاح دون طلب توليد صوت.
- مفاتيح ElevenLabs يمكن تقييدها حسب النطاق/الـ credits/عناوين IP، وينص التوثيق على عدم كشفها في client-side code.

المصدر الرسمي لتحويل النص لصوت: https://elevenlabs.io/docs/api-reference/text-to-speech/convert

- توليد الصوت: `POST https://api.elevenlabs.io/v1/text-to-speech/{voice_id}` مع `xi-api-key` وJSON يتضمن `text`؛ الاستجابة ملف صوتي.
- فحص الاتصال يستخدم نقطة قراءة فقط؛ عملية التوليد نفسها لا تحدث إلا بعد تأكيد المالك للنموذج.

## قرارات تطبيقية

- يحتفظ backend بالمفاتيح مشفرة في SQLite؛ لا يعيدها إلى المتصفح ولا يكتبها في سجل النشاط.
- فحص الاتصال يبقى طلباً غير مولد؛ توليد الصوت والفيديو ينفذ فقط بعد إرسال نموذج المالك صراحة، ويجب إظهار تنبيه استهلاك الرصيد في الواجهة.
- عند `429` أو خطأ رصيد/حزمة `402`/`1101`/`1102` أو رفض اعتماد `401`/`403`، يُوقَف الحساب المتأثر في SQLite ويُجرّب حساب نشط آخر مرة واحدة كحد أقصى لكل حساب ضمن طلب التوليد الحالي؛ تُعاد قائمة الحسابات الموقوفة للواجهة.
- يعالج `Retry-After` كمدة توقف مؤقتة لحالات المعدل إذا توفر (والافتراضي 60 ثانية)؛ نفاد الرصيد/الحزمة ورفض الاعتماد يبقيان موقوفين حتى مراجعة المالك وإعادة تفعيل الحساب. لا يُعاد الطلب بعد خطأ شبكة مبهم أو خطأ مدخلات، ولا يُسجل أي مفتاح أو نص رد مزود كامل في سجل النشاط.

## مواصفات التنفيذ المطلوبة

- Kling 3.0: `POST https://api-singapore.klingai.com/text-to-video/kling-3.0`; body يحوي `prompt` (حد أقصى 3072 محرفاً) و`settings` الرسمية للدقة والمدة والنسبة والصوت، ويعيد `data.id` وحالة غير متزامنة. يستخدم `options.external_task_id` UUID داخلياً فريداً لكل الحساب.
- Kling polling: `GET https://api-singapore.klingai.com/tasks?external_task_ids=<id>`؛ الحالات `submitted`, `processing`, `succeeded`, `failed`. رابط الفيديو الناتج مؤقت، وتذكر الوثيقة أن النتيجة تزال بعد 30 يوماً.
- ElevenLabs speech: `POST https://api.elevenlabs.io/v1/text-to-speech/{voice_id}?output_format=...`, headers `xi-api-key` و`Content-Type: application/json`, body يتضمن `text` و`model_id`; response bytes صوتية.
- رموز Kling الرسمية: 1101/1102 لحساب متأخر أو حزمة موارد منتهية (HTTP 429)، و1302/1303 لتجاوز معدل/تزامن (HTTP 429)، و1000–1004 للمصادقة (HTTP 401)، و1103 لعدم السماح بالموارد (HTTP 403). 1100 استثناء حالة حساب، و1304 سياسة whitelist للـ IP؛ تُحفظ أسباب التوقف ولا تُسجل ردود المزود الكاملة.
- دمج الصوت: Kling Text-to-Video يقبل `audio=off|native` ولا يقبل رابط صوت خارجي. لذلك يرسل الأنبوب الصوت إلى ElevenLabs والفيديو الصامت إلى Kling، ثم يدمج الملفات محلياً عبر FFmpeg ويطيل آخر إطار إذا طال التعليق الصوتي عن الفيديو. هذا ليس lip-sync. توثيق Kling Lip-Sync يحتاج session/وجه ومقطعاً مرئياً وصوتاً بين 2 و60 ثانية، وهو مسار مختلف غير مستخدم هنا.
