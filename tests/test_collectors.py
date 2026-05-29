from bs4 import BeautifulSoup

from collectors.tenders import parse_ui4u_eminwon


def test_parse_ui4u_eminwon_rows():
    html = """
    <table>
      <tr bgcolor="#FFFFFF">
        <td onclick="javaScript:searchDetail('67928')">4038</td>
        <td onclick="javaScript:searchDetail('67928')"><p>의정부시 공고 제2026-1111호</p></td>
        <td onclick="javaScript:searchDetail('67928')"><p>공법선정위원회 평가위원(후보자) 모집 공고</p></td>
        <td onclick="javaScript:searchDetail('67928')">하수과</td>
        <td onclick="javaScript:searchDetail('67928')">2026-05-28</td>
        <td onclick="javaScript:searchDetail('67928')">0</td>
      </tr>
    </table>
    """
    site = {
        "name": "의정부시 고시공고",
        "url": "http://eminwon.ui4u.go.kr/list",
        "base": "http://eminwon.ui4u.go.kr",
        "detail_url": "https://www.ui4u.go.kr/portal/saeol/gosiView.do?notAncmtMgtNo={idx}&mId=0301040000",
    }
    notices = parse_ui4u_eminwon(BeautifulSoup(html, "html.parser"), site)

    assert len(notices) == 1
    assert notices[0]["id"] == "의정부시 고시공고|notAncmtMgtNo=67928"
    assert notices[0]["title"] == "의정부시 공고 제2026-1111호 공법선정위원회 평가위원(후보자) 모집 공고"
    assert notices[0]["date"] == "2026-05-28"
    assert "notAncmtMgtNo=67928" in notices[0]["link"]
