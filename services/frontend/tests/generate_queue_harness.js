// รัน generate.js ตัวจริงกับคิว (#21): POST ได้ 202 + job_id แล้ว poll GET /api/jobs/<id>
// เรียกจาก test_generate_queue.py:  node generate_queue_harness.js <scenario> <path/to/generate.js>
const fs = require("fs");
const vm = require("vm");
const [scenario, scriptPath] = process.argv.slice(2);

function el() {
  const h = {};
  return {
    textContent: "", value: "", disabled: false, src: "", style: {}, attrs: {}, classList: { add() {}, remove() {} },
    setAttribute(k, v) { this.attrs[k] = v; }, removeAttribute(k) { delete this.attrs[k]; },
    appendChild() {}, addEventListener(t, f) { h[t] = f; }, fire(t, e) { return h[t](e); },
  };
}

const form = el();
for (const [k, v] of Object.entries({ prompt: "a fox", negative_prompt: "", steps: "20", cfg_scale: "8",
  sampler_name: "Euler a", seed: "-1", width: "512", height: "512" })) form[k] = { value: v };
const n = { "generate-form": form };
for (const id of ["generate-submit", "generate-error", "generate-spinner", "preview-container", "preview-image",
  "preview-placeholder", "preview-meta", "meta-asset-id", "meta-prompt"]) n[id] = el();
n["generate-error"].attrs.hidden = "";

const polls = { done: ["pending", "running", "done"], failed: ["pending", "running", "failed"] }[scenario] || [];
const calls = [];
const spinnerTexts = [];
const reply = (status, body) => ({ ok: status < 400, status, json: async () => body });
const fetch = async (url, opts = {}) => {
  calls.push(`${opts.method || "GET"} ${url}`);
  if (opts.method === "POST") {
    return scenario === "rejected"
      ? reply(400, { error: "steps ต้องอยู่ระหว่าง 1-50" })
      : reply(202, { status: "queued", job_id: 12 });
  }
  const status = polls.shift();
  spinnerTexts.push(n["generate-spinner"].textContent);
  if (status === "done") return reply(200, { status, asset_id: 30, image_url: "/api/assets/30/image", error: null });
  if (status === "failed") return reply(200, { status, asset_id: null, image_url: null, error: "เชื่อมต่อ AI engine ไม่สำเร็จ / Could not reach AI engine" });
  return reply(200, { status, asset_id: null, image_url: null, error: null });
};

const ctx = {
  window: { csrfHeaders: () => ({ "X-CSRFToken": "tok" }) }, console: { error() {} }, fetch,
  setTimeout: (fn) => fn(), // poll ทันที ไม่ต้องรอ 1.5 วินาทีจริง
  document: { readyState: "complete", getElementById: (id) => n[id] || null, createElement: el, addEventListener() {} },
};
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(scriptPath, "utf8"), ctx);

(async () => {
  await form.fire("submit", { preventDefault() {}, stopPropagation() {} });
  spinnerTexts.push(n["generate-spinner"].textContent);
  console.log(JSON.stringify({
    calls,
    spinner_texts: spinnerTexts,
    image_src: n["preview-image"].src,
    asset_id: n["meta-asset-id"].textContent,
    error: "hidden" in n["generate-error"].attrs ? null : n["generate-error"].textContent,
    button_disabled: n["generate-submit"].disabled,
  }));
})();
