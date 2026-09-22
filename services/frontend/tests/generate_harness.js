// รัน generate.js ตัวจริงบน DOM จำลอง + fetch ที่ควบคุมได้ แล้วพิมพ์ผลเป็น JSON บรรทัดสุดท้าย
// เรียกจาก test_generate_page.py:  node generate_harness.js <scenario> <path/to/generate.js>
const fs = require("fs");
const vm = require("vm");
const [scenario, scriptPath] = process.argv.slice(2);

function el(attrs = {}) {
  const handlers = {};
  return {
    textContent: "", value: "", disabled: false, style: {}, children: [], attrs: { ...attrs },
    classList: { add() {}, remove() {} },
    set innerHTML(v) { if (v === "") this.children = []; }, get innerHTML() { return ""; },
    setAttribute(k, v) { this.attrs[k] = v; }, removeAttribute(k) { delete this.attrs[k]; },
    appendChild(c) { this.children.push(c); }, addEventListener(t, fn) { handlers[t] = fn; },
    fire(t, e = {}) { return handlers[t](e); },
  };
}

function load(nodes, fetchImpl, extra = {}) {
  const alerts = [];
  const ctx = {
    // csrfHeaders มาจาก js/csrf.js (#125) — stub ไว้ให้ JS ที่ใส่ token แล้วรันได้ (ตรวจ token แยกใน test_csrf_headers.py)
    window: { csrfHeaders: () => ({}) }, console: { error() {}, log() {} }, alert: (m) => alerts.push(m), fetch: fetchImpl,
    document: { readyState: "complete", getElementById: (id) => nodes[id] || null, createElement: () => el(), addEventListener() {} },
    ...extra,
  };
  vm.createContext(ctx);
  vm.runInContext(fs.readFileSync(scriptPath, "utf8"), ctx);
  return alerts;
}

async function seed() {
  let sent;
  const form = el();
  const values = { prompt: "cat", negative_prompt: "", steps: "20", cfg_scale: "8", sampler_name: "Euler a", seed: "0", width: "512", height: "512" };
  for (const [k, v] of Object.entries(values)) form[k] = { value: v };
  const nodes = { "generate-form": form };
  for (const id of ["generate-submit", "generate-error", "generate-spinner", "preview-container", "preview-image",
    "preview-placeholder", "preview-meta", "meta-asset-id", "meta-prompt"]) nodes[id] = el();
  load(nodes, async (_, opts) => {
    sent = JSON.parse(opts.body);
    return { ok: true, status: 200, json: async () => ({ image_url: "/api/assets/1/image", asset_id: 1 }) };
  });
  await form.fire("submit", { preventDefault() {}, stopPropagation() {} });
  return { seed: sent.seed };
}

(async () => {
  const result = await seed();
  console.log(JSON.stringify(result));
})();
