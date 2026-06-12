"""
content_writer.py
카테고리별로 최적화된 마크다운 포스팅을 자동 생성한다.
- adpick       : 애드픽 CPA/CPI 캠페인 추천 및 스토리텔링
- ai_news      : HTML 자동 슬라이드 배너 삽입 (애드픽 캠페인 3~5개 회전)
- latest_issue : HTML 자동 슬라이드 배너 삽입
"""

import os
import re
import hashlib
import logging
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from openai import OpenAI
from google import genai

load_dotenv()
logger = logging.getLogger(__name__)

def _now_kst():
    """GitHub Actions(UTC 환경) 및 로컬 모두에서 KST 시간을 정확히 반환"""
    return datetime.now(timezone.utc) + timedelta(hours=9)

def _make_description(body: str, max_len: int = 155) -> str:
    """본문에서 SEO용 meta description 자동 추출 (이모지·마크다운 제거)"""
    text = re.sub(r'<[^>]+>', '', body)
    text = re.sub(r'!\[.*?\]\(.*?\)', '', text)
    text = re.sub(r'\[([^\]]+)\]\(.*?\)', r'\1', text)
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'[*_`~>#\-]', '', text)
    text = re.sub(r'[\U00010000-\U0010ffff]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    if not text:
        return ""
    
    for part in text.split('.'):
        part = part.strip()
        if len(part) > 20:
            desc = (part[:max_len] + '...') if len(part) > max_len else part + '.'
            return desc.replace('"', "'")
            
    desc = (text[:max_len] + '...') if len(text) > max_len else text
    return desc.replace('"', "'")

# 애드픽 동적 슬라이드 배너 생성 로직
SLIDE_BANNER_HTML = """
<style>
.adpick-banner-wrap{{position:relative;overflow:hidden;border-radius:12px;
  background:linear-gradient(135deg,#1e90ff,#00bfff);padding:4px;margin:2em 0;}}
.adpick-banner{{display:flex;transition:transform .5s ease;}}
.adpick-banner-item{{min-width:100%;box-sizing:border-box;
  background:#fff;border-radius:10px;padding:20px 24px;text-align:center;}}
.adpick-banner-item a{{display:block;font-weight:700;font-size:1.05rem;
  color:#1e90ff;text-decoration:none;letter-spacing:-.3px;}}
.adpick-banner-item a:hover{{text-decoration:underline;}}
.adpick-banner-dots{{text-align:center;margin-top:6px;}}
.adpick-banner-dots span{{display:inline-block;width:8px;height:8px;margin:0 3px;
  border-radius:50%;background:#ccc;cursor:pointer;}}
.adpick-banner-dots span.active{{background:#1e90ff;}}
.adpick-notice{{font-size:.72rem;color:#999;text-align:center;margin-top:4px;}}
</style>
<div class="adpick-banner-wrap">
  <div class="adpick-banner" id="adpickBanner">
    {slides}
  </div>
</div>
<div class="adpick-banner-dots" id="adpickDots">{dots}</div>
<p class="adpick-notice">※ 이 배너는 애드픽 제휴마케팅 활동의 일환으로, 링크 클릭 및 전환 발생 시 수수료를 제공받습니다.</p>
<script>
(function(){{
  var items=document.querySelectorAll('#adpickBanner .adpick-banner-item');
  var dots=document.querySelectorAll('#adpickDots span');
  var idx=0;
  function go(n){{
    idx=(n+items.length)%items.length;
    document.getElementById('adpickBanner').style.transform='translateX(-'+idx*100+'%)';
    dots.forEach(function(d,i){{d.className=i===idx?'active':'';}}); 
  }}
  dots.forEach(function(d,i){{d.addEventListener('click',function(){{go(i);}});}});
  setInterval(function(){{go(idx+1);}},4000);
}})();
</script>
"""

def _build_slide_banner(campaigns: list = None) -> str:
    """애드픽 활성 캠페인 리스트를 받아 슬라이드 배너 HTML 동적 생성"""
    banner_items = []
    if campaigns:
        # 최대 5개 추출
        for c in campaigns[:5]:
            title = c.get("title", "")
            headline = c.get("headline", "")
            label = f"📢 [{c.get('type_label', '추천')}] {title} - {headline}"
            banner_items.append({"label": label, "url": c.get("tracking_link", "https://www.adpick.co.kr")})
    
    # 만약 캠페인이 없거나 부족한 경우 디폴트 배너들로 채움
    if not banner_items:
        banner_items = [
            {"label": "💰 집에서 하루 10분! 애드픽으로 부수익 만드는 방법", "url": "https://www.adpick.co.kr"},
            {"label": "📱 요즘 핫한 추천 앱 및 무료 혜택 한눈에 보기", "url": "https://www.adpick.co.kr"},
            {"label": "🎁 간단 회원가입으로 즉시 참여 가능한 이벤트 리스트", "url": "https://www.adpick.co.kr"}
        ]
        
    slides = "\n".join(
        f'<div class="adpick-banner-item"><a href="{item["url"]}" target="_blank" rel="noopener">{item["label"]}</a></div>'
        for item in banner_items
    )
    dots = "\n".join(
        f'<span class="{"active" if i == 0 else ""}"></span>'
        for i in range(len(banner_items))
    )
    return SLIDE_BANNER_HTML.format(slides=slides, dots=dots)

def _parse_ai_response(response_text: str, keyword: str) -> dict:
    """AI 응답 텍스트에서 [TITLE], [SLUG], [BODY]를 파싱하여 반환한다."""
    title = keyword
    slug = ""
    body = response_text

    title_match = re.search(r'\[TITLE\]\s*(.*?)\s*(?=\[SLUG\]|\[BODY\]|$)', response_text, re.IGNORECASE | re.DOTALL)
    slug_match = re.search(r'\[SLUG\]\s*(.*?)\s*(?=\[TITLE\]|\[BODY\]|$)', response_text, re.IGNORECASE | re.DOTALL)
    body_match = re.search(r'\[BODY\]\s*(.*?)\s*(?=\[TITLE\]|\[SLUG\]|$)', response_text, re.IGNORECASE | re.DOTALL)

    if title_match:
        title = title_match.group(1).strip().replace('"', '\\"')
    if slug_match:
        raw_slug = slug_match.group(1).strip().lower()
        slug = re.sub(r'[^a-z0-9-]', '-', raw_slug)
        slug = re.sub(r'-+', '-', slug).strip('-')
    if body_match:
        body = body_match.group(1).strip()

    if not slug:
        h = hashlib.md5(response_text.encode('utf-8')).hexdigest()[:6]
        slug = f"post-{h}"

    if title.startswith("# "):
        title = title[2:].strip().replace('"', '\\"')

    if not title_match and body.startswith("# "):
        lines = body.split("\n")
        first_line = lines[0]
        title = first_line[2:].strip().replace('"', '\\"')
        body = "\n".join(lines[1:]).strip()

    return {"title": title, "slug": slug, "body": body}

FORMAT_INSTRUCTION = """
반드시 아래와 같은 포맷으로만 출력하세요. 다른 인사말이나 설명은 일절 생략하세요:

[TITLE]
(여기에 후킹성이 강한 매력적인 국문 제목을 작성)
[SLUG]
(여기에 제목이나 키워드에 어울리는 3~5단어 내외의 영문 소문자 및 하이픈(-) 조합의 URL 슬러그를 작성. 예: adpick-cpa-campaign)
[BODY]
(여기에 마크다운 형식의 블로그 본문을 작성. 마크다운 첫 줄에 제목(#)은 넣지 마세요.)
"""

class ContentWriter:

    def __init__(self):
        # OpenAI 세팅
        api_key = os.getenv("OPENAI_API_KEY", "")
        self.client = OpenAI(api_key=api_key) if api_key and api_key != "your_openai_api_key_here" else None

        # Gemini 세팅
        gemini_key = os.getenv("GEMINI_API_KEY", "")
        self.gemini_client = None
        self.gemini_enabled = False
        if gemini_key and gemini_key != "your_gemini_api_key_here":
            try:
                self.gemini_client = genai.Client(api_key=gemini_key)
                self.gemini_enabled = True
                logger.info("Google Gemini API 초기화 성공")
            except Exception as e:
                logger.error(f"Google Gemini API 초기화 실패: {e}")

    def generate_blog_post(self, category: str, topic: dict, campaigns: list = None) -> str:
        """카테고리에 따라 적합한 포스팅 본문(마크다운)을 생성한다."""
        if category == "adpick":
            return self._generate_adpick_post(topic)
        elif category == "ai_news":
            return self._generate_ai_news_post(topic, campaigns)
        elif category == "latest_issue":
            return self._generate_latest_issue_post(topic, campaigns)
        else:
            raise ValueError(f"지원하지 않는 카테고리: {category}")

    def write_to_markdown_file(self, category: str, keyword: str, content: str) -> tuple:
        """Jekyll Front Matter를 부착해 _posts 폴더에 파일 저장."""
        output_dir = "_posts"
        os.makedirs(output_dir, exist_ok=True)

        now = _now_kst()
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%Y-%m-%d %H:%M:%S +0900")

        parsed = _parse_ai_response(content, keyword)
        title = parsed["title"]
        slug = parsed["slug"]
        body = parsed["body"]

        # 본문에 간혹 들어가는 잘못된 이미지 도메인 주소 보정
        body = re.sub(r'https?://adpick/assets/images/', r'/adpick/assets/images/', body)

        filename = f"{date_str}-{slug}.md"
        file_path = os.path.join(output_dir, filename)

        cat_map = {"adpick": "adpick", "ai_news": "ai-news", "latest_issue": "latest-issue"}
        tag_map = {
            "adpick": f"{keyword}, 애드픽추천, 제휴마케팅, 돈버는앱",
            "ai_news": "AI뉴스, 인공지능, 최신AI트렌드",
            "latest_issue": "이슈, 실시간트렌드, 핫뉴스",
        }

        # 대표 이미지(썸네일) 파싱 및 기본 이미지 매핑 로직
        img_match = re.search(r'!\[.*?\]\((.*?)\)', body)
        image_path = ""
        if img_match:
            raw_img_path = img_match.group(1).strip()
            # baseurl 제거 처리 (예: /adpick/assets/images/... -> assets/images/...)
            baseurl = "/adpick"
            if raw_img_path.startswith(f"{baseurl}/"):
                image_path = raw_img_path[len(baseurl)+1:]
            elif raw_img_path.startswith("/"):
                image_path = raw_img_path[1:]
            else:
                image_path = raw_img_path
        else:
            # 본문에 이미지가 없을 때 title 해시값 기반으로 기본 이미지 매핑
            h_val = int(hashlib.md5(title.encode('utf-8')).hexdigest(), 16)
            img_idx = (h_val % 17) + 1
            image_path = f"assets/images/{img_idx}.jpg"

        description = _make_description(body)

        # 태그 목록 가공: 대괄호 제거 및 개별 태그 쌍따옴표 처리로 YAML 에러 방지
        raw_tags = tag_map.get(category, keyword)
        tags_list = [t.strip() for t in raw_tags.split(",") if t.strip()]
        cleaned_tags = [t.replace("[", "").replace("]", "").replace('"', '\\"').strip() for t in tags_list]
        formatted_tags = ", ".join(f'"{t}"' for t in cleaned_tags)

        front_matter = (
            f"---\n"
            f"layout: post\n"
            f"title: \"{title}\"\n"
            f"date: {time_str}\n"
            f"permalink: /posts/{slug}/\n"
            f"image: {image_path}\n"
            f"author: admin\n"
            f"description: \"{description}\"\n"
            f"categories: {cat_map.get(category, 'general')}\n"
            f"tags: [{formatted_tags}]\n"
            f"---\n\n"
        )

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(front_matter + body)

        logger.info(f"포스팅 저장 완료: {file_path} (대표 이미지: {image_path})")
        return file_path, slug

    # ────────────────────────────────────────────────
    # 애드픽 포스팅 (CPA/CPI)
    # ────────────────────────────────────────────────
    def _generate_adpick_post(self, topic: dict) -> str:
        if self.gemini_enabled:
            return self._gemini_adpick_post(topic)
        elif self.client:
            return self._gpt_adpick_post(topic)
        return self._fallback_adpick_post(topic)

    def _gemini_adpick_post(self, topic: dict) -> str:
        system = (
            "대한민국 최고 바이럴 마케터·SEO 카피라이터. "
            "스팸성 광고 느낌을 최소화하고, 신뢰성 있는 정보성 가이드나 사용 혜택 중심 스토리텔링을 통해 "
            "독자에게 진정한 가치를 전달하며 가입/설치를 자연스럽게 유도하는 마크다운 포스팅을 작성한다."
        )
        # 이미지 URL이 비어있으면 기본 이미지로 대체 (엑박 방지)
        image_url = topic.get('image_url', '')
        if not image_url or not image_url.startswith('http'):
            h_val = int(hashlib.md5(topic['title'].encode('utf-8')).hexdigest(), 16)
            img_idx = (h_val % 17) + 1
            image_url = f"/adpick/assets/images/{img_idx}.jpg"
        user = f"""
캠페인 정보:
- 제목: {topic['title']}
- 헤드라인: {topic['headline']}
- 캠페인 유형: {topic['type_label']}
- 상세 소개글: {topic['promo_text']}
- 트래킹 링크: {topic['tracking_link']}
- 이미지 경로: {image_url}

규칙:
1. 제목(#): 호기심을 유발하고 유용한 가치를 약속하는 후킹성 매력적인 제목. (예: "매달 나가는 돈 30% 줄이는 비결, 드디어 공개된 대안은?")
2. 서론: 일상적인 공감대나 문제 상황 제시 (예: 고물가, 시간 낭비, 정보 불균형 등)로 독자의 몰입 유도.
3. 본문: 캠페인이 해결해 줄 수 있는 구체적인 혜택과 장점을 3가지 소주제로 나누어 체계적으로 분석.
         글 중간 적절한 위치에 해당 제품/앱의 이미지와 다운로드/가입 버튼(트래킹 링크 활용)을 자연스럽게 융합.
         이미지 표현: ![캠페인이미지]({image_url})
         가입/설치 버튼 표현: <a href="{topic['tracking_link']}" target="_blank" rel="noopener noreferrer" style="display:inline-block;padding:10px 20px;background-color:#1e90ff;color:#fff;text-decoration:none;border-radius:6px;font-weight:bold;">▶ {topic['title']} 자세히 알아보기</a>
4. 결론: 한 줄 총평 및 지금 행동해야 하는 이유 소구 (예: 선착순 혜택, 한정 이벤트 등).
5. 맨 마지막에 공정위 안내 문구 삽입: "이 포스팅은 애드픽 제휴마케팅 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다."
{FORMAT_INSTRUCTION}
"""
        try:
            response = self.gemini_client.models.generate_content(
                model='gemini-2.5-flash',
                contents=user,
                config=genai.types.GenerateContentConfig(
                    system_instruction=system
                )
            )
            return response.text.strip()
        except Exception as e:
            logger.error(f"Gemini API 호출 실패(adpick): {e}")
            return self._gpt_adpick_post(topic)

    def _gpt_adpick_post(self, topic: dict) -> str:
        if not self.client:
            return self._fallback_adpick_post(topic)

        system = (
            "대한민국 최고 바이럴 마케터·SEO 카피라이터. "
            "스팸성 광고 느낌을 최소화하고, 신뢰성 있는 정보성 가이드나 사용 혜택 중심 스토리텔링을 통해 "
            "독자에게 진정한 가치를 전달하며 가입/설치를 자연스럽게 유도하는 마크다운 포스팅을 작성한다."
        )
        # 이미지 URL이 비어있으면 기본 이미지로 대체 (엑박 방지)
        image_url = topic.get('image_url', '')
        if not image_url or not image_url.startswith('http'):
            h_val = int(hashlib.md5(topic['title'].encode('utf-8')).hexdigest(), 16)
            img_idx = (h_val % 17) + 1
            image_url = f"/adpick/assets/images/{img_idx}.jpg"
        user = f"""
캠페인 정보:
- 제목: {topic['title']}
- 헤드라인: {topic['headline']}
- 캠페인 유형: {topic['type_label']}
- 상세 소개글: {topic['promo_text']}
- 트래킹 링크: {topic['tracking_link']}
- 이미지 경로: {image_url}

규칙:
1. 제목(#): 호기심을 유발하고 유용한 가치를 약속하는 후킹성 매력적인 제목.
2. 서론: 일상적인 공감대나 문제 상황 제시로 독자의 몰입 유도.
3. 본문: 캠페인이 해결해 줄 수 있는 구체적인 혜택과 장점을 3가지 소주제로 나누어 체계적으로 분석.
         글 중간 적절한 위치에 해당 제품/앱의 이미지와 다운로드/가입 버튼(트래킹 링크 활용)을 자연스럽게 융합.
         이미지 표현: ![캠페인이미지]({image_url})
         가입/설치 버튼 표현: <a href="{topic['tracking_link']}" target="_blank" rel="noopener noreferrer" style="display:inline-block;padding:10px 20px;background-color:#1e90ff;color:#fff;text-decoration:none;border-radius:6px;font-weight:bold;">▶ {topic['title']} 자세히 알아보기</a>
4. 결론: 한 줄 총평 및 지금 행동해야 하는 이유 소구.
5. 맨 마지막에 공정위 안내 문구 삽입: "이 포스팅은 애드픽 제휴마케팅 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다."
{FORMAT_INSTRUCTION}
"""
        try:
            res = self.client.chat.completions.create(
                model="gpt-4o", temperature=0.8, max_tokens=2500,
                messages=[{"role":"system","content":system},{"role":"user","content":user}]
            )
            return res.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"OpenAI 호출 실패(adpick): {e}")
            return self._fallback_adpick_post(topic)

    def _fallback_adpick_post(self, topic: dict) -> str:
        h = hashlib.md5(topic['title'].encode('utf-8')).hexdigest()[:6]
        slug = f"adpick-{h}"
        title = f"\"모르면 100% 손해!\" 요즘 직장인들 사이 난리난 {topic['title']} 솔직 후기 및 팁"
        
        # 이미지 URL이 비어있으면 기본 이미지로 대체 (엑박 방지)
        image_url = topic.get('image_url', '')
        if not image_url or not image_url.startswith('http'):
            h_val = int(hashlib.md5(topic['title'].encode('utf-8')).hexdigest(), 16)
            img_idx = (h_val % 17) + 1
            image_url = f"/adpick/assets/images/{img_idx}.jpg"
        
        body = f"""
"남들은 다 챙기고 있는데 나만 모르고 살았던 혜택, 혹시 있으신가요?"

인플레이션과 고금리 시대가 계속되면서 일상 속 작은 정보 하나가 지갑의 두께를 결정하는 시대가 되었습니다.
오늘 소개할 **{topic['title']}**은 바로 이러한 고민을 가진 분들에게 혁신적인 해결책으로 자리매김하고 있습니다.

---

## 🔍 {topic['title']}이(가) 대체 무엇이길래?

{topic['title']}은 한마디로 **"{topic['headline']}"**라는 모토를 바탕으로 한 서비스(또는 상품)입니다.
최근 대세로 자리 잡은 스마트한 현대인들의 라이프스타일에 맞추어 설계되었으며, 특히 다음과 같은 문제점을 한 번에 해결해 줍니다.

1. **시간과 에너지 절약**: 복잡한 단계를 최소화하여 누구나 3분 만에 시작할 수 있습니다.
2. **검증된 효율성**: 불필요한 거품을 걷어내고 실 사용자에게 꼭 필요한 알짜 혜택만을 제공합니다.
3. **손쉬운 접근성**: 모바일과 웹 어디서나 간편하게 접근하고 관리할 수 있어 매력적입니다.

---

## ⭐ 놓쳐서는 안 될 3가지 핵심 혜택

### 1. 실용적인 편의성 제공
{topic['promo_text'] or "많은 유저들이 인정하듯 복잡함 없이 직관적인 사용자 경험을 선사합니다."}

### 2. 가속화되는 혜택 체감
실제 가입 및 이용 즉시 독보적인 메리트를 누릴 수 있으며, 추천 리워드 및 연동 혜택이 탄탄합니다.

### 3. 안정적인 플랫폼 신뢰성
사용자 중심의 업데이트를 지속적으로 진행하여 언제나 안전하고 편리하게 지속 가능한 사용성을 보장합니다.

---

## 📸 이미지 및 바로가기

![캠페인이미지]({image_url})

아래 링크를 통해 공식 페이지로 이동하여 상세 내용을 직접 확인하고 가장 빠른 혜택을 챙겨보세요.

<div style="text-align: center; margin: 2em 0;">
  <a href="{topic['tracking_link']}" target="_blank" rel="noopener noreferrer" style="display:inline-block;padding:14px 28px;background-color:#1e90ff;color:#fff;text-decoration:none;border-radius:6px;font-weight:bold;font-size:1.1rem;box-shadow:0 4px 6px rgba(30,144,255,0.3);">
    ▶ {topic['title']} 바로가기
  </a>
</div>

---

## 💡 에디터의 솔직 총평
스마트한 재테크 및 편리한 라이프스타일을 원한다면 지금 시작해 보는 것이 최선의 선택입니다. 망설이는 사이에 선착순 프로모션이나 특별 혜택이 종료될 수 있으니 지금 바로 확인해 보세요!

<br>

---
*이 포스팅은 애드픽 제휴마케팅 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다.*
""".strip()
        return f"[TITLE]\n{title}\n[SLUG]\n{slug}\n[BODY]\n{body}"

    # ────────────────────────────────────────────────
    # AI 뉴스 포스팅 (슬라이드 배너)
    # ────────────────────────────────────────────────
    def _generate_ai_news_post(self, topic: dict, campaigns: list) -> str:
        title = topic.get("title", "오늘의 AI 뉴스")
        summary = topic.get("summary", "")
        source_link = topic.get("link", "")
        banner = _build_slide_banner(campaigns)

        if self.gemini_enabled:
            body_raw = self._gemini_ai_news_body(title, summary, source_link)
        elif self.client:
            system = (
                "AI·기술 전문 블로거. SEO 최적화된 후킹성 제목과 읽기 쉬운 "
                "뉴스 해설 본문(마크다운)을 작성한다."
            )
            user = f"""
뉴스 제목: {title}
요약: {summary}
원문 링크: {source_link}

규칙:
1. 제목(#): 클릭 유도 강한 후킹 문구로 변환 (예 → "전 세계가 주목! ...")
2. 서론: 뉴스 핵심을 2~3문장으로 임팩트 있게 요약
3. 본문: 배경·의미·독자에게 미치는 영향을 3개 소제목으로 상세 설명
4. 결론: 앞으로 주목해야 할 포인트 + 독자 행동 유도
5. 마크다운 본문만 출력 (슬라이드 배너 HTML은 직접 삽입할 것이므로 제외)
{FORMAT_INSTRUCTION}
"""
            try:
                res = self.client.chat.completions.create(
                    model="gpt-4o", temperature=0.75, max_tokens=2000,
                    messages=[{"role":"system","content":system},{"role":"user","content":user}]
                )
                body_raw = res.choices[0].message.content.strip()
            except Exception as e:
                logger.error(f"OpenAI 호출 실패(ai_news): {e}")
                body_raw = self._fallback_ai_news_body(title, summary)
        else:
            body_raw = self._fallback_ai_news_body(title, summary)

        parsed = _parse_ai_response(body_raw, title)
        banner_body = parsed["body"] + f"\n\n---\n\n## 🛒 오늘의 추천 혜택 배너\n\n{banner}"
        
        return f"[TITLE]\n{parsed['title']}\n[SLUG]\n{parsed['slug']}\n[BODY]\n{banner_body}"

    def _gemini_ai_news_body(self, title: str, summary: str, source_link: str) -> str:
        system = (
            "AI·기술 전문 블로거. SEO 최적화된 후킹성 제목과 읽기 쉬운 "
            "뉴스 해설 본문(마크다운)을 작성한다."
        )
        user = f"""
뉴스 제목: {title}
요약: {summary}
원문 링크: {source_link}

규칙:
1. 제목(#): 클릭 유도 강한 후킹 문구로 변환 (예 → "전 세계가 주목! ...")
2. 서론: 뉴스 핵심을 2~3문장으로 임팩트 있게 요약
3. 본문: 배경·의미·독자에게 미치는 영향을 3개 소제목으로 상세 설명
4. 결론: 앞으로 주목해야 할 포인트 + 독자 행동 유도
{FORMAT_INSTRUCTION}
"""
        try:
            response = self.gemini_client.models.generate_content(
                model='gemini-2.5-flash',
                contents=user,
                config=genai.types.GenerateContentConfig(
                    system_instruction=system
                )
            )
            return response.text.strip()
        except Exception as e:
            logger.error(f"Gemini API 호출 실패(ai_news): {e}")
            return self._fallback_ai_news_body(title, summary)

    def _fallback_ai_news_body(self, title: str, summary: str) -> str:
        h = hashlib.md5(title.encode('utf-8')).hexdigest()[:6]
        slug = f"ai-news-{h}"
        body = f"""
지금 AI·IT 업계에서 가장 뜨거운 이슈가 터졌습니다.
{summary or "인공지능 기술이 또 한 번 패러다임을 바꾸는 소식이 들려오고 있습니다."}

---

## 📌 핵심 내용 요약

AI 기술의 발전 속도가 점점 빨라지면서 일상과 산업 전반에 걸친 변화가 가속화되고 있습니다.
이번 뉴스는 그중에서도 특히 **실생활 적용 가능성**이 높은 내용으로, 전문가들 사이에서 큰 반향을 일으키고 있습니다.

## 🔍 이 뉴스가 중요한 이유

1. **산업 변화**: 기존 업무 방식과 비즈니스 모델에 직접적인 영향을 미칩니다.
2. **일상 적용**: 일반 소비자도 곧 체감할 수 있는 실질적인 변화가 예상됩니다.
3. **글로벌 경쟁**: 국내외 기업들이 발 빠르게 대응 전략을 수립 중입니다.

## 💡 앞으로 주목해야 할 포인트

AI 트렌드는 단순한 기술 이슈를 넘어 **투자·취업·교육** 전반에 영향을 미칩니다.
지금 이 흐름을 놓치지 않도록, 최신 AI 뉴스를 매일 팔로우하세요!
""".strip()
        return f"[TITLE]\n🤖 전 세계가 주목! {title}\n[SLUG]\n{slug}\n[BODY]\n{body}"

    # ────────────────────────────────────────────────
    # 최신 이슈 포스팅 (슬라이드 배너)
    # ────────────────────────────────────────────────
    def _generate_latest_issue_post(self, topic: dict, campaigns: list) -> str:
        title = topic.get("title", "오늘의 핫이슈")
        summary = topic.get("summary", "")
        banner = _build_slide_banner(campaigns)

        if self.gemini_enabled:
            body_raw = self._gemini_issue_body(title, summary)
        elif self.client:
            system = "바이럴 콘텐츠 전문가. 후킹성 강한 제목과 몰입감 있는 이슈 해설 마크다운을 작성한다."
            user = f"""
이슈 키워드: {title}
검색 동향: {summary}

규칙:
1. 제목(#): 호기심 폭발 후킹 문구 (예 → "왜 갑자기 모두가 '{title}'을 검색하나?")
2. 서론: 이슈의 배경과 사람들이 관심 갖는 이유를 생생하게 소개
3. 본문: 이슈의 전말·다양한 시각·향후 전망을 3개 소제목으로 상세 서술
4. 결론: 핵심 정리 + 독자에게 액션 촉구
{FORMAT_INSTRUCTION}
"""
            try:
                res = self.client.chat.completions.create(
                    model="gpt-4o", temperature=0.8, max_tokens=2000,
                    messages=[{"role":"system","content":system},{"role":"user","content":user}]
                )
                body_raw = res.choices[0].message.content.strip()
            except Exception as e:
                logger.error(f"OpenAI 호출 실패(latest_issue): {e}")
                body_raw = self._fallback_issue_body(title, summary)
        else:
            body_raw = self._fallback_issue_body(title, summary)

        parsed = _parse_ai_response(body_raw, title)
        banner_body = parsed["body"] + f"\n\n---\n\n## 🛒 오늘의 추천 혜택 배너\n\n{banner}"
        
        return f"[TITLE]\n{parsed['title']}\n[SLUG]\n{parsed['slug']}\n[BODY]\n{banner_body}"

    def _gemini_issue_body(self, title: str, summary: str) -> str:
        system = "바이럴 콘텐츠 전문가. 후킹성 강한 제목과 몰입감 있는 이슈 해설 마크다운을 작성한다."
        user = f"""
이슈 키워드: {title}
검색 동향: {summary}

규칙:
1. 제목(#): 호기심 폭발 후킹 문구 (예 → "왜 갑자기 모두가 '{title}'을 검색하나?")
2. 서론: 이슈의 배경과 사람들이 관심 갖는 이유를 생생하게 소개
3. 본문: 이슈의 전말·다양한 시각·향후 전망을 3개 소제목으로 상세 서술
4. 결론: 핵심 정리 + 독자에게 액션 촉구
{FORMAT_INSTRUCTION}
"""
        try:
            response = self.gemini_client.models.generate_content(
                model='gemini-2.5-flash',
                contents=user,
                config=genai.types.GenerateContentConfig(
                    system_instruction=system
                )
            )
            return response.text.strip()
        except Exception as e:
            logger.error(f"Gemini API 호출 실패(latest_issue): {e}")
            return self._fallback_issue_body(title, summary)

    def _fallback_issue_body(self, title: str, summary: str) -> str:
        h = hashlib.md5(title.encode('utf-8')).hexdigest()[:6]
        slug = f"issue-{h}"
        body = f"""
{summary or "지금 대한민국에서 가장 뜨거운 키워드가 등장했습니다!"}
이슈 하나가 오늘 하루 온라인을 가득 채웠고, 수십만 명이 동시에 검색창에 이 단어를 입력했습니다.

---

## 📌 이슈의 핵심, 30초 만에 파악하기

**{title}** — 이 키워드가 갑자기 급상승한 데에는 분명한 이유가 있습니다.
단순한 해프닝을 넘어 많은 사람들의 공감을 이끌어낸 사회적 맥락이 담겨 있습니다.

## 🔍 다양한 시각으로 본 이번 이슈

1. **화제의 중심**: 이슈의 발단과 전개 과정을 시간순으로 정리했습니다.
2. **여론의 반응**: 각계각층의 다양한 반응과 의견이 엇갈리고 있습니다.
3. **앞으로의 전망**: 이 이슈가 어디까지 이어질지, 전문가 시각을 담았습니다.

## 💬 당신의 생각은?

매일 새로운 이슈가 터지는 세상, 중요한 건 빠른 판단입니다.
오늘 이슈도 북마크해 두고 흐름을 놓치지 마세요!
""".strip()
        return f"[TITLE]\n🔥 왜 갑자기 모두가 '{title}'을 검색하나? 지금 바로 확인하세요\n[SLUG]\n{slug}\n[BODY]\n{body}"


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    writer = ContentWriter()
    
    mock_campaigns = [
        {"title": "애드픽 쇼핑메이트", "headline": "쇼핑정보로 재테크하기", "tracking_link": "https://adpick.co.kr", "type_label": "가입형(CPA)"},
        {"title": "앱테크 파블로", "headline": "공부하며 돈 버는 리워드 앱", "tracking_link": "https://adpick.co.kr", "type_label": "설치형(CPI)"}
    ]

    for cat, topic in [
        ("adpick",       {"title": "앱테크 파블로", "headline": "공부하며 돈 버는 리워드 앱", "promo_text": "매일 공부하며 리워드를 적립하는 신개념 Web3.0 리워드 플랫폼", "tracking_link": "https://adpick.co.kr", "image_url": "https://via.placeholder.com/150", "type_label": "설치형(CPI)"}),
        ("ai_news",      {"title": "Gemini 2.5 출시 임박", "summary": "구글이 새로운 초거대 AI 모델의 마일스톤 업데이트를 준비 중", "link": ""}),
        ("latest_issue", {"title": "실시간 급상승 핫이슈", "summary": "현재 실시간 검색량 5만 건 돌파"}),
    ]:
        print(f"\n{'='*60}")
        content = writer.generate_blog_post(cat, topic, mock_campaigns)
        saved_file, slug = writer.write_to_markdown_file(cat, topic.get("title", "test"), content)
        print(f"[{cat}] 저장 완료: {saved_file} (슬러그: {slug})")
