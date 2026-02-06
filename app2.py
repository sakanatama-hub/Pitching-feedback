import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

st.set_page_config(layout="wide")
st.title("⚾ 投手分析：実写クオリティ・スピンビジュアライザー")

uploaded_file = st.file_uploader("CSVファイルをアップロード", type='csv')

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file, skiprows=4)
    # 統計用データの数値変換
    for col in ['Velocity', 'Total Spin', 'VB (trajectory)', 'HB (trajectory)']:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    # 最新の1球のデータ（渕上選手のFastballなど）
    row = df.dropna(subset=['Spin Direction']).iloc[0]
    spin_str = row['Spin Direction']
    p_type = row['Pitch Type']

    def create_photorealistic_ball(spin_dir_str):
        # 1. Rapsodoの回転軸算出 (時計盤 -> 物理軸)
        hour, minute = map(int, spin_dir_str.split(':'))
        tilt_rad = np.deg2rad((hour % 12 + minute / 60) * 30)
        # 進行方向(y)に直交する回転軸
        axis = np.array([np.cos(tilt_rad), 0, -np.sin(tilt_rad)])

        # 2. 球体メッシュの作成
        u = np.linspace(0, 2*np.pi, 100)
        v = np.linspace(0, np.pi, 100)
        x = np.outer(np.cos(u), np.sin(v))
        y = np.outer(np.sin(u), np.sin(v))
        z = np.outer(np.ones(np.size(u)), np.cos(v))

        # 3. 本物の野球ボールのテクスチャ画像をマッピング
        # 高解像度の野球ボール展開図（シームが正確なもの）を指定
        ball_texture_url = "https://raw.githubusercontent.com/mrdoob/three.js/master/examples/textures/baseball.jpg"

        # 4. 回転アニメーションのフレーム
        frames = []
        n_frames = 40
        for i in range(n_frames):
            angle = (i / n_frames) * (2 * np.pi)
            
            # 回転行列 (Rodrigues' rotation formula)
            u_axis = axis / np.linalg.norm(axis)
            c, s = np.cos(angle), np.sin(angle)
            K = np.array([[0, -u_axis[2], u_axis[1]], [u_axis[2], 0, -u_axis[0]], [-u_axis[1], u_axis[0], 0]])
            R = np.eye(3) + s * K + (1 - c) * np.dot(K, K)
            
            # メッシュの回転計算
            pts = np.vstack([x.flatten(), y.flatten(), z.flatten()])
            r_pts = R @ pts
            rx = r_pts[0].reshape(x.shape)
            ry = r_pts[1].reshape(y.shape)
            rz = r_pts[2].reshape(z.shape)

            frames.append(go.Frame(data=[
                go.Surface(
                    x=rx, y=ry, z=rz,
                    surfacecolor=np.ones(rx.shape), # ダミー
                    colorscale=[[0, 'white'], [1, 'white']],
                    showscale=False,
                    # テクスチャ画像の貼り付け設定
                    texturesrc=ball_texture_url 
                )
            ], name=f'f{i}'))

        # 初期描画
        fig = go.Figure(
            data=frames[0].data,
            layout=go.Layout(
                scene=dict(
                    xaxis_visible=False, yaxis_visible=False, zaxis_visible=False,
                    aspectmode='cube',
                    camera=dict(eye=dict(x=1.2, y=-1.5, z=0.5))
                ),
                updatemenus=[{
                    "type": "buttons", "showactive": False,
                    "buttons": [{"label": "Play", "method": "animate", 
                                 "args": [None, {"frame": {"duration": 20, "redraw": True}, "fromcurrent": True, "loop": True}]}]
                }],
                title=f"【{p_type}】 Spin Direction: {spin_str} (Photo Texture Model)",
                margin=dict(l=0, r=0, b=0, t=50)
            ),
            frames=frames
        )
        return fig

    # 表示
    st.plotly_chart(create_photorealistic_ball(spin_str), use_container_width=True)

    # JavaScriptで自動再生
    st.components.v1.html(
        """<script>
        var itv = setInterval(function() {
            var btns = window.parent.document.querySelectorAll('button');
            btns.forEach(function(b) {
                if (b.innerText === 'Play') { b.click(); clearInterval(itv); }
            });
        }, 100);
        </script>""", height=0
    )

    # 変化量チャート
    import plotly.express as px
    st.subheader("📊 球種別変化量（白背景・公式スタイル）")
    fig_mov = px.scatter(df.dropna(subset=['HB (trajectory)', 'VB (trajectory)']), 
                         x='HB (trajectory)', y='VB (trajectory)', color='Pitch Type',
                         template="plotly_white", range_x=[-60, 60], range_y=[-60, 60])
    fig_mov.add_hline(y=0, line_color="black", line_width=1)
    fig_mov.add_vline(x=0, line_color="black", line_width=1)
    st.plotly_chart(fig_mov)

else:
    st.info("CSVファイルをアップロードしてください。")
