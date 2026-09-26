/* One place for endpoints and contact links.
   How to connect the Google Sheet: see README.md. */
const CEIBS_CONFIG = {
  /* Google Apps Script web app URL (/exec). Preferred. */
  googleScriptUrl: "",
  /* Formspree endpoint, used only if googleScriptUrl is empty.
     Example: "https://formspree.io/f/xxxxxxxx" */
  formspreeUrl: "",
  contacts: {
    /* WeChat ID, or a full https:// link to a QR page. */
    wechat: "",
    /* International number, digits only or with +. Example: "+8613800138000" */
    whatsapp: "",
    /* Username without @. */
    telegram: "",
    /* Email address. */
    email: "",
  },
};
