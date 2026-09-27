// รัน gallery.js ตัวจริงบน DOM จำลอง เพื่อตรวจตัวกรองแท็กกับการซิงก์ URL (Issue #59)
// เรียกจาก test_gallery_tags.py:  node gallery_tags_harness.js <scenario> <path/to/gallery.js>
const fs = require("fs");
const vm = require("vm");
const [scenario, scriptPath] = process.argv.slice(2);

function el() {
  const handlers = {};
  return {
    textContent: "", className: "", type: "", disabled: false, hidden: false,
    attrs: {}, children: [], dataset: {},
    classList: {
      classes: new Set(),
      add(c) { this.classes.add(c); },
      remove(c) { this.classes.delete(c); },
      contains(c) { return this.classes.has(c); },
    },
    set innerHTML(v) { if (v === "") this.children = []; }, get innerHTML() { return ""; },
    setAttribute(k, v) { this.attrs[k] = v; }, removeAttribute(k) { delete this.attrs[k]; },
    appendChild(c) { this.children.push(c); }, addEventListener(t, fn) { handlers[t] = fn; },
    fire(t, e = {}) { return handlers[t] ? handlers[t](e) : undefined; },
    has(t) { return Boolean(handlers[t]); },
  };
}

const tick = () => new Promise((r) => setTimeout(r, 0));

// คลังภาพจำลอง: 3 ใบ portrait+anime · 2 ใบ landscape · 1 ใบ portrait อย่างเดียว
const ASSETS = [
  { id: 1, prompt: "girl in kimono", tags: ["portrait", "anime"] },
  { id: 2, prompt: "anime warrior", tags: ["portrait", "anime"] },
  { id: 3, prompt: "boy reading", tags: ["portrait", "anime"] },
  { id: 4, prompt: "misty valley", tags: ["landscape", "nature"] },
  { id: 5, prompt: "green forest", tags: ["landscape", "nature"] },
  { id: 6, prompt: "studio portrait", tags: ["portrait"] },
];

function query(params) {
  const wanted = (params.get("tags") || "").split(",").map((t) => t.trim()).filter(Boolean);
  const q = (params.get("q") || "").toLowerCase();
  let items = ASSETS.filter((a) => wanted.every((t) => a.tags.includes(t)));
  if (q) items = items.filter((a) => a.prompt.toLowerCase().includes(q));
  return items.map((a) => ({ ...a, image_url: `/api/assets/${a.id}/image`, created_at: null }));
}

(async () => {
  const nodes = {};
  for (const id of ["gallery-grid", "gallery-search-form", "gallery-search-input", "gallery-prev-btn",
    "gallery-next-btn", "gallery-page-indicator", "gallery-empty", "gallery-error",
    "gallery-tags", "gallery-clear-btn"]) nodes[id] = el();

  const requests = [];
  const tagRequests = [];
  const urlHistory = [];
  // scenario tags_endpoint_down: จำลอง endpoint ล่ม เพื่อดูว่าหน้ายังใช้ได้อยู่
  const tagsReply = scenario === "tags_endpoint_down"
    ? { ok: false, status: 500, json: async () => ({ error: "boom" }) }
    : null;
  const start = scenario === "url_initial" ? "?page=2&q=anime&tags=portrait" : "";

  const location = {
    origin: "http://luma.test",
    pathname: "/pages/gallery.html",
    search: start,
    get href() { return this.origin + this.pathname + this.search; },
  };

  const windowListeners = {};
  const ctx = {
    window: {
      location,
      csrfHeaders: () => ({ "X-CSRFToken": "tok" }),
      confirm: () => true,
      addEventListener: (type, fn) => { windowListeners[type] = fn; },
      history: {
        pushState(_s, _t, next) { urlHistory.push({ kind: "push", url: next }); location.search = next.includes("?") ? next.slice(next.indexOf("?")) : ""; },
        replaceState(_s, _t, next) { urlHistory.push({ kind: "replace", url: next }); location.search = next.includes("?") ? next.slice(next.indexOf("?")) : ""; },
      },
    },
    URL, URLSearchParams, console: { error() {}, log() {} }, alert() {}, setTimeout,
    fetch: async (url) => {
      const parsed = new URL(String(url));
      // GET /api/tags (#178) — แท็กทั้งหมดของผู้ใช้ เรียงจำนวนภาพมาก->น้อย เหมือน backend
      // ไม่ขึ้นกับว่าเปิดหน้าไหนอยู่ จึงนับจาก ASSETS ทั้งชุด
      if (parsed.pathname.endsWith("/api/tags")) {
        tagRequests.push(String(url));
        if (tagsReply) return tagsReply;
        const counts = new Map();
        ASSETS.forEach((a) => a.tags.forEach((n) => counts.set(n, (counts.get(n) || 0) + 1)));
        const items = [...counts.entries()]
          .map(([name, asset_count]) => ({ name, asset_count }))
          .sort((a, b) => b.asset_count - a.asset_count || a.name.localeCompare(b.name));
        return { ok: true, status: 200, json: async () => ({ items, total: items.length }) };
      }
      requests.push(String(url));
      // scenario rapid_clicks: ให้คำขอแรกตอบช้ากว่าคำขอที่สอง เพื่อจำลองการกดรัว
      if (scenario === "rapid_clicks" && requests.length === 2) {
        await new Promise((r) => setTimeout(r, 30));
      }
      const all = query(parsed.searchParams);
      const page = Number(parsed.searchParams.get("page")) || 1;
      // scenario tag_only_on_another_page: แบ่งหน้าจริงหน้าละ 3 ใบ ให้หน้า 1 มีแต่ภาพ
      // portrait/anime — landscape กับ nature อยู่หน้า 2 เหมือนอาการจริงของ #178
      const items = scenario === "tag_only_on_another_page"
        ? all.slice((page - 1) * 3, page * 3)
        : all;
      return { ok: true, status: 200, json: async () => ({ items, page, total: all.length }) };
    },
    document: { readyState: "complete", getElementById: (id) => nodes[id] || null, createElement: () => el() },
  };
  vm.createContext(ctx);
  vm.runInContext(fs.readFileSync(scriptPath, "utf8"), ctx);
  await tick();

  const chips = () => nodes["gallery-tags"].children;
  const chip = (name) => chips().find((c) => c.dataset.tag === name);
  const lastRequest = () => requests[requests.length - 1];
  const activeNames = () => chips().filter((c) => c.classList.contains("is-active")).map((c) => c.dataset.tag);

  async function click(name) {
    await chip(name).fire("click");
    await tick();
  }

  const report = (extra) => console.log(JSON.stringify({
    requests,
    tagRequests,
    last: lastRequest(),
    urlHistory,
    chipNames: chips().map((c) => c.dataset.tag),
    active: activeNames(),
    cards: nodes["gallery-grid"].children.length,
    empty: nodes["gallery-empty"].textContent,
    emptyHidden: "hidden" in nodes["gallery-empty"].attrs,
    errorHidden: "hidden" in nodes["gallery-error"].attrs,
    clearHidden: nodes["gallery-clear-btn"].hidden,
    ...extra,
  }));

  if (scenario === "first_load" || scenario === "tags_endpoint_down") return report({});

  if (scenario === "tag_only_on_another_page") {
    // หน้า 1 ได้แค่ภาพ 3 ใบแรก (portrait+anime) — landscape กับ nature อยู่หน้า 2
    return report({ pageOneTags: [...new Set(ASSETS.slice(0, 3).flatMap((a) => a.tags))] });
  }

  if (scenario === "tag_click") {
    await click("portrait");
    return report({});
  }

  if (scenario === "tag_two") {
    await click("portrait");
    await click("anime");
    return report({});
  }

  if (scenario === "tag_toggle_off") {
    await click("portrait");
    await click("portrait");
    return report({});
  }

  if (scenario === "tag_resets_page") {
    await nodes["gallery-next-btn"].fire("click");   // ไปหน้า 2 ก่อน
    await tick();
    await click("portrait");
    return report({});
  }

  if (scenario === "url_initial") {
    return report({ searchInputValue: nodes["gallery-search-input"].value });
  }

  if (scenario === "popstate") {
    await click("portrait");
    const pushesBefore = urlHistory.filter((h) => h.kind === "push").length;
    location.search = "";                              // จำลองว่าเบราว์เซอร์ถอย URL กลับไปแล้ว
    await windowListeners.popstate();
    await tick();
    return report({ pushesBefore, pushesAfter: urlHistory.filter((h) => h.kind === "push").length });
  }

  if (scenario === "no_match") {
    await click("portrait");
    await click("landscape");                          // ไม่มีภาพไหนมีครบสองอันนี้
    return report({});
  }

  if (scenario === "rapid_clicks") {
    // กดสองแท็กติดกันโดยไม่รอผลอันแรก — ผลของคำขอที่ช้ากว่าต้องไม่ถูกเอามาวาดทับ
    const first = chip("portrait").fire("click");
    const second = chip("landscape").fire("click");
    await Promise.all([first, second]);
    await new Promise((r) => setTimeout(r, 60));
    return report({});
  }

  if (scenario === "clear") {
    await click("portrait");
    await nodes["gallery-clear-btn"].fire("click");
    await tick();
    return report({});
  }

  throw new Error(`ไม่รู้จัก scenario: ${scenario}`);
})();
