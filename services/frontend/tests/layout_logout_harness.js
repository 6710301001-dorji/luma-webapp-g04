// รัน layout.js ตัวจริงบน DOM จำลอง ทดสอบเฉพาะ handleLogout() (#207)
// เรียกจาก test_layout_logout.py:  node layout_logout_harness.js <scenario> <path/to/layout.js>
const fs = require("fs");
const vm = require("vm");
const [scenario, scriptPath] = process.argv.slice(2);

function el(extra = {}) {
  const handlers = {};
  return {
    textContent: "", innerHTML: "", className: "", style: {}, dataset: {},
    addEventListener(type, fn) { handlers[type] = fn; },
    fire(type, e = {}) { return handlers[type] ? handlers[type](e) : undefined; },
    has(type) { return Boolean(handlers[type]); },
    setAttribute() {}, removeAttribute() {}, appendChild() {},
    querySelectorAll: () => [],
    ...extra,
  };
}

function load({ logoutImpl }) {
  const navSlot = el();
  const userSlot = el();
  const nodes = { "app-nav-slot": navSlot, "nav-user-slot": userSlot };
  const alerts = [];
  const store = {};
  const location = { href: "" };
  const createdButtons = [];

  const ctx = {
    window: { csrfHeaders: () => ({ "X-CSRFToken": "t" }), location },
    console: { error() {}, log() {} },
    alert: (msg) => alerts.push(msg),
    localStorage: {
      removeItem(key) { delete store[key]; },
      setItem(key, v) { store[key] = v; },
      getItem(key) { return store[key]; },
    },
    document: {
      readyState: "complete",
      body: { dataset: { page: "generate" } },
      getElementById: (id) => nodes[id] || null,
      querySelectorAll: () => [],
      querySelector: () => null,
      createElement: () => {
        const node = el();
        createdButtons.push(node);
        return node;
      },
      addEventListener() {},
    },
    fetch: async (url, opts) => {
      if (url.endsWith("/partials/nav.html")) {
        return { ok: true, status: 200, text: async () => "" };
      }
      if (url.endsWith("/api/auth/me")) {
        return { ok: true, status: 200, json: async () => ({ email: "demo@luma.local", displayName: "demo" }) }; // no-secret-check
      }
      if (url.endsWith("/api/auth/logout")) {
        return logoutImpl(url, opts);
      }
      throw new Error("unexpected fetch " + url);
    },
  };
  vm.createContext(ctx);
  vm.runInContext(fs.readFileSync(scriptPath, "utf8"), ctx);
  return { alerts, store, location, createdButtons };
}

const sleep = () => new Promise((r) => setTimeout(r, 0));
const sleep3 = async () => { await sleep(); await sleep(); await sleep(); };

async function main() {
  if (scenario === "logout_success_redirects_and_clears_storage") {
    const env = load({
      logoutImpl: async () => ({ ok: true, status: 200, json: async () => ({}) }),
    });
    await sleep3(); // รอ initLayout -> checkAuthStatus สร้างปุ่มเสร็จก่อน
    env.store["luma_user_email"] = "demo@luma.local"; // no-secret-check
    const logoutBtn = env.createdButtons.find((b) => b.has("click"));
    await logoutBtn.fire("click");
    await sleep();
    console.log(JSON.stringify({
      redirectedTo: env.location.href,
      storageHasEmail: "luma_user_email" in env.store,
      alerts: env.alerts,
    }));
    return;
  }

  if (scenario === "logout_csrf_failure_does_not_redirect") {
    const env = load({
      logoutImpl: async () => ({ ok: false, status: 400, json: async () => ({ error: "CSRF token missing" }) }),
    });
    await sleep3();
    env.store["luma_user_email"] = "demo@luma.local"; // no-secret-check
    const logoutBtn = env.createdButtons.find((b) => b.has("click"));
    await logoutBtn.fire("click");
    await sleep();
    console.log(JSON.stringify({
      redirectedTo: env.location.href,
      storageHasEmail: "luma_user_email" in env.store,
      alerts: env.alerts,
    }));
    return;
  }

  if (scenario === "logout_network_error_does_not_redirect") {
    const env = load({
      logoutImpl: async () => { throw new Error("network down"); },
    });
    await sleep3();
    env.store["luma_user_email"] = "demo@luma.local"; // no-secret-check
    const logoutBtn = env.createdButtons.find((b) => b.has("click"));
    await logoutBtn.fire("click");
    await sleep();
    console.log(JSON.stringify({
      redirectedTo: env.location.href,
      storageHasEmail: "luma_user_email" in env.store,
      alerts: env.alerts,
    }));
    return;
  }

  throw new Error(`ไม่รู้จัก scenario: ${scenario}`);
}

main();
