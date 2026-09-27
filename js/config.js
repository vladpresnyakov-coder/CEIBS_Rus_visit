/* One place for endpoints and contact links.
   How to connect the Google Sheet: see README.md. */
const CEIBS_CONFIG = {
  /* Google Apps Script web app URL (/exec). Preferred.
     Script appends rows to the sheet and emails an Excel/CSV copy to
     vlad.presnyakov@gmail.com — paste the /exec URL here once deployed. */
  googleScriptUrl: "",
  /* Formspree endpoint, used only if googleScriptUrl is empty.
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
