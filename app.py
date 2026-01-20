import streamlit as st
import pandas as pd
import requests
import urllib.parse
import time
import xml.etree.ElementTree as ET # XML 파싱용

# SSL 경고 무시
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.set_page_config(page_title="수질 실시간 조회", layout="wide")
st.title("🧪 수질자동측정망 실시간 데이터 (최종)")
st.caption("파라미터를 'siteId'로 변경하여 용담호 데이터를 정확히 조준합니다.")

# 사용자 정보
USER_KEY = "5e7413b16c759d963b94776062c5a130c3446edf4d5f7f77a679b91bfd437912"
ENCODED_KEY = urllib.parse.quote(USER_KEY)
BASE_URL = "https://apis.data.go.kr/1480523/WaterQualityService/getRealTimeWaterQualityList"

# ---------------------------------------------------------
# [핵심] 금강 수계 주요 지점 코드 (S코드 + WAMIS 코드 혼합 스캔)
# ---------------------------------------------------------
# '다산'이 S02009인 걸로 보아, 금강은 S03xxx일 확률이 매우 높음.
TARGET_STATIONS = [
    {"name": "용담호(추정)", "code": "S03001"}, 
    {"name": "대청호(추정)", "code": "S03002"},
    {"name": "이원(추정)",   "code": "S03003"},
    {"name": "갑천(추정)",   "code": "S03004"},
    # 혹시 모르니 WAMIS 코드도 같이
    {"name": "용담호(WAMIS)", "code": "2003660"},
]

# ---------------------------------------------------------
# 데이터 호출 함수 (siteId 적용)
# ---------------------------------------------------------
def fetch_realtime_data_final(station_code):
    # [수정] ptNo -> siteId로 변경
    params = f"?serviceKey={ENCODED_KEY}&numOfRows=10&pageNo=1&siteId={station_code}"
    full_url = BASE_URL + params
    
    try:
        r = requests.get(full_url, verify=False, timeout=5)
        
        # XML 파싱 (JSON이 잘 안 와서 XML로 직접 뜯음)
        if r.status_code == 200:
            try:
                root = ET.fromstring(r.content)
                
                # 결과 코드 확인
                result_code = root.findtext('.//resultCode')
                if result_code != '00':
                    return None, f"API 에러: {root.findtext('.//resultMsg')}"
                
                # 아이템 추출
                items = root.findall('.//item')
                if items:
                    # 첫 번째 데이터만 가져옴
                    item = items[0]
                    
                    # XML 태그 값 추출 헬퍼
                    def get_val(tag):
                        v = item.findtext(tag)
                        return v if v else "-"
                    
                    # 데이터 매핑 (m01, m02... 이게 뭔지 모르니 일단 다 가져옴)
                    parsed_data = {
                        "지점명": get_val('siteName'), # 서버가 주는 진짜 이름
                        "코드": get_val('siteId'),
                        "시간": get_val('msrDate'), # 혹은 msrTime
                        "수온": get_val('m72'), # 보통 m72 근처가 수온
                        "pH": get_val('m70'),   # m70 근처가 pH
                        "DO": get_val('m69'),   # m69 근처가 DO
                        "탁도": get_val('m29'),  # m29 근처
                        "TOC": get_val('m27'),  # m27 근처
                    }
                    return parsed_data, "성공"
                else:
                    return None, "데이터 없음(Empty)"
            except Exception as e:
                return None, f"XML 파싱 실패: {e}"
        else:
            return None, f"HTTP {r.status_code}"
            
    except Exception as e:
        return None, f"통신 에러: {e}"

# ---------------------------------------------------------
# 메인 UI
# ---------------------------------------------------------
if st.button("🚀 진짜 용담호 찾기 (siteId 적용)", type="primary"):
    
    results = []
    bar = st.progress(0)
    
    for i, station in enumerate(TARGET_STATIONS):
        time.sleep(0.2)
        
        data, msg = fetch_realtime_data_final(station['code'])
        
        if data:
            results.append(data) # 성공한 데이터 추가
        else:
            results.append({
                "지점명": station['name'],
                "코드": station['code'],
                "상태": msg
            })
            
        bar.progress((i+1)/len(TARGET_STATIONS))
        
    st.divider()
    st.subheader("📊 조회 결과")
    
    df = pd.DataFrame(results)
    st.dataframe(df, use_container_width=True)
    
    st.info("""
    **💡 데이터 해석 팁**
    - `siteName`에 '다산'이 아닌 '용담', '대청'이 나오면 성공입니다.
    - `m01`, `m02` 같은 코드는 항목(pH, DO 등)을 의미합니다. 데이터가 나오면 제가 항목 이름을 매칭해 드리겠습니다.
    """)
