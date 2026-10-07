import streamlit as st
import pandas as pd
import numpy as np
import json
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, timedelta
import re
import os
import io
import requests
import time
import base64
from PIL import Image, ImageOps

# --- 1. ページ設定 ---
st.set_page_config(layout="wide", page_title="投球解析システム")

# ==========================================
# 🔒 簡易パスワード認証システム
# ==========================================
def check_password():
    """パスワードが正しいかチェックし、セッション状態を更新する"""
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False
    
    if st.session_state["authenticated"]:
        return True

    st.title("🔒 投球解析システム - ログイン")
    
    with st.form("login_form"):
        password_input = st.text_input("パスワードを入力してください", type="password")
        submit_button = st.form_submit_button("ログイン")
        
        if submit_button:
            if password_input == "1189":
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("❌ パスワードが間違っています。")
                
    return False

if not check_password():
    st.stop()

# ==========================================
# 🚀 メインロジック
# ==========================================

GITHUB_TOKEN = (
    st.secrets.get("PITCHING_FEEDBACK") or 
    st.secrets.get("GITHUB_TOKEN") or 
    os.environ.get("GITHUB_TOKEN", "")
)

GITHUB_REPO = "sakanatama-hub/Pitching-feedback"  
GITHUB_PITCH_FILE_PATH = "data/pitch_data.xlsx"

# 🖼️ シルエット画像のRaw URL
SILHOUETTE_IMAGE_URL = "https://raw.githubusercontent.com/sakanatama-hub/Pitching-feedback/main/data/assets%3Arelease_silhouette.png"

def load_data_from_github(file_path):
    if not GITHUB_TOKEN:
        st.error("【設定エラー】StreamlitのSecretsにトークンが設定されていないか、読み込めていません。")
        return pd.DataFrame()
        
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{file_path}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    res = requests.get(url, headers=headers)
    
    if res.status_code == 200:
        content = res.json()
        download_url = content["download_url"]
        file_res = requests.get(download_url)
        df = pd.read_excel(io.BytesIO(file_res.content))
        if 'TaggedPitchType' in df.columns:
            df['TaggedPitchType'] = df['TaggedPitchType'].replace('Sinker', 'Two seam')
        return df
    else:
        return pd.DataFrame()

def save_to_github_direct(df_to_save, file_path, message_text="Update pitch data"):
    if not GITHUB_TOKEN:
        return False, "Secretsにトークンが設定されていません。"
        
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{file_path}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    
    res = requests.get(url, headers=headers)
    sha = None
    if res.status_code == 200:
        file_info = res.json()
        sha = file_info.get("sha")

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_to_save.to_excel(writer, index=False)
    excel_data = output.getvalue()
    
    content_b64 = base64.b64encode(excel_data).decode("utf-8")
    
    payload = {
        "message": message_text,
        "content": content_b64
    }
    if sha:
        payload["sha"] = sha
        
    put_res = requests.put(url, headers=headers, json=payload)
    
    if put_res.status_code in [200, 201]:
        st.session_state['pitch_df'] = df_to_save
        return True, "成功"
    else:
        return False, put_res.json().get("message", "GitHubへの保存に失敗しました。")

if 'pitch_df' not in st.session_state:
    with st.spinner("GitHubから最新の投球データを読み込み中..."):
        st.session_state['pitch_df'] = load_data_from_github(GITHUB_PITCH_FILE_PATH)

PLAYER_HANDS = {
    "#11 大栄 陽斗": "右", "#12 村上 崚久": "右", "#13 細川 拓哉": "右", 
    "#14 ヴァデルナ・フェルガス": "左", "#15 渕上 佳輝": "右", "#16 後藤 凌寿": "右", 
    "#17 加藤 泰靖": "右", "#18 市川 祐": "右", "#19 高尾 響": "右", 
    "#20 嘉陽 宗一郎": "右", "#21 池村 健太郎": "左", "#30 平野 大智": "右"
}

COLOR_MAP_PITCH = {
    "Straight": "red", "Fastball": "red", "ストレート": "red", "四縫線": "red", "4-Seam": "red",
    "Split": "blue", "Splitter": "blue", "スプリット": "blue",
    "Changeup": "green", "CH": "green", "チェンジアップ": "green",
    "Cutter": "orange", "Cut": "orange", "カット": "orange",
    "Slider": "yellow", "SL": "yellow", "スライダー": "yellow",
    "Curve": "darkblue", "Curveball": "darkblue", "CU": "darkblue", "カーブ": "darkblue",
    "Sinker": "pink", "SI": "pink", "シンカー": "pink", "TwoSeam": "pink"
}

COLUMN_MAP = {
    'TaggedPitchType': 'Pitch Type', 'RelSpeed': 'Velocity', 'SpinRate': 'Spin Rate',
    'Tilt': 'Spin Direction', 'InducedVertBreak': 'VB', 'HorzBreak': 'HB',
    'SpinEfficiency': 'Spin Efficiency',
    'Total Spin': 'Spin Rate',
    'True Spin (release)': 'True Spin',
    'Spin Efficiency (release)': 'Spin Efficiency',
    'Spin Direction': 'Spin Direction',
    'VB (trajectory)': 'VB',
    'HB (trajectory)': 'HB',
    'Velocity': 'Velocity',
    'RelHeight': 'RelHeight',
    'RelSide': 'RelSide',
    'Release Height': 'RelHeight',
    'Release Side': 'RelSide',
    'Release Height (release)': 'RelHeight',
    'Release Side (release)': 'RelSide'
}

def time_to_degrees(time_str):
    try:
        match = re.match(r"(\d+):(\d+)", str(time_str))
        if not match: return 0.0
        hh, mm = map(int, match.groups())
        return ((hh % 12) * 60 + mm) * 0.5
    except:
        return 0.0

@st.cache_data(ttl=3600)
def get_processed_silhouette_b64(is_right_handed=True):
    """
    GitHubのRaw URLから画像を直接ダウンロードし、背景透過および「右投手の場合に反転」処理を行う関数
    """
    headers = {}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"

    try:
        r = requests.get(SILHOUETTE_IMAGE_URL, headers=headers, timeout=5)
        if r.status_code != 200:
            return None

        img = Image.open(io.BytesIO(r.content)).convert("RGBA")
        
        # 白色の背景を透明化する処理
        datas = img.getdata()
        newData = []
        for item in datas:
            if item[0] > 210 and item[1] > 210 and item[2] > 210:
                newData.append((255, 255, 255, 0))
            else:
                newData.append(item)
        img.putdata(newData)
        
        # 右投手の場合に画像を左右反転させる
        if is_right_handed:
            img = ImageOps.mirror(img)
            
        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        return f"data:image/png;base64,{base64.b64encode(buffered.getvalue()).decode('utf-8')}"
    except Exception as e:
        return None

def add_pitcher_url_background(fig, is_right_handed=True):
    """
    手元（ボール）の位置が実際のリリースデータ（高さ1.55m~1.65m, 横0.5m~0.6m）に
    ぴったり重なるよう配置座標とサイズを調整
    """
    img_src = get_processed_silhouette_b64(is_right_handed)
    
    if img_src:
        if is_right_handed:
            x_min, x_max = -0.32, 1.08
        else:
            x_min, x_max = -1.08, 0.32
            
        y_min, y_max = -0.35, 1.80

        fig.add_layout_image(
            dict(
                source=img_src,
                xref="x",
                yref="y",
                x=x_min,
                y=y_max,
                sizex=abs(x_max - x_min),
                sizey=abs(y_max - y_min),
                sizing="stretch",
                opacity=0.45,
                layer="below"
            )
        )

# --- タブ構造の定義 ---
tab1, tab2 = st.tabs(["📊 分析フィードバック", "📥 投手データ登録・削除"])

# ==========================================
# タブ2：投手データ登録・削除
# ==========================================
with tab2:
    st.header("📝 投手データ管理（登録・削除）")
    
    op_mode = st.radio(
        "行う操作を選択してください",
        ["📥 新規データの追加登録", "🗑️ 登録済みデータの選択削除"],
        horizontal=True,
        key="pitch_manage_op_mode"
    )
    
    st.divider()

    if op_mode == "📥 新規データの追加登録":
        st.subheader("📥 投球データのアップロード")
        
        col_reg1, col_reg2, col_reg3 = st.columns(3)
        with col_reg1:
            target_player = st.selectbox("対象の選手を選択", sorted(list(PLAYER_HANDS.keys())), key="pitch_reg_p")
        with col_reg2:
            target_date = st.date_input("対象の日付を選択", date.today(), key="pitch_reg_d")
        with col_reg3:
            data_type = st.radio("練習種別（試合区別）", ["ブルペン", "シートBT"], horizontal=True, key="pitch_reg_type")
        
        data_source = st.radio("アップロードするデータの種類（計測機器）を選択", ["Trackman（トラックマン）", "Rapsodo（ラプソード）"], horizontal=True, key="pitch_reg_source")
        uploaded_file = st.file_uploader("投球データファイルをアップロード (.csv / .xlsx)", type=['csv', 'xlsx', 'xls'], key="pitch_file_uploader")
        
        if uploaded_file is not None:
            if st.button("🚀 投球データをGitHubへ保存", key="btn_save_pitch", use_container_width=True):
                with st.spinner("データを処理してGitHubへ同期保存中..."):
                    try:
                        file_ext = os.path.splitext(uploaded_file.name)[-1].lower()
                        if file_ext == '.csv':
                            temp_df = pd.read_csv(uploaded_file, nrows=15, header=None)
                            skip = next((i for i, row in temp_df.iterrows() if any(k in str(row.values) for k in ["PitchNo", "Pitcher", "Pitch Type", "Total Spin"])), 0)
                            uploaded_file.seek(0)
                            new_df = pd.read_csv(uploaded_file, skiprows=skip)
                        else:
                            temp_df = pd.read_excel(uploaded_file, nrows=15, header=None)
                            skip = next((i for i, row in temp_df.iterrows() if any(k in str(row.values) for k in ["PitchNo", "Pitcher", "Pitch Type", "Total Spin"])), 0)
                            uploaded_file.seek(0)
                            new_df = pd.read_excel(uploaded_file, skiprows=skip)
                            
                        new_df = new_df.rename(columns=COLUMN_MAP)
                        new_df['Player Name'] = target_player
                        new_df['Date'] = target_date.strftime('%Y-%m-%d')
                        new_df['Data Type'] = data_type
                        new_df['Data Source'] = data_source
                        
                        cols_to_num = ['Spin Rate', 'Spin Efficiency', 'VB', 'HB', 'Velocity', 'RelHeight', 'RelSide']
                        for c in cols_to_num:
                            if c in new_df.columns:
                                new_df[c] = pd.to_numeric(new_df[c].astype(str).str.replace('%', ''), errors='coerce')
                        
                        latest_db = load_data_from_github(GITHUB_PITCH_FILE_PATH)
                        if not latest_db.empty:
                            target_condition = (
                                (latest_db['Player Name'] == target_player) & 
                                (latest_db['Date'] == target_date.strftime('%Y-%m-%d')) & 
                                (latest_db['Data Type'] == data_type)
                            )
                            modified_db = latest_db[~target_condition]
                            updated_db = pd.concat([modified_db, new_df], ignore_index=True)
                        else:
                            updated_db = new_df
                            
                        success, message = save_to_github_direct(updated_db, GITHUB_PITCH_FILE_PATH, f"Add pitch data: {target_player}")
                        if success:
                            st.success(f"✅ {target_player} のデータを [{data_source} - {data_type}] としてGitHubへ保存しました！")
                            st.balloons()
                        else:
                            st.error(f"❌ GitHubへの保存に失敗しました: {message}")
                    except Exception as e:
                        st.error(f"❌ 解析・保存エラー: {e}")

    else:
        st.subheader("🗑️ 登録済みデータの選択・完全削除")
        
        db_df = load_data_from_github(GITHUB_PITCH_FILE_PATH)
        
        if db_df.empty:
            st.warning("現在、データベースに登録済みのデータが見つかりません。")
        else:
            db_df['Date'] = db_df['Date'].astype(str)
            if 'Data Source' not in db_df.columns:
                db_df['Data Source'] = "標準"
            else:
                db_df['Data Source'] = db_df['Data Source'].fillna("標準")
                
            registered_players = sorted(db_df['Player Name'].dropna().unique().tolist())
            
            del_selected_player = st.selectbox("1. 削除対象の選手を選択してください", registered_players, key="del_p_select")
            player_records = db_df[db_df['Player Name'] == del_selected_player]
            
            group_keys = ['Date', 'Data Type', 'Data Source']
            sessions = player_records.groupby(group_keys).size().reset_index(name='投球数')
            
            if sessions.empty:
                st.info(f"ℹ️ {del_selected_player} の登録データはありません。")
            else:
                session_options = []
                for idx, r in sessions.iterrows():
                    session_options.append(f"{r['Date']} | {r['Data Type']} | {r['Data Source']} ({r['投球数']}球)")
                
                del_selected_session = st.selectbox("2. 削除するデータ項目を選択してください", session_options, key="del_s_select")
                
                sel_idx = session_options.index(del_selected_session)
                target_session = sessions.iloc[sel_idx]
                
                s_date = target_session['Date']
                s_type = target_session['Data Type']
                s_source = target_session['Data Source']
                
                delete_target_mask = (
                    (db_df['Player Name'] == del_selected_player) & 
                    (db_df['Date'] == s_date) & 
                    (db_df['Data Type'] == s_type) & 
                    (db_df['Data Source'] == s_source)
                )
                
                target_df = db_df[delete_target_mask]
                
                st.markdown("---")
                st.subheader("🎯 削除の細かさを指定")
                
                del_scope = st.radio(
                    "削除の範囲を選択してください",
                    ["選択したセッションの全データを一括削除", "指定した球種のみ削除", "特定の1球を選んで削除"],
                    key="del_scope_option"
                )
                
                final_delete_mask = delete_target_mask.copy()
                
                if del_scope == "選択したセッションの全データを一括削除":
                    st.error(f"🚨 **削除内容確認**: 【{del_selected_player}】 の **{s_date} ({s_type} / {s_source})** 全 {len(target_df)} 件を削除します。")
                
                elif del_scope == "指定した球種のみ削除":
                    if 'Pitch Type' in target_df.columns:
                        avail_types = sorted(target_df['Pitch Type'].dropna().unique().tolist())
                        sel_pt = st.selectbox("削除したい球種を選択", avail_types, key="del_pt_select")
                        
                        final_delete_mask = delete_target_mask & (db_df['Pitch Type'] == sel_pt)
                        del_cnt = len(db_df[final_delete_mask])
                        st.error(f"🚨 **削除内容確認**: 【{del_selected_player}】 の **{s_date} ({s_type})** から **球種: {sel_pt}** ({del_cnt}件) を削除します。")
                    else:
                        st.warning("球種データが見つからないため一括削除を行います。")

                elif del_scope == "特定の1球を選んで削除":
                    preview_df = target_df.reset_index()
                    
                    row_options = preview_df['index'].tolist()
                    def format_row(row_idx):
                        r = preview_df[preview_df['index'] == row_idx].iloc[0]
                        pt = r['Pitch Type'] if 'Pitch Type' in r else '不明'
                        vel = f"{r['Velocity']} km/h" if 'Velocity' in r else ''
                        return f"ID:{row_idx} - 球種:{pt} {vel}"

                    selected_row_idx = st.selectbox("削除する1球（行）を選択", row_options, format_func=format_row, key="del_row_select")
                    final_delete_mask = (db_df.index == selected_row_idx)
                    st.error(f"🚨 **削除内容確認**: ID {selected_row_idx} の1球データのみ削除します。")

                st.markdown("---")
                st.write("▼ 削除対象となるデータのプレビュー")
                st.dataframe(db_df[final_delete_mask][['Player Name', 'Date', 'Data Type', 'Pitch Type', 'Velocity']].head(10), use_container_width=True)
                
                confirm_check = st.checkbox("上記データを削除することを確認しました", key="del_final_check")
                
                if st.button("🚨 このデータを完全に削除する", key="btn_execute_delete", disabled=not confirm_check, type="primary", use_container_width=True):
                    with st.spinner("GitHub上のデータベースから削除を実行中..."):
                        try:
                            cleaned_db = db_df[~final_delete_mask]
                            
                            success, msg = save_to_github_direct(cleaned_db, GITHUB_PITCH_FILE_PATH, f"Delete pitch data: {del_selected_player}")
                            
                            if success:
                                st.success("🎉 データの削除が正常に完了しました！")
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error(f"❌ 削除データの保存に失敗しました: {msg}")
                        except Exception as ex:
                            st.error(f"❌ 削除処理エラー: {ex}")

# ==========================================
# タブ1：分析フィードバック
# ==========================================
with tab1:
    st.header("投球解析フィードバック")
    
    df_all = st.session_state['pitch_df'].copy()
    
    if df_all.empty:
        st.info("データが未登録か、GitHubからロードできませんでした。「投手データ登録・削除」タブからアップロードしてください。")
    else:
        if 'Data Source' not in df_all.columns:
            df_all['Data Source'] = "Trackman（トラックマン）"
        else:
            df_all['Data Source'] = df_all['Data Source'].fillna("Trackman（トラックマン）")
            
        available_players = sorted(df_all['Player Name'].dropna().unique())
        
        sel_c1, sel_c2, sel_c3, sel_c4 = st.columns(4)
        with sel_c1:
            p_name = st.selectbox("分析する選手", available_players, key="pitch_view_p")
        
        df_player = df_all[df_all['Player Name'] == p_name].copy()
        df_player['Date'] = pd.to_datetime(df_player['Date']).dt.date
        
        today = date.today()
        current_year = today.year
        
        available_dates = sorted(df_player['Date'].unique())
        if available_dates:
            target_year = available_dates[-1].year
            min_data_date = available_dates[0]
            max_data_date = available_dates[-1]
        else:
            target_year = current_year
            min_data_date = today
            max_data_date = today
            
        period_options = ["全体", "今日", "今週", "今月"]
        for m in range(1, 12 + 1):
            period_options.append(f"{m}月")
        period_options.append("カスタム")
        
        with sel_c2:
            selected_period = st.selectbox("分析対象の期間", period_options, index=0, key="pitch_period_select")
        
        start_date, end_date = None, None
        
        if selected_period == "全体":
            start_date, end_date = min_data_date, max_data_date
        elif selected_period == "今日":
            start_date, end_date = today, today
        elif selected_period == "今週":
            start_date = today - timedelta(days=6)
            end_date = today
        elif selected_period == "今月":
            start_date = today.replace(day=1)
            next_month = today.replace(day=28) + timedelta(days=4)
            end_date = next_month.replace(day=1) - timedelta(days=1)
        elif "月" in selected_period:
            try:
                m_num = int(selected_period.replace("月", ""))
                start_date = date(target_year, m_num, 1)
                if m_num == 12:
                    end_date = date(target_year, 12, 31)
                else:
                    end_date = date(target_year, m_num + 1, 1) - timedelta(days=1)
            except Exception as e:
                start_date, end_date = min_data_date, max_data_date
        elif selected_period == "カスタム":
            with st.container():
                custom_range = st.date_input("細かく日程を指定", value=(min_data_date, max_data_date), min_value=min_data_date, max_value=max_data_date, key="pitch_view_d")
                if isinstance(custom_range, tuple) and len(custom_range) == 2:
                    start_date, end_date = custom_range
                elif isinstance(custom_range, date):
                    start_date, end_date = custom_range, custom_range
                    
        with sel_c3:
            view_type = st.selectbox("練習種別フィルター", ["両方（すべて表示）", "ブルペンのみ", "シートBTのみ"], key="pitch_view_type")
        with sel_c4:
            source_filter = st.selectbox("データ元フィルター", ["両方（すべて表示）", "Trackmanのみ", "Rapsodoのみ"], key="pitch_view_source")
        
        if start_date and end_date:
            df = df_player[(df_player['Date'] >= start_date) & (df_player['Date'] <= end_date)].copy()
            
            if view_type == "ブルペンのみ":
                df = df[df['Data Type'] == "ブルペン"]
            elif view_type == "シートBTのみ":
                df = df[df['Data Type'] == "シートBT"]
                
            if source_filter == "Trackmanのみ":
                df = df[df['Data Source'].astype(str).str.contains("Trackman")]
            elif source_filter == "Rapsodoのみ":
                df = df[df['Data Source'].astype(str).str.contains("Rapsodo")]
        else:
            df = pd.DataFrame()
            
        if not df.empty:
            df['ID'] = df.index
            
            cols_to_num = ['Spin Rate', 'Spin Efficiency', 'VB', 'HB', 'Velocity', 'RelHeight', 'RelSide']
            for c in cols_to_num:
                if c in df.columns:
                    df[c] = pd.to_numeric(df[c].astype(str).str.replace('%', ''), errors='coerce')

            hand = PLAYER_HANDS.get(p_name, "右")
            is_right_hand = (hand == "右")
            
            c_dir, c_rev, c_eff, c_vb, c_hb, c_vel, c_rh, c_rs = 'Spin Direction', 'Spin Rate', 'Spin Efficiency', 'VB', 'HB', 'Velocity', 'RelHeight', 'RelSide'
            
            # ==========================================
            # 💡 チーム全投手のリリース平均ポイント（符号調整＆ヴァデルナ除外）の計算
            # ==========================================
            df_team_calc = df_all.copy()
            for c in [c_rh, c_rs]:
                if c in df_team_calc.columns:
                    df_team_calc[c] = pd.to_numeric(df_team_calc[c].astype(str).str.replace('%', ''), errors='coerce')
            
            # 1. ヴァデルナ選手を平均算出から除外
            df_team_calc = df_team_calc[~df_team_calc['Player Name'].astype(str).str.contains("ヴァデルナ")].dropna(subset=[c_rh, c_rs])
            
            if not df_team_calc.empty:
                # 2. 左投手のRelSide（池村等）は絶対値（正の値）に変換して「身体中心からの距離」を全投手共通で平均計算
                df_team_calc['RelSide_abs'] = df_team_calc[c_rs].abs()
                
                team_avg_rh = df_team_calc[c_rh].mean()
                team_abs_rs = df_team_calc['RelSide_abs'].mean()
                
                # 3. グラフ表示時、対象選手が左投手（ヴァデルナ・池村等）の場合は符号をマイナスに反転
                team_display_rs = team_abs_rs if is_right_hand else -team_abs_rs
            else:
                team_avg_rh, team_display_rs = None, None

            if 'Pitch Type' in df.columns:
                st.subheader(f"📊 平均データサマリー ({start_date} ～ {end_date} / {view_type} / {source_filter})")
                
                agg_dict = {}
                for c in [c_vel, c_rev, c_eff, c_vb, c_hb, c_rh, c_rs]:
                    if c in df.columns:
                        agg_dict[c] = ['mean', 'max'] if c == c_vel else 'mean'
                
                stats_df = df.groupby('Pitch Type').agg(agg_dict).reset_index()
                stats_df.columns = [f"{col[0]}_{col[1]}" if col[1] else col[0] for col in stats_df.columns]
                
                rename_dict = {
                    f"{c_vel}_mean": "平均球速", f"{c_vel}_max": "最高球速",
                    f"{c_rev}_mean": "平均回転数", f"{c_eff}_mean": "回転効率 (%)",
                    f"{c_vb}_mean": "縦変化量 (VB)", f"{c_hb}_mean": "横変化量 (HB)",
                    f"{c_rh}_mean": "リリース高さ (m)", f"{c_rs}_mean": "リリース横位置 (m)"
                }
                stats_df = stats_df.rename(columns=rename_dict)
                st.dataframe(stats_df.style.format(precision=2), use_container_width=True)
                
                st.divider()
                st.subheader("📈 変化量マップ")
                plot_col1, plot_col2 = st.columns(2)
                
                hover_items = ['ID', 'Date', 'Data Type', c_vel]
                if 'Data Source' in df.columns:
                    hover_items.append('Data Source')
                    
                with plot_col1:
                    st.write("▼ 全投球プロット")
                    fig_all = px.scatter(
                        df, 
                        x=c_hb, 
                        y=c_vb, 
                        color='Pitch Type', 
                        range_x=[-60, 60], 
                        range_y=[-60, 60], 
                        color_discrete_map=COLOR_MAP_PITCH, 
                        hover_data=hover_items
                    )
                    fig_all.add_hline(y=0, line_dash="dash", line_color="black")
                    fig_all.add_vline(x=0, line_dash="dash", line_color="black")
                    fig_all.update_layout(plot_bgcolor='white', width=550, height=550, yaxis=dict(scaleanchor="x", scaleratio=1, gridcolor='lightgray'), xaxis=dict(gridcolor='lightgray'))
                    st.plotly_chart(fig_all, use_container_width=False)
                with plot_col2:
                    st.write("▼ 球種別平均プロット")
                    plot_x = "横変化量 (HB)" if "横変化量 (HB)" in stats_df.columns else f"{c_hb}_mean"
                    plot_y = "縦変化量 (VB)" if "縦変化量 (VB)" in stats_df.columns else f"{c_vb}_mean"
                    fig_avg = px.scatter(stats_df, x=plot_x, y=plot_y, color='Pitch Type', text='Pitch Type', range_x=[-60, 60], range_y=[-60, 60], color_discrete_map=COLOR_MAP_PITCH)
                    fig_avg.update_traces(marker=dict(size=15), textposition='top center')
                    fig_avg.add_hline(y=0, line_dash="dash", line_color="black")
                    fig_avg.add_vline(x=0, line_dash="dash", line_color="black")
                    fig_avg.update_layout(plot_bgcolor='white', width=550, height=550, yaxis=dict(scaleanchor="x", scaleratio=1, gridcolor='lightgray'), xaxis=dict(gridcolor='lightgray'))
                    st.plotly_chart(fig_avg, use_container_width=False)

                # --- 📍 リリース位置プロット ---
                st.divider()
                st.subheader(f"📍 リリース位置（投手目線 / {hand}投手）")
                
                if c_rh in df.columns and c_rs in df.columns and not df[[c_rh, c_rs]].dropna().empty:
                    rel_col1, rel_col2 = st.columns(2)
                    
                    hover_items_rel = ['ID', 'Date', 'Data Type', c_vel, c_rh, c_rs]
                    if 'Data Source' in df.columns:
                        hover_items_rel.append('Data Source')
                        
                    x_range = [0.0, 1.2] if is_right_hand else [-1.2, 0.0]
                    y_range = [1.0, 2.3]  # y軸は1.0m以上から表示
                    
                    with rel_col1:
                        st.write("▼ 全投球リリース位置")
                        fig_rel_all = px.scatter(
                            df.dropna(subset=[c_rh, c_rs]),
                            x=c_rs,
                            y=c_rh,
                            color='Pitch Type',
                            range_x=x_range,
                            range_y=y_range,
                            labels={c_rs: '左右 [m]', c_rh: '高さ [m]'},
                            color_discrete_map=COLOR_MAP_PITCH,
                            hover_data=hover_items_rel
                        )
                        add_pitcher_url_background(fig_rel_all, is_right_hand)
                        
                        # 💡 チーム全投手のリリース平均ポイント（★マーク）の追加（左投手はマイナス反転表示）
                        if team_display_rs is not None and team_avg_rh is not None:
                            fig_rel_all.add_trace(go.Scatter(
                                x=[team_display_rs],
                                y=[team_avg_rh],
                                mode='markers+text',
                                name='チーム平均',
                                text=['★ チーム平均'],
                                textposition='top center',
                                marker=dict(size=18, color='black', symbol='star', line=dict(width=1, color='white')),
                                hoverinfo='text',
                                hovertext=f"チーム平均<br>高さ: {team_avg_rh:.2f}m<br>左右: {team_display_rs:.2f}m"
                            ))
                        
                        fig_rel_all.add_hline(y=0, line_width=2, line_color="black")
                        fig_rel_all.add_vline(x=0, line_dash="dash", line_color="gray")
                        fig_rel_all.update_layout(
                            plot_bgcolor='white', 
                            width=550, 
                            height=550, 
                            yaxis=dict(gridcolor='lightgray', dtick=0.1), 
                            xaxis=dict(gridcolor='lightgray', dtick=0.2)
                        )
                        st.plotly_chart(fig_rel_all, use_container_width=False)
                        
                    with rel_col2:
                        st.write("▼ 球種別平均リリース位置")
                        rel_stats = df.groupby('Pitch Type').agg({c_rs: 'mean', c_rh: 'mean'}).reset_index()
                        fig_rel_avg = px.scatter(
                            rel_stats,
                            x=c_rs,
                            y=c_rh,
                            color='Pitch Type',
                            text='Pitch Type',
                            range_x=x_range,
                            range_y=y_range,
                            labels={c_rs: '左右 [m]', c_rh: '高さ [m]'},
                            color_discrete_map=COLOR_MAP_PITCH
                        )
                        add_pitcher_url_background(fig_rel_avg, is_right_hand)
                        
                        # 💡 チーム全投手のリリース平均ポイント（★マーク）の追加（左投手はマイナス反転表示）
                        if team_display_rs is not None and team_avg_rh is not None:
                            fig_rel_avg.add_trace(go.Scatter(
                                x=[team_display_rs],
                                y=[team_avg_rh],
                                mode='markers+text',
                                name='チーム平均',
                                text=['★ チーム平均'],
                                textposition='top center',
                                marker=dict(size=18, color='black', symbol='star', line=dict(width=1, color='white')),
                                hoverinfo='text',
                                hovertext=f"チーム平均<br>高さ: {team_avg_rh:.2f}m<br>左右: {team_display_rs:.2f}m"
                            ))
                        
                        fig_rel_avg.update_traces(marker=dict(size=15), textposition='top center')
                        fig_rel_avg.add_hline(y=0, line_width=2, line_color="black")
                        fig_rel_avg.add_vline(x=0, line_dash="dash", line_color="gray")
                        fig_rel_avg.update_layout(
                            plot_bgcolor='white', 
                            width=550, 
                            height=550, 
                            yaxis=dict(gridcolor='lightgray', dtick=0.1), 
                            xaxis=dict(gridcolor='lightgray', dtick=0.2)
                        )
                        st.plotly_chart(fig_rel_avg, use_container_width=False)
                else:
                    st.info("ℹ️ リリース位置データ（RelHeight / RelSide）が含まれていないか、有効な数値データが存在しません。")

                # --- 3Dスピンビジュアライザー ---
                st.divider()
                st.subheader("⚾️ 3D軌道")
                valid_df = df.dropna(subset=['Pitch Type', c_dir, c_rev])
                
                if not valid_df.empty:
                    available_types = sorted(valid_df['Pitch Type'].dropna().unique())
                    sel_type = st.selectbox("球種を選択して回転を確認:", available_types, key="pitch_viz_select")
                    
                    subset = valid_df[valid_df['Pitch Type'] == sel_type]
                    avg_rpm = subset[c_rev].mean()
                    avg_eff = subset[c_eff].mean() if c_eff in subset.columns else 100.0
                    avg_tilt_str = str(subset[c_dir].iloc[0])
                    tilt_deg = time_to_degrees(avg_tilt_str)
                    
                    st.write(f"**{sel_type}** の平均データ： 回転数 {avg_rpm:.0f} RPM / 効率 {avg_eff:.1f}% / Tilt {avg_tilt_str}")
                    
                    # 3D回転座標計算
                    t = np.linspace(0, 2 * np.pi, 200)
                    alpha = 0.4
                    sx, sy, sz = np.cos(t) + alpha * np.cos(3*t), np.sin(t) - alpha * np.sin(3*t), 2 * np.sqrt(alpha * (1 - alpha)) * np.sin(2*t)
                    base_pts = np.vstack([sx, sz, sy]).T 
                    
                    tilt_rad = np.deg2rad(tilt_deg)
                    rot_y = np.array([[np.cos(tilt_rad), 0, -np.sin(tilt_rad)], [0, 1, 0], [np.sin(tilt_rad), 0, np.cos(tilt_rad)]])
                    gyro_rad = np.deg2rad((100 - avg_eff) * 0.9)
                    g_sign = -1 if is_right_hand else 1
                    rot_gyro = np.array([[1, 0, 0], [0, np.cos(gyro_rad), g_sign*np.sin(gyro_rad)], [0, -g_sign*np.sin(gyro_rad), np.cos(gyro_rad)]])
                    
                    combined_rot = rot_y @ rot_gyro
                    axis = combined_rot @ np.array([0.0, 0.0, 1.0])
                    seam_points = (base_pts @ combined_rot.T).tolist()
                    multiplier = -1 if any(k in sel_type.lower() for k in ["cut", "slider", "sl", "curve"]) else 1
                    
                    seam_json = json.dumps(seam_points)
                    axis_json = json.dumps(axis.tolist())
                    
                    html_code = f"""
                    <div id="ball_canvas" style="width:100%; height:600px;"></div>
                    <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
                    <script>
                        (function() {{
                            var points = {seam_json};
                            var axis = {axis_json};
                            var rpm = {avg_rpm};
                            var mult = {multiplier};
                            var cur_angle = 0;
                            function rotate(p, ax, a) {{
                                var c = Math.cos(a), s = Math.sin(a), u = ax[0], v = ax[1], w = ax[2];
                                return [
                                    p[0]*(c+u*u*(1-c)) + p[1]*(u*v*(1-c)-w*s) + p[2]*(u*w*(1-c)+v*s),
                                    p[0]*(v*u*(1-c)+w*s) + p[1]*(c+v*v*(1-c)) + p[2]*(v*w*(1-c)-u*s),
                                    p[0]*(w*u*(1-c)-v*s) + p[1]*(w*v*(1-c)+u*s) + p[2]*(c+w*w*(1-c))
                                ];
                            }}
                            var data = [
                                {{ type: 'scatter3d', mode: 'lines', x: [], y: [], z: [], line: {{color: '#BC1010', width: 15}} }},
                                {{ type: 'scatter3d', mode: 'lines', x: [axis[0]*-1.5, axis[0]*1.5], y: [axis[1]*-1.5, axis[1]*1.5], z: [axis[2]*-1.5, axis[2]*1.5], line: {{color: '#333', width: 5}} }}
                            ];
                            var layout = {{
                                scene: {{ xaxis: {{visible:false}}, yaxis: {{visible:false}}, zaxis: {{visible:false}}, aspectmode:'cube', camera: {{eye: {{x:1.5, y:1.5, z:1.5}} }} }},
                                margin: {{l:0, r:0, b:0, t:0}}
                            }};
                            Plotly.newPlot('ball_canvas', data, layout, {{responsive: true}});
                            function animate() {{
                                cur_angle -= mult * (rpm / 60) * (2 * Math.PI) / 60;
                                var rx = [], ry = [], rz = [];
                                for(var i=0; i<points.length; i++) {{
                                    var r = rotate(points[i], axis, cur_angle);
                                    rx.push(r[0]); ry.push(r[1]); rz.push(r[2]);
                                }}
                                Plotly.restyle('ball_canvas', {{x: [rx, null], y: [ry, null], z: [rz, null]}}, [0]);
                                requestAnimationFrame(animate);
                            }}
                            animate();
                        }})();
                    </script>
                    """
                    st.components.v1.html(html_code, height=600)
