"""입력값 검증과 연도 계산.

DB나 Flask에 의존하지 않는 순수 함수만 모아 두어 pytest로 바로 검증할 수 있다.
검증에 실패하면 ValueError를 발생시키고, 메시지는 그대로 화면에 보여준다.
"""
from config import (
    MAX_CONTENT_LENGTH,
    MAX_NICKNAME_LENGTH,
    MAX_PLACE_LENGTH,
    MAX_YEAR,
    MIN_YEAR,
    TARGET_AGE,
)

YEAR_RANGE_MESSAGE = (
    f"이용 가능한 출생연도는 {MIN_YEAR - TARGET_AGE}~{MAX_YEAR - TARGET_AGE}년이에요. "
    f"(탐색 연도 {MIN_YEAR}~{MAX_YEAR}년)"
)


def parse_birth_year(raw):
    """사용자가 입력한 출생연도 문자열을 정수로 바꾼다."""
    text = (raw or "").strip()
    if not text:
        raise ValueError("출생연도를 입력해 주세요.")
    # isdigit()은 '²'(위첨자)도 숫자로 보지만 int()는 바꾸지 못한다 → int()가 바꿀 수 있는 isdecimal() 사용
    if not text.isdecimal() or len(text) != 4:
        raise ValueError("출생연도는 숫자 4자리로 입력해 주세요. (예: 2004)")
    return int(text)


def calculate_target_year(birth_year):
    """출생연도에 16을 더해 탐색 연도를 구한다. 범위를 벗어나면 ValueError."""
    target_year = birth_year + TARGET_AGE
    check_target_year(target_year)
    return target_year


def check_target_year(target_year):
    """탐색 연도가 지원 범위(MIN_YEAR~MAX_YEAR) 안인지 확인한다."""
    if not MIN_YEAR <= target_year <= MAX_YEAR:
        raise ValueError(YEAR_RANGE_MESSAGE)


def years_ago(target_year, current_year):
    """접속 시점의 현재 연도 기준으로 몇 년 전인지 계산한다. (예: 2026, 2010 → 16)"""
    return current_year - target_year


def validate_place(raw):
    """사용자가 입력한 동네 이름을 검사하고, 앞뒤 공백을 지운 값을 돌려준다."""
    text = (raw or "").strip()
    if not text:
        raise ValueError("16살 때 살던 동네를 입력해 주세요.")
    if len(text) > MAX_PLACE_LENGTH:
        raise ValueError(f"동네 이름은 {MAX_PLACE_LENGTH}자 이내로 입력해 주세요.")
    return text


def _compact(text):
    """비교용: 공백을 모두 지운다. ('인천 부평구' → '인천부평구')"""
    return "".join((text or "").split())


def region_names(region):
    """한 지역을 가리킬 수 있는 이름들 (공백 없이).

    예) 인천광역시 부평구 → 인천광역시부평구, 인천부평구, 인천시부평구, 인천부평, 부평구, 부평, incheon-bupyeong
    '서구'처럼 '구'를 빼면 한 글자만 남는 이름은 너무 짧아 빼지 않는다.
    """
    sido, gu = region["sido"], region["gu"]
    short = sido[:2]  # 서울특별시 → 서울, 인천광역시 → 인천
    names = {region["id"], sido + gu, short + gu, short + "시" + gu, gu}
    if gu.endswith("구") and len(gu) >= 3:
        names |= {short + gu[:-1], gu[:-1]}
    return {_compact(name) for name in names}


def find_region(regions, text):
    """입력한 동네 이름에 맞는 지원 지역을 찾는다. 없거나 여러 곳에 맞으면 None (= 미지원 동네)."""
    query = _compact(text)
    matches = [region for region in regions if query in region_names(region)]
    return matches[0] if len(matches) == 1 else None


def validate_comment(nickname, content):
    """댓글의 닉네임과 내용을 검사하고, 앞뒤 공백을 지운 값을 돌려준다."""
    # API로 숫자·목록 같은 값이 직접 들어오면 .strip()에서 오류(500)가 나므로 먼저 거부한다.
    if not isinstance(nickname or "", str) or not isinstance(content or "", str):
        raise ValueError("닉네임과 내용은 글자로 입력해 주세요.")
    nickname = (nickname or "").strip()
    content = (content or "").strip()

    if not nickname:
        raise ValueError("닉네임을 입력해 주세요.")
    if len(nickname) > MAX_NICKNAME_LENGTH:
        raise ValueError(f"닉네임은 {MAX_NICKNAME_LENGTH}자 이내로 입력해 주세요.")
    if not content:
        raise ValueError("내용을 입력해 주세요.")
    if len(content) > MAX_CONTENT_LENGTH:
        raise ValueError(f"내용은 {MAX_CONTENT_LENGTH}자 이내로 입력해 주세요.")

    return nickname, content
