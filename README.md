# LivePulse MVP

오프라인 행사에서 참가자가 QR코드로 접속해 실시간 질문에 답변하고, 진행자가 결과를 발표 화면에 시각화하는 실행 가능한 MVP입니다.

프로덕션: [https://livepulse-tau.vercel.app](https://livepulse-tau.vercel.app)

## 구현된 기능

- 행사 생성 및 행사별 고유 코드·QR코드
- 단일 선택 질문과 1~5점 평점 질문
- 질문 순서 변경, 수정, 삭제
- 익명 참가자 세션과 브라우저 재접속 복구
- 질문 열기, 응답 마감, 재오픈, 결과 공개
- 같은 참가자의 재제출 시 기존 답변 갱신
- 진행자·참가자·발표 화면의 실시간 WebSocket 동기화
- 결과 공개 전 참가자·발표 API에서 선택지별 통계 차단
- 막대그래프·원그래프와 평점 평균
- CSV 응답 다운로드
- Supabase PostgreSQL 영속 저장과 로컬·테스트용 SQLite 대체 모드
- 자동 API 문서와 핵심 통합 테스트

## 화면

- 진행자 행사 목록: `/host`
- 행사 관리: `/host/{event_id}`
- 참가자: `/e/{event_code}`
- 발표 화면: `/present/{presentation_token}`
- API 문서: `/docs`

## 실행

Python 3.11 이상을 권장합니다.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
cp .env.example .env.local
uvicorn app.main:app --reload --env-file .env.local --host 0.0.0.0 --port 8000
```

브라우저에서 `http://localhost:8000/host`를 엽니다.

`DATABASE_URL`이 설정되어 있으면 Supabase PostgreSQL을 사용합니다. 비어 있으면
개발·테스트용 SQLite(`LIVEPULSE_DB`)를 사용합니다.

### 데모 행사 생성

```bash
python scripts/seed_demo.py
```

출력된 관리·참가·발표 주소를 각각 열어 전체 흐름을 확인할 수 있습니다.

## 휴대전화로 QR 접속하기

`localhost`는 휴대전화에서 서버 컴퓨터를 가리키지 않습니다. 같은 와이파이에서 서버 컴퓨터의 LAN IP를 사용하거나 HTTPS 터널을 연결하세요.

```bash
# 예시
export PUBLIC_BASE_URL=http://192.168.0.15:8000
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Windows PowerShell에서는 다음과 같이 설정합니다.

```powershell
$env:PUBLIC_BASE_URL="http://192.168.0.15:8000"
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

QR 이미지는 `PUBLIC_BASE_URL`이 있으면 그 주소를 우선 사용합니다.

## Supabase 설정

Supabase 프로젝트 상단의 **Connect** 메뉴에서 두 연결 문자열을 복사합니다.

- `DATABASE_URL`: Transaction Pooler, 포트 `6543`
- `DIRECT_URL`: Session Pooler, 포트 `5432`
- `SUPABASE_URL`: 프로젝트 URL
- `SUPABASE_PUBLISHABLE_KEY`: 공개 클라이언트 키

마이그레이션은 `supabase/migrations/`에 있습니다. LivePulse 업무 테이블은 모두
대소문자를 보존한 `"LivePulse_"` 접두어를 사용하며 RLS가 기본 활성화됩니다.
비밀 연결 문자열은 `.env.local`에만 저장하고 Git에 커밋하지 않습니다.

## Vercel 배포

- 프로젝트: `team-aib/livepulse`
- Framework Preset: `FastAPI`
- 진입점: `app.main:app`
- 함수 리전: 도쿄 `hnd1` — Supabase의 `ap-northeast-1`과 동일 리전
- 런타임 비밀값: `DATABASE_URL`만 Production에 등록

`DIRECT_URL`은 마이그레이션·관리 전용이므로 Vercel 런타임에 등록하지 않습니다.
프로덕션 QR은 요청받은 배포 주소를 자동 사용하므로 `PUBLIC_BASE_URL`이 없어도
정상 동작합니다.

## 테스트

```bash
pip install -r requirements-dev.txt
pytest -q
```

테스트 범위에는 전체 질문 흐름, 통계 비공개, 중복 답변 갱신, 동시 질문 방지,
평점 평균, CSV, WebSocket 초기 스냅샷, DB 쿼리 변환과 PostgreSQL 시간값
직렬화가 포함됩니다.

## 구조

```text
app/
  main.py          FastAPI 라우트와 WebSocket
  service.py       상태 전환, 통계, 도메인 로직
  db.py            Supabase PostgreSQL·SQLite 호환 연결
  schemas.py       요청 데이터 검증
  realtime.py      역할별 WebSocket 연결 관리
  static/          진행자·참가자·발표 화면
supabase/
  migrations/      LivePulse_ 접두어 PostgreSQL 스키마
scripts/
  seed_demo.py     데모 데이터 생성
tests/             통합 테스트
docs/              아키텍처, API, 설정, 주요 결정
LICENSE            GNU GPL v3
```

## 현재 MVP의 의도적인 제한

이 버전은 빠른 현장 검증을 위한 단일 서버 프로토타입입니다.

- 주최자 로그인과 조직별 권한이 아직 없습니다. 같은 서버에 접근 가능한 사용자는 행사 목록을 볼 수 있습니다.
- 현재 접속자 수와 WebSocket 연결은 서버 메모리를 기준으로 하므로 Vercel 다중 인스턴스 운영 전 Supabase Realtime 또는 Redis 기반 공유 계층이 필요합니다.
- `DATABASE_URL`이 없는 로컬 환경에서는 SQLite로 동작합니다. 실제 배포에서는 Supabase PostgreSQL을 사용합니다.
- 행사 종료 취소, 결과 공개 취소, 응답 초기화는 안전을 위해 제공하지 않습니다.
- 종료 행사 자동 삭제 정책은 아직 실행되지 않습니다. 현재 데이터는 명시적으로
  삭제하기 전까지 Supabase에 남으므로, 30일 보존 자동화는 배포 운영 작업에서
  별도로 추가해야 합니다.
- 자유응답, 워드클라우드, 퀴즈, 참가 PIN, SSO는 후속 범위입니다.

## 다음 구현 우선순위

1. 주최자 인증과 행사별 역할 권한
2. Supabase Realtime 기반 다중 인스턴스 실시간 처리
3. 종료 행사 30일 보존 및 자동 정리 작업
4. 현장 운영 로그와 관리자 감사 기록 UI
5. 타이머, 복수 선택, 자유응답 모더레이션
6. 실제 행사장 네트워크 환경의 동시 접속·집중 제출 부하 테스트

## Docker 실행

```bash
PUBLIC_BASE_URL=http://192.168.0.15:8000 docker compose up --build
```

데이터는 `livepulse-data` 볼륨에 저장됩니다.
