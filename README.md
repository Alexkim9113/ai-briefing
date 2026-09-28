# METAXIS (AI 브리핑)

국내외 AI 뉴스·논문·정책·유튜브를 매일 자동으로 모아 한 페이지로 보여주는 사이트입니다.

- **비용 0원**: GitHub Actions(공개 저장소 무료)로 수집하고 GitHub Pages(무료)로 게시합니다. 유료 API나 서버가 없습니다.
- **저작권 안전**: 제목, 원문 앞부분에서 자동 발췌한 180자 이내 요약, 원문 링크만 저장합니다. 본문 전체와 원본의 사진·썸네일은 수집하지 않고, 표지는 사이트가 직접 만든 그라데이션 디자인입니다.
- **완전 자동**: 매일 한국시간 오전 6시(오후 6시 보충)에 자동으로 수집하고 사이트를 갱신합니다.

## 처음 한 번만 설정

1. 이 폴더를 GitHub **공개(Public)** 저장소에 올립니다.
2. 저장소 **Settings → Pages → Build and deployment → Source** 를 **GitHub Actions** 로 바꿉니다.
3. **Actions** 탭 → "매일 AI 브리핑" → **Run workflow** 를 한 번 눌러 첫 브리핑을 만듭니다.
4. 사이트 주소: `https://<내 아이디>.github.io/<저장소 이름>/`

## 소스 추가·삭제

`sources.json` 한 파일만 고치면 됩니다.

```json
{"name": "표시 이름", "category": "news_ko", "url": "RSS 주소", "limit": 8, "filter": true}
```

- `category`: `news_ko`, `news_global`, `papers`, `policy`, `youtube` 중 하나
- `limit`: 하루 최대 항목 수(기본 8)
- `filter`: `true` 이면 AI 관련 단어(`ai_keywords`)가 들어간 글만 남깁니다
- 유튜브 채널 추가: `https://www.youtube.com/feeds/videos.xml?channel_id=채널ID`

수집에 실패한 소스는 사이트 맨 아래 "수집 상태"에서 확인할 수 있습니다. 한 소스가 실패해도 나머지는 정상 수집됩니다.

## 직접 실행(선택)

```bash
python briefing.py          # 수집 + site/ 생성 (파이썬 3.9 이상, 설치할 라이브러리 없음)
python briefing.py build    # 저장된 data/ 로 사이트만 다시 생성

# 네트워크 없이 테스트
python tests/make_fixtures.py && python briefing.py --fixtures tests/fixtures
```
