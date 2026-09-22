/**
 * LUMA — Smart Canvas & Image Studio Logic
 * -------------------------------------------------------------------------
 * จัดการ Canvas, อัปโหลดภาพจากเครื่องหรือเลือกจากแกลเลอรี, ลากย้าย/ปรับขนาด,
 * สกัดจานสี 5 โทนเด่น (#60) และส่งคำขอลบพื้นหลังไปยัง Pipeline (#61)
 */

(() => {
  const API_BASE = window.LUMA_CONFIG ? window.LUMA_CONFIG.apiBase : "";
  // backend ยังไม่มี /api/pipeline/segmentation/remove_bg (#61, #101) — เปิดเป็น true เมื่อมีแล้ว
  const REMOVE_BG_READY = false;

  function initCanvasStudio() {
    const uploadInput = document.getElementById("canvas-upload-input");
    const previewContainer = document.getElementById("canvas-preview-container");
    const previewImg = document.getElementById("canvas-preview-img");
    const placeholder = document.getElementById("canvas-placeholder");
    const removeBgBtn = document.getElementById("btn-remove-bg");
    const extractPaletteBtn = document.getElementById("btn-extract-palette");
    const paletteContainer = document.getElementById("palette-container");
    const paletteSwatches = document.getElementById("palette-swatches");
    const pickGalleryBtn = document.getElementById("btn-pick-gallery");
    const picker = document.getElementById("gallery-picker");
    const pickerMessage = document.getElementById("gallery-picker-message");
    const scaleInput = document.getElementById("canvas-scale");
    const scaleValue = document.getElementById("canvas-scale-value");
    const resetLayoutBtn = document.getElementById("btn-reset-layout");

    let currentImageBase64 = null;
    // ตำแหน่ง/ขนาดของภาพบนพื้นที่ทำงาน (#60) — ใช้ CSS transform ไม่แตะพิกเซลของภาพ
    // จานสีและลบพื้นหลังจึงยังใช้ภาพต้นฉบับเต็มใบเสมอ
    const layout = { x: 0, y: 0, scale: 1 };
    let drag = null;

    // จานสีที่โชว์อยู่ต้องเป็นของภาพปัจจุบันเสมอ — ล้างทิ้งตอนเปลี่ยนภาพและตอนสกัดสีล้ม
    function clearPalette() {
      if (paletteSwatches) paletteSwatches.innerHTML = "";
      if (paletteContainer) paletteContainer.setAttribute("hidden", "");
    }

    function applyLayout() {
      previewImg.style.transform = `translate(${layout.x}px, ${layout.y}px) scale(${layout.scale})`;
      if (scaleInput) scaleInput.value = String(Math.round(layout.scale * 100));
      if (scaleValue) scaleValue.textContent = `${Math.round(layout.scale * 100)}%`;
    }

    function resetLayout() {
      layout.x = 0;
      layout.y = 0;
      layout.scale = 1;
      applyLayout();
    }

    // ทางเข้าเดียวของภาพ — อัปโหลดและเลือกจากแกลเลอรีต้องได้สถานะเหมือนกันทุกอย่าง
    function setImage(dataUrl) {
      currentImageBase64 = dataUrl;
      clearPalette();
      previewImg.src = currentImageBase64;
      previewImg.removeAttribute("hidden");
      placeholder.setAttribute("hidden", "");
      previewContainer.classList.add("has-image");
      resetLayout();

      if (removeBgBtn) removeBgBtn.disabled = !REMOVE_BG_READY;
      if (extractPaletteBtn) extractPaletteBtn.disabled = false;
      if (scaleInput) scaleInput.disabled = false;
      if (resetLayoutBtn) resetLayoutBtn.disabled = false;
    }

    function readAsDataUrl(blob, onDone) {
      const reader = new FileReader();
      reader.onload = (event) => onDone(event.target.result);
      reader.readAsDataURL(blob);
    }

    if (uploadInput) {
      uploadInput.addEventListener("change", (e) => {
        const file = e.target.files[0];
        if (!file) return;
        readAsDataUrl(file, setImage);
      });
    }

    // ลากย้าย: pointer capture ส่ง move/up มาที่ตัวภาพเอง ไม่ต้องฟังทั้ง window
    previewImg.addEventListener("pointerdown", (e) => {
      if (!currentImageBase64) return;
      drag = { pointerX: e.clientX, pointerY: e.clientY, startX: layout.x, startY: layout.y };
      if (previewImg.setPointerCapture) previewImg.setPointerCapture(e.pointerId);
      previewImg.classList.add("is-dragging");
      if (e.preventDefault) e.preventDefault();
    });
    previewImg.addEventListener("pointermove", (e) => {
      if (!drag) return;
      layout.x = drag.startX + (e.clientX - drag.pointerX);
      layout.y = drag.startY + (e.clientY - drag.pointerY);
      applyLayout();
    });
    const endDrag = () => {
      drag = null;
      previewImg.classList.remove("is-dragging");
    };
    previewImg.addEventListener("pointerup", endDrag);
    previewImg.addEventListener("pointercancel", endDrag);

    if (scaleInput) {
      scaleInput.addEventListener("input", () => {
        layout.scale = Number(scaleInput.value) / 100;
        applyLayout();
      });
    }
    if (resetLayoutBtn) resetLayoutBtn.addEventListener("click", resetLayout);

    function showPickerMessage(text) {
      if (!pickerMessage) return;
      pickerMessage.textContent = text;
      pickerMessage.removeAttribute("hidden");
    }

    async function pickFromGallery(item) {
      try {
        // same-origin: cookie session ติดไปเอง — /image เช็คเจ้าของ (#115)
        const res = await fetch(`${API_BASE}${item.image_url}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        readAsDataUrl(await res.blob(), setImage);
      } catch (err) {
        console.error("Gallery image load error:", err);
        showPickerMessage("โหลดภาพนี้ไม่สำเร็จ ลองใหม่อีกครั้ง");
      }
    }

    if (pickGalleryBtn && picker) {
      pickGalleryBtn.addEventListener("click", async () => {
        picker.innerHTML = "";
        picker.setAttribute("hidden", "");
        if (pickerMessage) pickerMessage.setAttribute("hidden", "");
        pickGalleryBtn.disabled = true;
        try {
          const res = await fetch(`${API_BASE}/api/assets?per_page=24`);
          if (res.status === 401) {
            showPickerMessage("เข้าสู่ระบบก่อน ถึงจะเลือกภาพจากแกลเลอรีได้");
            return;
          }
          if (!res.ok) throw new Error(`HTTP ${res.status}`);
          const items = (await res.json()).items || [];
          if (items.length === 0) {
            showPickerMessage("ยังไม่มีภาพในแกลเลอรี สร้างภาพได้ที่หน้าสร้างภาพ");
            return;
          }
          items.forEach((item) => {
            const thumb = document.createElement("img");
            thumb.className = "canvas-picker__thumb";
            thumb.src = `${API_BASE}${item.image_url}`;
            thumb.alt = item.prompt || `ภาพ #${item.id}`;
            thumb.title = item.prompt || `ภาพ #${item.id}`;
            thumb.addEventListener("click", () => pickFromGallery(item));
            picker.appendChild(thumb);
          });
          picker.removeAttribute("hidden");
        } catch (err) {
          console.error("Gallery list error:", err);
          showPickerMessage("โหลดรายการภาพไม่สำเร็จ ตรวจสอบการเชื่อมต่อเซิร์ฟเวอร์");
        } finally {
          pickGalleryBtn.disabled = false;
        }
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
            headers: { "Content-Type": "application/json", ...window.csrfHeaders() },
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
            headers: { "Content-Type": "application/json", ...window.csrfHeaders() },
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
