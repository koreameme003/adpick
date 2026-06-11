import requests
import config
import re

def generate_blog_post(campaign_info, platform="naver"):
    """
    고품질 원고를 생성하며, 후킹 링크를 [문구](링크) 형식으로 포함합니다.
    """
    print(f"AI 콘텐츠 생성 중 ({platform}): {campaign_info['title']}")
    
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {config.GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    platform_name = "네이버 블로그" if platform == "naver" else "티스토리"
    platform_specific = "네이버 블로그는 이모지를 매우 적극적으로 사용하여 친근하게 작성하세요." if platform == "naver" else "티스토리는 전문적이고 깔끔한 레이아웃으로 작성하세요."
    
    images_count = len(campaign_info.get('images', []))
    image_instr = f"본문 중간중간에 [IMAGE_PLACEHOLDER_1] ~ [IMAGE_PLACEHOLDER_{images_count}] 태그를 삽입하세요." if images_count > 0 else "본문에 이미지 태그([IMAGE_PLACEHOLDER_n])를 넣지 마세요."
    
    video_instr = ""
    if campaign_info.get('video_links'):
        video_instr = f"- 관련 영상: {', '.join(campaign_info['video_links'])}\n본문에 영상 시청을 유도하거나 관련된 언급을 자연스럽게 넣어주세요."
    else:
        video_instr = "관련 영상 정보가 없으므로 영상에 대한 언급은 일체 하지 마세요."

    prompt = f"""
    당신은 한국 최고의 블로그 마케터입니다. 아래 캠페인 정보와 '참고 사이트'에서 수집된 실제 데이터를 바탕으로 {platform_name}용 고품질 포스팅을 작성해 주세요.

    **[중요 지침: 언어 관련]**
    - 본문 내용은 반드시 한국어(한글)로 작성하세요.
    - 다만, 브랜드명이나 필수적인 영어 표현은 사용 가능합니다.
    - 숫자, 이모지, 기본 문장 부호(., !? 등)는 적극 활용하세요.

    [캠페인 기본 정보]
    - 제목: {campaign_info['title']}
    - 주요 내용: {campaign_info['message']}
    - 상세 정보/요약: {campaign_info.get('highlights', '없음')}
    - 제휴 링크: {campaign_info['url']}
    {video_instr}

    [참고 사이트 수집 데이터 - 최우선 활용 지침]
    아래 내용은 실제 다른 블로그나 SNS에서 수집된 매우 구체적이고 생생한 정보입니다. 
    당신의 임무는 **이 참고 데이터를 '본문의 뼈대'로 삼는 것**입니다. 
    1. 수집된 데이터에 있는 구체적인 사례, 수치, 사용자들의 반응, 특징적인 표현들을 **최대한 많이, 그리고 구체적으로** 원고에 포함시키세요.
    2. 단순히 나열하는 것이 아니라, AI의 전문적인 마케팅 문체(후킹, 공감, 스토리텔링)와 자연스럽게 버무려 '실제 체험자가 쓴 것 같은' 신뢰감을 주어야 합니다.
    3. 기본 정보보다 이 참고 데이터에 있는 세부적인 내용들에 더 높은 가중치를 두고 작성해 주세요.
    {campaign_info.get('reference_texts', '수집된 참고 정보 없음 (기본 정보로만 작성)')}

    [작성 가이드라인 - 필독]
    1. 제목: 독자의 시선을 사로잡는 '초강력 후킹 제목'을 최소 2가지 제안하고 하나를 선택해 작성하세요.
    2. 구조화 (필수 섹션):
        - **👋 도입부**: 해당 행사가 왜 핫한지, 왜 지금 관심을 가져야 하는지 스토리텔링으로 시작.
        - **📌 핵심 상세 정보**: 특징, 혜택, 상세 안내 등 **참고 데이터를 기반으로 한 실질적인 정보**를 가독성 있게 정리.
        - **✨ 실체험 포인트/팁**: 참고 데이터에서 추출한 '팁'이나 '주의사항', '사용자 반응' 등을 강조.
        - **🎬 관련 영상 (있는 경우만)**: 홍보 영상에 대한 기대감을 높이는 코멘트 추가.
    3. 링크 처리 (매우 중요):
       - 반드시 **[짧은 후킹 문구](제휴링크URL)** 형식을 사용하세요.
       - **절대로 단락 전체나 긴 문장, 섹션 제목을 대괄호 `[]`로 감싸지 마세요.**
       - 링크 문구는 '연애성향 테스트 확인하기', '상세 정보 확인' 등 **20자 이내의 짧은 문구**로만 한정하세요.
       - 예: [👉 연애성향 테스트 확인하기]({campaign_info['url']})
       - 본문 중간과 하단에 자연스럽게 3회 이상 배치하세요.
    4. 디자인: 이모지를 적절히 섞어 지루하지 않게 구성하고, 문단 사이 여백을 충분히 두세요.
    5. 이미지와 배치 (매우 중요): 
       - {image_instr}
       - **이미지 태그([IMAGE_PLACEHOLDER_n])를 본문 전체에 골고루 분산 배치하세요.**
       - **절대로 2개 이상의 이미지를 연속으로(바로 붙여서) 배치하지 마세요.**
       - 이미지 사이에는 반드시 **최소 2~3개 이상의 텍스트 문단**이 있어야 합니다.
    6. 플랫폼 스타일: {platform_specific}
    7. 공정위 문구: 마지막에 "이 포스팅은 소정의 수익이 발생할 수 있습니다"를 포함하세요.

    **[출력 형식 - 반드시 준수]**
    반드시 아래의 영어 키워드 태그로 구분하여 출력하세요.
    TITLE: [제목]
    CONTENT: [본문]
    TAGS: [태그1, 태그2]
    """

    def clean_non_korean(text):
        if not text: return ""
        # 1. URL 보호 (URL은 영어여야 함)
        url_pattern = r'https?://[^\s\n\)]+'
        urls = re.findall(url_pattern, text)
        placeholder = "URLPT{}" # 언더바 없는 토큰 사용
        for i, url in enumerate(urls):
            text = text.replace(url, placeholder.format(i))
            
        # 2. 이미지 플레이스홀더 보호 [IMAGE_PLACEHOLDER_n]
        text = re.sub(r'\[IMAGE_PLACEHOLDER_(\d+)\]', r'IMGPT\1', text)
        
        # 3. 한글/영어/숫자/문장부호/이모지 유지
        cleaned = re.sub(r'[^가-힣a-zA-Z0-9\s.,!?\'\"\_\-:;()\[\]{}#@&%*+=\>\<~·\U00010000-\U0010ffff]', '', text)
        
        # 4. 이미지 플레이스홀더 및 URL 복원
        cleaned = re.sub(r'IMGPT(\d+)', r'[IMAGE_PLACEHOLDER_\1]', cleaned)
        for i, url in enumerate(urls):
            cleaned = cleaned.replace(placeholder.format(i), url)
            
        return cleaned

    data = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": "당신은 한국어 블로그 포스팅 전문가이자 마케팅 전략가입니다. 반드시 요청된 형식(TITLE:, CONTENT:, TAGS:)을 지켜주세요."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7,
        "max_tokens": 3000
    }

    try:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code != 200:
            print(f"API 오류 발생 ({response.status_code}): {response.text}")
        response.raise_for_status()
        result = response.json()
        content = result['choices'][0]['message']['content']
        
        title = ""
        body = ""
        tags = []
        
        if "TITLE:" in content and "CONTENT:" in content:
            try:
                title_part = content.split("TITLE:")[1].split("CONTENT:")[0].strip()
                content_part = content.split("CONTENT:")[1].split("TAGS:")[0].strip()
                tags_part = content.split("TAGS:")[1].strip() if "TAGS:" in content else ""
                
                title = clean_non_korean(title_part)
                body = clean_non_korean(content_part)
                tags = [clean_non_korean(t.strip()) for t in tags_part.split(",") if t.strip()]
            except Exception as parse_err:
                print(f"파싱 오류: {parse_err}\n원본 내용: {content}")
                title = clean_non_korean(campaign_info['title'])
                body = clean_non_korean(content)
        else:
            print(f"형식 미준수 응답 수신: {content}")
            title = clean_non_korean(campaign_info['title'])
            body = clean_non_korean(content)
            
        return title, body, tags
    except Exception as e:
        import traceback
        print(f"AI 생성 실패 상세 에러:\n{traceback.format_exc()}")
        return campaign_info['title'], f"내용 생성 실패. 상세: {campaign_info['message']}", []
