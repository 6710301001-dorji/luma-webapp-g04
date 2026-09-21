/**
 * LUMA — Generate Image Logic
 * -------------------------------------------------------------------------
 * จัดการฟอร์มสร้างภาพจาก Prompt ส่งคำขอไปยัง POST /api/generate
 * และแสดงผลลัพธ์ภาพที่ได้บนหน้าเว็บ
 *
 * อ้างอิง: Issue #57, docs/API_CONTRACT.md
 */

(() => {
  const API_BASE = window.LUMA_CONFIG ? window.LUMA_CONFIG.apiBase : "http://127.0.0.1:5000";

  function initGeneratePage() {
    const form = document.getElementById("generate-form");
    if (!form) return;

    const submitBtn = document.getElementById("generate-submit");
    const errorBox = document.getElementById("generate-error");
    const spinner = document.getElementById("generate-spinner");
    const previewContainer = document.getElementById("preview-container");
    const previewImage = document.getElementById("preview-image");
    const previewPlaceholder = document.getElementById("preview-placeholder");
    const previewMeta = document.getElementById("preview-meta");
    const metaAssetId = document.getElementById("meta-asset-id");
    const metaPrompt = document.getElementById("meta-prompt");

    let isGenerating = false;

    async function handleGenerateSubmit(event) {
      if (event) {
        event.preventDefault();
        event.stopPropagation();
      }

      // ป้องกันการยิงคำขอซ้ำซ้อน (Debounce / Double Submit Lock)
      if (isGenerating) return false;
      isGenerating = true;

      hideError();

      const prompt = form.prompt ? form.prompt.value.trim() : "";
      if (!prompt) {
        showError("กรุณากรอก Prompt สำหรับสร้างภาพ");
        isGenerating = false;
        return false;
      }

      const negative_prompt = form.negative_prompt ? form.negative_prompt.value.trim() : "";
      const steps = parseInt(form.steps ? form.steps.value : "20", 10) || 20;
      const cfg_scale = parseFloat(form.cfg_scale ? form.cfg_scale.value : "8.0") || 8.0;
      const sampler_name = form.sampler_name ? form.sampler_name.value : "DPM++ 2M Karras";
      // ห้ามใช้ `|| -1` — seed 0 เป็นค่าที่ถูกต้อง แต่เป็น falsy จะกลายเป็น -1 (สุ่ม)
      const parsedSeed = parseInt(form.seed ? form.seed.value : "-1", 10);
      const seed = Number.isNaN(parsedSeed) ? -1 : parsedSeed;
      const width = parseInt(form.width ? form.width.value : "512", 10) || 512;
      const height = parseInt(form.height ? form.height.value : "512", 10) || 512;

      const payload = {
        prompt,
        negative_prompt,
        steps,
        cfg_scale,
        sampler_name,
        seed,
        width,
        height,
      };

      setLoading(true);

      try {
        const res = await fetch(`${API_BASE}/api/generate`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(payload),
        });

        const data = await res.json();

        if (!res.ok) {
          throw new Error(data.error || `สร้างภาพไม่สำเร็จ (HTTP ${res.status})`);
        }

        // แสดงผลภาพที่สร้างสำเร็จ
        const imageUrl = data.image_url.startsWith("http")
          ? data.image_url
          : `${API_BASE}${data.image_url}`;

        previewImage.src = imageUrl;
        previewImage.removeAttribute("hidden");
        previewPlaceholder.setAttribute("hidden", "");
        previewContainer.classList.add("has-image");

        // แสดงข้อมูล Metadata ป้องกัน XSS ด้วย textContent
        if (metaAssetId) metaAssetId.textContent = data.asset_id;
        if (metaPrompt) metaPrompt.textContent = prompt;
        if (previewMeta) previewMeta.removeAttribute("hidden");
      } catch (err) {
        console.error("Generate error:", err);
        showError(err.message || "ไม่สามารถเชื่อมต่อเซิร์ฟเวอร์ได้ ตรวจสอบว่า Backend และ AI Engine ทำงานอยู่");
      } finally {
        isGenerating = false;
        setLoading(false);
      }

      return false;
    }

    form.addEventListener("submit", handleGenerateSubmit);

    function showError(message) {
      errorBox.textContent = message;
      errorBox.removeAttribute("hidden");
    }

    function hideError() {
      errorBox.textContent = "";
      errorBox.setAttribute("hidden", "");
    }

    function setLoading(isLoading) {
      if (submitBtn) {
        submitBtn.disabled = isLoading;
        submitBtn.textContent = isLoading ? "กำลังสร้างภาพ…" : "สร้างภาพ (Generate)";
      }
      if (spinner) {
        if (isLoading) {
          spinner.removeAttribute("hidden");
        } else {
          spinner.setAttribute("hidden", "");
        }
      }
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initGeneratePage);
  } else {
    initGeneratePage();
  }
})();
