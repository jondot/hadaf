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
6. הגדר משימה מתוזמנת ב־Claude (בענן, מחוברת לריפו שלך) שרצה כל בוקר עם ההוראה:
   > Use the publish-issue skill to produce and publish today's issue.

## איך זה עובד

```
newspaper.toml                       ← ההעדפות של העיתון
.claude/skills/editor/               ← כללי העריכה: מה נכנס, איך כותבים, פורמט הקובץ
.claude/skills/gather/               ← האוספים: סוכן Sonnet לכל מדור, במקביל
.claude/skills/fact-check/           ← המאמת: בודק כל טענה מול המקור שלה
.claude/skills/publish-issue/        ← התהליך היומי, מקצה לקצה
issues/YYYY/MM/DD.md                 ← הגיליון
issues/YYYY/MM/DD.sources.json       ← מקור לכל טענה
issues/YYYY/MM/DD.check.md           ← דוח הבדיקה
scripts/build.py                     ← בונה את האתר: גיליון, ארכיון, מדיניות, RSS
templates/base.html                  ← העיצוב
```

בכל בוקר: Claude בודק מחדש את הגיליון של אתמול ושולח סוכן איסוף לכל מדור במקביל (על Sonnet, כדי לחסוך). העורך (Opus) מסנן לפי כללי העריכה, כותב טיוטה, ומעביר אותה למאמת נפרד. המודל של כל תפקיד מוגדר ב־`newspaper.toml`. אחרי התיקונים הוא דוחף את הגיליון ל־`main`, ו־GitHub Actions בונה ומפרסם את האתר.

הבנייה מקומית: `python3 scripts/build.py` (Python 3.11 ומעלה, בלי תלויות).

---

**English.** A one-page daily newspaper written, edited and fact-checked by Claude, with no human editor, no ads and no tracking. Fork it, edit `newspaper.toml` (and, if you want, the editor skill), enable GitHub Pages with the Actions source, and schedule a daily Claude task in the cloud that runs: *"Use the publish-issue skill to produce and publish today's issue."*
