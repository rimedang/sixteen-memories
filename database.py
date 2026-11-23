"""SQLite 연결과 조회·저장 함수.

SQL 문은 모두 이 파일에 모아 두고, app.py는 이 함수들만 호출한다.
SQL에 값을 넣을 때는 항상 ? 자리표시자를 써서 SQL 인젝션을 막는다.
"""
import sqlite3

from config import SCHEMA_PATH


def connect(db_path):
    """DB에 연결한다. 결과 행을 dict처럼 이름으로 꺼낼 수 있게 설정한다."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn):
    """schema.sql을 실행해 테이블을 만든다. 이미 있으면 그대로 둔다."""
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))


# ---------- 지역 ----------

def get_regions(conn):
    # rowid 순서 = regions.csv에 적힌 순서 (서울 → 인천, 인구 순위 순)
    rows = conn.execute("SELECT * FROM regions ORDER BY rowid").fetchall()
    return [dict(row) for row in rows]


def get_region(conn, region_id):
    row = conn.execute("SELECT * FROM regions WHERE id = ?", (region_id,)).fetchone()
    return dict(row) if row else None


# ---------- 추억 자료 ----------

def get_memories(conn, region_id, year):
    """해당 지역에서 탐색 연도가 start_year~end_year 안에 드는 추억을 찾는다."""
    rows = conn.execute(
        """
        SELECT * FROM memories
        WHERE region_id = ? AND start_year <= ? AND ? <= end_year
        ORDER BY start_year, id
        """,
        (region_id, year, year),
    ).fetchall()
    memories = [dict(row) for row in rows if year not in skip_years(row["skip_years"])]
    for memory in memories:
        attach_photo_for_year(conn, memory, year)
    return memories


def skip_years(text):
    """'2019;2020;2021' → {2019, 2020, 2021}. 기간 중 빠진 해(예: 축제 미개최)."""
    return {int(part) for part in (text or "").split(";") if part.strip().isdigit()}


def attach_photo_for_year(conn, memory, year):
    """연도별 사진이 있으면 그 해에 맞는 사진으로 바꿔 끼운다.

    - 기본 사진(image_file)이 있는 추억(예: 해마다 열리는 축제):
      그 해 사진이 있을 때만 연도별 사진, 없으면 기본 사진.
    - 기본 사진이 없는 추억(예: 해마다 모습이 바뀌는 거리):
      '선택한 연도 이하 중 가장 최근 사진'. 사진이 2013, 2015년에 있을 때 2016년을 보면 2015년 사진.
    memory["photos"]에는 전체 사진 목록을 넣어, 화면에서 연도 버튼으로 넘겨 볼 수 있게 한다.

    기본 사진은 여러 장일 수 있다: image_file에 'a.jpg;b.jpg;c.jpg'처럼 ;로 이어 적으면
    memory["images"]에 모두 담겨 화면에 함께 보인다. (연도별 사진을 쓰는 해에는 그 사진 1장)
    """
    gallery = [part.strip() for part in (memory["image_file"] or "").split(";") if part.strip()]
    photos = [dict(row) for row in conn.execute(
        """
        SELECT year, image_file, image_source FROM memory_photos
        WHERE memory_id = ?
        ORDER BY year
        """,
        (memory["id"],),
    )]
    memory["photos"] = photos
    memory["photo_year"] = None
    if gallery:
        shown = [p for p in photos if p["year"] == year]
    else:
        shown = [p for p in photos if p["year"] <= year]
    photo = shown[-1] if shown else None
    if photo:
        gallery = [photo["image_file"]]
        memory["image_source"] = photo["image_source"] or memory["image_source"]
        memory["photo_year"] = photo["year"]
    memory["images"] = gallery
    memory["image_file"] = gallery[0] if gallery else None


def memory_exists(conn, memory_id):
    row = conn.execute("SELECT 1 FROM memories WHERE id = ?", (memory_id,)).fetchone()
    return row is not None


# ---------- 전국 공통 유행 ----------

def get_trends(conn, year):
    rows = conn.execute(
        "SELECT * FROM trends WHERE year = ? ORDER BY id", (year,)
    ).fetchall()
    return [dict(row) for row in rows]


# ---------- 댓글 ----------

def get_comments(conn, memory_id):
    rows = conn.execute(
        """
        SELECT id, nickname, content, created_at FROM comments
        WHERE memory_id = ?
        ORDER BY id
        """,
        (memory_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def get_comment_summaries(conn, memory_ids, limit):
    """추억마다 (소감 수, 최근 소감 limit개)를 구한다. 결과 화면 카드에 미리 보여줄 때 쓴다.

    최근 소감은 오래된 것 → 최근 것 순서로 돌려준다.
    """
    summaries = {}
    for memory_id in memory_ids:
        count = conn.execute(
            "SELECT COUNT(*) FROM comments WHERE memory_id = ?", (memory_id,)
        ).fetchone()[0]
        recent = conn.execute(
            """
            SELECT id, nickname, content, created_at FROM comments
            WHERE memory_id = ?
            ORDER BY id DESC LIMIT ?
            """,
            (memory_id, limit),
        ).fetchall()
        summaries[memory_id] = (count, [dict(row) for row in reversed(recent)])
    return summaries


def add_comment(conn, memory_id, nickname, content):
    cursor = conn.execute(
        "INSERT INTO comments (memory_id, nickname, content) VALUES (?, ?, ?)",
        (memory_id, nickname, content),
    )
    conn.commit()
    row = conn.execute(
        "SELECT id, nickname, content, created_at FROM comments WHERE id = ?",
        (cursor.lastrowid,),
    ).fetchone()
    return dict(row)


# ---------- 연도별 이야기 (전국 유행 공통 공간) ----------

def get_year_comments(conn, year):
    rows = conn.execute(
        """
        SELECT id, nickname, content, created_at FROM year_comments
        WHERE year = ?
        ORDER BY id
        """,
        (year,),
    ).fetchall()
    return [dict(row) for row in rows]


def add_year_comment(conn, year, nickname, content):
    cursor = conn.execute(
        "INSERT INTO year_comments (year, nickname, content) VALUES (?, ?, ?)",
        (year, nickname, content),
    )
    conn.commit()
    row = conn.execute(
        "SELECT id, nickname, content, created_at FROM year_comments WHERE id = ?",
        (cursor.lastrowid,),
    ).fetchone()
    return dict(row)
