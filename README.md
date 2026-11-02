[![대시보드 바로가기](https://img.shields.io/badge/대시보드_바로가기-1751D0?style=for-the-badge)](https://hsc-class02.github.io/EJ_SNUH/)

# 서울대학교병원 ALIO·DART 재무분석 Agent

서울대학교병원의 ALIO 경영공시를 기본 자료원으로 사용하고, OpenDART에 조회 가능한 공시가 있는 경우 이를 보완 자료로 활용합니다. 매월 1일 09:00 KST에 재무자료를 수집하고 GitHub Pages 대시보드를 갱신합니다.

## 데이터 소스 및 현재 커버리지

- ALIO 기관코드: `C0083` (서울대학교병원)
- ALIO 요약 재무상태표: 항목 `3120`
- ALIO 요약 손익계산서: 항목 `3130`
- 현재 확보한 최신 공시 기준: 2021~2025년 결산자료 5개년
- ALIO 표의 단위(백만원)를 대시보드 저장 단위인 원으로 환산
- DART는 기업코드·공시목록을 확인하고, 재무공시가 없으면 ALIO 자료를 사용

ALIO 요약 재무공시에는 현금흐름표가 포함되어 있지 않으므로 CFO와 FCF는 임의로 추정하지 않고 공란으로 둡니다. 추가 현금흐름 분석에는 외부회계감사보고서 등 상세 재무자료를 별도로 연결해야 합니다.

## 최초 설정

1. 저장소 `HSC-Class02/EJ_SNUH`의 Settings → Pages → Source를 **GitHub Actions**로 설정합니다.
2. ALIO 수집은 공개 공시 페이지를 이용하므로 별도 인증키가 필요하지 않습니다.
3. DART 자료도 조회하려면 OpenDART 인증키를 발급받아 Settings → Secrets and variables → Actions에 `DART_API_KEY` 이름으로 저장합니다. 인증키를 소스코드에 직접 입력하지 마세요.
4. Actions → Update SNUH financial dashboard → Run workflow로 수동 실행할 수 있습니다.
5. 대시보드: https://hsc-class02.github.io/EJ_SNUH/

## 수집·분석 항목

| 구분 | 지표 |
|---|---|
| 손익 | 매출, 영업이익, 당기순이익 |
| 재무상태 | 유동자산, 유동부채, 자산총계, 부채총계, 자본총계 |
| 수익성 | 영업이익률, 순이익률, ROA, ROE |
| 안정성 | 유동비율, 부채비율, 자기자본비율 |
| 현금흐름 | CFO, FCF (ALIO 요약 공시에는 없어 공란 처리) |

비율은 ALIO 요약 재무자료에서 확보 가능한 항목을 사용해 계산합니다. ROA와 ROE는 당기순이익을 기말 자산총계 및 기말 자본총계로 나눈 단순 비율입니다. 동종 병원 간 직접 비교 시에는 회계기준과 법인 범위를 먼저 확인해야 합니다.

## 국내 Peer Hospitals

| 기관 | 유형 | 비교 관점 |
|---|---|---|
| 서울아산병원 | 상급종합병원 | 대형 중증진료·연구·교육 |
| 삼성서울병원 | 상급종합병원 | 중증진료·첨단의료 투자 |
| 세브란스병원 | 상급종합병원 | 대학병원·연구·교육 |
| 분당서울대학교병원 | 상급종합병원 | 동일 계열·디지털병원 운영 |

## 주요 파일

- `src/fetch_alio.py`: ALIO 보고서 HTML 수집 및 재무표 파싱
- `src/fetch_dart.py`: OpenDART 기업코드 및 공시목록 조회
- `src/main.py`: 데이터 소스 선택, 지표 계산 및 JSON/CSV 출력
- `data/raw/alio/`: 수집한 ALIO 원본 HTML
- `data/processed/financials.csv`: 분석용 재무자료
- `data/processed/errors.json`: 소스별 수집 오류 기록
- `docs/data.json`: 대시보드 데이터
- `.github/workflows/update-dashboard.yml`: 월간 수집 및 Pages 배포

## 로컬 실행

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python -m unittest discover -s tests -v
# DART_API_KEY가 설정되어 있으면 DART도 확인하고, 없거나 재무공시가 없으면 ALIO를 사용합니다.
python -m src.main
python -m http.server 8000 -d docs
```
