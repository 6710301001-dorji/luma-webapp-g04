/**
 * LUMA — Generate Image Logic
 * -------------------------------------------------------------------------
 * จัดการฟอร์มสร้างภาพจาก Prompt ส่งคำขอไปยัง POST /api/generate (เข้าคิว #21)
 * แล้วถามสถานะที่ GET /api/jobs/<id> จนเสร็จ จึงแสดงผลลัพธ์ภาพบนหน้าเว็บ
 *
 * อ้างอิง: Issue #57, docs/API_CONTRACT.md
 */

(() => {
  const API_BASE = window.LUMA_CONFIG ? window.LUMA_CONFIG.apiBase : "";
  const POLL_MS = 1500;
  // เกินนี้แล้วยังไม่เสร็จ -> บอกผู้ใช้ งานยังอยู่ในคิว ภาพจะขึ้นในคลังผลงานเมื่อเสร็จ
  const MAX_WAIT_MS = 10 * 60 * 1000;
  const STATUS_TEXT = {
    pending: "อยู่ในคิว รอคิวก่อนหน้าเสร็จ…",
    running: "AI กำลังสร้างภาพ…",
  };

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
    const metaInfo = document.getElementById("meta-info");

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
            ...window.csrfHeaders(),
          },
          body: JSON.stringify(payload),
        });

        const queued = await res.json().catch(() => ({}));

        if (!res.ok || !queued.job_id) {
          throw new Error(queued.error || `สร้างภาพไม่สำเร็จ (HTTP ${res.status})`);
        }

        const data = await waitForJob(queued.job_id);

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
        if (metaInfo) metaInfo.textContent = describeSettings(payload, data.seed_used);
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

    /** บรรทัดรายละเอียดแบบเดียวกับ Forge WebUI (#174)
     *
     *  seed สำคัญที่สุดในบรรทัดนี้ — ส่ง seed: -1 (สุ่ม) แล้วได้ภาพที่ชอบ ถ้าไม่รู้ว่า
     *  Forge ใช้เลขอะไร ก็สร้างภาพเดิมซ้ำไม่ได้เลย (API_CONTRACT.md เขียนข้อนี้ไว้เอง)
     *
     *  ค่าอื่นเอาจาก payload ที่หน้านี้ส่งไป ส่วน seed เอาจาก seed_used ที่ backend
     *  ตอบกลับมา เพราะเลขที่ส่งไปคือ -1 ไม่ใช่เลขที่ Forge ใช้จริง
     *
     *  jobs.seed_used เป็น nullable — ถ้า Forge ไม่แจ้งกลับมา ต้องบอกผู้ใช้ว่าไม่ทราบ
     *  ไม่ใช่โชว์ "undefined" หรือ "-1" ให้เข้าใจผิดว่านี่คือ seed ที่เอาไปใช้ซ้ำได้
     */
    function describeSettings(settings, seedUsed) {
      const seedText = (seedUsed === null || seedUsed === undefined || seedUsed < 0)
        ? "ไม่ทราบ (Forge ไม่ได้แจ้งกลับมา)"
        : String(seedUsed);
      return [
        `Steps: ${settings.steps}`,
        `Sampler: ${settings.sampler_name}`,
        `CFG scale: ${settings.cfg_scale}`,
        `Seed: ${seedText}`,
        `Size: ${settings.width}x${settings.height}`,
      ].join(", ");
    }

    // ถามสถานะงานจนเสร็จ — done คืนข้อมูลงาน, failed โยน error ที่ backend บอกเหตุผลไว้
    async function waitForJob(jobId) {
      const started = Date.now();
      for (;;) {
        const res = await fetch(`${API_BASE}/api/jobs/${jobId}`);
        const job = await res.json().catch(() => ({}));
        if (!res.ok) {
          throw new Error(job.error || `ตรวจสถานะงานไม่สำเร็จ (HTTP ${res.status})`);
        }
        if (job.status === "done") return job;
        if (job.status === "failed") {
          throw new Error(job.error || "สร้างภาพไม่สำเร็จ");
        }
        setStatus(STATUS_TEXT[job.status] || "กำลังประมวลผล…");
        if (Date.now() - started > MAX_WAIT_MS) {
          throw new Error("รอนานเกินไป งานยังอยู่ในคิว — ภาพจะขึ้นในคลังผลงานเมื่อสร้างเสร็จ");
        }
        await new Promise((resolve) => setTimeout(resolve, POLL_MS));
      }
    }

    function setStatus(text) {
      if (spinner) spinner.textContent = text;
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
          spinner.textContent = "กำลังส่งงานเข้าคิว…";
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
