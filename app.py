import streamlit as st
import pandas as pd
import requests
import urllib.parse
import time

st.set_page_config(page_title="수질자동측정망 4번 공략", layout="wide")
st.title("🧪 수질자동측정망 '4번 자료' 직공략")
st.caption("목록 조회가 404라면, 'getMeasuringList(측정정보 조회)'를 바로 찌릅니다.")

# 사용자 키
USER_KEY = "5e7413b16c759d963b94776062c5a130c3446edf4d5f7f77a679b91bfd437912"

# ---------------------------------------------------------
# [핵심] 4번 기능: 측정정보 조회 (getMeasuringList)
# ---------------------------------------------------------
def hit_endpoint_4(station_code):
    # 공공데이터포털 국립환경과학원 수질자동측정망 표준 주소
    base_url = "http://apis.data.go.kr/1480523/WaterQualityService/getMeasuringList"
    
    # 키 인코딩 (필수)
    encoded_key = urllib.parse.quote(USER_KEY)
    
    # 파라미터 조립 (4번 기능 표준 파라미터)
    # ptNo: 측정소코드
    params = f"?serviceKey={encoded_key}&numOfRows=10&pageNo=1&returnType=json&ptNo={station_code}"
    
    full_url = base_url + params
    
    try:
        r = requests.get(full_url, timeout=5)
        
        if r.status_code == 200:
            try:
                data = r.json()
                # 데이터 구조 확인
                if 'getMeasuringList' in data and 'item' in data['getMeasuringList']:
                    items = data['getMeasuringList']['item']
                    if items:
                        # 리스트가 아니라 딕셔너리 하나만 올 수도 있음
                        if isinstance(items, dict): items = [items]
                        return items[0], "성공"
            except:
                pass
        elif r.status_code == 404:
            return None, "404(주소틀림)"
        elif r.status_code == 500:
            return None, "500(서버오류)"
            
    except Exception as e:
        return None, str(e)
        
    return None, "데이터 없음"

# ---------------------------------------------------------
# 코드 스캐닝 (용담호 찾기)
# ---------------------------------------------------------
# 수질자동측정망은 보통 S + 숫자 3자리 ~ 4자리 코드를 씁니다. (금강은 S03xxx 예상)
# 혹은 WAMIS 코드(2003660 등)를 그대로 쓸 수도 있습니다.
CANDIDATE_CODES = [
    # 1. 자동측정망 전용 코드 (S코드) - 금강 권역(S03) 집중 스캔
    *[f"S03{i:03d}" for i in range(1, 20)],
    # 2. WAMIS 코드 (혹시나 해서)
    "2003660", "3012640", "3008680" 
]

# ---------------------------------------------------------
# 메인 UI
# ---------------------------------------------------------
st.info("💡 '4번 기능'을 사용하여 용담호, 대청호 데이터를 찾습니다.")

if st.button("🚀 4번 자료 조회 시작 (코드 스캔)", type="primary"):
    
    results = []
    bar = st.progress(0)
    found_count = 0
    
    status_text = st.empty()
    
    for i, code in enumerate(CANDIDATES_CODES):
        status_text.text(f"스캔 중... {code}")
        
        # 0.1초 딜레이 (서버 보호)
        time.sleep(0.1)
        
        data, msg = hit_endpoint_4(code)
        
        if data:
            # 성공! (데이터가 들어옴)
            found_count += 1
            
            # 항목 매핑 (pH, DO, TOC 등)
            # API마다 필드명이 다를 수 있어 유연하게 처리
            res = {
                "코드": code,
                "시간": data.get('dt') or data.get('ymdhm') or data.get('wmyr'),
                "pH": data.get('ph') or data.get('item_ph'),
                "DO": data.get('do') or data.get('item_do'),
                "TOC": data.get('toc') or data.get('item_toc'),
                "탁도": data.get('tur') or data.get('item_tur'),
                "수온": data.get('wtem') or data.get('item_temp'),
                "전기전도도": data.get('ec') or data.get('item_ec')
            }
            results.append(res)
            
        elif msg == "404(주소틀림)":
            # 404가 계속 뜨면 주소 자체가 틀린 것 (즉시 중단)
            st.error("🚨 4번 기능 주소도 404입니다. 'getMeasuringList'가 아닌 다른 이름일 수 있습니다.")
            st.stop()
            
        bar.progress((i+1)/len(CANDIDATE_CODES))
        
    status_text.text("스캔 완료")

    # 결과 표
    if results:
        st.success(f"🎉 {found_count}개의 데이터를 찾았습니다!")
        df = pd.DataFrame(results)
        st.dataframe(df, use_container_width=True)
        st.caption("위 표에 데이터가 나왔다면 성공입니다. 이제 이 코드들로 그래프를 그리면 됩니다.")
    else:
        st.warning("스캔 결과 데이터가 없습니다. (키 권한 문제거나, 코드가 S03 계열이 아닐 수 있습니다.)")
