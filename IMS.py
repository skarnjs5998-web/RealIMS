import streamlit as st
import pandas as pd
import os
from datetime import datetime

# --- 수정된 파일 경로 설정 ---
INVENTORY_FILE = '출판부_재고자산.csv'  # 요청하신 대로 수정됨
TRANSACTION_FILE = '거래기록.csv'  # 요청하신 대로 수정됨
ORDERS_FILE = 'orders.csv'  # 주문 기록은 기존 유지 (필요시 변경 가능)

# 페이지 기본 설정
st.set_page_config(page_title="인하대 출판부 재고 관리", layout="wide")
st.title("📚 인하대 출판부 재고 관리 시스템")


# --- 데이터 로드 및 저장 함수 ---
def load_data(file_path, columns):
    if not os.path.exists(file_path):
        # 파일이 없으면 빈 데이터프레임 생성
        df = pd.DataFrame(columns=columns)
        df.to_csv(file_path, index=False)
        return df
    # 한글 파일명이므로 인코딩 에러 방지를 위해 필요한 경우 engine='python'을 쓸 수도 있으나,
    # 기본적으로 utf-8 csv는 잘 읽힙니다.
    return pd.read_csv(file_path)


def save_data(df, file_path):
    df.to_csv(file_path, index=False)


# 데이터 불러오기
df_inventory = load_data(INVENTORY_FILE, ['책 이름', '가격', 'ISBN', '현재 수량', '안전 재고'])
df_transactions = load_data(TRANSACTION_FILE, ['일시', '유형', '거래처', '책 이름', '수량', '가격'])
df_orders = load_data(ORDERS_FILE, ['일시', '거래처', '책 이름', '주문 수량', '상태'])

# --- 사이드바: 사용자 구분 ---
st.sidebar.header("로그인 / 사용자 모드")
user_role = st.sidebar.radio("접속 권한 선택", ("외부 정보 이용자", "내부 정보 이용자 (관리자)"))

is_admin = False

if user_role == "내부 정보 이용자 (관리자)":
    password = st.sidebar.text_input("관리자 비밀번호", type="password")
    if password == "inha1234":
        is_admin = True
        st.sidebar.success("인증되었습니다.")
    else:
        st.sidebar.warning("비밀번호를 입력하세요.")

# --- 메뉴 구성 ---
if is_admin:
    menu = ["현재 재고", "주문 청구", "입출고 입력", "거래 기록", "알림", "리포트 및 분석"]
else:
    menu = ["현재 재고", "주문 청구"]

choice = st.sidebar.selectbox("메뉴 선택", menu)

# --- 현재 재고 ---
if choice == "현재 재고":
    st.subheader("📦 현재 재고 조회")
    search_term = st.text_input("책 이름 또는 ISBN 검색")

    if search_term:
        result = df_inventory[
            df_inventory['책 이름'].str.contains(search_term) |
            df_inventory['ISBN'].astype(str).str.contains(search_term)
            ]
    else:
        result = df_inventory

    st.dataframe(result[['책 이름', 'ISBN', '현재 수량', '가격']], use_container_width=True)

# --- 주문 청구 ---
elif choice == "주문 청구":
    st.subheader("📝 도서 주문 청구")
    st.info("외부 서점 및 거래처 전용 주문 페이지입니다.")

    with st.form("order_form"):
        partner_name = st.text_input("거래처명 (서점명)")
        book_name_order = st.selectbox("주문할 책 선택", df_inventory['책 이름'].unique())
        order_qty = st.number_input("주문 수량", min_value=1, value=10)

        submit_order = st.form_submit_button("주문 하기")

        if submit_order:
            if partner_name and book_name_order:
                new_order = pd.DataFrame({
                    '일시': [datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
                    '거래처': [partner_name],
                    '책 이름': [book_name_order],
                    '주문 수량': [order_qty],
                    '상태': ['대기']
                })
                df_orders = pd.concat([df_orders, new_order], ignore_index=True)
                save_data(df_orders, ORDERS_FILE)
                st.success(f"'{book_name_order}' {order_qty}권 주문이 접수되었습니다.")
            else:
                st.error("거래처명과 책 이름을 확인해주세요.")

# --- 입출고 입력 ---
elif choice == "입출고 입력":
    st.subheader("🚚 재고 입/출고 및 파손 처리")

    col1, col2 = st.columns(2)
    with col1:
        io_type = st.radio("작업 유형", ["입고", "출고", "파손", "반품"])

    with col2:
        io_partner = st.text_input("거래처 (파손 시 생략 가능)")
        io_book = st.selectbox("책 선택", df_inventory['책 이름'].unique())
        io_qty = st.number_input("수량", min_value=1, value=1)

    if st.button("입력 처리"):
        current_idx = df_inventory.index[df_inventory['책 이름'] == io_book].tolist()

        if not current_idx:
            st.error("존재하지 않는 책입니다.")
        else:
            idx = current_idx[0]
            current_qty = df_inventory.at[idx, '현재 수량']
            book_price = df_inventory.at[idx, '가격']

            # 수량 계산
            if io_type in ["입고", "반품"]:
                new_qty = current_qty + io_qty
            else:  # 출고, 파손
                new_qty = current_qty - io_qty

            if new_qty < 0:
                st.error("재고가 부족하여 출고/파손 처리를 할 수 없습니다.")
            else:
                # 1. 재고 파일 업데이트
                df_inventory.at[idx, '현재 수량'] = new_qty
                save_data(df_inventory, INVENTORY_FILE)

                # 2. 거래 기록 파일 업데이트
                new_transaction = pd.DataFrame({
                    '일시': [datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
                    '유형': [io_type],
                    '거래처': [io_partner if io_type != "파손" else "폐기"],
                    '책 이름': [io_book],
                    '수량': [io_qty],
                    '가격': [book_price]
                })
                df_transactions = pd.concat([df_transactions, new_transaction], ignore_index=True)
                save_data(df_transactions, TRANSACTION_FILE)

                st.success(f"{io_type} 처리 완료: {io_book} ({io_qty}권)")
                st.rerun()

# --- 거래 기록 ---
elif choice == "거래 기록":
    st.subheader("📜 전체 거래 기록")
    if not df_transactions.empty:
        df_sorted = df_transactions.sort_values(by='일시', ascending=False)
        st.dataframe(df_sorted, use_container_width=True)
    else:
        st.info("거래 기록이 없습니다.")

# --- 알림 ---
elif choice == "알림":
    st.subheader("🔔 알림 센터")
    tab1, tab2 = st.tabs(["주문 요청", "안전 재고 경고"])

    with tab1:
        st.write("외부에서 들어온 주문 내역입니다.")
        if not df_orders.empty:
            st.dataframe(df_orders.sort_values(by='일시', ascending=False))
        else:
            st.info("신규 주문이 없습니다.")

    with tab2:
        st.write("안전 재고 이하로 떨어진 도서 목록입니다.")
        low_stock_books = df_inventory[df_inventory['현재 수량'] <= df_inventory['안전 재고']]
        if not low_stock_books.empty:
            for i, row in low_stock_books.iterrows():
                st.error(f"⚠️ [재고 부족] '{row['책 이름']}' - 현재: {row['현재 수량']}권 (안전 재고: {row['안전 재고']}권)")
        else:
            st.success("모든 도서의 재고가 안전합니다.")

# --- 리포트 및 분석 ---
elif choice == "리포트 및 분석":
    st.subheader("📊 리포트 및 분석")

    # 1. 월간 판매량
    st.markdown("### 1. 월간 판매량 (출고 기준)")
    if not df_transactions.empty:
        df_transactions['일시'] = pd.to_datetime(df_transactions['일시'])
        sales_data = df_transactions[df_transactions['유형'] == '출고'].copy()

        if not sales_data.empty:
            sales_data['월'] = sales_data['일시'].dt.strftime('%Y-%m')
            monthly_sales = sales_data.groupby(['월', '책 이름'])['수량'].sum().reset_index()
            st.bar_chart(data=monthly_sales, x='월', y='수량', color='책 이름', use_container_width=True)
        else:
            st.info("데이터가 충분하지 않습니다.")

    # 2. 재고 자산 평가
    st.markdown("### 2. 현재 재고 자산 평가")
    total_asset = (df_inventory['현재 수량'] * df_inventory['가격']).sum()
    st.metric(label="총 재고 자산 가치", value=f"{total_asset:,.0f} 원")

    # 3. 거래처별 반품률
    st.markdown("### 3. 거래처별 반품률")
    if not df_transactions.empty:
        partner_stats = df_transactions[df_transactions['유형'].isin(['출고', '반품'])]
        if not partner_stats.empty:
            stats = partner_stats.groupby(['거래처', '유형'])['수량'].sum().unstack(fill_value=0)
            if '출고' in stats.columns and '반품' in stats.columns:
                stats['반품률(%)'] = (stats['반품'] / (stats['출고'] + 0.0001)) * 100
                stats['반품률(%)'] = stats['반품률(%)'].round(2)
                st.dataframe(stats[['출고', '반품', '반품률(%)']])
            else:
                st.info("데이터가 충분하지 않습니다.")