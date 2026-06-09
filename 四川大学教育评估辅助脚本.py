from __future__ import annotations

import argparse
import getpass
import json
import os
import random
import re
import shutil
import sys
import time
from pathlib import Path

import selenium
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


INDEX_URL = "http://zhjw.scu.edu.cn/student/teachingEvaluation/newEvaluation/index"
EVALUATION_PATH = "/student/teachingEvaluation/newEvaluation/evaluation/"
DEFAULT_WAIT_SECONDS = 101

COMMENTS = [
    "课程内容充实，老师讲解清楚，学习收获较多。",
    "课堂节奏适中，重点突出，整体学习体验很好。",
    "老师教学认真负责，案例丰富，帮助理解课程。",
    "课程安排合理，讲授细致，课堂互动效果较好。",
    "内容实用性强，讲解条理清晰，受益较多。",
    "教学过程认真，知识点清楚，课堂氛围较好。",
    "课程目标明确，讲授深入浅出，整体效果很好。",
    "老师备课充分，讲解耐心，课程收获比较明显。",
]


def find_edge_binary() -> Path | None:
    candidates = [
        shutil.which("msedge"),
        shutil.which("msedge.exe"),
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return Path(candidate)
    return None


def find_driver_near_script() -> Path | None:
    candidates = [
        Path(__file__).with_name("msedgedriver.exe"),
        Path.cwd() / "msedgedriver.exe",
        shutil.which("msedgedriver"),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return Path(candidate)
    return None


def self_check() -> None:
    print(f"Python: {sys.version.split()[0]}")
    print(f"Selenium: {selenium.__version__}")
    print(f"Edge binary: {find_edge_binary() or 'not found'}")
    print(f"msedgedriver: {find_driver_near_script() or 'not found'}")


def make_driver(headless: bool) -> webdriver.Edge:
    profile_dir = Path(__file__).with_name("scu-eval-edge-profile")
    profile_dir.mkdir(parents=True, exist_ok=True)

    options = EdgeOptions()
    edge_binary = find_edge_binary()
    if edge_binary:
        options.binary_location = str(edge_binary)
    options.add_argument(f"--user-data-dir={profile_dir.resolve()}")
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    if headless:
        options.add_argument("--headless=new")
        options.add_argument("--window-size=1400,900")

    driver_path = find_driver_near_script()
    if driver_path:
        return webdriver.Edge(service=EdgeService(str(driver_path)), options=options)
    return webdriver.Edge(options=options)


def wait_body(driver: webdriver.Edge, seconds: int = 20) -> None:
    WebDriverWait(driver, seconds).until(EC.presence_of_element_located((By.TAG_NAME, "body")))


def visible_text(driver: webdriver.Edge) -> str:
    try:
        return driver.find_element(By.TAG_NAME, "body").text
    except Exception:
        return ""


def click_by_text(driver: webdriver.Edge, patterns: list[str], timeout: int = 5) -> bool:
    end = time.time() + timeout
    regexes = [re.compile(pattern) for pattern in patterns]
    while time.time() < end:
        elements = driver.find_elements(By.XPATH, "//*[normalize-space(text()) != '']")
        for element in elements:
            try:
                text = element.text.strip()
                if not text:
                    continue
                if any(regex.search(text) for regex in regexes) and element.is_displayed() and element.is_enabled():
                    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", element)
                    element.click()
                    return True
            except Exception:
                continue
        time.sleep(0.3)
    return False


def set_input_value(driver: webdriver.Edge, element, value: str) -> None:
    driver.execute_script(
        """
        const el = arguments[0];
        const value = arguments[1];
        el.focus();
        el.value = value;
        el.dispatchEvent(new Event('input', { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true }));
        """,
        element,
        value,
    )


def find_input(driver: webdriver.Edge, keywords: list[str], input_type: str | None = None):
    script = """
    const keywords = arguments[0].map(s => s.toLowerCase());
    const wantedType = arguments[1];
    const isVisible = el => {
      const box = el.getBoundingClientRect();
      const style = window.getComputedStyle(el);
      return box.width > 0 && box.height > 0 && style.visibility !== 'hidden' && style.display !== 'none';
    };
    const inputs = Array.from(document.querySelectorAll('input')).filter(el => isVisible(el) && !el.disabled && !el.readOnly);
    for (const input of inputs) {
      const type = (input.type || '').toLowerCase();
      if (wantedType && type !== wantedType) continue;
      const text = [
        input.name,
        input.id,
        input.placeholder,
        input.getAttribute('aria-label'),
        input.getAttribute('autocomplete'),
        input.className,
      ].filter(Boolean).join(' ').toLowerCase();
      if (keywords.some(k => text.includes(k))) return input;
    }
    if (wantedType) return inputs.find(i => (i.type || '').toLowerCase() === wantedType) || null;
    return inputs.find(i => ['text', 'tel', 'number', ''].includes((i.type || '').toLowerCase())) || null;
    """
    return driver.execute_script(script, keywords, input_type)


def fill_login_fields(driver: webdriver.Edge, student_id: str, password: str) -> None:
    user_input = find_input(driver, ["user", "account", "username", "login", "学号", "工号", "账号", "手机号"])
    pass_input = find_input(driver, ["password", "pwd", "密码"], "password")
    if user_input:
        set_input_value(driver, user_input, student_id)
    else:
        print("没有自动找到账号输入框，请手动填写。")
    if pass_input:
        set_input_value(driver, pass_input, password)
    else:
        print("没有自动找到密码输入框，请手动填写。")


def looks_like_login_page(driver: webdriver.Edge) -> bool:
    text = visible_text(driver)
    return any(word in text for word in ["欢迎登录", "统一身份登录", "账号登录", "短信验证"])


def login_flow(driver: webdriver.Edge, student_id: str, password: str) -> None:
    wait_body(driver)
    if INDEX_URL in driver.current_url and "登录" not in visible_text(driver):
        return

    print("尝试进入统一身份登录...")
    click_by_text(driver, [r"统一身份登录", r"统一认证", r"统一身份认证"], timeout=8)
    time.sleep(1)

    print("尝试切换到账号登录...")
    click_by_text(driver, [r"账号登录", r"账号密码登录", r"密码登录"], timeout=8)
    time.sleep(1)

    print("填写账号和密码...")
    fill_login_fields(driver, student_id, password)

    print("请在浏览器里手动填写图片验证码。填好后回到这里按 Enter，脚本会点击登录。")
    input()
    click_by_text(driver, [r"^登录$", r"^登\s*录$", r"登录"], timeout=8)
    time.sleep(2)

    body = visible_text(driver)
    if "获取验证码" in body or "短信" in body or "验证码" in body:
        print("尝试点击获取短信验证码...")
        click_by_text(driver, [r"获取验证码", r"发送验证码", r"获取动态码"], timeout=10)
        print("请在浏览器里输入收到的短信验证码。填好后回到这里按 Enter，脚本会继续。")
        input()
        click_by_text(driver, [r"^登录$", r"^确定$", r"^确认$", r"^提交$", r"^下一步$"], timeout=10)

    print("等待进入教学评估列表页...")
    end = time.time() + 180
    while time.time() < end:
        if "teachingEvaluation/newEvaluation/index" in driver.current_url:
            return
        time.sleep(1)
    print("没有检测到自动跳转到评估列表页。如果页面已经登录成功，也可以继续手动进入评估列表。")


def wait_for_evaluation_page(driver: webdriver.Edge) -> None:
    print("请在浏览器里选择评估对象并打开对应评估页面。脚本会自动检测并填表。")
    end = time.time() + 900
    while time.time() < end:
        for handle in driver.window_handles:
            try:
                driver.switch_to.window(handle)
                if EVALUATION_PATH in driver.current_url:
                    wait_body(driver)
                    time.sleep(1)
                    return
            except Exception:
                continue
        time.sleep(1)
    raise TimeoutException("长时间没有检测到具体评估页面。")


def click_select_all_a(driver: webdriver.Edge) -> bool:
    return click_by_text(driver, [r"^全选\s*\(?A\)?$", r"^A$", r"^优秀$", r"^非常满意$"], timeout=3)


def choose_a_for_radio_groups(driver: webdriver.Edge) -> int:
    return int(
        driver.execute_script(
            """
            const fire = el => {
              el.dispatchEvent(new Event('input', { bubbles: true }));
              el.dispatchEvent(new Event('change', { bubbles: true }));
              el.dispatchEvent(new MouseEvent('click', { bubbles: true }));
            };
            const isVisible = el => {
              const box = el.getBoundingClientRect();
              const style = window.getComputedStyle(el);
              return box.width > 0 && box.height > 0 && style.visibility !== 'hidden' && style.display !== 'none';
            };
            const textFor = input => {
              const label = input.id ? document.querySelector(`label[for="${CSS.escape(input.id)}"]`) : null;
              const wrapped = input.closest('label');
              const nearby = input.closest('td, th, li, div, tr, fieldset');
              return [
                input.value, input.id, input.name, input.title, input.getAttribute('aria-label'),
                label ? label.innerText : '', wrapped ? wrapped.innerText : '',
                nearby ? nearby.innerText.slice(0, 120) : '',
              ].filter(Boolean).join(' ');
            };

            const radios = Array.from(document.querySelectorAll("input[type='radio']")).filter(r => !r.disabled);
            const groups = new Map();
            for (const radio of radios) {
              const key = radio.name || radio.getAttribute("data-name") || Math.random().toString();
              if (!groups.has(key)) groups.set(key, []);
              groups.get(key).push(radio);
            }

            let changed = 0;
            for (const items of groups.values()) {
              let target = items.find(item => /(^|[^A-Za-z])A([^A-Za-z]|$)|优秀|非常满意/.test(textFor(item)));
              if (!target) target = items[0];
              if (target && !target.disabled) {
                target.checked = true;
                try { target.click(); } catch (_) {}
                fire(target);
                changed += 1;
              }
            }

            const containers = Array.from(document.querySelectorAll('tr, fieldset, .question, .form-group, .el-form-item, .ant-form-item'))
              .filter(isVisible)
              .filter(el => /A|优秀|非常满意/.test(el.innerText || ''));
            for (const container of containers) {
              const candidates = Array.from(container.querySelectorAll('label, span, button, a, div'))
                .filter(isVisible)
                .filter(el => /^\\s*(A\\b|A[.、．]|优秀|非常满意)/.test(el.innerText || ''));
              if (candidates.length) {
                try {
                  candidates[0].click();
                  changed += 1;
                } catch (_) {}
              }
            }
            return changed;
            """
        )
    )


def fill_score_inputs(driver: webdriver.Edge, min_score: int, max_score: int) -> int:
    return int(
        driver.execute_script(
            """
            const minScore = arguments[0];
            const maxScore = arguments[1];
            const randomScore = () => String(Math.floor(Math.random() * (maxScore - minScore + 1)) + minScore);
            const isVisible = el => {
              const box = el.getBoundingClientRect();
              const style = window.getComputedStyle(el);
              return box.width > 0 && box.height > 0 && style.visibility !== 'hidden' && style.display !== 'none';
            };
            const inputs = Array.from(document.querySelectorAll("input"))
              .filter(input => isVisible(input) && !input.disabled && !input.readOnly)
              .filter(input => {
                const type = (input.type || '').toLowerCase();
                if (!['text', 'number', 'tel', ''].includes(type)) return false;
                const text = `${input.name || ''} ${input.id || ''} ${input.placeholder || ''} ${input.className || ''}`;
                const maxLength = input.maxLength || 0;
                const looksNumericBox = maxLength > 0 && maxLength <= 5;
                const hasScoreHint = /score|grade|mark|point|分|成绩|评分|总评|得分/.test(text);
                return hasScoreHint || looksNumericBox;
              });

            let count = 0;
            for (const input of inputs) {
              input.focus();
              input.value = randomScore();
              input.dispatchEvent(new Event('input', { bubbles: true }));
              input.dispatchEvent(new Event('change', { bubbles: true }));
              count += 1;
            }
            return count;
            """,
            min_score,
            max_score,
        )
    )


def choose_random_checkboxes(driver: webdriver.Edge) -> int:
    return int(
        driver.execute_script(
            """
            const fire = el => {
              el.dispatchEvent(new Event('input', { bubbles: true }));
              el.dispatchEvent(new Event('change', { bubbles: true }));
              el.dispatchEvent(new MouseEvent('click', { bubbles: true }));
            };
            const boxes = Array.from(document.querySelectorAll("input[type='checkbox']")).filter(box => !box.disabled);
            const groups = new Map();
            for (const box of boxes) {
              const container = box.closest('tr, .question, .form-group, li, div');
              const key = box.name || (container ? container.textContent.slice(0, 40) : 'default');
              if (!groups.has(key)) groups.set(key, []);
              groups.get(key).push(box);
            }

            let changed = 0;
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
              const pickCount = Math.floor(Math.random() * (maxPick - minPick + 1)) + minPick;
              const shuffled = items.slice().sort(() => Math.random() - 0.5);
              for (const item of shuffled.slice(0, pickCount)) {
                item.checked = true;
                try { item.click(); } catch (_) {}
                fire(item);
                changed += 1;
              }
            }
            return changed;
            """
        )
    )


def fill_comment(driver: webdriver.Edge, comment: str) -> int:
    return int(
        driver.execute_script(
            """
            const comment = arguments[0];
            const isVisible = el => {
              const box = el.getBoundingClientRect();
              const style = window.getComputedStyle(el);
              return box.width > 0 && box.height > 0 && style.visibility !== 'hidden' && style.display !== 'none';
            };
            const areas = Array.from(document.querySelectorAll("textarea"))
              .filter(area => isVisible(area) && !area.disabled && !area.readOnly);
            const textInputs = Array.from(document.querySelectorAll("input[type='text']:not([readonly])"))
              .filter(input => isVisible(input) && !input.disabled)
              .filter(input => /意见|建议|评价|评语|comment|suggest/i.test(`${input.name || ''} ${input.id || ''} ${input.placeholder || ''}`));
            const targets = areas.length ? areas : textInputs;
            let count = 0;
            for (const target of targets) {
              target.focus();
              target.value = comment;
              target.dispatchEvent(new Event('input', { bubbles: true }));
              target.dispatchEvent(new Event('change', { bubbles: true }));
              count += 1;
            }
            return count;
            """,
            comment,
        )
    )


def find_and_click_save(driver: webdriver.Edge) -> bool:
    if click_by_text(driver, [r"^保存$", r"^保存评价$", r"^暂存$", r"^保存并退出$"], timeout=5):
        return True
    for selector in [".save", "#save", "button[name*='save']", "input[name*='save']"]:
        try:
            element = driver.find_element(By.CSS_SELECTOR, selector)
            if element.is_displayed() and element.is_enabled():
                driver.execute_script("arguments[0].scrollIntoView({block:'center'});", element)
                element.click()
                return True
        except Exception:
            continue
    return False


def diagnose_score_fields(driver: webdriver.Edge) -> list[dict[str, object]]:
    return driver.execute_script(
        """
        const visible = el => {
          const box = el.getBoundingClientRect();
          const style = window.getComputedStyle(el);
          return box.width > 0 && box.height > 0 && style.display !== 'none' && style.visibility !== 'hidden';
        };
        return Array.from(document.querySelectorAll("input, textarea, select, [contenteditable='true']"))
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
              aroundText: around ? around.innerText.slice(0, 220) : "",
            };
          })
          .filter(item => /分|评分|得分|score|grade|mark|point|评价/.test(JSON.stringify(item)))
          .slice(0, 80);
        """
    )


def wait_with_countdown(seconds: int) -> None:
    for remaining in range(seconds, 0, -1):
        if remaining % 10 == 0 or remaining <= 5:
            print(f"保存等待倒计时：{remaining}s")
        time.sleep(1)


def fill_current_page(driver: webdriver.Edge, min_score: int, max_score: int, wait_seconds: int, save: bool) -> None:
    wait_body(driver)
    time.sleep(1)
    clicked_all_a = click_select_all_a(driver)
    radio_count = choose_a_for_radio_groups(driver)
    score_count = fill_score_inputs(driver, min_score, max_score)
    checkbox_count = choose_random_checkboxes(driver)
    comment = random.choice(COMMENTS)
    comment_count = fill_comment(driver, comment)

    print(f"Clicked select-all A: {clicked_all_a}")
    print(f"Radio groups filled: {radio_count}")
    print(f"Score inputs filled: {score_count}")
    print(f"Checkbox options selected: {checkbox_count}")
    print(f"Comment: {comment}")
    print(f"Comment fields filled: {comment_count}")

    if not save:
        print("已自动填充。请检查页面；当前不会自动保存。")
        return

    wait_with_countdown(wait_seconds)
    if find_and_click_save(driver):
        print("已点击保存按钮。如有浏览器确认框，请在页面中处理。")
    else:
        print("没有找到保存按钮，请检查后手动保存。")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=INDEX_URL)
    parser.add_argument("--student-id", default=os.getenv("SCU_STUDENT_ID"))
    parser.add_argument("--password", default=os.getenv("SCU_PASSWORD"))
    parser.add_argument("--min-score", type=int, default=95)
    parser.add_argument("--max-score", type=int, default=98)
    parser.add_argument("--wait", type=int, default=DEFAULT_WAIT_SECONDS)
    parser.add_argument("--save", action="store_true")
    parser.add_argument("--submit", action="store_true", help="兼容旧参数：现在等同于 --save。")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--skip-login", action="store_true")
    parser.add_argument("--manual-fill", action="store_true")
    parser.add_argument("--diagnose-score", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    if args.check:
        self_check()
        return

    print("Starting Edge through Selenium...", flush=True)
    try:
        driver = make_driver(args.headless)
    except WebDriverException as exc:
        print("无法启动 Edge。请确认 msedgedriver.exe 与脚本在同一目录，或已加入 PATH。")
        print(f"错误：{exc}")
        sys.exit(1)

    try:
        driver.get(args.url)
        wait_body(driver)

        if not args.skip_login and looks_like_login_page(driver):
            student_id = args.student_id or input("学工号：").strip()
            password = args.password or getpass.getpass("密码：")
            login_flow(driver, student_id, password)

        if args.manual_fill:
            input("评估表单可见后按 Enter 开始填充：")
        else:
            wait_for_evaluation_page(driver)

        if args.diagnose_score:
            print(json.dumps(diagnose_score_fields(driver), ensure_ascii=False, indent=2))

        fill_current_page(driver, args.min_score, args.max_score, args.wait, args.save or args.submit)
        input("按 Enter 关闭浏览器：")
    except TimeoutException as exc:
        print(f"等待页面超时：{exc}")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
