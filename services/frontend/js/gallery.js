/**
 * LUMA — Personal Gallery Logic
 * -------------------------------------------------------------------------
 * ดึงรายการภาพจาก GET /api/assets แสดงผลเป็นการ์ด Grid
 * รองรับการค้นหาตาม Prompt (?q=...) และการเปลี่ยนหน้า (Pagination)
 *
 * อ้างอิง: Issue #58, docs/API_CONTRACT.md
 *
 * ห้าม hardcode localhost/IP — อ่าน API base จาก window.LUMA_CONFIG เท่านั้น
 */

(() => {
  const API_BASE = window.LUMA_CONFIG ? window.LUMA_CONFIG.apiBase : "";

  let currentPage = 1;
  const perPage = 12;
  let currentQuery = "";

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

    async function loadAssets(page = 1, query = "") {
      currentPage = page;
      currentQuery = query;

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

        const res = await fetch(url.toString());
        if (!res.ok) {
          throw new Error(`โหลดภาพไม่สำเร็จ (HTTP ${res.status})`);
        }

        const data = await res.json();
        const items = data.items || [];
        const total = data.total || 0;

        if (items.length === 0) {
          if (emptyBox) {
            emptyBox.textContent = query
              ? `ไม่พบรูปภาพที่ตรงกับคำค้นหา "${query}"`
              : "ยังไม่มีรูปภาพในคลังผลงาน เริ่มต้นสร้างภาพได้ที่หน้าสร้างภาพ";
            emptyBox.removeAttribute("hidden");
          }
        } else {
          items.forEach((item) => {
            const card = createAssetCard(item);
            grid.appendChild(card);
          });
        }

        updatePagination(data.page || 1, Math.ceil(total / perPage) || 1);
      } catch (err) {
        console.error("Gallery load error:", err);
        if (errorBox) {
          errorBox.textContent = "ไม่สามารถเชื่อมต่อเซิร์ฟเวอร์เพื่อโหลดรูปภาพได้";
          errorBox.removeAttribute("hidden");
        }
      }
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

      footer.appendChild(idEl);
      footer.appendChild(dateEl);

      body.appendChild(promptEl);
      body.appendChild(footer);

      card.appendChild(imageWrap);
      card.appendChild(body);

      return card;
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
        loadAssets(1, q);
      });
    }

    if (prevBtn) {
      prevBtn.addEventListener("click", () => {
        if (currentPage > 1) {
          loadAssets(currentPage - 1, currentQuery);
        }
      });
    }

    if (nextBtn) {
      nextBtn.addEventListener("click", () => {
        loadAssets(currentPage + 1, currentQuery);
      });
    }

    // เริ่มต้นโหลดภาพหน้าแรก
    loadAssets(1, "");
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initGallery);
  } else {
    initGallery();
  }
})();
