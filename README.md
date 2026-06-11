# 텐핑 & AI 블로그 자동 포스팅 시스템

이 프로젝트는 텐핑(Tenping)의 고단가 캠페인을 수집하여 AI(Groq Llama 3)를 통해 고품질 블로그 원고를 생성하고, 네이버 및 티스토리에 자동으로 포스팅하는 시스템입니다.

## 주요 기능
- **텐핑 캠페인 수집**: 고단가 캠페인 자동 추출 및 상세 정보/이미지 수집.
- **AI 원고 생성**: Groq API를 사용하여 소문내기 전용 고품질 원고 작성.
- **자동 포스팅**: Playwright를 이용한 네이버/티스토리 자동 업로드 및 이미지 삽입.
- **Codespaces 지원**: GitHub Codespaces 환경에서 즉시 실행 가능.

## 시작하기

### 1. 환경 설정
`config.py.example` 파일을 복사하여 `config.py`를 생성하고 본인의 계정 정보를 입력하세요.

```bash
cp config.py.example config.py
```

### 2. 의존성 설치
```bash
pip install -r requirements.txt
playwright install --with-deps chromium
```

### 3. 실행 방법
```bash
python main.py
```

## GitHub Codespaces에서 사용하기
1. 이 저장소를 본인의 GitHub에 올립니다.
2. `Code` -> `Codespaces` -> `Create codespace on main`을 클릭합니다.
3. 실행 전 `config.py`를 설정하세요.

## 주의 사항
- `config.py`와 세션 파일(`*.json`)은 절대 퍼블릭 저장소에 올리지 마세요.
- 블로그 포스팅 시 공정위 문구가 자동으로 포함됩니다.
