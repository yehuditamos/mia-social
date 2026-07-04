# Environment Variables — Mia Social

> כל סוד, URL, וטוקן מוגדר דרך env בלבד.
> אין ערכים קשורים (hardcoded) בקוד.

---

## קבצי סביבה

| קובץ | שימוש |
|------|-------|
| `.env.example` | תבנית — נכנסת ל-Git, ללא ערכים אמיתיים |
| `.env` | פיתוח מקומי — לא נכנס ל-Git |
| `.env.production` | Production — מוגדר דרך Render Dashboard / secrets manager |

> סביבת development רצה על Render (לא localhost) — משתני הסביבה מוגדרים ב-Render Dashboard תחת ה-service של dev.

---

## משתני סביבה — רשימה מלאה

### כללי

| משתנה | תיאור | דוגמה |
|--------|-------|-------|
| `APP_ENV` | סביבה פעילה | `development` / `staging` / `production` |
| `BASE_URL` | URL בסיסי של השרת | `https://app.miasocial.co.il` |
| `SECRET_KEY` | מפתח הצפנה של Flask | `random-long-string` |

### WhatsApp Cloud API

| משתנה | תיאור |
|--------|-------|
| `WHATSAPP_VERIFY_TOKEN` | טוקן לאימות Webhook מול Meta |
| `WHATSAPP_ACCESS_TOKEN` | טוקן גישה ל-WhatsApp Cloud API |
| `WHATSAPP_PHONE_NUMBER_ID` | מזהה מספר הטלפון בעסק |
| `WHATSAPP_BUSINESS_ACCOUNT_ID` | מזהה חשבון העסק |

### Meta OAuth (פייסבוק + אינסטגרם)

| משתנה | תיאור |
|--------|-------|
| `META_APP_ID` | App ID מ-Meta Developer Console |
| `META_APP_SECRET` | App Secret — לעולם לא בקוד |
| `META_OAUTH_REDIRECT_URI` | `/auth/meta/callback` — URL מלא לפי סביבה |

### AI

| משתנה | תיאור |
|--------|-------|
| `ANTHROPIC_API_KEY` | מפתח לשימוש ב-Claude (Copy Worker, Vision Worker) |

### Database

| משתנה | תיאור |
|--------|-------|
| `DATABASE_URL` | connection string מלא |

### Storage

| משתנה | תיאור |
|--------|-------|
| `STORAGE_BUCKET` | שם ה-bucket לאחסון מדיה |
| `STORAGE_ACCESS_KEY` | מפתח גישה |
| `STORAGE_SECRET_KEY` | מפתח סודי |

---

## ערכים לפי סביבה

> אין ngrok. Render משמש מהיום הראשון — URL יציב וקבוע לאורך כל הפיתוח.

### Development (Render)
```env
APP_ENV=development
BASE_URL=https://mia-social-backend.onrender.com
META_OAUTH_REDIRECT_URI=https://mia-social-backend.onrender.com/auth/meta/callback
```

### Production
```env
APP_ENV=production
BASE_URL=https://app.miasocial.co.il
META_OAUTH_REDIRECT_URI=https://app.miasocial.co.il/auth/meta/callback
```

---

## כללים

1. `.env` לעולם לא נכנס ל-Git — מופיע ב-`.gitignore`
2. `META_APP_SECRET` ו-`ANTHROPIC_API_KEY` לא מועברים ל-frontend לעולם
3. `access_token` של משתמשות מוצפן לפני שמירה ב-DB
4. בייצור — כל הסודות דרך secrets manager, לא קובץ flat
