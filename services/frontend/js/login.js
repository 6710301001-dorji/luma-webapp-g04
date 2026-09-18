/**
 * LUMA — Login Page Logic
 * -------------------------------------------------------------------------
 * จัดการฟอร์มเข้าสู่ระบบ และส่งคำขอไปยัง POST /api/auth/login
 * พร้อมส่ง Session Cookie ข้ามพอร์ต (credentials: "include")
 *
 * อ้างอิง: Issue #50, docs/API_CONTRACT.md
 *
 * ห้าม hardcode localhost/IP — อ่าน API base จาก window.LUMA_CONFIG เท่านั้น
 */

(() => {
  const API_BASE = window.LUMA_CONFIG ? window.LUMA_CONFIG.apiBase : "";

  function initLogin() {
    const form = document.getElementById("login-form");
    if (!form) return;

    const errorBox = document.getElementById("login-error");
    const successBox = document.getElementById("login-success");
    const submitBtn = document.getElementById("login-submit");

    // ตรวจสอบว่าเพิ่งสมัครสมาชิกสำเร็จมาหรือไม่
    const params = new URLSearchParams(window.location.search);
    if (params.get("registered") === "true" && successBox) {
      successBox.textContent = "สมัครสมาชิกสำเร็จเรียบร้อย! กรุณาเข้าสู่ระบบด้วยอีเมลและรหัสผ่านของคุณ";
      successBox.removeAttribute("hidden");
    }

    function showError(msg) {
      if (errorBox) {
        errorBox.textContent = msg;
        errorBox.removeAttribute("hidden");
      }
      if (successBox) successBox.setAttribute("hidden", "");
    }

    function hideMessages() {
      if (errorBox) errorBox.setAttribute("hidden", "");
      if (successBox) successBox.setAttribute("hidden", "");
    }

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      hideMessages();

      const email = form.email ? form.email.value.trim() : "";
      const password = form.password ? form.password.value : "";

      if (!email || !password) {
        showError("กรุณากรอกอีเมลและรหัสผ่าน");
        return;
      }

      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.textContent = "กำลังเข้าสู่ระบบ…";
      }

      try {
        const res = await fetch(`${API_BASE}/api/auth/login`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          credentials: "include",
          body: JSON.stringify({
            email,
            password,
          }),
        });

        const data = await res.json();

        if (!res.ok) {
          throw new Error(data.error || `เข้าสู่ระบบไม่สำเร็จ (HTTP ${res.status})`);
        }

        localStorage.setItem("luma_user_email", email);

        if (successBox) {
          successBox.textContent = "เข้าสู่ระบบสำเร็จ! กำลังนำท่านเข้าสู่ระบบ…";
          successBox.removeAttribute("hidden");
        }

        setTimeout(() => {
          window.location.href = "generate.html";
        }, 1000);
      } catch (err) {
        console.error("Login error:", err);
        showError(err.message || "เกิดข้อผิดพลาดในการเชื่อมต่อเซิร์ฟเวอร์");
      } finally {
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.textContent = "เข้าสู่ระบบ";
        }
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initLogin);
  } else {
    initLogin();
  }
})();