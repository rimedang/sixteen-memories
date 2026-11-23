"""Flask 화면·API 통합 테스트 (계획서 기능·비기능 요구사항 검증 기준)."""
from pathlib import Path

import database
from database import connect
from seed import seed

FIXTURE_DIR = Path(__file__).parent / "fixtures"


# ---------- 동네·연도 입력 ----------

def test_search_redirects_to_share_link(client):
    response = client.get("/search?region=test-a&birth_year=2004")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/result?region=test-a&year=2020")


def test_search_finds_region_by_typed_name(client):
    # 자동완성으로 고른 이름, 시 이름을 줄인 이름, 띄어쓰기 없이 쓴 이름 모두 같은 지역으로 간다.
    for typed in ["서울특별시 테스트A구", "서울 테스트A구", "테스트A구", "서울테스트A"]:
        response = client.get("/search", query_string={"region": typed, "birth_year": "2004"})
        assert response.headers["Location"].endswith("/result?region=test-a&year=2020"), typed


def test_unsupported_region_shows_notice_and_trends(client):
    # 미지원 동네도 멈추지 않고: 결과 화면에서 "준비 중" 안내 + 그해 전국 유행을 보여준다.
    response = client.get("/search", query_string={"region": "대구 수성구", "birth_year": "2004"}, follow_redirects=True)
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "아직 준비 중인 동네예요" in html
    assert "대구 수성구" in html
    assert "2020 TV방송" in html               # 2020년 전국 유행
    assert "2020년 이야기 나누기" in html       # 연도별 이야기도 이용 가능
    assert "기간형 추억 A" not in html          # 다른 지역 추억은 보여주지 않음


def test_empty_region_shows_notice(client):
    response = client.get("/search?region=&birth_year=2004")
    assert response.status_code == 400
    assert "동네를 입력해 주세요" in response.get_data(as_text=True)


def test_unsupported_region_name_is_shown_as_text(client):
    # 보안: 입력한 동네 이름은 HTML로 해석하지 않고 글자 그대로 보여준다.
    html = client.get("/result", query_string={"region": "<b>우리동네</b>", "year": "2016"}).get_data(as_text=True)
    assert "&lt;b&gt;우리동네&lt;/b&gt;" in html
    assert "<b>우리동네</b>" not in html


def test_out_of_range_year_shows_notice(client):
    response = client.get("/search?region=test-a&birth_year=1990")
    assert response.status_code == 400
    assert "1997~2006" in response.get_data(as_text=True)


def test_text_birth_year_shows_notice(client):
    response = client.get("/search?region=test-a&birth_year=abcd")
    assert response.status_code == 400
    assert "숫자 4자리" in response.get_data(as_text=True)


# ---------- 추억 자료 조회 ----------

def test_result_shows_only_memories_of_region_and_year(client):
    html = client.get("/result?region=test-a&year=2016").get_data(as_text=True)
    assert "기간형 추억 A" in html          # 2015~2018 자료 → 표시
    assert "단일 연도 추억 B" not in html    # 2020 자료 → 숨김
    assert "다른 지역 추억 C" not in html    # 다른 지역 → 숨김


def test_result_without_memories_shows_notice(client):
    html = client.get("/result?region=test-a&year=2013").get_data(as_text=True)
    assert "추억 자료를 준비하고 있어요" in html


# ---------- 결과 공유 ----------

def test_share_link_shows_target_year_and_years_ago(client):
    response = client.get("/result?region=test-a&year=2016")
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "2016년, 지금으로부터 10년 전" in html
    assert "2000" not in html  # 출생연도(2000년생)는 공유 화면에 나오지 않음


def test_result_fetches_regions_only_once(client, monkeypatch):
    # 지역 이름 해석과 화면 렌더링이 같은 지역 목록을 공유하도록 조회 횟수를 한 번으로 제한한다.
    original_get_regions = database.get_regions
    call_count = 0

    def counted_get_regions(conn):
        nonlocal call_count
        call_count += 1
        return original_get_regions(conn)

    monkeypatch.setattr(database, "get_regions", counted_get_regions)

    response = client.get("/result?region=test-a&year=2016")

    assert response.status_code == 200
    assert call_count == 1


def test_share_link_with_bad_year_shows_notice(client):
    assert client.get("/result?region=test-a&year=2030").status_code == 400
    assert client.get("/result?region=test-a&year=abc").status_code == 400


def test_share_link_with_missing_params_shows_notice(client):
    # 주소를 잘못 복사해 region이나 year가 빠져도 서버 오류 없이 입력 화면에서 안내한다.
    assert "동네를 입력해 주세요" in client.get("/result?year=2016").get_data(as_text=True)
    assert "올바르지 않은 연도" in client.get("/result?region=test-a").get_data(as_text=True)
    assert client.get("/result").status_code == 400


def test_share_link_opens_same_result_as_search(client):
    # 검색 후 도착한 화면과, 복사한 링크를 새 창에서 연 화면이 같아야 한다.
    searched = client.get("/search?region=테스트A구&birth_year=2000", follow_redirects=True)
    shared = client.get("/result?region=test-a&year=2016")
    assert searched.status_code == shared.status_code == 200
    assert searched.get_data(as_text=True) == shared.get_data(as_text=True)


# ---------- 전국 공통 유행 ----------

def test_trends_of_target_year_only(client):
    html = client.get("/result?region=test-b&year=2016").get_data(as_text=True)
    assert "2016 영화" in html
    assert "2016 노래" in html          # 설명·출처가 없는 유행도 표시
    assert "2020 TV방송" not in html


# ---------- 추억별 댓글 ----------

def post_comment(client, memory_id, nickname, content):
    return client.post(
        f"/api/memories/{memory_id}/comments",
        json={"nickname": nickname, "content": content},
    )


def test_comment_is_saved_only_to_its_memory(client):
    assert post_comment(client, "mem-a", "아림", "A 추억 소감").status_code == 201

    a_comments = client.get("/api/memories/mem-a/comments").get_json()["comments"]
    b_comments = client.get("/api/memories/mem-b/comments").get_json()["comments"]
    assert [c["content"] for c in a_comments] == ["A 추억 소감"]
    assert b_comments == []  # A 추억의 댓글이 B 추억에 나타나지 않음


def test_invalid_comments_are_rejected(client):
    assert post_comment(client, "mem-a", "", "내용").status_code == 400
    assert post_comment(client, "mem-a", "아림", "").status_code == 400
    assert post_comment(client, "mem-a", "아림", "가" * 201).status_code == 400
    assert client.get("/api/memories/mem-a/comments").get_json()["comments"] == []


def test_comment_on_unknown_memory_is_rejected(client):
    assert post_comment(client, "없는추억", "아림", "내용").status_code == 404
    assert client.get("/api/memories/없는추억/comments").status_code == 404


def test_comment_api_rejects_malformed_body(client):
    # 수정 전에는 본문이 목록이거나 닉네임이 숫자이면 서버 오류(500)가 났다.
    for url in ["/api/memories/mem-a/comments", "/api/years/2016/comments"]:
        assert client.post(url, json=["아림", "내용"]).status_code == 400
        assert client.post(url, json={"nickname": 123, "content": "내용"}).status_code == 400
        assert client.post(url, data="not json", content_type="application/json").status_code == 400
    assert client.get("/api/memories/mem-a/comments").get_json()["comments"] == []
    assert client.get("/api/years/2016/comments").get_json()["comments"] == []


def test_recent_comments_are_previewed_on_card(client):
    # 소감이 있으면 '소감 보기'를 누르지 않아도 최근 2개를 카드에 보여주고, 전체 수를 표시한다.
    for text in ["첫 번째 소감", "두 번째 소감", "세 번째 소감"]:
        post_comment(client, "mem-a", "아림", text)
    html = client.get("/result?region=test-a&year=2016").get_data(as_text=True)
    assert "두 번째 소감" in html and "세 번째 소감" in html
    assert "첫 번째 소감" not in html
    assert "(3)" in html


def test_card_without_comments_has_no_preview(client):
    html = client.get("/result?region=test-a&year=2016").get_data(as_text=True)
    assert '<ul class="comment-preview" hidden>' in html


def test_script_comment_is_stored_as_plain_text(client):
    # 보안: 태그는 저장만 되고, 화면에서는 app.js가 textContent로 그대로 표시한다.
    text = "<script>alert('hi')</script>"
    post_comment(client, "mem-a", "아림", text)
    comments = client.get("/api/memories/mem-a/comments").get_json()["comments"]
    assert comments[0]["content"] == text


# ---------- 데이터 적재 ----------

def test_seed_rejects_invalid_rows(tmp_path):
    conn = connect(tmp_path / "seed.db")
    result = seed(conn, FIXTURE_DIR)
    conn.close()
    assert result["memories"] == 8 and result["trends"] == 3 and result["photos"] == 3
    # 제목 없음, 미지원 지역, 잘못된 카테고리, 없는 추억의 사진, 범위 밖 연도의 사진
    assert len(result["skipped"]) == 5


# ---------- 연도별 사진 ----------

def test_photo_shows_latest_capture_up_to_selected_year(client):
    # 사진: 2015년, 2017년 → 2016년에는 2015년 사진, 2018년에는 2017년 사진
    # (2017년 사진 주소는 연도 버튼에도 들어 있으므로, 화면에 표시되는 img의 src만 확인한다)
    html_2016 = client.get("/result?region=test-a&year=2016").get_data(as_text=True)
    assert 'class="memory-photo" src="/static/images/memories/test-a-2015.jpg"' in html_2016
    assert '<span class="photo-year">2015년 모습</span>' in html_2016

    html_2018 = client.get("/result?region=test-a&year=2018").get_data(as_text=True)
    assert 'class="memory-photo" src="/static/images/memories/test-a-2017.jpg"' in html_2018
    assert '<span class="photo-year">2017년 모습</span>' in html_2018


def test_comments_are_shared_across_years_of_same_memory(client):
    # 연도별로 사진이 달라도 추억은 하나라서 댓글이 한 곳에 모인다
    client.post("/api/memories/mem-a/comments", json={"nickname": "아림", "content": "2016년에 자주 갔어요"})
    html_2018 = client.get("/result?region=test-a&year=2018").get_data(as_text=True)
    assert 'data-memory-id="mem-a"' in html_2018
    comments = client.get("/api/memories/mem-a/comments").get_json()["comments"]
    assert comments[0]["content"] == "2016년에 자주 갔어요"


def test_memory_without_source_is_shown_without_link(client):
    html = client.get("/result?region=test-a&year=2016").get_data(as_text=True)
    assert "출처 없는 추억 D" in html
    assert html.count("관련 글 보기") == 2  # 출처가 있는 추억 A와 유행 1건만 링크 표시


def test_trend_poster_is_shown_with_credit(client):
    html = client.get("/result?region=test-a&year=2016").get_data(as_text=True)
    assert 'src="/static/images/trends/t-2016-1.jpg"' in html
    assert "이미지: TMDB" in html
    assert "This product uses the TMDB API" in html  # TMDB 이용 조건의 출처 표시


def test_seed_removes_regions_dropped_from_csv(tmp_path):
    # 실제 사례: 서울 10곳 → 5곳으로 줄였을 때 DB에 예전 지역이 남지 않아야 함
    data = tmp_path / "data"
    data.mkdir()
    (data / "regions.csv").write_text(
        "region_id,sido,gu\nkeep,서울특별시,남는구\ndrop,서울특별시,빠지는구\n", encoding="utf-8")
    conn = connect(tmp_path / "seed.db")
    seed(conn, data)
    (data / "regions.csv").write_text("region_id,sido,gu\nkeep,서울특별시,남는구\n", encoding="utf-8")
    seed(conn, data)
    ids = [row[0] for row in conn.execute("SELECT id FROM regions")]
    conn.close()
    assert ids == ["keep"]


# ---------- 빠진 해, 연도 버튼 ----------

def test_memory_with_default_photo_uses_dated_photo_only_in_that_year(client):
    # mem-g: 기본 사진 + 2017년 사진 (실제 사례: 노원탈축제는 기본 사진, 2014·2016… 은 그해 축제 사진)
    html_2017 = client.get("/result?region=test-b&year=2017").get_data(as_text=True)
    assert 'class="memory-photo" src="/static/images/memories/test-g-2017.jpg"' in html_2017
    assert '<span class="photo-year">2017년 모습</span>' in html_2017

    # 2018년에는 2017년 사진을 이어 쓰지 않고 기본 사진, "○○년 모습" 배지도 없음
    html_2018 = client.get("/result?region=test-b&year=2018").get_data(as_text=True)
    assert 'class="memory-photo" src="/static/images/memories/test-g.jpg"' in html_2018
    assert '<span class="photo-year">' not in html_2018


def test_memory_with_several_photos_shows_all(client):
    # mem-h: image_file에 사진 3장을 ;로 적은 추억 (실제 사례: 계산 나무놀이터)
    html = client.get("/result?region=test-b&year=2016").get_data(as_text=True)
    for name in ["test-h-1.jpg", "test-h-2.jpg", "test-h-3.jpg"]:
        assert f'class="gallery-photo" src="/static/images/memories/{name}"' in html


def test_memory_is_hidden_in_skip_years(client):
    # mem-e: 2014~2018 중 2016년만 미개최 (실제 사례: 부평풍물대축제 2019~2021 미개최)
    assert "빠진 해 있는 축제 E" not in client.get("/result?region=test-a&year=2016").get_data(as_text=True)
    assert "빠진 해 있는 축제 E" in client.get("/result?region=test-a&year=2017").get_data(as_text=True)


def test_photo_year_buttons_list_all_photos(client):
    html = client.get("/result?region=test-a&year=2016").get_data(as_text=True)
    assert 'data-year="2015"' in html and 'data-year="2017"' in html  # 2017년 사진도 버튼으로 볼 수 있음
    assert 'class="photo-year-button is-active"' in html


# ---------- 연도별 이야기 (전국 유행 공통 공간) ----------

def test_year_comments_are_separated_by_year(client):
    assert client.post("/api/years/2016/comments", json={"nickname": "아림", "content": "포켓몬 빵"}).status_code == 201
    assert [c["content"] for c in client.get("/api/years/2016/comments").get_json()["comments"]] == ["포켓몬 빵"]
    assert client.get("/api/years/2017/comments").get_json()["comments"] == []


def test_year_comments_are_separate_from_memory_comments(client):
    client.post("/api/years/2016/comments", json={"nickname": "아림", "content": "연도 이야기"})
    assert client.get("/api/memories/mem-a/comments").get_json()["comments"] == []


def test_year_comments_reject_bad_input(client):
    assert client.get("/api/years/2030/comments").status_code == 404
    assert client.post("/api/years/2016/comments", json={"nickname": "", "content": "x"}).status_code == 400
    assert client.post("/api/years/2016/comments", json={"nickname": "a", "content": "가" * 201}).status_code == 400


def test_result_page_has_year_board(client):
    html = client.get("/result?region=test-a&year=2016").get_data(as_text=True)
    assert "2016년 이야기 나누기" in html
    assert 'data-comments-url="/api/years/2016/comments"' in html


# ---------- 이전·다음 연도 이동 ----------

def test_year_nav_links_to_neighbor_years_of_same_region(client):
    html = client.get("/result?region=test-a&year=2016").get_data(as_text=True)
    assert 'href="/result?region=test-a&amp;year=2015"' in html
    assert 'href="/result?region=test-a&amp;year=2017"' in html


def test_year_nav_hides_buttons_at_range_ends(client):
    first = client.get("/result?region=test-a&year=2013").get_data(as_text=True)
    last = client.get("/result?region=test-a&year=2022").get_data(as_text=True)
    assert "year=2012" not in first and "year=2014" in first
    assert "year=2023" not in last and "year=2021" in last


def test_memory_without_description_is_shown(client):
    # 설명을 지어내지 않도록 설명은 선택 항목 (제목·분류·사진만 있는 추억도 표시)
    html = client.get("/result?region=test-a&year=2016").get_data(as_text=True)
    assert "설명 없는 추억 F" in html
