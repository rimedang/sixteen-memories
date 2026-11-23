"""입력 검증과 연도 계산 테스트 (계획서 '동네·연도 입력' 검증 기준)."""
import pytest

from validators import (
    calculate_target_year,
    find_region,
    parse_birth_year,
    validate_comment,
    validate_place,
    years_ago,
)


def test_target_year_is_birth_year_plus_16():
    # 계획서 검증 기준: 2004년생 → 2020년
    assert calculate_target_year(2004) == 2020


@pytest.mark.parametrize("birth_year, expected", [(1997, 2013), (2006, 2022)])
def test_target_year_boundaries_are_allowed(birth_year, expected):
    assert calculate_target_year(birth_year) == expected


@pytest.mark.parametrize("birth_year", [1996, 2007, 1980])
def test_out_of_range_year_shows_available_years(birth_year):
    with pytest.raises(ValueError, match="1997~2006"):
        calculate_target_year(birth_year)


@pytest.mark.parametrize("raw, message", [
    ("", "입력해 주세요"),          # 빈 입력
    ("   ", "입력해 주세요"),       # 공백만 입력
    ("abcd", "숫자 4자리"),         # 문자 입력
    ("20o4", "숫자 4자리"),         # 숫자와 문자 혼합
    ("204", "숫자 4자리"),          # 자릿수 부족
    ("²⁰⁰⁴", "숫자 4자리"),         # 위첨자 숫자 (수정 전: 영어 내부 오류 문구가 화면에 나옴)
])
def test_invalid_birth_year_input(raw, message):
    with pytest.raises(ValueError, match=message):
        parse_birth_year(raw)


def test_years_ago_uses_current_year():
    # 계획서 예시: 2026년 접속 시 2010년 → 16년 전
    assert years_ago(2010, 2026) == 16


def test_comment_trims_spaces():
    assert validate_comment("  아림 ", " 반가워요 ") == ("아림", "반가워요")


@pytest.mark.parametrize("nickname, content, message", [
    ("", "내용", "닉네임"),
    ("아림", "", "내용을 입력"),
    ("아림", "   ", "내용을 입력"),
    ("아림", "가" * 201, "200자"),
])
def test_invalid_comment_is_rejected(nickname, content, message):
    with pytest.raises(ValueError, match=message):
        validate_comment(nickname, content)


@pytest.mark.parametrize("nickname, content", [(123, "내용"), ("아림", ["목록"]), ("아림", {"a": 1})])
def test_comment_with_non_text_values_is_rejected(nickname, content):
    # API로 글자가 아닌 값이 들어와도 서버 오류 대신 안내 문구로 거부한다.
    with pytest.raises(ValueError, match="글자로 입력"):
        validate_comment(nickname, content)


def test_comment_with_exactly_200_chars_is_allowed():
    _, content = validate_comment("아림", "가" * 200)
    assert len(content) == 200


@pytest.mark.parametrize("nickname, content", [(None, "내용"), ("아림", None), (None, None)])
def test_comment_with_none_values_is_treated_as_empty_input(nickname, content):
    # None은 API에서 누락된 값을 의미하므로 길이·타입 계산 전에 빈 입력 안내를 반환해야 한다.
    with pytest.raises(ValueError):
        validate_comment(nickname, content)


def test_comment_accepts_exact_nickname_boundary():
    # 닉네임은 최대 20자까지 허용되므로 경계값 20자는 그대로 저장 가능해야 한다.
    nickname, content = validate_comment("가" * 20, "소감")
    assert nickname == "가" * 20
    assert content == "소감"


def test_comment_rejects_nickname_over_boundary():
    # 최대값을 초과하는 21자 닉네임은 자르고 저장하지 않고 안내 문구를 반환해야 한다.
    with pytest.raises(ValueError, match="20자 이내"):
        validate_comment("가" * 21, "소감")


def test_comment_preserves_script_text_as_plain_input():
    # validate_comment는 실행 가능한 HTML을 제거하지 않고 원문을 보존한다.
    # 실제 화면 표시의 HTML 해석 방지는 정적 자산과 템플릿의 책임이다.
    nickname, content = validate_comment("아림", "<script>alert('hi')</script>")
    assert nickname == "아림"
    assert content == "<script>alert('hi')</script>"


# ---------- 동네 입력 ----------

REGIONS = [
    {"id": "incheon-bupyeong", "sido": "인천광역시", "gu": "부평구"},
    {"id": "incheon-seo", "sido": "인천광역시", "gu": "서구"},
    {"id": "seoul-gangseo", "sido": "서울특별시", "gu": "강서구"},
]


@pytest.mark.parametrize("typed", ["인천광역시 부평구", "인천 부평구", "인천부평", "부평구", "부평", " 부평 ", "incheon-bupyeong"])
def test_find_region_accepts_common_names(typed):
    assert find_region(REGIONS, typed)["id"] == "incheon-bupyeong"


def test_find_region_does_not_confuse_similar_names():
    assert find_region(REGIONS, "서구")["id"] == "incheon-seo"      # '강서구'와 헷갈리지 않음
    assert find_region(REGIONS, "강서")["id"] == "seoul-gangseo"


@pytest.mark.parametrize("typed", ["대구 수성구", "부평동", "인천", "서"])
def test_find_region_returns_none_for_unsupported(typed):
    assert find_region(REGIONS, typed) is None


def test_validate_place_rejects_empty_and_too_long():
    with pytest.raises(ValueError, match="입력해 주세요"):
        validate_place("   ")
    with pytest.raises(ValueError, match="30자 이내"):
        validate_place("가" * 31)
    assert validate_place("  인천 부평구 ") == "인천 부평구"
