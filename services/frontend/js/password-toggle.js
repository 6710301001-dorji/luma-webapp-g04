/**
 * LUMA — ปุ่มรูปตาสลับแสดง/ซ่อนรหัสผ่าน (หน้า login และ register)
 * -------------------------------------------------------------------------
 * ใช้ร่วมกันทั้งสองหน้า — หา .auth-field__toggle ทุกตัวในหน้าแล้วผูก click เอง
 * ไม่ต้องแก้ login.js/register.js เลย เพราะแค่สลับ type ของ input ข้างๆ ปุ่ม
 */

(() => {
  function initPasswordToggles() {
    document.querySelectorAll(".auth-field__toggle").forEach((btn) => {
      const wrap = btn.closest(".auth-field__input-wrap");
      const input = wrap ? wrap.querySelector("input") : null;
      const eye = btn.querySelector(".auth-field__eye");
      const eyeOff = btn.querySelector(".auth-field__eye-off");
      if (!input) return;

      btn.addEventListener("click", () => {
        const show = input.type === "password";
        input.type = show ? "text" : "password";
        btn.setAttribute("aria-label", show ? "ซ่อนรหัสผ่าน" : "แสดงรหัสผ่าน");
        btn.setAttribute("aria-pressed", String(show));
        // ห้ามใช้ eye.hidden = show — SVGElement ไม่มี IDL property "hidden" ที่
        // สะท้อนกลับไปเป็น attribute จริงแบบ HTMLElement ไอคอนเลยไม่สลับเลยสักครั้ง
        // (รีวิว PR #204 โดย @6710301001-dorji) ต้องสั่ง attribute ตรงๆ แทน
        if (eye) eye.toggleAttribute("hidden", show);
        if (eyeOff) eyeOff.toggleAttribute("hidden", !show);
      });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initPasswordToggles);
  } else {
    initPasswordToggles();
  }
})();
