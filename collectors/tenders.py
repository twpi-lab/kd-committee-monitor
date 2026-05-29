"""
입찰공고 사이트 15곳 수집기
- parser='default'    : 일반 게시판 (양주·의정부 등)
- parser='molit'      : 대광위 (idx 추출 + Referer 헤더)
- parser='gtrans'     : 경기교통공사 (article_seq 추출)
- parser='playwright' : 경기도 (JS 렌더링)
"""
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
import urllib3
import requests
from datetime import datetime
from urllib.parse import urlparse, parse_qs
from bs4 import BeautifulSoup

from config import BASE_HEADERS, MONITOR_URLS
from storage import write_log

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Playwright (경기도청 JS 렌더링용) - 없으면 fetch_notices에서 안내
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_OK = True
except ImportError:
    PLAYWRIGHT_OK = False


# ════════════════════════════════════════════
#  공용 헬퍼
# ════════════════════════════════════════════

def make_id(site_name: str, link: str, title: str, date: str) -> str:
    try:
        parsed = urlparse(link or "")
        qs = parse_qs(parsed.query)
        for key in ("not_ancmt_mgt_no", "notAncmtMgtNo", "nttNo", "board_seq", "idx", "id", "article_seq"):
            if key in qs and qs[key]:
                return f"{site_name}|{key}={qs[key][0]}"
    except Exception:
        pass
    return f"{site_name}|{title[:40]}|{date}"


def abs_link(href: str, base: str) -> str:
    if not href:
        return ""
    h = href.strip()
    if not h or h.startswith("#") or h.lower().startswith("javascript"):
        return ""
    if h.startswith("http"):
        return h
    if h.startswith("./"):
        h = h[2:]
    return base.rstrip("/") + "/" + h.lstrip("/")


def extract_idx(row, tag) -> str:
    """대광위 onclick 패턴: idx= 또는 fn_xxx('숫자') 모두 인식"""
    combined = (
        (tag.get("onclick") or "") +
        (tag.get("href") or "") +
        str(row)
    )
    m = re.search(r"idx[=\'\"]+(\d+)", combined)
    if m:
        return m.group(1)
    m = re.search(r"fn\w*\s*\(\s*['\"]?\s*(\d+)", combined)
    if m:
        return m.group(1)
    return ""


def print_preview(site_name: str, notices: list):
    count = len(notices)
    print(f"\n📋 {site_name}: {count}건 확인")
    if not notices:
        return
    for i, n in enumerate(notices[:5]):
        is_last = (i == min(4, count - 1)) and count <= 5
        prefix  = "  └─" if is_last else "  ├─"
        print(f"{prefix} {n['title'][:42]}  ({n['date'][:10] if n['date'] else '-'})")
    if count > 5:
        print(f"  └─ ... 외 {count - 5}건 더")


_DATE_RE = re.compile(r"\d{4}[.\-/]\d{1,2}[.\-/]\d{1,2}")


def extract_date(row) -> str:
    """행에서 날짜를 깨끗하게 추출.
    1) td.date / td.reg_date / td.regdate 우선
    2) 위에서 못 찾으면 모든 td 텍스트에 정규식 search
    3) prefix(예: '등록일 : 2026/05/15')가 붙어도 정규식이 날짜 부분만 추출
    4) 정규식 매칭 실패 시 빈 문자열 (조회수 같은 비날짜 텍스트 오염 방지)
    """
    for sel in ("td.date", "td.reg_date", "td.regdate"):
        tag = row.select_one(sel)
        if tag:
            txt = tag.get_text(strip=True)
            m = _DATE_RE.search(txt)
            if m:
                return m.group(0)
    for td in row.select("td"):
        txt = td.get_text(strip=True)
        m = _DATE_RE.search(txt)
        if m:
            return m.group(0)
    return ""


def _build_notice(site_name, title, link, date, fallback_url="") -> dict:
    return {
        "id":           make_id(site_name, link, title, date),
        "title":        title,
        "link":         link or fallback_url,
        "date":         date,
        "site":         site_name,
        "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


# ════════════════════════════════════════════
#  파서
# ════════════════════════════════════════════

def _extract_onclick_id(tag) -> str:
    """onclick="boardView('1','67851')" 등에서 숫자 ID 추출"""
    onclick = tag.get("onclick", "") or ""
    m = re.search(r"boardView\s*\(\s*['\"]?\d+['\"]?\s*,\s*['\"]?(\d+)", onclick)
    if m:
        return m.group(1)
    return ""


def parse_default(soup, site) -> list:
    notices = []
    detail_url = site.get("detail_url", "")
    rows = (
        soup.select("table tbody tr")
        or soup.select("ul.bbs_list li")
        or soup.select(".board_list tbody tr")
        or soup.select(".list_wrap li")
        or soup.select(".tbl_wrap tbody tr")
    )
    for row in rows:
        tag = (
            row.select_one("td.subject a") or row.select_one("td.title a")
            or row.select_one("td.tit a")  or row.select_one("td a")
            or row.select_one("a")
        )
        if not tag:
            continue
        title = tag.get_text(strip=True)
        if not title or len(title) < 2:
            continue
        # "새글" 접미사 제거
        title = re.sub(r"\s*새글\s*$", "", title)
        # 링크: href 우선, onclick fallback
        link = abs_link(tag.get("href", ""), site["base"])
        if not link and detail_url:
            oid = _extract_onclick_id(tag)
            if oid:
                link = detail_url.format(idx=oid)
        date = extract_date(row)
        notices.append(_build_notice(site["name"], title, link, date, site["url"]))
    return notices


def parse_goyang(soup, site) -> list:
    """고양시 — td.text-left a 에서 실제 제목, searchDetail('ID')에서 고유ID 추출"""
    notices = []
    rows = soup.select("table tbody tr")
    for row in rows:
        # 실제 제목은 td.text-left 안의 <a>
        tag = row.select_one("td.text-left a")
        if not tag:
            continue
        title = tag.get_text(strip=True)
        if not title or len(title) < 2:
            continue
        # searchDetail('숫자') 패턴에서 ID 추출
        href = tag.get("href", "") or ""
        m = re.search(r"searchDetail\s*\(\s*['\"]?(\d+)", href)
        mgt_no = m.group(1) if m else ""
        # POST 전용이라 상세 링크 불가 → 목록 URL 사용, ID만 기록
        link = site["url"]
        date = extract_date(row)
        notice = _build_notice(site["name"], title, link, date, site["url"])
        if mgt_no:
            notice["id"] = f"{site['name']}|not_ancmt_mgt_no={mgt_no}"
        notices.append(notice)
    return notices


def parse_molit(soup, site) -> list:
    notices = []
    rows = soup.select("table tbody tr")
    # 디버그: 첫 행 HTML 구조 기록 (날짜 추출 문제 파악용)
    if rows and not extract_date(rows[0]):
        write_log(f"[대광위_디버그] 첫 행 HTML(500자): {str(rows[0])[:500]}")
    for row in rows:
        tag = (
            row.select_one("td.title a") or row.select_one("td.subject a")
            or row.select_one("td a")     or row.select_one("a")
        )
        if not tag:
            continue
        title = tag.get_text(strip=True)
        if not title or len(title) < 2:
            continue
        idx  = extract_idx(row, tag)
        link = site["detail_url"].format(idx=idx) if idx else site["url"]
        date = extract_date(row)
        notices.append(_build_notice(site["name"], title, link, date, site["url"]))
    return notices


def parse_gtrans(soup, site) -> list:
    notices = []
    detail_url = site.get("detail_url", "")

    rows = (
        soup.select("table tbody tr")
        or soup.select(".board_list tbody tr")
        or soup.select("ul.bbs_list li")
        or soup.select(".list_wrap li")
        or soup.select("ul li")
    )
    for row in rows:
        tag = (
            row.select_one("td.subject a") or row.select_one("td.title a")
            or row.select_one(".tit a")    or row.select_one("td a")
            or row.select_one("a")
        )
        if not tag:
            continue
        title = tag.get_text(strip=True)
        if not title or len(title) < 2:
            continue

        href = tag.get("href", "") or ""
        link = ""
        if detail_url:
            row_html = str(row) + (tag.get("onclick") or "") + href
            m = re.search(r"article_seq[=,'\"]*([0-9]+)", row_html)
            if m:
                link = detail_url.format(seq=m.group(1))
        if not link:
            link = abs_link(href, site["base"])
        if not link:
            link = site["url"]

        date = extract_date(row)
        notices.append(_build_notice(site["name"], title, link, date, site["url"]))
    return notices


def _pw_fetch_html(site: dict) -> str:
    """Playwright로 경기도청 페이지 HTML을 가져온다."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page(
                user_agent=BASE_HEADERS["User-Agent"],
                extra_http_headers={"Accept-Language": "ko-KR,ko;q=0.9"},
            )
            page.goto(site["url"], timeout=30000, wait_until="domcontentloaded")
            # 경기도청은 AJAX로 게시글을 비동기 로드 — 로더가 사라질 때까지 대기
            try:
                page.wait_for_selector(
                    "#boardList tbody tr td a",
                    timeout=15000,
                )
            except Exception:
                pass
            return page.content()
        finally:
            browser.close()


def fetch_gg_playwright(site: dict) -> list:
    """경기도청 — Playwright 헤드리스 chromium으로 JS 렌더링 후 파싱 (최대 2회 시도)"""
    if not PLAYWRIGHT_OK:
        write_log(f"[크롤링오류] {site['name']} | playwright 미설치")
        return []

    notices = []
    html = ""
    last_err = None

    for attempt in range(1, 3):
        try:
            html = _pw_fetch_html(site)
            last_err = None
            break
        except Exception as e:
            last_err = e
            if attempt < 2:
                time.sleep(3)

    if last_err:
        print(f"  ⚠️  Playwright 오류 (2회 시도): {last_err}")
        write_log(f"[크롤링오류] {site['name']} | Playwright(2회): {last_err}")
        return []

    soup = BeautifulSoup(html, "html.parser")
    rows = (
        soup.select("table tbody tr")
        or soup.select(".bbs_list li")
        or soup.select(".board_list tbody tr")
        or soup.select(".tbl_list tbody tr")
        or soup.select(".list_wrap li")
        or soup.select("ul.list li")
        or soup.select(".bd_list li")
        or soup.select("ul.board_ul li")
    )
    for row in rows:
        tag = (
            row.select_one("td.td_subject a")
            or row.select_one("td.subject a")
            or row.select_one("td.title a")
            or row.select_one(".tit a")
            or row.select_one(".subject a")
            or row.select_one("td a")
            or row.select_one("a")
        )
        if not tag:
            continue
        title = tag.get_text(strip=True)
        if not title or len(title) < 2:
            continue
        href = tag.get("href", "")
        link = abs_link(href, site["base"])
        if not link:
            link = site["url"]
        date = extract_date(row)
        notices.append(_build_notice(site["name"], title, link, date))

    if not notices:
        write_log(f"[경기도PW_디버그] 0건 | 렌더링 후 행 수: {len(rows)}")
        try:
            debug_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "state", "debug_gg_html.html",
            )
            with open(debug_path, "w", encoding="utf-8") as f:
                f.write(html or "(empty)")
            write_log(f"[경기도PW_디버그] HTML 덤프 저장: state/debug_gg_html.html ({len(html)}자)")
        except Exception as e:
            write_log(f"[경기도PW_디버그] HTML 덤프 실패: {e}")
    return notices


def fetch_notices(site: dict) -> list:
    if site.get("parser") == "playwright":
        notices = fetch_gg_playwright(site)
        print_preview(site["name"], notices)
        if not notices and not PLAYWRIGHT_OK:
            print("  ⚠️  playwright 미설치 (pip install playwright && playwright install chromium)")
        return notices

    headers  = {**BASE_HEADERS, **site.get("extra_headers", {})}
    max_try  = 3 if site.get("parser") == "molit" else 2
    last_err = None

    for attempt in range(1, max_try + 1):
        try:
            res = requests.get(
                site["url"], headers=headers,
                timeout=25, verify=site.get("ssl", True),
            )
            res.encoding = "utf-8"
            soup = BeautifulSoup(res.text, "html.parser")

            parser = site.get("parser", "default")
            if parser == "molit":
                notices = parse_molit(soup, site)
            elif parser == "gtrans":
                notices = parse_gtrans(soup, site)
            elif parser == "goyang":
                notices = parse_goyang(soup, site)
            else:
                notices = parse_default(soup, site)

            print_preview(site["name"], notices)
            return notices

        except Exception as e:
            last_err = e
            if attempt < max_try:
                time.sleep(2)

    print(f"\n📋 {site['name']}: 0건 확인")
    print(f"  ⚠️  크롤링 오류 ({max_try}회 시도): {last_err}")
    write_log(f"[크롤링오류] {site['name']} | {last_err}")
    return []


def fetch_all() -> list:
    """모든 사이트 병렬 크롤링 → 공고 리스트 반환"""
    all_notices = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        results = executor.map(fetch_notices, MONITOR_URLS)
        for notices in results:
            all_notices.extend(notices)
    return all_notices
