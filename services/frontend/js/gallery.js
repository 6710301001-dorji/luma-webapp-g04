/**
 * LUMA — Personal Gallery Logic
 * -------------------------------------------------------------------------
 * ดึงรายการภาพจาก GET /api/assets แสดงผลเป็นการ์ด Grid
 * รองรับการค้นหาตาม Prompt (?q=...) กรองด้วย tag (?tags=a,b) และการเปลี่ยนหน้า
 *
 * อ้างอิง: Issue #58, #59, docs/API_CONTRACT.md
 *
 * ห้าม hardcode localhost/IP — อ่าน API base จาก window.LUMA_CONFIG เท่านั้น
 */

(() => {
  const API_BASE = window.LUMA_CONFIG ? window.LUMA_CONFIG.apiBase : "";

  let currentPage = 1;
  const perPage = 12;
  let currentQuery = "";
  let currentTags = [];

  // กดแท็กรัวๆ หรือกดย้อนกลับติดกัน = มีหลายคำขอวิ่งพร้อมกัน
  // คำขอที่ตอบช้ากว่าอาจมาถึงทีหลังแล้วเขียนทับผลของคำขอล่าสุด
  // หรือแย่กว่านั้นคือ append ซ้อนกันจนได้การ์ดเกินจำนวนต่อหน้า (เจอจริงตอนทดสอบด้วย browser)
  // นับรอบไว้ แล้วรับเฉพาะผลของรอบล่าสุดเท่านั้น
  let requestId = 0;

  // tag ที่เคยเห็นจากภาพที่โหลดมาแล้ว — สะสมไว้เพื่อให้ปุ่มไม่หายตอนเปลี่ยนหน้า
  // (ยังไม่มี endpoint ที่บอกว่าผู้ใช้มี tag อะไรบ้าง ดู #59)
  const knownTags = new Set();

  function initGallery() {
    const grid = document.getElementById("gallery-grid");
    if (!grid) return;

    const searchForm = document.getElementById("gallery-search-form");
    const searchInput = document.getElementById("gallery-search-input");
    const prevBtn = document.getElementById("gallery-prev-btn");
    const nextBtn = document.getElementById("gallery-next-btn");
    const pageIndicator = document.getElementById("gallery-page-indicator");
    const emptyBox = document.getElementById("gallery-empty");
    const errorBox = document.getElementById("gallery-error");
    const tagBox = document.getElementById("gallery-tags");
    const clearBtn = document.getElementById("gallery-clear-btn");

    /** เขียนเงื่อนไขปัจจุบันลง URL เพื่อให้กดย้อนกลับได้และก๊อปลิงก์ส่งต่อได้ (MUST ของ #59) */
    function syncUrl(replace) {
      const url = new URL(window.location.href);
      const params = url.searchParams;
      params.delete("page");
      params.delete("q");
      params.delete("tags");
      if (currentPage > 1) params.set("page", String(currentPage));
      if (currentQuery) params.set("q", currentQuery);
      if (currentTags.length) params.set("tags", currentTags.join(","));
      const next = url.pathname + (params.toString() ? `?${params}` : "");
      if (replace) {
        window.history.replaceState(null, "", next);
      } else {
        window.history.pushState(null, "", next);
      }
    }

    function readUrl() {
      const params = new URLSearchParams(window.location.search);
      const page = parseInt(params.get("page") || "1", 10);
      return {
        page: Number.isFinite(page) && page > 0 ? page : 1,
        query: (params.get("q") || "").trim(),
        tags: (params.get("tags") || "").split(",").map((t) => t.trim()).filter(Boolean),
      };
    }

    async function loadAssets(page = 1, query = "", tags = [], options = {}) {
      const myRequest = ++requestId;
      currentPage = page;
      currentQuery = query;
      currentTags = tags;

      if (grid) grid.innerHTML = "";
      if (emptyBox) emptyBox.setAttribute("hidden", "");
      if (errorBox) errorBox.setAttribute("hidden", "");

      try {
        // API_BASE ว่าง (same-origin) -> path แบบ relative ต้องมี base ไม่งั้น new URL() โยน TypeError
        const url = new URL(`${API_BASE}/api/assets`, window.location.origin);
        url.searchParams.set("page", String(page));
        url.searchParams.set("per_page", String(perPage));
        if (query) {
          url.searchParams.set("q", query);
        }
        if (tags.length) {
          // AND intersection — backend คืนเฉพาะภาพที่มีครบทุก tag (API_CONTRACT ข้อ 2)
          url.searchParams.set("tags", tags.join(","));
        }

        const res = await fetch(url.toString());
        if (!res.ok) {
          throw new Error(`โหลดภาพไม่สำเร็จ (HTTP ${res.status})`);
        }

        const data = await res.json();
        if (myRequest !== requestId) return;   // มีคำขอใหม่กว่าแซงไปแล้ว ทิ้งผลนี้

        const items = data.items || [];
        const total = data.total || 0;

        if (items.length === 0) {
          if (emptyBox) {
            emptyBox.textContent = describeEmpty(query, tags);
            emptyBox.removeAttribute("hidden");
          }
        } else {
          items.forEach((item) => {
            (item.tags || []).forEach((name) => knownTags.add(name));
            const card = createAssetCard(item);
            grid.appendChild(card);
          });
        }

        renderTagFilter();
        updatePagination(data.page || 1, Math.ceil(total / perPage) || 1);
        if (!options.fromHistory) syncUrl(options.replaceUrl);
      } catch (err) {
        if (myRequest !== requestId) return;
        console.error("Gallery load error:", err);
        if (errorBox) {
          errorBox.textContent = "ไม่สามารถเชื่อมต่อเซิร์ฟเวอร์เพื่อโหลดรูปภาพได้";
          errorBox.removeAttribute("hidden");
        }
      }
    }

    /** บอกให้ชัดว่าไม่เจอเพราะเงื่อนไขไหน ไม่ใช่ปล่อยหน้าว่าง (MUST ของ #59) */
    function describeEmpty(query, tags) {
      if (query && tags.length) {
        return `ไม่พบภาพที่ตรงกับคำค้นหา "${query}" และมีแท็ก ${tags.join(" + ")} ครบทุกอัน`;
      }
      if (tags.length > 1) {
        return `ไม่พบภาพที่มีแท็ก ${tags.join(" + ")} ครบทุกอัน ลองเลือกให้น้อยลง`;
      }
      if (tags.length === 1) {
        return `ไม่พบภาพที่มีแท็ก ${tags[0]}`;
      }
      if (query) {
        return `ไม่พบรูปภาพที่ตรงกับคำค้นหา "${query}"`;
      }
      return "ยังไม่มีรูปภาพในคลังผลงาน เริ่มต้นสร้างภาพได้ที่หน้าสร้างภาพ";
    }

    /** ปุ่มแท็กให้กดเลือกได้หลายอัน — กดซ้ำคือยกเลิก */
    function renderTagFilter() {
      if (!tagBox) return;
      // แท็กที่เลือกอยู่ต้องแสดงเสมอ แม้หน้านี้จะไม่มีภาพที่ใช้แท็กนั้น
      // ไม่งั้นพอกรองจนไม่เหลือภาพ ปุ่มจะหายแล้วกดยกเลิกไม่ได้
      const names = [...new Set([...knownTags, ...currentTags])].sort();
      tagBox.innerHTML = "";
      names.forEach((name) => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "gallery-tag";
        btn.textContent = name;                    // textContent กัน XSS — ชื่อ tag มาจากผู้ใช้
        btn.dataset.tag = name;
        const active = currentTags.includes(name);
        btn.setAttribute("aria-pressed", String(active));
        if (active) btn.classList.add("is-active");
        btn.addEventListener("click", () => {
          const next = active
            ? currentTags.filter((t) => t !== name)
            : [...currentTags, name];
          loadAssets(1, currentQuery, next);       // เปลี่ยนตัวกรองแล้วต้องกลับหน้า 1 เสมอ
        });
        tagBox.appendChild(btn);
      });
      if (clearBtn) clearBtn.hidden = currentTags.length === 0 && !currentQuery;
    }

    function createAssetCard(item) {
      const card = document.createElement("div");
      card.className = "asset-card";

      const imageWrap = document.createElement("div");
      imageWrap.className = "asset-card__image-wrap";

      const img = document.createElement("img");
      img.className = "asset-card__image";
      img.alt = item.prompt || "ภาพ AI";
      img.loading = "lazy";
      img.src = item.image_url.startsWith("http")
        ? item.image_url
        : `${API_BASE}${item.image_url}`;

      imageWrap.appendChild(img);

      const body = document.createElement("div");
      body.className = "asset-card__body";

      const promptEl = document.createElement("p");
      promptEl.className = "asset-card__prompt";
      promptEl.textContent = item.prompt || "(ไม่มี prompt)";

      const tagsEl = document.createElement("div");
      tagsEl.className = "asset-card__tags";
      (item.tags || []).forEach((name) => {
        const chip = document.createElement("span");
        chip.className = "asset-card__tag";
        chip.textContent = name;                   // textContent กัน XSS
        tagsEl.appendChild(chip);
      });

      const footer = document.createElement("div");
      footer.className = "asset-card__footer";

      const idEl = document.createElement("span");
      idEl.textContent = `#${item.id}`;

      const dateEl = document.createElement("span");
      if (item.created_at) {
        const d = new Date(item.created_at);
        dateEl.textContent = `${d.getDate()}/${d.getMonth() + 1}/${d.getFullYear() + 543}`;
      } else {
        dateEl.textContent = "-";
      }

      const deleteBtn = document.createElement("button");
      deleteBtn.type = "button";
      deleteBtn.className = "asset-card__delete";
      deleteBtn.textContent = "ลบ";
      deleteBtn.addEventListener("click", () => deleteAsset(item, deleteBtn));

      footer.appendChild(idEl);
      footer.appendChild(dateEl);
      footer.appendChild(deleteBtn);

      body.appendChild(promptEl);
      body.appendChild(tagsEl);
      body.appendChild(footer);

      card.appendChild(imageWrap);
      card.appendChild(body);

      return card;
    }

    // #58: ต้องถามยืนยันก่อนลบ — ลบแล้วเอาคืนไม่ได้ (ลบทั้งไฟล์และแถวใน DB)
    async function deleteAsset(item, button) {
      if (!window.confirm(`ลบภาพ #${item.id} ถาวร?\nลบแล้วกู้คืนไม่ได้`)) return;

      button.disabled = true;
      try {
        const res = await fetch(`${API_BASE}/api/assets/${item.id}`, {
          method: "DELETE",
          headers: { ...window.csrfHeaders() },
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          throw new Error(data.error || `HTTP ${res.status}`);
        }
        // ลบใบสุดท้ายของหน้าที่ไม่ใช่หน้าแรก -> ถอยไปหน้าก่อน ไม่ค้างอยู่หน้าว่าง
        const lastOnPage = grid.children.length === 1 && currentPage > 1;
        loadAssets(lastOnPage ? currentPage - 1 : currentPage, currentQuery, currentTags,
                   { replaceUrl: true });
      } catch (err) {
        console.error("Delete asset error:", err);
        alert(`ลบภาพไม่สำเร็จ: ${err.message}`);
        button.disabled = false;
      }
    }

    function updatePagination(page, totalPages) {
      if (pageIndicator) {
        pageIndicator.textContent = `หน้า ${page} จาก ${totalPages}`;
      }
      if (prevBtn) {
        prevBtn.disabled = page <= 1;
      }
      if (nextBtn) {
        nextBtn.disabled = page >= totalPages;
      }
    }

    if (searchForm) {
      searchForm.addEventListener("submit", (e) => {
        e.preventDefault();
        const q = searchInput ? searchInput.value.trim() : "";
        loadAssets(1, q, currentTags);
      });
    }

    if (clearBtn) {
      clearBtn.addEventListener("click", () => {
        if (searchInput) searchInput.value = "";
        loadAssets(1, "", []);
      });
    }

    if (prevBtn) {
      prevBtn.addEventListener("click", () => {
        if (currentPage > 1) {
          loadAssets(currentPage - 1, currentQuery, currentTags);
        }
      });
    }

    if (nextBtn) {
      nextBtn.addEventListener("click", () => {
        loadAssets(currentPage + 1, currentQuery, currentTags);
      });
    }

    // กดย้อนกลับ/ไปข้างหน้าของเบราว์เซอร์ -> โหลดตามเงื่อนไขใน URL
    // fromHistory กัน pushState ซ้ำ ไม่งั้นกดย้อนกลับแล้วจะวนอยู่กับที่
    window.addEventListener("popstate", () => {
      const state = readUrl();
      if (searchInput) searchInput.value = state.query;
      loadAssets(state.page, state.query, state.tags, { fromHistory: true });
    });

    // เปิดหน้ามาด้วย URL ที่มีเงื่อนไขอยู่แล้ว (เช่นก๊อปลิงก์มาจากเพื่อน) ต้องเคารพเงื่อนไขนั้น
    const initial = readUrl();
    if (searchInput) searchInput.value = initial.query;
    loadAssets(initial.page, initial.query, initial.tags, { replaceUrl: true });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initGallery);
  } else {
    initGallery();
  }
})();
