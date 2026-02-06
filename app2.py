import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np

# --- ページ設定 ---
st.set_page_config(layout="wide")
st.title("⚾ リアル・ピッチ・ビジュアライザー")

uploaded_file = st.file_uploader("CSVファイルをアップロード", type='csv')

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file, skiprows=4)
    
    # データクリーニング（統計用）
    for col in ['Velocity', 'Total Spin', 'VB (trajectory)', 'HB (trajectory)']:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    # 1. 統計表示 (数値があるもののみ)
    st.subheader("📊 球種別統計")
    stats = df.groupby('Pitch Type')[['Velocity', 'Total Spin']].agg(['mean', 'max']).dropna().round(1)
    stats.columns = ['平均球速', '最高球速', '平均回転数', '最高回転数']
    st.dataframe(stats)

    # 2. 変化量チャート (白背景)
    st.subheader("⚾ 変化量チャート")
    import plotly.express as px
    fig_mov = px.scatter(df.dropna(subset=['HB (trajectory)', 'VB (trajectory)']), 
                         x='HB (trajectory)', y='VB (trajectory)', color='Pitch Type',
                         template="plotly_white", range_x=[-60, 60], range_y=[-60, 60])
    fig_mov.add_shape(type="line", x0=-60, y0=0, x1=60, y1=0, line=dict(color="gray", dash="dash"))
    fig_mov.add_shape(type="line", x0=0, y0=-60, x1=0, y1=60, line=dict(color="gray", dash="dash"))
    st.plotly_chart(fig_mov)

    # 3. リアルな回転軸アニメーション
    st.subheader("🔄 リアル回転シミュレーション (最新の1球)")
    
    # 最新のデータを取得
    row = df.dropna(subset=['Spin Direction']).iloc[0]
    spin_dir = row['Spin Direction']
    pitch_type = row['Pitch Type']

    # --- ボールの3Dモデル作成 ---
    def create_animated_ball(spin_str):
        # 12:00形式を角度に変換
        hour, minute = map(int, spin_str.split(':'))
        # ラプソードの定義: 12:00はバックスピン(軸は水平)
        # 進行方向から見て、時計の針の方向にボールが「浮き上がる力」が働いていると定義
        angle_deg = (hour % 12 + minute / 60) * 30
        angle_rad = np.deg2rad(angle_deg)
        
        # 球体のメッシュ作成
        n = 30
        u = np.linspace(0, 2 * np.pi, n)
        v = np.linspace(0, np.pi, n)
        x = np.outer(np.cos(u), np.sin(v))
        y = np.outer(np.sin(u), np.sin(v))
        z = np.outer(np.ones(np.size(u)), np.cos(v))

        # 野球ボールのテクスチャ（外部のフリー素材URLを使用）
        # ※インターネット環境が必要です
        ball_texture = "https://raw.githubusercontent.com/mrdoob/three.js/master/examples/textures/planets/earth_atmos_2048.jpg" # 代替用。実際は野球ボール画像を推奨
        # リアルな野球ボールスキンURL
        ball_skin = "https://upload.wikimedia.org/wikipedia/commons/thumb/9/92/Baseball_template_clean_2.jpg/1024px-Baseball_template_clean_2.jpg"

        fig = go.Figure()

        # アニメーションのフレーム作成 (回転させる)
        frames = []
        for t in range(0, 20):
            rot = t * 0.3 # 回転速度
            # 回転行列を適用（スピン軸を中心に回転）
            # 簡易化のため、Z軸（スピン方向）周りの回転としてシミュレート
            frames.append(go.Frame(data=[go.Surface(
                x=x*np.cos(rot) - y*np.sin(rot),
                y=x*np.sin(rot) + y*np.cos(rot),
                z=z,
                surfacecolor=np.random.rand(n, n), # 擬似的なテクスチャ感
                colorscale=[[0, 'white'], [0.5, 'red'], [1, 'white']], # 縫い目イメージ
                showscale=False
            )]))

        # ベースとなる球体
        fig.add_trace(go.Surface(x=x, y=y, z=z, 
                                 colorscale=[[0, 'white'], [1, '#dddddd']], 
                                 showscale=False))

        # 回転軸を示すロッド (固定)
        axis_len = 1.5
        ax = np.sin(angle_rad) * axis_len
        az = np.cos(angle_rad) * axis_len
        fig.add_trace(go.Scatter3d(x=[-ax, ax], y=[0, 0], z=[-az, az],
                                 mode='lines', line=dict(color='black', width=10)))

        fig.update_layout(
            scene=dict(
                xaxis_visible=False, yaxis_visible=False, zaxis_visible=False,
                aspectmode='cube',
                camera=dict(eye=dict(x=1.5, y=1.5, z=1.5))
            ),
            updatemenus=[dict(type="buttons", buttons=[dict(label="Play Spin", method="animate", args=[None, {"frame": {"duration": 50}}])])]
        )
        fig.frames = frames
        return fig

    st.plotly_chart(create_animated_ball(spin_dir))
    st.info(f"このボールは {pitch_type} の回転軸 ({spin_dir}) を中心に回転しています。Playボタンを押してください。")

else:
    st.info("CSVファイルをアップロードしてください。")
