// Load display-safe titles from the backend; default generation remains available offline.
(() => {
  async function loadCheckpoints() {
    const select = document.getElementById("checkpoint");
    const status = document.getElementById("checkpoint-status");
    if (!select || !status) return;
    try {
      const response = await fetch(`${window.LUMA_CONFIG ? window.LUMA_CONFIG.apiBase : ""}/api/checkpoints`);
      if (!response.ok) throw new Error("Model list unavailable");
      const data = await response.json();
      if (!Array.isArray(data.items) || data.items.some(item => typeof item?.title !== "string")) {
        throw new Error("Invalid model list");
      }
      for (const item of data.items) {
        const option = document.createElement("option");
        option.value = item.title;
        option.textContent = item.title;
        select.appendChild(option);
      }
      status.textContent = data.items.length ? "เลือกโมเดลสำหรับภาพนี้ได้เลย" : "ยังไม่มีโมเดลใน Forge";
    } catch (_) {
      status.textContent = "โหลดรายชื่อโมเดลไม่ได้ ใช้ค่าเริ่มต้นได้ หรือลองรีเฟรชหน้าอีกครั้ง";
    }
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", loadCheckpoints);
  else loadCheckpoints();
})();
