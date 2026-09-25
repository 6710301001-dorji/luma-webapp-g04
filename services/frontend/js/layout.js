/**
 * LUMA — Shared layout loader & Auth State Manager
 * -------------------------------------------------------------------------
 * โหลดเมนูกลาง, จัดการ Responsive Toggle, และแสดงสถานะของหน้าปัจจุบัน
 * Issue #56 — โครงหน้าเว็บ UI
 *
 * ห้าม hardcode localhost/IP — อ่าน API base จาก window.LUMA_CONFIG เท่านั้น
 */

(() => {
  const API_BASE = window.LUMA_CONFIG ? window.LUMA_CONFIG.apiBase : "";

  async function initLayout() {
    const slot = document.getElementById("app-nav-slot");
    if (!slot) return;

    try {
      const res = await fetch("../partials/nav.html");
      if (!res.ok) {
        throw new Error(`โหลด nav.html ไม่สำเร็จ (HTTP ${res.status})`);
      }
      slot.innerHTML = await res.text();
      markCurrentPage();
      setupMobileToggle();
      checkAuthStatus();
    } catch (err) {
      console.error("[layout] โหลดเมนูไม่สำเร็จ:", err);
    }
  }

  async function checkAuthStatus() {
    const userSlot = document.getElementById("nav-user-slot");
    if (!userSlot) return;

    try {
      const res = await fetch(`${API_BASE}/api/auth/me`, {
        credentials: "include",
      });

      if (res.ok) {
        const data = await res.json();
        const displayName = data.displayName || data.email.split("@")[0];

        userSlot.innerHTML = "";

        const userGreeting = document.createElement("span");
        userGreeting.style.fontSize = "0.85rem";
        userGreeting.style.color = "#555";
        userGreeting.style.marginRight = "0.5rem";
        userGreeting.textContent = displayName;

        const logoutBtn = document.createElement("button");
        logoutBtn.className = "nav-link-btn";
        logoutBtn.textContent = "ออกจากระบบ";
        logoutBtn.addEventListener("click", handleLogout);

        userSlot.appendChild(userGreeting);
        userSlot.appendChild(logoutBtn);
      } else {
        userSlot.innerHTML = '<a class="app-nav__link" data-page="login" href="login.html">เข้าสู่ระบบ</a>';
      }
    } catch {
      // โหมดออฟไลน์
    }
  }

  async function handleLogout() {
    try {
      await fetch(`${API_BASE}/api/auth/logout`, {
        method: "POST",
        headers: { ...window.csrfHeaders() },
        credentials: "include",
      });
    } catch (err) {
      console.error("Logout error:", err);
    } finally {
      localStorage.removeItem("luma_user_email");
      window.location.href = "login.html";
    }
  }

  function markCurrentPage() {
    const current = document.body.dataset.page;
    if (!current) return;
    document.querySelectorAll(".app-nav__link").forEach((link) => {
      if (link.dataset.page === current) {
        link.setAttribute("aria-current", "page");
      }
    });
  }

  function setupMobileToggle() {
    const toggle = document.querySelector(".app-header__toggle");
    const nav = document.querySelector(".app-nav");
    if (!toggle || !nav) return;

    toggle.addEventListener("click", () => {
      const isOpen = nav.classList.toggle("is-open");
      toggle.setAttribute("aria-expanded", String(isOpen));
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initLayout);
  } else {
    initLayout();
  }
})();
