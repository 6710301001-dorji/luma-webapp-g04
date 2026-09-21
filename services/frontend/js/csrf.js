/**
 * LUMA — CSRF header (#51)
 * -------------------------------------------------------------------------
 * backend ส่ง token มาใน cookie `csrf_token` ทุก response
 * ทุก fetch ที่เป็น POST ต้องใส่ `...window.csrfHeaders()` ใน headers ไม่งั้นได้ 400
 */
window.csrfHeaders = function () {
  const match = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]*)/);
  return match ? { "X-CSRFToken": decodeURIComponent(match[1]) } : {};
};
