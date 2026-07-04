# Architecture — Mia Social

> מיה לא בנויה סביב פלטפורמות. היא בנויה סביב יכולות.
> לכל יכולה יש Worker עצמאי. Mia Brain מתאמת ביניהם.

---

## עקרון מרכזי

```
❌  לא:  Mia → Instagram Service → Meta API
✅  כן:  Mia Brain → Copy Worker + Publish Worker → כל פלטפורמה
```

Workers הם יכולות. פלטפורמות הן יעדים. הם נפרדים.

---

## System Flow

```
WhatsApp (User)
      │
      ▼
  Webhook  (/webhook)
      │  validates, parses, dispatches
      ▼
┌─────────────────────────────┐
│         Mia Brain           │
│  (orchestrator / router)    │
└──────────────┬──────────────┘
               │
       ┌───────┴────────────────────────────────────────┐
       │                                                │
       ▼                                                ▼
  [by intent]                                    [by need]
       │                                                │
  ┌────┴─────────────────────────────────────────────┐  │
  │                   Workers                        │  │
  │                                                  │  │
  │  👀 Vision Worker      — מבין תמונות וסרטונים   │  │
  │  ✍️  Copy Worker       — כותב כיתובים            │  │
  │  🎬 Media Worker       — עורך מדיה, כתוביות      │  │
  │  📤 Publish Worker     — מפרסם לפלטפורמות        │  │
  │  💬 Community Worker   — מטפל בתגובות            │  │
  │  📈 Analytics Worker   — קורא נתוני ביצועים      │  │
  │  📅 Planner Worker     — גאנט ותזמון             │  │
  │  ♿ Accessibility Worker— תיאורי תמונות, ALT      │  │
  │  🧠 Memory Worker      — זוכר את העסק            │  │
  └──────────────────────────────────────────────────┘
               │
               ▼
      Meta API / Storage / DB
```

---

## Workers — הגדרות

### 👀 Vision Worker
קולט מדיה (תמונה / וידאו) ומחזיר תיאור מובנה: נושא, אווירה, אנשים, טקסט בתמונה.
משמש את Copy Worker ואת Accessibility Worker.

### ✍️ Copy Worker
כותב כיתובים, כותרות, תגובות, וסטוריז.
מבוסס על פרופיל העסק מ-Memory Worker.
מחזיר וריאנטים — מיה מציגה אחד ומאפשרת עריכה בשיחה.

### 🎬 Media Worker
מורד מדיה מ-WhatsApp, ממיר פורמטים, מוסיף כתוביות לסרטונים.
מכין את המדיה לפרסום לפי דרישות כל פלטפורמה.

### 📤 Publish Worker
מפרסם מיידי או מתוזמן לכל פלטפורמה.
מקבל: media_url + caption + platform + scheduled_at.
מחזיר: platform_post_id.

### 💬 Community Worker
מאזין לתגובות חדשות בפוסטים.
מסווג לפי סנטימנט, מציע תגובה, שולח למשתמשת לאישור.

### 📈 Analytics Worker
שולף reach, engagement, impressions מ-Meta API.
מסכם ושולח דוח שבועי למשתמשת.

### 📅 Planner Worker
מנהל גאנט תוכן — מתי מפרסמים, מה, לאיזה פלטפורמה.
מתאם עם Publish Worker לביצוע.

### ♿ Accessibility Worker
יוצר תיאורי Alt לכל תמונה.
בודק שהכיתוב קריא ונגיש.

### 🧠 Memory Worker
שומר את פרופיל העסק, העדפות המשתמשת, היסטוריית פרסומים.
כל Worker שואל אותו לפני פעולה.

---

## OAuth & Webhook URLs

### Callback Route
```
POST /auth/meta/callback
```
מקבל את ה-`code` מ-Meta אחרי שהמשתמשת אישרה הרשאות.
מחליף `code` ל-`access_token` ושומר ב-DB.

### Webhook Route
```
GET  /webhook   — אימות מול Meta (hub.verify_token)
POST /webhook   — קבלת הודעות נכנסות
```

### URLs לפי סביבה

| סביבה | Base URL | OAuth Redirect URI | Webhook URL |
|-------|----------|--------------------|-------------|
| development | `https://mia-dev.onrender.com` | `https://mia-dev.onrender.com/auth/meta/callback` | `https://mia-dev.onrender.com/webhook` |
| production | `https://app.miasocial.co.il` | `https://app.miasocial.co.il/auth/meta/callback` | `https://app.miasocial.co.il/webhook` |

> כל URL מוגדר דרך env בלבד — אין URL קשור (hardcoded) בקוד.
> אין ngrok. Render משמש מהיום הראשון — URL יציב וקבוע.

### הפרדת סביבות

```
.env.development   — Render (mia-dev)
.env.production    — הדומיין הסופי
```

משתנה `APP_ENV` קובע איזה קובץ נטען.
בקוד: `os.getenv("APP_ENV")` — ואף URL לא מופיע ישירות.

---

## הגדרת Redirect URI ב-Meta Developer Console

Meta דורש רישום מראש של כל Redirect URI מורשה.
יש לרשום את שני ה-URIs (development/production) תחת:
**App → Facebook Login → Valid OAuth Redirect URIs**

ה-URL יציב ולא משתנה — אין צורך לעדכן בכל סשן.

---

## Data Flow — OAuth

```
User (WhatsApp)
  │ כותבת "חברי את פייסבוק"
  ▼
Mia Brain
  │ מייצרת OAuth URL עם state token
  ▼
User מקבלת קישור ולוחצת
  │
  ▼
Meta Authorization Dialog
  │ המשתמשת מאשרת
  ▼
Meta → GET /auth/meta/callback?code=XXX&state=YYY
  │
  ▼
Backend מחליף code → access_token
  │
  ▼
Memory Worker שומר token מוצפן
  │
  ▼
Mia Brain שולחת אישור למשתמשת ב-WhatsApp
```
