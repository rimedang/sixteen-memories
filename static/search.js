// 입력 화면: 16살 때 살던 동네 자동완성
// - "인천", "부평", "인천 ㅂ", "ㄴㅇ"처럼 일부만 입력해도 지원 지역 중 맞는 곳을 추천한다.
// - 한글을 입력하는 중(예: "부펴")에도 추천이 끊기지 않도록 마지막 글자는 초성·중성까지만 비교한다.
// - 목록에 없는 동네는 그대로 제출할 수 있다. → 결과 화면에서 "준비 중" 안내와 전국 유행을 보여준다.
// 보안: 추천 목록은 textContent로만 만든다.

const input = document.getElementById("region");
const list = document.getElementById("region-suggestions");
const regions = JSON.parse(document.getElementById("region-data").textContent);

const CHOSEONG = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ";
const HANGUL_START = 0xac00;
const HANGUL_COUNT = 11172;

// 완성형 한글 한 글자를 [초성 번호, 중성 번호, 종성 번호]로 나눈다. 한글이 아니면 null.
function splitHangul(char) {
  const code = char.charCodeAt(0) - HANGUL_START;
  if (code < 0 || code >= HANGUL_COUNT) return null;
  return [Math.floor(code / 588), Math.floor((code % 588) / 28), code % 28];
}

// 입력 중인 마지막 글자(typed)가 지역 이름의 글자(target)와 맞는지 본다.
// "ㅂ" → 부, "펴" → 평 처럼 아직 다 치지 않은 글자도 맞는 것으로 본다.
function sameLetterSoFar(typed, target) {
  if (typed === target) return true;
  const targetParts = splitHangul(target);
  if (!targetParts) return false;
  const jamoIndex = CHOSEONG.indexOf(typed);
  if (jamoIndex >= 0) return jamoIndex === targetParts[0];
  const typedParts = splitHangul(typed);
  return (
    typedParts !== null &&
    typedParts[2] === 0 && // 받침 없이 입력 중인 글자만
    typedParts[0] === targetParts[0] &&
    typedParts[1] === targetParts[1]
  );
}

// 단어 하나가 이름 안 어딘가에 들어 있는지 (마지막 글자는 입력 중일 수 있음)
function containsWord(name, word) {
  const head = word.slice(0, -1);
  const last = word.slice(-1);
  for (let i = 0; i + word.length <= name.length; i++) {
    if (name.startsWith(head, i) && sameLetterSoFar(last, name[i + head.length])) {
      return true;
    }
  }
  return false;
}

// "노원구" → "ㄴㅇㄱ" (초성만으로도 찾을 수 있게)
function toChoseong(text) {
  return [...text].map((char) => {
    const parts = splitHangul(char);
    return parts ? CHOSEONG[parts[0]] : char;
  }).join("");
}

const ONLY_JAMO = /^[ㄱ-ㅎ]+$/;

function matches(region, query) {
  const name = (region.sido + region.gu).replace(/\s/g, "");
  const words = query.trim().split(/\s+/).filter(Boolean);
  return words.every((word) =>
    ONLY_JAMO.test(word) ? toChoseong(name).includes(word) : containsWord(name, word)
  );
}

// 구 이름이 입력과 같은 글자로 시작하는 곳을 위로 (예: "서구" → 서구가 강서구보다 먼저)
function startsWithGu(region, query) {
  const last = query.trim().split(/\s+/).pop() || "";
  return last && region.gu.startsWith(last) ? 0 : 1;
}

let activeIndex = -1;
let shown = [];

function setOpen(open) {
  list.hidden = !open;
  input.setAttribute("aria-expanded", String(open));
  if (!open) {
    activeIndex = -1;
    input.removeAttribute("aria-activedescendant");
  }
}

function render() {
  const query = input.value;
  shown = regions
    .filter((region) => matches(region, query))
    .sort((a, b) => startsWithGu(a, query) - startsWithGu(b, query));
  list.replaceChildren();

  for (const [index, region] of shown.entries()) {
    const item = document.createElement("li");
    item.id = `region-option-${index}`;
    item.role = "option";
    item.className = "suggestion";
    const gu = document.createElement("strong");
    const sido = document.createElement("span");
    gu.textContent = region.gu;
    sido.textContent = region.sido;
    item.append(gu, sido);
    // mousedown: 입력칸의 blur보다 먼저 실행되어 목록이 닫히기 전에 고를 수 있다.
    item.addEventListener("mousedown", (event) => {
      event.preventDefault();
      choose(index);
    });
    list.append(item);
  }

  if (shown.length === 0 && query.trim()) {
    const notice = document.createElement("li");
    notice.className = "suggestion-empty";
    notice.textContent = "지원 목록에 없는 동네예요. 그대로 검색하면 그해 전국 유행을 볼 수 있어요.";
    list.append(notice);
  }
  activeIndex = -1;
  setOpen(list.children.length > 0);
}

function highlight(index) {
  const options = list.querySelectorAll(".suggestion");
  activeIndex = index;
  options.forEach((option, i) => option.setAttribute("aria-selected", String(i === index)));
  if (index >= 0) {
    input.setAttribute("aria-activedescendant", options[index].id);
    options[index].scrollIntoView({ block: "nearest" });
  }
}

function choose(index) {
  const region = shown[index];
  input.value = `${region.sido} ${region.gu}`;
  setOpen(false);
  document.getElementById("birth_year").focus();
}

input.addEventListener("input", render);
input.addEventListener("focus", render);
input.addEventListener("blur", () => setOpen(false));

input.addEventListener("keydown", (event) => {
  if (event.isComposing) return; // 한글 조합 중 Enter·방향키는 IME에 맡긴다.
  const count = list.querySelectorAll(".suggestion").length;
  if (event.key === "ArrowDown" && count) {
    event.preventDefault();
    if (list.hidden) render();
    highlight((activeIndex + 1) % count);
  } else if (event.key === "ArrowUp" && count) {
    event.preventDefault();
    highlight((activeIndex - 1 + count) % count);
  } else if (event.key === "Enter" && !list.hidden && activeIndex >= 0) {
    event.preventDefault(); // 추천을 고르는 Enter는 폼 제출이 아니다.
    choose(activeIndex);
  } else if (event.key === "Escape") {
    setOpen(false);
  }
});
