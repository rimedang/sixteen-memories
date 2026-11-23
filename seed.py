"""조사한 CSV 파일을 DB에 넣는 스크립트.

실행: python seed.py

- data/regions.csv, data/memories.csv, data/trends.csv, data/memory_photos.csv를 읽는다.
- 필수 칸이 비었거나 연도·지역·분류가 잘못된 행은 DB에 넣지 않고 경고를 출력한다.
  (출처와 유행 설명은 선택 항목)
- 같은 id의 행은 새 내용으로 덮어쓴다. 사용자 댓글(comments)은 지우지 않는다.
"""
import csv
import sys

from config import DATA_DIR, DATABASE_PATH, MAX_YEAR, MIN_YEAR, TREND_CATEGORIES
from database import connect, init_db


def read_csv(path):
    """CSV를 읽어 dict 목록으로 돌려준다. 파일이 없으면 빈 목록."""
    if not path.exists():
        return []
    # utf-8-sig: 엑셀에서 저장한 CSV 앞에 붙는 BOM 문자를 없애 준다.
    with open(path, encoding="utf-8-sig", newline="") as f:
        return [
            {key.strip(): (value or "").strip() for key, value in row.items() if key}
            for row in csv.DictReader(f)
        ]


def check_memory_row(row, region_ids):
    """추억 자료 한 줄을 검사한다. 문제가 있으면 이유를 담은 문자열, 없으면 None."""
    # 설명(description)과 출처(source_title, source_url)는 선택 항목이라 검사하지 않는다.
    for field in ("id", "region_id", "title", "category", "start_year", "end_year"):
        if not row.get(field):
            return f"'{field}' 값이 비어 있음"
    if row["region_id"] not in region_ids:
        return f"지원하지 않는 지역 '{row['region_id']}'"
    if not (row["start_year"].isdigit() and row["end_year"].isdigit()):
        return "start_year, end_year는 숫자여야 함"
    start, end = int(row["start_year"]), int(row["end_year"])
    if start > end:
        return "start_year가 end_year보다 큼"
    if end < MIN_YEAR or start > MAX_YEAR:
        return f"탐색 연도 범위({MIN_YEAR}~{MAX_YEAR})와 겹치지 않음"
    if not all(y.isdigit() for y in parse_skip_years_text(row.get("skip_years", ""))):
        return "skip_years는 '2019;2020'처럼 연도를 ;로 구분해야 함"
    return None


def parse_skip_years_text(text):
    return [part.strip() for part in (text or "").split(";") if part.strip()]


def check_trend_row(row):
    """전국 유행 한 줄을 검사한다. 문제가 있으면 이유, 없으면 None."""
    # 설명(description)과 출처는 선택 항목이다.
    for field in ("id", "year", "category", "title"):
        if not row.get(field):
            return f"'{field}' 값이 비어 있음"
    if not row["year"].isdigit() or not MIN_YEAR <= int(row["year"]) <= MAX_YEAR:
        return f"year는 {MIN_YEAR}~{MAX_YEAR} 사이 숫자여야 함"
    if row["category"] not in TREND_CATEGORIES:
        return f"category는 {TREND_CATEGORIES} 중 하나여야 함"
    return None


def check_photo_row(row, memory_ids):
    """연도별 사진 한 줄을 검사한다. 문제가 있으면 이유, 없으면 None."""
    for field in ("memory_id", "year", "image_file"):
        if not row.get(field):
            return f"'{field}' 값이 비어 있음"
    if row["memory_id"] not in memory_ids:
        return f"memories.csv에 없는 추억 '{row['memory_id']}'"
    if not row["year"].isdigit() or int(row["year"]) > MAX_YEAR:
        return f"year는 {MAX_YEAR} 이하 숫자여야 함"
    return None


def seed(conn, data_dir=DATA_DIR):
    """CSV를 DB에 넣고, 넣은 개수와 건너뛴 행 목록을 돌려준다."""
    # 전국 유행은 댓글이 연결되지 않으므로 테이블을 지우고 다시 만든다.
    # → CSV에서 지우거나 id를 바꾼 행이 남지 않고, 열이 추가돼도 자동 반영된다.
    # 연도별 사진도 댓글이 연결되지 않으므로 같은 방식으로 다시 만든다.
    conn.execute("DROP TABLE IF EXISTS trends")
    conn.execute("DROP TABLE IF EXISTS memory_photos")
    init_db(conn)
    skipped = []

    regions = read_csv(data_dir / "regions.csv")
    for row in regions:
        conn.execute(
            "INSERT OR REPLACE INTO regions (id, sido, gu, name_note) VALUES (?, ?, ?, ?)",
            (row["region_id"], row["sido"], row["gu"], row.get("gu_name_note", "")),
        )
    region_ids = {row["region_id"] for row in regions}

    # regions.csv에서 뺀 지역을 DB에서도 지운다. 단, 추억이 연결된 지역은 남긴다
    # (추억·댓글이 사라지지 않게). 예) 서울 10곳 → 5곳으로 축소
    placeholders = ",".join("?" * len(region_ids)) or "''"
    conn.execute(
        f"""DELETE FROM regions
            WHERE id NOT IN ({placeholders})
              AND id NOT IN (SELECT region_id FROM memories)""",
        tuple(region_ids),
    )

    memory_count = 0
    for line_no, row in enumerate(read_csv(data_dir / "memories.csv"), start=2):
        problem = check_memory_row(row, region_ids)
        if problem:
            skipped.append(f"memories.csv {line_no}행: {problem}")
            continue
        conn.execute(
            """INSERT OR REPLACE INTO memories
               (id, region_id, title, description, category, start_year, end_year, skip_years,
                source_title, source_url, image_file, image_source, image_license)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (row["id"], row["region_id"], row["title"], row.get("description", ""),
             row["category"], int(row["start_year"]), int(row["end_year"]),
             ";".join(parse_skip_years_text(row.get("skip_years", ""))),
             row.get("source_title", ""), row.get("source_url", ""), row.get("image_file", ""),
             row.get("image_source", ""), row.get("image_license", "")),
        )
        memory_count += 1

    trend_count = 0
    for line_no, row in enumerate(read_csv(data_dir / "trends.csv"), start=2):
        problem = check_trend_row(row)
        if problem:
            skipped.append(f"trends.csv {line_no}행: {problem}")
            continue
        conn.execute(
            """INSERT OR REPLACE INTO trends
               (id, year, category, title, description, source_title, source_url,
                image_file, image_source)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (row["id"], int(row["year"]), row["category"], row["title"],
             row.get("description", ""), row.get("source_title", ""),
             row.get("source_url", ""), row.get("image_file", ""),
             row.get("image_source", "")),
        )
        trend_count += 1

    memory_ids = {r[0] for r in conn.execute("SELECT id FROM memories")}
    photo_count = 0
    for line_no, row in enumerate(read_csv(data_dir / "memory_photos.csv"), start=2):
        problem = check_photo_row(row, memory_ids)
        if problem:
            skipped.append(f"memory_photos.csv {line_no}행: {problem}")
            continue
        conn.execute(
            "INSERT INTO memory_photos (memory_id, year, image_file, image_source) VALUES (?, ?, ?, ?)",
            (row["memory_id"], int(row["year"]), row["image_file"], row.get("image_source", "")),
        )
        photo_count += 1

    conn.commit()
    return {
        "regions": len(regions),
        "memories": memory_count,
        "trends": trend_count,
        "photos": photo_count,
        "skipped": skipped,
    }


if __name__ == "__main__":
    DATABASE_PATH.parent.mkdir(exist_ok=True)
    connection = connect(DATABASE_PATH)
    result = seed(connection)
    connection.close()

    print(f"지역 {result['regions']}곳, 추억 {result['memories']}건, "
          f"전국 유행 {result['trends']}건, 연도별 사진 {result['photos']}장을 DB에 넣었습니다.")
    for message in result["skipped"]:
        print("  [건너뜀]", message)
    sys.exit(0)
