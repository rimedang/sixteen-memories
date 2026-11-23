"""「열여섯, 우리 동네」 Flask 서버.

실행: python app.py  → 브라우저에서 http://127.0.0.1:5000 접속

화면
  /         동네(자동완성)·출생연도 입력
  /search   입력 검증 후 결과 주소로 이동
  /result   결과 화면 (공유 링크: /result?region=지역&year=탐색연도)
            region에는 지원 지역 id(예: incheon-bupyeong) 또는 사용자가 입력한 동네 이름이 온다.
            미지원 동네면 "준비 중" 안내와 함께 그해 전국 유행·연도별 이야기를 보여준다.
API (JavaScript가 호출)
  GET  /api/memories/<추억id>/comments   댓글 목록
  POST /api/memories/<추억id>/comments   댓글 저장
  GET  /api/years/<연도>/comments         연도별 이야기 목록 (전국 유행 공통 공간)
  POST /api/years/<연도>/comments         연도별 이야기 저장
"""
from datetime import date

from flask import Flask, g, jsonify, redirect, render_template, request, url_for

import database
from config import (
    COMMENT_PREVIEW_COUNT,
    DATABASE_PATH,
    MAX_CONTENT_LENGTH,
    MAX_NICKNAME_LENGTH,
    MAX_PLACE_LENGTH,
    MAX_YEAR,
    MIN_YEAR,
    TREND_CATEGORIES,
)
from validators import (
    calculate_target_year,
    check_target_year,
    find_region,
    parse_birth_year,
    validate_comment,
    validate_place,
    years_ago,
)

UNSUPPORTED_REGION_MESSAGE = "아직 준비 중인 동네예요. 개발자에게 추가를 요청해 주세요."


def create_app(db_path=DATABASE_PATH, current_year=None):
    """Flask 앱을 만든다. 테스트에서는 임시 DB 경로와 현재 연도를 넘겨 쓴다."""
    app = Flask(__name__)
    app.config["DB_PATH"] = str(db_path)
    app.config["CURRENT_YEAR"] = current_year

    def get_db():
        # 요청 하나마다 DB 연결 하나를 만들고, 요청이 끝나면 닫는다.
        if "db" not in g:
            g.db = database.connect(app.config["DB_PATH"])
        return g.db

    @app.teardown_appcontext
    def close_db(_error):
        conn = g.pop("db", None)
        if conn is not None:
            conn.close()

    def show_input_page(error=None, status=200):
        regions = database.get_regions(get_db())
        return render_template(
            "index.html",
            regions=regions,
            error=error,
            max_place=MAX_PLACE_LENGTH,
            selected_region=request.args.get("region", ""),
            birth_year=request.args.get("birth_year", ""),
        ), status

    @app.route("/")
    def index():
        return show_input_page()

    @app.route("/search")
    def search():
        # 처리 순서는 계획서와 같다: ① 입력값 검증 → ② 탐색 연도 계산 → ③ 지원 동네 확인
        try:
            place = validate_place(request.args.get("region"))
            birth_year = parse_birth_year(request.args.get("birth_year"))
            target_year = calculate_target_year(birth_year)
        except ValueError as error:
            return show_input_page(str(error), 400)
        region = find_region(database.get_regions(get_db()), place)
        # 지원 동네는 id로, 미지원 동네는 입력한 이름 그대로 결과 주소에 담는다.
        return redirect(url_for("result", region=region["id"] if region else place, year=target_year))

    @app.route("/result")
    def result():
        conn = get_db()
        try:
            place = validate_place(request.args.get("region"))
        except ValueError as error:
            return show_input_page(str(error), 400)
        try:
            year = int(request.args.get("year", ""))
            check_target_year(year)
        except ValueError as error:
            message = str(error) if "출생연도" in str(error) else "올바르지 않은 연도예요."
            return show_input_page(message, 400)

        # 지역 목록은 한 번만 조회해 지역 찾기와 화면(지원 동네 바로가기)에 함께 쓴다.
        regions = database.get_regions(conn)
        region = find_region(regions, place)  # None이면 미지원 동네
        memories = database.get_memories(conn, region["id"], year) if region else []
        summaries = database.get_comment_summaries(
            conn, [m["id"] for m in memories], COMMENT_PREVIEW_COUNT
        )
        for memory in memories:
            memory["comment_count"], memory["recent_comments"] = summaries[memory["id"]]

        current_year = app.config["CURRENT_YEAR"] or date.today().year
        trends = database.get_trends(conn, year)
        trends_by_category = {
            category: [t for t in trends if t["category"] == category]
            for category in TREND_CATEGORIES
        }
        return render_template(
            "result.html",
            region=region,
            place=place,
            # 결과·연도 이동 링크에 넣을 값: 지원 동네는 id, 미지원 동네는 입력한 이름
            region_key=region["id"] if region else place,
            regions=regions,
            unsupported_message=UNSUPPORTED_REGION_MESSAGE,
            year=year,
            years_ago=years_ago(year, current_year),
            # 같은 동네의 이전·다음 해로 바로 이동하는 버튼 (범위 끝이면 None → 버튼 숨김)
            prev_year=year - 1 if year > MIN_YEAR else None,
            next_year=year + 1 if year < MAX_YEAR else None,
            memories=memories,
            trends_by_category=trends_by_category,
            max_nickname=MAX_NICKNAME_LENGTH,
            max_content=MAX_CONTENT_LENGTH,
        )

    @app.get("/api/memories/<memory_id>/comments")
    def list_comments(memory_id):
        conn = get_db()
        if not database.memory_exists(conn, memory_id):
            return jsonify(error="없는 추억이에요."), 404
        return jsonify(comments=database.get_comments(conn, memory_id))

    def save_comment(save):
        """요청 본문의 닉네임·내용을 검증하고 save(닉네임, 내용)로 저장한다.

        지역 추억 댓글과 연도별 이야기가 같은 검증 규칙을 쓰도록 한 곳에 모았다.
        """
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            # JSON이 아니거나 객체가 아닌 본문(예: [1, 2])은 빈 값으로 보고 아래 검증에서 거부한다.
            data = {}
        try:
            nickname, content = validate_comment(data.get("nickname"), data.get("content"))
        except ValueError as error:
            return jsonify(error=str(error)), 400
        return jsonify(comment=save(nickname, content)), 201

    @app.post("/api/memories/<memory_id>/comments")
    def create_comment(memory_id):
        conn = get_db()
        if not database.memory_exists(conn, memory_id):
            return jsonify(error="없는 추억이에요."), 404
        return save_comment(lambda nick, text: database.add_comment(conn, memory_id, nick, text))

    # ---------- 연도별 이야기 (전국 유행 공통 공간) ----------

    def is_supported_year(year):
        try:
            check_target_year(year)
            return True
        except ValueError:
            return False

    @app.get("/api/years/<int:year>/comments")
    def list_year_comments(year):
        if not is_supported_year(year):
            return jsonify(error="지원하지 않는 연도예요."), 404
        return jsonify(comments=database.get_year_comments(get_db(), year))

    @app.post("/api/years/<int:year>/comments")
    def create_year_comment(year):
        if not is_supported_year(year):
            return jsonify(error="지원하지 않는 연도예요."), 404
        conn = get_db()
        return save_comment(lambda nick, text: database.add_year_comment(conn, year, nick, text))

    return app


if __name__ == "__main__":
    if not DATABASE_PATH.exists():
        print("DB가 없습니다. 먼저 'python seed.py'를 실행해 주세요.")
    else:
        create_app().run(debug=True)
