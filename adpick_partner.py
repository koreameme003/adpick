"""
adpick_partner.py
애드픽(Adpick) 광고메이트 캠페인 리스트 API 클라이언트
- API: https://adpick.co.kr/apis/offers.php?affid={AFFID}&os=&adtype=&category=&order=rand
- 실제 응답 필드: apOffer, apType, apAppTitle, apHeadline, apAppPromoText,
                  apImages(icon/banner...), apTrackingLink, apRemain, apOS
"""

import os
import requests
import logging
import json
import time

logger = logging.getLogger(__name__)

# apType 코드 → 한국어 레이블 매핑
AP_TYPE_MAP = {
    "1":  "설치형(CPI)",
    "3":  "가입형(CPA)",
    "4":  "이벤트형(CPA)",
    "16": "사전예약",
}


class AdpickAPI:
    """애드픽 광고메이트 캠페인 목록 API 클라이언트."""

    BASE_URL = "https://adpick.co.kr/apis/offers.php"
    CACHE_FILE = "campaign_cache.json"
    CACHE_TTL = 60

    def __init__(self):
        # .env 또는 환경변수에서 ADPICK_AFFID 읽기
        self.affid = os.getenv("ADPICK_AFFID", "")
        if not self.affid:
            logger.warning(
                "ADPICK_AFFID 환경변수가 설정되지 않았습니다. "
                ".env 파일에 ADPICK_AFFID=your_id 형식으로 입력하세요."
            )

    def get_campaigns(
        self,
        adtype: str = "",
        category: str = "",
        order: str = "rand",
        limit: int = 30,
    ) -> list[dict]:
        """
        애드픽 광고메이트 캠페인 목록을 가져온다.

        Args:
            adtype:   "CPI"(설치형) | "CPA"(가입/이벤트) | "" (전체)
            category: "game" | "notgame" | "" (전체)
            order:    "rand"(랜덤) | "randone"(1개) | "" (최신순)
            limit:    반환할 최대 캠페인 수

        Returns:
            정제된 캠페인 딕셔너리 리스트.
            각 항목: {id, title, headline, promo_text, tracking_link,
                      image_url, banner_url, type_label, os, remain}
        """
        if not self.affid:
            logger.error("ADPICK_AFFID 미설정 → 더미 캠페인 반환")
            return self._dummy_campaigns()

        cache_key = f"{adtype}_{category}_{order}"
        cache_data = {}
        if os.path.exists(self.CACHE_FILE):
            try:
                with open(self.CACHE_FILE, "r", encoding="utf-8") as f:
                    cache_data = json.load(f)
            except Exception as e:
                logger.warning(f"캐시 파일 읽기 실패: {e}")

        now = time.time()
        use_cache = False
        raw = []

        if cache_key in cache_data:
            entry = cache_data[cache_key]
            timestamp = entry.get("timestamp", 0)
            if now - timestamp < self.CACHE_TTL:
                logger.info(f"애드픽 캐시 유효 ({int(now - timestamp)}초 경과) -> 캐시 데이터 사용")
                raw = entry.get("data", [])
                use_cache = True

        if not use_cache:
            params = {"affid": self.affid, "os": "", "adtype": adtype,
                      "category": category, "order": order}
            try:
                logger.info(f"애드픽 API 호출: {self.BASE_URL} params={params}")
                resp = requests.get(self.BASE_URL, params=params, timeout=10)
                resp.raise_for_status()
                raw = resp.json()

                # 캐시 데이터 업데이트
                cache_data[cache_key] = {
                    "timestamp": now,
                    "data": raw
                }
                try:
                    with open(self.CACHE_FILE, "w", encoding="utf-8") as f:
                        json.dump(cache_data, f, ensure_ascii=False, indent=2)
                    logger.info("애드픽 API 응답 캐시 저장 성공")
                except Exception as e:
                    logger.error(f"캐시 파일 쓰기 실패: {e}")
            except Exception as e:
                logger.error(f"애드픽 API 호출 실패: {e}")
                if cache_key in cache_data:
                    logger.info("API 호출 실패 -> 만료된 캐시 데이터 활용(Fallback)")
                    raw = cache_data[cache_key].get("data", [])
                else:
                    logger.info("API 호출 실패 및 캐시 없음 -> 더미 반환")
                    return self._dummy_campaigns()

        # 응답은 항상 리스트 형태
        items = raw if isinstance(raw, list) else []

        campaigns = []
        for item in items[:limit]:
            # 이미지 URL 우선순위: icon256 > icon > banner640x960 > banner1024x500
            images = item.get("apImages", {}) or {}
            image_url = (
                images.get("icon256", "")
                or images.get("icon", "")
                or ""
            )
            banner_url = (
                images.get("banner640x960", "")
                or images.get("banner1024x500", "")
                or images.get("banner640x640", "")
                or images.get("banner640x100", "")
                or ""
            )

            ap_type = str(item.get("apType", ""))
            type_label = AP_TYPE_MAP.get(ap_type, f"기타({ap_type})")

            # 잔여 수량이 0이면 스킵 (소진된 캠페인)
            remain = item.get("apRemain", 0)
            if isinstance(remain, int) and remain <= 0:
                continue

            campaigns.append({
                "id":            item.get("apOffer", ""),
                "title":         item.get("apAppTitle", "").strip(),
                "headline":      item.get("apHeadline", "").strip(),
                # apAppPromoText = 광고 상세 설명 (줄바꿈 포함 긴 텍스트)
                "promo_text":    item.get("apAppPromoText", "").strip(),
                "tracking_link": item.get("apTrackingLink", "").strip(),
                "image_url":     image_url,
                "banner_url":    banner_url,
                "type_label":    type_label,
                "os":            item.get("apOS", "") or "Both",
                "remain":        remain,
            })

        logger.info(f"애드픽 캠페인 {len(campaigns)}개 수집 완료 (소진 제외)")
        return campaigns

    @staticmethod
    def _dummy_campaigns() -> list[dict]:
        """API 키 없을 때 테스트용 더미 데이터."""
        return [
            {
                "id": "dummy001",
                "title": "[테스트] 애드픽 쇼핑메이트 회원가입",
                "headline": "쇼핑정보로 재테크하는 꿀팁! 애드픽 쇼핑메이트",
                "promo_text": "소개하고 싶은 상품을 선택하고, 나만의 수익 링크를 각종 SNS, 커뮤니티 등에 홍보하면 끝!",
                "tracking_link": "https://adpick.co.kr",
                "image_url": "",
                "banner_url": "",
                "type_label": "가입형(CPA)",
                "os": "Both",
                "remain": 999,
            },
            {
                "id": "dummy002",
                "title": "[테스트] 파블로 - 키울수록 돈버는 리워드 앱테크",
                "headline": "Web3.0 학습과 리워드가 결합된 앱테크 플랫폼!",
                "promo_text": "공부하면서 돈 버는 앱! 매일 출석 체크하고 미션 수행하면 보상 지급.",
                "tracking_link": "https://adpick.co.kr",
                "image_url": "",
                "banner_url": "",
                "type_label": "설치형(CPI)",
                "os": "Both",
                "remain": 297,
            },
        ]
