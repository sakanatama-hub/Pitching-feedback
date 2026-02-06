import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

st.set_page_config(layout="wide")
st.title("⚾ 超精密：リアル・スピン・ビジュアライザー")

uploaded_file = st.file_uploader("CSVをアップロード", type='csv')

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file, skiprows=4)
    for col in ['Velocity', 'Total Spin', 'VB (trajectory)', 'HB (trajectory)']:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    # 最新データの取得
    valid_data = df.dropna(subset=['Spin Direction', 'Pitch Type'])
    if not valid_data.empty:
        row = valid_data.iloc[0]
        spin_str = row['Spin Direction']
        p_type = row['Pitch Type']
    else:
        st.stop()

    def create_authentic_ball_code(spin_dir_str):
        # 1. Rapsodo回転軸の計算
        hour, minute = map(int, spin_dir_str.split(':'))
        tilt_rad = np.deg2rad((hour % 12 + minute / 60) * 30)
        axis = np.array([np.cos(tilt_rad), 0, -np.sin(tilt_rad)])

        # 2. 縫い目の幾何学（馬蹄形）
        t = np.linspace(0, 2 * np.pi, 108) # 108本の縫い目
        a, b = 0.62, 0.42 # 実際のボールに近い曲率
        
        sx = np.cos(t) * np.sqrt(1 - a**2 * np.cos(2*t)**2)
        sy = np.sin(t) * np.sqrt(1 - a**2 * np.cos(2*t)**2)
        sz = a * np.cos(2*t)
        
        # 3. 「V字ステッチ」の生成
        # 単なる線ではなく、外側の革から内側の溝へ向かう108本の独立したV字を描く
        stitch_coords = []
        for i in range(len(t)):
            # 縫い目の中央点（溝の底）
            mid = np.array([sx[i], sy[i], sz[i]])
            # 縫い目の外側（左右の革の端）
            # 法線ベクトルを利用して横に広げる
            normal = mid / np.linalg.norm(mid)
            tangent = np.array([-sy[i], sx[i], 0])
            if np.linalg.norm(tangent) == 0: tangent = np.array([0, 1, 0])
            side = np.cross(normal, tangent)
            side /= np.linalg.norm(side)
            
            p1 = mid * 1.02 + side * 0.05  # 左側の革
            p2 = mid * 0.98               # 溝の底
            p3 = mid * 1.02 - side * 0.05  # 右側の革
            
            # 各ステッチを[x, y, z, None]の形式で結合して一気に描画
            stitch_coords.extend([p1, p2, p3, [None, None, None]])
        
        stitch_pts = np.array(stitch_coords).T

        # 4. 球体（革）
        u, v = np.mgrid[0:2*np.pi:50j, 0:np.pi:50j]
        bx, by, bz = np.cos(u)*np.sin(v), np.sin(u)*np.sin(v), np.cos(v)

        def rotate(pts, ax, ang):
            ax = ax / np.linalg.norm(ax)
            c, s = np.cos(ang), np.sin(ang)
            K = np.array([[0, -ax[2], ax[1]], [ax[2], 0, -ax[0]], [-ax[1], ax[0], 0]])
            R = np.eye(3) + s * K + (1 - c) * np.dot(K, K)
            return R @ pts

        # 5. アニメーション
        frames = []
        for i in range(30):
            angle = (i / 30) * (2 * np.pi)
            r_ball = rotate(np.vstack([bx.flatten(), by.flatten(), bz.flatten()]), axis, angle)
            r_st = rotate(stitch_pts[:3, :], axis, angle)
            
            frames.append(go.Frame(data=[
                # 球体表面
                go.Surface(x=r_ball[0].reshape(bx.shape), y=r_ball[1].reshape(by.shape), z=r_ball[2].reshape(bz.shape),
                           colorscale=[[0, '#FDFDFD'], [1, '#EFEFEA']], showscale=False),
                # 108本のV字ステッチ
                go.Scatter3d(x=r_st[0], y=r_st[1], z=r_st[2], mode='lines',
                             line=dict(color='#BC1010', width=5))
            ], name=f'f{i}'))

        fig = go.Figure(
            data=frames[0].data,
            layout=go.Layout(
                scene=dict(xaxis_visible=False, yaxis_visible=False, zaxis_visible=False, aspectmode='cube',
                           camera=dict(eye=dict(x=1.2, y=-1.5, z=0.6))),
                updatemenus=[{
                    "type": "buttons", "showactive": False,
                    "buttons": [{"label": "Play", "method": "animate", 
                                 "args": [None, {"frame": {"duration": 33, "redraw": True}, "fromcurrent": True, "loop": True}]}]
                }],
                title=f"【{p_type}】 Spin Direction: {spin_str}",
                margin=dict(l=0, r=0, b=0, t=50)
            ),
            frames=frames
        )
        return fig

    st.plotly_chart(create_authentic_ball_code(spin_str), use_container_width=True)

    # 自動再生
    st.components.v1.html(
        """<script>
        var itv = setInterval(function() {
            var btns = window.parent.document.querySelectorAll('button');
            btns.forEach(function(b) { if (b.innerText === 'Play') { b.click(); clearInterval(itv); } });
        }, 100);
        </script>""", height=0
    )

else:
    st.info("CSVをアップロードしてください。")
