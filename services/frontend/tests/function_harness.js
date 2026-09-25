// รัน function.js ตัวจริงบน DOM + canvas จำลอง แล้วพิมพ์ผลเป็น JSON บรรทัดสุดท้าย
// เรียกจาก test_function_page.py:  node function_harness.js <scenario> <path/to/function.js>
const fs = require("fs");
const vm = require("vm");
const [scenario, scriptPath] = process.argv.slice(2);

function el(extra = {}) {
  const handlers = {};
  return {
    textContent: "", value: "", disabled: false, hidden: false, files: null,
    addEventListener(type, fn) { handlers[type] = fn; },
    fire(type, event = {}) { return handlers[type] ? handlers[type](event) : undefined; },
    has(type) { return Boolean(handlers[type]); },
    ...extra,
  };
}

// canvas จำลอง — เก็บคำสั่งวาดไว้ตรวจ และคุม getBoundingClientRect ได้
// displayWidth ต่างจาก width เพื่อจำลองว่า CSS ย่อภาพลง (max-width:100%)
function makeCanvas(displayWidth) {
  const strokes = [];
  const canvas = el({
    width: 0, height: 0,
    getContext: () => ({
      clearRect() {}, drawImage() {}, setLineDash() {},
      strokeRect(x, y, w, h) { strokes.push({ x, y, width: w, height: h }); },
      set lineWidth(v) {}, set strokeStyle(v) {},
    }),
    getBoundingClientRect: () => ({
      left: 0, top: 0,
      width: displayWidth || canvas.width,
      height: (displayWidth || canvas.width) * (canvas.height / (canvas.width || 1)),
    }),
    toDataURL: () => "data:image/png;base64,Q0FOVkFT",
  });
  canvas.strokes = strokes;
  return canvas;
}

const IDS = ["fn-canvas", "fn-file", "fn-reset", "fn-hint", "fn-error", "fn-selection",
  "fn-blur-btn", "fn-objects-btn", "fn-objects-result", "fn-blur-size", "fn-hue",
  "fn-tolerance", "fn-min-area"];

function load({ displayWidth, fetchImpl, imageSize = [800, 600] }) {
  const nodes = {};
  IDS.forEach((id) => { nodes[id] = el(); });
  const canvas = makeCanvas(displayWidth);
  nodes["fn-canvas"] = canvas;
  nodes["fn-blur-size"].value = "15";
  nodes["fn-hue"].value = "50";
  nodes["fn-tolerance"].value = "20";
  nodes["fn-min-area"].value = "200";

  const loaded = [];
  class FakeImage {
    set src(value) {
      loaded.push(value);
      this.naturalWidth = imageSize[0];
      this.naturalHeight = imageSize[1];
      if (this.onload) this.onload();
    }
  }
  class FakeFileReader {
    readAsDataURL() { this.result = "data:image/png;base64,T1JJRw=="; this.onload(); }
  }

  const ctx = {
    window: { csrfHeaders: () => ({ "X-CSRFToken": "t" }) },
    console: { error() {}, log() {} },
    fetch: fetchImpl,
    Image: FakeImage,
    FileReader: FakeFileReader,
    Math,
    Number,
    JSON,
    document: { getElementById: (id) => nodes[id] || null },
  };
  vm.createContext(ctx);
  vm.runInContext(fs.readFileSync(scriptPath, "utf8"), ctx);
  return { nodes, canvas, loaded };
}

function pickImage(env) {
  env.nodes["fn-file"].files = [{ name: "a.png" }];
  env.nodes["fn-file"].fire("change");
}

function drag(canvas, from, to) {
  canvas.fire("mousedown", { clientX: from[0], clientY: from[1] });
  canvas.fire("mousemove", { clientX: to[0], clientY: to[1] });
  canvas.fire("mouseup", { clientX: to[0], clientY: to[1] });
}

const sleep = () => new Promise((r) => setTimeout(r, 0));

async function main() {
  if (scenario === "scaled_drag") {
    // ภาพจริง 800px แต่แสดงบนจอ 400px -> ลากที่จอ 100-200 ต้องกลายเป็น 200-400 ในภาพ
    const env = load({ displayWidth: 400 });
    pickImage(env);
    let sent = null;
    const env2 = env;
    drag(env2.canvas, [100, 50], [200, 100]);
    console.log(JSON.stringify({
      selectionText: env2.nodes["fn-selection"].textContent,
      blurDisabled: env2.nodes["fn-blur-btn"].disabled,
    }));
    return;
  }

  if (scenario === "clamped_drag") {
    // ลากเลยขอบภาพ -> ต้องถูกตัดให้อยู่ในภาพ ไม่ส่งค่าเกินไป backend
    const env = load({ displayWidth: 800 });
    pickImage(env);
    drag(env.canvas, [-50, -50], [9999, 9999]);
    console.log(JSON.stringify({ selectionText: env.nodes["fn-selection"].textContent }));
    return;
  }

  if (scenario === "click_without_drag") {
    const env = load({ displayWidth: 800 });
    pickImage(env);
    drag(env.canvas, [100, 100], [100, 100]);
    console.log(JSON.stringify({
      selectionText: env.nodes["fn-selection"].textContent,
      blurDisabled: env.nodes["fn-blur-btn"].disabled,
    }));
    return;
  }

  if (scenario === "blur_request") {
    let sent = null;
    const env = load({
      displayWidth: 400,
      fetchImpl: async (url, opts) => {
        sent = { url, body: JSON.parse(opts.body), headers: opts.headers };
        return { ok: true, status: 200, json: async () => ({ image: "QkxVUlJFRA==" }) };
      },
    });
    pickImage(env);
    drag(env.canvas, [100, 50], [200, 100]);
    env.nodes["fn-blur-size"].value = "21";
    await env.nodes["fn-blur-btn"].fire("click");
    await sleep();
    console.log(JSON.stringify({
      url: sent.url, region: sent.body.region, size: sent.body.size,
      hasCsrf: Boolean(sent.headers["X-CSRFToken"]),
      lastLoaded: env.loaded[env.loaded.length - 1],
    }));
    return;
  }

  if (scenario === "objects_request") {
    let sent = null;
    const env = load({
      displayWidth: 800,
      fetchImpl: async (url, opts) => {
        sent = { url, body: JSON.parse(opts.body) };
        return {
          ok: true, status: 200,
          json: async () => ({ objects: [{ x: 1, y: 2, width: 3, height: 4 }], count: 1 }),
        };
      },
    });
    pickImage(env);
    env.nodes["fn-hue"].value = "120";
    env.nodes["fn-tolerance"].value = "30";
    env.nodes["fn-min-area"].value = "500";
    await env.nodes["fn-objects-btn"].fire("click");
    await sleep();
    console.log(JSON.stringify({
      url: sent.url, body: sent.body,
      result: env.nodes["fn-objects-result"].textContent,
      strokes: env.canvas.strokes,
    }));
    return;
  }

  if (scenario === "objects_empty") {
    const env = load({
      displayWidth: 800,
      fetchImpl: async () => ({ ok: true, status: 200, json: async () => ({ objects: [], count: 0 }) }),
    });
    pickImage(env);
    await env.nodes["fn-objects-btn"].fire("click");
    await sleep();
    console.log(JSON.stringify({
      result: env.nodes["fn-objects-result"].textContent,
      hidden: env.nodes["fn-objects-result"].hidden,
      buttonDisabled: env.nodes["fn-objects-btn"].disabled,
    }));
    return;
  }

  if (scenario === "server_error") {
    const env = load({
      displayWidth: 800,
      fetchImpl: async () => ({
        ok: false, status: 400, json: async () => ({ error: "region is outside the image" }),
      }),
    });
    pickImage(env);
    await env.nodes["fn-objects-btn"].fire("click");
    await sleep();
    console.log(JSON.stringify({
      error: env.nodes["fn-error"].textContent,
      errorHidden: env.nodes["fn-error"].hidden,
      buttonDisabled: env.nodes["fn-objects-btn"].disabled,
    }));
    return;
  }

  throw new Error(`ไม่รู้จัก scenario: ${scenario}`);
}

main();
