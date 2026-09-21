// รัน generate.js / canvas.js ตัวจริงบน DOM จำลอง + fetch ที่ควบคุมได้ แล้วพิมพ์ผลเป็น JSON บรรทัดสุดท้าย
// เรียกจาก test_canvas_generate.py:  node canvas_generate_harness.js <scenario> <path/to/file.js>
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
    window: {}, console: { error() {}, log() {} }, alert: (m) => alerts.push(m), fetch: fetchImpl,
    document: { readyState: "complete", getElementById: (id) => nodes[id] || null, createElement: () => el(), addEventListener() {} },
    ...extra,
  };
  vm.createContext(ctx);
  vm.runInContext(fs.readFileSync(scriptPath, "utf8"), ctx);
  return alerts;
}

const reply = (ok, body) => async () => ({ ok, status: ok ? 200 : 502, json: async () => body });

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

async function canvas() {
  const nodes = {};
  for (const id of ["canvas-upload-input", "canvas-preview-container", "canvas-preview-img", "canvas-placeholder",
    "btn-remove-bg", "btn-extract-palette", "palette-swatches"]) nodes[id] = el();
  nodes["palette-container"] = el({ hidden: "" });
  let next = reply(true, { colors: ["#112233", "#445566"] });
  class FileReader { readAsDataURL() { this.onload({ target: { result: "data:image/png;base64,AAAA" } }); } }
  const alerts = load(nodes, (...a) => next(...a), { FileReader });
  const upload = () => nodes["canvas-upload-input"].fire("change", { target: { files: [{}] } });
  const palette = () => ({ swatches: nodes["palette-swatches"].children.length, hidden: "hidden" in nodes["palette-container"].attrs });

  upload();
  await nodes["btn-extract-palette"].fire("click");
  const afterSuccess = palette();

  if (scenario === "palette_fail_after_success") {
    next = reply(false, { error: "AI engine down" });
    await nodes["btn-extract-palette"].fire("click");
  } else if (scenario === "upload_after_success") {
    upload();
  }
  return { afterSuccess, after: palette(), alerts: alerts.length };
}

(async () => {
  const result = scenario === "seed_zero" ? await seed() : await canvas();
  console.log(JSON.stringify(result));
})();
