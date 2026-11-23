"""프로젝트 전체에서 함께 쓰는 설정값.

숫자를 코드 곳곳에 직접 쓰지 않고 여기 모아 두면,
범위를 바꿀 때 이 파일 하나만 고치면 된다.
"""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# 기준 나이: 출생연도 + 16 = 탐색 연도
TARGET_AGE = 16

# 탐색 연도 범위 (계획서 2010~2023 → 2013~2022로 축소, docs/plan_changes.md 참고)
MIN_YEAR = 2013
MAX_YEAR = 2022

# 동네 입력 길이 제한 (미지원 동네도 결과 화면에 그대로 보여주므로 너무 긴 입력은 막는다)
MAX_PLACE_LENGTH = 30

# 결과 화면 추억 카드에 미리 보여줄 최근 소감 수
COMMENT_PREVIEW_COUNT = 2

# 댓글 길이 제한
MAX_NICKNAME_LENGTH = 20
MAX_CONTENT_LENGTH = 200

# 전국 공통 유행 카테고리 (화면에 보여줄 순서)
# 계획서 "음식·패션·놀이·대중문화" → 공식 통계로 확인 가능한 간식·대중문화·모바일·놀이 6분야(간식·노래·영화·TV방송·앱·게임·놀이)로 변경
TREND_CATEGORIES = ["간식", "노래", "영화", "TV방송", "앱·게임", "놀이"]

# 파일 위치
DATABASE_PATH = BASE_DIR / "instance" / "app.db"
DATA_DIR = BASE_DIR / "data"
SCHEMA_PATH = BASE_DIR / "schema.sql"
