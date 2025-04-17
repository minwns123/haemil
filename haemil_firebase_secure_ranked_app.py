
import streamlit as st
import pandas as pd
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, firestore

if not firebase_admin._apps:
    cred = credentials.Certificate(st.secrets["firebase"])
    firebase_admin.initialize_app(cred)

db = firestore.client()

if "user" not in st.session_state:
    st.session_state.user = None

def get_users():
    return [doc.to_dict() for doc in db.collection("users").stream()]

def get_pending_users():
    return [doc.to_dict() for doc in db.collection("pending_users").stream()]

def get_records():
    return [doc.to_dict() for doc in db.collection("records").stream()]

def add_user(user):
    db.collection("users").document(user["id"]).set(user)

def add_pending_user(user):
    db.collection("pending_users").document(user["id"]).set(user)

def delete_pending_user(user_id):
    db.collection("pending_users").document(user_id).delete()

def add_record(record):
    db.collection("records").add(record)

def delete_all_records():
    for doc in db.collection("records").stream():
        doc.reference.delete()

st.set_page_config(page_title="박해밀 드립 스탯", layout="centered")
st.title("⚾ Haemil drip.gg")

if not st.session_state.user:
    st.subheader("🔐 로그인 또는 회원가입 신청")
    tab1, tab2 = st.tabs(["로그인", "회원가입 신청"])

    with tab1:
        login_id = st.text_input("아이디", key="login_id")
        login_pw = st.text_input("비밀번호", type="password", key="login_pw")
        if st.button("로그인"):
            users = get_users()
            user = next((u for u in users if u["id"] == login_id and u["password"] == login_pw), None)
            if user:
                st.session_state.user = user
                st.success("🎉 " + user["name"] + "님, 로그인 완료")
                st.rerun()
            else:
                st.error("아이디 또는 비밀번호가 올바르지 않습니다.")

    with tab2:
        new_name = st.text_input("이름 (닉네임)")
        new_id = st.text_input("아이디 (영문, 숫자)")
        new_pw = st.text_input("비밀번호", type="password")
        if st.button("회원가입 신청"):
            if new_name and new_id and new_pw:
                users = get_users()
                pending = get_pending_users()
                if new_id.lower() == "admin":
                    st.warning("관리자 아이디는 사용할 수 없습니다.")
                elif any(u["id"] == new_id for u in users + pending):
                    st.warning("이미 사용 중인 아이디입니다.")
                else:
                    new_user = {"id": new_id, "name": new_name, "password": new_pw}
                    add_pending_user(new_user)
                    st.success("회원가입 신청 완료! 관리자의 승인을 기다려주세요.")
            else:
                st.warning("모든 항목을 입력해주세요.")

else:
    user = st.session_state.user
    is_admin = user["id"] == "admin"
    st.success("🎉 " + user["name"] + "님, 로그인 완료")

    menu = st.radio("📂 메뉴 선택", ["🏏 평가", "📊 통계", "🧑‍🤝‍🧑 구성원 레벨"] + (["🛂 가입 승인 대기"] if is_admin else []))

    users = get_users()
    records = get_records()
    pending = get_pending_users()

    if menu == "🏏 평가":
        memo = st.text_input("🗒️ 드립 메모 (선택)", placeholder="예: 지하철 환승 드립")
        col1, col2, col3 = st.columns(3)
        for label, result in zip(["안타", "홈런", "아웃"], ["안타", "홈런", "아웃"]):
            with [col1, col2, col3][["안타", "홈런", "아웃"].index(label)]:
                if st.button(label):
                    record = {
                        "evaluator": user["name"],
                        "result": result,
                        "memo": memo,
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M")
                    }
                    add_record(record)
                    st.success(result + " 평가 완료!")
                    st.rerun()

    elif menu == "📊 통계":
        if records:
            df = pd.DataFrame(records)
            st.subheader("📊 해밀 드립 평가 통계")
            total = len(df)
            hits = df["result"].isin(["안타", "홈런"]).sum()
            hr = df["result"].eq("홈런").sum()
            avg = round(hits / total, 3)
            hr_rate = round(hr / total, 3)

            st.write(f"총 평가 수: {total}")
            st.write(f"안타: {hits} | 홈런: {hr} | 아웃: {df['result'].eq('아웃').sum()}")
            st.write(f"타율: **{avg}** | 홈런율: **{hr_rate}**")

            st.subheader("📜 전체 평가 기록")
            st.subheader("🏆 Today Rank (오늘의 심사단)")
            today_str = datetime.now().strftime("%Y-%m-%d")
            today_df = df[df["timestamp"].str.startswith(today_str)]
            if today_df.empty:
                st.info("오늘 평가 기록이 없습니다.")
            else:
                rank_df = today_df.groupby("evaluator").size().reset_index(name="count")
                rank_df = rank_df.sort_values("count", ascending=False).reset_index(drop=True)
                medals = ["🥇", "🥈", "🥉"] + ["🎯"] * 10
                for i, row in rank_df.iterrows():
                    medal = medals[i] if i < len(medals) else ""
                    st.write(f"{medal} {row['evaluator']} — {row['count']}회")

            st.dataframe(df[::-1], use_container_width=True)

            if is_admin:
                st.subheader("🛠️ 관리자 도구")
                if st.button("⚠️ 전체 기록 초기화"):
                    delete_all_records()
                    st.warning("기록이 초기화되었습니다.")
                    st.rerun()
        else:
            st.info("아직 평가 기록이 없습니다.")

    elif menu == "🧑‍🤝‍🧑 구성원 레벨":
        st.subheader("👥 전체 구성원 레벨")
        df = pd.DataFrame(records)
        for u in users:
            name = u["name"]
            user_records = df[df["evaluator"] == name] if not df.empty else pd.DataFrame()
            eval_count = len(user_records)
            if eval_count < 5:
                level = "🐣 입문자"
            elif eval_count < 10:
                level = "🧢 견습 평가단"
            elif eval_count < 20:
                level = "🔥 열정 평가단"
            elif eval_count < 40:
                level = "⚾ 해밀 공식 심사단"
            else:
                level = "🧙 해밀 교단 마스터"

            st.write("**" + name + "** — " + level + f" (총 {eval_count}회 평가)")

    elif menu == "🛂 가입 승인 대기" and is_admin:
        st.subheader("📝 가입 승인 대기 목록")
        if pending:
            for u in pending:
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(u["name"] + " (" + u["id"] + ")")
                with col2:
                    if st.button("✅ 승인", key="approve_" + u["id"]):
                        add_user(u)
                        delete_pending_user(u["id"])
                        st.success(u["name"] + " 승인됨")
                        st.rerun()
                    if st.button("❌ 거절", key="reject_" + u["id"]):
                        delete_pending_user(u["id"])
                        st.warning(u["name"] + " 거절됨")
                        st.rerun()
        else:
            st.info("대기 중인 신청이 없습니다.")

    if st.button("🔓 로그아웃"):
        st.session_state.user = None
        st.rerun()
