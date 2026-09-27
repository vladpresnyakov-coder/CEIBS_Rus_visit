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

Open the folder in a terminal. A local server is required, because the page loads its text from JSON. Opening the HTML file directly will not work.

```bash
cd ~/Desktop/GitHub/CEIBS_Russia
python3 -m http.server 4317
```

Then open [http://127.0.0.1:4317](http://127.0.0.1:4317).

- English: [http://127.0.0.1:4317/](http://127.0.0.1:4317/)
- 中文: [http://127.0.0.1:4317/zh.html](http://127.0.0.1:4317/zh.html)
- Русский: [http://127.0.0.1:4317/ru.html](http://127.0.0.1:4317/ru.html)

The first visit to the English page follows the browser language and remembers the choice in `localStorage` (`ceibs-russia-lang`). A shared link to `zh.html` or `ru.html` stays in that language.

## Deploy to Vercel

The site is static. No build step.

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

## Connect the form to a Google Sheet

The endpoint is the `googleScriptUrl` string in `js/config.js`. Leave it empty until the sheet is ready. If it is empty and `formspreeUrl` is also empty, the form tells the guest to message Vlad instead of pretending the note was sent.

Each submission includes `lang` (`en`, `zh`, or `ru`), so you can see which language they used. After a successful send, the page shows “Your pre-registration is accepted.”

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
