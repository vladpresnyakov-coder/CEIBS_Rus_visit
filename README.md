# Russia in Winter — CEIBS classmates, January 2027

A one-page promo site for a private trip organized by russian cohort GEMBA 2025. English, simplified Chinese, and Russian. It collects pre-registrations.

## Sections

1. **Hero** — Red Square in snow, the two-line headline, dates, a countdown to 24 January 2027 (midnight, Moscow time), and a button to the form.
2. **Four tracks** — Business, Education, Culture, Unique. Guests can mix them. Each track card has its own photo underneath (T-Bank, SKOLKOVO, VDNKh ice, whale).
3. **Why Russia, why winter** — four short points, January temperatures, the Gulf Stream, a clothing checklist, northern lights, and the visa line.
4. **Program** — day by day from 24 to 31 January, the 1–3 February extension, and a horizontal strip of moments.
5. **Pre-registration** — name, whether they will come, phone and WeChat (required unless they chose “I can’t”), accompanying adults/children with ages, places to visit, business interest, and tracks.
6. **Footer** — organizer line and the contact channels filled in `js/config.js` (WeChat QR for Vlad is wired).

## Headline options

The live headline is split in `content/*.json` as `hero.headlineLead` and `hero.headlineRest`. The same alternatives are commented at the top of `js/main.js`.

English:

1. Russia in Winter. / Seen Through Our Eyes. *(this is the one on the page)*
2. Seven Days. / Three Russias. One Private Circle.
3. Come North. / Winter Is When Russia Shows Itself.

中文:

1. 冬天的俄罗斯。 / 我们眼中的样子。
2. 七天。 / 三种俄罗斯，一个小圈子。
3. 往北来。 / 冬天，俄罗斯才像它自己。

Русский:

1. Россия зимой. / Нашими глазами.
2. Семь дней. / Три России. Один свой круг.
3. Приезжайте на север. / Зимой Россия больше всего похожа на себя.

## Run it locally

Open the folder in a terminal. A local server is required, because the page loads its text from JSON and the form posts to `/api/pre-register`.

```bash
cd ~/Desktop/GitHub/CEIBS_Russia
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 server.py
```

Then open [http://127.0.0.1:8080](http://127.0.0.1:8080).

- English: [http://127.0.0.1:8080/](http://127.0.0.1:8080/)
- 中文: [http://127.0.0.1:8080/zh.html](http://127.0.0.1:8080/zh.html)
- Русский: [http://127.0.0.1:8080/ru.html](http://127.0.0.1:8080/ru.html)

Without `DATABASE_URL`, submissions are stored in `data/pre_registrations.sqlite` (gitignored). With `DATABASE_URL` set to a Postgres URL, the same table is written there.

You can still use a plain static server for layout checks only (`python3 -m http.server 4317`), but the form API will not work that way.

The first visit to the English page follows the browser language and remembers the choice in `localStorage` (`ceibs-russia-lang`). A shared link to `zh.html` or `ru.html` stays in that language.

## Deploy to Railway

1. Create a Railway project from this GitHub repo.
2. Add a **PostgreSQL** plugin/service. Railway injects `DATABASE_URL` into the web service — reference that variable on the app service (no need to paste the URL by hand if you link the services).
3. **Build command:** `pip install -r requirements.txt`
4. **Start command:** `python3 server.py`
5. Listen port: `server.py` binds `0.0.0.0:$PORT` (Railway sets `PORT`; default locally is `8080`).
6. On startup the app creates table `pre_registrations` if it does not exist.
7. After each successful insert the server emails a full `.xlsx` export of `pre_registrations` (see SMTP variables below). Missing SMTP config only logs a warning — the form still returns `{ "ok": true }`.

Primary form path: browser `POST /api/pre-register` with the JSON body from `js/main.js` → insert → `{ "ok": true }`. After a successful (or failed) API call the page still shows the thanks screen, opens the WeChat QR when configured, and copies a text summary to the clipboard. If the API fails after one retry, the thanks note explains the clipboard fallback and does not claim the row was saved to the database.

### Railway / env variables

| Variable | Required | Default / example | Purpose |
| --- | --- | --- | --- |
| `DATABASE_URL` | Yes (prod) | from Railway Postgres | Persist pre-registrations |
| `PORT` | No | set by Railway / `8080` locally | Listen port |
| `MAIL_TO` | No | `vlad.presnyakov@gmail.com` | Inbox for the xlsx export |
| `MAIL_FROM` | No | `SMTP_USER`, else `MAIL_TO` | From address |
| `SMTP_HOST` | For email | `smtp.gmail.com` | SMTP server |
| `SMTP_PORT` | For email | `587` | SMTP port (STARTTLS) |
| `SMTP_USER` | For email | your Gmail address | SMTP login |
| `SMTP_PASSWORD` | For email | Gmail **App Password** | SMTP password (not the normal Gmail password) |

**Gmail App Password setup:** Google Account → Security → 2-Step Verification (on) → App passwords → create one for “Mail” → paste the 16-character value into Railway as `SMTP_PASSWORD`. Set `SMTP_USER` to the same Gmail address, `SMTP_HOST=smtp.gmail.com`, `SMTP_PORT=587`. Optionally override `MAIL_TO` / `MAIL_FROM`.

## Deploy to Vercel

The static files can still be hosted on Vercel, but **Vercel will not run `server.py` or write to Postgres**. Prefer Railway for the live form. If you only need a static preview on Vercel:

1. In `index.html`, `zh.html`, and `ru.html`, replace every `https://YOUR_DOMAIN` with the real address, including `https://`. WeChat and WhatsApp need an absolute image URL for the preview. The share image is `images/og.jpg` (under 80 KB).
2. Push the folder to a Git repository, or deploy the folder with the Vercel CLI: `npx vercel`.
3. Vercel serves `index.html` at `/`. `vercel.json` only adds caching and a few security headers.

## Edit the words

All visible copy lives in:

- `content/en.json`
- `content/zh.json`
- `content/ru.json`

The keys match. Change a sentence in all three files, or the missing language will show a blank. Image ids (`redSquare`, `aurora`, `skolkovo`, and the rest) are shared — do not translate them. The list is in `MEDIA` inside `js/main.js`.

To change which photo a day uses, edit that day’s `"image"` value in all three JSON files.

## Form storage (Postgres / SQLite)

Validated submissions `POST` JSON to `/api/pre-register`. The server inserts a row and returns `{ "ok": true }`. On success it also builds an Excel export of the **entire** `pre_registrations` table and emails it when SMTP env vars are set (see Railway section above).

JSON body keys match `payload()` in `js/main.js`: `lang`, `fullName`, `join`, `joinLabel`, `otherDates`, `companies`, `businessInterest`, `phone`, `wechat`, `contact`, `adults`, `children`, `childAges`, `tracks`, `tracksLabels`.

Table `pre_registrations` columns:

| Column | Source |
| --- | --- |
| `full_name` | `fullName` |
| `phone` | `phone` |
| `wechat` | `wechat` |
| `cant` | `true` when `join === "cant"` |
| `join_choice` | `join` (`in` / `likely` / `other` / `cant`) |
| `join_label` | `joinLabel` |
| `other_dates` | `otherDates` |
| `companies` | `companies` (places of interest) |
| `business_interest` | `businessInterest` |
| `adults` / `children` / `child_ages` | companions |
| `tracks` / `tracks_labels` | track ids and labels |
| `contact` | combined phone / WeChat |
| `language` | `lang` |
| `user_agent` | request `User-Agent` |
| `created_at` | server timestamp |
| `raw_json` | full request JSON |

## Optional Google Sheet mirror

The primary path no longer depends on `googleScriptUrl`. You may still paste a Sheet `/exec` URL into `googleScriptUrl` in `js/config.js` as a secondary mirror. While it is empty, submissions only go to `/api/pre-register` (plus the thanks / WeChat / clipboard UX).

Each submission includes `lang` (`en`, `zh`, or `ru`). After send, the page shows “Your pre-registration is accepted.”

1. Create a Google Sheet.
2. Extensions → Apps Script. Delete the sample and paste this:

```javascript
var NOTIFY_EMAIL = "vlad.presnyakov@gmail.com";

function doPost(e) {
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
  var data = JSON.parse(e.postData.contents);
  var headers = [
    "timestamp",
    "lang",
    "fullName",
    "join",
    "joinLabel",
    "otherDates",
    "companies",
    "businessInterest",
    "phone",
    "wechat",
    "contact",
    "adults",
    "children",
    "childAges",
    "tracks",
    "tracksLabels"
  ];
  if (sheet.getLastRow() === 0) {
    sheet.appendRow(headers);
  }
  var row = [
    new Date(),
    data.lang || "",
    data.fullName || "",
    data.join || "",
    data.joinLabel || "",
    data.otherDates || "",
    data.companies || "",
    data.businessInterest || "",
    data.phone || "",
    data.wechat || "",
    data.contact || "",
    data.adults || "",
    data.children || "",
    data.childAges || "",
    data.tracks || "",
    data.tracksLabels || ""
  ];
  sheet.appendRow(row);
  try {
    emailExcelCopy_(sheet, data);
  } catch (err) {
    // Sheet write still succeeded.
  }
  return ContentService
    .createTextOutput(JSON.stringify({ ok: true }))
    .setMimeType(ContentService.MimeType.JSON);
}

function emailExcelCopy_(sheet, latest) {
  var values = sheet.getDataRange().getValues();
  var csv = values.map(function (row) {
    return row.map(function (cell) {
      var text = String(cell == null ? "" : cell);
      if (/[",\n]/.test(text)) return '"' + text.replace(/"/g, '""') + '"';
      return text;
    }).join(",");
  }).join("\n");
  var blob = Utilities.newBlob(csv, "application/vnd.ms-excel", "ceibs-russia-registrations.xls");
  MailApp.sendEmail({
    to: NOTIFY_EMAIL,
    subject: "CEIBS Russia pre-registration: " + (latest.fullName || "new"),
    body: [
      "New pre-registration saved to the sheet.",
      "",
      "Name: " + (latest.fullName || ""),
      "Join: " + (latest.joinLabel || latest.join || ""),
      "Phone: " + (latest.phone || ""),
      "WeChat: " + (latest.wechat || ""),
      "Adults: " + (latest.adults || ""),
      "Children: " + (latest.children || ""),
      "Child ages: " + (latest.childAges || ""),
      "Lang: " + (latest.lang || "")
    ].join("\n"),
    attachments: [blob]
  });
}
```

3. Deploy → New deployment → type: Web app.
4. Execute as: **Me**. Who has access: **Anyone**.
5. Authorize the script when Google asks (including Gmail send permission). Copy the URL that ends in `/exec`.
6. Paste it into `googleScriptUrl` in `js/config.js`.
7. Redeploy the site. Send a test entry from the page.

`join` is a stable code: `in`, `likely`, `other`, `cant`. `joinLabel` is the button text in the guest’s language. `tracks` is the same kind of code list (`business, culture`). `tracksLabels` is the translated names. Phone and WeChat are required unless the guest chose `cant`.

The browser sends the note with `mode: "no-cors"`, because Apps Script does not answer a normal browser preflight. The page treats a completed request as success and cannot read an error body back from Google. If a test row never appears, open the deployment again and confirm access is **Anyone**, then redeploy and use the new `/exec` URL.

### Formspree instead

Create a form at [formspree.io](https://formspree.io), copy the endpoint (`https://formspree.io/f/…`), and put it in `formspreeUrl`. It is used only when `googleScriptUrl` is empty. The same field names arrive as the JSON keys above.

## Contact buttons

In `js/config.js`, fill in `contacts`:

- `wechat` — path to a QR image (for example `images/wechat-qr.webp`; a tap opens the QR), a WeChat ID (a tap copies it), or a full `https://` link
- `whatsapp` — phone number with country code, for example `+79991234567`
- `telegram` — username, without `@`
- `email` — an email address

Empty channels are hidden. Do not invent contact methods that are not configured.

## Swap a photo

1. Export a WebP (or keep the filename and overwrite the file in `images/`).
2. Hero: keep `images/hero-red-square-winter.webp` under about 400 KB. It is the first image and it is not lazy-loaded.
3. If the picture’s shape changed a lot, update `w` and `h` for that id in `MEDIA` in `js/main.js`.
4. After a new hero, rebuild `images/og.jpg` at 1200×630 and replace `https://YOUR_DOMAIN` if the preview should update.
5. Add the author, license, and source URL to `CREDITS.md`.

Placeholders (diver, restaurant interior) are SVG files with a comment at the top describing the exact photo to drop in. Food close-ups and the Arctic boat on the page are real, freely licensed photos, but they were not taken on this trip. Notes are in `CREDITS.md`.

There are no trackers and no cookie banner.
