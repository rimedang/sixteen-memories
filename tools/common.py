"""자료 준비 도구(TMDB 포스터, IGDB 게임 표지)가 함께 쓰는 코드.

- .env 파일에서 API 키 읽기
- data/trends.csv 읽기·쓰기
- 이미지 내려받기
- 검색 결과 중 연도가 가장 가까운 작품 고르기
"""
import csv
import os
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / ".env"
TRENDS_CSV = ROOT / "data" / "trends.csv"
TREND_IMAGE_DIR = ROOT / "static" / "images" / "trends"

# 도구가 trends.csv에 기록하는 열 (없으면 새로 만든다)
TOOL_COLUMNS = ("image_file", "image_source", "search_title")


def read_env_file(path):
    """.env 파일의 '이름=값' 줄을 dict로 읽는다. 파일이 없으면 빈 dict."""
    values = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        values[name.strip()] = value.strip().strip('"').strip("'")
    return values


def get_secret(name):
    """터미널 환경변수를 먼저 보고, 없으면 .env 파일에서 값을 찾는다."""
    return (os.environ.get(name) or read_env_file(ENV_FILE).get(name, "")).strip()


def load_trends():
    """trends.csv를 읽어 (열 이름 목록, 행 목록)을 돌려준다."""
    with open(TRENDS_CSV, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames)
        rows = list(reader)
    for column in TOOL_COLUMNS:
        if column not in fieldnames:
            fieldnames.append(column)
    return fieldnames, rows


def save_trends(fieldnames, rows):
    # utf-8-sig: 엑셀에서 열어도 한글이 깨지지 않게 저장
    with open(TRENDS_CSV, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def trend_image_path(row):
    """유행 이미지를 저장할 위치를 연도 폴더로 정한다.

    (내려받을 파일 경로, trends.csv의 image_file에 적을 값)을 돌려준다.
    예: id 2013-movie-1, year 2013 → static/images/trends/2013/2013-movie-1.jpg, "trends/2013/2013-movie-1.jpg"
    """
    name = f"{row['id']}.jpg"
    return TREND_IMAGE_DIR / row["year"] / name, f"trends/{row['year']}/{name}"


def download(url, target, headers=None):
    target.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(request, timeout=30) as res:
        target.write_bytes(res.read())


def choose_closest_year(candidates, year, year_of):
    """후보 중 연도가 가장 가까운 것을 고른다. 차이가 같으면 앞쪽(검색 관련도 높은) 결과.

    year_of: 후보 하나를 받아 연도(int 또는 None)를 돌려주는 함수
    """
    if not candidates:
        return None

    def year_gap(item):
        found = year_of(item)
        return abs(found - year) if found else 99

    return min(candidates, key=year_gap)


def search_text(row):
    """검색에 쓸 제목: search_title(영문 등)이 있으면 그것, 없으면 title."""
    return (row.get("search_title") or row["title"]).strip()


def year_warning(found_year, year):
    if found_year is None or abs(found_year - year) > 1:
        return "  ← 연도 차이가 큼, 맞는 작품인지 확인 필요"
    return ""
