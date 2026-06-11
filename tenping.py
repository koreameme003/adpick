import time
import os
import re
from playwright.sync_api import sync_playwright
import config

def is_headed_supported():
    """브라우저 창(Headed)을 띄울 수 있는 환경인지 확인합니다."""
    import sys
    if sys.platform.startswith('linux'):
        return os.environ.get('DISPLAY') is not None
    return True

def get_tenping_campaigns(limit=10, headless=True):
    # 환경 검색 및 자동 전환
    if not headless and not is_headed_supported():
        print("\n[알림] 현재 환경(Codespaces 등)에서는 브라우저 창을 띄울 수 없습니다.")
        print("자동으로 Headless(백그라운드) 모드로 전환하여 캠페인을 수집합니다.")
        headless = True

    print(f"텐핑에서 고단가 캠페인 {limit}개를 수집합니다...")
    campaigns = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        # 저장된 세션 로드
        context_args = {}
        if os.path.exists(config.TENPING_SESSION_PATH):
            context_args["storage_state"] = config.TENPING_SESSION_PATH
        
        context = browser.new_context(**context_args)
        page = context.new_page()
        
        # 메인 페이지 접속 (캠페인 목록이 메인 페이지에 노출됨)
        page.goto("https://tenping.kr/")
        time.sleep(5)
        
        # 스크롤을 내려 캠페인을 더 불러옴
        for _ in range(3):
            page.mouse.wheel(0, 2000)
            time.sleep(2)
            
        # 캠페인 링크 추출 (a 태그 중 '/Home/Send_Campaign_SNS'를 포함하는 것)
        items = page.query_selector_all("a[href*='/Home/Send_Campaign_SNS']")
        print(f"찾은 항목 수: {len(items)}")
        
        for item in items:
            try:
                text = item.inner_text().strip()
                href = item.get_attribute("href")
                
                if text and href:
                    # 텍스트 형식 분리 (예: "참여 리빙 제목\n상세설명\n오늘 단가 2,200원  오늘 잔여 100건")
                    lines = text.split('\n')
                    if len(lines) >= 3:
                        title = lines[0].strip()
                        desc = lines[1].strip()
                        price_line = lines[-1].strip() # 마지막 줄이 보통 단가/잔여 정보
                        
                        # 금액 추출 (예: "오늘 단가 4,200원 오늘 잔여...")
                        if "단가" in price_line and "원" in price_line:
                            price_str = price_line.split("원")[0].split("단가")[-1].strip()
                            price = int(''.join(filter(str.isdigit, price_str))) if any(c.isdigit() for c in price_str) else 0
                        else:
                            price = 0
                            price_str = "0"
                            
                        campaigns.append({
                            "title": f"[{title.split(' ')[0]}] {title.split(' ', 1)[-1] if ' ' in title else title} - {desc}",
                            "price": price,
                            "price_display": f"{price:,}원",
                            "href": f"https://tenping.kr{href}" if href and not href.startswith("http") else href
                        })
            except Exception as e:
                continue
                
        # 단가 높은 순으로 정렬
        campaigns.sort(key=lambda x: x['price'], reverse=True)
        
        # 상위 N개만 선택
        top_campaigns = campaigns[:limit]
        
        browser.close()
        return top_campaigns

def get_campaign_detail(campaign_url, headless=True):
    # 환경 검색 및 자동 전환
    if not headless and not is_headed_supported():
        print("\n[알림] 현재 환경(Codespaces 등)에서는 브라우저 창을 띄울 수 없습니다.")
        print("자동으로 Headless(백그라운드) 모드로 전환하여 상세 정보를 추출합니다.")
        headless = True

    print(f"캠페인 상세 정보 추출 중: {campaign_url}")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context_args = {}
        if os.path.exists(config.TENPING_SESSION_PATH):
            context_args["storage_state"] = config.TENPING_SESSION_PATH
        context = browser.new_context(**context_args)
        page = context.new_page()
        page.goto(campaign_url, wait_until="networkidle")
        time.sleep(3)
        
        # 상세 내용 및 제휴 링크 추출
        detail = {
            "title": page.query_selector("h2").inner_text().strip() if page.query_selector("h2") else "",
            "description": "",
            "images": [],
            "video_links": [],
            "creative_images": [],
            "affiliate_link": "",
            "highlights": "" # 추가된 상세 요약 텍스트
        }
        
        desc_el = page.query_selector(".description, .campaign-desc, [class*='Desc'], .cont")
        if desc_el:
            detail["description"] = desc_el.inner_text().strip()
            # 기본 설명 이미지 태그 추출
            img_tags = desc_el.query_selector_all("img")
            for img in img_tags:
                src = img.get_attribute("src")
                if src and "http" in src and src not in detail["images"]:
                    detail["images"].append(src)
        
        # 1. 영상 크리에이티브 추출
        try:
            video_section = page.locator("div:has-text('영상 크리에이티브'), section:has-text('영상 크리에이티브'), div:has-text('유튜브')").first
            if video_section.is_visible(timeout=2000):
                # 유튜브 iframe 찾기
                iframes = video_section.locator("iframe[src*='youtube.com']").all()
                for iframe in iframes:
                    src = iframe.get_attribute("src")
                    if src:
                        if "/embed/" in src:
                            video_id = src.split("/embed/")[1].split("?")[0]
                            video_url = f"https://www.youtube.com/watch?v={video_id}"
                            if video_url not in detail["video_links"]:
                                detail["video_links"].append(video_url)
                        else:
                            if src not in detail["video_links"]:
                                detail["video_links"].append(src)
                
                # 유튜브 링크(a 태그) 찾기
                y_links = video_section.locator("a[href*='youtube.com'], a[href*='youtu.be']").all()
                for link in y_links:
                    href = link.get_attribute("href")
                    if href and href not in detail["video_links"]:
                        detail["video_links"].append(href)
        except Exception as ve:
            print(f"[텐핑] 영상 추출 중 오류: {ve}")

        # 2. 이미지 크리에이티브 추출 (그리드 및 리스트 형태 캡처 강화)
        try:
            image_section = page.locator("div:has-text('이미지 크리에이티브'), section:has-text('이미지 크리에이티브'), div:has-text('이미지를 활용'), div:has-text('소문내기 시 아래')").first
            if image_section.is_visible(timeout=3000):
                # <img> 태그뿐만 아니라 <a> 태그의 href(다운로드 링크)도 확인
                img_elements = image_section.locator("img, a[href*='.jpg'], a[href*='.png']").all()
                for el in img_elements:
                    src = el.get_attribute("src") or el.get_attribute("href")
                    if not src or "data:" in src or "icon" in src.lower():
                        src = el.get_attribute("data-src")
                    
                    if src and "http" in src and src not in detail["creative_images"]:
                        # 인덱스 페이지나 다운로드 버튼 아이콘 제외 로직
                        if any(ext in src.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                            detail["creative_images"].append(src)
                
                # 만약 이미지가 부족하다면 섹션 전체에서 다시 탐색
                if len(detail["creative_images"]) < 1:
                    all_imgs = image_section.locator("img").all()
                    for img in all_imgs:
                        src = img.get_attribute("src")
                        if src and "http" in src and "tenping" not in src: # 텐핑 로고 등 제외
                             detail["creative_images"].append(src)
        except Exception as ie:
            print(f"[텐핑] 이미지 크리에이티브 추출 중 오류: {ie}")

        # 3. 추가 정보 및 '소문내기 참고 사이트' 추출
        detail["reference_links"] = []
        try:
            # 1. '소문내기 참고 사이트' 헤더 찾기 (대소문자 및 태그 다양성 대응)
            ref_header = page.get_by_role("heading", name="소문내기 참고 사이트").first
            if ref_header.count() == 0:
                ref_header = page.locator("div:has-text('소문내기 참고 사이트')").first
            
            if ref_header.count() > 0 and ref_header.is_visible(timeout=3000):
                print("[텐핑] '소문내기 참고 사이트' 헤더 발견")
                
                # 헤더의 부모 및 그 주변 형제들을 모두 조사 (넓은 범위 탐색)
                search_areas = [
                    ref_header.locator("xpath=.."), # 부모
                    ref_header.locator("xpath=../.."), # 조부모
                    ref_header.locator("xpath=following-sibling::div") # 바로 다음 형제
                ]
                
                exclude_keywords = [
                    "iryan.kr", "tenping.kr", "profile", "ranking", "guide", "tip",
                    "kakaolink", "facebook.com/sharer", "twitter.com/intent",
                    "naver.me", "band.us", "story.kakao.com", "plus.kakao.com",
                    "instagram.com/tenping", "facebook.com/tenping", "play.google", "apple.com"
                ]

                found_links = []
                for area in search_areas:
                    if area.count() > 0:
                        links = area.locator("a[href^='http']").all()
                        for link in links:
                            href = link.get_attribute("href")
                            if href and not any(k in href.lower() for k in exclude_keywords):
                                if href not in detail["reference_links"]:
                                    detail["reference_links"].append(href)
                
                if detail["reference_links"]:
                    print(f"[텐핑] 참고 사이트 {len(detail['reference_links'])}개 추출 성공")
                
            # (백업/보조) '아래 링크를 참고하여' 문구 기반 탐색
            if not detail["reference_links"]:
                tip_box = page.locator("div:has-text('아래 링크를 참고하여'), div:has-text('참고하여 소문을')").first
                if tip_box.count() > 0:
                    # 해당 문구가 있는 곳의 부모 영역 전체 뒤짐
                    neighbor_links = tip_box.locator("xpath=..//a[href^='http']").all()
                    for link in neighbor_links:
                        href = link.get_attribute("href")
                        if href and not any(k in href.lower() for k in exclude_keywords):
                            if href not in detail["reference_links"]:
                                detail["reference_links"].append(href)
        except Exception as re:
            print(f"[텐핑] 참고 사이트 추출 중 오류: {re}")
            
            # 일반 텍스트 정보 (요점 정리)
            extra_texts = []
            info_sections = page.locator("div:has-text('일정'), div:has-text('장소'), div:has-text('안내'), div:has-text('참고 사항')").all()
            for sec in info_sections[:5]:
                txt = sec.inner_text().strip()
                if txt and 20 < len(txt) < 500:
                    extra_texts.append(txt)
            detail["highlights"] = "\n".join(set(extra_texts))
        except:
            pass
        
        # 제휴 링크 추출
        try:
            link_found = False
            inputs = page.query_selector_all("input")
            for inp in inputs:
                val = inp.get_attribute("value")
                if val and "iryan.kr" in val:
                    detail["affiliate_link"] = val.strip()
                    link_found = True
                    break
            
            if not link_found:
                body_text = page.inner_text()
                import re
                match = re.search(r'https?://iryan\.kr/[a-zA-Z0-9]+', body_text)
                if match:
                    detail["affiliate_link"] = match.group(0)
                    link_found = True
            
            if not link_found:
                link_input = page.locator("input[readonly], input[value*='tenping.kr/Connect/GetLink']").first
                if link_input.is_visible(timeout=2000):
                    detail["affiliate_link"] = link_input.get_attribute("value")
                else:
                    campaign_id = campaign_url.split("campaignId=")[-1].split("&")[0]
                    detail["affiliate_link"] = f"https://tenping.kr/Connect/GetLink?campaignId={campaign_id}"
        except Exception as le:
            print(f"[텐핑] 링크 추출 중 오류: {le}")
            campaign_id = campaign_url.split("campaignId=")[-1].split("&")[0]
            detail["affiliate_link"] = f"https://tenping.kr/Connect/GetLink?campaignId={campaign_id}"

        # 4. 소문 배너 퍼가기 HTML 추출 (대표 이미지 설정을 위해 최상단 삽입용)
        detail["banner_html"] = ""
        try:
            # '소문 배너 퍼가기' 섹션 찾기
            banner_area = page.locator("div:has-text('소문 배너 퍼가기'), section:has-text('소문 배너')").first
            if banner_area.count() > 0 and banner_area.is_visible(timeout=3000):
                # HTML 코드가 포함된 요소 찾기 (보통 '미리보기' 아래의 div나 textarea)
                code_locator = banner_area.locator("xpath=..//div[contains(text(), '<div') or contains(text(), '<a')]").first
                if code_locator.count() == 0:
                    code_locator = banner_area.locator("div[style*='background'], .code-box, textarea").first
                
                if code_locator.count() > 0:
                    detail["banner_html"] = code_locator.inner_text().strip()
                
                # 만약 inner_text로 안되면 value 확인 (textarea인 경우)
                if not detail["banner_html"] or "<div" not in detail["banner_html"]:
                    detail["banner_html"] = code_locator.get_attribute("value") or ""
                
                if detail["banner_html"]:
                    print(f"[텐핑] 소문 배너 HTML 추출 성공 (길이: {len(detail['banner_html'])})")
        except Exception as be:
            print(f"[텐핑] 배너 HTML 추출 중 오류: {be}")

        browser.close()
        return detail
            
def crawl_reference_sites(links, headless=True):
    """참고 사이트 링크들을 방문하여 텍스트 컨텐츠를 추출합니다."""
    if not links:
        return ""
    
    # 환경 검색 및 자동 전환
    if not headless and not is_headed_supported():
        print("\n[알림] 현재 환경(Codespaces 등)에서는 브라우저 창을 띄울 수 없습니다.")
        print("자동으로 Headless(백그라운드) 모드로 전환하여 크롤링을 진행합니다.")
        headless = True

    print(f"[텐핑] 참고 사이트 {len(links)}개 크롤링 시작...")
    collected_texts = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context()
        
        for url in links[:3]: # 최대 3개만 크롤링
            try:
                page = context.new_page()
                print(f" - 크롤링 중: {url}")
                page.goto(url, timeout=30000, wait_until="domcontentloaded")
                time.sleep(2)
                
                # 네이버 블로그인 경우 프레임 처리
                if "blog.naver.com" in url:
                    frame = page.frame_locator("#mainFrame")
                    content = frame.locator(".se-main-container, #postViewArea").inner_text()
                else:
                    # 일반 사이트는 body 텍스트 추출 (너무 길지 않게)
                    content = page.locator("body").inner_text()
                
                if content:
                    # 불필요한 공백 제거 및 요약
                    clean_text = " ".join(content.split())
                    collected_texts.append(f"[참고 사이트 내용 ({url})]\n{clean_text[:1000]}")
                
                page.close()
            except Exception as e:
                print(f" - 크롤링 실패 ({url}): {e}")
                
        browser.close()
    
    return "\n\n".join(collected_texts)

def download_image(url, save_path):
    import requests
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            with open(save_path, 'wb') as f:
                f.write(response.content)
            return True
    except Exception as e:
        print(f"이미지 다운로드 실패: {e}")
    return False

if __name__ == "__main__":
    camps = get_tenping_campaigns(limit=10, headless=False)
    if camps:
        print(f"\n총 {len(camps)}개의 고단가 캠페인을 불러왔습니다.")
