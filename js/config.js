/* One place for endpoints and contact links.
   Primary store: POST /api/pre-register (server.py → Postgres or local SQLite).
   Optional mirrors: googleScriptUrl / formspreeUrl — see README.md. */
const CEIBS_CONFIG = {
  /* Optional Google Apps Script web app URL (/exec).
     Script appends rows to the sheet and emails an Excel/CSV copy to
     vlad.presnyakov@gmail.com — paste the /exec URL here once deployed.
     Submissions always go to /api/pre-register first; this is a secondary mirror. */
  googleScriptUrl: "",
  /* Optional Formspree endpoint, used only if googleScriptUrl is empty.
     Example: "https://formspree.io/f/xxxxxxxx" */
  formspreeUrl: "",
  contacts: {
    /* Path to WeChat QR image, WeChat ID (tap copies), or https:// link. */
    wechat: "images/wechat-qr.webp",
    /* Leave empty unless you intentionally add that channel. */
    whatsapp: "",
    telegram: "",
    email: "",
  },
};
