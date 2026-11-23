-- 「열여섯, 우리 동네」 데이터베이스 구조
-- 지역 추억 자료, 전국 공통 유행, 사용자 댓글을 서로 다른 테이블로 관리한다.

-- 지원 지역 (data/regions.csv)
CREATE TABLE IF NOT EXISTS regions (
    id           TEXT PRIMARY KEY,      -- 예: seoul-nowon
    sido         TEXT NOT NULL,         -- 예: 서울특별시
    gu           TEXT NOT NULL,         -- 예: 노원구
    name_note    TEXT                   -- 예: 2016년 당시 이름은 남구
);

-- 지역 추억 자료 (data/memories.csv)
-- start_year~end_year 사이의 탐색 연도에 표시된다. 한 해짜리 자료는 두 값을 같게 넣는다.
CREATE TABLE IF NOT EXISTS memories (
    id            TEXT PRIMARY KEY,     -- 예: nowon-01 (CSV에서 정한 고정 번호)
    region_id     TEXT NOT NULL REFERENCES regions(id),
    title         TEXT NOT NULL,
    description   TEXT NOT NULL,
    category      TEXT NOT NULL,
    start_year    INTEGER NOT NULL,
    end_year      INTEGER NOT NULL,
    skip_years    TEXT,                 -- 선택: 기간 중 빠진 해 (예: "2019;2020;2021" 축제 미개최)
    source_title  TEXT,                 -- 선택: 확인한 기사·자료 이름
    source_url    TEXT,                 -- 선택: 확인한 기사·자료 주소
    image_file    TEXT,                 -- static/images/ 기준 경로. 여러 장이면 ;로 이어 적음 (예: memories/gyeyang/gyeyang-7-1.jpg;memories/gyeyang/gyeyang-7-2.jpg)
    image_source  TEXT,
    image_license TEXT
);

-- 전국 공통 유행 (data/trends.csv)
CREATE TABLE IF NOT EXISTS trends (
    id           TEXT PRIMARY KEY,      -- 예: 2013-movie-1
    year         INTEGER NOT NULL,
    category     TEXT NOT NULL,         -- 간식 / 노래 / 영화 / TV방송 / 앱·게임 / 놀이
    title        TEXT NOT NULL,
    description  TEXT,                  -- 선택: 한 줄 설명
    source_title TEXT,                  -- 선택
    source_url   TEXT,                  -- 선택
    image_file   TEXT,                  -- 선택: static/images/ 기준 경로 (예: trends/2013/2013-movie-1.jpg)
    image_source TEXT                   -- 선택: 예) TMDB
);

-- 추억의 연도별 사진 (data/memory_photos.csv)
-- 같은 장소를 해마다 찍은 사진을 한 추억에 연결한다. 추억을 연도별로 나누지 않으므로
-- 댓글은 한 곳에 모인다. 결과 화면은 "선택한 연도 이하 중 가장 최근 사진"을 보여준다.
CREATE TABLE IF NOT EXISTS memory_photos (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    memory_id    TEXT NOT NULL REFERENCES memories(id),
    year         INTEGER NOT NULL,      -- 사진이 보여주는 연도 (예: 2015 → 2015~2016년에 표시)
    image_file   TEXT NOT NULL,         -- static/images/ 기준 경로 (예: memories/bupyeong/bupyeong-5-2015.jpg)
    image_source TEXT
);

CREATE INDEX IF NOT EXISTS idx_photos_memory ON memory_photos(memory_id, year);

-- 사용자 댓글: memory_id로 특정 추억에 연결된다.
CREATE TABLE IF NOT EXISTS comments (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    memory_id  TEXT NOT NULL REFERENCES memories(id),
    nickname   TEXT NOT NULL,
    content    TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_comments_memory ON comments(memory_id);

-- 연도별 이야기: 전국 유행처럼 지역과 상관없는 그 해의 추억을 나누는 공통 공간.
-- 지역 추억 댓글(comments)과 분리해 저장한다.
CREATE TABLE IF NOT EXISTS year_comments (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    year       INTEGER NOT NULL,
    nickname   TEXT NOT NULL,
    content    TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_year_comments_year ON year_comments(year);
