"""TMDB에서 전국 유행(영화·TV방송) 포스터를 내려받아 trends.csv에 연결하는 도구.

웹사이트(app.py)와는 별개로, 자료를 준비할 때 한 번 실행한다.

[직접 수행] 준비
  1. https://www.themoviedb.org 가입 → 프로필 → 설정 → API 에서 API 키(v3) 발급
  2. 프로젝트 폴더의 .env 파일에 한 줄 저장 (.gitignore로 GitHub에 올라가지 않음)
       TMDB_API_KEY=발급받은키
     또는 PowerShell에서: $env:TMDB_API_KEY = "발급받은키"

실행
  python tools/fetch_tmdb_posters.py --dry-run   # 어떤 작품이 찾아지는지 확인만
  python tools/fetch_tmdb_posters.py             # 포스터 저장 + trends.csv에 파일 이름 기록
  python tools/fetch_tmdb_posters.py --overwrite # 이미 포스터가 있는 행도 다시 받기
그다음 python seed.py 를 실행하면 화면에 반영된다.
"""
import argparse
import csv
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / ".env"
TRENDS_CSV = ROOT / "data" / "trends.csv"
POSTER_DIR = ROOT / "static" / "images" / "trends"

API_BASE = "https://api.themoviedb.org/3"
IMAGE_BASE = "https://image.tmdb.org/t/p/w342"  # 가로 342px 크기의 포스터

# trends.csv의 분류 → TMDB 검색 종류 (노래는 TMDB에 없으므로 제외)
CATEGORY_TO_MEDIA = {"영화": "movie", "TV방송": "tv"}


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


def get_api_key():
    """터미널 환경변수를 먼저 보고, 없으면 .env 파일에서 키를 찾는다."""
    return (os.environ.get("TMDB_API_KEY")
            or read_env_file(ENV_FILE).get("TMDB_API_KEY", "")).strip()


def release_year(item):
    """TMDB 검색 결과에서 개봉(방영 시작) 연도를 꺼낸다. 없으면 None."""
    date = item.get("release_date") or item.get("first_air_date") or ""
    return int(date[:4]) if date[:4].isdigit() else None


def choose_best(results, year):
    """포스터가 있는 결과 중 연도가 가장 가까운 작품을 고른다.

    연도 차이가 같으면 TMDB가 먼저 보여준(더 관련 있는) 결과를 고른다.
    """
    candidates = [item for item in results if item.get("poster_path")]
    if not candidates:
        return None

    def year_gap(item):
        found = release_year(item)
        return abs(found - year) if found else 99

    return min(candidates, key=year_gap)


def search(media, title, api_key):
    params = urllib.parse.urlencode(
        {"api_key": api_key, "query": title, "language": "ko-KR"}
    )
    with urllib.request.urlopen(f"{API_BASE}/search/{media}?{params}", timeout=15) as res:
        return json.load(res).get("results", [])


def download(poster_path, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(IMAGE_BASE + poster_path, timeout=30) as res:
        target.write_bytes(res.read())


def main():
    parser = argparse.ArgumentParser(description="TMDB 포스터 내려받기")
    parser.add_argument("--dry-run", action="store_true", help="검색 결과만 보여주고 저장하지 않음")
    parser.add_argument("--overwrite", action="store_true", help="이미 포스터가 있는 행도 다시 받기")
    args = parser.parse_args()

    api_key = get_api_key()
    if not api_key:
        print("TMDB_API_KEY가 없습니다. 프로젝트 폴더의 .env 파일에 "
              "'TMDB_API_KEY=발급받은키' 한 줄을 적고 저장하세요.")
        return 1

    with open(TRENDS_CSV, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames)
        rows = list(reader)
    for column in ("image_file", "image_source"):
        if column not in fieldnames:
            fieldnames.append(column)

    for row in rows:
        media = CATEGORY_TO_MEDIA.get(row["category"])
        if media is None or (row.get("image_file") and not args.overwrite):
            continue

        best = choose_best(search(media, row["title"], api_key), int(row["year"]))
        if best is None:
            print(f"[못 찾음] {row['id']} {row['title']}")
            continue

        found_title = best.get("title") or best.get("name")
        found_year = release_year(best)
        warning = ""
        if found_year is None or abs(found_year - int(row["year"])) > 1:
            warning = "  ← 연도 차이가 큼, 맞는 작품인지 확인 필요"
        print(f"[찾음] {row['id']} {row['title']} → {found_title} ({found_year}){warning}")

        if not args.dry_run:
            relative = f"trends/{row['id']}.jpg"
            download(best["poster_path"], POSTER_DIR / f"{row['id']}.jpg")
            row["image_file"] = relative
            row["image_source"] = "TMDB"

    if not args.dry_run:
        with open(TRENDS_CSV, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        print("trends.csv에 포스터 파일 이름을 기록했습니다. 이제 python seed.py 를 실행하세요.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
