// 결과 화면의 동작: 결과 링크 복사, 추억 소감 창, 연도별 이야기, 연도별 사진 넘겨 보기
// 보안: 사용자가 쓴 댓글은 textContent로만 넣어서 HTML로 해석되지 않게 한다.

const PREVIEW_COUNT = 2; // 추억 카드에 미리 보여줄 최근 소감 수 (config.py의 COMMENT_PREVIEW_COUNT와 같게)

// ---------- 결과 링크 복사 ----------
const copyButton = document.getElementById("copy-link");
const copyStatus = document.getElementById("copy-status");

copyButton.addEventListener("click", async () => {
  const link = window.location.href;
  try {
    await navigator.clipboard.writeText(link);
    copyStatus.textContent = "링크를 복사했어요. 친구에게 보내 보세요!";
  } catch {
    // 클립보드 권한이 없을 때는 주소를 직접 보여준다.
    copyStatus.textContent = "복사하지 못했어요. 이 주소를 복사해 주세요: " + link;
  }
});

// ---------- 댓글 공통 ----------
function createCommentItem(comment, withTime = true) {
  const item = document.createElement("li");
  const name = document.createElement("strong");
  const body = document.createElement("p");
  name.textContent = comment.nickname; // innerHTML을 쓰지 않는다
  body.textContent = comment.content;
  item.append(name);
  if (withTime) {
    const time = document.createElement("time");
    time.textContent = comment.created_at;
    item.append(time);
  }
  item.append(body);
  return item;
}

// 목록 자리에 안내 문구 한 줄을 보여준다. (소감이 없을 때, 불러오지 못했을 때)
function showListMessage(listElement, text) {
  const item = document.createElement("li");
  item.className = "empty";
  item.textContent = text;
  listElement.replaceChildren(item);
}

function renderComments(listElement, comments) {
  if (comments.length === 0) {
    showListMessage(listElement, "첫 소감을 남겨 주세요.");
    return;
  }
  listElement.replaceChildren(...comments.map((comment) => createCommentItem(comment)));
}

// 서버에 요청하고 JSON 응답을 돌려준다. 실패하면 화면에 보여줄 안내 문구를 담은 Error를 던진다.
// - 서버가 꺼져 있거나 인터넷이 끊김 → fetch 자체가 실패
// - 서버 오류(500)처럼 JSON이 아닌 응답 → response.json()이 실패
// - 잘못된 입력(400)·없는 추억(404) → 서버가 보낸 error 문구를 그대로 사용
async function requestJson(url, options) {
  let response;
  try {
    response = await fetch(url, options);
  } catch {
    throw new Error("서버에 연결하지 못했어요. 잠시 후 다시 시도해 주세요.");
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.error || "요청을 처리하지 못했어요. 잠시 후 다시 시도해 주세요.");
  }
  return data;
}

// 댓글 목록을 불러와 그린다. 성공하면 댓글 배열, 실패하면 안내 문구를 보여주고 null을 돌려준다.
async function loadComments(url, listElement) {
  try {
    const data = await requestJson(url);
    renderComments(listElement, data.comments);
    return data.comments;
  } catch (error) {
    showListMessage(listElement, error.message);
    return null;
  }
}

// 폼 내용을 저장한다. 성공하면 true, 실패하면 폼 아래에 안내 문구를 보여주고 false.
async function submitComment(url, form) {
  const errorBox = form.querySelector(".form-error");
  const button = form.querySelector('button[type="submit"]');
  errorBox.textContent = "";
  button.disabled = true; // 저장하는 동안 버튼을 여러 번 눌러 같은 소감이 겹쳐 저장되지 않게

  try {
    await requestJson(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        nickname: form.nickname.value,
        content: form.content.value,
      }),
    });
  } catch (error) {
    errorBox.textContent = error.message;
    return false;
  } finally {
    button.disabled = false;
  }
  form.content.value = "";
  updateCharCount(form);
  return true;
}

function updateCharCount(form) {
  const counter = form.querySelector(".char-count");
  counter.textContent = `${form.content.value.length} / ${form.content.maxLength}`;
}

for (const form of document.querySelectorAll(".comment-form")) {
  form.content.addEventListener("input", () => updateCharCount(form));
}

// ---------- 연도별 이야기 (결과 화면에 항상 펼쳐 둔다) ----------
const yearBoard = document.querySelector(".year-board");
if (yearBoard) {
  const list = yearBoard.querySelector(".comment-list");
  const form = yearBoard.querySelector(".comment-form");
  const url = yearBoard.dataset.commentsUrl;
  loadComments(url, list);
  form.addEventListener("submit", async (event) => {
    event.preventDefault(); // 페이지가 새로고침되지 않게 막기
    if (await submitComment(url, form)) {
      await loadComments(url, list);
    }
  });
}

// ---------- 추억 소감 창 ----------
// '소감 보기·남기기'를 누르면 화면 위에 창(dialog)이 열린다. 뒤의 결과 화면은 그대로 둔다.
const dialog = document.getElementById("comment-dialog");
const dialogTitle = document.getElementById("comment-dialog-title");
const dialogList = dialog.querySelector(".comment-list");
const dialogForm = dialog.querySelector(".comment-form");
let currentCard = null; // 지금 창에 열려 있는 추억 카드

// 카드의 미리보기(최근 소감)와 소감 수를 새 목록에 맞춰 다시 그린다.
function updateCardPreview(card, comments) {
  const preview = card.querySelector(".comment-preview");
  preview.replaceChildren(...comments.slice(-PREVIEW_COUNT).map((c) => createCommentItem(c, false)));
  preview.hidden = comments.length === 0;
  card.querySelector(".comment-count").textContent = comments.length ? ` (${comments.length})` : "";
}

async function openCommentDialog(card) {
  currentCard = card;
  dialogTitle.textContent = card.dataset.title;
  dialogForm.querySelector(".form-error").textContent = "";
  dialogList.replaceChildren();
  document.body.classList.add("dialog-open"); // 뒤 화면이 같이 스크롤되지 않게
  dialog.showModal();
  await loadComments(card.dataset.commentsUrl, dialogList);
}

for (const button of document.querySelectorAll(".open-comments")) {
  button.addEventListener("click", () => openCommentDialog(button.closest(".memory-card")));
}

dialog.querySelector(".dialog-close").addEventListener("click", () => dialog.close());
// 창 바깥(어두운 배경)을 누르면 닫는다. Esc 키는 브라우저가 알아서 닫아 준다.
dialog.addEventListener("click", (event) => {
  if (event.target === dialog) dialog.close();
});
dialog.addEventListener("close", () => {
  document.body.classList.remove("dialog-open");
  currentCard = null;
});

dialogForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const card = currentCard;
  const url = card.dataset.commentsUrl;
  if (await submitComment(url, dialogForm)) {
    const comments = await loadComments(url, dialogList);
    if (comments) updateCardPreview(card, comments);
  }
});

// ---------- 연도별 사진 넘겨 보기 ----------
// 카드 안의 연도 버튼을 누르면, 결과 연도를 바꾸지 않고 그 해의 사진으로 바꾼다.
for (const figure of document.querySelectorAll(".memory-card figure")) {
  const photo = figure.querySelector(".memory-photo");
  const badge = figure.querySelector(".photo-year");
  const buttons = figure.querySelectorAll(".photo-year-button");

  for (const button of buttons) {
    button.addEventListener("click", () => {
      photo.src = button.dataset.src;
      photo.alt = photo.alt.replace(/\d{4}년 모습$/, `${button.dataset.year}년 모습`);
      if (badge) {
        badge.textContent = `${button.dataset.year}년 모습`;
      }
      for (const other of buttons) {
        const active = other === button;
        other.classList.toggle("is-active", active);
        other.setAttribute("aria-pressed", String(active));
      }
    });
  }
}
