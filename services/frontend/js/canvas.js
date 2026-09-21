/**
 * LUMA — Smart Canvas & Image Studio Logic
 * -------------------------------------------------------------------------
 * จัดการ Canvas, อัปโหลดภาพจากเครื่อง, สกัดจานสี 5 โทนเด่น (#60)
 * และส่งคำขอลบพื้นหลังไปยัง Pipeline (#61)
 */

(() => {
  const API_BASE = window.LUMA_CONFIG ? window.LUMA_CONFIG.apiBase : "http://127.0.0.1:5000";

  function initCanvasStudio() {
    const uploadInput = document.getElementById("canvas-upload-input");
    const previewContainer = document.getElementById("canvas-preview-container");
    const previewImg = document.getElementById("canvas-preview-img");
    const placeholder = document.getElementById("canvas-placeholder");
    const removeBgBtn = document.getElementById("btn-remove-bg");
    const extractPaletteBtn = document.getElementById("btn-extract-palette");
    const paletteContainer = document.getElementById("palette-container");
    const paletteSwatches = document.getElementById("palette-swatches");

    let currentImageBase64 = null;

    // จานสีที่โชว์อยู่ต้องเป็นของภาพปัจจุบันเสมอ — ล้างทิ้งตอนเปลี่ยนภาพและตอนสกัดสีล้ม
    function clearPalette() {
      if (paletteSwatches) paletteSwatches.innerHTML = "";
      if (paletteContainer) paletteContainer.setAttribute("hidden", "");
    }

    if (uploadInput) {
      uploadInput.addEventListener("change", (e) => {
        const file = e.target.files[0];
        if (!file) return;

        const reader = new FileReader();
        reader.onload = (event) => {
          currentImageBase64 = event.target.result;
          clearPalette();
          previewImg.src = currentImageBase64;
          previewImg.removeAttribute("hidden");
          placeholder.setAttribute("hidden", "");
          previewContainer.classList.add("has-image");

          if (removeBgBtn) removeBgBtn.disabled = false;
          if (extractPaletteBtn) extractPaletteBtn.disabled = false;
        };
        reader.readAsDataURL(file);
      });
    }

    if (extractPaletteBtn) {
      extractPaletteBtn.addEventListener("click", async () => {
        if (!currentImageBase64) return;

        extractPaletteBtn.disabled = true;
        extractPaletteBtn.textContent = "กำลังสกัดสี…";

        try {
          const res = await fetch(`${API_BASE}/api/pipeline/palette/extract`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ image: currentImageBase64 }),
          });

          // ห้าม fallback เป็นสีตายตัว — ผู้ใช้จะเข้าใจว่าเป็นสีจากภาพของตัวเอง
          const data = await res.json().catch(() => ({}));
          if (!res.ok || !Array.isArray(data.colors)) {
            throw new Error(data.error || `HTTP ${res.status}`);
          }
          const colors = data.colors;

          paletteSwatches.innerHTML = "";
          colors.forEach((hex) => {
            const swatch = document.createElement("div");
            swatch.className = "palette-color-box";
            swatch.style.backgroundColor = hex;
            swatch.textContent = hex;
            swatch.title = `คลิกเพื่อคัดลอก ${hex}`;

            swatch.addEventListener("click", () => {
              navigator.clipboard.writeText(hex);
              const originalText = swatch.textContent;
              swatch.textContent = "Copied!";
              setTimeout(() => {
                swatch.textContent = originalText;
              }, 1200);
            });

            paletteSwatches.appendChild(swatch);
          });

          paletteContainer.removeAttribute("hidden");
        } catch (err) {
          console.error("Palette extract error:", err);
          clearPalette();
          alert("ไม่สามารถสกัดสีได้ ตรวจสอบการเชื่อมต่อเซิร์ฟเวอร์");
        } finally {
          extractPaletteBtn.disabled = false;
          extractPaletteBtn.textContent = "🎨 สกัดจานสีจากภาพ";
        }
      });
    }

    if (removeBgBtn) {
      removeBgBtn.addEventListener("click", async () => {
        if (!currentImageBase64) return;

        removeBgBtn.disabled = true;
        removeBgBtn.textContent = "กำลังตัดพื้นหลัง…";

        try {
          const res = await fetch(`${API_BASE}/api/pipeline/segmentation/remove_bg`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ image: currentImageBase64 }),
          });

          const data = await res.json().catch(() => ({}));
          if (!res.ok || !data.result_image) {
            throw new Error(data.error || `HTTP ${res.status}`);
          }
          previewImg.src = data.result_image;
          alert("ลบพื้นหลังสำเร็จเรียบร้อย");
        } catch (err) {
          console.error("Remove bg error:", err);
          alert("ไม่สามารถลบพื้นหลังได้ในขณะนี้");
        } finally {
          removeBgBtn.disabled = false;
          removeBgBtn.textContent = "✂️ ลบพื้นหลังอัตโนมัติ";
        }
      });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initCanvasStudio);
  } else {
    initCanvasStudio();
  }
})();
