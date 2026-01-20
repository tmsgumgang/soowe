import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import time

# ---------------------------------------------------------
# 설정
# ---------------------------------------------------------
st.set_page_config(page_title="수질자동측정망 통합 관제", layout="wide")
st.title("🧪 수질자동측정망 실시간 통합 관제")
st.caption("공공데이터포털 API와 WAMIS를 연동하여, 어떤 상황에서도 데이터를 확보합니다.")

# 사용자 키 (Decoding 된 상태)
API_KEY = "5e7413b16c759d963b94776062c5a130c3446edf4d5f7f77a679b91bfd437912"

# ---------------------------------------------------------
# [모드 1] 공공데이터포털 API (정석)
# ---------------------------------------------------------
def fetch_api_list():
    """수질자동측정망 측정소 목록을 가져옵니다."""
    url = "http://apis.data.go.kr/1480523/WaterQualityService/getMsrstnList"
    params = {
        "serviceKey": API_KEY,
        "numOfRows": "200",
        "pageNo": "1",
        "returnType": "json"
    }
    try:
        r = requests.get(url, params=params, timeout=5)
        data = r.json()
        if 'getMsrstnList' in data and 'item' in data['getMsrstnList']:
            items = data['getMsrstnList']['item']
            df = pd.DataFrame(items)
            return df, "성공"
    except Exception as e:
        return None, str(e)
    return None, "데이터 없음"

def fetch_api_data(pt_no):
    """실시간 측정 데이터를 가져옵니다."""
    url = "http://apis.data.go.kr/1480523/WaterQualityService/getMeasuringList"
    params = {
        "serviceKey": API_KEY,
        "numOfRows": "1", # 최신 1개
        "pageNo": "1",
        "returnType": "json",
        "ptNo": pt_no
    }
    try:
        r = requests.get(url, params=params, timeout=3)
        data = r.json()
        if 'getMeasuringList' in data and 'item' in data['getMeasuringList']:
            items = data['getMeasuringList']['item']
            return items[0] if isinstance(items, list) else items
    except:
        pass
    return None

# ---------------------------------------------------------
# [모드 2] WAMIS API (백업)
# ---------------------------------------------------------
# 주요 지점 WAMIS 코드 매핑
WAMIS_MAP = {
    "용담호": "2003660", "봉황천": "3012680", "이원": "3008680", 
    "장계": "3001640", "옥천천": "3008640", "대청호": "3008660",
    "현도": "3010660", "갑천": "3009660", "미호강": "3010670",
    "남면": "3011620", "공주": "3012640", "유구천": "3012650",
    "부여": "3012660"
}

def fetch_wamis_data(station_name):
    code = WAMIS_MAP.get(station_name)
    if not code: return None
    
    now = datetime.now().strftime("%Y%m%d")
    url = "http://www.wamis.go.kr:8080/wamis/openapi/wkw/wq_dtdata"
    params = {"basin": "3", "obscd": code, "startdt": now, "enddt": now, "output": "json"}
    
    try:
        r = requests.get(url, params=params, timeout=3)
        data = r.json()
        if 'list' in data and data['list']:
            return data['list'][-1] # 최신값
    except: pass
    return None

# ---------------------------------------------------------
# 메인 로직
# ---------------------------------------------------------
target_stations = ["용담호", "봉황천", "이원", "장계", "옥천천", "대청호", "현도", "갑천", "미호강", "남면", "공주", "유구천", "부여"]

st.subheader("📊 실시간 수질 현황판")

# 1. API 접속 시도
df_api, msg = fetch_api_list()

if df_api is not None:
    st.success(f"✅ API 연결 성공! (총 {len(df_api)}개 측정소 감지)")
    use_wamis = False
else:
    st.warning(f"⚠️ API 접속 불가 ({msg}) -> WAMIS 모드로 자동 전환합니다.")
    use_wamis = True

if st.button("데이터 조회 (새로고침)", type="primary"):
    results = []
    bar = st.progress(0)
    
    for i, name in enumerate(target_stations):
        res = {"지점명": name, "상태": "대기", "pH": "-", "DO": "-", "TOC": "-", "탁도": "-"}
        
        # [Strategy] API 먼저 시도 -> 안 되면 WAMIS
        found_data = None
        
        # 1. API 시도
        if not use_wamis and df_api is not None:
            # 이름으로 코드 찾기
            match = df_api[df_api['ptNm'].str.contains(name, na=False)]
            if not match.empty:
                code = match.iloc[0]['ptNo']
                api_data = fetch_api_data(code)
                if api_data:
                    found_data = {
                        "pH": api_data.get('ph'),
                        "DO": api_data.get('do'),
                        "TOC": api_data.get('toc'),
                        "탁도": api_data.get('tur'),
                        "수온": api_data.get('wtep'),
                        "시간": f"{api_data.get('wmyr')}-{api_data.get('wmmd')} {api_data.get('wmht')}",
                        "소스": "API"
                    }
        
        # 2. API 실패 시 WAMIS 시도
        if not found_data:
            w_data = fetch_wamis_data(name)
            if w_data:
                found_data = {
                    "pH": w_data.get('ph'),
                    "DO": w_data.get('do'),
                    "TOC": w_data.get('toc'),
                    "탁도": w_data.get('tur'),
                    "수온": w_data.get('wtem'),
                    "시간": f"{w_data.get('ymd')} {w_data.get('hm')}",
                    "소스": "WAMIS"
                }

        # 결과 매핑
        if found_data:
            res.update(found_data)
            res['상태'] = f"🟢 수신({found_data['소스']})"
        else:
            res['상태'] = "🔴 수신실패"
            
        results.append(res)
        bar.progress((i+1)/len(target_stations))
        time.sleep(0.1)

    # 표 출력
    st.dataframe(pd.DataFrame(results).set_index("지점명"), use_container_width=True)
    st.caption("※ '수신실패'가 뜨면 해당 지점의 통신 상태를 확인해주세요.")
