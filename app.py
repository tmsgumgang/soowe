import streamlit as st
import pandas as pd
import requests
import urllib.parse
import time
import xml.etree.ElementTree as ET
import urllib3
from datetime import datetime

# SSL 경고 무시
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.set_page_config(page_title="2026 실시간 수질(최종)", layout="wide")
st.title("🧪 2026년 1월 '진짜' 데이터 조회")
st.caption("2025-11-30(평균값)이 아닌, 2026년 1월 실시간 데이터를 강제 호출합니다.")

# 사용자 키
USER_KEY = "5e7413b16c759d963b94776062c5a130c3446edf4d5f7f77a679b91bfd437912"
ENCODED_KEY = urllib.parse.quote(USER_KEY)
BASE_URL = "https://apis.data.go.kr/1480523/WaterQualityService/getRealTimeWaterQualityList"

# [확인된 코드] 용담, 이원, 대청
TARGETS = [
    {"code": "S03008", "name": "용담호"},
    {"code": "S03011", "name": "이원"},
    {"code": "S03003", "name": "대청호"},
    {"code": "S03002", "name": "갑천"},
]

def fetch_2026_jan_data(station_code):
    # [핵심전략] 연도(wmyr)와 월(wmmd)을 동시에 지정
    # 이렇게 해야 "평균값"이 아니라 "그 달의 데이터"를 뒤지기 시작함
    params = f"?serviceKey={ENCODED_KEY}&numOfRows=10&pageNo=1&siteId={station_code}&wmyr=2026&wmmd=01"
    full_url = BASE_URL + params
    
    try:
        r = requests.get(full_url, verify=False, timeout=5)
        if r.status_code == 200:
            try:
                root = ET.fromstring(r.content)
                items = root.findall('.//item')
                
                if items:
                    # 데이터 파싱
                    parsed_items = []
                    for item in items:
                        d = {child.tag: child.text for child in item}
                        parsed_items.append(d)
                    
                    # 날짜/시간 내림차순 정렬 (가장 최신이 위로)
                    parsed_items.sort(key=lambda x: (x.get('msrDate', ''), x.get('msrTime', '')), reverse=True)
                    
                    # 최신 데이터 리턴
                    return parsed_items[0], "성공"
                else:
                    return None, "2026년 1월 데이터 없음"
            except:
                return None, "XML 파싱 실패"
        return None, f"HTTP {r.status_code}"
    except Exception as e:
        return None, f"통신 에러: {e}"

# --- 메인 실행 ---
if st.button("🚀 2026년 1월 데이터 가져오기", type="primary"):
    
    results = []
    bar = st.progress(0)
    
    for i, t in enumerate(TARGETS):
        time.sleep(0.1)
        data, msg = fetch_2026_jan_data(t['code'])
        
        if data:
            res = {
                "지점명": t['name'],
                "시간": f"{data.get('msrDate','')} {data.get('msrTime','')}",
                "수온": data.get('m72', '-'), # 0-30 범위 예상
                "pH": data.get('m70', '-'),   # 6-9 범위 예상
                "DO": data.get('m69', '-'),   # 5-15 범위 예상
                "탁도": data.get('m29', '-'),
                "TOC": data.get('m27', '-'),
                "전기전도도": data.get('m71', '-')
            }
            results.append(res)
        else:
            results.append({"지점명": t['name'], "시간": "없음", "비고": msg})
            
        bar.progress((i+1)/len(TARGETS))
        
    st.dataframe(pd.DataFrame(results), use_container_width=True)
    st.info("※ 만약 이래도 '없음'이 뜨면, 공공데이터포털에는 2026년 실시간 데이터가 아직 안 올라온 것입니다. (보통 검증 후 공개되어 1~2달 늦습니다)")
