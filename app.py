import streamlit as st
import pandas as pd
import requests
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta
import platform
import time

# ---------------------------------------------------------
# 1. 기본 설정
# ---------------------------------------------------------
st.set_page_config(page_title="금강 수계 수위-수질 통합 분석", layout="wide")

# 한글 폰트 설정
try:
    system_name = platform.system()
    if system_name == 'Darwin': plt.rc('font', family='AppleGothic') 
    elif system_name == 'Windows': plt.rc('font', family='Malgun Gothic') 
    else: plt.rc('font', family='NanumGothic')
    plt.rc('axes', unicode_minus=False)
except: pass

# API 키 설정
try:
    API_KEY = st.secrets["public_api_key"]
except:
    st.error("API 키가 설정되지 않았습니다. Secrets를 확인하세요.")
    st.stop()

# ---------------------------------------------------------
# 2. 관측소 목록 가져오기 (API + 수동 하이브리드)
# ---------------------------------------------------------

@st.cache_data(ttl=86400)
def get_kwater_station_list():
    """
    K-water 수위 관측소 목록 조회 (API 실패 시 수동 리스트 사용)
    """
    # API 조회 대상 (큰 댐)
    api_targets = [('1003110', '대청댐'), ('1001110', '용담댐')]
    
    # 수동 추가 대상 (API 리스트에 안 나오는 보 본체 코드)
    manual_targets = [
        {'obsrvtNm': '공주보 (본체)', 'walobsrvtcode': '3012110', 'parent_dam_code': '3012110', 'parent_dam_name': '공주보'},
        {'obsrvtNm': '세종보 (본체)', 'walobsrvtcode': '3012120', 'parent_dam_code': '3012120', 'parent_dam_name': '세종보'},
        {'obsrvtNm': '백제보 (본체)', 'walobsrvtcode': '3012130', 'parent_dam_code': '3012130', 'parent_dam_name': '백제보'}
    ]
    
    url = "http://apis.data.go.kr/B500001/dam/excllncobsrvt/wal/wallist"
    all_stations = []

    for dam_code, dam_name in api_targets:
        params = {"serviceKey": API_KEY, "_type": "json", "damcode": dam_code}
        try:
            response = requests.get(url, params=params, verify=False)
            data = response.json()
            items = data['response']['body']['items']['item']
            if isinstance(items, dict): items = [items]
            for item in items:
                item['parent_dam_code'] = dam_code
                item['parent_dam_name'] = dam_name
                all_stations.append(item)
        except: continue
    
    all_stations.extend(manual_targets)
            
    if all_stations:
        df = pd.DataFrame(all_stations)
        df['display_name'] = "[" + df['parent_dam_name'] + "] " + df['obsrvtNm']
        return df
    return pd.DataFrame()

@st.cache_data(ttl=86400)
def get_quality_station_list():
    """
    환경공단 수질측정소 목록 조회
    """
    url = "http://apis.data.go.kr/1480523/WaterQualityService/getMsrstnList"
    params = {"serviceKey": API_KEY, "numOfRows": "200", "pageNo": "1", "returnType": "json"}
    
    try:
        response = requests.get(url, params=params)
        data = response.json()
        items = data['getMsrstnList']['item']
        return pd.DataFrame(items)
    except:
        # 실패 시 수동 리스트 (주요 지점 코드)
        dummy_data = [
            {'ptNo': '2015A30', 'ptNm': '공주보(수질)'},
            {'ptNo': '2015A40', 'ptNm': '세종보(수질)'},
            {'ptNo': '1003A05', 'ptNm': '대청댐(수질)'},
            {'ptNo': '2015A35', 'ptNm': '백제보(수질)'}
        ]
        return pd.DataFrame(dummy_data)

# ---------------------------------------------------------
# 3. 실제 데이터 조회 함수 (수위 + 수질 5개 항목)
# ---------------------------------------------------------
@st.cache_data(ttl=3600)
def get_data(dam_code, wal_code, quality_code, start, end):
    
    # --- [1] K-water 수위 데이터 조회 ---
    url_wal = "https://apis.data.go.kr/B500001/dam/excllncobsrvt/hourwal/hourwallist"
    params_wal = {
        "serviceKey": API_KEY, "_type": "json", "numOfRows": "999", "pageNo": "1",
        "sdate": start.strftime("%Y-%m-%d"), "stime": "00",
        "edate": end.strftime("%Y-%m-%d"), "etime": "23",
        "damcode": dam_code, "wal": wal_code
    }
    
    df_wal = pd.DataFrame()
    try:
        res = requests.get(url_wal, params=params_wal, verify=False).json()
        items = res['response']['body']['items']['item']
        if items:
            if isinstance(items, dict): items = [items]
            df_wal = pd.DataFrame(items)
            df_wal['datetime'] = pd.to_datetime(df_wal['obsrdt'])
            df_wal['water_level'] = pd.to_numeric(df_wal['flux'])
            df_wal = df_wal[['datetime', 'water_level']].sort_values('datetime')
    except Exception as e:
        print(f"수위 데이터 오류: {e}")

    # --- [2] 환경공단 수질 데이터 조회 (TN, TP, TOC, DO, pH) ---
    # *참고: 이 API는 '일별(날짜별)'로 호출해야 하는 경우가 많음
    url_qual = "http://apis.data.go.kr/1480523/WaterQualityService/getWaterMeasuringList"
    
    qual_items = []
    
    # 시작일부터 종료일까지 하루씩 반복 호출 (API 제한 고려)
    # 기간이 길면 로딩이 조금 걸릴 수 있음
    curr_date = start
    while curr_date <= end:
        params_qual = {
            "serviceKey": API_KEY,
            "numOfRows": "100", # 시간별 데이터 24개+a
            "pageNo": "1",
            "ptNo": quality_code,
            "wmyr": curr_date.strftime("%Y"),
            "wmmd": curr_date.strftime("%m%d"),
            "returnType": "json"
        }
        
        try:
            # 타임아웃 3초 설정 (너무 오래 걸리면 스킵)
            q_res = requests.get(url_qual, params=params_qual, timeout=3)
            q_data = q_res.json()
            
            if 'getWaterMeasuringList' in q_data and 'item' in q_data['getWaterMeasuringList']:
                day_items = q_data['getWaterMeasuringList']['item']
                if isinstance(day_items, dict): day_items = [day_items]
                qual_items.extend(day_items)
        except:
            pass # 해당 날짜 데이터 없으면 패스
            
        curr_date += timedelta(days=1)
    
    df_qual = pd.DataFrame()
    if qual_items:
        df_qual = pd.DataFrame(qual_items)
        
        # 컬럼 매핑 (API 응답 태그 -> 한글 이름)
        # API 응답 예시: wmyr, wmmd, wmht(시간), ph, do, toc, tn, tp
        
        # 날짜/시간 생성
        # 시간 정보가 '1', '13' 처럼 올 수 있음 -> '01', '13'으로 패딩 필요
        df_qual['hour_str'] = df_qual['wmht'].astype(str).str.zfill(2) 
        df_qual['date_str'] = df_qual['wmyr'] + "-" + df_qual['wmmd'].str[:2] + "-" + df_qual['wmmd'].str[2:]
        df_qual['datetime'] = pd.to_datetime(df_qual['date_str'] + " " + df_qual['hour_str'] + ":00", errors='coerce')
        
        # 수치 데이터 형변환 (에러 발생 시 NaN 처리)
        cols_to_parse = {
            'ph': 'pH', 
            'do': 'DO(mg/L)', 
            'toc': 'TOC(mg/L)', 
            'tn': 'TN(mg/L)', 
            'tp': 'TP(mg/L)'
        }
        
        for api_col, view_col in cols_to_parse.items():
            if api_col in df_qual.columns:
                df_qual[view_col] = pd.to_numeric(df_qual[api_col], errors='coerce')
            else:
                df_qual[view_col] = 0 # 컬럼이 아예 없으면 0 처리
        
        # 필요한 컬럼만 선택
        select_cols = ['datetime'] + list(cols_to_parse.values())
        df_qual = df_qual[select_cols].dropna(subset=['datetime']).sort_values('datetime')

    return df_wal, df_qual

# ---------------------------------------------------------
# 4. 메인 화면 UI
# ---------------------------------------------------------
st.title("🌊 금강 수계 수위-수질 통합 분석기")
st.caption("K-water 수위와 환경공단 수질(TN, TP, TOC, DO, pH) 실데이터 분석")

# 사이드바
with st.sidebar:
    st.header("1️⃣ 지점 선택")
    
    # 수위
    df_wal_stations = get_kwater_station_list()
    if not df_wal_stations.empty:
        # 공주보 우선 선택
        idx = 0
        names = df_wal_stations['display_name'].unique()
        for i, n in enumerate(names):
            if "공주보" in n: idx = i; break
        sel_wal_name = st.selectbox("수위 관측소", names, index=idx)
        w_row = df_wal_stations[df_wal_stations['display_name'] == sel_wal_name].iloc[0]
        sel_dam, sel_wal = w_row['parent_dam_code'], w_row['walobsrvtcode']
    else:
        st.error("수위 관측소 로드 실패"); st.stop()
        
    # 수질
    df_qual_stations = get_quality_station_list()
    if not df_qual_stations.empty:
        # 공주보 우선 선택
        q_idx = 0
        q_names = df_qual_stations['ptNm'].unique()
        for i, n in enumerate(q_names):
            if "공주보" in n: q_idx = i; break
        sel_qual_name = st.selectbox("수질 측정소", q_names, index=q_idx)
        sel_qual_code = df_qual_stations[df_qual_stations['ptNm'] == sel_qual_name].iloc[0]['ptNo']
    else:
        sel_qual_code = "TEST"

    st.divider()
    st.header("2️⃣ 분석 항목 설정")
    # 사용자가 비교하고 싶은 수질 항목 선택
    target_quality = st.selectbox(
        "비교할 수질 항목", 
        ["TOC(mg/L)", "TP(mg/L)", "TN(mg/L)", "DO(mg/L)", "pH"],
        index=0
    )
    
    # 각 항목별 경보 기준 예시 (TOC: 보통 4~5 넘으면 나쁨)
    default_th = 5.0 if "TOC" in target_quality else (0.1 if "TP" in target_quality else 7.0)
    alert_th = st.number_input(f"{target_quality} 경보 기준값", value=default_th, step=0.1)

    st.divider()
    st.header("3️⃣ 기간 설정")
    # API 부하 고려하여 기본 3일로 설정
    start_date = st.date_input("시작", datetime.now() - timedelta(days=3))
    end_date = st.date_input("종료", datetime.now())

# 메인 실행
if st.button("데이터 조회 및 분석", type="primary"):
    with st.spinner(f"{sel_wal_name} 수위와 {sel_qual_name} 수질 데이터를 가져오는 중..."):
        
        df_level, df_quality = get_data(sel_dam, sel_wal, sel_qual_code, start_date, end_date)
        
        # 데이터 존재 여부 체크
        if df_level.empty:
            st.error("❌ 수위 데이터가 없습니다.")
        elif df_quality.empty:
            st.error(f"❌ '{sel_qual_name}'의 수질 데이터가 조회되지 않았습니다. (해당 기간 데이터 없음 or API 권한 확인 필요)")
        else:
            # 데이터 병합
            df_merged = pd.merge_asof(
                df_level, df_quality, on='datetime', direction='nearest', tolerance=pd.Timedelta('1H')
            )
            
            # 분석용 컬럼 생성
            df_merged['is_alert'] = df_merged[target_quality] >= alert_th
            
            st.success(f"분석 완료! 총 {len(df_merged)}건의 데이터를 비교합니다.")
            
            # [차트] 이중축 그래프
            fig, ax1 = plt.subplots(figsize=(12, 6))
            
            # 축1: 수위
            sns.lineplot(data=df_merged, x='datetime', y='water_level', ax=ax1, color='#1f77b4', label='수위(m)', linewidth=2)
            ax1.set_ylabel('수위 (m)', color='#1f77b4', fontweight='bold')
            ax1.grid(True, alpha=0.3)
            
            # 축2: 선택한 수질 항목
            ax2 = ax1.twinx()
            sns.lineplot(data=df_merged, x='datetime', y=target_quality, ax=ax2, color='#ff7f0e', label=target_quality, marker='o')
            # 경보 기준선
            ax2.axhline(alert_th, color='red', linestyle='--', label=f'기준값 ({alert_th})')
            ax2.set_ylabel(target_quality, color='#ff7f0e', fontweight='bold')
            
            # 범례
            lines1, labels1 = ax1.get_legend_handles_labels()
            lines2, labels2 = ax2.get_legend_handles_labels()
            ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left')
            
            st.pyplot(fig)
            
            # [상관관계] 산점도
            st.markdown("---")
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader(f"📊 수위 vs {target_quality} 상관분석")
                fig2, ax_s = plt.subplots()
                sns.scatterplot(data=df_merged, x='water_level', y=target_quality, hue='is_alert', palette={True: 'red', False: 'gray'}, ax=ax_s)
                ax_s.axhline(alert_th, color='red', linestyle='--')
                st.pyplot(fig2)
                
            with col2:
                st.subheader("📋 데이터 요약")
                st.write(df_merged[['datetime', 'water_level', target_quality]].describe())

            with st.expander("📥 전체 데이터 보기"):
                st.dataframe(df_merged)
