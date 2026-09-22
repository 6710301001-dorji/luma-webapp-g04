// รัน img2img.js ตัวจริงบน DOM + canvas จำลอง แล้วพิมพ์ผลเป็น JSON บรรทัดสุดท้าย
// เรียกจาก test_img2img_page.py:  node img2img_harness.js <scenario> <path/to/img2img.js>
const fs = require("fs");
const vm = require("vm");
const [scenario, scriptPath] = process.argv.slice(2);

let offscreen = 0;

// context ปลอม: จำว่ามีการวาดเส้นกี่ครั้ง — getImageData คืนพิกเซลที่ "ถูกระบาย" ตามจำนวนเส้น
function context(canvas) {
  return {
    strokes: 0, cleared: 0, images: 0, put: null,
    clearRect() { this.cleared += 1; this.strokes = 0; },
    drawImage() { this.images += 1; },
    beginPath() {}, moveTo() {}, lineTo() {}, stroke() { this.strokes += 1; },
    getImageData(x, y, w, h) {
      const data = new Uint8ClampedArray(w * h * 4);
      for (let i = 0; i < Math.min(this.strokes * 10, w * h); i++) data[i * 4 + 3] = 255;
      return { data };
    },
    createImageData(w, h) { return { data: new Uint8ClampedArray(w * h * 4) }; },
    putImageData(img) { this.put = img; canvas.white = img.data.filter((v, i) => i % 4 === 0 && v === 255).length; },
  };
}

function el(id, attrs = {}) {
  const handlers = {};
  const classes = new Set();
  const node = {
    id, value: "", textContent: "", disabled: false, attrs: { ...attrs }, src: "", width: 0, height: 0, white: 0,
    classList: { add: (c) => classes.add(c), remove: (c) => classes.delete(c), has: (c) => classes.has(c) },
    setAttribute(k, v) { this.attrs[k] = v; }, removeAttribute(k) { delete this.attrs[k]; },
    addEventListener(t, fn) { handlers[t] = fn; }, fire(t, e = {}) { return handlers[t](e); },
    getContext() { return this.ctx || (this.ctx = context(this)); },
    getBoundingClientRect() { return { left: 0, top: 0, width: this.width / 2, height: this.height / 2 }; },
    toDataURL() { return this.id === "mask-export" ? `mask:white=${this.white}` : `canvas:${this.id}`; },
  };
  return node;
}

class Image {
  set src(v) { this._src = v; this.naturalWidth = 2000; this.naturalHeight = 1000; this.onload(); }
  get src() { return this._src; }
}
class FileReader { readAsDataURL() { this.onload({ target: { result: "data:image/png;base64,AAAA" } }); } }

(async () => {
  const ids = ["i2i-form", "i2i-upload", "i2i-mode", "i2i-mode-hint", "i2i-brush", "i2i-brush-size", "i2i-brush-size-value",
    "i2i-brush-color", "i2i-color-group", "i2i-clear", "i2i-strength", "i2i-strength-value", "i2i-stage", "i2i-placeholder",
    "i2i-base", "i2i-mask", "i2i-error", "i2i-submit", "i2i-result", "i2i-result-img", "i2i-prompt", "i2i-negative",
    "i2i-steps", "i2i-cfg", "i2i-seed"];
  const n = Object.fromEntries(ids.map((id) => [id, el(id)]));
  Object.assign(n["i2i-mode"], { value: "text" });
  Object.assign(n["i2i-strength"], { value: "0.7" });
  Object.assign(n["i2i-brush-size"], { value: "24" });
  Object.assign(n["i2i-brush-color"], { value: "#ff3b30" });
  Object.assign(n["i2i-steps"], { value: "20" });
  Object.assign(n["i2i-cfg"], { value: "8" });
  Object.assign(n["i2i-seed"], { value: "-1" });
  for (const id of ["i2i-error", "i2i-result", "i2i-brush", "i2i-base", "i2i-mask"]) n[id].attrs.hidden = "";

  const calls = [];
  const reply = scenario === "server_error"
    ? { ok: false, status: 400, json: async () => ({ error: "mask ต้องขนาดเท่าภาพต้นฉบับ / mask must match init_image size" }) }
    : { ok: true, status: 200, json: async () => ({ status: "success", asset_id: 9, image_url: "/api/assets/9/image" }) };
  const fetch = async (url, opts) => { calls.push({ url, headers: opts.headers, body: JSON.parse(opts.body) }); return reply; };

  const ctx = {
    window: { csrfHeaders: () => ({ "X-CSRFToken": "tok" }) }, console: { error() {}, log() {} }, fetch, Image, FileReader,
    document: {
      readyState: "complete",
      getElementById: (id) => n[id] || null,
      createElement: () => el(offscreen++ === 0 ? "original" : "mask-export"),
    },
  };
  vm.createContext(ctx);
  vm.runInContext(fs.readFileSync(scriptPath, "utf8"), ctx);

  const upload = () => n["i2i-upload"].fire("change", { target: { files: [{}] } });
  const setMode = (m) => { n["i2i-mode"].value = m; n["i2i-mode"].fire("change"); };
  const stroke = () => {
    n["i2i-mask"].fire("pointerdown", { clientX: 10, clientY: 10, pointerId: 1 });
    n["i2i-mask"].fire("pointermove", { clientX: 40, clientY: 30 });
    n["i2i-mask"].fire("pointerup", {});
  };
  const submit = async () => { await n["i2i-form"].fire("submit", { preventDefault() {} }); };
  n["i2i-prompt"].value = "a fox";

  if (scenario !== "no_image") upload();
  if (scenario === "inpaint_no_stroke") setMode("inpaint");
  if (scenario === "inpaint_stroke") { setMode("inpaint"); stroke(); }
  if (scenario === "sketch") { setMode("sketch"); stroke(); }
  if (scenario === "mode_change_clears") { setMode("inpaint"); stroke(); setMode("text"); setMode("inpaint"); }
  await submit();

  const sent = calls[0] || null;
  console.log(JSON.stringify({
    calls: calls.length,
    url: sent && sent.url,
    csrf: sent && sent.headers["X-CSRFToken"],
    body: sent && sent.body,
    canvas: [n["i2i-base"].width, n["i2i-base"].height],
    base_strokes: n["i2i-base"].getContext().strokes,
    mask_strokes: n["i2i-mask"].getContext().strokes,
    error: "hidden" in n["i2i-error"].attrs ? null : n["i2i-error"].textContent,
    result_src: "hidden" in n["i2i-result"].attrs ? null : n["i2i-result-img"].src,
    button_disabled: n["i2i-submit"].disabled,
    brush_hidden: "hidden" in n["i2i-brush"].attrs,
  }));
})();
