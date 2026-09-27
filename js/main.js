/* Headline options. The live lines are hero.headlineLead / headlineRest in content/*.json.
   English:
     1. Russia in Winter. / Seen Through Our Eyes.
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
*/

const PAGE_LANG = document.documentElement.dataset.lang || "en";
const ARRIVAL = new Date("2027-01-24T00:00:00+03:00");

const MEDIA = {
  redSquare: { src: "images/hero-red-square-winter.webp", w: 1600, h: 1067 },
  basil: { src: "images/basil-snow-night.webp", w: 1400, h: 2109 },
  coast: { src: "images/teriberka-coast.webp", w: 1400, h: 746 },
  aurora: { src: "images/teriberka-aurora.webp", w: 1400, h: 1750 },
  hermitage: { src: "images/hermitage-neva-winter.webp", w: 1400, h: 1050 },
  peterhof: { src: "images/peterhof-winter.webp", w: 1400, h: 1106 },
  palace: { src: "images/winter-palace-night.webp", w: 1400, h: 933 },
  petersburg: { src: "images/petersburg-winter-bridge.webp", w: 1600, h: 1200 },
  yandex: { src: "images/yandex-hq.webp", w: 1600, h: 1200 },
  rover: { src: "images/yandex-rover.webp", w: 1400, h: 1050 },
  sber: { src: "images/sber-hq.webp", w: 1600, h: 1200 },
  skolkovo: { src: "images/skolkovo-disk.webp", w: 1600, h: 1200 },
  campusCollage: { src: "images/campus-collage.webp", w: 2400, h: 834 },
  tinkoff: { src: "images/tinkoff-office.webp", w: 1059, h: 585 },
  vdnkhIce: { src: "images/vdnkh-ice.webp", w: 927, h: 812 },
  whale: { src: "images/whale-fluke.webp", w: 1200, h: 1178 },
  festival: { src: "images/winter-festival.webp", w: 1600, h: 1227 },
  crowns: { src: "images/crowns-regalia.webp", w: 1600, h: 1243 },
  kremlin: { src: "images/kremlin-winter.webp", w: 1600, h: 1066 },
  izba: { src: "images/izba-tea.webp", w: 1600, h: 1066 },
  lenin: { src: "images/icebreaker-lenin.webp", w: 1400, h: 933 },
  uni: { src: "images/sea-urchin.webp", w: 1400, h: 1050 },
  crab: { src: "images/king-crab.webp", w: 1400, h: 1050 },
  scallop: { src: "images/scallop-plate.webp", w: 1400, h: 1543 },
  boat: { src: "images/rocky-shore.webp", w: 1600, h: 1200 },
  diver: { src: "images/arctic-diver.webp", w: 1200, h: 1600 },
  club: { src: "images/moscow-club.webp", w: 1600, h: 1069 },
  creative: { src: "images/placeholder-creative-studio.svg", w: 900, h: 1200 },
  dining: { src: "images/izba-tea.webp", w: 1600, h: 1066 },
  plate: { src: "images/russian-plate.webp", w: 1600, h: 1059 },
  wechatQr: { src: "images/wechat-qr.webp", w: 888, h: 1191 },
};

const TRACK_PHOTOS = {
  business: "tinkoff",
  education: "skolkovo",
  culture: "vdnkhIce",
  unique: "whale",
};

const DAY_FRAME = {
  jan24: "center 45%",
  jan25: "center",
  jan26: "center 40%",
  jan27: "center",
  jan28: "center 28%",
  jan29: "center",
  jan30: "center 36%",
  jan31: "center 42%",
};

const ICONS = {
  business: `<svg viewBox="0 0 32 32" aria-hidden="true"><path d="M6 26V8.5A2.5 2.5 0 0 1 8.5 6h9A2.5 2.5 0 0 1 20 8.5V26"/><path d="M20 14h3.5A2.5 2.5 0 0 1 26 16.5V26"/><path d="M4 26h24M10 11h6M10 15h6M10 19h4"/></svg>`,
  education: `<svg viewBox="0 0 32 32" aria-hidden="true"><path d="M5 14 16 8l11 6-11 6-11-6Z"/><path d="M10 16.2V22c2.2 1.8 9.8 1.8 12 0v-5.8"/></svg>`,
  culture: `<svg viewBox="0 0 32 32" aria-hidden="true"><path d="M7 26V14a9 9 0 0 1 18 0v12"/><path d="M6 26h20"/><path d="M13 26v-5a3 3 0 0 1 6 0v5"/></svg>`,
  unique: `<svg viewBox="0 0 32 32" aria-hidden="true"><path d="M5 22c3.2-7 6-7.2 8.2-1.6 2.2 5.4 4.2 7 7.4.6 2.2-4.4 4.6-5.4 6.4-5.4"/><circle cx="24" cy="8" r="1.3" fill="currentColor" stroke="none"/></svg>`,
};

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[ch]));
}

function imgHTML(id, alt, options) {
  const media = MEDIA[id];
  if (!media) return "";
  const opts = options || {};
  const lazy = opts.eager ? 'fetchpriority="high"' : 'loading="lazy"';
  const pos = opts.position ? ` style="object-position:${esc(opts.position)}"` : "";
  const sizes = opts.sizes ? ` sizes="${esc(opts.sizes)}"` : "";
  return `<img src="${esc(media.src)}" alt="${esc(alt || "")}" width="${media.w}" height="${media.h}" ${lazy} decoding="async"${sizes}${pos}>`;
}

function isBlank(text) {
  const value = String(text || "").trim();
  return value === "" || value === "—" || value === "-" || value === "–";
}

function render(copy) {
  document.title = copy.meta.title;
  const brand = document.getElementById("brand");
  const nav = document.getElementById("nav-links");
  const headerCta = document.getElementById("header-cta");
  const skip = document.querySelector(".skip");
  if (skip) skip.textContent = copy.skip;
  if (brand) brand.textContent = copy.nav.brand;
  if (headerCta) headerCta.textContent = copy.nav.register;
  if (nav) {
    nav.innerHTML = ["tracks", "why", "program", "register"]
      .map((key) => {
        const href = key === "register" ? "#register" : `#${key}`;
        return `<a href="${href}">${esc(copy.nav[key])}</a>`;
      })
      .join("");
  }
  const langNav = document.querySelector(".lang");
  if (langNav) langNav.setAttribute("aria-label", copy.nav.langLabel);

  const heroImg = document.querySelector(".hero-img");
  if (heroImg) heroImg.alt = copy.hero.imageAlt;

  document.getElementById("hero-copy").innerHTML = `
    <p class="eyebrow">${esc(copy.hero.eyebrow)}</p>
    <h1><span class="line">${esc(copy.hero.headlineLead)}</span><span class="line">${esc(copy.hero.headlineRest)}</span></h1>
    <p class="hero-dates">${esc(copy.hero.dates)}</p>
    <p class="subline">${esc(copy.hero.subline)}</p>
    <div class="hero-actions"><a class="btn" href="#register">${esc(copy.hero.cta)}</a></div>
    <div class="countdown" role="timer" aria-label="${esc(copy.hero.countdownLabel)}">
      <p class="countdown-label" id="countdown-label">${esc(copy.hero.countdownLabel)}</p>
      <div class="ticks" id="ticks">
        ${["days", "hours", "minutes", "seconds"].map((unit) => `
          <div><span data-unit="${unit}">00</span><small>${esc(copy.hero[unit])}</small></div>
        `).join("")}
      </div>
    </div>
  `;

  const tracks = copy.tracks.items.map((item, index) => {
    const photoId = TRACK_PHOTOS[item.id];
    const photoAlt = (copy.tracks.photoAlts && copy.tracks.photoAlts[item.id]) || item.title;
    return `
    <article class="track reveal">
      ${ICONS[item.id] || ""}
      <h3>${esc(item.title)}</h3>
      <p>${esc(item.text)}</p>
      ${photoId ? `<div class="track-photo">${imgHTML(photoId, photoAlt, { sizes: "(min-width: 980px) 22vw, (min-width: 720px) 45vw, 100vw" })}</div>` : ""}
    </article>
  `;
  }).join("");

  const days = copy.program.days.map((day) => `
    <li class="day reveal" id="${esc(day.id)}">
      <div class="day-photo">${imgHTML(day.image, day.imageAlt, { position: DAY_FRAME[day.id] || "center", sizes: "(min-width: 980px) 40vw, 100vw" })}</div>
      <div class="day-body">
        <div class="day-top">
          <p class="day-date"><span class="day-num">${esc(day.dayNum)}</span><span class="day-when">${esc(day.weekday)} · ${esc(day.month)}</span></p>
          <p class="day-city">${esc(day.city)}</p>
          <p class="hotel"><span>${esc(copy.program.hotel)}</span>${esc(day.hotel)}</p>
        </div>
        <div class="slots">
          ${slot(copy.program.morning, day.morning)}
          ${slot(copy.program.afternoon, day.afternoon)}
          ${slot(copy.program.evening, day.evening)}
        </div>
      </div>
    </li>
  `).join("");

  const gallery = copy.program.gallery.map((item) => `
    <figure class="shot">
      ${imgHTML(item.image, item.alt, { sizes: "(min-width: 720px) 240px, 78vw" })}
      <figcaption>${item.placeholder ? `<span class="badge">${esc(copy.program.photoToAdd)}</span>` : ""}${esc(item.caption)}</figcaption>
    </figure>
  `).join("");

  const join = copy.form.joinOptions.map((option) => `
    <label class="choice">
      <input type="radio" name="join" value="${esc(option.id)}" />
      <span>${esc(option.label)}</span>
    </label>
  `).join("");

  const checks = copy.tracks.items.map((item) => `
    <label class="check">
      <input type="checkbox" name="tracks" value="${esc(item.id)}" />
      <span>${esc(item.title)}</span>
    </label>
  `).join("");

  document.getElementById("rest").innerHTML = `
    <section class="section" id="tracks">
      <div class="wrap">
        <p class="eyebrow">${esc(copy.tracks.eyebrow)}</p>
        <h2>${esc(copy.tracks.title)}</h2>
        <p class="lede">${esc(copy.tracks.intro)}</p>
        <div class="track-grid has-photos">${tracks}</div>
        <p class="tracks-caption">${esc(copy.tracks.campusCaption)}</p>
      </div>
    </section>
    <section class="section why" id="why">
      <div class="wrap why-grid">
        <figure class="why-photo reveal">
          ${imgHTML(copy.why.image, copy.why.imageAlt, { sizes: "(min-width: 980px) 50vw, 100vw" })}
          <div class="temps">
            ${copy.why.temps.map((temp) => `<div><strong>${esc(temp.value)}</strong><span>${esc(temp.place)}</span></div>`).join("")}
          </div>
          <p class="temps-note">${esc(copy.why.tempsNote)}</p>
        </figure>
        <div>
          <p class="eyebrow">${esc(copy.why.eyebrow)}</p>
          <h2>${esc(copy.why.title)}</h2>
          <ol class="points">
            ${copy.why.points.map((point) => `<li class="reveal"><h3>${esc(point.title)}</h3><p>${esc(point.text)}</p></li>`).join("")}
          </ol>
        </div>
      </div>
      <p class="visa wrap">${esc(copy.why.visa)}</p>
    </section>
    <section class="section program" id="program">
      <div class="wrap">
        <p class="eyebrow">${esc(copy.program.eyebrow)}</p>
        <h2>${esc(copy.program.title)}</h2>
        <ol class="days">${days}</ol>
        <p class="extension">${esc(copy.program.extension)}</p>
        ${!isBlank(copy.program.backup) ? `
        <aside class="backup">
          ${copy.program.backupImage ? imgHTML(copy.program.backupImage, copy.program.backupAlt, { sizes: "(min-width: 720px) 220px, 100vw" }) : ""}
          <p>${esc(copy.program.backup)}</p>
        </aside>` : ""}
      </div>
      <div class="wrap gallery-head">
        <h3>${esc(copy.program.galleryTitle)}</h3>
        <p class="gallery-hint">${esc(copy.program.galleryHint)}</p>
      </div>
      <div class="gallery" tabindex="0" aria-label="${esc(copy.program.galleryTitle)}">${gallery}</div>
    </section>
    <section class="register" id="register">
      <div class="wrap register-grid">
        <div>
          <p class="eyebrow">${esc(copy.form.eyebrow)}</p>
          <h2>${esc(copy.form.title)}</h2>
          <p class="lede">${esc(copy.form.intro)}</p>
        </div>
        <div>
          <form id="pre-form" novalidate>
            <div class="field" data-field="name">
              <label for="full-name">${esc(copy.form.name)} <span class="req">*</span></label>
              <input id="full-name" name="fullName" type="text" autocomplete="name" required placeholder="${esc(copy.form.namePlaceholder)}" />
              <p class="hint" data-error="name"></p>
            </div>
            <fieldset class="field" data-field="join">
              <legend>${esc(copy.form.join)} <span class="req">*</span></legend>
              <div class="choices">${join}</div>
              <p class="hint" data-error="join"></p>
            </fieldset>
            <div class="field" data-field="otherDates" id="other-dates-field" hidden>
              <label for="other-dates">${esc(copy.form.otherDates)} <span class="req">*</span></label>
              <input id="other-dates" name="otherDates" type="text" placeholder="${esc(copy.form.otherDatesPlaceholder)}" />
              <p class="hint" data-error="otherDates"></p>
            </div>
            <div class="field">
              <label for="companies">${esc(copy.form.companies)}</label>
              <textarea id="companies" name="companies" placeholder="${esc(copy.form.companiesPlaceholder)}"></textarea>
            </div>
            <div class="field">
              <label for="interest">${esc(copy.form.interest)}</label>
              <textarea id="interest" name="businessInterest" placeholder="${esc(copy.form.interestPlaceholder)}"></textarea>
            </div>
            <div class="field-row" id="contact-fields">
              <div class="field" data-field="phone">
                <label for="phone">${esc(copy.form.phone)} <span class="req contact-req">*</span></label>
                <input id="phone" name="phone" type="tel" autocomplete="tel" placeholder="${esc(copy.form.phonePlaceholder)}" />
                <p class="hint" data-error="phone"></p>
              </div>
              <div class="field" data-field="wechat">
                <label for="wechat">${esc(copy.form.wechat)} <span class="req contact-req">*</span></label>
                <input id="wechat" name="wechat" type="text" autocomplete="off" placeholder="${esc(copy.form.wechatPlaceholder)}" />
                <p class="hint" data-error="wechat"></p>
              </div>
            </div>
            <fieldset class="field companions" id="companions-fields">
              <legend>${esc(copy.form.companions)}</legend>
              <div class="field-row">
                <div class="field">
                  <label for="adults">${esc(copy.form.adults)}</label>
                  <input id="adults" name="adults" type="number" min="0" max="20" step="1" inputmode="numeric" placeholder="0" />
                </div>
                <div class="field">
                  <label for="children">${esc(copy.form.children)}</label>
                  <input id="children" name="children" type="number" min="0" max="20" step="1" inputmode="numeric" placeholder="0" />
                </div>
              </div>
              <div class="field" data-field="childAges" id="child-ages-field" hidden>
                <label for="child-ages">${esc(copy.form.childAges)} <span class="req">*</span></label>
                <input id="child-ages" name="childAges" type="text" placeholder="${esc(copy.form.childAgesPlaceholder)}" />
                <p class="hint" data-error="childAges"></p>
              </div>
            </fieldset>
            <fieldset class="field">
              <legend>${esc(copy.form.tracks)}</legend>
              <div class="checks">${checks}</div>
            </fieldset>
            <div class="hp" aria-hidden="true">
              <label>${esc(copy.form.honeypot)} <input type="text" name="website" tabindex="-1" autocomplete="off" /></label>
            </div>
            <p class="form-error" id="form-error" role="alert" hidden></p>
            <button class="btn" type="submit" id="submit-btn">${esc(copy.form.submit)}</button>
          </form>
          <div class="thanks" id="thanks" hidden tabindex="-1">
            <h3>${esc(copy.form.thanksTitle)}</h3>
            <p>${esc(copy.form.thanksBody)}</p>
            <p data-thanks-note hidden></p>
          </div>
        </div>
      </div>
    </section>
  `;

  document.getElementById("footer").innerHTML = `
    <div class="wrap">
      <p class="org">${esc(copy.footer.organized)}</p>
      <div class="contacts" id="contacts"></div>
      <p class="copied" id="copied" aria-live="polite"></p>
      <p class="prelim">${esc(copy.footer.preliminary)}</p>
    </div>
  `;

  renderContacts(copy);
  bindForm(copy);
  bindCountdown(copy);
  bindReveal();
}

function slot(label, text) {
  const empty = isBlank(text);
  return `<div><h3>${esc(label)}</h3><p class="${empty ? "is-empty" : ""}">${esc(text)}</p></div>`;
}

function renderContacts(copy) {
  const contacts = (typeof CEIBS_CONFIG !== "undefined" && CEIBS_CONFIG.contacts) || {};
  const root = document.getElementById("contacts");
  const items = [
    { key: "wechat", label: copy.footer.wechat },
    { key: "whatsapp", label: copy.footer.whatsapp },
    { key: "telegram", label: copy.footer.telegram },
    { key: "email", label: copy.footer.email },
  ];
  const rendered = items.map((item) => {
    const href = contactHref(item.key, contacts);
    if (!href) return "";
    if (item.key === "wechat" && isQrPath(href)) {
      return `<button type="button" class="contact" data-wechat-qr="${esc(href)}">${esc(item.label)}</button>`;
    }
    if (item.key === "wechat" && !/^https?:/i.test(href)) {
      return `<button type="button" class="contact" data-wechat="${esc(href)}">${esc(item.label)}</button>`;
    }
    return `<a class="contact" href="${esc(href)}" ${item.key === "email" ? "" : 'target="_blank" rel="noopener noreferrer"'}>${esc(item.label)}</a>`;
  }).filter(Boolean);
  root.innerHTML = rendered.join("");

  const note = document.getElementById("copied");
  root.querySelectorAll("[data-wechat]").forEach((button) => {
    button.addEventListener("click", async () => {
      const id = button.getAttribute("data-wechat");
      try {
        await navigator.clipboard.writeText(id);
        note.textContent = copy.footer.copied;
      } catch (err) {
        note.textContent = id;
      }
    });
  });
  root.querySelectorAll("[data-wechat-qr]").forEach((button) => {
    button.addEventListener("click", () => {
      openWechatQr(button.getAttribute("data-wechat-qr"), copy);
    });
  });
}

function isQrPath(value) {
  return /\.(webp|png|jpe?g|gif|svg)(\?.*)?$/i.test(String(value || "").trim())
    || /^images\//i.test(String(value || "").trim());
}

function openWechatQr(src, copy) {
  const existing = document.getElementById("wechat-modal");
  if (existing) existing.remove();
  const modal = document.createElement("div");
  modal.id = "wechat-modal";
  modal.className = "wechat-modal";
  modal.setAttribute("role", "dialog");
  modal.setAttribute("aria-modal", "true");
  modal.setAttribute("aria-label", copy.footer.wechat);
  modal.innerHTML = `
    <button type="button" class="wechat-modal-backdrop" aria-label="${esc(copy.footer.closeQr || "Close")}"></button>
    <div class="wechat-modal-card">
      <img src="${esc(src)}" alt="${esc(copy.footer.wechatQrAlt || copy.footer.wechat)}" width="888" height="1191" />
      <button type="button" class="btn wechat-modal-close">${esc(copy.footer.closeQr || "Close")}</button>
    </div>
  `;
  document.body.appendChild(modal);
  const close = () => modal.remove();
  modal.querySelector(".wechat-modal-backdrop").addEventListener("click", close);
  modal.querySelector(".wechat-modal-close").addEventListener("click", close);
  document.addEventListener("keydown", function onKey(event) {
    if (event.key === "Escape") {
      close();
      document.removeEventListener("keydown", onKey);
    }
  });
}

function contactHref(key, contacts) {
  const raw = String(contacts[key] || "").trim();
  if (!raw) return "";
  if (key === "email") return `mailto:${raw}`;
  if (key === "whatsapp") return `https://wa.me/${raw.replace(/[^\d]/g, "")}`;
  if (key === "telegram") return `https://t.me/${raw.replace(/^@/, "")}`;
  return raw;
}

function bindForm(copy) {
  const form = document.getElementById("pre-form");
  const otherField = document.getElementById("other-dates-field");
  const childAgesField = document.getElementById("child-ages-field");
  const contactFields = document.getElementById("contact-fields");
  const companionsFields = document.getElementById("companions-fields");
  const errorBox = document.getElementById("form-error");

  function syncJoinUi() {
    const selected = form.querySelector('input[name="join"]:checked');
    const isOther = selected && selected.value === "other";
    const isCant = selected && selected.value === "cant";
    otherField.hidden = !isOther;
    if (contactFields) contactFields.hidden = Boolean(isCant);
    if (companionsFields) companionsFields.hidden = Boolean(isCant);
    form.querySelectorAll(".contact-req").forEach((node) => {
      node.hidden = Boolean(isCant);
    });
    const children = Number(form.children.value || 0);
    childAgesField.hidden = isCant || !(children > 0);
  }

  form.addEventListener("change", syncJoinUi);
  form.addEventListener("input", (event) => {
    if (event.target && event.target.name === "children") syncJoinUi();
  });
  syncJoinUi();

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const errors = validate(form, copy);
    paintErrors(form, errors);
    if (Object.keys(errors).length) {
      const first = form.querySelector(".is-invalid input, .is-invalid textarea");
      if (first) first.focus();
      return;
    }
    if (form.website.value.trim()) {
      showThanks();
      return;
    }
    const button = document.getElementById("submit-btn");
    button.disabled = true;
    button.textContent = copy.form.sending;
    errorBox.hidden = true;
    try {
      const body = payload(form, copy);
      const result = await send(body);
      showThanks(result && result.via === "local" ? copy.form.thanksLocalNote : "");
      if (result && result.via === "local") {
        await finishLocalSubmission(body, copy);
      }
    } catch (err) {
      errorBox.hidden = false;
      errorBox.textContent = copy.form.errors.network;
      button.disabled = false;
      button.textContent = copy.form.submit;
    }
  });
}

function validate(form, copy) {
  const errors = {};
  const name = form.fullName.value.trim();
  if (name.length < 2) errors.name = copy.form.errors.name;
  const selected = form.querySelector('input[name="join"]:checked');
  if (!selected) errors.join = copy.form.errors.join;
  if (selected && selected.value === "other" && form.otherDates.value.trim().length < 2) {
    errors.otherDates = copy.form.errors.otherDates;
  }
  if (selected && selected.value !== "cant") {
    if (form.phone.value.trim().length < 5) errors.phone = copy.form.errors.phone;
    if (form.wechat.value.trim().length < 2) errors.wechat = copy.form.errors.wechat;
    const children = Number(form.children.value || 0);
    if (children > 0 && form.childAges.value.trim().length < 1) {
      errors.childAges = copy.form.errors.childAges;
    }
  }
  return errors;
}

function paintErrors(form, errors) {
  form.querySelectorAll("[data-field]").forEach((field) => {
    const key = field.getAttribute("data-field");
    const hint = field.querySelector("[data-error]");
    field.classList.toggle("is-invalid", Boolean(errors[key]));
    if (hint) hint.textContent = errors[key] || "";
  });
}

function payload(form, copy) {
  const data = new FormData(form);
  const selected = form.querySelector('input[name="join"]:checked');
  const option = copy.form.joinOptions.find((item) => item.id === selected.value);
  const trackIds = data.getAll("tracks");
  const labels = copy.tracks.items.filter((item) => trackIds.includes(item.id)).map((item) => item.title);
  const cant = selected.value === "cant";
  const phone = cant ? "" : String(data.get("phone") || "").trim();
  const wechat = cant ? "" : String(data.get("wechat") || "").trim();
  const adults = cant ? "" : String(data.get("adults") || "").trim();
  const children = cant ? "" : String(data.get("children") || "").trim();
  const childAges = cant || !(Number(children) > 0) ? "" : String(data.get("childAges") || "").trim();
  return {
    lang: PAGE_LANG,
    fullName: data.get("fullName").trim(),
    join: selected.value,
    joinLabel: option ? option.label : "",
    otherDates: selected.value === "other" ? data.get("otherDates").trim() : "",
    companies: String(data.get("companies") || "").trim(),
    businessInterest: String(data.get("businessInterest") || "").trim(),
    phone,
    wechat,
    contact: [phone, wechat].filter(Boolean).join(" / "),
    adults,
    children,
    childAges,
    tracks: trackIds.join(", "),
    tracksLabels: labels.join(" | "),
  };
}

async function send(body) {
  const config = typeof CEIBS_CONFIG !== "undefined" ? CEIBS_CONFIG : {};
  const google = String(config.googleScriptUrl || "").trim();
  const formspree = String(config.formspreeUrl || "").trim();
  if (google) {
    await fetch(google, {
      method: "POST",
      mode: "no-cors",
      headers: { "Content-Type": "text/plain;charset=utf-8" },
      body: JSON.stringify(body),
    });
    return { via: "google" };
  }
  if (formspree) {
    const response = await fetch(formspree, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(body),
    });
    if (!response.ok) throw new Error("network");
    return { via: "formspree" };
  }
  /* Interim: accept locally until googleScriptUrl is set in js/config.js. */
  return { via: "local" };
}

function formatSubmissionSummary(body) {
  const lines = [
    "CEIBS Russia pre-registration",
    `Language: ${body.lang || ""}`,
    `Name: ${body.fullName || ""}`,
    `Join: ${body.joinLabel || body.join || ""}`,
  ];
  if (body.otherDates) lines.push(`Other dates: ${body.otherDates}`);
  if (body.companies) lines.push(`Companies: ${body.companies}`);
  if (body.businessInterest) lines.push(`Business interest: ${body.businessInterest}`);
  if (body.phone) lines.push(`Phone: ${body.phone}`);
  if (body.wechat) lines.push(`WeChat: ${body.wechat}`);
  if (body.adults !== "") lines.push(`Adults: ${body.adults}`);
  if (body.children !== "") lines.push(`Children: ${body.children}`);
  if (body.childAges) lines.push(`Child ages: ${body.childAges}`);
  if (body.tracksLabels) lines.push(`Tracks: ${body.tracksLabels}`);
  return lines.join("\n");
}

async function finishLocalSubmission(body, copy) {
  const summary = formatSubmissionSummary(body);
  console.log("[CEIBS pre-registration]", body);
  try {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(summary);
    }
  } catch (_) {
    /* Clipboard may be blocked; thanks + WeChat QR still work. */
  }
  const contacts = (typeof CEIBS_CONFIG !== "undefined" && CEIBS_CONFIG.contacts) || {};
  const wechat = String(contacts.wechat || "").trim();
  if (wechat && isQrPath(wechat)) {
    openWechatQr(wechat, copy);
  }
}

function showThanks(extraNote) {
  const form = document.getElementById("pre-form");
  const thanks = document.getElementById("thanks");
  form.hidden = true;
  thanks.hidden = false;
  const note = thanks.querySelector("[data-thanks-note]");
  if (note) {
    const text = String(extraNote || "").trim();
    note.textContent = text;
    note.hidden = !text;
  }
  thanks.focus();
}

function bindCountdown(copy) {
  const ticks = document.getElementById("ticks");
  const label = document.getElementById("countdown-label");
  let timer = 0;
  const units = ["days", "hours", "minutes", "seconds"];

  function paint() {
    const diff = ARRIVAL.getTime() - Date.now();
    if (diff <= 0) {
      label.textContent = copy.hero.countdownDone;
      ticks.hidden = true;
      clearInterval(timer);
      timer = 0;
      return;
    }
    const total = Math.floor(diff / 1000);
    const values = {
      days: Math.floor(total / 86400),
      hours: Math.floor((total % 86400) / 3600),
      minutes: Math.floor((total % 3600) / 60),
      seconds: total % 60,
    };
    units.forEach((unit) => {
      const node = ticks.querySelector(`[data-unit="${unit}"]`);
      if (node) node.textContent = String(values[unit]).padStart(2, "0");
    });
  }

  function arm() {
    if (timer) return;
    paint();
    timer = setInterval(paint, 1000);
  }

  arm();
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) {
      clearInterval(timer);
      timer = 0;
    } else {
      arm();
    }
  });
}

function bindReveal() {
  const nodes = document.querySelectorAll(".reveal");
  if (!("IntersectionObserver" in window) || window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    nodes.forEach((node) => node.classList.add("is-in"));
    return;
  }
  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      entry.target.classList.add("is-in");
      observer.unobserve(entry.target);
    });
  }, { threshold: 0.16 });
  nodes.forEach((node) => observer.observe(node));
}

function bindHeader() {
  const header = document.getElementById("header");
  const onScroll = () => header.classList.toggle("is-scrolled", window.scrollY > 12);
  onScroll();
  window.addEventListener("scroll", onScroll, { passive: true });
}

async function init() {
  bindHeader();
  try {
    const response = await fetch(`content/${PAGE_LANG}.json`);
    if (!response.ok) throw new Error("load");
    const copy = await response.json();
    render(copy);
  } catch (err) {
    const rest = document.getElementById("rest");
    const fallback = {
      en: "The page text did not load. Refresh and try again.",
      zh: "页面文字没有载入。请刷新后再试。",
      ru: "Текст страницы не загрузился. Обновите страницу.",
    };
    rest.innerHTML = `<p class="load-error">${esc(fallback[PAGE_LANG] || fallback.en)}</p>`;
  }
}

init();
