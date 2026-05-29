"""
🏛️ 위원회/국민참여단 모집 공고 알림봇 — 진입점

- 동작: 매일 07:00 자동 실행 (schedule)
- 수동 조작 (대화형):
    t = 즉시 테스트   k = 키워드 확인
    l = 발송 로그     r = 알림 초기화
    q = 종료

- 비대화형 1회 실행: python main.py --once
  (GitHub Actions·cron 등에서 사용. 명령어 입력 루프 없이 즉시 종료)
"""
import os
import sys
import time
import threading
from datetime import datetime

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import schedule

from config import (
    ALERT_TIME,
    MONITOR_URLS,
    LOG_FILE,
    SENT_FILE,
    COMMITTEE_KEYWORDS,
    RECRUIT_KEYWORDS,
    EXCLUDE_KEYWORDS,
)
from collectors.tenders import fetch_all
from filters import match_keywords, urgency_tag
from notifier import send_batch
from storage import append_all_notices, load_sent_ids, save_sent_ids, write_log


_crawl_lock = threading.Lock()
_shutdown = threading.Event()


def crawl_store_and_notify():
    if not _crawl_lock.acquire(blocking=False):
        print("  ⏳ 이미 실행 중 — 건너뜀")
        return
    try:
        _crawl_store_and_notify_impl()
    finally:
        _crawl_lock.release()


def _crawl_store_and_notify_impl():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n{'=' * 60}")
    print(f"  위원회/국민참여단 공고 수집 + 알림 시작: {now}")
    print(f"{'=' * 60}")

    all_new_notices = fetch_all()
    total_crawled = len(all_new_notices)

    added = append_all_notices(all_new_notices)
    sent_ids = load_sent_ids()

    print(f"\n🗂️  새 공고 저장: {added}건 (총 크롤링: {total_crawled}건)")

    matched = []
    for notice in all_new_notices:
        nid = notice["id"]
        if nid in sent_ids:
            continue
        is_match, _, _ = match_keywords(notice["title"])
        if not is_match:
            continue
        matched.append({
            "notice": notice,
            "is_urgent": bool(urgency_tag(notice["title"])),
        })

    found = 0
    if matched:
        all_ok, sent_items = send_batch(matched, now)
        if sent_items:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            for item in sent_items:
                n = item["notice"]
                sent_ids[n["id"]] = ts
                write_log(f"[알림발송] {n['site']} | {n['title']}")
            found = len(sent_items)
            print(f"\n  🔔 묶음 알림 발송: {found}건")
        if not all_ok:
            failed = len(matched) - len(sent_items)
            print(f"  ⚠️  일부 청크 발송 실패: {failed}건은 다음 실행 때 재시도")
            write_log(f"[묶음발송부분실패] 매칭 {len(matched)}건 중 {failed}건 실패")

    save_sent_ids(sent_ids)

    print(f"\n{'─' * 60}")
    print(f"  크롤링: {total_crawled}건 | 새 저장: {added}건 | 알림 발송: {found}건")
    if found == 0:
        print("  📭 매칭된 새 공고 없음")
    print(f"{'=' * 60}")


def show_keywords():
    print(f"\n{'─' * 60}")
    print(f"  🏛️ COMMITTEE_KEYWORDS ({len(COMMITTEE_KEYWORDS)}개):\n     {', '.join(COMMITTEE_KEYWORDS)}")
    print(f"\n  📝 RECRUIT_KEYWORDS ({len(RECRUIT_KEYWORDS)}개):\n     {', '.join(RECRUIT_KEYWORDS)}")
    print(f"\n  ❌ EXCLUDE_KEYWORDS ({len(EXCLUDE_KEYWORDS)}개):\n     {', '.join(EXCLUDE_KEYWORDS)}")
    print(f"{'─' * 60}")
    print("\n명령어 입력 > ", end="", flush=True)


def show_log():
    print(f"\n{'─' * 60}")
    if not os.path.exists(LOG_FILE):
        print("  📋 발송 기록 없음")
    else:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
        for line in (lines[-10:] if len(lines) >= 10 else lines):
            print(f"  {line.rstrip()}")
    print(f"{'─' * 60}")
    print("\n명령어 입력 > ", end="", flush=True)


def reset_sent():
    if os.path.exists(SENT_FILE):
        os.remove(SENT_FILE)
    print("  🗑️  sent_ids 초기화 완료 (다음 실행부터 다시 알림)")
    print("\n명령어 입력 > ", end="", flush=True)


def input_listener():
    while not _shutdown.is_set():
        try:
            cmd = input().strip().lower()
            if cmd == "t":
                print("\n[즉시 테스트 실행 중...]")
                crawl_store_and_notify()
                print("\n명령어 입력 > ", end="", flush=True)
            elif cmd == "k":
                show_keywords()
            elif cmd == "l":
                show_log()
            elif cmd == "r":
                reset_sent()
            elif cmd == "q":
                print("\n👋 알림봇을 종료합니다.")
                _shutdown.set()
                return
            else:
                print("  t=즉시테스트 | k=키워드확인 | l=발송로그 | r=알림초기화 | q=종료")
                print("\n명령어 입력 > ", end="", flush=True)
        except EOFError:
            time.sleep(1)


def main():
    if "--once" in sys.argv:
        crawl_store_and_notify()
        return

    print("""
╔═══════════════════════════════════════════════════════╗
║  🏛️ 위원회/국민참여단 모집 공고 알림봇 시작!        ║
╠═══════════════════════════════════════════════════════╣""")
    print(f"║  📡 모니터링 (총 {len(MONITOR_URLS)}곳):")
    for i, s in enumerate(MONITOR_URLS, 1):
        print(f"║     {i}. {s['name']}")
    print("""╠═══════════════════════════════════════════════════════╣
║  📁 state/all_notices.json : 수집 공고 누적          ║
║  📁 state/sent_ids.json    : 알림 발송 이력          ║
╠═══════════════════════════════════════════════════════╣
║  ⌨️  t  →  즉시 테스트    k  →  키워드 확인          ║
║  ⌨️  l  →  발송 로그      r  →  알림 초기화          ║
║  ⌨️  q  →  종료                                      ║
╚═══════════════════════════════════════════════════════╝
""")
    schedule.every().day.at(ALERT_TIME).do(crawl_store_and_notify)
    print(f"⏰ 다음 실행 예정: {schedule.next_run()}\n")
    print("명령어 입력 > ", end="", flush=True)

    th = threading.Thread(target=input_listener, daemon=True)
    th.start()
    while not _shutdown.is_set():
        schedule.run_pending()
        _shutdown.wait(30)
    schedule.clear()


if __name__ == "__main__":
    main()
