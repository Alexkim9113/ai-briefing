# METAXIS (AI 브리핑)

국내외 AI 뉴스·논문·정책·영상 강연를 매일 자동으로 모아 한 페이지로 보여주는 사이트입니다.

- **비용 0원**: GitHub Actions(공개 저장소 무료)로 수집하고 GitHub Pages(무료)로 게시합니다. 유료 API나 서버가 없습니다.
- **저작권 안전**: 제목, 원문 앞부분에서 자동 발췌한 180자 이내 요약, 원문 링크만 저장합니다. 본문 전체와 원본의 사진·썸네일은 수집하지 않고, 표지는 사이트가 직접 만든 그라데이션 디자인입니다.
- **완전 자동**: 30분마다 GitHub 서버에서 자동으로 수집하고 사이트를 갱신합니다(내 컴퓨터가 꺼져 있어도 동작).

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

- `category`: `news_ko`, `news_global`, `papers`, `policy`, `talks`(영상·강연) 중 하나
- `field`: 논문·연구 분야 표시(예: 의료, 법·윤리·정책, 에너지·환경, 문화·예술)
- `limit`: 하루 최대 항목 수(기본 8)
- `filter`: `true` 이면 AI 관련 단어(`ai_keywords`)가 들어간 글만 남깁니다
- 유튜브 채널 추가: `https://www.youtube.com/feeds/videos.xml?channel_id=채널ID` (현재는 TED·TEDx·TED-Ed의 AI 관련 영상만)
- `keywords`: 이 단어가 제목·설명에 있는 글만 남김, `max_age_days`: 새 글이 드문 소스의 수집 기간(일)

수집에 실패한 소스는 사이트 맨 아래 "수집 상태"에서 확인할 수 있습니다. 한 소스가 실패해도 나머지는 정상 수집됩니다.

## 직접 실행(선택)

```bash
python briefing.py          # 수집 + site/ 생성 (파이썬 3.9 이상, 설치할 라이브러리 없음)
python briefing.py build    # 저장된 data/ 로 사이트만 다시 생성

# 네트워크 없이 테스트
python tests/make_fixtures.py && python briefing.py --fixtures tests/fixtures
```

## 주소(.com)를 바꿀 때

1. 도메인 업체에서 DNS를 GitHub Pages로 연결합니다(`www`는 CNAME → `alexkim9113.github.io`, 루트 도메인은 A 레코드 185.199.108.153 / 109.153 / 110.153 / 111.153).
2. `sources.json` 의 `site.domain` 에 도메인(예: `metaxis.com`)을 적습니다. 사이트 주소, 검색엔진용 정보, 사이트맵, CNAME 파일이 모두 새 주소로 바뀝니다.
3. 저장소 Settings → Pages 에서 Custom domain 과 Enforce HTTPS 를 확인합니다. 예전 github.io 주소는 새 주소로 자동 연결됩니다.

## 데이터 보관

- 수집한 내용은 `data/날짜.json` 에 날짜별로 저장되어 저장소(main 브랜치)에 영구 보관됩니다. 사이트 화면(`site/`)은 매번 이 데이터로 새로 만들어지므로, 디자인이나 주소를 바꿔도 지난 기록은 그대로 남습니다.
- 같은 데이터가 사이트의 `/data/날짜.json` 으로도 공개되어 다른 곳으로 옮길 때 그대로 가져갈 수 있습니다.

## 검색 노출(SEO)

- 모든 페이지에 제목·설명·대표 주소(canonical)·공유 이미지(og.png)·구조화 데이터(JSON-LD)가 들어갑니다.
- `sitemap.xml`, `robots.txt`, RSS(`feed.xml`)를 자동으로 만듭니다.
- 구글 서치 콘솔과 네이버 서치어드바이저에 사이트를 등록한 뒤, 받은 인증 코드를 `sources.json` 의 `google_verification`, `naver_verification` 에 넣으면 됩니다.

## 카테고리 아카이브 · 에디터 글

- 메뉴의 카테고리를 누르면 지금까지 모은 그 카테고리 글을 최신순 8개씩 페이지로 넘겨 볼 수 있어요. 데이터(`data/*.json`)가 쌓이는 만큼 계속 늘어나요.
- 표지 사진은 헤드라인·주요 소식에만 붙어요. 저작권 없는 퍼블릭 도메인(CC0) 사진을 `static/photos/`에 모아 두고 기사 주제에 맞춰 자동으로 골라요. 출처는 `static/photos/credits.json`과 사이트의 '사진 출처' 페이지에 있어요.
- 에디터 글은 사이트의 `editor/write.html`에서 써요. 처음 한 번 GitHub 토큰(ai-briefing 저장소의 Contents 읽기·쓰기 권한)을 넣고 비밀번호 4자리를 정하면, 다음부터는 비밀번호만 넣고 글·사진을 올릴 수 있어요. 토큰은 그 기기 브라우저 안에만 암호화되어 저장되고, 비밀번호를 5번 틀리면 지워져요.
- 글은 `posts/*.json`, 사진은 `posts/img/`에 저장되고 올리는 즉시 사이트가 다시 만들어져요(1~2분).
