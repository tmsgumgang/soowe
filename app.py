import streamlit as st
import pandas as pd
import requests
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta
import platform

# ---------------------------------------------------------
# 1. 기본 설정
# ---------------------------------------------------------
st.set_page_config(page_title="금강 수위-수질 상관관계 분석", layout="wide")

# 한글 폰트 설정 (OS별 호환, 폰트 없을 시 에러 방지용 try-except)
try:
    system_name = platform.system()
    if system_name == 'Darwin': # Mac
        plt.rc('font', family='AppleGothic') 
    elif system_name == 'Windows': # Windows
        plt.rc('font', family='Malgun Gothic') 
    else: # Linux (Streamlit Cloud)
        plt.rc('font', family='NanumGothic')
    plt.rc('axes', unicode_minus=False)
except:
    pass # 폰트 설정 실패해도 앱은 죽지 않게 함

# API 키 가져오기
try:
    API_KEY = st.secrets["public_api_key"]
except FileNotFoundError:
    st.error("⚠️ API 키 설정을 찾을 수 없습니다. Streamlit Cloud의 Secrets에 'public_api_key'를 등록해주세요.")
    st.stop()

# ---------------------------------------------------------
# 2. 데이터 수집 함수 (디버깅 강화 버전)
# ---------------------------------------------------------

@st.cache_data(ttl=3600)
def get_kwater_level(dam_code, wal_code, start_date, end_date):
    """
    K-water 시간단위 수위 정보 조회 (에러 확인용 디버깅 코드 포함)
    """
    url = "https://apis.data.go.kr/B500001/dam/excllncobsrvt/hourwal/hourwallist"
    
    params = {
        "serviceKey": API_KEY,
        "_type": "json",  # JSON 형식 요청
        "numOfRows": "999",
        "pageNo": "1",
        "sdate": start_date.strftime("%Y-%m-%d"),
        "stime": "00",
        "edate": end_date.strftime("%Y-%m-%d"),
        "etime": "23",
        "damcode": dam_code,
        "wal": wal_code
    }
    
    try:
        # SSL 인증서 무시 (공공데이터포털 호환성)
        response = requests.get(url, params=params, verify=False)
        
        # 1. HTTP 상태 코드 확인
        if response.status_code != 200:
            st.error(f"❌ 서버 연결 실패 (HTTP Status: {response.status_code})")
            return pd.DataFrame()

        # 2. 응답 내용 파싱 시도
        try:
            data = response.json()
        except Exception:
            # JSON 변환 실패 시 (보통 XML 에러 메시지인 경우)
            st.error("❌ 서버가 JSON이 아닌 응답을 보냈습니다. (에러 메시지 확인 필요)")
            st.code(response.text[:500]) # 에러 내용 화면에 출력
            return pd.DataFrame()

        # 3. 데이터 구조 확인 (에러가 가장 많이 나는 곳)
        # 정상 응답: {'response': {'body': {'items': ... }}}
        if 'response' not in data:
            st.error("❌ API 응답에 'response' 필드가 없습니다. (키 등록 대기중일 수 있음)")
            st.write("▼ 서버 응답 내용:")
            st.json(data) # 응답 내용 전체 출력
            return pd.DataFrame()
            
        if 'body' not in data['response']:
            st.error("❌ API 응답에 'body' 필드가 없습니다.")
            st.write(data)
            return pd.DataFrame()

        items = data['response']['body']['items']
        
        # 데이터가 비어있는 경우 (items가 빈 문자열이거나 None일 때)
        if not items:
            st.warning(f"⚠️ 해당 기간({start_date}~{end_date})에 조회된 데이터가 없습니다.")
            return pd.DataFrame()

        # item 리스트 추출
        item_list = items.get('item', [])
        
        # 데이터가 1건일 경우 dict 형태이므로 list로 변환
        if isinstance(item_list, dict):
            item_list = [item_list]
            
        df = pd.DataFrame(item_list)
        
        # 필수 컬럼 존재 여부 확인
        if 'obsrdt' not in df.columns or 'flux' not in df.columns:
            st.error("❌ 데이터에 필요한 컬럼(obsrdt, flux)이 없습니다.")
            st.dataframe(df.head())
            return pd.DataFrame()

        # 데이터 형변환
        df['datetime'] = pd.to_datetime(df['obsrdt'])
        df['water_level'] = pd.to_numeric(df['flux'])
        
        return df[['datetime', 'water_level']].sort_values('datetime')
        
    except Exception as e:
        st.error(f"데이터 처리 중 알 수 없는 오류 발생: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=3600)
def get_water_quality(site_code, start_date, end_date):
    """
    수질 데이터 (현재는 테스트용 더미 데이터 반환)
    """
    # 실제 API 연동 시 이곳을 수정하세요.
    dates = pd.date_range(start=start_date, end=end_date + timedelta(hours=23), freq='H')
    import numpy as np
    
    dummy_data = []
    for d in dates:
        dummy_data.append({
            'datetime': d,
            'toc': np.random.uniform(2.0, 9.0),
            'chla': np.random.uniform(5.0, 45.0)
        })
    
    df = pd.DataFrame(dummy_data)
    st.info("ℹ️ 수질 데이터는 현재 테스트용(Dummy)입니다.")
    return df

# ---------------------------------------------------------
# 3. 메인 앱 화면
# ---------------------------------------------------------

st.title("🌊 금강 수계 수위-수질 경보 예측 대시보드")

# 사이드바 설정
with st.sidebar:
    st.header("🔍 설정")
    
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("시작일", datetime.now() - timedelta(days=3))
    with col2:
        end_date = st.date_input("종료일", datetime.now())
    
    st.markdown("---")
    
    # 지점 선택 (관측소 코드 매핑)
    site_map = {
        "공주보": {"dam": "3012110", "wal": "3012640", "quality": "2015A30"},
        "세종보": {"dam": "3012120", "wal": "3012650", "quality": "2015A40"},
        "대청댐": {"dam": "1012110", "wal": "1010640", "quality": "1003A05"}
    }
    
    selected_site = st.selectbox("지점 선택", list(site_map.keys()))
    codes = site_map[selected_site]
    
    alert_threshold = st.slider("조류 경보 기준 (Chl-a)", 0, 100, 25)

# 실행 버튼
if st.button("데이터 조회 및 분석 시작", type="primary"):
    with st.spinner('데이터를 불러오는 중입니다...'):
        
        # 1. K-water 수위 데이터 호출 (디버깅 함수 사용)
        df_level = get_kwater_level(codes['dam'], codes['wal'], start_date, end_date)
        
        # 2. 수질 데이터 호출
        df_quality = get_water_quality(codes['quality'], start_date, end_date)
        
        # 3. 분석 및 시각화
        if not df_level.empty and not df_quality.empty:
            # 데이터 병합
            df_merged = pd.merge_asof(
                df_level.sort_values('datetime'), 
                df_quality.sort_values('datetime'), 
                on='datetime', 
                direction='nearest',
                tolerance=pd.Timedelta('1H')
            )
            
            df_merged['is_alert'] = df_merged['chla'] >= alert_threshold
            df_merged['status'] = df_merged['is_alert'].apply(lambda x: '경보' if x else '정상')
            
            st.success("데이터 병합 성공!")
            
            # 차트 1: 시계열
            st.subheader("📈 수위 vs 수질 변화")
            fig, ax1 = plt.subplots(figsize=(10, 5))
            
            sns.lineplot(data=df_merged, x='datetime', y='water_level', ax=ax1, color='blue', label='수위(m)')
            ax1.set_ylabel('수위 (m)', color='blue')
            
            ax2 = ax1.twinx()
            sns.lineplot(data=df_merged, x='datetime', y='chla', ax=ax2, color='green', label='Chl-a')
            ax2.axhline(alert_threshold, color='red', linestyle='--', label='경보 기준')
            ax2.set_ylabel('Chl-a (mg/m³)', color='green')
            
            lines1, labels1 = ax1.get_legend_handles_labels()
            lines2, labels2 = ax2.get_legend_handles_labels()
            ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left')
            
            st.pyplot(fig)

            # 원본 데이터 표시
            with st.expander("데이터 원본 보기"):
                st.dataframe(df_merged)
                
        elif df_level.empty:
            st.error("수위 데이터를 가져오지 못해 분석을 중단합니다. (위 에러 메시지를 확인하세요)")
