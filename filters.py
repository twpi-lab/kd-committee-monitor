"""
위원회/국민참여단 모집 공고 키워드 매칭.

규칙:
1. 제외 키워드가 있으면 즉시 제외
2. 위원회/참여단 유형 키워드 AND 모집 신호 키워드가 함께 있으면 매칭
3. 청년DB처럼 '인재풀/후보자/등록' 성격은 위원회 유형 없이도 별도 허용
"""
import re

from config import COMMITTEE_KEYWORDS, RECRUIT_KEYWORDS, EXCLUDE_KEYWORDS, URGENT_KEYWORDS


def _kw_in(kw: str, text: str) -> bool:
    """키워드 포함 검사. 영문 포함 키워드는 대소문자 무시."""
    if any(c.isascii() and c.isalpha() for c in kw):
        return kw.lower() in text.lower()
    return kw in text


def match_keywords(title: str):
    """return: (is_match, matched_type_keywords, matched_recruit_keywords)"""
    t = title or ""
    for ex in EXCLUDE_KEYWORDS:
        if _kw_in(ex, t):
            return (False, [], [])

    committee = [kw for kw in COMMITTEE_KEYWORDS if _kw_in(kw, t)]
    recruit = [kw for kw in RECRUIT_KEYWORDS if _kw_in(kw, t)]

    if committee and recruit:
        return (True, committee, recruit)

    # 청년DB/정부위원회 인재풀류: 제목이 '청년인재 등록', '후보자 추천'처럼
    # 위원회라는 단어 없이 올라오는 경우를 일부 허용한다.
    pool_terms = ["인재풀", "청년DB", "청년인재", "후보자", "정부위원회"]
    if recruit and any(_kw_in(kw, t) for kw in pool_terms):
        return (True, [kw for kw in pool_terms if _kw_in(kw, t)], recruit)

    return (False, [], [])


def urgency_tag(title: str) -> str:
    t = title or ""
    for w in URGENT_KEYWORDS:
        if w in t:
            return "🚨 긴급 "
    m = re.search(r"D-(\d+)", t)
    if m and int(m.group(1)) <= 7:
        return "🚨 긴급 "
    return ""
