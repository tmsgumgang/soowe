import streamlit as st
import pandas as pd
import requests
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta
import platform

# ---------------------------------------------------------
# 1. 기본 설정 및 키 설정
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

# [키 설정]
# 1. 한강홍수통제소 (수위용) - 새로 주신 키
HRFCO_KEY = "F09631CC-1CFB-4C55-8329-BE03A787011E"

# 2. 공공데이터포털 (수질용) - 기존 키 (환경공단 데이터용)
# Secrets에 있다면 가져오고, 없으면 하드코딩된 값 사용
try:
    DATA_GO_KEY = st.secrets["public_api_key"]
except:
    DATA_GO_KEY = "5e7413b16c759d963b94776062c5a130c3446edf4d5f7f77a679b91bfd437912"

# ---------------------------------------------------------
# 2. 지점 목록 정의 (수동 매핑)
# ---------------------------------------------------------
@st.cache_data(ttl=86400)
def get_station_mapping():
    """
    수위 관측소(한강홍수통제소 Code)와 수질 측정소(환경공단 Code)를 매핑합니다.
    * 수위 코드는 7자리 표준코드(30xxxxx)를 사용합니다.
    """
    stations = [
        {
            "name": "공주보", 
            "wal_code": "3012640", # 공주보 수위국
            "qual_code": "2015A30" # 공주보 수질측정소
        },
        {
            "name": "세종보", 
            "wal_code": "3012650", 
            "qual_code": "2015A40"
        },
        {
            "name": "백제보", 
            "wal_code": "3012620", 
            "qual_code": "2015A35"
        },
        {
            "name": "대전 갑천 (갑천교)", 
            "wal_code": "3009660", # 대전시(갑천교)
            "qual_code": "2014A20" # 갑천1 (대표 지점)
        },
        {
            "name": "옥천 이원 (이원교)", 
            "wal_code": "3008680", # 옥천군(이원교)
            "qual_code": "1003A07" # 이원 (대청호 상류)
        },
        {
            "name": "대청댐 (본체)", 
            "wal_code": "1003660", # 대청댐
            "qual_code": "1003A05" # 대청호(추소) - 댐 앞 대표지점
        }
