// ตรวจ layout ของหน้า img2img ใน browser จริง (Chrome/Edge headless ผ่าน DevTools protocol) — รีวิว #143
// ไม่ต้องติดตั้งอะไรเพิ่ม: ใช้ WebSocket/fetch ที่มากับ node 22+
// เรียกจาก test_img2img_layout.py:  node img2img_layout_check.js <browser.exe> <page url> <width> <height>
// พิมพ์ JSON: ตำแหน่งของ canvas ทั้งสองชั้น + ผลการระบายด้วยเมาส์จริงที่กลางภาพ
const { spawn } = require("child_process");
const fs = require("fs");
const os = require("os");
const path = require("path");

const [browserPath, pageUrl, W, H] = process.argv.slice(2);
const profile = fs.mkdtempSync(path.join(os.tmpdir(), "luma-cdp-"));
const browser = spawn(browserPath, [
  "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
  "--remote-debugging-port=0", `--user-data-dir=${profile}`,
  ...(process.getuid && process.getuid() === 0 ? ["--no-sandbox"] : []), "about:blank",
], { stdio: "ignore" });

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function devtoolsPort() {
  const file = path.join(profile, "DevToolsActivePort");
  for (let i = 0; i < 200; i++) {
    if (fs.existsSync(file)) {
      const port = fs.readFileSync(file, "utf8").split("\n")[0].trim();
      if (port) return port;
    }
    await sleep(50);
  }
  throw new Error("browser did not open a DevTools port");
}

async function main() {
  const port = await devtoolsPort();
  const targets = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
  const ws = new WebSocket(targets.find((t) => t.type === "page").webSocketDebuggerUrl);
  await new Promise((r, j) => { ws.onopen = r; ws.onerror = j; });
  let id = 0;
  const waiting = new Map();
  ws.onmessage = (m) => {
    const msg = JSON.parse(m.data);
    if (msg.id && waiting.has(msg.id)) { waiting.get(msg.id)(msg); waiting.delete(msg.id); }
  };
  const send = (method, params = {}) => new Promise((resolve, reject) => {
    const mid = ++id;
    waiting.set(mid, (msg) => (msg.error ? reject(new Error(JSON.stringify(msg.error))) : resolve(msg.result)));
    ws.send(JSON.stringify({ id: mid, method, params }));
  });
  const evaluate = async (expression) => {
    const r = await send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true });
    if (r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description || "page error");
    return r.result.value;
  };

  await send("Emulation.setDeviceMetricsOverride", { width: 1280, height: 900, deviceScaleFactor: 1, mobile: false });
  await send("Page.enable");
  await send("Page.navigate", { url: pageUrl });
  await evaluate(`new Promise((r) => { const t = setInterval(() => { if (document.getElementById("i2i-upload")) { clearInterval(t); r(); } }, 50); })`);

  // อัปโหลดภาพ W x H ผ่าน input จริง แล้วเลือกโหมด inpaint
  await evaluate(`(async () => {
    const c = document.createElement("canvas"); c.width = ${W}; c.height = ${H};
    const g = c.getContext("2d"); g.fillStyle = "#3a7"; g.fillRect(0, 0, ${W}, ${H});
    const blob = await new Promise((r) => c.toBlob(r, "image/png"));
    const dt = new DataTransfer(); dt.items.add(new File([blob], "fixture.png", { type: "image/png" }));
    const input = document.getElementById("i2i-upload");
    input.files = dt.files; input.dispatchEvent(new Event("change", { bubbles: true }));
    const mode = document.getElementById("i2i-mode");
    mode.value = "inpaint"; mode.dispatchEvent(new Event("change", { bubbles: true }));
    for (let i = 0; i < 100 && document.getElementById("i2i-base").hidden; i++) await new Promise((r) => setTimeout(r, 50));
    document.getElementById("i2i-stage").scrollIntoView({ block: "center" });
    await new Promise((r) => setTimeout(r, 150));
  })()`);

  const rect = (elementId) => evaluate(`(() => { const b = document.getElementById("${elementId}").getBoundingClientRect();
    return { x: b.x, y: b.y, w: b.width, h: b.height }; })()`);
  const base = await rect("i2i-base");
  const mask = await rect("i2i-mask");

  // ระบายด้วยเมาส์จริงที่กลาง "ภาพที่มองเห็น" (#i2i-base) แล้วอ่านว่าชั้น mask ถูกระบายที่กลางภาพไหม
  const cx = base.x + base.w / 2;
  const cy = base.y + base.h / 2;
  const mouse = (type, x, y) => send("Input.dispatchMouseEvent", { type, x, y, button: "left", buttons: type === "mouseReleased" ? 0 : 1, clickCount: 1 });
  await mouse("mousePressed", cx, cy);
  await mouse("mouseMoved", cx + 2, cy + 1);
  await mouse("mouseReleased", cx + 2, cy + 1);
  const painted = await evaluate(`(() => {
    const m = document.getElementById("i2i-mask");
    const px = m.getContext("2d").getImageData(Math.floor(m.width / 2), Math.floor(m.height / 2), 1, 1).data;
    return { centre_alpha: px[3], intrinsic: [m.width, m.height] };
  })()`);

  console.log(JSON.stringify({ base, mask, ...painted }));
  ws.close();
}

main()
  .catch((e) => { console.error(e.stack || String(e)); process.exitCode = 1; })
  .finally(() => { browser.kill(); setTimeout(() => { try { fs.rmSync(profile, { recursive: true, force: true }); } catch {} }, 500); });
