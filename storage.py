"""
JSON 파일 I/O + 발송 이력 관리
"""
import json
import os
import tempfile
from datetime import datetime

from config import ALL_FILE, SENT_FILE, LOG_FILE, RUN_STATUS_FILE


def _atomic_write_json(path: str, data):
    """임시 파일에 쓴 뒤 os.replace로 원자적 교체 (쓰기 중 중단 시 데이터 보호)"""
    dir_name = os.path.dirname(path) or "."
    fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def load_json_list(path: str) -> list:
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_json_list(path: str, data: list, max_items: int = None):
    if max_items and len(data) > max_items:
        data = data[-max_items:]
    _atomic_write_json(path, data)


def load_sent_ids() -> dict:
    """
    dict{id: timestamp} 형식. 구버전(list[str], list[list])도 흡수.
    """
    if not os.path.exists(SENT_FILE):
        return {}
    try:
        with open(SENT_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except Exception:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, list) and raw:
        if isinstance(raw[0], str):
            return {item: "1970-01-01 00:00:00" for item in raw}
        if isinstance(raw[0], list) and len(raw[0]) == 2:
            return {k: v for k, v in raw}
    return {}


def save_sent_ids(sent: dict):
    """최신 5000건만 유지 (timestamp 오름차순 기준). dict로 직접 저장."""
    sorted_items = sorted(sent.items(), key=lambda x: x[1])[-5000:]
    trimmed = dict(sorted_items)
    _atomic_write_json(SENT_FILE, trimmed)


def append_all_notices(new_notices: list) -> int:
    all_data = load_json_list(ALL_FILE)
    existing_ids = {n.get("id") for n in all_data}
    added = 0
    for n in new_notices:
        nid = n["id"]
        if nid not in existing_ids:
            all_data.append(n)
            existing_ids.add(nid)
            added += 1
    save_json_list(ALL_FILE, all_data, max_items=10000)
    return added


def write_log(msg: str):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")


def save_run_status(status: dict):
    """마지막 실행 상태를 workflow health check가 읽을 수 있게 저장."""
    _atomic_write_json(RUN_STATUS_FILE, status)
