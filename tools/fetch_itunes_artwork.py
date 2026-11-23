"""iTunes Search API에서 전국 유행 '노래'의 앨범 커버를 내려받아 trends.csv에 연결하는 도구.

iTunes Search API는 API 키가 필요 없다.

실행
  python tools/fetch_itunes_artwork.py --dry-run   # 어떤 곡이 찾아지는지 확인만
  python tools/fetch_itunes_artwork.py             # 커버 저장 + trends.csv에 파일 이름 기록
그다음 python seed.py 를 실행하면 화면에 반영된다.

검색어는 trends.csv의 search_title 칸(예: "밤편지 아이유")을 쓰고, 없으면 곡 제목을 쓴다.

주의 (실행하며 확인한 점)
- 한국(KR) 스토어는 음악 검색 결과가 0개라서 미국(US) 스토어로 검색한다.
- US 스토어는 곡명을 영어로 돌려준다 (밤편지 → Through the Night). 그래서 곡명 일치 대신
  "곡명+가수" 검색 순위를 믿고, 노래방·연주곡·라이브 등 원곡이 아닌 버전만 걸러낸다.
- 요청을 빠르게 많이 보내면 403 오류가 나므로 곡마다 4초씩 쉬고, 403이면 60초 후 한 번 더 시도한다.
"""
import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # tools.common을 찾기 위해

from tools.common import (  # noqa: E402
    choose_closest_year,
    download,
    load_trends,
    save_trends,
    search_text,
    year_warning,
    trend_image_path,
)

SEARCH_URL = "https://itunes.apple.com/search"
CATEGORY = "노래"
COUNTRY = "US"   # KR 스토어는 음악 검색 결과가 없음
WAIT_SECONDS = 4  # 요청 제한(403) 방지
RETRY_WAIT_SECONDS = 60


def normalize(text):
    """비교용 문자열: 괄호 앞부분만, 공백·기호를 빼고 소문자로. ("눈, 코, 입" → "눈코입")"""
    core = text.split("(")[0]
    return re.sub(r"[\W_]+", "", core).casefold()


def release_year(track):
    date = track.get("releaseDate", "")
    return int(date[:4]) if date[:4].isdigit() else None


# 원곡이 아닌 버전을 걸러내는 단어 (실제로 노래방·연주곡·오르골 버전이 먼저 잡혔음)
# 단어 단위로 비교한다 ("alive"의 live, "against"의 inst를 잘못 걸러내지 않도록)
NOT_ORIGINAL = re.compile(
    r"\b(karaoke|inst\.?|instrumental|cover|live|music box|japanese ver\w*|remix|"
    r"originally performed|piano|acoustic|mr)\b"
)


def is_original(track):
    text = f"{track.get('trackName', '')} {track.get('collectionName', '')}".casefold()
    return NOT_ORIGINAL.search(text) is None


def choose_best(tracks, title, year):
    """"곡명+가수" 검색 결과 중 원곡으로 보이는 첫 번째 곡을 고른다.

    US 스토어는 곡명을 영어로 돌려주므로(밤편지 → Through the Night) 곡명 일치 대신
    검색 순위를 믿고, 노래방·연주곡·라이브 같은 다른 버전만 걸러낸다.
    """
    for track in tracks:
        if track.get("artworkUrl100") and is_original(track):
            return track
    return None


def big_artwork(url):
    """artworkUrl100(100×100)을 600×600 크기 주소로 바꾼다."""
    return url.replace("100x100bb", "600x600bb")


def search(term):
    params = urllib.parse.urlencode(
        {"term": term, "country": COUNTRY, "media": "music", "entity": "song", "limit": 25}
    )
    with urllib.request.urlopen(f"{SEARCH_URL}?{params}", timeout=15) as res:
        return json.load(res).get("results", [])


def main():
    parser = argparse.ArgumentParser(description="iTunes 앨범 커버 내려받기")
    parser.add_argument("--dry-run", action="store_true", help="검색 결과만 보여주고 저장하지 않음")
    parser.add_argument("--overwrite", action="store_true", help="이미 커버가 있는 행도 다시 받기")
    args = parser.parse_args()

    fieldnames, rows = load_trends()
    for row in rows:
        if row["category"] != CATEGORY or (row.get("image_file") and not args.overwrite):
            continue

        year = int(row["year"])
        time.sleep(WAIT_SECONDS)
        try:
            tracks = search(search_text(row))
        except urllib.error.HTTPError as error:
            if error.code != 403:
                raise
            print(f"[대기] 요청 제한(403) → {RETRY_WAIT_SECONDS}초 쉬고 다시 시도")
            time.sleep(RETRY_WAIT_SECONDS)
            try:
                tracks = search(search_text(row))
            except urllib.error.HTTPError:
                print(f"[오류] {row['id']} {row['title']} → 요청 제한, 나중에 다시 실행하세요")
                continue
        best = choose_best(tracks, row["title"], year)
        if best is None:
            print(f"[못 찾음] {row['id']} {row['title']}  → search_title을 바꿔 보세요")
            continue

        found_year = release_year(best)
        print(f"[찾음] {row['id']} {row['title']} → {best['trackName']} / {best['artistName']}"
              f" ({found_year}){year_warning(found_year, year)}")

        if not args.dry_run:
            target, image_file = trend_image_path(row)
            download(big_artwork(best["artworkUrl100"]), target)
            row["image_file"] = image_file
            row["image_source"] = "Apple Music"

    if not args.dry_run:
        save_trends(fieldnames, rows)
        print("trends.csv에 앨범 커버 파일 이름을 기록했습니다. 이제 python seed.py 를 실행하세요.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
