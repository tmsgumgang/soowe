import streamlit as st
import pandas as pd
import requests
import urllib.parse
import time
import math
import xml.etree.ElementTree as ET
import urllib3
from datetime import datetime

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.set_page_config(page_title="2026 수질 끝장 추적", layout="wide")
st.title("🧪 금강 수계 최신 데이터 끝장 추적")
st.caption("마지막 페이지 근처를 정밀 수색하여 2026년 데이터를 찾아냅니다.")

USER_KEY = "5e7413b16c759d963b94776062c5a130c3446edf4d5f7f77a679b91bfd437912"
ENCODED_KEY = urllib.parse.quote(USER_KEY)
BASE_URL = "https://apis.data.go.kr/1480523/WaterQualityService/getRealTimeWaterQualityList"

# [확인된 코드]
TARGETS = [
    {"code": "S03008", "name": "용담호"},
    {"code": "S03011", "name": "이원"},
    {"code": "S03003", "name": "대청호"},
    {"code": "S03002", "name": "갑천"},
    {"code": "S03012", "name": "봉황천"},
]

def fetch_deep_search(station_code):
    # 1. 전체 개수 파악
    init_url = f"{BASE_URL}?serviceKey={ENCODED_KEY}&numOfRows=1&pageNo=1&siteId={station_code}"
    
    try:
        r = requests.get(init_url, verify=False, timeout=5)
        root = ET.fromstring(r.content)
        total_str = root.findtext('.//totalCount')
        if not total_str or int(total_str) == 0: return None, "데이터 없음"
        
        total_count = int(total_str)
        page_size = 10
        last_page = math.ceil(total_count / page_size)
        
        # 2. [전략] 마지막 페이지와 그 전 페이지까지 뒤진다 (데이터 누락 방지)
        # API가 실시간 업데이트 중이면 마지막 페이지가 바뀔 수 있음
        pages_to_check = [last_page, last_page - 1] if last_page > 1 else [last_page]
        
        all_items = []
        
        for p in pages_to_check:
            url = f"{BASE_URL}?serviceKey={ENCODED_KEY}&numOfRows={page_size}&pageNo={p}&siteId={station_code}"
            r2 = requests.get(url, verify=False, timeout=5)
            if r2.status_code == 200:
                root2 = ET.fromstring(r2.content)
                items = root2.findall('.//item')
                for item in items:
                    all_items.append({child.tag: child.text for child in item})
        
        if not all_items: return None, "데이터 로드 실패"
        
        # 3. 날짜 기준 내림차순 정렬 (가장 미래의 시간이 0번)
        all_items.sort(key=lambda x: (x.get('msrDate', ''), x.get('msrTime', '')), reverse=True)
        
        return all_items[0], "성공"

    except Exception as e:
        return None, f"에러: {e}"

# --- 메인 ---
if st.button("🚀 최신 데이터 정밀 수색", type="primary"):
    
    results = []
    bar = st.progress(0)
    
    for i, t in enumerate(TARGETS):
        time.sleep(0.1)
        data, msg = fetch_deep_search(t['code'])
        
        if data:
            res = {
                "지점명": t['name'],
                "시간": f"{data.get('msrDate','')} {data.get('msrTime','')}",
                "수온": data.get('m72', '-'),
                "pH": data.get('m70', '-'),
                "DO": data.get('m69', '-'),
                "탁도": data.get('m29', '-'),
                "TOC": data.get('m27', '-'),
                "전기전도도": data.get('m71', '-')
            }
            results.append(res)
        else:
            results.append({"지점명": t['name'], "시간": "실패", "비고": msg})
        
        bar.progress((i+1)/len(TARGETS))
        
    df = pd.DataFrame(results)
    st.subheader("📊 정밀 수색 결과")
    st.dataframe(df, use_container_width=True)
    
    # 최신 날짜 분석
    dates = df['시간'].sort_values(ascending=False).unique()
    latest = dates[0] if len(dates) > 0 else "없음"
    
    if "2026" in str(latest):
        st.success(f"🎉 성공! 2026년 데이터를 찾았습니다. ({latest})")
    elif "2025-11" in str(latest) or "2025-12" in str(latest):
        st.info(f"ℹ️ 현재 API에서 제공하는 가장 최신 데이터는 **{latest}** 입니다. (검증 지연으로 추정)")
        st.caption("공공데이터포털 정책상 '검증 완료된 데이터'만 올라오기 때문에 1~2달 늦을 수 있습니다.")
