import os
import json
import time
from playwright.sync_api import sync_playwright
import config

def save_session(browser_context, path):
    storage = browser_context.storage_state()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(storage, f, ensure_ascii=False, indent=2)
    print(f"세션 저장 완료: {path}")

def load_session(path):
    if os.path.exists(path):
        return path
    return None

def is_headed_supported():
    """브라우저 창(Headed)을 띄울 수 있는 환경인지 확인합니다."""
    import sys
    if sys.platform.startswith('linux'):
        return os.environ.get('DISPLAY') is not None
    return True # Windows/macOS는 기본적으로 지원한다고 가정

def login_naver(headless=False):
    # 환경 검크 및 자동 전환
    if not headless and not is_headed_supported():
        print("\n[알림] 현재 환경(Codespaces 등)에서는 브라우저 창을 띄울 수 없습니다.")
        print("자동으로 Headless(백그라운드) 모드로 전환합니다.")
        headless = True

    print("네이버 로그인 시도 중...")
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=headless)
        except Exception as e:
            if not headless:
                print(f"\n[오류] 브라우저 실행 실패: {e}")
                print("브라우저 창을 띄울 수 없는 환경인 것 같습니다. Headless 모드로 다시 시도합니다.")
                browser = p.chromium.launch(headless=True)
            else:
                raise e
        # 세션 파일이 있으면 로드
        context_args = {}
        if os.path.exists(config.NAVER_SESSION_PATH):
            context_args["storage_state"] = config.NAVER_SESSION_PATH
        
        context = browser.new_context(
            **context_args,
            permissions=["clipboard-read", "clipboard-write"]
        )
        page = context.new_page()
        
        page.goto("https://nid.naver.com/nidlogin.login")
        
        # 로그인 상태인지 확인
        time.sleep(3)
        if "nid.naver.com" not in page.url or "login" not in page.url:
            print("이미 네이버에 로그인되어 있습니다.")
            save_session(context, config.NAVER_SESSION_PATH)
            browser.close()
            return True

        if not headless:
            print("네이버 로그인을 시도합니다. 자동으로 입력되지 않으면 브라우저에서 직접 로그인해 주세요.")
            try:
                # 캡차를 피하기 위해 스크립트로 직접 입력 시도
                page.evaluate(f'document.getElementById("id").value = "{config.NAVER_ID}"')
                page.evaluate(f'document.getElementById("pw").value = "{config.NAVER_PW}"')
                page.click(r"#log\.login")
            except:
                pass
            
            print("브라우저에서 로그인을 완료해 주세요. (2단계 인증 등 포함)")
            print("로그인이 완료되어 네이버 메인 페이지가 나타나면 자동으로 세션이 저장됩니다.")
            
            try:
                # 기기 등록 확인 페이지 감지 및 버튼 클릭 로직 추가
                print("로그인 완료 대기 중... (기기 등록 확인 창이 뜨면 자동으로 처리합니다.)")
                start_wait = time.time()
                while time.time() - start_wait < 120:
                    curr_url = page.url
                    if "deviceConfirm" in curr_url or "nid.naver.com/login/ext/" in curr_url:
                        print(f"기기 등록 확인 페이지 감지: {curr_url}")
                        try:
                            # 더욱 확장된 선택자 리스트 (XPath 및 Playwright 최적화)
                            selectors = [
                                'text="등록안함"',
                                'text="등록 안함"', 
                                '#new\\.dontsave',
                                'a#new\\.dontsave',
                                '.btn_upload > a',
                                'a.btn_upload',
                                'button:has-text("등록안함")',
                                'button:has-text("등록 안함")',
                                '.btn_area > .btn_upload',
                                '[id="new.dontsave"]',
                                '//a[contains(text(), "등록안함")]',
                                '//a[contains(text(), "등록 안함")]',
                                'span:has-text("등록안함")',
                                'span:has-text("등록 안함")'
                            ]
                            
                            # 1. 메인 페이지에서 찾기
                            found = False
                            for selector in selectors:
                                try:
                                    btn = page.locator(selector).first
                                    # 요소가 존재하고 보일 때까지 약간 대기
                                    if btn.count() > 0:
                                        print(f"메인 페이지에서 '{selector}' 버튼 감지. 상태 확인 중...")
                                        if btn.is_visible(timeout=2000):
                                            print(f"클릭 시도: {selector}")
                                            # 클릭 시도 (force=True 및 dispatch_event fallback)
                                            try:
                                                btn.click(force=True, timeout=3000)
                                            except:
                                                btn.dispatch_event("click")
                                            found = True
                                            break
                                except: continue
                                
                            # 2. 메인 페이지에서 못 찾으면 모든 프레임 뒤지기
                            if not found:
                                print("메인 페이지에서 버튼을 찾지 못해 프레임 탐색을 시작합니다.")
                                for frame in page.frames:
                                    if frame == page.main_frame: continue
                                    for selector in selectors:
                                        try:
                                            btn = frame.locator(selector).first
                                            if btn.count() > 0 and btn.is_visible(timeout=1000):
                                                print(f"프레임({frame.name or frame.url})에서 '{selector}' 버튼 발견! 클릭 시도...")
                                                try:
                                                    btn.click(force=True, timeout=3000)
                                                except:
                                                    btn.dispatch_event("click")
                                                found = True
                                                break
                                        except: continue
                                    if found: break
                                    
                            if found:
                                print("로그인 유지/등록안함 처리 완료.")
                                time.sleep(3)
                            else:
                                print("등록안함 버튼을 찾지 못했습니다. 수동 클릭이 필요할 수 있습니다.")
                        except Exception as e:
                            print(f"버튼 처리 중 알림: {e}")
                    
                    if "www.naver.com" in curr_url and "deviceConfirm" not in curr_url:
                        print("네이버 메인 접속 성공.")
                        break
                    time.sleep(2)

                time.sleep(2)
                save_session(context, config.NAVER_SESSION_PATH)
                print("네이버 로그인 성공 및 세션 저장 완료")
                browser.close()
                return True
            except Exception as e:
                print(f"네이버 로그인 대기 시간 초과: {e}")
                browser.close()
                return False
        else:
            print("Headless 모드에서는 네이버 로그인이 제한됩니다. 일반 모드(headless=False)로 실행해 주세요.")
            browser.close()
            return False

def login_tistory(headless=False):
    # 환경 검색 및 자동 전환
    if not headless and not is_headed_supported():
        print("\n[알림] 현재 환경(Codespaces 등)에서는 브라우저 창을 띄울 수 없습니다.")
        print("자동으로 Headless(백그라운드) 모드로 전환합니다.")
        headless = True

    print("티스토리 로그인 시도 중...")
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=headless)
        except Exception as e:
            if not headless:
                print(f"\n[오류] 브라우저 실행 실패: {e}")
                print("브라우저 창을 띄울 수 없는 환경인 것 같습니다. Headless 모드로 다시 시도합니다.")
                browser = p.chromium.launch(headless=True)
            else:
                raise e
        context_args = {}
        context = browser.new_context(
            **context_args,
            permissions=["clipboard-read", "clipboard-write"]
        )
        page = context.new_page()
        
        page.goto("https://www.tistory.com/auth/login")
        
        time.sleep(3)
        if os.path.exists(config.TISTORY_SESSION_PATH) and "tistory.com/auth/login" not in page.url:
            print("이미 티스토리에 로그인되어 있습니다.")
            save_session(context, config.TISTORY_SESSION_PATH)
            browser.close()
            return True

        if not headless:
            print("티스토리 로그인을 시작합니다.")
            try:
                # 1. 노란색 카카오 로그인 버튼 클릭
                kakao_btn = page.locator('.link_kakao, a:has-text("카카오계정으로 로그인")').first
                if kakao_btn.is_visible(timeout=10000):
                    print("카카오 로그인 버튼 클릭...")
                    kakao_btn.click()
                
                # 2. 로그인 정보 입력 시도
                time.sleep(3)
                if "login" in page.url:
                    print("로그인 정보를 입력합니다...")
                    # 아이디/비번 필드 찾기 및 입력
                    id_field = page.locator('input[name="loginId"], #loginId--1').first
                    pw_field = page.locator('input[name="password"], #password--2').first
                    
                    if id_field.is_visible(timeout=5000):
                        id_field.fill(config.TISTORY_ID)
                    if pw_field.is_visible(timeout=5000):
                        pw_field.fill(config.TISTORY_PW)
                        page.keyboard.press("Enter")
                
                # 3. 계속하기 버튼 및 완료 대기
                print("로그인을 완료하고 '계속하기' 버튼이 나오면 클릭하거나 기다려 주세요.")
                start_wait = time.time()
                while time.time() - start_wait < 120:
                    # 계속하기 버튼 자동 클릭 시도
                    try:
                        continue_btn = page.locator('button:has-text("계속하기"), .btn_g.highlight').first
                        if continue_btn.is_visible(timeout=1000):
                            print("'계속하기' 버튼 감지: 클릭합니다.")
                            continue_btn.click()
                    except: pass
                    
                    # 티스토리 홈으로 이동했는지 확인
                    if page.url == "https://www.tistory.com/" or "dashboard" in page.url:
                        print("티스토리 로그인 성공 감지.")
                        break
                    time.sleep(3)

                time.sleep(3)
                save_session(context, config.TISTORY_SESSION_PATH)
                browser.close()
                return True
            except Exception as e:
                print(f"티스토리 로그인 대기 실패: {e}")
                browser.close()
                return False
        return False
        return False

def login_tenping(headless=False):
    # 환경 검색 및 자동 전환
    if not headless and not is_headed_supported():
        print("\n[알림] 현재 환경(Codespaces 등)에서는 브라우저 창을 띄울 수 없습니다.")
        print("자동으로 Headless(백그라운드) 모드로 전환합니다.")
        headless = True

    print("텐핑 로그인 시도 중...")
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=headless)
        except Exception as e:
            if not headless:
                print(f"\n[오류] 브라우저 실행 실패: {e}")
                print("브라우저 창을 띄울 수 없는 환경인 것 같습니다. Headless 모드로 다시 시도합니다.")
                browser = p.chromium.launch(headless=True)
            else:
                raise e
        context_args = {}
        context = browser.new_context(
            **context_args,
            permissions=["clipboard-read", "clipboard-write"]
        )
        page = context.new_page()
        
        page.goto("https://tenping.kr/member/login")
        
        time.sleep(3)
        if os.path.exists(config.TENPING_SESSION_PATH) and "login" not in page.url.lower():
            print("이미 텐핑에 로그인되어 있습니다.")
            save_session(context, config.TENPING_SESSION_PATH)
            browser.close()
            return True

        if not headless:
            print("텐핑 로그인을 시도합니다. 자동으로 입력되지 않으면 직접 입력해 주세요.")
            try:
                placeholder_id = page.get_by_placeholder("휴대폰 번호", exact=False)
                if placeholder_id.count() > 0:
                    placeholder_id.first.fill(config.TENPING_ID)
                
                placeholder_pw = page.get_by_placeholder("비밀번호", exact=False)
                if placeholder_pw.count() > 0:
                    placeholder_pw.first.fill(config.TENPING_PW)
                    page.keyboard.press("Enter")
            except:
                pass
                
            print("텐핑 로그인을 완료하고 메인 페이지로 이동해 주세요.")
            try:
                page.wait_for_url("https://tenping.kr/", timeout=120000)
                time.sleep(2)
                save_session(context, config.TENPING_SESSION_PATH)
                print("텐핑 로그인 성공 및 세션 저장 완료")
                browser.close()
                return True
            except:
                print("텐핑 로그인 대기 시간 초과")
                browser.close()
                return False
        browser.close()
        return False

if __name__ == "__main__":
    # 초기 세션 생성을 위해 브라우저를 띄워 실행
    print("초기 세션 생성을 시작합니다.")
    login_naver(headless=False)
    login_tistory(headless=False)
    login_tenping(headless=False)
