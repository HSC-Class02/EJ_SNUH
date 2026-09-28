[![🔗 대시보드 바로가기](https://img.shields.io/badge/🔗_대시보드_바로가기-1751D0?style=for-the-badge)](https://hsc-class02.github.io/EJ_SNUH/)

# 서울대학교병원 DART 재무분석 Agent

Open DART API로 2010년 이후 사업보고서·반기보고서·분기보고서를 수집하고 주요 재무수치와 비율을 계산해 GitHub Pages 대시보드로 배포합니다. 매월 1일 09:00 KST에 자동 갱신됩니다.

## 최초 설정
1. 이 압축파일의 **내용물**을 `HSC-Class02/EJ_SNUH` 저장소 루트에 업로드합니다.
2. Open DART에서 API 인증키를 발급합니다.
3. GitHub 저장소 → Settings → Secrets and variables → Actions → New repository secret에서 이름 `DART_API_KEY`, 값에 발급 키를 입력합니다. 키를 코드에 직접 쓰지 마세요.
4. Settings → Pages → Source를 **GitHub Actions**로 설정합니다.
5. Actions → Update DART dashboard → Run workflow를 한 번 실행합니다.
6. 저장소 우측 About의 톱니바퀴 → Website에 `https://hsc-class02.github.io/EJ_SNUH/`를 입력합니다. About 링크는 GitHub API 권한 없이 파일만으로 자동 변경할 수 없어 최초 1회 수동 설정이 필요합니다.

## 수집·분석 범위
- 2010년 이후 사업/반기/분기보고서
- 수익, 영업이익, 순이익, 자산·부채·자본, 현금흐름, CAPEX, FCF
- 영업·순이익률, 유동·부채·자기자본비율, ROA, ROE, 총자산회전율, CFO/순이익, 이자보상배율
- 서울대학교병원은 비상장 공공병원이므로 PER/PBR/EV/EBITDA 같은 시장가치 지표는 기본 제외합니다. DART 계정과목 명칭이 연도별로 다르면 값이 비어 있을 수 있습니다.

## 국내 Peer Hospitals
| 기관 | 유형 | 비교 관점 |
|---|---|---|
| 서울아산병원 | 상급종합병원 | 대형 중증진료·연구·교육 |
| 삼성서울병원 | 상급종합병원 | 중증진료·첨단의료 투자 |
| 세브란스병원 | 상급종합병원 | 대학병원·연구·교육 |
| 분당서울대학교병원 | 상급종합병원 | 동일 계열·디지털병원 운영 |

Peer는 기능적 유사성 기준 참고 목록이며 재무수치 직접 비교 전 회계기준·법인범위를 확인해야 합니다.

## 로컬 실행
```bash
python -m venv venv
# Windows: venv\Scripts\activate / macOS·Linux: source venv/bin/activate
pip install -r requirements.txt
# Windows PowerShell: $env:DART_API_KEY="발급키"
# macOS·Linux: export DART_API_KEY="발급키"
python -m src.main
python -m http.server 8000 -d docs
```

## 파일 구조
- `src/`: DART 수집·변환 Agent
- `data/raw/`: 공시 목록 원본 메타데이터
- `data/processed/`: 분석 CSV와 오류 로그
- `docs/`: GitHub Pages 대시보드
- `.github/workflows/update-dashboard.yml`: 월간 수집·배포 워크플로

> ZIP에는 운영체제 메타파일이나 기타 숨김파일이 없습니다. 단, GitHub Actions가 요구하는 표준 경로인 `.github` 폴더만 포함합니다.
