// รัน register.js ตัวจริงบน DOM จำลอง + fetch ที่ควบคุมได้ แล้วพิมพ์ผลเป็น JSON บรรทัดสุดท้าย
// เรียกจาก test_register.py:  node register_harness.js <scenario> <path/to/register.js>
const fs = require("fs");
const vm = require("vm");
const [scenario, scriptPath] = process.argv.slice(2);

const replies = {
  created: { ok: true, status: 201, json: async () => ({ status: "success" }) },
  taken: { ok: false, status: 409, json: async () => ({ error: "อีเมลหรือชื่อนี้ถูกใช้แล้ว / Email or displayName already taken" }) },
  html_500: { ok: false, status: 500, json: async () => { throw new SyntaxError("Unexpected token <"); } },
};

(async () => {
  const calls = [];
  let submit, ready;
  const el = () => ({ textContent: "", attrs: {}, disabled: false, setAttribute(k, v) { this.attrs[k] = v; }, removeAttribute(k) { delete this.attrs[k]; } });
  const errorBox = el();
  const form = { addEventListener: (_, fn) => { submit = fn; } };
  const confirm = scenario === "mismatch" ? "different-password" : "password123";  // no-secret-check
  const fields = { displayName: "Tester", email: "tester@luma.ai", password: "password123", confirmPassword: confirm };  // no-secret-check
  for (const [k, v] of Object.entries(fields)) form[k] = { value: v };
  const nodes = { "register-form": form, "register-error": errorBox, "register-submit": el() };

  const window = { location: { href: "" }, csrfHeaders: () => ({}) };
  const ctx = vm.createContext({
    window, console: { error() {}, log() {} },
    document: { getElementById: (id) => nodes[id], addEventListener: (_, fn) => { ready = fn; } },
    fetch: async (url, opts) => { calls.push({ url, method: opts.method, body: JSON.parse(opts.body) }); return replies[scenario]; },
  });
  vm.runInContext(fs.readFileSync(scriptPath, "utf8"), ctx);
  ready();
  await submit({ preventDefault() {} });
  console.log(JSON.stringify({ calls, href: window.location.href, error: errorBox.textContent }));
})();
