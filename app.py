import streamlit as st
import pandas as pd
import requests
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta
import platform

# ---------------------------------------------------------
# 1. 기본 설정 및 비밀 키 로드
# ---------------------------------------------------------
st.set_page_config(page_title="금강 수위-수질 상관관계 분석", layout="wide")

# 한글 폰트 설정 (OS별 호환)
system_name = platform.system()
if system_name == 'Darwin': # Mac
    plt.rc('font', family='AppleGothic') 
elif system_name == 'Windows': # Windows
    plt.rc('font', family='Malgun Gothic') 
else: # Linux
    plt.rc('font', family='NanumGothic')
plt.rc('axes', unicode_minus=False)

# API 키 가져오기 (GitHub 배포 시 보안을 위해 st.secrets 사용)
# 로컬 실행 시: .streamlit/secrets.toml 파일 필요
# GitHub 배포 시: Streamlit Cloud 대시보드에서 Secrets 설정 필요
try:
    API_KEY = st.secrets["public_api_key"]
except FileNotFoundError:
    st.error("⚠️ API 키를 찾을 수 없습니다. .streamlit/secrets.toml 파일을 확인하거나 Streamlit Cloud의 Secrets 설정을 확인하세요.")
    st.stop()

# ---------------------------------------------------------
# 2. 데이터 수집 함수 (K-water & 환경공단)
# ---------------------------------------------------------

@st.cache_data(ttl=3600)  # 1시간 동안 데이터 캐싱(재사용)
def get_kwater_level(dam_code, wal_code, start_date, end_date):
    """
    K-water 시간단위 수위 정보 조회 (hourwal)
    """
    # K-water 수위 API 엔드포인트
    url = "https://apis.data.go.kr/B500001/dam/excllncobsrvt/hourwal/hourwallist"
    
    # 요청 파라미터
    params = {
        "serviceKey": API_KEY,  # Decoding된 키 사용
        "_type": "json",
        "numOfRows": "999",     # 충분한 데이터 확보
        "pageNo": "1",
        "sdate": start_date.strftime("%Y-%m-%d"),
        "stime": "00",
        "edate": end_date.strftime("%Y-%m-%d"),
        "etime": "23",
        "damcode": dam_code,
        "wal": wal_code
    }
    
    try:
        # verify=False는 공공데이터포털 SSL 인증서 문제 방지용
        response = requests.get(url, params=params, verify=False)
        data = response.json()
        
        # 데이터 파싱
        items = data['response']['body']['items']['item']
        if isinstance(items, dict): # 데이터가 1건일 경우 리스트로 변환
            items = [items]
            
        df = pd.DataFrame(items)
        
        # 필요한 컬럼 정리 및 형변환
        df['datetime'] = pd.to_datetime(df['obsrdt'])
        df['water_level'] = pd.to_numeric(df['flux']) # 수위 (EL.m)
        
        # 날짜순 정렬 후 반환
        return df[['datetime', 'water_level']].sort_values('datetime')
        
    except Exception as e:
        st.warning(f"K-water 데이터 조회 중 오류가 발생했습니다: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=3600)
def get_water_quality(site_code, start_date, end_date):
    """
    국립환경과학원/환경공단 수질 측정 데이터 조회
    (실제 API 호출 실패 시, 앱 테스트를 위해 더미 데이터를 생성하여 반환합니다)
    """
    # 환경공단 수질측정망 API 엔드포인트 (확인된 URL로 교체 필요할 수 있음)
    url = "http://apis.data.go.kr/1480523/WaterQualityService/getWaterMeasuringList"
    
    # ------------------------------------------------------------
    # [실제 API 호출 로직]
    # 만약 수질 데이터 API 키가 K-water와 다르다면 별도의 secret을 만들어야 합니다.
    # 현재는 동일한 API_KEY를 사용한다고 가정합니다.
    # ------------------------------------------------------------
    # params = {
    #     "serviceKey": API_KEY,
    #     "numOfRows": "999",
    #     "pageNo": "1",
    #     "ptNo": site_code, # 측정소 코드
    #     "wmyr": start_date.strftime("%Y"),
    #     "wmmd": start_date.strftime("%m%d")
    # }
    # try:
    #     response = requests.get(url, params=params)
    #     ... (파싱 로직 추가 필요) ...
    # except...
    # ------------------------------------------------------------

    # [테스트용 더미 데이터 생성기]
    # 실제 API 연동 전, 차트가 그려지는지 확인하기 위한 가짜 데이터입니다.
    dates = pd.date_range(start=start_date, end=end_date + timedelta(hours=23), freq='H')
    import numpy as np
    
    dummy_data = []
    for d in dates:
        # 수질 데이터 랜덤 생성 (Chl-a: 0~50 mg/m3)
        dummy_data.append({
            'datetime': d,
            'toc': np.random.uniform(2.0, 9.0),   # 총유기탄소
            'chla': np.random.uniform(5.0, 45.0)  # 클로로필-a (조류)
        })
    
    df = pd.DataFrame(dummy_data)
    st.info("ℹ️ 현재 수질 데이터는 테스트용(Dummy) 데이터입니다. 실제 API 연동 시 코드를 수정해주세요.")
    return df

# ---------------------------------------------------------
# 3. 메인 앱 화면 구성 (UI)
# ---------------------------------------------------------

st.title("🌊 금강 수계 수위-수질 경보 예측 대시보드")
st.markdown("""
이 대시보드는 **K-water(수위)**와 **환경공단(수질)** 데이터를 융합하여 분석합니다.
수위 변화에 따른 조류 경보(클로로필-a 기준) 발생 가능성을 시각화합니다.
""")

# 사이드바: 사용자 입력
with st.sidebar:
    st.header("🔍 설정 패널")
    
    # 날짜 선택 (기본값: 최근 7일)
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("시작일", datetime.now() - timedelta(days=7))
    with col2:
        end_date = st.date_input("종료일", datetime.now())
    
    st.markdown("---")
    st.subheader("📍 분석 지점 선택")
    
    # 지점별 코드 매핑 (실제 코드로 업데이트 필요)
    # 예시: 공주보, 세종보, 대청댐
    site_map = {
        "공주보 (Gongju-bo)": {
            "dam_code": "3012110", "wal_code": "3012640", "quality_code": "2015A30"
        },
        "세종보 (Sejong-bo)": {
            "dam_code": "3012120", "wal_code": "3012650", "quality_code": "2015A40"
        },
        "대청댐 (Daecheong Dam)": {
            "dam_code": "1012110", "wal_code": "1010640", "quality_code": "1003A05"
        }
    }
    
    selected_site_name = st.selectbox("지점 목록", list(site_map.keys()))
    site_codes = site_map[selected_site_name]
    
    st.markdown("---")
    st.subheader("⚠️ 경보 시뮬레이션 설정")
    # 사용자가 직접 경보 기준을 조정하여 시뮬레이션 가능
    alert_threshold = st.slider(
        "조류 경보 기준 (Chl-a mg/m³)", 
        min_value=0, max_value=100, value=25, 
        help="이 수치를 초과하면 '경보 발생'으로 간주하여 분석합니다."
    )

# 실행 버튼
if st.button("데이터 조회 및 분석 시작", type="primary"):
    with st.spinner(f"'{selected_site_name}' 데이터를 불러오는 중입니다..."):
        
        # 1. API 데이터 호출
        df_level = get_kwater_level(site_codes['dam_code'], site_codes['wal_code'], start_date, end_date)
        df_quality = get_water_quality(site_codes['quality_code'], start_date, end_date)
        
        # 데이터 유효성 검사
        if df_level.empty:
            st.error("❌ 수위 데이터를 가져오지 못했습니다. API 키나 관측소 코드를 확인해주세요.")
        elif df_quality.empty:
            st.error("❌ 수질 데이터를 가져오지 못했습니다.")
        else:
            # 2. 데이터 병합 (Merge)
            # 시간(datetime)을 기준으로 가장 가까운 데이터끼리 합침
            df_merged = pd.merge_asof(
                df_level.sort_values('datetime'), 
                df_quality.sort_values('datetime'), 
                on='datetime', 
                direction='nearest',
                tolerance=pd.Timedelta('1H') # 1시간 이내 데이터만 매칭
            )
            
            # 3. 데이터 분석 (경보 여부 판별)
            df_merged['is_alert'] = df_merged['chla'] >= alert_threshold
            df_merged['status'] = df_merged['is_alert'].apply(lambda x: '경보(Danger)' if x else '정상(Normal)')
            
            # 데이터가 잘 합쳐졌는지 확인
            if df_merged.empty:
                st.warning("데이터는 가져왔으나, 시간대가 일치하지 않아 병합된 결과가 없습니다.")
            else:
                st.success(f"분석 완료! 총 {len(df_merged)}건의 데이터를 분석했습니다.")
                
                # --- [시각화 1] 시계열 복합 차트 ---
                st.subheader("📈 수위와 조류농도(Chl-a) 변화 추이")
                
                fig, ax1 = plt.subplots(figsize=(12, 6))
                
                # 왼쪽 축: 수위
                sns.lineplot(data=df_merged, x='datetime', y='water_level', ax=ax1, color='#1f77b4', label='수위 (EL.m)', linewidth=2)
                ax1.set_ylabel('수위 (m)', color='#1f77b4', fontweight='bold')
                ax1.tick_params(axis='y', labelcolor='#1f77b4')
                ax1.grid(True, alpha=0.3)
                
                # 오른쪽 축: 수질
                ax2 = ax1.twinx()
                sns.lineplot(data=df_merged, x='datetime', y='chla', ax=ax2, color='#2ca02c', label='Chl-a (mg/m³)', linestyle='--')
                
                # 경보 기준선 표시
                ax2.axhline(y=alert_threshold, color='red', linestyle=':', label=f'경보 기준 ({alert_threshold})')
                
                ax2.set_ylabel('조류농도 (mg/m³)', color='#2ca02c', fontweight='bold')
                ax2.tick_params(axis='y', labelcolor='#2ca02c')
                
                # 범례 통합 표시
                lines_1, labels_1 = ax1.get_legend_handles_labels()
                lines_2, labels_2 = ax2.get_legend_handles_labels()
                ax1.legend(lines_1 + lines_2, labels_1 + labels_2, loc='upper left')
                
                st.pyplot(fig)
                
                # --- [시각화 2] 상관관계 분석 ---
                st.markdown("---")
                col_a, col_b = st.columns(2)
                
                with col_a:
                    st.subheader("📊 수위별 경보 발생 분포")
                    # 산점도 그리기
                    fig2, ax_scatter = plt.subplots()
                    sns.scatterplot(
                        data=df_merged, 
                        x='water_level', 
                        y='chla', 
                        hue='status', 
                        palette={'경보(Danger)': 'red', '정상(Normal)': 'gray'},
                        alpha=0.7,
                        ax=ax_scatter
                    )
                    ax_scatter.axhline(y=alert_threshold, color='red', linestyle='--')
                    ax_scatter.set_title("수위가 낮을 때 경보가 많은가?")
                    st.pyplot(fig2)
                
                with col_b:
                    st.subheader("🧮 수위 구간별 경보 확률")
                    # 수위를 0.5m 단위로 구간화(Binning)
                    df_merged['level_bin'] = (df_merged['water_level'] * 2).round() / 2
                    
                    # 구간별 경보 확률 계산
                    risk_df = df_merged.groupby('level_bin')['is_alert'].mean() * 100
                    
                    st.bar_chart(risk_df)
                    st.caption("X축: 수위(m), Y축: 경보 발생 확률(%)")
                
                # 원본 데이터 확인 (접기/펼치기)
                with st.expander("💾 원본 데이터 확인하기"):
                    st.dataframe(df_merged)
