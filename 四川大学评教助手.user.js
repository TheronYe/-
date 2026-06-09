// ==UserScript==
// @name         四川大学评教助手
// @namespace    local.scu.teaching-evaluation-helper
// @version      0.1.0
// @description  辅助四川大学教务系统教学评估页面填充；不识别验证码，不保存账号密码。
// @license      MIT
// @match        http://zhjw.scu.edu.cn/*
// @match        https://zhjw.scu.edu.cn/*
// @match        http://*.scu.edu.cn/*
// @match        https://*.scu.edu.cn/*
// @run-at       document-idle
// @grant        none
// ==/UserScript==

(function () {
  "use strict";

  const INDEX_PATH = "/student/teachingEvaluation/newEvaluation/index";
  const EVALUATION_PATH = "/student/teachingEvaluation/newEvaluation/evaluation/";
  const SCORE_MIN = 95;
  const SCORE_MAX = 98;
  const SAVE_WAIT_SECONDS = 101;

  const COMMENTS = [
    "课程内容充实，老师讲解清楚，学习收获较多。",
    "课堂节奏适中，重点突出，整体学习体验很好。",
    "老师教学认真负责，案例丰富，帮助理解课程。",
    "课程安排合理，讲授细致，课堂互动效果较好。",
    "内容实用性强，讲解条理清晰，受益较多。",
    "教学过程认真，知识点清楚，课堂氛围较好。",
    "课程目标明确，讲授深入浅出，整体效果很好。",
    "老师备课充分，讲解耐心，课程收获比较明显。"
  ];

  const state = {
    filled: false,
    countdownTimer: null
  };

  function $(selector, root = document) {
    return root.querySelector(selector);
  }

  function $$(selector, root = document) {
    return Array.from(root.querySelectorAll(selector));
  }

  function visible(el) {
    if (!el) return false;
    const box = el.getBoundingClientRect();
    const style = getComputedStyle(el);
    return box.width > 0 && box.height > 0 && style.display !== "none" && style.visibility !== "hidden";
  }

  function fire(el) {
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
    el.dispatchEvent(new MouseEvent("click", { bubbles: true }));
  }

  function randomInt(min, max) {
    return Math.floor(Math.random() * (max - min + 1)) + min;
  }

  function shuffle(items) {
    return items.slice().sort(() => Math.random() - 0.5);
  }

  function pageText() {
    return document.body ? document.body.innerText : "";
  }

  function clickText(patterns) {
    const regexes = patterns.map((pattern) => pattern instanceof RegExp ? pattern : new RegExp(pattern));
    const elements = $$("button, a, span, div, label, input[type='button'], input[type='submit']");
    for (const el of elements) {
      const text = (el.innerText || el.value || "").trim();
      if (!text || !visible(el)) continue;
      if (regexes.some((regex) => regex.test(text))) {
        el.scrollIntoView({ block: "center" });
        el.click();
        return true;
      }
    }
    return false;
  }

  function installPanel() {
    if ($("#scu-eval-helper-panel")) return;

    const style = document.createElement("style");
    style.textContent = `
      #scu-eval-helper-panel {
        position: fixed;
        right: 18px;
        bottom: 22px;
        z-index: 2147483647;
        width: 210px;
        font: 14px/1.45 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        color: #1f2937;
        background: #ffffff;
        border: 1px solid #d1d5db;
        box-shadow: 0 8px 24px rgba(15, 23, 42, 0.18);
        border-radius: 8px;
        padding: 10px;
      }
      #scu-eval-helper-panel strong {
        display: block;
        margin-bottom: 7px;
        font-size: 14px;
      }
      #scu-eval-helper-panel button {
        width: 100%;
        margin-top: 6px;
        padding: 7px 8px;
        border: 1px solid #2563eb;
        border-radius: 6px;
        background: #2563eb;
        color: #fff;
        cursor: pointer;
      }
      #scu-eval-helper-panel button.secondary {
        border-color: #9ca3af;
        background: #f3f4f6;
        color: #111827;
      }
      #scu-eval-helper-status {
        margin-top: 8px;
        font-size: 12px;
        color: #4b5563;
        word-break: break-word;
      }
    `;
    document.head.appendChild(style);

    const panel = document.createElement("div");
    panel.id = "scu-eval-helper-panel";
    panel.innerHTML = `
      <strong>四川大学评教助手</strong>
      <button id="scu-eval-fill">自动填充</button>
      <button id="scu-eval-save" class="secondary">等待101秒并保存</button>
      <button id="scu-eval-diagnose" class="secondary">诊断分数</button>
      <div id="scu-eval-helper-status">已加载</div>
    `;
    document.body.appendChild(panel);

    $("#scu-eval-fill").addEventListener("click", () => fillEvaluation(true));
    $("#scu-eval-save").addEventListener("click", () => waitAndSave());
    $("#scu-eval-diagnose").addEventListener("click", () => diagnoseScores());
  }

  function setStatus(message) {
    const status = $("#scu-eval-helper-status");
    if (status) status.textContent = message;
  }

  function clickSelectAllA() {
    return clickText([/^全选\s*\(?A\)?$/, /^A$/, /^优秀$/, /^非常满意$/]);
  }

  function textForInput(input) {
    const label = input.id ? document.querySelector(`label[for="${CSS.escape(input.id)}"]`) : null;
    const wrapped = input.closest("label");
    const nearby = input.closest("td, th, li, div, tr, fieldset");
    return [
      input.value,
      input.id,
      input.name,
      input.title,
      input.getAttribute("aria-label"),
      label ? label.innerText : "",
      wrapped ? wrapped.innerText : "",
      nearby ? nearby.innerText.slice(0, 140) : ""
    ].filter(Boolean).join(" ");
  }

  function chooseRadiosA() {
    const radios = $$("input[type='radio']").filter((radio) => !radio.disabled);
    const groups = new Map();
    for (const radio of radios) {
      const key = radio.name || radio.getAttribute("data-name") || Math.random().toString();
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(radio);
    }

    let count = 0;
    for (const items of groups.values()) {
      let target = items.find((item) => /(^|[^A-Za-z])A([^A-Za-z]|$)|优秀|非常满意/.test(textForInput(item)));
      if (!target) target = items[0];
      if (!target || target.disabled) continue;
      target.checked = true;
      try { target.click(); } catch (_) {}
      fire(target);
      count += 1;
    }

    const containers = $$("tr, fieldset, .question, .form-group, .el-form-item, .ant-form-item")
      .filter(visible)
      .filter((el) => /A|优秀|非常满意/.test(el.innerText || ""));
    for (const container of containers) {
      const candidates = $$("label, span, button, a, div", container)
        .filter(visible)
        .filter((el) => /^\s*(A\b|A[.、．]|优秀|非常满意)/.test(el.innerText || ""));
      if (candidates.length) {
        try {
          candidates[0].click();
          count += 1;
        } catch (_) {}
      }
    }

    return count;
  }

  function fillScores() {
    const inputs = $$("input")
      .filter((input) => visible(input) && !input.disabled && !input.readOnly)
      .filter((input) => {
        const type = (input.type || "").toLowerCase();
        if (!["text", "number", "tel", ""].includes(type)) return false;
        const text = `${input.name || ""} ${input.id || ""} ${input.placeholder || ""} ${input.className || ""}`;
        const maxLength = input.maxLength || 0;
        const looksNumericBox = maxLength > 0 && maxLength <= 5;
        const hasScoreHint = /score|grade|mark|point|分|成绩|评分|总评|得分/.test(text);
        return hasScoreHint || looksNumericBox;
      });

    let count = 0;
    for (const input of inputs) {
      input.focus();
      input.value = String(randomInt(SCORE_MIN, SCORE_MAX));
      fire(input);
      count += 1;
    }

    const editables = $$("[contenteditable='true']")
      .filter(visible)
      .filter((el) => /分|评分|得分/.test((el.closest("tr, div, fieldset") || el).innerText || ""));
    for (const el of editables) {
      el.textContent = String(randomInt(SCORE_MIN, SCORE_MAX));
      fire(el);
      count += 1;
    }

    return count;
  }

  function chooseCheckboxes() {
    const boxes = $$("input[type='checkbox']").filter((box) => !box.disabled);
    const groups = new Map();
    for (const box of boxes) {
      const container = box.closest("tr, .question, .form-group, li, div");
      const key = box.name || (container ? container.textContent.slice(0, 40) : "default");
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(box);
    }

    let count = 0;
    for (const items of groups.values()) {
      for (const item of items) {
        if (item.checked) {
          item.checked = false;
          try { item.click(); } catch (_) {}
          fire(item);
        }
      }

      const minPick = items.length >= 2 ? 2 : 1;
      const maxPick = Math.min(items.length, 4);
      const pickCount = randomInt(minPick, maxPick);
      for (const item of shuffle(items).slice(0, pickCount)) {
        item.checked = true;
        try { item.click(); } catch (_) {}
        fire(item);
        count += 1;
      }
    }

    count += clickCustomMultiChoice();
    return count;
  }

  function clickCustomMultiChoice() {
    const candidates = $$("tr, fieldset, .question, .form-group, .el-form-item, .ant-form-item")
      .filter(visible)
      .filter((el) => /多选|第\s*6\s*题|六/.test(el.innerText || ""));

    let count = 0;
    for (const container of candidates) {
      const options = $$("label, span, button, a, div", container)
        .filter(visible)
        .filter((el) => {
          const text = (el.innerText || "").trim();
          return /^[A-Z][.、．\s]|^[A-Z]$|^选项/.test(text) && text.length <= 30;
        });
      const pickCount = Math.min(Math.max(2, randomInt(2, 4)), options.length);
      for (const option of shuffle(options).slice(0, pickCount)) {
        try {
          option.click();
          count += 1;
        } catch (_) {}
      }
    }
    return count;
  }

  function fillComment() {
    const comment = COMMENTS[randomInt(0, COMMENTS.length - 1)];
    const areas = $$("textarea").filter((area) => visible(area) && !area.disabled && !area.readOnly);
    const textInputs = $$("input[type='text']:not([readonly])")
      .filter((input) => visible(input) && !input.disabled)
      .filter((input) => /意见|建议|评价|评语|comment|suggest/i.test(`${input.name || ""} ${input.id || ""} ${input.placeholder || ""}`));
    const targets = areas.length ? areas : textInputs;

    let count = 0;
    for (const target of targets) {
      target.focus();
      target.value = comment;
      fire(target);
      count += 1;
    }
    return { count, comment };
  }

  function fillEvaluation(force = false) {
    if (!location.href.includes(EVALUATION_PATH)) return;
    if (state.filled && !force) return;

    installPanel();
    const selectedAll = clickSelectAllA();
    const radioCount = chooseRadiosA();
    const scoreCount = fillScores();
    const checkboxCount = chooseCheckboxes();
    const commentResult = fillComment();

    state.filled = true;
    setStatus(`已填充：单选 ${radioCount}，分数 ${scoreCount}，多选 ${checkboxCount}，评语 ${commentResult.count}`);
    console.log("[SCU Eval Helper]", {
      selectedAll,
      radioCount,
      scoreCount,
      checkboxCount,
      comment: commentResult.comment,
      commentCount: commentResult.count
    });
  }

  function findSaveButton() {
    const textPatterns = [/^保存$/, /^保存评价$/, /^暂存$/, /^保存并退出$/];
    const elements = $$("button, a, input[type='button'], input[type='submit']");
    for (const el of elements) {
      const text = (el.innerText || el.value || "").trim();
      if (visible(el) && textPatterns.some((pattern) => pattern.test(text))) return el;
    }
    return $(".save, #save, button[name*='save'], input[name*='save']");
  }

  function waitAndSave() {
    if (!location.href.includes(EVALUATION_PATH)) return;
    if (!state.filled) fillEvaluation(false);
    if (state.countdownTimer) clearInterval(state.countdownTimer);

    let remaining = SAVE_WAIT_SECONDS;
    setStatus(`等待 ${remaining} 秒后自动保存`);
    state.countdownTimer = setInterval(() => {
      remaining -= 1;
      setStatus(`等待 ${remaining} 秒后自动保存`);
      if (remaining > 0) return;

      clearInterval(state.countdownTimer);
      state.countdownTimer = null;

      const button = findSaveButton();
      if (button) {
        button.scrollIntoView({ block: "center" });
        button.click();
        setStatus("已点击保存按钮");
      } else {
        setStatus("没有找到保存按钮，请手动保存");
      }
    }, 1000);
  }

  function diagnoseScores() {
    const fields = $$("input, textarea, select, [contenteditable='true']")
      .map((el, index) => {
        const around = el.closest("tr, fieldset, .question, .form-group, .el-form-item, .ant-form-item, div");
        return {
          index,
          tag: el.tagName,
          type: el.getAttribute("type") || "",
          name: el.getAttribute("name") || "",
          id: el.id || "",
          className: String(el.className || ""),
          placeholder: el.getAttribute("placeholder") || "",
          value: el.value || el.textContent || "",
          maxLength: el.maxLength || "",
          disabled: Boolean(el.disabled),
          readOnly: Boolean(el.readOnly),
          visible: visible(el),
          aroundText: around ? around.innerText.slice(0, 220) : ""
        };
      })
      .filter((item) => /分|评分|得分|score|grade|mark|point|评价/.test(JSON.stringify(item)))
      .slice(0, 80);

    const text = JSON.stringify(fields, null, 2);
    console.log("[SCU Eval Helper score diagnostics]", fields);
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text)
        .then(() => setStatus("分数字段诊断已复制，可发给我"))
        .catch(() => setStatus("诊断已输出到控制台"));
    } else {
      setStatus("诊断已输出到控制台");
    }
  }

  function loginAssist() {
    const text = pageText();
    if (/统一身份登录|统一身份认证/.test(text)) {
      setTimeout(() => clickText([/统一身份登录/, /统一身份认证/]), 600);
    }
    if (/账号登录|账号密码登录|密码登录/.test(text)) {
      setTimeout(() => clickText([/账号登录/, /账号密码登录/, /密码登录/]), 600);
    }
  }

  function boot() {
    if (!document.body) return;

    if (location.href.includes(EVALUATION_PATH)) {
      installPanel();
      setTimeout(() => fillEvaluation(false), 1200);
      return;
    }

    if (location.href.includes(INDEX_PATH)) {
      installPanel();
      setStatus("请选择评估对象，进入评估页后会自动填充");
      return;
    }

    loginAssist();
  }

  boot();
})();
