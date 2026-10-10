// รัน function.js ตัวจริงบน DOM + canvas จำลอง แล้วพิมพ์ผลเป็น JSON บรรทัดสุดท้าย
// เรียกจาก test_function_page.py:  node function_harness.js <scenario> <path/to/function.js>
const fs = require("fs");
const vm = require("vm");
const [scenario, scriptPath] = process.argv.slice(2);

function el(extra = {}) {
  const handlers = {};
  return {
    textContent: "", value: "", disabled: false, hidden: false, files: null, dataset: {},
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
  const ellipses = [];
  const canvas = el({
    width: 0, height: 0,
    getContext: () => ({
      clearRect() {}, drawImage() {}, setLineDash() {}, beginPath() {}, stroke() {},
      strokeRect(x, y, w, h) { strokes.push({ x, y, width: w, height: h }); },
      ellipse(x, y, radiusX, radiusY) { ellipses.push({ x, y, radiusX, radiusY }); },
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
  canvas.ellipses = ellipses;
  return canvas;
}

const IDS = ["fn-canvas", "fn-file", "fn-reset", "fn-hint", "fn-error", "fn-selection",
  "fn-blur-btn", "fn-objects-btn", "fn-objects-result", "fn-blur-size", "fn-confidence",
  "fn-min-size",
  // ขั้นตอน 1-2-3 (เลือกฟังก์ชัน -> เลือกภาพ -> ทำงาน)
  "fn-change-image", "fn-change-function", "fn-step-function", "fn-step-image",
  "fn-step-work", "fn-chosen-name", "fn-work-title", "fn-tool-blur", "fn-tool-objects",
  // ฟังก์ชันที่ 3: ลบพื้นหลัง (ใช้กรอบลากเลือกร่วมกับ blur)
  "fn-tool-removebg", "fn-removebg-btn", "fn-removebg-selection"];

function load({ displayWidth, fetchImpl, imageSize = [800, 600] }) {
  const nodes = {};
  IDS.forEach((id) => { nodes[id] = el(); });
  const choices = [el({ dataset: { function: "blur" } }), el({ dataset: { function: "objects" } }),
    el({ dataset: { function: "removebg" } })];
  // ตั้งสถานะเริ่มต้นให้ตรงกับ function.html ที่ใส่ hidden ไว้ตั้งแต่ต้น
  // (el() ตั้ง hidden=false ให้ทุกตัว ถ้าไม่ตั้งตรงนี้ mock จะไม่ตรงกับของจริง)
  ["fn-step-image", "fn-step-work", "fn-tool-blur", "fn-tool-objects", "fn-tool-removebg",
   "fn-objects-result"].forEach((id) => { nodes[id].hidden = true; });
  const canvas = makeCanvas(displayWidth);
  nodes["fn-canvas"] = canvas;
  nodes["fn-blur-size"].value = "15";
  nodes["fn-confidence"].value = "0.6";
  nodes["fn-min-size"].value = "20";

  const loaded = [];
  const offscreens = [];
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
    document: {
      getElementById: (id) => nodes[id] || null,
      // canvas ชั่วคราวที่ cleanImageDataUrl() สร้างเพื่อส่งภาพสะอาด (#176)
      // บันทึกไว้ว่ามันวาดอะไรลงไป เทสจะได้ยืนยันว่าเป็น currentImage ไม่ใช่ canvas ที่มีเส้นกรอบ
      createElement: (tag) => {
        if (tag !== "canvas") return el();
        const offscreen = el({
          width: 0, height: 0,
          getContext: () => ({ drawImage: (img) => { offscreen.drew = img; } }),
          toDataURL: () => "data:image/png;base64,Q0xFQU4=",
        });
        offscreens.push(offscreen);
        return offscreen;
      },
      // ปุ่มเลือกฟังก์ชันสองอัน — gallery ของ DOM จริงใช้ .fn-choice
      querySelectorAll: (sel) => (sel === ".fn-choice" ? choices : []),
    },
  };
  vm.createContext(ctx);
  vm.runInContext(fs.readFileSync(scriptPath, "utf8"), ctx);
  return { nodes, canvas, loaded, choices, offscreens };
}

function chooseFunction(env, key) {
  env.choices.find((c) => c.dataset.function === key).fire("click");
}

function pickImage(env, key = "blur") {
  chooseFunction(env, key);              // ขั้นที่ 1 ต้องเลือกฟังก์ชันก่อนเสมอ
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
  // ---- ขั้นตอน 1-2-3 ----
  const steps = (env) => ({
    step1: !env.nodes["fn-step-function"].hidden,
    step2: !env.nodes["fn-step-image"].hidden,
    step3: !env.nodes["fn-step-work"].hidden,
    toolBlur: !env.nodes["fn-tool-blur"].hidden,
    toolObjects: !env.nodes["fn-tool-objects"].hidden,
    toolRemoveBg: !env.nodes["fn-tool-removebg"].hidden,
    chosenName: env.nodes["fn-chosen-name"].textContent,
    objectsDisabled: env.nodes["fn-objects-btn"].disabled,
    resetDisabled: env.nodes["fn-reset"].disabled,
    hint: env.nodes["fn-hint"].textContent,
  });

  if (scenario === "start") {
    const env = load({ displayWidth: 400 });
    return console.log(JSON.stringify(steps(env)));
  }

  if (scenario === "after_choose_blur") {
    const env = load({ displayWidth: 400 });
    chooseFunction(env, "blur");
    return console.log(JSON.stringify(steps(env)));
  }

  if (scenario === "after_choose_objects") {
    const env = load({ displayWidth: 400 });
    chooseFunction(env, "objects");
    return console.log(JSON.stringify(steps(env)));
  }

  if (scenario === "after_choose_removebg") {
    const env = load({ displayWidth: 400 });
    chooseFunction(env, "removebg");
    return console.log(JSON.stringify(steps(env)));
  }

  if (scenario === "after_pick_image") {
    const env = load({ displayWidth: 400 });
    pickImage(env, "blur");
    return console.log(JSON.stringify(steps(env)));
  }

  if (scenario === "change_function") {
    const env = load({ displayWidth: 400 });
    pickImage(env, "blur");
    env.nodes["fn-change-function"].fire("click");
    return console.log(JSON.stringify(steps(env)));
  }

  if (scenario === "change_image") {
    const env = load({ displayWidth: 400 });
    pickImage(env, "objects");
    env.nodes["fn-change-image"].fire("click");
    return console.log(JSON.stringify(steps(env)));
  }

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
      sentImage: sent.body.image,
      offscreenCount: env.offscreens.length,
      offscreenSize: env.offscreens.length ? [env.offscreens[0].width, env.offscreens[0].height] : null,
      drewCurrentImage: env.offscreens.length ? Boolean(env.offscreens[0].drew) : false,
    }));
    return;
  }

  if (scenario === "removebg_drag") {
    // กรอบลากเลือกต้องผูกกับปุ่ม/ข้อความของ removebg ไม่ใช่ของ blur (คนละการ์ด)
    const env = load({ displayWidth: 800 });
    pickImage(env, "removebg");
    drag(env.canvas, [100, 50], [200, 100]);
    console.log(JSON.stringify({
      removebgSelectionText: env.nodes["fn-removebg-selection"].textContent,
      removebgDisabled: env.nodes["fn-removebg-btn"].disabled,
      blurSelectionText: env.nodes["fn-selection"].textContent,
      blurDisabled: env.nodes["fn-blur-btn"].disabled,
      // พรีวิวต้องวาดเป็นวงรี (ellipse) ไม่ใช่กรอบสี่เหลี่ยม (strokeRect) สำหรับ removebg
      ellipseCount: env.canvas.ellipses.length,
      ellipse: env.canvas.ellipses[env.canvas.ellipses.length - 1] || null,
      rectStrokeCount: env.canvas.strokes.length,
    }));
    return;
  }

  if (scenario === "blur_drag_still_draws_a_rectangle") {
    // เบลอต้องยังพรีวิวเป็นสี่เหลี่ยมเหมือนเดิม ไม่ได้เปลี่ยนไปเป็นวงรีไปด้วย
    const env = load({ displayWidth: 800 });
    pickImage(env, "blur");
    drag(env.canvas, [100, 50], [200, 100]);
    console.log(JSON.stringify({
      ellipseCount: env.canvas.ellipses.length,
      rectStrokeCount: env.canvas.strokes.length,
    }));
    return;
  }

  if (scenario === "removebg_request") {
    let sent = null;
    const env = load({
      displayWidth: 400,
      fetchImpl: async (url, opts) => {
        sent = { url, body: JSON.parse(opts.body), headers: opts.headers };
        return { ok: true, status: 200, json: async () => ({ image: "RVJBU0VE" }) };
      },
    });
    pickImage(env, "removebg");
    drag(env.canvas, [100, 50], [200, 100]);
    await env.nodes["fn-removebg-btn"].fire("click");
    await sleep();
    console.log(JSON.stringify({
      url: sent.url, region: sent.body.region,
      hasCsrf: Boolean(sent.headers["X-CSRFToken"]),
      lastLoaded: env.loaded[env.loaded.length - 1],
      sentImage: sent.body.image,
      buttonDisabled: env.nodes["fn-removebg-btn"].disabled,
    }));
    return;
  }

  if (scenario === "removebg_server_error") {
    const env = load({
      displayWidth: 800,
      fetchImpl: async () => ({
        ok: false, status: 400, json: async () => ({ error: "region must stay within the image bounds" }),
      }),
    });
    pickImage(env, "removebg");
    drag(env.canvas, [100, 50], [200, 100]);
    await env.nodes["fn-removebg-btn"].fire("click");
    await sleep();
    console.log(JSON.stringify({
      error: env.nodes["fn-error"].textContent,
      errorHidden: env.nodes["fn-error"].hidden,
      buttonDisabled: env.nodes["fn-removebg-btn"].disabled,
    }));
    return;
  }

  if (scenario === "stale_blur_response_does_not_override_reset") {
    // (#207) จำลอง race: กดเบลอ -> ระหว่างรอ response ผู้ใช้กดเปลี่ยนฟังก์ชัน
    // (resetToStart) -> response เก่าเพิ่งกลับมา -> ต้องไม่ทับ DOM กลับไปขั้นที่ 3
    let resolveFetch;
    const env = load({
      displayWidth: 400,
      fetchImpl: () => new Promise((resolve) => {
        resolveFetch = () => resolve({ ok: true, status: 200, json: async () => ({ image: "U1RBTEU=" }) });
      }),
    });
    pickImage(env, "blur");
    drag(env.canvas, [100, 50], [200, 100]);
    const clickPromise = env.nodes["fn-blur-btn"].fire("click"); // ยิง fetch แต่ยังไม่ resolve

    env.nodes["fn-change-function"].fire("click"); // ผู้ใช้เปลี่ยนใจก่อน response กลับมา

    resolveFetch(); // response เก่าเพิ่งมาถึงตอนนี้
    await clickPromise;
    await sleep();

    console.log(JSON.stringify({
      step1Visible: !env.nodes["fn-step-function"].hidden,
      step3Visible: !env.nodes["fn-step-work"].hidden,
      hint: env.nodes["fn-hint"].textContent,
      lastLoaded: env.loaded[env.loaded.length - 1] || null,
    }));
    return;
  }

  if (scenario === "stale_removebg_response_does_not_override_new_image") {
    // (#207) กดลบพื้นหลัง -> ระหว่างรอ response ผู้ใช้เปลี่ยนภาพใหม่ (fileInput change)
    // -> response เก่ากลับมาทีหลัง -> ต้องไม่ทับภาพใหม่ที่เพิ่งโหลด
    let resolveFetch;
    const env = load({
      displayWidth: 400,
      fetchImpl: () => new Promise((resolve) => {
        resolveFetch = () => resolve({ ok: true, status: 200, json: async () => ({ image: "U1RBTEU=" }) });
      }),
    });
    pickImage(env, "removebg");
    drag(env.canvas, [100, 50], [200, 100]);
    const clickPromise = env.nodes["fn-removebg-btn"].fire("click");

    env.nodes["fn-file"].files = [{ name: "b.png" }];
    env.nodes["fn-file"].fire("change"); // เลือกไฟล์ใหม่ก่อน response เก่าจะกลับมา

    resolveFetch();
    await clickPromise;
    await sleep();

    console.log(JSON.stringify({
      // ภาพสุดท้ายที่โหลดต้องเป็นไฟล์ใหม่ (จาก FakeFileReader) ไม่ใช่ผลลบพื้นหลังเก่า
      lastLoaded: env.loaded[env.loaded.length - 1],
      removebgDisabled: env.nodes["fn-removebg-btn"].disabled,
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
    pickImage(env, "objects");
    env.nodes["fn-confidence"].value = "0.75";
    env.nodes["fn-min-size"].value = "40";
    await env.nodes["fn-objects-btn"].fire("click");
    await sleep();
    console.log(JSON.stringify({
      url: sent.url, body: sent.body,
      result: env.nodes["fn-objects-result"].textContent,
      strokes: env.canvas.strokes,
      sentImage: sent.body.image,
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
