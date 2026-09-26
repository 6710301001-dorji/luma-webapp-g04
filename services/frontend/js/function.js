/**
 * LUMA — หน้า Function (Issue #163)
 * -------------------------------------------------------------------------
 * สองเครื่องมือ: เบลอเฉพาะกรอบที่ลากเลือก · ตีกรอบวัตถุในภาพ
 *
 * ไล่เป็นขั้น: เลือกฟังก์ชัน -> เลือกภาพ -> ทำงาน
 * สองฟังก์ชันนี้ทำงานแยกกัน ไม่ได้ทำต่อจากกัน จึงแสดงทีละอันตามที่ผู้ใช้เลือก
 * แสดงพร้อมกันทั้งคู่ทำให้เข้าใจผิดว่าต้องทำเรียงกัน
 *
 * หน้าเว็บไม่ประมวลผลภาพเอง — ส่งไป backend ซึ่งส่งต่อ ai-engine อีกที
 * ที่นี่ทำแค่ เลือกบริเวณ · ยิง fetch · วาดผลลงบน canvas
 *
 * ห้าม hardcode localhost/IP — อ่าน API base จาก window.LUMA_CONFIG เท่านั้น
 */

(() => {
  const API_BASE = window.LUMA_CONFIG ? window.LUMA_CONFIG.apiBase : "";

  const canvas = document.getElementById("fn-canvas");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");

  const fileInput = document.getElementById("fn-file");
  const resetBtn = document.getElementById("fn-reset");
  const changeImageBtn = document.getElementById("fn-change-image");
  const changeFunctionBtn = document.getElementById("fn-change-function");
  const stepFunction = document.getElementById("fn-step-function");
  const stepImage = document.getElementById("fn-step-image");
  const stepWork = document.getElementById("fn-step-work");
  const chosenName = document.getElementById("fn-chosen-name");
  const workTitle = document.getElementById("fn-work-title");
  const toolBlur = document.getElementById("fn-tool-blur");
  const toolObjects = document.getElementById("fn-tool-objects");

  const FUNCTIONS = {
    blur: { name: "เบลอเฉพาะจุด", work: "ลากกรอบแล้วกดเบลอ", tool: toolBlur },
    objects: { name: "ตีกรอบวัตถุ", work: "ตั้งค่าแล้วกดหาวัตถุ", tool: toolObjects },
  };
  let chosen = null;
  const hint = document.getElementById("fn-hint");
  const errorBox = document.getElementById("fn-error");
  const selectionText = document.getElementById("fn-selection");
  const blurBtn = document.getElementById("fn-blur-btn");
  const objectsBtn = document.getElementById("fn-objects-btn");
  const objectsResult = document.getElementById("fn-objects-result");

  let originalDataUrl = null; // ภาพที่ผู้ใช้เลือกตอนแรก ใช้ตอนกดคืนค่า
  let currentImage = null;    // Image object ที่กำลังแสดงอยู่
  let selection = null;       // กรอบที่ลากเลือก หน่วยเป็น "พิกเซลของภาพ" ไม่ใช่พิกเซลบนจอ
  let boxes = [];             // กรอบวัตถุที่ ai-engine ส่งกลับมา
  let dragStart = null;

  function showError(message) {
    errorBox.textContent = message;
    errorBox.hidden = false;
  }

  function clearError() {
    errorBox.hidden = true;
    errorBox.textContent = "";
  }

  /** วาดใหม่ทั้งหมด: ภาพ -> กรอบวัตถุ -> กรอบที่กำลังลาก */
  function redraw() {
    if (!currentImage) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(currentImage, 0, 0);

    // เส้นต้องหนาตามขนาดภาพ ไม่งั้นภาพใหญ่จะเห็นเป็นเส้นผมบางๆ
    const lineWidth = Math.max(2, Math.round(canvas.width / 400));

    ctx.lineWidth = lineWidth;
    ctx.strokeStyle = "#16a34a";
    boxes.forEach((box) => ctx.strokeRect(box.x, box.y, box.width, box.height));

    if (selection) {
      ctx.strokeStyle = "#6d28d9";
      ctx.setLineDash([lineWidth * 3, lineWidth * 2]);
      ctx.strokeRect(selection.x, selection.y, selection.width, selection.height);
      ctx.setLineDash([]);
    }
  }

  function loadImage(dataUrl) {
    const image = new Image();
    image.onload = () => {
      currentImage = image;
      canvas.width = image.naturalWidth;
      canvas.height = image.naturalHeight;
      selection = null;
      boxes = [];
      selectionText.textContent = "ยังไม่ได้เลือกกรอบ";
      objectsResult.hidden = true;
      hint.textContent = `ภาพขนาด ${image.naturalWidth} x ${image.naturalHeight} — ลากเมาส์บนภาพเพื่อเลือกกรอบ`;
      blurBtn.disabled = true;
      objectsBtn.disabled = chosen !== "objects";
      resetBtn.disabled = false;
      stepWork.hidden = false;
      redraw();
    };
    image.onerror = () => showError("เปิดภาพไม่สำเร็จ ลองไฟล์อื่น");
    image.src = dataUrl;
  }

  /** ไปขั้นที่ 2 — เลือกภาพสำหรับฟังก์ชันที่เพิ่งเลือก */
  function chooseFunction(key) {
    chosen = key;
    clearError();
    chosenName.textContent = FUNCTIONS[key].name;
    workTitle.textContent = FUNCTIONS[key].work;
    Object.values(FUNCTIONS).forEach((f) => { f.tool.hidden = true; });
    FUNCTIONS[key].tool.hidden = false;
    stepFunction.hidden = true;
    stepImage.hidden = false;
    stepWork.hidden = true;
  }

  /** กลับไปขั้นที่ 1 — ล้างทุกอย่างทิ้ง เพราะสองฟังก์ชันไม่ได้ทำงานต่อจากกัน */
  function resetToStart() {
    chosen = null;
    Object.values(FUNCTIONS).forEach((f) => { f.tool.hidden = true; });
    chosenName.textContent = "";
    workTitle.textContent = "";
    originalDataUrl = null;
    currentImage = null;
    selection = null;
    boxes = [];
    fileInput.value = "";
    objectsResult.hidden = true;
    selectionText.textContent = "ยังไม่ได้เลือกกรอบ";
    hint.textContent = "ยังไม่ได้เลือกภาพ";
    blurBtn.disabled = true;
    objectsBtn.disabled = true;
    resetBtn.disabled = true;
    clearError();
    stepFunction.hidden = false;
    stepImage.hidden = true;
    stepWork.hidden = true;
  }

  document.querySelectorAll(".fn-choice").forEach((btn) => {
    btn.addEventListener("click", () => chooseFunction(btn.dataset.function));
  });

  changeFunctionBtn.addEventListener("click", resetToStart);

  changeImageBtn.addEventListener("click", () => {
    // เปลี่ยนภาพแต่ยังอยู่ฟังก์ชันเดิม — ถอยไปขั้นที่ 2 ไม่ต้องเริ่มใหม่ทั้งหมด
    const keep = chosen;
    resetToStart();
    chooseFunction(keep);
  });

  fileInput.addEventListener("change", () => {
    const file = fileInput.files && fileInput.files[0];
    if (!file) return;
    clearError();
    const reader = new FileReader();
    reader.onload = () => {
      originalDataUrl = reader.result;
      loadImage(originalDataUrl);
    };
    reader.onerror = () => showError("อ่านไฟล์ไม่สำเร็จ");
    reader.readAsDataURL(file);
  });

  resetBtn.addEventListener("click", () => {
    if (originalDataUrl) {
      clearError();
      loadImage(originalDataUrl);
    }
  });

  /** แปลงพิกัดเมาส์บนจอ -> พิกัดในภาพจริง
   *  canvas ถูกย่อด้วย CSS (max-width:100%) พิกัดสองระบบจึงไม่เท่ากัน
   *  ถ้าส่งพิกัดบนจอไปตรงๆ กรอบที่เบลอจะเพี้ยนตามขนาดหน้าต่างของแต่ละคน */
  function toImagePoint(event) {
    const rect = canvas.getBoundingClientRect();
    return {
      x: Math.round((event.clientX - rect.left) * (canvas.width / rect.width)),
      y: Math.round((event.clientY - rect.top) * (canvas.height / rect.height)),
    };
  }

  function clamp(value, max) {
    return Math.max(0, Math.min(value, max));
  }

  function updateSelection(event) {
    const point = toImagePoint(event);
    const x1 = clamp(Math.min(dragStart.x, point.x), canvas.width);
    const y1 = clamp(Math.min(dragStart.y, point.y), canvas.height);
    const x2 = clamp(Math.max(dragStart.x, point.x), canvas.width);
    const y2 = clamp(Math.max(dragStart.y, point.y), canvas.height);
    selection = { x: x1, y: y1, width: x2 - x1, height: y2 - y1 };
    redraw();
  }

  canvas.addEventListener("mousedown", (event) => {
    if (!currentImage) return;
    dragStart = toImagePoint(event);
    selection = null;
    redraw();
  });

  canvas.addEventListener("mousemove", (event) => {
    if (dragStart) updateSelection(event);
  });

  canvas.addEventListener("mouseup", (event) => {
    if (!dragStart) return;
    updateSelection(event);
    dragStart = null;
    // กรอบเล็กกว่า 1 พิกเซลคือคลิกเฉยๆ ไม่ใช่การลาก
    if (!selection || selection.width < 1 || selection.height < 1) {
      selection = null;
      selectionText.textContent = "ยังไม่ได้เลือกกรอบ";
      blurBtn.disabled = true;
      redraw();
      return;
    }
    selectionText.textContent =
      `กรอบที่เลือก: ${selection.width} x ${selection.height} ที่ (${selection.x}, ${selection.y})`;
    blurBtn.disabled = false;
  });

  canvas.addEventListener("mouseleave", () => {
    if (dragStart) dragStart = null;
  });

  async function postJson(path, body) {
    const res = await fetch(`${API_BASE}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...window.csrfHeaders() },
      credentials: "include",
      body: JSON.stringify(body),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(data.error || `คำขอไม่สำเร็จ (HTTP ${res.status})`);
    }
    return data;
  }

  blurBtn.addEventListener("click", async () => {
    if (!selection || !currentImage) return;
    clearError();
    blurBtn.disabled = true;
    const label = blurBtn.textContent;
    blurBtn.textContent = "กำลังเบลอ...";
    try {
      const data = await postJson("/api/pipeline/blur-region", {
        image: canvas.toDataURL("image/png"),
        region: selection,
        size: Number(document.getElementById("fn-blur-size").value),
      });
      loadImage(`data:image/png;base64,${data.image}`);
    } catch (err) {
      showError(err.message);
      blurBtn.disabled = false;
    } finally {
      blurBtn.textContent = label;
    }
  });

  objectsBtn.addEventListener("click", async () => {
    if (!currentImage) return;
    clearError();
    objectsBtn.disabled = true;
    const label = objectsBtn.textContent;
    objectsBtn.textContent = "กำลังหาวัตถุ...";
    try {
      const data = await postJson("/api/pipeline/find-objects", {
        image: canvas.toDataURL("image/png"),
        center_degrees: Number(document.getElementById("fn-hue").value),
        tolerance_degrees: Number(document.getElementById("fn-tolerance").value),
        minimum_area: Number(document.getElementById("fn-min-area").value),
      });
      boxes = data.objects || [];
      objectsResult.textContent = boxes.length
        ? `ตีกรอบให้ ${boxes.length} วัตถุ`
        : "ไม่พบวัตถุที่ตรงกับสีที่เลือก ลองเพิ่มค่าองศาที่ยอมให้เพี้ยน";
      objectsResult.hidden = false;
      redraw();
    } catch (err) {
      showError(err.message);
    } finally {
      objectsBtn.disabled = false;
      objectsBtn.textContent = label;
    }
  });
})();
