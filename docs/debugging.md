# 디버깅 기록 (실제로 발생한 문제)

| # | 증상 | 원인 | 해결 | 관련 파일 |
|---|---|---|---|---|
| 1 | 지원 지역 목록에서 인천이 서울보다 먼저 나옴 | `ORDER BY sido DESC`: 가나다순으로 "서울 < 인천"이라 내림차순이면 인천이 먼저 | CSV에 적힌 순서(`ORDER BY rowid`)로 정렬 | `database.py` `get_regions` |
| 2 | 결과 화면 본문이 화면 왼쪽 끝에 붙음 | `.result-body { padding: 56px 0 24px }`가 `.wrap`의 좌우 여백(20px)을 덮어씀 | 위·아래 여백만 따로 지정 (`padding-top`, `padding-bottom`) | `static/style.css` |
| 3 | trends.csv에서 id를 `2013-drama-1` → `2013-tv-1`로 바꿨는데 예전 행이 DB에 남음 | `INSERT OR REPLACE`는 같은 id만 교체하고, CSV에서 사라진 행은 지우지 않음 | 전국 유행은 댓글이 연결되지 않으므로 적재할 때마다 테이블을 새로 만듦 | `seed.py` |
| 4 | TMDB에서 "도깨비" 검색 시 다른 작품 "도깨비 불"의 포스터가 잡힘 | 짧은 제목은 동명 작품이 많고, TMDB의 한국어 공식 제목은 "쓸쓸하고 찬란하神 - 도깨비" | `search_title` 칸을 추가해 검색어를 따로 지정 | `tools/common.py` `search_text` |
| 5 | "낭만닥터 김사부 2", "펜트하우스 2"를 찾지 못함 | TMDB는 시즌을 별도 작품이 아닌 한 시리즈로 관리 | `search_title`에 시리즈 제목 입력 | `data/trends.csv` |
| 6 | IGDB에서 "Genshin Impact"(원신) 검색 시 확장팩 포스터가 잡힘 | ① 같은 해 확장팩과 본편 중 연도만 비교 ② IGDB 검색 결과 30개에 본편이 아예 없음 (확장팩만 반환) | ① 제목이 정확히 같은 결과를 우선 ② 정확히 같은 제목이 없으면 `where name ~ "제목"`으로 한 번 더 조회 | `tools/fetch_igdb_covers.py` `choose_best`, `search` |
| 7 | 카카오톡 같은 일반 앱도 IGDB에서 게임 표지를 찾으려 함 | '앱·게임' 분류에 앱과 게임이 섞임 | 영문 검색어(`search_title`)가 있는 행만 검색 | `tools/fetch_igdb_covers.py` `needs_cover` |
| 9 | iTunes 검색 결과가 모든 노래에서 0개 | 한국(KR) 스토어는 Search API에 음악 결과를 주지 않음 ("IU"로도 0개). 미국(US) 스토어는 결과가 있지만 곡명을 영어로 돌려줌 (밤편지 → Through the Night) | 미국 스토어로 검색 | `tools/fetch_itunes_artwork.py` `COUNTRY` |
| 10 | 곡명 일치로 고르자 "썸"은 노래방 버전, "아로하"는 다른 가수 커버, "Dynamite"는 오르골 버전이 잡힘 | 원곡은 영어 곡명이라 한글 곡명 일치 조건에서 빠지고, 한글 제목을 그대로 쓴 커버곡만 남음 | 곡명 일치 대신 "곡명+가수" 검색 순위를 믿고, karaoke·inst·live·music box 등이 들어간 버전만 제외 | `is_original`, `choose_best` |
| 11 | 짧은 시간에 요청하면 HTTP 403 | Apple의 요청 횟수 제한 | 곡마다 4초 대기, 403이면 60초 후 한 번 재시도 | `WAIT_SECONDS`, `RETRY_WAIT_SECONDS` |
| 12 | "제외 단어" 테스트가 실패 (노래방 버전이 걸러지지 않음) | 정규식의 `\b`(단어 경계)가 파일에 쓰이는 과정에서 백스페이스 문자로 바뀜 | 테스트가 실패해 발견 → 파일에서 문자를 직접 확인(`cat -A`)하고 `\b`로 교체 | `NOT_ORIGINAL` |
| 13 | 메인 화면을 열면 TemplateSyntaxError, 테스트 4개 실패 | VSCode의 HTML 자동 정렬이 Jinja 문법 `{% if selected_region == 'other' %}`를 HTML 속성으로 착각해 `selected_region="" ="other"`로 바꿈 | 원래 문법으로 복구하고, `.prettierignore`에 `templates/`를 넣어 템플릿은 자동 정렬에서 제외 | `templates/index.html`, `.prettierignore` |
| 8 | Git Bash에서 `python seed.py` 실행 시 한글 출력이 깨짐 | 터미널 인코딩(cp949)과 출력 인코딩 불일치 | PowerShell에서 실행하거나 `PYTHONIOENCODING=utf-8` 설정 (DB 적재 결과에는 영향 없음) | - |

## 디버깅 방법
- 포스터 도구는 `--dry-run` 옵션으로 **저장 전에 매칭 결과를 먼저 확인**하고, 연도 차이가 2년 이상이면 경고를 출력하도록 만들어 잘못된 매칭을 찾았다.
- 6번은 실제 IGDB 응답을 출력해 보고(이름·연도·표지 여부) 본편이 검색 결과에 없다는 것을 확인한 뒤 해결했다.
- 해결한 문제는 재발하지 않도록 테스트를 추가했다 (예: `test_igdb_choose_best_prefers_exact_title`).

## 최종 점검에서 찾은 문제 (2026-11-23, Claude Code로 예외 입력을 넣어 보며 점검)

| # | 증상 | 원인 | 해결 | 관련 파일 |
|---|---|---|---|---|
| 14 | 출생연도에 `²⁰⁰⁴`(위첨자 숫자)를 넣으면 `invalid literal for int() with base 10` 영어 문구가 화면에 나옴 | `str.isdigit()`은 위첨자도 숫자로 보지만 `int()`는 바꾸지 못함 | `isdecimal()`로 검사 (전각 숫자 `１９９７`처럼 `int()`가 바꿀 수 있는 숫자는 계속 허용) | `validators.py` `parse_birth_year` |
| 15 | 댓글 API에 본문을 목록(`[1, 2]`)으로 보내거나 닉네임을 숫자(`123`)로 보내면 500 서버 오류 | `data.get(...)`, `nickname.strip()`이 dict·문자열이 아닌 값에서 `AttributeError` | 본문이 객체가 아니면 빈 값으로 보고, 글자가 아닌 값은 "글자로 입력해 주세요"로 거부 (400) | `app.py` `save_comment`, `validators.py` `validate_comment` |
| 16 | 서버가 꺼져 있을 때 소감 창이 비어 있고 "남기기"를 눌러도 안내가 없음 | `fetch` 실패·JSON이 아닌 응답을 처리하지 않음 | `requestJson()`으로 요청 처리를 모으고 안내 문구 표시 (`refactoring.md` 3번) | `static/app.js` |
| 17 | 휴대폰 화면(폭 375px)에서 부평역처럼 연도별 사진이 많은 카드의 **설명 글 오른쪽이 잘리고**, 2020년 이후 연도 버튼이 보이지 않음 | 좁은 화면용 1열 그리드 `1fr`은 내용의 최소 너비보다 작아지지 않아, 연도 버튼 줄(521px)만큼 칸이 넓어지고 카드(`overflow: hidden`)가 넘친 부분을 잘라냄 | `minmax(0, 1fr)`로 칸 너비를 카드 폭에 맞춤 → 연도 버튼 줄은 카드 안에서 가로 스크롤 | `static/style.css` (`@media (max-width: 860px)`) |

- 14·15는 화면의 입력칸으로는 잘 일어나지 않고 주소나 API를 직접 호출할 때 생긴다. 그래도 사용자에게 영어 오류나 500이 보이면 안 되므로 고쳤다.
- 재발 방지 테스트: `test_invalid_birth_year_input`(위첨자), `test_comment_with_non_text_values_is_rejected`, `test_comment_api_rejects_malformed_body`.
  수정 전 코드로 되돌린 복사본에서 이 테스트 5개가 실패하고, 수정 후 모두 통과하는 것을 확인했다.
