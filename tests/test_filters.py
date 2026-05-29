import pytest

from filters import match_keywords, urgency_tag


@pytest.mark.parametrize("title", [
    "제3기 국민참여위원회 위원 공개모집 공고",
    "2026년 정책모니터단 참여자 모집 안내",
    "청렴시민감사관 공개모집",
    "청년위원 후보자 등록 안내",
    "정부위원회 청년인재 추천 및 인재풀 등록",
    "주민참여예산위원회 위원 추가모집",
    "국민소통단 모집 공고",
])
def test_match_recruitment_titles(title):
    matched, left, right = match_keywords(title)
    assert matched is True
    assert left
    assert right


@pytest.mark.parametrize("title", [
    "제3기 국민참여위원회 선정 결과 공고",
    "정책모니터단 회의 개최 안내",
    "주민참여예산위원회 회의록 게시",
    "위원회 운영 용역 입찰 공고",
    "기간제근로자 채용 공고",
    "시민참여 이벤트 안내",
])
def test_exclude_noise_titles(title):
    matched, _, _ = match_keywords(title)
    assert matched is False


def test_plain_notice_without_recruit_signal_not_match():
    matched, _, _ = match_keywords("국민참여위원회 운영 안내")
    assert matched is False


def test_urgency_tag():
    assert urgency_tag("국민참여단 추가모집")
    assert urgency_tag("위원 공개모집 D-3")
    assert urgency_tag("위원 공개모집") == ""
