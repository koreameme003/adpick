import time
import os
from playwright.sync_api import sync_playwright
import config

def debug_tenping():
    print("텐핑 디버깅 시작...")
    
    if os.path.exists(config.TENPING_SESSION_PATH):
        print(f"세션 파일 발견: {config.TENPING_SESSION_PATH}")
    else:
        print("세션 파일이 없습니다! 로그인이 필요합니다.")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context_args = {}
        if os.path.exists(config.TENPING_SESSION_PATH):
            context_args["storage_state"] = config.TENPING_SESSION_PATH
        
        context = browser.new_context(**context_args)
        page = context.new_page()
        
        # 메인 페이지 접속
        page.goto("https://tenping.kr/")
        print("메인 페이지 로딩 대기 중...")
        time.sleep(5)
        
        print(f"현재 URL: {page.url}")
        
        # 캠페인, 소문내기 관련 모든 링크 찾기
        links = page.query_selector_all("a")
        print("\n--- 텐핑 메인 페이지의 전체 링크 목록 추출 ---")
        
        with open("links_output.txt", "w", encoding="utf-8") as f:
            for link in links:
                try:
                    href = link.get_attribute("href")
                    text = link.inner_text().strip()
                    if text and href and href != "#":
                        f.write(f"[{text}] -> {href}\n")
                except:
                    pass
                    
        print("'links_output.txt' 파일에 링크 목록을 저장했습니다.")
        time.sleep(2)
        # 실제 HTML 구조를 파일로 저장
        with open("tenping_debug.html", "w", encoding="utf-8") as f:
            f.write(page.content())
        print("페이지 소스를 'tenping_debug.html'에 저장했습니다.")
        
        # 스크린샷 저장
        page.screenshot(path="tenping_debug.png")
        print("스크린샷을 'tenping_debug.png'에 저장했습니다.")
        
        time.sleep(2)
        browser.close()

if __name__ == "__main__":
    debug_tenping()
