/**
 * LUMA — Register form
 * -------------------------------------------------------------------------
 * สมัครผ่าน POST /api/auth/register (backend จริง) แล้วพาไปหน้า login
 *
 * ห้าม hardcode localhost/IP — อ่าน API base จาก window.LUMA_CONFIG เท่านั้น
 *
 * หมายเหตุ: การเช็ค "อีเมลนี้มีคนใช้แล้วหรือยัง" ทำที่ backend เท่านั้น
 * (ดู #49 "กันการเดาว่ามีบัญชีอยู่จริง")
 */

const API_BASE = window.LUMA_CONFIG ? window.LUMA_CONFIG.apiBase : "";
const MIN_PASSWORD_LENGTH = 8;

function initRegisterForm() {
  const form = document.getElementById("register-form");
  if (!form) return;

  const errorBox = document.getElementById("register-error");
  const submitBtn = document.getElementById("register-submit");

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    hideError();

    const displayName = form.displayName.value.trim();
    const email = form.email.value.trim();
    const password = form.password.value;
    const confirmPassword = form.confirmPassword.value;

    const validationError = validate({
      displayName,
      email,
      password,
      confirmPassword,
    });
    if (validationError) {
      showError(validationError);
      return;
    }

    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ displayName, email, password }),
      });
      // 500 จาก proxy/server อาจไม่ใช่ JSON — อย่าให้ res.json() โยนแทนข้อความจริง
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        showError(data.error || `สมัครสมาชิกไม่สำเร็จ (HTTP ${res.status})`);
        return;
      }

      // login.js แสดงข้อความ "สมัครสำเร็จ" เมื่อเห็น ?registered=true
      window.location.href = "login.html?registered=true";
    } catch (err) {
      showError(err.message || "เกิดข้อผิดพลาด ลองใหม่อีกครั้ง");
    } finally {
      setLoading(false);
    }
  });

  /** ตรวจฝั่ง client เท่านั้น — เช็คอีเมลซ้ำต้องทำที่ backend (#49) */
  function validate({ displayName, email, password, confirmPassword }) {
    if (!displayName || !email || !password || !confirmPassword) {
      return "กรอกข้อมูลให้ครบทุกช่อง";
    }
    if (password.length < MIN_PASSWORD_LENGTH) {
      return `รหัสผ่านต้องยาวอย่างน้อย ${MIN_PASSWORD_LENGTH} ตัวอักษร`;
    }
    if (password !== confirmPassword) {
      return "รหัสผ่านทั้งสองช่องไม่ตรงกัน";
    }
    return null;
  }

  function showError(message) {
    // ใช้ textContent เสมอ ไม่ใช้ innerHTML เพราะข้อความ error
    // อาจสะท้อนกลับมาจาก backend ในอนาคต ป้องกัน stored/reflected XSS
    errorBox.textContent = message;
    errorBox.removeAttribute("hidden");
  }

  function hideError() {
    errorBox.textContent = "";
    errorBox.setAttribute("hidden", "");
  }

  function setLoading(isLoading) {
    submitBtn.disabled = isLoading;
    submitBtn.textContent = isLoading ? "กำลังสมัครสมาชิก…" : "สมัครสมาชิก";
  }
}

document.addEventListener("DOMContentLoaded", initRegisterForm);