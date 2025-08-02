import streamlit as st
import sqlite3
import datetime
import pandas as pd
import time
import os

# --- データベース設定 ---
DB_FILE = "chat.db"

MAX_ROOM = 10

ADMINID = os.environ.get("ADMIN_KEY")
PASSWORD = os.environ.get("PASS_KEY")

def init_db():
    """データベースを初期化し、テーブルが存在しない場合は作成する"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id INTEGER NOT NULL,
            timestamp TEXT NOT NULL,
            nickname TEXT NOT NULL,
            message TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def add_message(room_id, nickname, message):
    """メッセージをデータベースに追加する"""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO chat_history (room_id, timestamp, nickname, message) VALUES (?, ?, ?, ?)",
        (room_id, timestamp, nickname, message)
    )
    conn.commit()
    conn.close()

def get_messages(room_id):
    """指定された部屋のメッセージ履歴を取得する"""
    conn = sqlite3.connect(DB_FILE)
    # 辞書形式で結果を受け取るように設定
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        "SELECT nickname, timestamp, message FROM chat_history WHERE room_id = ? ORDER BY timestamp ASC",
        (room_id,)
    )
    messages = cursor.fetchall()
    conn.close()
    return messages

def delete_messages_in_room(room_id):
    """指定された部屋のメッセージを全て削除する"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM chat_history WHERE room_id = ?", (room_id,))
    conn.commit()
    conn.close()

def count_messages_per_room():
    """部屋ごとのメッセージ数を集計する"""
    conn = sqlite3.connect(DB_FILE)
    try:
        df = pd.read_sql_query(
            "SELECT room_id, COUNT(*) as message_count FROM chat_history GROUP BY room_id",
            conn
        )
        return df
    except pd.io.sql.DatabaseError:
        # テーブルが空の場合のエラーをハンドリング
        return pd.DataFrame(columns=['room_id', 'message_count'])
    finally:
        conn.close()

# --- Streamlit UI ---

# ページの初期設定
st.set_page_config(page_title="Streamlit チャットルーム", layout="centered")

# データベースの初期化
init_db()

# セッションステートの初期化
if 'is_logged_in' not in st.session_state:
    st.session_state.is_logged_in = False
    st.session_state.nickname = ""
    st.session_state.room_id = 0
    st.session_state.admin_logged_in = False

# --- 管理者向け機能（サイドバー） ---
with st.sidebar:
    st.title("管理者メニュー")
    if not st.session_state.admin_logged_in:
        admin_id = st.text_input("管理者ID", key="admin_id")
        admin_pass = st.text_input("パスワード", type="password", key="admin_pass")
        if st.button("管理者ログイン"):
            if admin_id == ADMINID and admin_pass == PASSWORD:
                st.session_state.admin_logged_in = True
                st.success("管理者としてログインしました。")
                time.sleep(1)
                st.rerun() # 画面を再読み込みしてダッシュボードを表示
            else:
                st.error("IDまたはパスワードが間違っています。")
    
    if st.session_state.admin_logged_in:
        st.header("管理者ダッシュボード")
        
        # 部屋ごとのチャット回数表示
        st.subheader("部屋別チャット投稿数")
        message_counts_df = count_messages_per_room()
        st.dataframe(message_counts_df, use_container_width=True)
        
        # チャット履歴削除機能
        st.subheader("チャット履歴削除")
        if not message_counts_df.empty:
            delete_room_id = st.selectbox(
                "削除する部屋を選択",
                options=message_counts_df['room_id'].unique(),
                key="delete_room_select"
            )
            if st.button(f"部屋 {delete_room_id} の履歴を削除", type="primary"):
                delete_messages_in_room(delete_room_id)
                st.success(f"部屋 {delete_room_id} のチャット履歴を削除しました。")
                time.sleep(1)
                st.rerun()
        else:
            st.info("投稿履歴のある部屋はありません。")

        if st.button("管理者ログアウト"):
            st.session_state.admin_logged_in = False
            st.success("ログアウトしました。")
            time.sleep(1)
            st.rerun()

# --- メイン画面の表示切り替え ---

if not st.session_state.is_logged_in:
    # --- トップページ（入室画面） ---
    st.title("かもやんの部屋へようこそ！")

    st.subheader("投稿状況(1日程度で履歴はクリアされます)")
    st.info("部屋ごとの投稿数を表示しています。")
    login_message_counts_df = count_messages_per_room()
    # 投稿数を部屋番号をキーにした辞書に変換
    counts_dict = dict(zip(login_message_counts_df['room_id'], login_message_counts_df['message_count']))
    
    # 1からMAX_ROOMまでの部屋の情報を整形して表示
    cols = st.columns(5)
    for i in range(1, MAX_ROOM+1):
        room_count = counts_dict.get(i, 0)
        col = cols[(i-1) % 5]
        col.metric(label=f"部屋 {i}", value=f"{room_count} 件")

    st.subheader("チャットルームに入室する")
    with st.form("login_form"):
        room_id_input = st.number_input(
            "部屋番号", min_value=1, max_value=MAX_ROOM, step=1
        )
        nickname_input = st.text_input("ニックネーム")
        submitted = st.form_submit_button("入室する")

        if submitted:
            if not nickname_input:
                st.error("ニックネームを入力してください。")
            else:
                st.session_state.is_logged_in = True
                st.session_state.nickname = nickname_input
                st.session_state.room_id = room_id_input
                st.rerun()

else:
    # --- チャットルーム画面 ---
    st.title(f"チャットルーム (部屋 {st.session_state.room_id})")

    if st.button("退室する"):
        st.session_state.is_logged_in = False
        st.session_state.nickname = ""
        st.session_state.room_id = 0
        st.rerun()

    # チャット履歴の表示
    chat_container = st.container()
    with chat_container:
        messages = get_messages(st.session_state.room_id)
        for msg in messages:
            with st.chat_message(name=msg["nickname"]):
                st.markdown(f'**{msg["nickname"]}** ({msg["timestamp"]})')
                st.markdown(msg["message"])

    # メッセージ入力
    if prompt := st.chat_input("メッセージをどうぞ"):
        add_message(st.session_state.room_id, st.session_state.nickname, prompt)
        st.rerun()