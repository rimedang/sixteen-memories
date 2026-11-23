"""자료 준비 도구(TMDB·IGDB)의 선택 로직 테스트 (인터넷 연결 없이 실행)."""
from tools import fetch_igdb_covers as igdb
from tools import fetch_tmdb_posters as tmdb
from tools.common import TREND_IMAGE_DIR, read_env_file, search_text, trend_image_path


# ---------- 공통 ----------

def test_trend_image_is_saved_in_year_folder():
    target, image_file = trend_image_path({"id": "2015-movie-2", "year": "2015"})
    assert target == TREND_IMAGE_DIR / "2015" / "2015-movie-2.jpg"
    assert image_file == "trends/2015/2015-movie-2.jpg"


def test_read_env_file_ignores_comments_and_quotes(tmp_path):
    env = tmp_path / ".env"
    env.write_text('# 주석\nTMDB_API_KEY="abc123"\n\nOTHER=x\n', encoding="utf-8")
    assert read_env_file(env) == {"TMDB_API_KEY": "abc123", "OTHER": "x"}
    assert read_env_file(tmp_path / "없는파일") == {}


def test_search_text_prefers_search_title():
    assert search_text({"title": "클래시 오브 클랜", "search_title": "Clash of Clans"}) == "Clash of Clans"
    assert search_text({"title": "명량", "search_title": ""}) == "명량"


# ---------- TMDB ----------

def test_tmdb_release_year_reads_movie_and_tv_dates():
    assert tmdb.release_year({"release_date": "2013-01-23"}) == 2013
    assert tmdb.release_year({"first_air_date": "2012-10-01"}) == 2012
    assert tmdb.release_year({"release_date": ""}) is None


def test_tmdb_choose_best_prefers_closest_year_with_poster():
    results = [
        {"title": "리메이크", "release_date": "2019-05-01", "poster_path": "/a.jpg"},
        {"title": "포스터 없음", "release_date": "2013-01-01", "poster_path": None},
        {"title": "원작", "release_date": "2013-01-23", "poster_path": "/b.jpg"},
    ]
    assert tmdb.choose_best(results, 2013)["title"] == "원작"


def test_tmdb_choose_best_returns_none_without_posters():
    assert tmdb.choose_best([{"title": "x", "poster_path": None}], 2013) is None
    assert tmdb.choose_best([], 2013) is None


# ---------- IGDB ----------

def test_igdb_clean_title_removes_kakao_label():
    assert igdb.clean_title("애니팡2 for Kakao") == "애니팡2"


def test_igdb_release_year_from_unix_time():
    assert igdb.release_year({"first_release_date": 1375315200}) == 2013  # 2013-08-01
    assert igdb.release_year({}) is None


def test_igdb_choose_best_needs_cover():
    games = [
        {"name": "표지 없음", "first_release_date": 1375315200},
        {"name": "표지 있음", "first_release_date": 1375315200, "cover": {"image_id": "abc"}},
    ]
    assert igdb.choose_best(games, 2013)["name"] == "표지 있음"


def test_igdb_choose_best_prefers_exact_title():
    # 실제 사례: "Genshin Impact" 검색 시 같은 해의 확장팩이 먼저 잡혔던 문제
    games = [
        {"name": "Genshin Impact: A New Star Approaches", "first_release_date": 1601251200,
         "cover": {"image_id": "dlc"}},
        {"name": "Genshin Impact", "first_release_date": 1601251200, "cover": {"image_id": "main"}},
    ]
    assert igdb.choose_best(games, 2020, "Genshin Impact")["name"] == "Genshin Impact"


# ---------- iTunes ----------

def test_itunes_normalize_ignores_spaces_symbols_and_feat():
    from tools.fetch_itunes_artwork import normalize
    assert normalize("눈, 코, 입") == normalize("눈,코,입") == "눈코입"
    assert normalize("자니 (Feat. Dynamic Duo)") == "자니"


def test_itunes_choose_best_skips_karaoke_and_instrumental():
    from tools.fetch_itunes_artwork import choose_best
    # 실제 사례: "썸 소유 정기고" 검색 시 노래방 버전, "시간을 달려서" 검색 시 연주곡이 먼저 잡힘
    tracks = [
        {"trackName": "썸 : Originally Performed By 소유,정기고 (Karaoke Verison)", "artworkUrl100": "k"},
        {"trackName": "Rough (Inst.)", "artworkUrl100": "i"},
        {"trackName": "Some (feat. Lil Boi)", "collectionName": "Some", "artworkUrl100": "o"},
    ]
    assert choose_best(tracks, "썸", 2014)["artworkUrl100"] == "o"
    assert choose_best([], "썸", 2014) is None


def test_itunes_is_original_uses_whole_words():
    from tools.fetch_itunes_artwork import is_original
    assert is_original({"trackName": "Alive", "collectionName": "Against All Odds"})
    assert not is_original({"trackName": "Some (Live)"})
