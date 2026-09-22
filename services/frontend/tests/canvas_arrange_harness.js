// รัน canvas.js ตัวจริงบน DOM จำลอง: ลากย้าย / ปรับขนาด / เลือกภาพจากแกลเลอรี (#60)
// เรียกจาก test_canvas_arrange.py:  node canvas_arrange_harness.js <scenario> <path/to/canvas.js>
const fs = require("fs");
const vm = require("vm");
const [scenario, scriptPath] = process.argv.slice(2);

function el(attrs = {}) {
  const handlers = {};
  const classes = new Set();
  return {
    textContent: "", value: "", disabled: false, style: {}, children: [], attrs: { ...attrs }, src: "",
    classList: { add: (c) => classes.add(c), remove: (c) => classes.delete(c), has: (c) => classes.has(c) },
    set innerHTML(v) { if (v === "") this.children = []; }, get innerHTML() { return ""; },
    setAttribute(k, v) { this.attrs[k] = v; }, removeAttribute(k) { delete this.attrs[k]; },
    appendChild(c) { this.children.push(c); }, addEventListener(t, fn) { handlers[t] = fn; },
    fire(t, e = {}) { return handlers[t](e); },
  };
}

const tick = () => new Promise((r) => setTimeout(r, 0));

(async () => {
  const nodes = {};
  for (const id of ["canvas-upload-input", "canvas-preview-container", "canvas-preview-img", "canvas-placeholder",
    "btn-remove-bg", "btn-extract-palette", "palette-swatches", "btn-pick-gallery", "gallery-picker",
    "gallery-picker-message", "canvas-scale", "canvas-scale-value", "btn-reset-layout"]) nodes[id] = el();
  nodes["palette-container"] = el({ hidden: "" });
  nodes["gallery-picker"].attrs.hidden = "";
  nodes["gallery-picker-message"].attrs.hidden = "";

  const calls = [];
  const listReply = scenario === "gallery_401"
    ? { ok: false, status: 401, json: async () => ({ error: "Unauthorized" }) }
    : { ok: true, status: 200, json: async () => ({ items: [
      { id: 3, prompt: "a fox", image_url: "/api/assets/3/image" },
      { id: 2, prompt: "a cat", image_url: "/api/assets/2/image" },
    ] }) };
  const fetch = async (url) => {
    calls.push(String(url));
    if (String(url).startsWith("/api/assets?")) return listReply;
    return { ok: true, status: 200, blob: async () => ({ fake: "blob", from: String(url) }) };
  };
  // FileReader คืน Data URL ที่บอกได้ว่ามาจากไฟล์ไหน
  class FileReader {
    readAsDataURL(source) {
      const tag = source.from ? source.from : "upload";
      this.onload({ target: { result: `data:image/png;base64,${tag}` } });
    }
  }

  const ctx = {
    window: { csrfHeaders: () => ({}) }, console: { error() {}, log() {} }, alert() {}, fetch, FileReader,
    document: { readyState: "complete", getElementById: (id) => nodes[id] || null, createElement: () => el(), addEventListener() {} },
  };
  vm.createContext(ctx);
  vm.runInContext(fs.readFileSync(scriptPath, "utf8"), ctx);

  const img = nodes["canvas-preview-img"];
  const upload = () => nodes["canvas-upload-input"].fire("change", { target: { files: [{}] } });
  const state = () => ({
    transform: img.style.transform || "",
    scale_input: nodes["canvas-scale"].value,
    scale_label: nodes["canvas-scale-value"].textContent,
    src: img.src,
    palette_enabled: !nodes["btn-extract-palette"].disabled,
    scale_enabled: !nodes["canvas-scale"].disabled,
  });

  let result = {};
  if (scenario === "drag_and_scale") {
    const before = state();
    img.fire("pointerdown", { clientX: 10, clientY: 10, pointerId: 1 });   // ยังไม่มีภาพ -> ต้องไม่ขยับ
    img.fire("pointermove", { clientX: 90, clientY: 90 });
    const noImage = state();
    upload();
    img.fire("pointerdown", { clientX: 10, clientY: 10, pointerId: 1 });
    img.fire("pointermove", { clientX: 40, clientY: 25 });
    const dragging = img.classList.has("is-dragging");
    img.fire("pointerup", {});
    img.fire("pointermove", { clientX: 200, clientY: 200 });                // ปล่อยแล้ว -> ต้องไม่ขยับต่อ
    const moved = state();
    nodes["canvas-scale"].value = "150";
    nodes["canvas-scale"].fire("input");
    const scaled = state();
    upload();                                                               // ภาพใหม่ -> รีเซ็ต
    const fresh = state();
    result = { before, noImage, dragging, moved, scaled, fresh };
  } else if (scenario === "reset") {
    upload();
    img.fire("pointerdown", { clientX: 0, clientY: 0, pointerId: 1 });
    img.fire("pointermove", { clientX: 5, clientY: 7 });
    img.fire("pointerup", {});
    nodes["canvas-scale"].value = "60";
    nodes["canvas-scale"].fire("input");
    nodes["btn-reset-layout"].fire("click");
    result = state();
  } else {
    await nodes["btn-pick-gallery"].fire("click");
    const picker = nodes["gallery-picker"];
    result = {
      thumbs: picker.children.map((t) => t.src),
      picker_hidden: "hidden" in picker.attrs,
      message: "hidden" in nodes["gallery-picker-message"].attrs ? null : nodes["gallery-picker-message"].textContent,
    };
    if (picker.children.length) {
      await picker.children[1].fire("click");
      await tick();
      result.after_pick = state();
    }
    result.calls = calls;
  }
  console.log(JSON.stringify(result));
})();
