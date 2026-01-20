import streamlit as st
import pandas as pd
import requests
import urllib.parse
import time

# SSL 경고 무시
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.set_page_config(page_title="수질 실시간 조회", layout="wide")
st.title("🧪 수질자동측정망 실시간 데이터 조회")
st.caption("사용자가 확인한 'getRealTimeWaterQualityList' 주소로 데이터를 호출합니다.")

# ---------------------------------------------------------
# [설정] 사용자 정보 입력
# ---------------------------------------------------------
USER_KEY = "5e7413b16c759d963b94776062c5a130c3446edf4d5f7f77a679b91bfd437912"
ENCODED_KEY = urllib.parse.quote(USER_KEY)

# 사용자 확인 정보: https + getRealTimeWaterQualityList
BASE_URL = "https://apis.data.go.kr/1480523/WaterQualityService/getRealTimeWaterQualityList"

# ---------------------------------------------------------
# [핵심] 주요 지점 코드 매핑 (WAMIS 코드 기준)
# ---------------------------------------------------------
# 수질자동측정망은 WAMIS 코드(7자리)를 공유할 확률이 매우 높습니다.
TARGET_STATIONS = [
    {"name": "용담호", "code": "2003660"}, # 용담댐
    {"name": "대청호", "code": "3008660"}, # 대청댐
    {"name": "이원",   "code": "3008680"},
    {"name": "갑천",   "code": "3009660"},
    {"name": "공주",   "code": "3012640"},
    {"name": "부여",   "code": "3012660"},
]

# ---------------------------------------------------------
# 데이터 호출 함수
# ---------------------------------------------------------
def fetch_realtime_data(station_name, station_code):
    # 파라미터 조립
    # ptNo: 측정소코드 (여기선 WAMIS 코드를 시도)
    # numOfRows: 1 (최신값)
    params = f"?serviceKey={ENCODED_KEY}&numOfRows=1&pageNo=1&returnType=json&ptNo={station_code}"
    full_url = BASE_URL + params
    
    try:
        # HTTPS 접속, 타임아웃 10초
        r = requests.get(full_url, verify=False, timeout=10)
        
        if r.status_code == 200:
            try:
                data = r.json()
                # 데이터 구조 파싱
                if 'getRealTimeWaterQualityList' in data and 'item' in data['getRealTimeWaterQualityList']:
                    items = data['getRealTimeWaterQualityList']['item']
                    if items:
                        return items[0] if isinstance(items, list) else items, "성공"
                return None, "데이터 없음(정상응답)"
            except:
                return None, "JSON 파싱 실패(XML 응답)"
        elif r.status_code == 404:
            return None, "404(주소 오류)"
        elif r.status_code == 500:
            return None, "500(서버 오류)"
        else:
            return None, f"HTTP {r.status_code}"
            
    except Exception as e:
        return None, f"통신 에러: {e}"

# ---------------------------------------------------------
# 메인 UI
# ---------------------------------------------------------
if st.button("🚀 용담호~부여 데이터 가져오기", type="primary"):
    
    results = []
    bar = st.progress(0)
    
    st.write(f"📡 접속 주소: `{BASE_URL}` (HTTPS)")
    
    for i, station in enumerate(TARGET_STATIONS):
        time.sleep(0.2) # 서버 부하 방지
        
        data, msg = fetch_realtime_data(station['name'], station['code'])
        
        if data:
            # 항목 매핑 (API 응답 필드명에 따라 유연하게)
            res = {
                "지점명": station['name'],
                "코드": station['code'],
                "시간": data.get('ymdhm') or data.get('mesureDt') or data.get('dt'),
                "pH": data.get('ph') or data.get('item_ph'),
                "DO": data.get('do') or data.get('item_do'),
                "TOC": data.get('toc') or data.get('item_toc'),
                "탁도": data.get('tur') or data.get('item_tur'),
                "전기전도도": data.get('ec') or data.get('item_ec'),
                "수온": data.get('wtem') or data.get('item_temp'),
                "상태": "✅ 수신"
            }
            results.append(res)
        else:
            # 실패 시 로그
            results.append({
                "지점명": station['name'],
                "코드": station['code'],
                "시간": "-",
                "pH": "-",
                "상태": f"❌ {msg}"
            })
            
        bar.progress((i+1)/len(TARGET_STATIONS))
        
    # 결과 표 출력
    st.divider()
    st.subheader("📊 조회 결과")
    df = pd.DataFrame(results)
    st.dataframe(df, use_container_width=True)
    
    # 팁 제공
    if any(df['상태'].str.contains("404")):
        st.error("여전히 404라면, 'ptNo' 파라미터 이름이 다를 수 있습니다. (예: siteId)")
    elif any(df['상태'].str.contains("데이터 없음")):
        st.warning("정상 응답이지만 데이터가 비어있다면, 코드가 틀렸을 수 있습니다. (S코드를 써야 할 수도 있음)")
    else:
        st.success("🎉 성공입니다! 이 데이터로 그래프를 그리면 됩니다.")
