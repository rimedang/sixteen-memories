"""TMDB에서 전국 유행(영화·TV방송) 포스터를 내려받아 trends.csv에 연결하는 도구.

웹사이트(app.py)와는 별개로, 자료를 준비할 때 한 번 실행한다.

[직접 수행] 준비
  1. https://www.themoviedb.org 가입 → 프로필 → 설정 → API 에서 API 키(v3) 발급
  2. 프로젝트 폴더의 .env 파일에 한 줄 저장 (.gitignore로 GitHub에 올라가지 않음)
       TMDB_API_KEY=발급받은키

실행
  python tools/fetch_tmdb_posters.py --dry-run   # 어떤 작품이 찾아지는지 확인만
  python tools/fetch_tmdb_posters.py             # 포스터 저장 + trends.csv에 파일 이름 기록
  python tools/fetch_tmdb_posters.py --overwrite # 이미 포스터가 있는 행도 다시 받기
그다음 python seed.py 를 실행하면 화면에 반영된다.
"""
import argparse
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # tools.common을 찾기 위해

from tools.common import (  # noqa: E402
    choose_closest_year,
    download,
    get_secret,
    load_trends,
    save_trends,
    search_text,
    year_warning,
    trend_image_path,
)

API_BASE = "https://api.themoviedb.org/3"
IMAGE_BASE = "https://image.tmdb.org/t/p/w342"  # 가로 342px 크기의 포스터

# trends.csv의 분류 → TMDB 검색 종류
CATEGORY_TO_MEDIA = {"영화": "movie", "TV방송": "tv"}


def release_year(item):
    """TMDB 검색 결과에서 개봉(방영 시작) 연도를 꺼낸다. 없으면 None."""
    date = item.get("release_date") or item.get("first_air_date") or ""
    return int(date[:4]) if date[:4].isdigit() else None


def choose_best(results, year):
    """포스터가 있는 결과 중 연도가 가장 가까운 작품을 고른다."""
    with_poster = [item for item in results if item.get("poster_path")]
    return choose_closest_year(with_poster, year, release_year)


def search(media, title, api_key):
    params = urllib.parse.urlencode({"api_key": api_key, "query": title, "language": "ko-KR"})
    with urllib.request.urlopen(f"{API_BASE}/search/{media}?{params}", timeout=15) as res:
        return json.load(res).get("results", [])


def main():
    parser = argparse.ArgumentParser(description="TMDB 포스터 내려받기")
    parser.add_argument("--dry-run", action="store_true", help="검색 결과만 보여주고 저장하지 않음")
    parser.add_argument("--overwrite", action="store_true", help="이미 포스터가 있는 행도 다시 받기")
    args = parser.parse_args()

    api_key = get_secret("TMDB_API_KEY")
    if not api_key:
        print("TMDB_API_KEY가 없습니다. 프로젝트 폴더의 .env 파일에 "
              "'TMDB_API_KEY=발급받은키' 한 줄을 적고 저장하세요.")
        return 1

    fieldnames, rows = load_trends()
    for row in rows:
        media = CATEGORY_TO_MEDIA.get(row["category"])
        if media is None or (row.get("image_file") and not args.overwrite):
            continue

        year = int(row["year"])
        best = choose_best(search(media, search_text(row), api_key), year)
        if best is None:
            print(f"[못 찾음] {row['id']} {row['title']}")
            continue

        found_year = release_year(best)
        print(f"[찾음] {row['id']} {row['title']} → "
              f"{best.get('title') or best.get('name')} ({found_year}){year_warning(found_year, year)}")

        if not args.dry_run:
            target, image_file = trend_image_path(row)
            download(IMAGE_BASE + best["poster_path"], target)
            row["image_file"] = image_file
            row["image_source"] = "TMDB"

    if not args.dry_run:
        save_trends(fieldnames, rows)
        print("trends.csv에 포스터 파일 이름을 기록했습니다. 이제 python seed.py 를 실행하세요.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
