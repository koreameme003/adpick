"""
keyword_analyzer.py
카테고리(adpick / ai_news / latest_issue)에 따라 키워드·토픽을 수집하는 분석기.
- adpick      : 애드픽 API로 CPA 캠페인 목록 수집 (adpick_partner.py 활용)
- ai_news     : Google 뉴스 RSS에서 AI·인공지능 최신 헤드라인 수집
- latest_issue: Google 트렌드 RSS에서 실시간 급상승 이슈 수집
"""

import xml.etree.ElementTree as ET
import requests
from bs4 import BeautifulSoup
import random
import logging
import re

from adpick_partner import AdpickAPI

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


class KeywordAnalyzer:

    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    ]

    def __init__(self):
        self.adpick = AdpickAPI()

    def _headers(self) -> dict:
        return {
            "User-Agent": random.choice(self.USER_AGENTS),
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.5",
        }

    # ──────────────────────────────────────────
    # ① 애드픽 캠페인 선택
    # ──────────────────────────────────────────
    def get_adpick_topic(self) -> dict:
        """
        애드픽 API에서 CPA 캠페인 하나를 선정하여 반환한다.
        반환: {keyword, title, headline, promo_text, tracking_link, image_url, type_label}
        """
        campaigns = self.adpick.get_campaigns(adtype="CPA", order="rand", limit=20)

        if not campaigns:
            logging.warning("[애드픽] 캠페인 목록 없음 → Fallback")
            return {
                "keyword": "무료 가입 이벤트",
                "title": "지금 바로 가입하면 혜택이 쏟아진다!",
                "headline": "가입만 해도 포인트 지급",
                "promo_text": "간단 회원가입을 완료하면 풍성한 즉시 참여 혜택과 이벤트 보상을 드립니다.",
                "tracking_link": "https://www.adpick.co.kr",
                "image_url": "",
                "type_label": "가입형(CPA)",
            }

        chosen = random.choice(campaigns)
        logging.info(f"[애드픽] 선정된 캠페인: {chosen['title']}")

        return {
            "keyword": chosen["title"],
            "title": chosen["title"],
            "headline": chosen["headline"],
            "promo_text": chosen["promo_text"],
            "tracking_link": chosen["tracking_link"],
            "image_url": chosen["image_url"],
            "type_label": chosen["type_label"],
        }

    # ──────────────────────────────────────────
    # ② AI 뉴스 크롤러 (그대로 유지)
    # ──────────────────────────────────────────
    def get_ai_news_topic(self) -> dict:
        """Google 뉴스 RSS에서 AI·인공지능 최신 헤드라인을 가져온다."""
        feeds = [
            "https://news.google.com/rss/search?q=인공지능+AI&hl=ko&gl=KR&ceid=KR:ko",
            "https://news.google.com/rss/search?q=AI+chatgpt+gemini&hl=ko&gl=KR&ceid=KR:ko",
        ]
        items = []
        for url in feeds:
            try:
                r = requests.get(url, headers=self._headers(), timeout=10)
                root = ET.fromstring(r.content)
                for item in root.findall(".//item"):
                    title_el = item.find("title")
                    desc_el = item.find("description")
                    link_el = item.find("link")
                    if title_el is not None and title_el.text:
                        title = re.sub(r"<[^>]+>", "", title_el.text).strip()
                        desc = re.sub(r"<[^>]+>", "", desc_el.text or "").strip() if desc_el is not None else ""
                        link = link_el.text.strip() if link_el is not None else ""
                        items.append({"title": title, "summary": desc[:200], "link": link})
            except Exception as e:
                logging.warning(f"AI 뉴스 RSS 수집 실패 ({url}): {e}")

        if items:
            chosen = random.choice(items[:10])
            logging.info(f"[AI 뉴스] 선정: {chosen['title'][:40]}...")
            return chosen

        # Fallback
        fallback = {
            "title": "2026년 AI 인공지능 최신 동향 – 오늘 꼭 알아야 할 핵심 3가지",
            "summary": "세계 AI 기업들의 최신 모델 업데이트와 국내 도입 사례를 한눈에 정리했습니다.",
            "link": "",
        }
        logging.info("[AI 뉴스] Fallback 사용")
        return fallback

    # ──────────────────────────────────────────
    # ③ 최신 이슈 크롤러 (그대로 유지)
    # ──────────────────────────────────────────
    def _fetch_related_news(self, keyword: str) -> str:
        """구글 뉴스 RSS를 활용해 키워드와 관련된 최신 기사 3~5개의 제목을 수집한다."""
        url = f"https://news.google.com/rss/search?q={keyword}&hl=ko&gl=KR&ceid=KR:ko"
        try:
            r = requests.get(url, headers=self._headers(), timeout=10)
            xml_data = r.content.decode('utf-8')
            root = ET.fromstring(xml_data)
            news_titles = []
            for item in root.findall(".//item")[:5]:  # 상위 5개 기사
                title_el = item.find("title")
                if title_el is not None and title_el.text:
                    news_titles.append(title_el.text.strip())
            if news_titles:
                return " | ".join(f"{i+1}. {title}" for i, title in enumerate(news_titles))
        except Exception as e:
            logging.warning(f"관련 뉴스 수집 실패 ({keyword}): {e}")
        return ""

    def get_latest_issue_topic(self) -> dict:
        """Google 트렌드 RSS에서 실시간 급상승 이슈를 가져온다."""
        url = "https://trends.google.com/trending/rss?geo=KR"
        try:
            r = requests.get(url, headers=self._headers(), timeout=10)
            # UTF-8 강제 디코딩으로 한글 깨짐 원천 방지
            xml_data = r.content.decode('utf-8')
            root = ET.fromstring(xml_data)
            items = []
            for item in root.findall(".//item"):
                title_el = item.find("title")
                approx = item.find("{https://trends.google.com/trends/trendingsearches/daily}approx_traffic")
                if title_el is not None and title_el.text:
                    items.append({
                        "title": title_el.text.strip(),
                        "summary": f"현재 검색량: {approx.text if approx is not None else '급상승 중'}",
                    })
            if items:
                chosen = random.choice(items[:15])
                logging.info(f"[최신 이슈] 선정: {chosen['title']}")
                
                # 추가: 관련 실시간 뉴스 맥락 수집
                news_context = self._fetch_related_news(chosen['title'])
                if news_context:
                    chosen['summary'] = f"{chosen['summary']} | 관련 뉴스: {news_context}"
                
                return chosen
        except Exception as e:
            logging.warning(f"구글 트렌드 RSS 수집 실패: {e}")

        fallback = {
            "title": "오늘 가장 화제가 된 뉴스 이슈 정리",
            "summary": "지금 대한민국에서 가장 많이 검색된 실시간 이슈를 빠르게 확인하세요.",
        }
        logging.info("[최신 이슈] Fallback 사용")
        return fallback

    # ──────────────────────────────────────────
    # ④ 통합 진입점
    # ──────────────────────────────────────────
    def get_topic(self, category: str) -> dict:
        """
        category: "adpick" | "ai_news" | "latest_issue"
        반환: {keyword, title, summary, ...}
        """
        if category == "adpick":
            return self.get_adpick_topic()
        elif category == "ai_news":
            data = self.get_ai_news_topic()
            data["keyword"] = data["title"]
            return data
        elif category == "latest_issue":
            data = self.get_latest_issue_topic()
            data["keyword"] = data["title"]
            return data
        else:
            raise ValueError(f"지원하지 않는 카테고리: {category}")


if __name__ == "__main__":
    analyzer = KeywordAnalyzer()
    for cat in ["adpick", "ai_news", "latest_issue"]:
        print(f"\n[{cat}] →", analyzer.get_topic(cat))
