import time
import os
from playwright.sync_api import sync_playwright
import config
from login_manager import save_session

def manual_login_tenping():
    print("="*50)
    print("      텐핑 수동 로그인 및 세션 저장 스크립트")
    print("="*50)
    print("브라우저가 열리면 텐핑에 로그인해 주세요.")
    print("로그인이 완료되고 텐핑 메인 화면이 나타나면 자동으로 세션이 저장됩니다.")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        
        page.goto("https://tenping.kr/Account/Login")
        
        try:
            # 텐핑 메인 페이지로 이동할 때까지 대기 (최장 3분)
            page.wait_for_url("https://tenping.kr/", timeout=180000)
            print("\n로그인 완료를 감지했습니다! 세션을 저장합니다...")
            time.sleep(3) # 안정화 
            
            save_session(context, config.TENPING_SESSION_PATH)
            print("세션 저장 성공! 이제 main.py를 실행하실 수 있습니다.")
            
        except Exception as e:
            print(f"\n세션 저장 실패: {e}")
            print("시간이 초과되었거나 창이 닫혔습니다. 다시 시도해 주세요.")
            
        finally:
            browser.close()

if __name__ == "__main__":
    manual_login_tenping()
