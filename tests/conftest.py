"""모든 테스트가 함께 쓰는 준비 코드(fixture).

테스트마다 임시 폴더에 새 DB를 만들고 tests/fixtures의 [테스트] 자료를 넣는다.
실제 서비스 DB(instance/app.db)는 건드리지 않는다.
"""
from pathlib import Path

import pytest

from app import create_app
from database import connect
from seed import seed

FIXTURE_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "test.db"
    conn = connect(path)
    seed(conn, FIXTURE_DIR)
    conn.close()
    return path


@pytest.fixture
def client(db_path):
    # 현재 연도를 2026으로 고정해 "몇 년 전" 계산 결과가 매년 바뀌지 않게 한다.
    app = create_app(db_path=db_path, current_year=2026)
    app.config["TESTING"] = True
    return app.test_client()
