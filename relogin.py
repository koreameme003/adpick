import time
from login_manager import login_naver, login_tistory, login_tenping

def relogin_all():
    print("="*50)
    print("   세션 재로그인 도구")
    print("="*50)
    print("이 도구는 네이버, 티스토리, 텐핑의 로그인 세션을 수동으로 갱신합니다.")
    print("브라우저가 열리면 로그인을 완료해 주세요.\n")

    print("[1/3] 네이버 로그인 중...")
    login_naver(headless=False)
    
    print("\n[2/3] 티스토리 로그인 중...")
    login_tistory(headless=False)
    
    print("\n[3/3] 텐핑 로그인 중...")
    login_tenping(headless=False)

    print("\n" + "="*50)
    print("   모든 세션 갱신 완료!")
    print("="*50)
    print("이제 main.py를 실행하여 포스팅을 진행할 수 있습니다.")
    time.sleep(3)

if __name__ == "__main__":
    relogin_all()
