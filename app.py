import streamlit as st
import pandas as pd
import requests

# ---------------------------------------------------------
# 1. 설정
# ---------------------------------------------------------
st.set_page_config(page_title="관측소 전체 조회 (원본)", layout="wide")
st.title("📋 전국 관측소 리스트 (필터링 OFF)")
st.caption("API가 보내주는 모든 정보를 숨김없이 그대로 보여줍니다.")

# API 키
HRFCO_KEY = "F09631CC-1CFB-4C55-8329-BE03A787011E"
try:
    DATA_GO_KEY = st.secrets["public_api_key"]
except:
    DATA_GO_KEY = "5e7413b16c759d963b94776062c5a130c3446edf4d5f7f77a679b91bfd437912"

HEADERS = {'User-Agent': 'Mozilla/5.0'}

# ---------------------------------------------------------
# 2. 한강홍수통제소 (수위) - 모든 컬럼 가져오기
# ---------------------------------------------------------
def get_hrfco_all_columns():
    url = f"http://api.hrfco.go.kr/{HRFCO_KEY}/waterlevel/list.json"
    
    try:
        response = requests.get(url, headers=HEADERS, verify=False, timeout=15)
        data = response.json()
        
        if 'content' in data:
            df = pd.DataFrame(data['content'])
            
            # [수정] 한글 변환을 시도는 하되, 없는 컬럼은 쿨하게 넘어감
            # 혹시 이름이 obsnm이 아니라 other_name 일 수도 있으니 여러개 시도
            rename_map = {
                'wlobscd': '코드',
                'obsnm': '관측소명',
                'station_nm': '관측소명', # 혹시 이걸로 올까봐
                'addr': '주소',
                'agcnm': '관리기관',
                'lat': '위도',
                'lon': '경도'
            }
            # 컬럼 이름 바꾸기 (해당하는 것만 바뀜)
            df = df.rename(columns=rename_map)
            
            # [핵심] 필터링 삭제! 모든 컬럼을 그냥 리턴함
            # 이름을 앞으로 보내기 위해 순서만 살짝 조정
            cols = list(df.columns)
            if '관측소명' in cols:
                cols.insert(0, cols.pop(cols.index('관측소명')))
            if '코드' in cols:
                cols.insert(1, cols.pop(cols.index('코드')))
                
            return df[cols], "성공"
        else:
            return None, "데이터 없음 (Content 비어있음)"
    except Exception as e:
        return None, f"에러: {e}"

# ---------------------------------------------------------
# 3. 환경공단 (수질) - 모든 컬럼 가져오기
# ---------------------------------------------------------
def get_nier_all_columns():
    url = "http://apis.data.go.kr/1480523/WaterQualityService/getMsrstnList"
    params = {"serviceKey": DATA_GO_KEY, "numOfRows": "3000", "pageNo": "1", "returnType": "json"}
    
    try:
        response = requests.get(url, params=params, headers=HEADERS, timeout=20)
        try:
            data = response.json()
            if 'getMsrstnList' in data and 'item' in data['getMsrstnList']:
                df = pd.DataFrame(data['getMsrstnList']['item'])
                
                # 한글 변환 (필터링 X)
                rename_map = {
                    'ptNo': '코드',
                    'ptNm': '측정소명',
                    'addr': '주소',
                    'deptNm': '관리부서'
                }
                df = df.rename(columns=rename_map)
                
                # 순서 조정
                cols = list(df.columns)
                if '측정소명' in cols:
                    cols.insert(0, cols.pop(cols.index('측정소명')))
                    
                return df[cols], "성공"
            return None, "데이터 없음"
        except:
            return None, "응답 형식 에러"
    except Exception as e:
        return None, f"에러: {e}"

# ---------------------------------------------------------
# 4. 메인 화면
# ---------------------------------------------------------
tab1, tab2 = st.tabs(["🌊 수위 관측소 (전체)", "🧪 수질 측정소 (전체)"])

with tab1:
    if st.button("수위 관측소 전체 조회", key="btn1"):
        with st.spinner("가져오는 중..."):
            df, msg = get_hrfco_all_columns()
            if df is not None:
                st.success(f"✅ 총 {len(df)}개 관측소 (숨겨진 컬럼 없이 모두 표시)")
                st.dataframe(df, use_container_width=True)
                
                csv = df.to_csv(index=False).encode('utf-8-sig')
                st.download_button("📥 엑셀 다운로드", csv, "수위관측소_전체.csv")
            else:
                st.error(msg)

with tab2:
    if st.button("수질 측정소 전체 조회", key="btn2"):
        with st.spinner("가져오는 중..."):
            df_q, msg_q = get_nier_all_columns()
            if df_q is not None:
                st.success(f"✅ 총 {len(df_q)}개 측정소")
                st.dataframe(df_q, use_container_width=True)
                
                csv_q = df_q.to_csv(index=False).encode('utf-8-sig')
                st.download_button("📥 엑셀 다운로드", csv_q, "수질측정소_전체.csv")
            else:
                st.error(msg_q)
