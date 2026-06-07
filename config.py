"""
위원회/국민참여단 모집 공고 알림봇 설정.

원칙:
- 실제 참여 자격을 주장할 수 있는 지역/광역 소스 + 전국 단위 기관만 수집한다.
- 서울시는 사용자 결정에 따라 제외한다.
- 단순 의견수렴/이벤트/결과발표는 필터에서 제외한다.
"""
import os
from pathlib import Path

# ────────────────────────────────────────────────
#  .env 파일 자동 로드 (로컬 실행용; GitHub Actions에서는 Secrets 사용)
# ────────────────────────────────────────────────
_env_file = Path(__file__).parent / ".env"
if _env_file.exists():
    for _line in _env_file.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _, _v = _line.partition("=")
            os.environ.setdefault(_k.strip(), _v.strip())

# ────────────────────────────────────────────────
#  텔레그램
# ────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
ALERT_TIME = "07:00"

# ────────────────────────────────────────────────
#  데이터 저장 경로
# ────────────────────────────────────────────────
BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state")
os.makedirs(BASE_DIR, exist_ok=True)

ALL_FILE = os.path.join(BASE_DIR, "all_notices.json")
SENT_FILE = os.path.join(BASE_DIR, "sent_ids.json")
LOG_FILE = os.path.join(BASE_DIR, "alert_log.txt")
RUN_STATUS_FILE = os.path.join(BASE_DIR, "run_status.json")

# ────────────────────────────────────────────────
#  HTTP 헤더
# ────────────────────────────────────────────────
BASE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
}

# ────────────────────────────────────────────────
#  키워드: 위원회/참여단 유형 AND 모집 신호 - 제외 신호
# ────────────────────────────────────────────────
COMMITTEE_KEYWORDS = [
    "위원", "위원회", "위촉위원", "자문위원", "전문위원", "평가위원",
    "국민참여위원", "주민참여예산위원", "시민참여단", "국민참여단",
    "정책모니터단", "모니터단", "모니터링단", "국민소통단", "시민소통단",
    "자문단", "평가단", "검토단", "서포터즈", "시민감사관", "청렴시민감사관",
    "옴부즈만", "배심원단", "숙의단", "패널",
]

RECRUIT_KEYWORDS = [
    "모집", "공개모집", "재모집", "추가모집", "선발", "공모", "추천",
    "신청", "접수", "등록", "후보자", "인재풀", "위촉", "참여자 모집",
]

EXCLUDE_KEYWORDS = [
    "선정 결과", "선정결과", "합격자", "발표", "명단", "회의 결과", "회의결과",
    "회의 개최", "회의개최", "회의록", "개최 안내", "심의 결과", "심의결과",
    "입찰", "용역", "낙찰", "계약", "견적", "채용", "기간제", "공무직",
    "교육생", "수강생", "강사", "행사", "이벤트", "공모전 결과", "수상작",
    "보도자료", "설명자료", "해명자료", "카드뉴스",
    # 사용자는 40대이므로 청년/2030/대학생 등 연령 제한 공고는 제외한다.
    "청년", "2030", "20대", "30대", "만 19세", "만19세", "만 29세", "만29세",
    "만 34세", "만34세", "만 39세", "만39세", "대학생", "대학(원)생",
]

URGENT_KEYWORDS = ["마감", "긴급", "오늘", "내일", "D-", "추가모집", "재모집"]

# ────────────────────────────────────────────────
#  모니터링 사이트
#  - 지역/광역 6곳: 기존 MVP
#  - 전국 단위 5곳: B안 확장
# ────────────────────────────────────────────────
MONITOR_URLS = [
    # 지역/광역 — 실제 거주/직장 근거가 있는 곳
    {
        "name": "양주시 고시공고",
        "url": "https://www.yangju.go.kr/www/selectEminwonList.do?key=4075",
        "base": "https://www.yangju.go.kr/www",
        "ssl": True,
        "parser": "default",
    },
    {
        "name": "의정부시 고시공고",
        "url": "https://www.ui4u.go.kr/portal/saeol/gosiList.do?seCode=01&mId=0301040000",
        "base": "https://www.ui4u.go.kr/portal/saeol",
        "ssl": False,
        "parser": "default",
        "detail_url": "https://www.ui4u.go.kr/portal/saeol/gosiView.do?notAncmtMgtNo={idx}&mId=0301040000",
        "timeout": 12,
        "fallback_urls": [
            {
                "url": "http://eminwon.ui4u.go.kr/emwp/gov/mogaha/ntis/web/ofr/action/OfrAction.do?jndinm=OfrNotAncmtEJB&context=NTIS&method=selectListOfrNotAncmt&methodnm=selectListOfrNotAncmtHomepage&homepage_pbs_yn=Y&subCheck=Y&not_ancmt_se_code=01,04,05&title=%EA%B3%A0%EC%8B%9C%EA%B3%B5%EA%B3%A0&initValue=Y&countYn=Y",
                "base": "http://eminwon.ui4u.go.kr",
                "ssl": True,
                "parser": "ui4u_eminwon",
                "encoding": "utf-8-sig",
                "timeout": 25,
            },
        ],
    },
    {
        "name": "경기도 고시공고",
        "url": "https://www.gg.go.kr/bbs/board.do?bsIdx=469&menuId=1547",
        "base": "https://www.gg.go.kr",
        "ssl": True,
        "parser": "playwright",
    },
    {
        "name": "남양주시 고시공고",
        "url": "https://www.nyj.go.kr/www/selectEminwonWebList.do?key=2492",
        "base": "https://www.nyj.go.kr/www",
        "ssl": True,
        "parser": "default",
    },
    {
        "name": "성동구 고시공고",
        "url": "https://www.sd.go.kr/main/selectGosiList.do",
        "base": "https://www.sd.go.kr/main",
        "ssl": True,
        "parser": "default",
    },
    {
        "name": "경기도의회 공고",
        "url": "https://www.ggc.go.kr/site/main/board/pblcntc/list",
        "base": "https://www.ggc.go.kr",
        "ssl": True,
        "parser": "default",
    },

    # 전국 단위 — 실제 연령/접속 조건에 맞는 곳만 유지
    {
        "name": "국가교육위원회",
        "url": "https://www.ne.go.kr/user/bbs/BD_selectBbsList.do?q_bbsSn=1003",
        "base": "https://www.ne.go.kr/user/bbs",
        "ssl": True,
        "parser": "default",
    },
    {
        "name": "국민권익위원회",
        "url": "https://www.acrc.go.kr/menu.es?mid=a10401010000",
        "base": "https://www.acrc.go.kr",
        "ssl": True,
        "parser": "default",
    },
    {
        "name": "국민통합위원회",
        "url": "https://www.k-cohesion.go.kr/PCNC/contents/P30200000000.do",
        "base": "https://www.k-cohesion.go.kr",
        "ssl": True,
        "parser": "kcohesion",
        "detail_url": "https://www.k-cohesion.go.kr/PCNC/contents/P30200000000.do?schM=view&id={doc_id}&schBcid=category01",
    },
    {
        "name": "국민참여예산",
        "url": "https://www.mybudget.go.kr/cmmnBoard/boardNoticeList",
        "base": "https://www.mybudget.go.kr",
        "ssl": True,
        "parser": "default",
    },
]
