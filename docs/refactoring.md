# 리팩토링 기록

## 1. 자료 준비 도구의 중복 코드를 `tools/common.py`로 분리

### 배경
처음에는 TMDB 포스터 도구(`tools/fetch_tmdb_posters.py`) 하나만 있었다. 이후 게임 표지를 받는
IGDB 도구를 추가하려고 보니, 다음 코드를 두 파일에 똑같이 써야 하는 상황이 되었다.

| 중복될 코드 | 역할 |
|---|---|
| `read_env_file`, 키 읽기 | `.env` 파일에서 API 키 읽기 |
| CSV 읽기·열 추가·저장 | `data/trends.csv` 처리 (BOM, 새 열 추가) |
| 이미지 내려받기 | 폴더 생성 + 파일 저장 |
| 연도가 가장 가까운 결과 고르기 | 동명 작품(리메이크 등) 중 올바른 작품 선택 |
| 연도 차이 경고 문구 | 잘못 찾았을 가능성 표시 |

### 전 (`docs/refactoring/before_fetch_tmdb_posters.py`)
- TMDB 도구 안에 위 기능이 모두 들어 있어 파일 하나가 여러 역할을 함
- `main()` 안에서 CSV를 직접 열고, 열 이름 목록을 직접 고치고, 저장까지 처리
- 연도 비교 로직이 `choose_best` 안에 TMDB 전용으로 묶여 있어 다른 API에 재사용 불가

```python
def choose_best(results, year):
    candidates = [item for item in results if item.get("poster_path")]
    if not candidates:
        return None

    def year_gap(item):
        found = release_year(item)
        return abs(found - year) if found else 99

    return min(candidates, key=year_gap)
```

### 후
- 공통 기능은 `tools/common.py`에 한 번만 작성: `get_secret`, `load_trends`, `save_trends`,
  `download`, `choose_closest_year`, `search_text`, `year_warning`
- 연도 비교는 "연도를 꺼내는 함수(`year_of`)"를 인자로 받아 TMDB·IGDB 모두 사용

```python
# tools/common.py
def choose_closest_year(candidates, year, year_of):
    ...

# tools/fetch_tmdb_posters.py — TMDB 결과에서 연도를 꺼내는 방법만 알려 준다
def choose_best(results, year):
    with_poster = [item for item in results if item.get("poster_path")]
    return choose_closest_year(with_poster, year, release_year)

# tools/fetch_igdb_covers.py — IGDB는 유닉스 시간이라 연도 꺼내는 방법만 다르다
def choose_best(games, year):
    with_cover = [g for g in games if (g.get("cover") or {}).get("image_id")]
    return choose_closest_year(with_cover, year, release_year)
```

### 효과
- 각 도구 파일에는 그 API에만 해당하는 코드(검색 주소, 인증, 연도 형식)만 남음
- CSV 저장 방식을 바꿀 때 한 곳만 고치면 됨
- 영문 검색어(`search_title`) 기능을 공통 함수 `search_text`에 넣어 두 도구가 동시에 사용

### 검증
- 리팩토링 전후로 같은 테스트(`tests/test_tmdb_posters.py`)가 통과함을 확인
- IGDB 선택 로직 테스트 3개를 추가해 공통 함수가 두 API 모두에서 동작함을 확인
- 실행 결과: `42 passed`

## 2. 댓글 저장 코드를 두 공간이 함께 쓰도록 정리 (`save_comment`)

자세한 전후 비교는 기말보고서 8-2에 있다. 요약:

| 부분 | 전 | 후 |
|---|---|---|
| `app.py` | 추억 댓글 API 안에 검증·저장이 함께 있음 | `save_comment(save)` 하나가 검증한 뒤 저장 함수를 부름 → 추억 댓글·연도별 이야기가 같은 규칙 사용 |
| `static/app.js` | 주소를 `/api/memories/${id}/comments`로 직접 조립 | HTML의 `data-comments-url`에서 주소를 읽음 → 같은 JS가 두 공간에서 동작 |
| `templates/result.html` | 댓글 입력 HTML을 따로 작성 | Jinja 매크로 `comment_form()` 하나로 통합 |

## 3. 결과 화면 JS의 서버 요청 코드를 `requestJson()` 하나로 모으고 오류 안내 추가 (2026-11-23)

> 작업 도구: Claude Code로 점검하다 문제를 발견하고 수정함. <!-- [직접 수행] 검토 후 "사용자가 검토함"으로 바꾸기 -->

### 전 (문제점)
`loadComments`(목록 불러오기)와 `submitComment`(저장)가 각각 `fetch` → `response.json()` → `response.ok` 확인을
따로 하고 있었고, 둘 다 **실패한 경우를 처리하지 않았다.**

```js
async function loadComments(url, listElement) {
  const response = await fetch(url);       // 서버가 꺼져 있으면 여기서 오류 → 아래 코드가 실행되지 않음
  const data = await response.json();      // 500 오류 HTML이 오면 여기서 오류
  if (!response.ok) {
    listElement.textContent = data.error;
    return null;
  }
  ...
}
async function submitComment(url, form) {
  ...
  const response = await fetch(url, { method: "POST", ... });   // 같은 처리를 한 번 더
  if (!response.ok) {
    errorBox.textContent = (await response.json()).error;
    return false;
  }
  ...
}
```

한계 (브라우저에서 `fetch`가 실패하도록 바꿔 직접 확인함):
- 서버가 꺼져 있거나 인터넷이 끊기면 소감 창이 **빈 채로** 있고, "남기기"를 눌러도 **아무 안내가 없음**.
  오류는 개발자 도구 콘솔에만 `Uncaught (in promise) TypeError: Failed to fetch`로 2번 찍힘
- 요청 처리 방식이 두 곳에 나뉘어 있어, 오류 처리를 넣으려면 두 곳을 모두 고쳐야 함
- 저장 중에 버튼을 여러 번 누를 수 있음

### 후
```js
// 서버에 요청하고 JSON 응답을 돌려준다. 실패하면 화면에 보여줄 안내 문구를 담은 Error를 던진다.
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
```
- `loadComments`, `submitComment`는 `requestJson`을 부르고 `try … catch`로 안내 문구만 보여줌
- 목록 자리에 안내 한 줄을 넣는 코드도 `showListMessage()` 하나로 합침 ("첫 소감을 남겨 주세요." / 오류 안내)
- 저장하는 동안 "남기기" 버튼을 잠시 비활성화 (`button.disabled`)

### 개선된 점
| 상황 | 전 | 후 |
|---|---|---|
| 서버 꺼짐·인터넷 끊김 | 빈 화면, 안내 없음, 콘솔 오류 2건 | "서버에 연결하지 못했어요…" 안내, 콘솔 오류 0건 |
| 서버 오류(500, JSON 아님) | 안내 없음 | "요청을 처리하지 못했어요…" 안내 |
| 잘못된 입력(400) | 서버 문구 표시 | 그대로 서버 문구 표시 (기존 동작 유지) |
| 저장 실패 시 쓰던 글 | 남아 있음 | 그대로 남아 있음 (다시 시도 가능) |

### 검증
- 브라우저에서 `window.fetch`를 실패하도록 바꿔 전후를 비교함 (위 표)
- 정상 동작(소감 저장 → 목록·카드 미리보기·소감 수 갱신, 빈 내용 거부 문구)을 브라우저에서 다시 확인함
- `python -m pytest`: 86 passed (JS는 pytest로 검사하지 않으므로 브라우저 확인으로 대신함)
