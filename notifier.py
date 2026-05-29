"""
텔레그램 발송
- send_telegram(message): 단건 (호환용)
- send_batch(items, now_str): 묶음 발송 (긴급/일반 분류, 4000자 분할)
  → (all_ok, sent_items) 반환 — 부분 성공 시 성공한 items만 sent_ids에 기록 가능
"""
import time
import requests
from html import escape as html_escape

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from storage import write_log


TELEGRAM_MSG_LIMIT = 4000  # 텔레그램 4096 한도, 여유 96자


def send_telegram(message: str) -> bool:
    """단건 발송. 실패 시 최대 3회 재시도, 타임아웃 30초."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    for attempt in range(1, 4):
        try:
            res = requests.post(url, data=payload, timeout=30)
            if res.status_code == 200:
                print("  ✅ 텔레그램 전송 성공!")
                return True
            if attempt < 3:
                print(f"  ⚠️  전송 실패 ({res.status_code}) - {attempt}회 재시도 중...")
                time.sleep(5)
            else:
                print(f"  ❌ 전송 실패 ({res.status_code}) - 3회 모두 실패")
                write_log(f"[텔레그램오류] HTTP {res.status_code}")
                return False
        except Exception as e:
            if attempt < 3:
                print(f"  ⚠️  텔레그램 오류 ({attempt}회) 재시도 중... {e}")
                time.sleep(5)
            else:
                print(f"  ❌ 텔레그램 오류 (3회 실패): {e}")
                write_log(f"[텔레그램오류] {e}")
                return False
    return False


def _format_item(idx: int, notice: dict) -> str:
    """공고 1건을 메시지 라인 1개로 직렬화 (HTML 안전)"""
    link  = notice.get("link") or "링크 없음"
    title = notice.get("title", "")
    site  = notice.get("site", "")
    date  = (notice.get("date") or "").strip()
    # parse_mode=HTML 사용 — 사용자 데이터의 <, >, & 이스케이프 필수
    return (
        f"<b>{idx}.</b> {html_escape(title)}\n"
        f"   🏢 {html_escape(site)} | 📅 {html_escape(date)}\n"
        f"   🔗 {html_escape(link)}"
    )


def build_batch_message(items: list, now_str: str) -> str:
    """
    items: [{"notice": dict, "is_urgent": bool}, ...]
    → 1건의 HTML 메시지 문자열 (긴급 / 일반 섹션 분리)
    """
    urgent = [it for it in items if it["is_urgent"]]
    normal = [it for it in items if not it["is_urgent"]]

    lines = [
        f"🔔 <b>[위원회/국민참여단 모집 공고 모니터링]</b>",
        f"⏰ {html_escape(now_str)}",
        "",
    ]
    idx = 0
    if urgent:
        lines.append(f"🚨 <b>긴급 ({len(urgent)}건)</b> — D-7 이내 또는 긴급 키워드")
        for it in urgent:
            idx += 1
            lines.append(_format_item(idx, it["notice"]))
            lines.append("")
    if normal:
        lines.append(f"📋 <b>일반 모집공고 ({len(normal)}건)</b>")
        for it in normal:
            idx += 1
            lines.append(_format_item(idx, it["notice"]))
            lines.append("")
    return "\n".join(lines).rstrip()


def _chunk_items(items: list, now_str: str, limit: int = TELEGRAM_MSG_LIMIT) -> list:
    """
    items를 텔레그램 길이 한도에 맞춰 청크 단위로 분할.
    각 청크는 자체적으로 build_batch_message로 완전한 메시지가 되도록 한다.
    return: [[item, item, ...], [item, ...], ...]
    """
    if not items:
        return []
    # 한 번에 다 들어가면 단일 청크
    if len(build_batch_message(items, now_str)) <= limit:
        return [items]
    chunks, cur = [], []
    for it in items:
        candidate = cur + [it]
        if cur and len(build_batch_message(candidate, now_str)) > limit:
            chunks.append(cur)
            cur = [it]
        else:
            cur = candidate
    if cur:
        chunks.append(cur)
    return chunks


def send_batch(items: list, now_str: str):
    """
    items: [{"notice": dict, "is_urgent": bool}, ...]
    → 묶음 메시지 1건(또는 분할 다건) 발송. 청크별 부분 성공 추적.
    return: (all_ok: bool, sent_items: list)
        - all_ok       : 모든 청크가 성공했는지
        - sent_items   : 실제 발송에 성공한 items만 (sent_ids 갱신용)
    """
    if not items:
        return True, []
    chunks = _chunk_items(items, now_str)
    sent_items = []
    all_ok = True
    for i, chunk in enumerate(chunks, 1):
        if len(chunks) > 1:
            print(f"  📤 묶음 {i}/{len(chunks)} 전송 중...")
        msg = build_batch_message(chunk, now_str)
        if send_telegram(msg):
            sent_items.extend(chunk)
        else:
            all_ok = False
    return all_ok, sent_items
