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
# 🖼️ エクステンション用横向きイラストのRaw URL
EXTENSION_IMAGE_URL = "https://raw.githubusercontent.com/sakanatama-hub/Pitching-feedback/main/data/%E3%82%A8%E3%82%AF%E3%82%B9%E3%83%86%E3%83%B3%E3%82%B7%E3%83%A7%E3%83%B3.webp"

# 表記ゆれ・スプリット系完全統一用マッピング（大文字小文字対応）
REPLACE_PITCH_DICT = {
    'CurveBall': 'Curveball', 'Curve ball': 'Curveball', 
    'Sinker': '2seam', 
    'Spritter': 'Splitter', 'spritter': 'Splitter', 'Split': 'Splitter', 'splitter': 'Splitter', 'スプリット': 'Splitter'
}

def standardize_pitch_types(df):
    """データフレーム内の球種表記を完全統一する関数"""
    if df.empty:
        return df
    
    # 部分一致や大文字小文字のゆれも含めてSplitterに統一するための正規化
    for col in ['Pitch Type', 'TaggedPitchType']:
        if col in df.columns:
            df[col] = df[col].replace(REPLACE_PITCH_DICT)
            # 文字列としてスプリット系が含まれるものを強制置換
            mask = df[col].astype(str).str.lower().isin(['spritter', 'split', 'スプリット'])
            df.loc[mask, col] = 'Splitter'
    return df

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
        
        df = standardize_pitch_types(df)
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

    df_to_save = standardize_pitch_types(df_to_save)

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

# アップロード中のロック状態管理
if 'is_uploading' not in st.session_state:
    st.session_state['is_uploading'] = False

PLAYER_HANDS = {
    "#11 大栄 陽斗": "右", "#12 村上 崚久": "右", "#13 細川 拓哉": "右", 
    "#14 ヴァデルナ・フェルガス": "左", "#15 渕上 佳輝": "右", "#16 後藤 凌寿": "右", 
    "#17 加藤 泰靖": "右", "#18 市川 祐": "右", "#19 高尾 響": "右", 
    "#20 嘉陽 宗一郎": "右", "#21 池村 健太郎": "左", "#30 平野 大智": "右"
}

# --- 🎨 視認性重視・高コントラスト球種カラーマップ ---
COLOR_MAP_PITCH = {
    "Straight": "#E60000", "Fastball": "#E60000", "ストレート": "#E60000", "四縫線": "#E60000", "4-Seam": "#E60000", "Four-Seam": "#E60000",
    "Curve": "#000080", "Curveball": "#000080", "CurveBall": "#000080", "CU": "#000080", "カーブ": "#000080",
    "Slider": "#FFD700", "SL": "#FFD700", "スライダー": "#FFD700", "Sweeper": "#8A2BE2", "スイーパー": "#8A2BE2",
    "Cutter": "#FF4500", "Cut": "#FF4500", "カット": "#FF4500", "カットボール": "#FF4500",
    "Split": "#0066FF", "Splitter": "#0066FF", "Spritter": "#0066FF", "スプリット": "#0066FF", "フォーク": "#0066FF", "FS": "#0066FF",
    "Changeup": "#00A86B", "ChangeUp": "#00A86B", "CH": "#00A86B", "チェンジアップ": "#00A86B",
    "Sinker": "#FF1493", "2seam": "#FF1493", "TwoSeam": "#FF1493", "Two-Seam": "#FF1493", "Two seam": "#FF1493", "ツーシーム": "#FF1493"
}

PITCH_ORDER_RANK = {
    "straight": 1, "fastball": 1, "ストレート": 1, "四縫線": 1, "4-seam": 1, "four-seam": 1,
    "curve": 2, "curveball": 2, "cu": 2, "カーブ": 2,
    "slider": 3, "sl": 3, "スライダー": 3, "sweeper": 3, "スイーパー": 3,
    "cutter": 4, "cut": 4, "カット": 4, "カットボール": 4,
    "split": 5, "splitter": 5, "spritter": 5, "スプリット": 5, "フォーク": 5, "fs": 5,
    "changeup": 6, "ch": 6, "チェンジアップ": 6,
    "sinker": 7, "2seam": 7, "si": 7, "シンカー": 7, "twoseam": 7, "two-seam": 7, "two seam": 7, "ツーシーム": 7
}

def get_pitch_rank(pitch_type_str):
    if not pitch_type_str or pd.isna(pitch_type_str):
        return 99
    pt_norm = str(pitch_type_str).strip().lower()
    return PITCH_ORDER_RANK.get(pt_norm, 98)

def sort_pitch_types(pitch_types_list):
    return sorted(list(set(pitch_types_list)), key=lambda x: (get_pitch_rank(x), str(x)))

def get_pitch_color(pitch_type_str):
    if not pitch_type_str or pd.isna(pitch_type_str):
        return "#808080"
    pt = str(pitch_type_str).strip()
    if pt in COLOR_MAP_PITCH:
        return COLOR_MAP_PITCH[pt]
    for k, v in COLOR_MAP_PITCH.items():
        if k.lower() == pt.lower():
            return v
    return "#808080"

def add_symbol_column(df, is_right_hand=True):
    """球種に応じたプロット形状（Symbol）をデータフレームに追加する関数"""
    if df.empty or 'Pitch Type' not in df.columns:
        if 'Symbol' not in df.columns:
            df['Symbol'] = 'circle'
        return df
    
    symbols = []
    cut_sym = 'triangle-left' if is_right_hand else 'triangle-right' # 右投手: ◀︎, 左投手: ▶︎
    
    for pt in df['Pitch Type']:
        if pd.isna(pt):
            symbols.append('circle')
            continue
        pt_lower = str(pt).strip().lower()
        if any(k in pt_lower for k in ["straight", "fastball", "ストレート", "四縫線", "4-seam", "four-seam"]):
            symbols.append('circle')        # ストレート: 丸
        elif any(k in pt_lower for k in ["sinker", "2seam", "twoseam", "two-seam", "two seam", "ツーシーム"]):
            symbols.append('star')          # ツーシーム: 星
        elif any(k in pt_lower for k in ["slider", "sl", "スライダー", "sweeper", "スイーパー"]):
            symbols.append('diamond')       # スライダー: ◆
        elif any(k in pt_lower for k in ["cutter", "cut", "カット"]):
            symbols.append(cut_sym)         # カット: ◀︎ / ▶︎
        elif any(k in pt_lower for k in ["curve", "cu", "カーブ"]):
            symbols.append('triangle-up')   # カーブ: ▲
        elif any(k in pt_lower for k in ["changeup", "ch", "チェンジアップ"]):
            symbols.append('square')        # チェンジ: ▫️
        elif any(k in pt_lower for k in ["split", "splitter", "spritter", "フォーク", "fs"]):
            symbols.append('triangle-down') # フォーク / スプリット: 下向き三角
        else:
            symbols.append('circle')
            
    df['Symbol'] = symbols
    return df

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
    'Release Side (release)': 'RelSide',
    'Release Extension': 'Extension',
    'ReleaseExtension': 'Extension',
    'Extension (release)': 'Extension',
    'Extension [m]': 'Extension',
    'VertRelAngle': 'VertRelAngle',
    'VerticalReleaseAngle': 'VertRelAngle',
    'Vertical Release Angle': 'VertRelAngle'
}

def time_to_degrees(time_str):
    try:
        match = re.match(r"(\d+):(\d+)", str(time_str))
        if not match: return 0.0
        hh, mm = map(int, match.groups())
        return ((hh % 12) * 60 + mm) * 0.5
    except:
        return 0.0

def extract_date_from_filename(filename):
    """ファイル名から日付（YYYY-MM-DD）を自動抽出する関数 (26.02.08 などの下二桁年.月.日形式に対応)"""
    match_yy = re.search(r'(\d{2})[./-](\d{1,2})[./-](\d{1,2})', filename)
    if match_yy:
        yy, m, d = match_yy.groups()
        try:
            full_year = 2000 + int(yy)
            return date(full_year, int(m), int(d)).strftime('%Y-%m-%d')
        except:
            pass

    match_hyphen = re.search(r'(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})日?', filename)
    if match_hyphen:
        y, m, d = match_hyphen.groups()
        try:
            return date(int(y), int(m), int(d)).strftime('%Y-%m-%d')
        except:
            pass
            
    match_8 = re.search(r'(\d{4})(\d{2})(\d{2})', filename)
    if match_8:
        y, m, d = match_8.groups()
        try:
            return date(int(y), int(m), int(d)).strftime('%Y-%m-%d')
        except:
            pass
            
    return date.today().strftime('%Y-%m-%d')

@st.cache_data(ttl=3600)
def get_processed_silhouette_b64(is_right_handed=True):
    headers = {}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"

    try:
        r = requests.get(SILHOUETTE_IMAGE_URL, headers=headers, timeout=5)
        if r.status_code != 200:
            return None

        img = Image.open(io.BytesIO(r.content)).convert("RGBA")
        datas = img.getdata()
        newData = []
        for item in datas:
            if item[0] > 210 and item[1] > 210 and item[2] > 210:
                newData.append((255, 255, 255, 0))
            else:
                newData.append(item)
        img.putdata(newData)
        
        if is_right_handed:
            img = ImageOps.mirror(img)
            
        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        return f"data:image/png;base64,{base64.b64encode(buffered.getvalue()).decode('utf-8')}"
    except Exception as e:
        return None

@st.cache_data(ttl=3600)
def get_processed_extension_silhouette_b64():
    headers = {}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"

    try:
        r = requests.get(EXTENSION_IMAGE_URL, headers=headers, timeout=5)
        if r.status_code != 200:
            return None

        img = Image.open(io.BytesIO(r.content)).convert("RGBA")
        datas = img.getdata()
        newData = []
        for item in datas:
            if item[0] > 220 and item[1] > 220 and item[2] > 220:
                newData.append((255, 255, 255, 0))
            else:
                newData.append(item)
        img.putdata(newData)
            
        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        return f"data:image/png;base64,{base64.b64encode(buffered.getvalue()).decode('utf-8')}"
    except Exception as e:
        return None

def add_pitcher_url_background(fig, is_right_handed=True):
    img_src = get_processed_silhouette_b64(is_right_handed)
    if img_src:
        if is_right_handed:
            x_min, x_max = -0.42, 0.98
        else:
            x_min, x_max = -0.98, 0.42
            
        y_min, y_max = -0.88, 1.72

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

def add_extension_url_background(fig):
    img_src = get_processed_extension_silhouette_b64()
    if img_src:
        fig.add_layout_image(
            dict(
                source=img_src,
                xref="x",
                yref="y",
                x=-0.12,
                y=2.05,
                sizex=2.15,
                sizey=2.05,
                xanchor="left",
                yanchor="top",
                sizing="stretch",
                opacity=0.40,
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
    
    if st.session_state['is_uploading']:
        st.warning("⏳ **【現在：登録処理中（ロック中）】** データをGitHubへ一括保存しています。完了するまで他の操作や次の選手の選択はできません。")
    else:
        st.success("🟢 **【現在：登録可能】** 次の選手やファイルの選択が可能です。「一括登録する」ボタンを押してデータを登録してください。")

    op_mode = st.radio(
        "行う操作を選択してください",
        ["📥 新規データの追加登録", "🗑️ 登録済みデータの選択削除"],
        horizontal=True,
        key="pitch_manage_op_mode",
        disabled=st.session_state['is_uploading']
    )
    
    st.divider()

    if op_mode == "📥 新規データの追加登録":
        st.subheader("📥 投球データの複数ファイル一括アップロード")
        
        col_reg1, col_reg2 = st.columns(2)
        with col_reg1:
            target_player = st.selectbox(
                "対象の選手を選択", 
                sorted(list(PLAYER_HANDS.keys())), 
                key="pitch_reg_p",
                disabled=st.session_state['is_uploading']
            )
        with col_reg2:
            data_type = st.radio(
                "練習種別（試合区別）", 
                ["ブルペン", "シートBT"], 
                horizontal=True, 
                key="pitch_reg_type",
                disabled=st.session_state['is_uploading']
            )
        
        data_source = st.radio(
            "アップロードするデータの種類（計測機器）を選択", 
            ["Trackman（トラックマン）", "Rapsodo（ラプソード）"], 
            horizontal=True, 
            key="pitch_reg_source",
            disabled=st.session_state['is_uploading']
        )
        
        uploaded_files = st.file_uploader(
            "投球データファイルを複数選択してアップロード (.csv / .xlsx)", 
            type=['csv', 'xlsx', 'xls'], 
            accept_multiple_files=True, 
            key="pitch_file_uploader",
            disabled=st.session_state['is_uploading']
        )
        
        if uploaded_files:
            st.info(f"📁 選択されたファイル数: {len(uploaded_files)}件（ファイル名から日付を自動判別します）")
            
            preview_data = []
            for f in uploaded_files:
                parsed_date = extract_date_from_filename(f.name)
                preview_data.append({"ファイル名": f.name, "自動判別された日付": parsed_date})
            st.dataframe(pd.DataFrame(preview_data), use_container_width=True)
            
            if st.button("🚀 投球データを一括登録する", key="btn_save_pitch", disabled=st.session_state['is_uploading'], type="primary", use_container_width=True):
                st.session_state['is_uploading'] = True
                st.rerun()

        if st.session_state['is_uploading'] and uploaded_files:
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            try:
                total_files = len(uploaded_files)
                latest_db = load_data_from_github(GITHUB_PITCH_FILE_PATH)
                updated_db = latest_db.copy() if not latest_db.empty else pd.DataFrame()
                
                success_count = 0
                for idx, uploaded_file in enumerate(uploaded_files):
                    file_name = uploaded_file.name
                    target_date_str = extract_date_from_filename(file_name)
                    status_text.text(f"⏳ 処理中 ({idx+1}/{total_files}): {file_name} (日付: {target_date_str}) を処理しています...")
                    
                    file_ext = os.path.splitext(file_name)[-1].lower()
                    if file_ext == '.csv':
                        bytes_data = uploaded_file.getvalue()
                        try:
                            text_data = bytes_data.decode('utf-8')
                        except UnicodeDecodeError:
                            text_data = bytes_data.decode('shift-jis', errors='ignore')
                            
                        lines = text_data.splitlines()
                        skip = 0
                        for line_idx, line in enumerate(lines):
                            if ('"No"' in line) or ('"Pitch Type"' in line) or ('PitchNo' in line):
                                skip = line_idx
                                break
                                
                        new_df = pd.read_csv(io.StringIO(text_data), skiprows=skip)
                    else:
                        temp_df = pd.read_excel(uploaded_file, nrows=15, header=None)
                        skip = 0
                        for line_idx, row in temp_df.iterrows():
                            row_str = str(row.values)
                            if 'No' in row_str or 'PitchType' in row_str or 'PitchNo' in row_str:
                                skip = line_idx
                                break
                        uploaded_file.seek(0)
                        new_df = pd.read_excel(uploaded_file, skiprows=skip)
                        
                    new_df = new_df.rename(columns=COLUMN_MAP)
                    new_df['Player Name'] = target_player
                    new_df['Date'] = target_date_str
                    new_df['Data Type'] = data_type
                    new_df['Data Source'] = data_source
                    
                    new_df = standardize_pitch_types(new_df)
                    
                    cols_to_num = ['Spin Rate', 'Spin Efficiency', 'VB', 'HB', 'Velocity', 'RelHeight', 'RelSide', 'Extension', 'VertRelAngle']
                    for c in cols_to_num:
                        if c in new_df.columns:
                            new_df[c] = pd.to_numeric(new_df[c].astype(str).str.replace('%', ''), errors='coerce')
                    
                    if not updated_db.empty and all(col in updated_db.columns for col in ['Player Name', 'Date', 'Data Type']):
                        target_condition = (
                            (updated_db['Player Name'] == target_player) & 
                            (updated_db['Date'] == target_date_str) & 
                            (updated_db['Data Type'] == data_type)
                        )
                        updated_db = updated_db[~target_condition]
                        updated_db = pd.concat([updated_db, new_df], ignore_index=True)
                    else:
                        updated_db = new_df
                        
                    success_count += 1
                    progress_bar.progress((idx + 1) / total_files)
                
                status_text.text("💾 GitHubへデータを同期保存中...")
                success, message = save_to_github_direct(updated_db, GITHUB_PITCH_FILE_PATH, f"Batch add pitch data for {target_player}")
                
                if success:
                    st.success(f"🎉 すべてのファイル ({success_count}件) の登録が正常に完了しました！次の選手を選択できるようになりました。")
                    st.balloons()
                else:
                    st.error(f"❌ GitHubへの保存に失敗しました: {message}")
                    
            except Exception as e:
                st.error(f"❌ 処理中にエラーが発生しました: {e}")
            finally:
                st.session_state['is_uploading'] = False
                time.sleep(1.5)
                st.rerun()

    else:
        st.subheader("🗑️ 登録済みデータの選択・完全削除")
        
        db_df = load_data_from_github(GITHUB_PITCH_FILE_PATH)
        db_df = standardize_pitch_types(db_df)
        
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
                    ["選択したセッションの全データを一括削除", "指定した球種のみ削除", "特定の球を複数選んで削除 (複数選択可)"],
                    key="del_scope_option"
                )
                
                final_delete_mask = delete_target_mask.copy()
                
                if del_scope == "選択したセッションの全データを一括削除":
                    st.error(f"🚨 **削除内容確認**: 【{del_selected_player}】 の **{s_date} ({s_type} / {s_source})** 全 {len(target_df)} 件を削除します。")
                
                elif del_scope == "指定した球種のみ削除":
                    if 'Pitch Type' in target_df.columns:
                        avail_types = sort_pitch_types(target_df['Pitch Type'].dropna().unique().tolist())
                        sel_pt = st.selectbox("削除したい球種を選択", avail_types, key="del_pt_select")
                        
                        final_delete_mask = delete_target_mask & (db_df['Pitch Type'] == sel_pt)
                        del_cnt = len(db_df[final_delete_mask])
                        st.error(f"🚨 **削除内容確認**: 【{del_selected_player}】 の **{s_date} ({s_type})** から **球種: {sel_pt}** ({del_cnt}件) を削除します。")
                    else:
                        st.warning("球種データが見つからないため一括削除を行います。")

                elif del_scope == "特定の球を複数選んで削除 (複数選択可)":
                    preview_df = target_df.reset_index()
                    
                    row_options = preview_df['index'].tolist()
                    def format_row(row_idx):
                        r = preview_df[preview_df['index'] == row_idx].iloc[0]
                        pt = r['Pitch Type'] if 'Pitch Type' in r and pd.notna(r['Pitch Type']) else '不明'
                        vel = f"{r['Velocity']} km/h" if 'Velocity' in r and pd.notna(r['Velocity']) else ''
                        return f"ID:{row_idx} - 球種:{pt} {vel}"

                    selected_row_indices = st.multiselect(
                        "削除したい球（1球または複数球）を選択してください",
                        options=row_options,
                        format_func=format_row,
                        key="del_rows_multiselect"
                    )
                    
                    if selected_row_indices:
                        final_delete_mask = db_df.index.isin(selected_row_indices)
                        st.error(f"🚨 **削除内容確認**: 選択された {len(selected_row_indices)} 件の投球データを削除します。")
                    else:
                        final_delete_mask = pd.Series(False, index=db_df.index)
                        st.info("💡 上記の選択ボックスから削除したい球を選択してください。")

                st.markdown("---")
                st.write("▼ 削除対象となるデータのプレビュー")
                st.dataframe(db_df[final_delete_mask][['Player Name', 'Date', 'Data Type', 'Pitch Type', 'Velocity']].head(10), use_container_width=True)
                
                confirm_check = st.checkbox("上記データを削除することを確認しました", key="del_final_check")
                
                if st.button("🚨 このデータを完全に削除する", key="btn_execute_delete", disabled=(not confirm_check or not final_delete_mask.any()), type="primary", use_container_width=True):
                    with st.spinner("GitHub上のデータベースから削除を実行中..."):
                        try:
                            cleaned_db = db_df[~final_delete_mask]
                            success, msg = save_to_github_direct(cleaned_db, GITHUB_PITCH_FILE_PATH, f"Delete pitch data: {del_selected_player}")
                            
                            if success:
                                st.success("🎉 データの削除が正常に完了しました！")
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error(f"❌ 削除データの失敗: {msg}")
                        except Exception as ex:
                            st.error(f"❌ 削除処理エラー: {ex}")

# ==========================================
# タブ1：分析フィードバック
# ==========================================
with tab1:
    st.header("投球解析フィードバック")
    
    df_all = st.session_state['pitch_df'].copy()
    df_all = standardize_pitch_types(df_all)
    
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
            df_base = df_player[(df_player['Date'] >= start_date) & (df_player['Date'] <= end_date)].copy()
            
            if view_type == "ブルペンのみ":
                df_base = df_base[df_base['Data Type'] == "ブルペン"]
            elif view_type == "シートBTのみ":
                df_base = df_base[df_base['Data Type'] == "シートBT"]
        else:
            df_base = pd.DataFrame()
            
        if not df_base.empty:
            df_base = standardize_pitch_types(df_base)
            df_base['ID'] = df_base.index
            cols_to_num = ['Spin Rate', 'Spin Efficiency', 'VB', 'HB', 'Velocity', 'RelHeight', 'RelSide', 'Extension', 'VertRelAngle']
            for c in cols_to_num:
                if c in df_base.columns:
                    df_base[c] = pd.to_numeric(df_base[c].astype(str).str.replace('%', ''), errors='coerce')

            hand = PLAYER_HANDS.get(p_name, "右")
            is_right_hand = (hand == "右")
            
            # 各種データフレームに球種シンボルを追加
            df_base = add_symbol_column(df_base, is_right_hand)
            
            c_dir, c_rev, c_eff, c_vb, c_hb, c_vel, c_rh, c_rs, c_ext = 'Spin Direction', 'Spin Rate', 'Spin Efficiency', 'VB', 'HB', 'Velocity', 'RelHeight', 'RelSide', 'Extension'
            c_vra = 'VertRelAngle'
            
            # --- 変化量・リリース用データ (df_pos_source) ---
            if source_filter == "Trackmanのみ":
                df_pos_source = df_base[df_base['Data Source'].astype(str).str.contains("Trackman")].copy()
            elif source_filter == "Rapsodoのみ":
                df_pos_source = df_base[df_base['Data Source'].astype(str).str.contains("Rapsodo")].copy()
            else:
                df_pos_source = df_base[df_base['Data Source'].astype(str).str.contains("Trackman")].copy()

            df_pos_source = standardize_pitch_types(df_pos_source)
            df_pos_source = add_symbol_column(df_pos_source, is_right_hand)

            # --- 回転系・3D用データ (df_rot_source) ---
            if source_filter == "Rapsodoのみ":
                df_rot_source = df_base[df_base['Data Source'].astype(str).str.contains("Rapsodo")].copy()
            elif source_filter == "Trackmanのみ":
                df_rot_source = df_base[df_base['Data Source'].astype(str).str.contains("Trackman")].copy()
            else:
                rap_chk = df_base[df_base['Data Source'].astype(str).str.contains("Rapsodo")]
                df_rot_source = rap_chk.copy() if not rap_chk.empty else df_base[df_base['Data Source'].astype(str).str.contains("Trackman")].copy()

            df_rot_source = standardize_pitch_types(df_rot_source)
            df_rot_source = add_symbol_column(df_rot_source, is_right_hand)

            # チーム平均算出（位置系はTrackman基準のチーム平均）
            df_team_calc = df_all.copy()
            df_team_calc = standardize_pitch_types(df_team_calc)
            for c in [c_rh, c_rs]:
                if c in df_team_calc.columns:
                    df_team_calc[c] = pd.to_numeric(df_team_calc[c].astype(str).str.replace('%', ''), errors='coerce')
            
            df_team_calc = df_team_calc[
                df_team_calc['Data Source'].astype(str).str.contains("Trackman") & 
                (~df_team_calc['Player Name'].astype(str).str.contains("ヴァデルナ"))
            ].dropna(subset=[c_rh, c_rs])
            
            if not df_team_calc.empty:
                df_team_calc['RelSide_abs'] = df_team_calc[c_rs].abs()
                player_means = df_team_calc.groupby('Player Name').agg({
                    c_rh: 'mean',
                    'RelSide_abs': 'mean'
                }).reset_index()
                
                team_avg_rh = float(player_means[c_rh].mean())
                team_abs_rs = float(player_means['RelSide_abs'].mean())
                team_display_rs = float(team_abs_rs if is_right_hand else -team_abs_rs)
            else:
                team_avg_rh, team_display_rs = None, None

            if 'Pitch Type' in df_base.columns:
                st.subheader(f"📊 平均データサマリー ({start_date} ～ {end_date} / {view_type} / {source_filter})")
                
                agg_dict = {}
                for c in [c_vel, c_rev, c_eff, c_vb, c_hb, c_rh, c_rs, c_ext]:
                    if c in df_base.columns:
                        agg_dict[c] = ['mean', 'max'] if c == c_vel else 'mean'
                
                df_vra_summary = df_base[df_base['Data Source'].astype(str).str.contains("Trackman")]
                if c_vra in df_vra_summary.columns:
                    agg_dict[c_vra] = 'mean'

                stats_df = df_base.groupby('Pitch Type').agg(agg_dict).reset_index()
                stats_df.columns = [f"{col[0]}_{col[1]}" if col[1] else col[0] for col in stats_df.columns]
                
                rename_dict = {
                    f"{c_vel}_mean": "平均球速", f"{c_vel}_max": "最高球速",
                    f"{c_rev}_mean": "平均回転数", f"{c_eff}_mean": "回転効率 (%)",
                    f"{c_vb}_mean": "縦変化量 (VB)", f"{c_hb}_mean": "横変化量 (HB)",
                    f"{c_rh}_mean": "リリース高さ (m)", f"{c_rs}_mean": "リリース横位置 (m)",
                    f"{c_ext}_mean": "エクステンション (m)",
                    f"{c_vra}_mean": "縦リリース角度 (°)"
                }
                stats_df = stats_df.rename(columns=rename_dict)
                
                stats_df['sort_rank'] = stats_df['Pitch Type'].apply(get_pitch_rank)
                stats_df = stats_df.sort_values(by=['sort_rank', 'Pitch Type']).drop(columns=['sort_rank']).reset_index(drop=True)
                
                st.dataframe(stats_df.style.format(precision=2), use_container_width=True)
                
                active_pitch_types = sort_pitch_types(df_pos_source['Pitch Type'].dropna().unique().tolist()) if not df_pos_source.empty else []
                category_orders_dict = {"Pitch Type": active_pitch_types}
                symbol_map_dict = {s: s for s in df_pos_source['Symbol'].unique()} if 'Symbol' in df_pos_source.columns else {}

                # --- 📈 変化量マップ（Trackman基準） ---
                st.divider()
                st.subheader("📈 変化量マップ（Trackman基準）")
                plot_col1, plot_col2 = st.columns(2)
                
                hover_items = ['ID', 'Date', 'Data Type', c_vel]
                if 'Data Source' in df_pos_source.columns:
                    hover_items.append('Data Source')
                    
                with plot_col1:
                    st.write("▼ 全投球プロット")
                    fig_all = px.scatter(
                        df_pos_source, 
                        x=c_hb, 
                        y=c_vb, 
                        color='Pitch Type',
                        symbol='Symbol',
                        symbol_map=symbol_map_dict,
                        range_x=[-60, 60], 
                        range_y=[-60, 60], 
                        color_discrete_map=COLOR_MAP_PITCH,
                        category_orders=category_orders_dict,
                        hover_data=hover_items
                    )
                    fig_all.add_hline(y=0, line_dash="dash", line_color="black")
                    fig_all.add_vline(x=0, line_dash="dash", line_color="black")
                    fig_all.update_layout(plot_bgcolor='white', width=550, height=550, yaxis=dict(scaleanchor="x", scaleratio=1, gridcolor='lightgray'), xaxis=dict(gridcolor='lightgray'))
                    st.plotly_chart(fig_all, use_container_width=False, key="chart_hb_vb_all")
                with plot_col2:
                    st.write("▼ 球種別平均プロット")
                    pos_stats = df_pos_source.groupby('Pitch Type').agg({c_hb: 'mean', c_vb: 'mean'}).reset_index()
                    pos_stats = add_symbol_column(pos_stats, is_right_hand)
                    pos_symbol_map = {s: s for s in pos_stats['Symbol'].unique()}
                    
                    fig_avg = px.scatter(
                        pos_stats, 
                        x=c_hb, 
                        y=c_vb, 
                        color='Pitch Type', 
                        symbol='Symbol',
                        symbol_map=pos_symbol_map,
                        range_x=[-60, 60], 
                        range_y=[-60, 60], 
                        color_discrete_map=COLOR_MAP_PITCH,
                        category_orders=category_orders_dict
                    )
                    fig_avg.update_traces(marker=dict(size=15))
                    fig_avg.add_hline(y=0, line_dash="dash", line_color="black")
                    fig_avg.add_vline(x=0, line_dash="dash", line_color="black")
                    fig_avg.update_layout(plot_bgcolor='white', width=550, height=550, yaxis=dict(scaleanchor="x", scaleratio=1, gridcolor='lightgray'), xaxis=dict(gridcolor='lightgray'))
                    st.plotly_chart(fig_avg, use_container_width=False, key="chart_hb_vb_avg")

                # --- 📍 リリース位置プロット（Trackman基準） ---
                st.divider()
                st.subheader(f"📍 リリース位置（投手目線 / {hand}投手 / Trackman基準）")
                
                if c_rh in df_pos_source.columns and c_rs in df_pos_source.columns and not df_pos_source[[c_rh, c_rs]].dropna().empty:
                    rel_col1, rel_col2, rel_col3 = st.columns(3)
                    
                    hover_items_rel = ['ID', 'Date', 'Data Type', c_vel, c_rh, c_rs]
                    if 'Data Source' in df_pos_source.columns:
                        hover_items_rel.append('Data Source')
                        
                    x_range = [0.0, 1.2] if is_right_hand else [-1.2, 0.0]
                    y_range = [1.0, 2.2]
                    
                    common_release_layout = dict(
                        plot_bgcolor='white',
                        height=400,
                        margin=dict(l=40, r=60, t=30, b=30),
                        yaxis=dict(scaleanchor="x", scaleratio=1, gridcolor='lightgray', dtick=0.1, range=y_range, title='高さ [m]'),
                        xaxis=dict(gridcolor='lightgray', dtick=0.2, range=x_range, title='左右 [m]')
                    )
                    
                    with rel_col1:
                        st.write("▼ 全投球リリース位置")
                        fig_rel_all = px.scatter(
                            df_pos_source.dropna(subset=[c_rh, c_rs]),
                            x=c_rs,
                            y=c_rh,
                            color='Pitch Type',
                            symbol='Symbol',
                            symbol_map=symbol_map_dict,
                            labels={c_rs: '左右 [m]', c_rh: '高さ [m]'},
                            color_discrete_map=COLOR_MAP_PITCH,
                            category_orders=category_orders_dict,
                            hover_data=hover_items_rel
                        )
                        add_pitcher_url_background(fig_rel_all, is_right_hand)
                        
                        if team_display_rs is not None and team_avg_rh is not None:
                            fig_rel_all.add_trace(go.Scatter(
                                x=[team_display_rs],
                                y=[team_avg_rh],
                                mode='markers',
                                name='チーム平均',
                                marker=dict(size=18, color='black', symbol='star', line=dict(width=1, color='white')),
                                hoverinfo='text',
                                hovertext=f"チーム平均<br>高さ: {team_avg_rh:.2f}m<br>左右: {team_display_rs:.2f}m"
                            ))
                        
                        fig_rel_all.add_hline(y=0, line_width=2, line_color="black")
                        fig_rel_all.add_vline(x=0, line_dash="dash", line_color="gray")
                        fig_rel_all.update_layout(**common_release_layout)
                        st.plotly_chart(fig_rel_all, use_container_width=True, key="chart_rel_all")
                        
                    with rel_col2:
                        st.write("▼ 球種別平均リリース位置")
                        rel_stats = df_pos_source.groupby('Pitch Type').agg({c_rs: 'mean', c_rh: 'mean'}).reset_index()
                        rel_stats = add_symbol_column(rel_stats, is_right_hand)
                        rel_stats_symbol_map = {s: s for s in rel_stats['Symbol'].unique()}
                        
                        fig_rel_avg = px.scatter(
                            rel_stats,
                            x=c_rs,
                            y=c_rh,
                            color='Pitch Type',
                            symbol='Symbol',
                            symbol_map=rel_stats_symbol_map,
                            labels={c_rs: '左右 [m]', c_rh: '高さ [m]'},
                            color_discrete_map=COLOR_MAP_PITCH,
                            category_orders=category_orders_dict
                        )
                        add_pitcher_url_background(fig_rel_avg, is_right_hand)
                        
                        if team_display_rs is not None and team_avg_rh is not None:
                            fig_rel_avg.add_trace(go.Scatter(
                                x=[team_display_rs],
                                y=[team_avg_rh],
                                mode='markers',
                                name='チーム平均',
                                marker=dict(size=18, color='black', symbol='star', line=dict(width=1, color='white')),
                                hoverinfo='text',
                                hovertext=f"チーム平均<br>高さ: {team_avg_rh:.2f}m<br>左右: {team_display_rs:.2f}m"
                            ))
                        
                        fig_rel_avg.update_traces(marker=dict(size=15))
                        fig_rel_avg.add_hline(y=0, line_width=2, line_color="black")
                        fig_rel_avg.add_vline(x=0, line_dash="dash", line_color="gray")
                        fig_rel_avg.update_layout(**common_release_layout)
                        st.plotly_chart(fig_rel_avg, use_container_width=True, key="chart_rel_avg")

                    with rel_col3:
                        st.write("▼ 球種別リリース範囲")
                        fig_rel_range = go.Figure()
                        
                        add_pitcher_url_background(fig_rel_range, is_right_hand)
                        valid_rel_df = df_pos_source.dropna(subset=[c_rh, c_rs, 'Pitch Type'])
                        shapes_list = []
                        
                        grouped_pt = {pt: grp for pt, grp in valid_rel_df.groupby('Pitch Type')}
                        ordered_pts = sort_pitch_types(list(grouped_pt.keys()))
                        
                        for pt in ordered_pts:
                            group = grouped_pt[pt]
                            if len(group) >= 1:
                                mean_x = float(group[c_rs].mean())
                                mean_y = float(group[c_rh].mean())
                                
                                max_w_cm = (group[c_rs].max() - group[c_rs].min()) * 100
                                max_h_cm = (group[c_rh].max() - group[c_rh].min()) * 100
                                
                                std_x = group[c_rs].std() if len(group) > 1 else 0.03
                                std_y = group[c_rh].std() if len(group) > 1 else 0.03
                                
                                rx = float(max(std_x * 1.8, 0.035) if not np.isnan(std_x) else 0.035)
                                ry = float(max(std_y * 1.8, 0.035) if not np.isnan(std_y) else 0.035)
                                
                                color = get_pitch_color(pt)
                                
                                shapes_list.append(dict(
                                    type="circle",
                                    xref="x", yref="y",
                                    x0=mean_x - rx, y0=mean_y - ry,
                                    x1=mean_x + rx, y1=mean_y + ry,
                                    fillcolor=color,
                                    opacity=0.35,
                                    line=dict(color=color, width=2)
                                ))
                                
                                legend_label = f"<b>{pt}</b><br>左右幅: {max_w_cm:.1f}cm<br>高さ幅: {max_h_cm:.1f}cm"
                                
                                fig_rel_range.add_trace(go.Scatter(
                                    x=[None], y=[None],
                                    mode='markers',
                                    name=legend_label,
                                    marker=dict(size=12, color=color)
                                ))
                        
                        fig_rel_range.add_hline(y=0, line_width=2, line_color="black")
                        fig_rel_range.add_vline(x=0, line_dash="dash", line_color="gray")
                        
                        layout_args_range = common_release_layout.copy()
                        layout_args_range['shapes'] = shapes_list
                        fig_rel_range.update_layout(**layout_args_range)
                        st.plotly_chart(fig_rel_range, use_container_width=True, key="chart_rel_range")

                    # --- 📍 月毎の平均リリース位置グラフ ---
                    st.write("▼ 月毎の平均リリース位置（投手目線 / 全球まとめた月毎の平均）")
                    df_rel_month = df_pos_source.dropna(subset=[c_rh, c_rs, 'Date']).copy()
                    df_rel_month['Month'] = pd.to_datetime(df_rel_month['Date']).dt.to_period('M').astype(str)
                    
                    rel_month_avg = df_rel_month.groupby('Month').agg({c_rs: 'mean', c_rh: 'mean'}).reset_index()
                    
                    fig_rel_month = px.scatter(
                        rel_month_avg,
                        x=c_rs,
                        y=c_rh,
                        color='Month',
                        text='Month',
                        labels={c_rs: '左右 [m]', c_rh: '高さ [m]', 'Month': '月'},
                        hover_data=['Month']
                    )
                    add_pitcher_url_background(fig_rel_month, is_right_hand)
                    
                    if team_display_rs is not None and team_avg_rh is not None:
                        fig_rel_month.add_trace(go.Scatter(
                            x=[team_display_rs],
                            y=[team_avg_rh],
                            mode='markers',
                            name='チーム平均',
                            marker=dict(size=18, color='black', symbol='star', line=dict(width=1, color='white')),
                            hoverinfo='text',
                            hovertext=f"チーム平均<br>高さ: {team_avg_rh:.2f}m<br>左右: {team_display_rs:.2f}m"
                        ))
                    
                    fig_rel_month.update_traces(textposition='top center', marker=dict(size=16))
                    fig_rel_month.add_hline(y=0, line_width=2, line_color="black")
                    fig_rel_month.add_vline(x=0, line_dash="dash", line_color="gray")
                    fig_rel_month.update_layout(**common_release_layout)
                    st.plotly_chart(fig_rel_month, use_container_width=True, key="chart_rel_month_avg")

                else:
                    st.info("ℹ️ リリース位置データが含まれていないか、有効な数値データが存在しません。")

                # --- 📐 縦リリース角度（VertRelAngle）分析セクション（トラックマン基準） ---
                st.divider()
                st.subheader("📐 縦リリース角度分析 (Vertical Release Angle / トラックマン基準)")
                
                df_vra_source = df_base[df_base['Data Source'].astype(str).str.contains("Trackman")].copy()
                
                if c_vra in df_vra_source.columns and not df_vra_source[c_vra].dropna().empty:
                    ang_col1, ang_col2 = st.columns(2)
                    
                    hover_items_ang = ['ID', 'Date', 'Data Type', c_vel, c_vra]
                    if 'Data Source' in df_vra_source.columns: hover_items_ang.append('Data Source')
                    
                    with ang_col1:
                        st.write("▼ 投球別 縦リリース角度 [°]")
                        fig_vra_all = px.scatter(
                            df_vra_source.dropna(subset=[c_vra]),
                            x=df_vra_source.dropna(subset=[c_vra]).index,
                            y=c_vra,
                            color='Pitch Type',
                            symbol='Symbol',
                            symbol_map={s: s for s in df_vra_source['Symbol'].unique()},
                            labels={'x': '投球順 (ID)', c_vra: '縦リリース角度 [°]'},
                            color_discrete_map=COLOR_MAP_PITCH,
                            category_orders=category_orders_dict,
                            hover_data=hover_items_ang
                        )
                        fig_vra_all.add_hline(y=0, line_dash="dash", line_color="gray")
                        fig_vra_all.update_layout(
                            plot_bgcolor='white', 
                            height=400, 
                            xaxis=dict(title='投球順 (ID)', gridcolor='lightgray'), 
                            yaxis=dict(title='縦リリース角度 [°]', gridcolor='lightgray')
                        )
                        st.plotly_chart(fig_vra_all, use_container_width=True, key="chart_vert_rel_angle_all")
                            
                    with ang_col2:
                        st.write("▼ 球種別平均 縦リリース角度 [°]")
                        vra_avg_df = df_vra_source.dropna(subset=[c_vra]).groupby('Pitch Type').agg({c_vra: 'mean'}).reset_index()
                        
                        fig_vra_avg = px.bar(
                            vra_avg_df,
                            x='Pitch Type',
                            y=c_vra,
                            color='Pitch Type',
                            text_auto='.2f',
                            labels={'Pitch Type': '球種', c_vra: '平均 縦リリース角度 [°]'},
                            color_discrete_map=COLOR_MAP_PITCH,
                            category_orders=category_orders_dict
                        )
                        fig_vra_avg.add_hline(y=0, line_dash="dash", line_color="gray")
                        fig_vra_avg.update_layout(
                            plot_bgcolor='white', 
                            height=400, 
                            xaxis=dict(title='球種', gridcolor='lightgray'), 
                            yaxis=dict(title='平均 縦リリース角度 [°]', gridcolor='lightgray'),
                            showlegend=False
                        )
                        st.plotly_chart(fig_vra_avg, use_container_width=True, key="chart_vert_rel_angle_avg")
                else:
                    st.info("ℹ️ トラックマンの縦リリース角度（VertRelAngle）データが含まれていません。")

                # --- 📏 エクステンション分析セクション ---
                st.divider()
                st.subheader("📏 エクステンション分析（プレートからの距離 ＆ リリース高さ）")
                
                if c_ext in df_pos_source.columns and c_rh in df_pos_source.columns and not df_pos_source[[c_ext, c_rh]].dropna().empty:
                    ext_x_range = [0.0, 2.5]
                    ext_y_range = [0.0, 2.2]
                    
                    ext_col1, ext_col2 = st.columns(2)
                    
                    hover_items_ext = ['ID', 'Date', 'Data Type', c_vel, c_ext, c_rh]
                    if 'Data Source' in df_pos_source.columns:
                        hover_items_ext.append('Data Source')
                        
                    with ext_col1:
                        st.write("▼ プレート起点のエクステンション × リリース高さ（全投球）")
                        fig_ext_scatter = px.scatter(
                            df_pos_source.dropna(subset=[c_ext, c_rh]),
                            x=c_ext,
                            y=c_rh,
                            color='Pitch Type',
                            symbol='Symbol',
                            symbol_map=symbol_map_dict,
                            range_x=ext_x_range,
                            range_y=ext_y_range,
                            labels={c_ext: 'エクステンション [m]', c_rh: '高さ [m]'},
                            color_discrete_map=COLOR_MAP_PITCH,
                            category_orders=category_orders_dict,
                            hover_data=hover_items_ext
                        )
                        add_extension_url_background(fig_ext_scatter)
                        
                        fig_ext_scatter.add_vline(x=0, line_width=2, line_color="black")
                        fig_ext_scatter.add_hline(y=0, line_width=2, line_color="black")
                        fig_ext_scatter.update_layout(
                            plot_bgcolor='white',
                            height=400,
                            xaxis=dict(gridcolor='lightgray', dtick=0.5, title='エクステンション [m]'),
                            yaxis=dict(gridcolor='lightgray', dtick=0.5, range=ext_y_range, title='高さ [m]')
                        )
                        st.plotly_chart(fig_ext_scatter, use_container_width=True, key="chart_ext_scatter")
                        
                    with ext_col2:
                        st.write("▼ 球種別平均（エクステンション × リリース高さ）")
                        ext_avg_stats = df_pos_source.dropna(subset=[c_ext, c_rh]).groupby('Pitch Type').agg({
                            c_ext: 'mean',
                            c_rh: 'mean'
                        }).reset_index()
                        ext_avg_stats = add_symbol_column(ext_avg_stats, is_right_hand)
                        ext_avg_symbol_map = {s: s for s in ext_avg_stats['Symbol'].unique()}
                        
                        fig_ext_avg = px.scatter(
                            ext_avg_stats,
                            x=c_ext,
                            y=c_rh,
                            color='Pitch Type',
                            symbol='Symbol',
                            symbol_map=ext_avg_symbol_map,
                            range_x=ext_x_range,
                            range_y=ext_y_range,
                            labels={c_ext: 'エクステンション [m]', c_rh: '高さ [m]'},
                            color_discrete_map=COLOR_MAP_PITCH,
                            category_orders=category_orders_dict
                        )
                        add_extension_url_background(fig_ext_avg)
                        
                        fig_ext_avg.update_traces(marker=dict(size=16))
                        fig_ext_avg.add_vline(x=0, line_width=2, line_color="black")
                        fig_ext_avg.add_hline(y=0, line_width=2, line_color="black")
                        fig_ext_avg.update_layout(
                            plot_bgcolor='white',
                            height=400,
                            xaxis=dict(gridcolor='lightgray', dtick=0.5, title='エクステンション [m]'),
                            yaxis=dict(gridcolor='lightgray', dtick=0.5, range=ext_y_range, title='高さ [m]')
                        )
                        st.plotly_chart(fig_ext_avg, use_container_width=True, key="chart_ext_avg")

                    # --- 📏 月毎のエクステンション分析グラフ（2種類） ---
                    st.divider()
                    st.write("▼ 月毎のエクステンション推移グラフ（個別プロット ＆ 平均折れ線）")
                    
                    df_ext_trend = df_pos_source.dropna(subset=[c_ext, 'Date']).copy()
                    df_ext_trend['Month'] = pd.to_datetime(df_ext_trend['Date']).dt.to_period('M').astype(str)
                    df_ext_trend = df_ext_trend.sort_values('Date').reset_index(drop=True)
                    df_ext_trend['Pitch_Index'] = df_ext_trend.index + 1
                    
                    ext_sub_col1, ext_sub_col2 = st.columns(2)
                    
                    with ext_sub_col1:
                        st.write("▼ 個別投球プロット（全投球の推移）")
                        fig_ext_all_plot = px.scatter(
                            df_ext_trend,
                            x='Pitch_Index',
                            y=c_ext,
                            color='Month',
                            labels={'Pitch_Index': '投球数 (球目)', c_ext: 'エクステンション [m]', 'Month': '月'},
                            hover_data=['Date', c_vel, 'Pitch Type']
                        )
                        fig_ext_all_plot.add_trace(go.Scatter(
                            x=df_ext_trend['Pitch_Index'],
                            y=df_ext_trend[c_ext],
                            mode='lines',
                            line=dict(color='gray', width=1, dash='dot'),
                            showlegend=False
                        ))
                        fig_ext_all_plot.update_layout(
                            plot_bgcolor='white',
                            height=400,
                            yaxis=dict(gridcolor='lightgray', title='エクステンション [m]'),
                            xaxis=dict(gridcolor='lightgray', title='投球数 (球目)')
                        )
                        st.plotly_chart(fig_ext_all_plot, use_container_width=True, key="chart_ext_all_plot")

                    with ext_sub_col2:
                        st.write("▼ 月毎の平均推移（平均プロットを線で繋いだグラフ）")
                        ext_month_avg = df_ext_trend.groupby('Month').agg({c_ext: 'mean'}).reset_index()
                        
                        fig_ext_line = px.line(
                            ext_month_avg,
                            x='Month',
                            y=c_ext,
                            markers=True,
                            labels={'Month': '月', c_ext: '平均エクステンション [m]'},
                        )
                        fig_ext_line.update_traces(line=dict(width=3, color='#E60000'), marker=dict(size=10))
                        fig_ext_line.update_layout(
                            plot_bgcolor='white',
                            height=400,
                            yaxis=dict(gridcolor='lightgray', title='平均エクステンション [m]'),
                            xaxis=dict(gridcolor='lightgray', title='月')
                        )
                        st.plotly_chart(fig_ext_line, use_container_width=True, key="chart_ext_line_avg")

                else:
                    st.info("ℹ️ エクステンションデータが存在しません。")

                # --- ⚾️ 3Dスピンビジュアライザー（Rapsodo回転データ参照） ---
                st.divider()
                st.subheader("⚾️ 3D軌道（Rapsodo回転データ参照）")
                valid_df = df_rot_source.dropna(subset=['Pitch Type', c_dir, c_rev])
                
                if not valid_df.empty:
                    available_types = sort_pitch_types(valid_df['Pitch Type'].dropna().unique().tolist())
                    sel_type = st.selectbox("球種を選択して回転を確認:", available_types, key="pitch_viz_select")
                    
                    subset = valid_df[valid_df['Pitch Type'] == sel_type]
                    avg_rpm = subset[c_rev].mean()
                    avg_eff = subset[c_eff].mean() if c_eff in subset.columns else 100.0
                    avg_tilt_str = str(subset[c_dir].iloc[0])
                    tilt_deg = time_to_degrees(avg_tilt_str)
                    
                    st.write(f"**{sel_type}** の平均データ： 回転数 {avg_rpm:.0f} RPM / 効率 {avg_eff:.1f}% / Tilt {avg_tilt_str}")
                    
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
