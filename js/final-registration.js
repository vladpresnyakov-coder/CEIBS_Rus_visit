/* Final documents stay in memory; only same-origin staged API requests. */
(() => {
  "use strict";
  const API = "/api/final-register";
  const MAX_BYTES = 10485760;
  const TYPES = ["image/jpeg", "image/png", "application/pdf"];
  const escape = (value) => String(value).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  function mount(copy, lang) {
    const root = document.getElementById("final-registration");
    if (!root) return;
    const reviewToken = new URLSearchParams(location.hash.slice(1)).get("review") || "";
    if (reviewToken) history.replaceState(null, "", location.pathname + location.search + "#register");
    const t = (key) => escape(copy[key]);
    const field = (id, label, type = "text", required = true) => `<div class="field"><label for="${id}">${escape(label)}${required ? ' <span class="req">*</span>' : ""}</label><input id="${id}" name="${id}" type="${type}" ${required ? "required" : ""} ${type === "text" ? 'maxlength="300"' : ""} aria-describedby="${id}-error"><p class="hint" id="${id}-error"></p></div>`;
    const options = (name, values) => `<div class="choices">${values.map(([value, label]) => `<label class="choice"><input type="radio" name="${name}" value="${value}" required><span>${escape(label)}</span></label>`).join("")}</div>`;
    const journey = (key) => `<fieldset class="final-group"><legend>${t(key)} <span class="req">*</span></legend>${field(`${key}-city`, copy.city)}<div class="field-row">${field(`${key}-date`, copy.date, "date")}${field(`${key}-time`, copy.time, "time")}</div>${field(`${key}-flight`, copy.flight)}</fieldset>`;
    root.innerHTML = `<p class="final-note">${t("requiredNote")}</p><p class="final-note">${t("sessionNote")}</p>
      <p id="final-availability" role="status">${t("checking")}</p>
      <form id="final-form" novalidate autocomplete="off">
        <div id="final-people"></div><button type="button" class="final-secondary" id="final-add">${t("addPerson")}</button>
        <p class="final-note">${t("groupTravel")}</p>${journey("arrival")}${journey("departure")}
        <fieldset class="final-group" id="final-single"><legend>${t("singleRoom")} <span class="req">*</span></legend>${options("singleRoom", [["yes", copy.yes], ["no", copy.no]])}<p class="hint" id="singleRoom-error"></p></fieldset>
        <fieldset class="final-group"><legend>${t("payment")} <span class="req">*</span></legend>${options("paymentMethod", [["alipay", copy.alipay], ["international_transfer", copy.internationalTransfer]])}<p class="final-note">${t("paymentNote")}</p><p class="hint" id="paymentMethod-error"></p></fieldset>
        <div class="field-row">${field("final-phone", copy.phone, "tel")}${field("final-wechat", copy.wechat)}</div>
        <p class="final-note" id="final-privacy">${t("privacy")}</p>
        <label class="final-consent" for="final-consent"><input type="checkbox" id="final-consent" required aria-describedby="final-privacy final-consent-error"><span>${t("consent")} <span class="req">*</span></span></label><p class="hint" id="final-consent-error"></p>
        <p class="form-error" id="final-error" role="alert" tabindex="-1" hidden></p>
        <p class="final-progress" id="final-progress" role="status" aria-live="polite"></p>
        <button class="btn" id="final-submit" type="submit" disabled>${t("submit")}</button>
      </form><div class="thanks" id="final-success" tabindex="-1" hidden><h3>${t("successTitle")}</h3><p>${t("successBody")}</p></div>`;
    const form = root.querySelector("form");
    const peopleRoot = root.querySelector("#final-people");
    const submit = root.querySelector("#final-submit");
    const availability = root.querySelector("#final-availability");
    const errorBox = root.querySelector("#final-error");
    const progress = root.querySelector("#final-progress");
    const single = root.querySelector("#final-single");
    const people = [];
    let nextPerson = 0;
    let draft = null;
    let enabled = false;
    let busy = false;
    let pending = null;

    function roomUI() {
      const solo = people.length === 1;
      single.hidden = !solo;
      single.querySelectorAll("input").forEach((input) => {
        input.required = solo;
        input.disabled = !solo || busy || Boolean(pending);
        if (!solo) input.checked = false;
      });
      root.querySelector("#singleRoom-error").textContent = "";
    }
    function addPerson() {
      const id = `final-person-${nextPerson++}`;
      const node = document.createElement("fieldset");
      node.className = "final-group final-person";
      const person = { node, passportId: null };
      node.innerHTML = `<legend></legend>${field(`${id}-name`, copy.fullName)}<div class="field"><label for="${id}-file">${t("passport")} <span class="req">*</span></label><input id="${id}-file" type="file" accept=".jpg,.jpeg,.png,.pdf,image/jpeg,image/png,application/pdf" required aria-describedby="${id}-hint ${id}-file-error"><p class="final-note" id="${id}-hint">${t("fileHint")}</p><p class="hint" id="${id}-file-error"></p></div>`;
      person.name = node.querySelector('input[type="text"]');
      person.scan = node.querySelector('input[type="file"]');
      person.name.minLength = 2;
      person.name.autocomplete = people.length ? "off" : "name";
      person.scan.addEventListener("change", () => {
        person.passportId = null;
        setError(person.scan, fileError(person.scan));
      });
      if (people.length) {
        const remove = document.createElement("button");
        remove.type = "button";
        remove.className = "final-secondary final-remove";
        remove.textContent = copy.removePerson;
        remove.addEventListener("click", () => {
          if (busy || pending) return;
          people.splice(people.indexOf(person), 1);
          person.passportId = null;
          node.remove();
          renumber();
          roomUI();
          root.querySelector("#final-add").focus();
        });
        node.appendChild(remove);
      }
      people.push(person);
      peopleRoot.appendChild(node);
      renumber();
      roomUI();
      return person;
    }
    function renumber() {
      people.forEach((person, i) => {
        person.node.querySelector("legend").textContent = i === 0 ? copy.primary : copy.companion.replace("{number}", String(i));
      });
    }
    function fileError(input) {
      const file = input.files[0];
      if (!file) return copy.errors.fileRequired;
      if (file.size === 0 || file.size > MAX_BYTES) return copy.errors.fileSize;
      const match = /\.(jpe?g|png|pdf)$/i.exec(file.name);
      const expected = match && ({ jpg: "image/jpeg", jpeg: "image/jpeg", png: "image/png", pdf: "application/pdf" })[match[1].toLowerCase()];
      if (!expected || (file.type && file.type !== expected)) return copy.errors.fileType;
      return "";
    }
    function setError(input, message) {
      const hint = document.getElementById(`${input.id}-error`);
      if (hint) hint.textContent = message;
      input.setAttribute("aria-invalid", message ? "true" : "false");
      input.setCustomValidity(message);
    }
    function validate() {
      let first = null;
      form.querySelectorAll("input").forEach((input) => {
        if (input.disabled) return;
        input.setCustomValidity("");
        let message = "";
        if (input.type === "file") message = fileError(input);
        else if (people.some((p) => p.name === input)) {
          const length = Array.from(input.value).length;
          if (!input.value.trim() || length < 2 || length > 300) message = copy.errors.name;
        } else if (input.type === "checkbox" && !input.checked) message = copy.errors.consent;
        else if (!input.checkValidity() || (input.required && ["text", "tel"].includes(input.type) && !input.value.trim())) message = copy.errors.required;
        if (input.type === "radio") {
          message = form.querySelector(`input[name="${input.name}"]:checked`) ? "" : copy.errors.choice;
          root.querySelector(`#${input.name}-error`).textContent = message;
        }
        setError(input, message);
        if (message && !first) first = input;
      });
      if (first) first.focus();
      return !first;
    }
    function lock() {
      form.querySelectorAll("input, button").forEach((input) => { input.disabled = busy || Boolean(pending); });
      submit.disabled = busy || !enabled;
      submit.textContent = pending ? copy.retrySubmit : copy.submit;
      form.setAttribute("aria-busy", String(busy));
      roomUI();
    }
    function showError(message) {
      errorBox.textContent = message;
      errorBox.hidden = false;
      errorBox.focus();
    }
    async function request(path, options = {}) {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 90000);
      try {
        const response = await fetch(API + path, { ...options, signal: controller.signal, credentials: "same-origin", cache: "no-store", redirect: "error", headers: { Accept: "application/json", ...(reviewToken ? { "X-Registration-Review": reviewToken } : {}), ...options.headers } });
        let data;
        try { data = await response.json(); } catch (_) { data = null; }
        if (!response.ok || !data || data.ok !== true) {
          const error = new Error("request");
          error.status = response.status;
          throw error;
        }
        return data;
      } finally { clearTimeout(timeout); }
    }
    function auth() { return { Authorization: `Bearer ${draft.token}` }; }
    function travel(key) {
      return Object.fromEntries(["city", "date", "time", "flight"].map((name) => [name, form.elements[`${key}-${name}`].value]));
    }
    root.querySelector("#final-add").addEventListener("click", () => {
      if (!busy && !pending) addPerson().name.focus();
    });
    form.addEventListener("input", (event) => {
      const input = event.target;
      if (input instanceof HTMLInputElement && input.type !== "file") {
        setError(input, "");
        if (input.type === "radio") root.querySelector(`#${input.name}-error`).textContent = "";
      }
    });
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (busy || !enabled || (!pending && !validate())) return;
      busy = true;
      errorBox.hidden = true;
      lock();
      let phase = "draft";
      let uploading = null;
      try {
        if (!pending) {
          if (!draft) {
            progress.textContent = copy.creating;
            const result = await request("/drafts", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ lang }) });
            if (typeof result.draftId !== "string" || typeof result.token !== "string" || !/^[0-9a-f-]{36}$/i.test(result.draftId)) throw new Error("draft");
            draft = { draftId: result.draftId, token: result.token };
          }
          phase = "upload";
          for (let i = 0; i < people.length; i += 1) {
            const person = people[i];
            if (person.passportId) continue;
            uploading = person;
            progress.textContent = copy.uploading.replace("{current}", String(i + 1)).replace("{total}", String(people.length));
            const body = new FormData();
            body.append("file", person.scan.files[0]);
            const result = await request(`/drafts/${draft.draftId}/passport`, { method: "POST", headers: auth(), body });
            if (typeof result.passportId !== "string") throw new Error("passport");
            person.passportId = result.passportId;
          }
          pending = {
            lang, people: people.map((p) => ({ fullName: p.name.value, passportId: p.passportId })),
            arrival: travel("arrival"), departure: travel("departure"),
            singleRoom: people.length === 1 ? form.querySelector('input[name="singleRoom"]:checked').value === "yes" : null,
            paymentMethod: form.querySelector('input[name="paymentMethod"]:checked').value,
            phone: form.elements["final-phone"].value, wechat: form.elements["final-wechat"].value, privacyConsent: true,
          };
        }
        phase = "submit";
        progress.textContent = copy.sending;
        const result = await request(`/drafts/${draft.draftId}/submit`, { method: "POST", headers: { ...auth(), "Content-Type": "application/json" }, body: JSON.stringify(pending) });
        if (typeof result.registrationId !== "string") throw new Error("submit");
        form.reset();
        people.forEach((person) => { person.passportId = null; });
        draft = null;
        pending = null;
        enabled = false;
        form.hidden = true;
        availability.hidden = true;
        root.querySelector("#final-success").hidden = false;
        root.querySelector("#final-success").focus();
      } catch (error) {
        const expired = [401, 404, 410].includes(error.status);
        if (expired) {
          draft = null;
          pending = null;
          people.forEach((person) => { person.passportId = null; });
        } else if (phase === "submit" && [400, 413, 415, 422].includes(error.status)) pending = null;
        let message = expired ? copy.errors.expired : pending ? copy.errors.retry : copy.errors.network;
        if (phase === "upload" && [400, 413, 415, 422].includes(error.status)) {
          message = copy.errors.fileRejected;
          if (uploading) setError(uploading.scan, message);
        }
        if (error.status === 503) message = pending ? copy.errors.retry : copy.unavailable;
        if (phase === "submit" && !pending && !expired) message = copy.errors.rejected;
        progress.textContent = "";
        showError(message);
      } finally {
        busy = false;
        lock();
      }
    });
    addPerson();
    request("/config").then((config) => {
      enabled = config.enabled === true && config.maxFileBytes === MAX_BYTES && Array.isArray(config.formats) && TYPES.every((type) => config.formats.includes(type)) && config.retentionDate === "2027-03-02";
      availability.textContent = enabled ? (config.reviewMode ? copy.reviewReady : copy.ready) : copy.unavailable;
      if (config.reviewMode && enabled) root.scrollIntoView();
      lock();
    }).catch(() => {
      enabled = false;
      availability.textContent = copy.unavailable;
      lock();
    });
  }
  window.CEIBSFinalRegistration = Object.freeze({ mount });
})();
