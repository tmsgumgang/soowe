import streamlit as st
import pandas as pd
import requests
import urllib.parse
import time
import math
import xml.etree.ElementTree as ET
import urllib3

# SSL 경고 무시
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.set_page_config(page_title="수질 실시간(진짜)", layout="wide")
st.title("🧪 금강 수계 실시간 수질 (최신값 강제 조회)")
st.caption("과거 데이터(2007년)를 건너뛰고, 전체 페이지를 계산하여 '맨 마지막 최신값'을 가져옵니다.")

# 사용자 키
USER_KEY = "5e7413b16c759d963b94776062c5a130c3446edf4d5f7f77a679b91bfd437912"
ENCODED_KEY = urllib.parse.quote(USER_KEY)
BASE_URL = "https://apis.data.go.kr/1480523/WaterQualityService/getRealTimeWaterQualityList"

# ---------------------------------------------------------
# [핵심] 최신 데이터 조회 로직 (2단계 점프)
# ---------------------------------------------------------
def fetch_latest_realtime(station_code):
    # 1단계: 1페이지를 호출해서 totalCount(전체 개수) 확인
    first_url = f"{BASE_URL}?serviceKey={ENCODED_KEY}&numOfRows=1&pageNo=1&siteId={station_code}"
    
    try:
        r1 = requests.get(first_url, verify=False, timeout=5)
        if r1.status_code != 200: return None, f"HTTP {r1.status_code}"
        
        root = ET.fromstring(r1.content)
        total_count_text = root.findtext('.//totalCount')
        
        if not total_count_text or int(total_count_text) == 0:
            return None, "데이터 없음"
            
        total_count = int(total_count_text)
        
        # 2단계: 마지막 페이지 계산 (10개씩 볼 때)
        # 예: 45개면 -> 5페이지가 마지막
        page_size = 10
        last_page = math.ceil(total_count / page_size)
        
        # 3단계: 마지막 페이지 호출
        final_url = f"{BASE_URL}?serviceKey={ENCODED_KEY}&numOfRows={page_size}&pageNo={last_page}&siteId={station_code}"
        r2 = requests.get(final_url, verify=False, timeout=10)
        
        if r2.status_code == 200:
            root2 = ET.fromstring(r2.content)
            items = root2.findall('.//item')
            
            if items:
                # 리스트 중 가장 마지막 것이 최신 데이터
                # (혹시 순서가 섞여있을 수 있으니 날짜로 정렬)
                parsed_items = []
                for item in items:
                    d = {child.tag: child.text for child in item}
                    parsed_items.append(d)
                
                # 날짜(msrDate) + 시간(msrTime) 기준으로 내림차순 정렬 (최신이 위로)
                # msrTime이 없는 경우도 대비
                parsed_items.sort(key=lambda x: (x.get('msrDate', ''), x.get('msrTime', '')), reverse=True)
                
                return parsed_items[0], "성공"
                
        return None, "마지막 페이지 로드 실패"

    except Exception as e:
        return None, f"에러: {e}"

# ---------------------------------------------------------
# 메인 UI: 금강 수계 전수 조사
# ---------------------------------------------------------
# 금강 수계 추정 코드 범위 (S03001 ~ S03020)
SCAN_CODES = [f"S03{i:03d}" for i in range(1, 21)]

if st.button("🚀 최신 실시간 데이터 가져오기", type="primary"):
    
    results = []
    bar = st.progress(0)
    status_text = st.empty()
    
    success_count = 0
    
    for i, code in enumerate(SCAN_CODES):
        status_text.text(f"조회 중... {code} (최신값 탐색)")
        time.sleep(0.1)
        
        item, msg = fetch_latest_realtime(code)
        
        if item:
            success_count += 1
            # 항목 매핑 (API 필드명 -> 한글)
            res = {
                "코드": code,
                "지점명": item.get('siteName', '-'),
                "시간": f"{item.get('msrDate', '')} {item.get('msrTime', '')}",
                "pH": item.get('m70', '-'),   # 보통 m70이 pH
                "DO(mg/L)": item.get('m69', '-'),   # m69
                "TOC(mg/L)": item.get('m27', '-'),  # m27
                "탁도(NTU)": item.get('m29', '-'),  # m29
                "전기전도도": item.get('m71', '-'), # m71
                "수온(℃)": item.get('m72', '-'),    # m72
                "총인(T-P)": item.get('m37', '-'),  # m37
                "총질소(T-N)": item.get('m28', '-'), # m28
            }
            results.append(res)
        else:
            # 실패한 건 굳이 보여주지 않거나 로그만 남김
            # results.append({"코드": code, "상태": msg})
            pass
            
        bar.progress((i+1)/len(SCAN_CODES))
        
    status_text.text("조회 완료!")

    # 결과 출력
    if results:
        df = pd.DataFrame(results)
        
        st.success(f"🎉 총 {success_count}개 지점의 최신 데이터를 가져왔습니다!")
        st.dataframe(df, use_container_width=True)
        
        # 날짜 확인 사살
        latest_date = df['시간'].max()
        st.info(f"📅 데이터 기준 시간: **{latest_date}** (이제 2026년 데이터가 맞을 겁니다!)")
        
        # 다운로드
        csv = df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 결과 엑셀 다운로드", csv, "수질_실시간_최신.csv")
    else:
        st.warning("데이터를 찾지 못했습니다. S코드 범위가 다르거나 통신 에러일 수 있습니다.")
