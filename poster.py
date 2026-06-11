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

def post_to_naver(title, body, affiliate_link, campaign_info=None, images=None, headless=True):
    # 환경 검크 및 자동 전환
    if not headless and not is_headed_supported():
        print("\n[알림] 현재 환경(Codespaces 등)에서는 브라우저 창을 띄울 수 없습니다.")
        print("자동으로 Headless(백그라운드) 모드로 전환하여 포스팅을 진행합니다.")
        headless = True

    print("네이버 블로그 포스팅 중...")
    images = images or []
    if campaign_info is None:
        campaign_info = {}
        
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)
            context_args = {}
            if os.path.exists(config.NAVER_SESSION_PATH):
                context_args["storage_state"] = config.NAVER_SESSION_PATH
            
            context = browser.new_context(
                **context_args,
                permissions=["clipboard-read", "clipboard-write"]
            )
            page = context.new_page()
            
            # 1. 블로그 글쓰기 페이지 진입
            write_url = f"https://blog.naver.com/{config.NAVER_ID}?Redirect=Write"
            page.goto(write_url, timeout=60000, wait_until="networkidle")
            time.sleep(5)
            
            print("[네이버] 메인 프레임 대기 중...")
            frame_element = page.wait_for_selector("#mainFrame", timeout=30000)
            main_frame = frame_element.content_frame()
            
            # 2. 팝업 제거
            cancel_selectors = [".se-popup-button-cancel", "button:text-is('취소')", ".btn_cancel", ".se-help-close"]
            for _ in range(3):
                page.keyboard.press("Escape")
                for sel in cancel_selectors:
                    try:
                        btn = main_frame.locator(sel).first
                        if btn.is_visible(timeout=500): btn.click(force=True)
                    except: pass
            
            # 3. 제목 입력
            print("[네이버] 제목 입력 중...")
            title_area = main_frame.locator(".se-documentTitle, .se-title-text").first
            title_area.click(force=True)
            time.sleep(1)
            page.keyboard.press("Control+A")
            page.keyboard.press("Backspace")
            page.keyboard.type(title, delay=50)
            time.sleep(1)
            
            # 본문 영역으로 이동
            page.keyboard.press("Enter")
            time.sleep(1)

            # [추가] 소문 배너 처리
            banner_html = campaign_info.get('banner_html', '')
            if banner_html:
                print("[네이버] 소문 배너 업로드...")
                img_src_match = re.search(r'src=["\'](https?://.*?)["\']', banner_html)
                if img_src_match:
                    img_url = img_src_match.group(1)
                    from tenping import download_image
                    banner_path = os.path.abspath("temp_images/banner_img.jpg")
                    os.makedirs("temp_images", exist_ok=True)
                    if download_image(img_url, banner_path):
                        try:
                            photo_btn = main_frame.locator('button.se-toolbar-button-image, button:has-text("사진")').first
                            if photo_btn.is_visible(timeout=5000):
                                with page.expect_file_chooser(timeout=10000) as fc_info:
                                    photo_btn.click(force=True)
                                file_chooser = fc_info.value
                                file_chooser.set_files(banner_path)
                                time.sleep(4) 
                                page.keyboard.press("Enter")
                                # 배너에 링크 추가
                                page.keyboard.press("Control+k")
                                time.sleep(1)
                                link_input = main_frame.locator('input[placeholder*="URL"], .se-popup-link-input').first
                                if link_input.is_visible(timeout=3000):
                                    link_input.fill(affiliate_link)
                                    page.keyboard.press("Enter")
                                    time.sleep(1.5)
                        except: pass

            # 4. 본문 주입
            print("[네이버] 본문 주입 중 (토큰 및 URL/링크 감지)...")
            # [문구](URL), URL, [IMAGE_PLACEHOLDER_N], 줄바꿈 단위 분할
            tokens = re.split(r'(\[.*?\]\(https?://[^\s\n\)]+\)|https?://[^\s\n]+|\[IMAGE_PLACEHOLDER_\d+\]|\n)', body)
            
            for token in tokens:
                if not token: continue
                
                # 1. 이미지 처리
                if token.startswith("[IMAGE_PLACEHOLDER_"):
                    try:
                        idx_match = re.search(r'\[IMAGE_PLACEHOLDER_(\d+)\]', token)
                        if idx_match:
                            idx = int(idx_match.group(1)) - 1
                            if 0 <= idx < len(images) and os.path.exists(images[idx]):
                                print(f"[네이버] 이미지 업로드: {images[idx]}")
                                with page.expect_file_chooser() as fc_info:
                                    main_frame.locator('button.se-toolbar-button-image, button:has-text("사진")').first.click()
                                file_chooser = fc_info.value
                                file_chooser.set_files(images[idx])
                                time.sleep(4) 
                                # 이미지에 링크 삽입
                                page.keyboard.press("Control+k")
                                time.sleep(1)
                                link_input = main_frame.locator('input[placeholder*="URL"], .se-popup-link-input').first
                                if link_input.is_visible(timeout=3000):
                                    link_input.fill(affiliate_link)
                                    page.keyboard.press("Enter")
                                    time.sleep(1.5)
                                else:
                                    page.keyboard.press("Escape")
                    except: pass
                    continue

                # 2. 마크다운 형식 링크 처리 [문구](URL)
                link_match = re.match(r'\[(.*?)\]\((.*?)\)', token)
                if link_match:
                    link_text = link_match.group(1)
                    link_url = link_match.group(2)
                    print(f"[네이버] 링크 삽입 (카드 유도): {link_text} -> {link_url}")
                    page.keyboard.type(link_text)
                    page.keyboard.press("Enter")
                    page.keyboard.type(link_url)
                    time.sleep(0.5)
                    page.keyboard.press("Enter")
                    time.sleep(3) # 카드 프리뷰 로딩 대기
                    continue

                # 3. URL 처리 (제휴 링크 또는 영상 링크)
                if token.startswith("http"):
                    print(f"[네이버] URL 카드 생성 시도: {token}")
                    page.keyboard.type(token)
                    time.sleep(0.5)
                    page.keyboard.press("Enter")
                    time.sleep(3) # 카드 프리뷰 로딩 대기
                    continue

                if token == '\n':
                    page.keyboard.press("Enter")
                    time.sleep(0.3)
                    continue

                # 4. 일반 텍스트 입력
                page.keyboard.insert_text(token.replace("\r", ""))

            if "소정의" not in body:
                page.keyboard.insert_text(f"\n\n이 포스팅은 소정의 수익이 발생할 수 있습니다.")
                page.keyboard.press("Enter")

            print("\n[네이버] 포스팅 준비 완료!")
            try:
                page.wait_for_event("close", timeout=0)
            except: pass
            browser.close()
    except Exception as e:
        print(f"[네이버] 오류: {e}")
        input("오류 확인 후 엔터를 누르세요 (브라우저 종료)...")
    return True

def post_to_tistory(title, body, affiliate_link, campaign_info=None, images=None, headless=True):
    # 환경 검크 및 자동 전환
    if not headless and not is_headed_supported():
        print("\n[알림] 현재 환경(Codespaces 등)에서는 브라우저 창을 띄울 수 없습니다.")
        print("자동으로 Headless(백그라운드) 모드로 전환하여 포스팅을 진행합니다.")
        headless = True

    print("티스토리 블로그 포스팅 중...")
    images = images or []
    if campaign_info is None:
        campaign_info = {}
        
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)
            context_args = {}
            if os.path.exists(config.TISTORY_SESSION_PATH):
                context_args["storage_state"] = config.TISTORY_SESSION_PATH
            context = browser.new_context(**context_args)
            page = context.new_page()
            
            write_url = f"https://{config.TISTORY_BLOG_NAME}.tistory.com/manage/newpost/"
            page.goto(write_url)
            page.wait_for_selector("#post-title-inp", timeout=10000)
            page.fill("#post-title-inp", title)
            
            editor_frame = page.frame_locator("#editor-tistory_ifr")
            mce_body = editor_frame.locator("body#tinymce")
            mce_body.wait_for(state="visible")
            
            # 1. 마크다운 형식 [문구](링크) 처리 (newline 변환 전 수행하여 매칭 범위를 한 단락으로 제한)
            html_body = re.sub(r'\[(.*?)\]\((https?://.*?)\)', r'<a href="\2" target="_blank" style="color: #3366ff; font-weight: bold; text-decoration: underline;">\1</a>', body)
            
            # 2. 줄바꿈 처리
            html_body = html_body.replace("\n", "<br>")
            
            # 3. 단독 URL 처리 (백업용)
            # 이미 <a> 태그가 된 것은 제외하고 남은 URL들을 처리
            def url_to_link(match):
                url = match.group(0)
                return f'<a href="{url}" target="_blank" style="color: #3366ff; text-decoration: underline;">{url}</a>'
            
            html_body = re.sub(r'(?<!href=")(?<!">)(https?://[^\s<]+)', url_to_link, html_body)

            for i, img_url in enumerate(images):
                placeholder = f"[IMAGE_PLACEHOLDER_{i+1}]"
                img_tag = f"<div style='text-align:center; padding: 20px 0;'><a href='{affiliate_link}' target='_blank'><img src='{img_url}' style='max-width:100%; border-radius:8px;'></a><p style='color:#888; font-size:14px;'>이미지 클릭 시 상세 페이지로 이동합니다.</p></div>"
                html_body = html_body.replace(placeholder, img_tag)
            
            disclosure_html = f"<div style='padding:20px; border-left:4px solid #3366ff;'><a href='{affiliate_link}' style='text-decoration:none; color:#3366ff; font-weight:bold;'>👉 상세 정보 및 신청하기 바로가기</a></div>"
            
            banner_html = campaign_info.get('banner_html', '')
            full_html = f"<div style='font-family:sans-serif; line-height:1.8; color:#333;'>"
            if banner_html:
                if 'href' not in banner_html:
                    banner_html = f"<a href='{affiliate_link}' target='_blank'>{banner_html}</a>"
                full_html += f"<div style='text-align:center; margin-bottom:30px;'>{banner_html}</div>"
            full_html += f"{html_body}<br><br>{disclosure_html}</div>"
            
            mce_body.evaluate("(el, html) => { el.innerHTML = html; }", full_html)
            
            print("\n[티스토리] 포스팅 준비 완료!")
            try:
                page.wait_for_event("close", timeout=0)
            except: pass
            browser.close()
    except Exception as e:
        print(f"[티스토리] 오류: {e}")
        input("오류 확인 후 엔터를 누르세요...")
    return True
