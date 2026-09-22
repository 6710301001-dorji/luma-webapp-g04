/**
 * LUMA — img2img 4 โหมด (Issue #33, Lecture 2 หน้า 58–61)
 * -------------------------------------------------------------------------
 * text           ส่งภาพต้นฉบับ + prompt
 * sketch         วาดเส้นสีลงบนภาพ แล้วส่งภาพที่วาดแล้ว
 * inpaint        ระบายบริเวณที่จะแก้ -> mask ขาว/ดำ ส่งคู่กับภาพต้นฉบับ
 * inpaint-sketch วาดเส้นสีบนภาพ และเส้นเดียวกันเป็น mask ด้วย
 *
 * POST /api/img2img (docs/API_CONTRACT.md) · ห้าม hardcode localhost/IP
 */

(() => {
  const API_BASE = window.LUMA_CONFIG ? window.LUMA_CONFIG.apiBase : "";
  const MAX_SIDE = 1024; // ภาพใหญ่กว่านี้ย่อก่อนส่ง — Forge รับสูงสุด 1024 และ payload ไม่บวม

  const MODE_HINTS = {
    text: "AI วาดใหม่ทั้งภาพโดยคงโครงเดิมตาม denoising strength",
    sketch: "วาดเส้นสีลงบนภาพ AI จะใช้เส้นเป็นแนวทาง",
    inpaint: "ระบายเฉพาะบริเวณที่อยากให้ AI วาดใหม่ ส่วนอื่นคงเดิม",
    "inpaint-sketch": "วาดเส้นสีเฉพาะบริเวณที่จะแก้ — เส้นเป็นทั้งแนวทางและขอบเขต",
  };

  function initImg2Img() {
    const $ = (id) => document.getElementById(id);
    const form = $("i2i-form");
    if (!form) return;

    const upload = $("i2i-upload");
    const modeSelect = $("i2i-mode");
    const modeHint = $("i2i-mode-hint");
    const brushBox = $("i2i-brush");
    const brushSize = $("i2i-brush-size");
    const brushSizeValue = $("i2i-brush-size-value");
    const brushColor = $("i2i-brush-color");
    const colorGroup = $("i2i-color-group");
    const clearBtn = $("i2i-clear");
    const strength = $("i2i-strength");
    const strengthValue = $("i2i-strength-value");
    const stage = $("i2i-stage");
    const placeholder = $("i2i-placeholder");
    const base = $("i2i-base");
    const maskLayer = $("i2i-mask");
    const errorBox = $("i2i-error");
    const submitBtn = $("i2i-submit");
    const result = $("i2i-result");
    const resultImg = $("i2i-result-img");

    // original: ภาพต้นฉบับที่ไม่มีเส้นวาด — inpaint ต้องส่งอันนี้ ไม่ใช่ภาพที่ระบายทับแล้ว
    const original = document.createElement("canvas");
    let hasImage = false;
    let hasMaskStroke = false;
    let drawing = null;

    const mode = () => modeSelect.value;
    const drawsColor = () => mode() === "sketch" || mode() === "inpaint-sketch";
    const drawsMask = () => mode().startsWith("inpaint");

    function showError(message) {
      errorBox.textContent = message;
      errorBox.removeAttribute("hidden");
    }

    function clearError() {
      errorBox.textContent = "";
      errorBox.setAttribute("hidden", "");
    }

    function resetDrawing() {
      if (!hasImage) return;
      const ctx = base.getContext("2d");
      ctx.clearRect(0, 0, base.width, base.height);
      ctx.drawImage(original, 0, 0);
      maskLayer.getContext("2d").clearRect(0, 0, maskLayer.width, maskLayer.height);
      hasMaskStroke = false;
    }

    function updateModeUi() {
      if (modeHint) modeHint.textContent = MODE_HINTS[mode()] || "";
      const canDraw = mode() !== "text";
      if (canDraw) brushBox.removeAttribute("hidden"); else brushBox.setAttribute("hidden", "");
      if (colorGroup) {
        if (drawsColor()) colorGroup.removeAttribute("hidden"); else colorGroup.setAttribute("hidden", "");
      }
      stage.classList[canDraw && hasImage ? "add" : "remove"]("is-drawable");
      // เปลี่ยนโหมดแล้วเส้นเดิมมีความหมายคนละแบบ (สี vs mask) — ล้างทิ้งกันส่งผิด
      resetDrawing();
    }

    function loadImage(dataUrl) {
      const img = new Image();
      img.onload = () => {
        const scale = Math.min(1, MAX_SIDE / Math.max(img.naturalWidth, img.naturalHeight));
        const width = Math.round(img.naturalWidth * scale);
        const height = Math.round(img.naturalHeight * scale);
        for (const canvas of [original, base, maskLayer]) {
          canvas.width = width;
          canvas.height = height;
        }
        original.getContext("2d").drawImage(img, 0, 0, width, height);
        hasImage = true;
        base.removeAttribute("hidden");
        maskLayer.removeAttribute("hidden");
        placeholder.setAttribute("hidden", "");
        clearError();
        updateModeUi();
      };
      img.src = dataUrl;
    }

    upload.addEventListener("change", (e) => {
      const file = e.target.files[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = (event) => loadImage(event.target.result);
      reader.readAsDataURL(file);
    });

    // ---- วาด: pointer events บนชั้น mask (อยู่บนสุด) + pointer capture ------------
    function toCanvasPoint(e) {
      const rect = maskLayer.getBoundingClientRect();
      return {
        x: (e.clientX - rect.left) * (maskLayer.width / rect.width),
        y: (e.clientY - rect.top) * (maskLayer.height / rect.height),
      };
    }

    function strokeTo(point) {
      const size = Number(brushSize.value);
      const layers = [];
      if (drawsColor()) layers.push([base.getContext("2d"), brushColor.value]);
      // สีบนชั้น mask ใช้แค่แสดงผล — ตอนส่งทุกพิกเซลที่ระบายกลายเป็นสีขาว
      if (drawsMask()) layers.push([maskLayer.getContext("2d"), "#ff0000"]);
      for (const [ctx, color] of layers) {
        ctx.strokeStyle = color;
        ctx.lineWidth = size;
        ctx.lineCap = "round";
        ctx.lineJoin = "round";
        ctx.beginPath();
        ctx.moveTo(drawing.x, drawing.y);
        ctx.lineTo(point.x, point.y);
        ctx.stroke();
      }
      if (drawsMask()) hasMaskStroke = true;
      drawing = point;
    }

    maskLayer.addEventListener("pointerdown", (e) => {
      if (!hasImage || mode() === "text") return;
      drawing = toCanvasPoint(e);
      if (maskLayer.setPointerCapture) maskLayer.setPointerCapture(e.pointerId);
      strokeTo(drawing); // แตะจุดเดียวก็ได้จุด
      if (e.preventDefault) e.preventDefault();
    });
    maskLayer.addEventListener("pointermove", (e) => {
      if (drawing) strokeTo(toCanvasPoint(e));
    });
    const stop = () => { drawing = null; };
    maskLayer.addEventListener("pointerup", stop);
    maskLayer.addEventListener("pointercancel", stop);

    // mask ตาม contract: ขาว = วาดใหม่ · ดำ = คงเดิม · ขนาดเท่าภาพ
    function exportMask() {
      const { width, height } = maskLayer;
      const painted = maskLayer.getContext("2d").getImageData(0, 0, width, height);
      const out = document.createElement("canvas");
      out.width = width;
      out.height = height;
      const ctx = out.getContext("2d");
      const bw = ctx.createImageData(width, height);
      for (let i = 0; i < painted.data.length; i += 4) {
        const value = painted.data[i + 3] > 0 ? 255 : 0;
        bw.data[i] = value;
        bw.data[i + 1] = value;
        bw.data[i + 2] = value;
        bw.data[i + 3] = 255;
      }
      ctx.putImageData(bw, 0, 0);
      return out.toDataURL("image/png");
    }

    brushSize.addEventListener("input", () => {
      brushSizeValue.textContent = brushSize.value;
    });
    strength.addEventListener("input", () => {
      strengthValue.textContent = Number(strength.value).toFixed(2);
    });
    modeSelect.addEventListener("change", updateModeUi);
    clearBtn.addEventListener("click", resetDrawing);

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      clearError();

      const prompt = $("i2i-prompt").value.trim();
      if (!hasImage) return showError("เลือกภาพต้นฉบับก่อน");
      if (!prompt) return showError("กรุณาระบุ prompt");
      if (drawsMask() && !hasMaskStroke) return showError("โหมด inpaint ต้องระบายบริเวณที่จะแก้ก่อน");

      const payload = {
        prompt,
        negative_prompt: $("i2i-negative").value.trim(),
        mode: mode(),
        // sketch ส่งภาพที่วาดเส้นแล้ว · text/inpaint ส่งภาพต้นฉบับ (ไม่มีสีแดงของ mask ติดไป)
        init_image: (drawsColor() ? base : original).toDataURL("image/png"),
        mask: drawsMask() ? exportMask() : null,
        denoising_strength: Number(strength.value),
        steps: parseInt($("i2i-steps").value, 10),
        cfg_scale: parseFloat($("i2i-cfg").value),
        seed: Number.isNaN(parseInt($("i2i-seed").value, 10)) ? -1 : parseInt($("i2i-seed").value, 10),
      };

      submitBtn.disabled = true;
      submitBtn.textContent = "AI กำลังแก้ภาพ…";
      try {
        const res = await fetch(`${API_BASE}/api/img2img`, {
          method: "POST",
          headers: { "Content-Type": "application/json", ...window.csrfHeaders() },
          body: JSON.stringify(payload),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok || !data.image_url) {
          throw new Error(data.error || `แก้ภาพไม่สำเร็จ (HTTP ${res.status})`);
        }
        resultImg.src = `${API_BASE}${data.image_url}`;
        result.removeAttribute("hidden");
      } catch (err) {
        console.error("img2img error:", err);
        showError(err.message);
      } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = "✨ แก้ภาพด้วย AI";
      }
    });

    updateModeUi();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initImg2Img);
  } else {
    initImg2Img();
  }
})();
