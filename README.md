# הדף

עיתון יומי של עמוד אחד. עובדות, בלי רעש.

הדף נכתב, נערך ונבדק כל בוקר על ידי Claude, בלי עורך אנושי. אין פרסומות, אין תוכן ממומן, אין מעקב. כל גיליון נבדק לפני פרסום על ידי מופע נפרד של Claude שפותח את המקור של כל טענה, ודוח הבדיקה נשמר כאן לצד הגיליון.

- **[מדיניות העריכה](POLICY.md)** — מה נכנס, מה לא, ולמה.
- **[הגיליונות](issues/)** — כל גיליון, המקורות שלו ודוח הבדיקה שלו.

## עיתון משלך

העיתון הזה הוא בעצם קובץ הוראות. כדי לייצר עיתון משלך:

1. עשה fork לריפו.
2. ערוך את `newspaper.toml`: שם, שפה, מדורים, אורך, קהל, מקורות ונושאים שלא נכנסים.
3. אם אתה רוצה לשנות את אופי העיתון עצמו, ערוך את הסקיל `.claude/skills/editor/SKILL.md`, ועדכן בהתאם את `POLICY.md` כדי שהקוראים יידעו.
4. מחק את התיקייה `issues/` (הגיליון הראשון שלך יקבל את המספר 1).
5. הפעל GitHub Pages: Settings › Pages › Source: **GitHub Actions**.
6. חבר את Claude: ב־Claude Code, בתוך הריפו, הרץ `/install-github-app` ובחר בטוקן של המנוי שלך. זה שומר את הסוד `CLAUDE_CODE_OAUTH_TOKEN` בריפו (את ה־PR שהוא פותח אפשר לסגור).

זהו. ה־workflow ‏`Daily issue` רץ כל בוקר, ואפשר להריץ אותו גם ידנית מלשונית Actions.

## איך זה עובד

הכל רץ ב־GitHub Actions, ב־workflow אחד (`.github/workflows/daily.yml`):

1. **איסוף, בלי AI.** `scripts/fetch_news.py` קורא את פידי ה־RSS שב־`newspaper.toml` (כ־25 כלי תקשורת ומקורות מדע וטכנולוגיה), את העמוד הראשי של Hacker News ואת "היום לפני" מוויקיפדיה, ושומר את הטקסט המלא של כל כתבה בתיקייה אחת: הצרור של היום. `scripts/fetch_data.py` מושך מזג אוויר, שערים וזמני שבת.
2. **עריכה, בלי גישה לרשת.** Claude רץ דרך Claude Code GitHub Action, על המנוי שלך, ועובד רק מהצרור. סוכני איסוף (Sonnet) עוברים על הצרור לפי מדור, העורך (Opus) בוחר וכותב, ומאמת נפרד בודק כל טענה מול טקסט הכתבה. לכל טענה נשמר ציטוט מדויק מהמקור.
3. **שער איכות.** `scripts/check_issue.py` בודק שכל ציטוט באמת מופיע בכתבה, שהמאמת לא פסל, ושיש לפחות 5 ידיעות. אם לא, לא מתפרסם כלום באותו יום, וה־workflow נכשל (GitHub שולח מייל).
4. **פרסום.** הגיליון נשמר בריפו והאתר נבנה מחדש.

```
newspaper.toml                       ← ההעדפות: מדורים, פידים, ערים, מודלים
.claude/skills/editor/               ← כללי העריכה: מה נכנס, איך כותבים, פורמט הקובץ
.claude/skills/gather/               ← האוספים: סוכן לכל מדור, מתוך הצרור
.claude/skills/fact-check/           ← המאמת: בודק כל טענה מול טקסט הכתבה
.claude/skills/publish-issue/        ← התהליך היומי, מקצה לקצה
issues/YYYY/MM/DD.md                 ← הגיליון
issues/YYYY/MM/DD.sources.json       ← לכל טענה: הכתבה וציטוט מדויק ממנה
issues/YYYY/MM/DD.check.md           ← דוח המאמת
issues/YYYY/MM/DD.notes.md           ← מה נכנס, מה נפל ולמה
issues/YYYY/MM/DD.data.json          ← נתוני תיבת השירות
scripts/fetch_news.py                ← בונה את הצרור היומי
scripts/fetch_data.py                ← נתוני השירות
scripts/check_issue.py               ← שער האיכות
scripts/build.py                     ← בונה את האתר: גיליון, ארכיון, מדיניות, RSS
templates/base.html                  ← העיצוב
```

הצרור עצמו לא נשמר בריפו; הוא נשמר כ־artifact של ה־workflow למשך 14 יום.

הבנייה מקומית: `python3 scripts/build.py` (Python 3.11 ומעלה, בלי תלויות).

---

**English.** A one-page daily newspaper written, edited and fact-checked by Claude, with no human editor, no ads and no tracking. A script collects the day's feeds and article texts; Claude, running in GitHub Actions on your subscription with no web access, writes and verifies the issue from that bundle only; a gate script checks every quote against its article before anything is published. Fork it, edit `newspaper.toml`, enable GitHub Pages (source: GitHub Actions), and run `/install-github-app` in Claude Code to add the `CLAUDE_CODE_OAUTH_TOKEN` secret.
