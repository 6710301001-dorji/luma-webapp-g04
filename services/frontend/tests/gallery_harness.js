// รัน gallery.js ตัวจริงบน DOM จำลอง + fetch/confirm ที่ควบคุมได้ แล้วพิมพ์ผลเป็น JSON บรรทัดสุดท้าย
// เรียกจาก test_gallery.py:  node gallery_harness.js <scenario> <path/to/gallery.js>
const fs = require("fs");
const vm = require("vm");
const [scenario, scriptPath] = process.argv.slice(2);

function el() {
  const handlers = {};
  return {
    textContent: "", className: "", type: "", disabled: false, attrs: {}, children: [],
    set innerHTML(v) { if (v === "") this.children = []; }, get innerHTML() { return ""; },
    setAttribute(k, v) { this.attrs[k] = v; }, removeAttribute(k) { delete this.attrs[k]; },
    appendChild(c) { this.children.push(c); }, addEventListener(t, fn) { handlers[t] = fn; },
    fire(t, e = {}) { return handlers[t](e); },
  };
}

const find = (node, cls) => node.className === cls ? node : node.children.map((c) => find(c, cls)).find(Boolean);
const tick = () => new Promise((r) => setTimeout(r, 0));

(async () => {
  const nodes = {};
  for (const id of ["gallery-grid", "gallery-search-form", "gallery-search-input", "gallery-prev-btn",
    "gallery-next-btn", "gallery-page-indicator", "gallery-empty", "gallery-error"]) nodes[id] = el();

  const calls = [];
  const alerts = [];
  let deleteReply = { ok: true, status: 200, body: { status: "deleted", asset_id: 7 } };
  const list = { items: [{ id: 7, prompt: "a cat", image_url: "/api/assets/7/image", created_at: null }], page: 1, total: 1 };

  const fetch = async (url, opts = {}) => {
    calls.push({ url: String(url), method: opts.method || "GET", headers: opts.headers || {} });
    if (opts.method === "DELETE") {
      return { ok: deleteReply.ok, status: deleteReply.status, json: async () => deleteReply.body };
    }
    return { ok: true, status: 200, json: async () => list };
  };

  const ctx = {
    window: {
      location: { origin: "http://luma.test" },
      csrfHeaders: () => ({ "X-CSRFToken": "tok" }),
      confirm: () => scenario !== "cancel",
    },
    URL, console: { error() {}, log() {} }, alert: (m) => alerts.push(m), fetch, setTimeout,
    document: { readyState: "complete", getElementById: (id) => nodes[id] || null, createElement: () => el() },
  };
  vm.createContext(ctx);
  vm.runInContext(fs.readFileSync(scriptPath, "utf8"), ctx);
  await tick();

  if (scenario === "fail") deleteReply = { ok: false, status: 404, body: { error: "ไม่พบภาพที่ระบุ / Asset not found" } };

  const card = nodes["gallery-grid"].children[0];
  const button = find(card, "asset-card__delete");
  await button.fire("click");
  await tick();

  const del = calls.find((c) => c.method === "DELETE");
  console.log(JSON.stringify({
    has_button: Boolean(button),
    delete_url: del ? del.url : null,
    csrf: del ? del.headers["X-CSRFToken"] || null : null,
    reloads: calls.filter((c) => c.method === "GET").length,
    alerts,
    button_disabled: button.disabled,
  }));
})();
