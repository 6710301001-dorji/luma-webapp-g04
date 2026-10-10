// รัน password-toggle.js ตัวจริงบน DOM จำลอง แล้วพิมพ์ผลเป็น JSON บรรทัดสุดท้าย
// เรียกจาก test_password_toggle.py:  node password_toggle_harness.js <scenario> <path/to/password-toggle.js>
const fs = require("fs");
const vm = require("vm");
const [scenario, scriptPath] = process.argv.slice(2);

function el(extra = {}) {
  const handlers = {};
  const attrs = new Map();
  return {
    type: "password",
    // "hidden" เป็น property ธรรมดาที่ไม่ผูกกับ attribute จริง — จำลองพฤติกรรมของ
    // SVGElement จริงที่ไม่มี IDL reflection ของ hidden แบบ HTMLElement (รีวิว PR #204
    // โดย @6710301001-dorji: โค้ดเดิมใช้ eye.hidden = show ซึ่งใช้ไม่ได้กับ SVG)
    // ถ้าโค้ดใน password-toggle.js กลับไปใช้ .hidden = x เทสนี้ต้องจับได้ว่าไม่เปลี่ยน
    // attribute จริง ไม่ใช่แค่เช็ค property เฉยๆ เหมือนเทสเดิมที่ตกบั๊กนี้ไป
    hidden: false,
    setAttribute(k, v) { attrs.set(k, v); },
    getAttribute(k) { return attrs.has(k) ? attrs.get(k) : null; },
    removeAttribute(k) { attrs.delete(k); },
    hasAttribute(k) { return attrs.has(k); },
    toggleAttribute(k, force) {
      const want = force === undefined ? !attrs.has(k) : Boolean(force);
      if (want) attrs.set(k, ""); else attrs.delete(k);
      return want;
    },
    addEventListener(type, fn) { handlers[type] = fn; },
    fire(type, e = {}) { return handlers[type] ? handlers[type](e) : undefined; },
    ...extra,
  };
}

function buildField() {
  const input = el({ type: "password" });
  const eye = el();      // ไม่มี hidden attribute ตอนเริ่ม (มองเห็นได้) ตรงกับ HTML จริง
  const eyeOff = el();
  eyeOff.toggleAttribute("hidden", true); // ตรงกับ HTML จริงที่ใส่ hidden ไว้ตั้งแต่ต้น
  const btn = el({
    querySelector(sel) { return sel === ".auth-field__eye" ? eye : sel === ".auth-field__eye-off" ? eyeOff : null; },
    closest() { return wrap; },
  });
  const wrap = { querySelector: () => input };
  return { input, eye, eyeOff, btn };
}

function load(fields) {
  const ctx = {
    document: {
      readyState: "complete",
      addEventListener() {},
      querySelectorAll: (sel) => (sel === ".auth-field__toggle" ? fields.map((f) => f.btn) : []),
    },
  };
  vm.createContext(ctx);
  vm.runInContext(fs.readFileSync(scriptPath, "utf8"), ctx);
}

function main() {
  if (scenario === "single_click_shows_password") {
    const field = buildField();
    load([field]);
    field.btn.fire("click");
    console.log(JSON.stringify({
      inputType: field.input.type,
      eyeHasHiddenAttr: field.eye.hasAttribute("hidden"),
      eyeOffHasHiddenAttr: field.eyeOff.hasAttribute("hidden"),
      ariaLabel: field.btn.getAttribute("aria-label"),
      ariaPressed: field.btn.getAttribute("aria-pressed"),
    }));
    return;
  }

  if (scenario === "second_click_hides_password_again") {
    const field = buildField();
    load([field]);
    field.btn.fire("click");
    field.btn.fire("click");
    console.log(JSON.stringify({
      inputType: field.input.type,
      eyeHasHiddenAttr: field.eye.hasAttribute("hidden"),
      eyeOffHasHiddenAttr: field.eyeOff.hasAttribute("hidden"),
      ariaLabel: field.btn.getAttribute("aria-label"),
    }));
    return;
  }

  if (scenario === "two_fields_are_independent") {
    const a = buildField();
    const b = buildField();
    load([a, b]);
    a.btn.fire("click"); // แสดงเฉพาะช่องแรก
    console.log(JSON.stringify({
      aType: a.input.type,
      bType: b.input.type,
    }));
    return;
  }

  throw new Error(`ไม่รู้จัก scenario: ${scenario}`);
}

main();
