import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

st.set_page_config(layout="wide")
st.title("⚾ 投手分析：超リアル・スピン・ビジュアライザー")

uploaded_file = st.file_uploader("CSVをアップロード", type='csv')

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file, skiprows=4)
    for col in ['Velocity', 'Total Spin', 'VB (trajectory)', 'HB (trajectory)']:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    # 最新データの取得
    row = df.dropna(subset=['Spin Direction']).iloc[0]
    spin_str = row['Spin Direction']
    p_type = row['Pitch Type']

    def generate_authentic_baseball(spin_dir_str):
        # 1. Rapsodo回転軸の計算
        hour, minute = map(int, spin_dir_str.split(':'))
        tilt_rad = np.deg2rad((hour % 12 + minute / 60) * 30)
        axis = np.array([np.cos(tilt_rad), 0, -np.sin(tilt_rad)])

        # 2. 野球ボールの皮と縫い目の構造的な再現
        # 108本のステッチ位置を正確に計算する
        t = np.linspace(0, 2 * np.pi, 109)[:-1]
        
        # 実際のボールの縫い目形状（Saddle Curveの最適化パラメータ）
        # 本物のボールはもっと深く、急激に湾曲しているため数値を調整
        a = 0.62  # 湾曲の深さ
        b = 0.45  # 幅の絞り込み
        
        # 基本となるシームの軌跡
        x = np.cos(t) * np.sqrt(1 - a**2 * np.cos(2*t)**2)
        y = np.sin(t) * np.sqrt(1 - a**2 * np.cos(2*t)**2)
        z = a * np.cos(2*t)
        
        # 縫い目は「V字」状に並んでいるため、2列のステッチポイントを作成
        # これが「108本の縫い目」のリアルな見た目を作る
        offset = 0.04
        # 1列目のステッチ
        s1 = np.vstack([x*(1+offset), y*(1+offset), z*(1+offset)])
        # 2列目のステッチ
        s2 = np.vstack([x*(1-offset), y*(1-offset), z*(1-offset)])
        
        # ステッチ間の糸を表現するために交互に配置
        stitch_lines = []
        for i in range(len(t)):
            stitch_lines.append(s1[:, i])
            stitch_lines.append(s2[:, i])
        stitch_lines = np.array(stitch_lines).T

        # 3. 球体メッシュ (皮の質感)
        u, v = np.mgrid[0:2*np.pi:50j, 0:np.pi:50j]
        bx, by, bz = np.cos(u)*np.sin(v), np.sin(u)*np.sin(v), np.cos(v)

        def rotate_pts(pts, axis, angle):
            u = axis / np.linalg.norm(axis)
            c, s = np.cos(angle), np.sin(angle)
            K = np.array([[0, -u[2], u[1]], [u[2], 0, -u[0]], [-u[1], u[0], 0]])
            R = np.eye(3) + s * K + (1 - c) * np.dot(K, K)
            return R @ pts

        # 4. アニメーションフレーム
        frames = []
        n_frames = 36
        for i in range(n_frames):
            ang = (i / n_frames) * (2 * np.pi)
            r_ball = rotate_pts(np.vstack([bx.flatten(), by.flatten(), bz.flatten()]), axis, ang)
            r_stitches = rotate_pts(stitch_lines, axis, ang)
            
            frames.append(go.Frame(data=[
                # ボール本体 (オフホワイトの革)
                go.Surface(x=r_ball[0].reshape(bx.shape), y=r_ball[1].reshape(by.shape), z=r_ball[2].reshape(bz.shape),
                           colorscale=[[0, '#FDFDFD'], [1, '#EFEFEA']], showscale=False),
                # 縫い目：108本のステッチをジグザグに結ぶ赤い糸
                go.Scatter3d(x=r_stitches[0], y=r_stitches[1], z=r_stitches[2],
                             mode='lines', line=dict(color='#BC1010', width=10))
            ], name=f'f{i}'))

        fig = go.Figure(
            data=frames[0].data,
            layout=go.Layout(
                scene=dict(
                    xaxis_visible=False, yaxis_visible=False, zaxis_visible=False,
                    aspectmode='cube',
                    camera=dict(eye=dict(x=1.3, y=-1.3, z=0.6))
                ),
                updatemenus=[{
                    "type": "buttons", "showactive": False,
                    "buttons": [{"label": "Play", "method": "animate", 
                                 "args": [None, {"frame": {"duration": 30, "redraw": True}, "fromcurrent": True, "loop": True}]}]
                }],
                title=f"【{p_type}】 Spin Direction: {spin_str}",
                margin=dict(l=0, r=0, b=0, t=50)
            ),
            frames=frames
        )
        return fig

    st.plotly_chart(generate_authentic_baseball(spin_str), use_container_width=True)

    # ページ表示時に自動で「Play」をクリックして回転させる
    st.components.v1.html(
        """<script>
        window.parent.document.querySelectorAll('button').forEach(btn => {
            if (btn.innerText === 'Play') { btn.click(); }
        });
        </script>""", height=0
    )

    # 統計情報の表示
    st.subheader("📊 投球データ詳細")
    stats = df.groupby('Pitch Type')[['Velocity', 'Total Spin']].agg(['mean', 'max']).dropna().round(1)
    st.dataframe(stats)

else:
    st.info("CSVファイルをアップロードしてください。")
