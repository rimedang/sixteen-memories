"""IGDB에서 전국 유행 '게임'의 표지 이미지를 내려받아 trends.csv에 연결하는 도구.

[직접 수행] 준비
  1. https://dev.twitch.tv/console 에서 애플리케이션 등록
     (OAuth 리디렉션 URL: http://localhost, 분류: Application Integration, 클라이언트 유형: 기밀)
  2. Client ID 확인, "새 비밀" 버튼으로 Client Secret 발급
  3. 프로젝트 폴더의 .env 파일에 두 줄 추가 (.gitignore로 GitHub에 올라가지 않음)
       IGDB_CLIENT_ID=발급받은ID
       IGDB_CLIENT_SECRET=발급받은비밀

실행
  python tools/fetch_igdb_covers.py --dry-run   # 어떤 게임이 찾아지는지 확인만
  python tools/fetch_igdb_covers.py             # 표지 저장 + trends.csv에 파일 이름 기록
그다음 python seed.py 를 실행하면 화면에 반영된다.

'앱·게임' 분류에는 카카오톡 같은 일반 앱도 섞여 있어서, 게임만 골라 검색하도록
trends.csv의 search_title 칸에 영문 제목이 적힌 행만 IGDB에서 찾는다.
(예: 클래시 오브 클랜 → search_title에 Clash of Clans)
"""
import argparse
import json
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
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

TOKEN_URL = "https://id.twitch.tv/oauth2/token"
GAMES_URL = "https://api.igdb.com/v4/games"
COVER_URL = "https://images.igdb.com/igdb/image/upload/t_cover_big/{image_id}.jpg"
CATEGORY = "앱·게임"


def needs_cover(row, overwrite=False):
    """IGDB에서 표지를 찾을 행인지 판단한다: 앱·게임 + 영문 검색어 있음 + (표지 없음 또는 덮어쓰기)."""
    if row["category"] != CATEGORY or not (row.get("search_title") or "").strip():
        return False
    return overwrite or not row.get("image_file")


def clean_title(title):
    """검색이 잘 되도록 ' for Kakao' 같은 국내 플랫폼 표기를 뗀다."""
    return title.replace(" for Kakao", "").replace("for Kakao", "").strip()


def release_year(game):
    """IGDB의 first_release_date(유닉스 시간, 초)에서 연도를 꺼낸다."""
    timestamp = game.get("first_release_date")
    if not timestamp:
        return None
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).year


def choose_best(games, year, title=""):
    """표지가 있는 게임 중 고른다.

    제목이 정확히 같은 게임이 있으면 그중에서만 고른다. 예) "Genshin Impact" 검색 시
    같은 해에 나온 확장팩 "Genshin Impact: A New Star Approaches"보다 본편을 우선한다.
    그다음 출시 연도가 가장 가까운 것을 고른다.
    """
    with_cover = [g for g in games if (g.get("cover") or {}).get("image_id")]
    exact = [g for g in with_cover if g.get("name", "").casefold() == title.casefold()]
    return choose_closest_year(exact or with_cover, year, release_year)


def get_access_token(client_id, client_secret):
    data = urllib.parse.urlencode({
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "client_credentials",
    }).encode()
    with urllib.request.urlopen(urllib.request.Request(TOKEN_URL, data=data), timeout=15) as res:
        return json.load(res)["access_token"]


def query_games(body, client_id, token):
    """IGDB에 질의문(body)을 보내고 게임 목록을 받는다."""
    request = urllib.request.Request(
        GAMES_URL,
        data=body.encode("utf-8"),
        headers={"Client-ID": client_id, "Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(request, timeout=15) as res:
        return json.load(res)


def search(title, client_id, token):
    """제목으로 검색한다. 결과에 제목이 정확히 같은 게임이 없으면 이름으로 한 번 더 찾는다.

    예) "Genshin Impact" 검색 결과에는 확장팩만 나오고 본편이 빠져 있어서,
        where name = "Genshin Impact" 로 본편을 따로 찾아 함께 돌려준다.
    """
    safe_title = title.replace('"', "")
    fields = "fields name,first_release_date,cover.image_id;"
    games = query_games(f'search "{safe_title}"; {fields} limit 30;', client_id, token)
    if not any(g.get("name", "").casefold() == safe_title.casefold() for g in games):
        games += query_games(f'{fields} where name ~ "{safe_title}"; limit 10;', client_id, token)
    return games


def main():
    parser = argparse.ArgumentParser(description="IGDB 게임 표지 내려받기")
    parser.add_argument("--dry-run", action="store_true", help="검색 결과만 보여주고 저장하지 않음")
    parser.add_argument("--overwrite", action="store_true", help="이미 표지가 있는 행도 다시 받기")
    args = parser.parse_args()

    client_id = get_secret("IGDB_CLIENT_ID")
    client_secret = get_secret("IGDB_CLIENT_SECRET")
    if not client_id or not client_secret:
        print("IGDB_CLIENT_ID 또는 IGDB_CLIENT_SECRET이 없습니다. .env 파일에 두 줄을 적고 저장하세요.")
        return 1
    token = get_access_token(client_id, client_secret)

    fieldnames, rows = load_trends()
    for row in rows:
        if not needs_cover(row, args.overwrite):
            continue

        year = int(row["year"])
        query = clean_title(search_text(row))
        best = choose_best(search(query, client_id, token), year, query)
        if best is None:
            print(f"[못 찾음] {row['id']} {row['title']}  → search_title의 영문 제목을 확인해 보세요")
            continue

        found_year = release_year(best)
        print(f"[찾음] {row['id']} {row['title']} → {best['name']} ({found_year})"
              f"{year_warning(found_year, year)}")

        if not args.dry_run:
            url = COVER_URL.format(image_id=best["cover"]["image_id"])
            target, image_file = trend_image_path(row)
            download(url, target)
            row["image_file"] = image_file
            row["image_source"] = "IGDB"

    if not args.dry_run:
        save_trends(fieldnames, rows)
        print("trends.csv에 표지 파일 이름을 기록했습니다. 이제 python seed.py 를 실행하세요.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
