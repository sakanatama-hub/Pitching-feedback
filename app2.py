import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

st.set_page_config(layout="wide")
st.title("⚾ 投手分析：12:48 スライス回転・完全再現")

uploaded_file = st.file_uploader("CSVをアップロード", type='csv')

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file, skiprows=4)
    for col in ['Velocity', 'Total Spin', 'VB (trajectory)', 'HB (trajectory)']:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    valid_data = df.dropna(subset=['Spin Direction', 'Pitch Type'])
    if not valid_data.empty:
        row = valid_data.iloc[0]
        spin_str = row['Spin Direction']
        p_type = row['Pitch Type']
    else:
        st.stop()

    def create_1248_spin_model():
        # 1. 12:48 の方向（右斜め上）を定義
        # 短針の位置：12時から 48/60 * 30度 = 24度。
        # ただし「12:48」は反時計回りに12分戻った位置（または右に大きく回った位置）
        # ここでは投手から見て「12:48」の方向を [sin, 0, cos] で定義
        gyro_angle = np.deg2rad((12 * 60 + 48) / 720 * 360) 
        
        # 指示通り、この方向を向いたまま「右斜め下」へ送り出すための回転軸
        # 12:48方向のベクトルに垂直な軸を回転軸（axis）にする
        target_dir = np.array([np.sin(gyro_angle), 0, np.cos(gyro_angle)])
        # 回転軸は、このターゲット方向に垂直な水平に近い軸
        axis = np.array([np.cos(gyro_angle), 0, -np.sin(gyro_angle)])

        # 2. 野球ボール曲線 (U字構造) の生成
        t = np.linspace(0, 2 * np.pi, 200)
        alpha = 0.4
        sx = np.cos(t) + alpha * np.cos(3*t)
        sy = np.sin(t) - alpha * np.sin(3*t)
        sz = 2 * np.sqrt(alpha * (1 - alpha)) * np.sin(2*t)
        norm = np.sqrt(sx**2 + sy**2 + sz**2)
        s_base = np.vstack([sx/norm, sy/norm, sz/norm])

        # 108本のステッチ
        t_st = np.linspace(0, 2 * np.pi, 108)
        ssx = np.cos(t_st) + alpha * np.cos(3*t_st)
        ssy = np.sin(t_st) - alpha * np.sin(3*t_st)
        ssz = 2 * np.sqrt(alpha * (1 - alpha)) * np.sin(2*t_st)
        sn = np.sqrt(ssx**2 + ssy**2 + ssz**2)
        st_base = np.vstack([ssx/sn, ssy/sn, ssz/sn])

        # 3. 初期姿勢：U字の膨らみが左（⊂）
        # 二等分線が左を向くようにセット
        R_init = np.array([
            [0, 0, 1],
            [1, 0, 0],
            [0, 1, 0]
        ])
        s_oriented = R_init @ s_base
        st_oriented = R_init @ st_base

        # 4. アニメーション計算
        u, v = np.mgrid[0:2*np.pi:40j, 0:np.pi:40j]
        bx, by, bz = np.cos(u)*np.sin(v), np.sin(u)*np.sin(v), np.cos(v)
        ball_mesh = np.vstack([bx.flatten(), by.flatten(), bz.flatten()]).astype(np.float64)

        def rotate_vecs(pts, ax, a):
            ax = ax / (np.linalg.norm(ax) + 1e-9)
            c, s = np.cos(a), np.sin(a)
            K = np.array([[0, -ax[2], ax[1]], [ax[2], 0, -ax[0]], [-ax[1], ax[0], 0]])
            R = np.eye(3) + s * K + (1 - c) * (K @ K)
            return R @ pts

        frames = []
        for i in range(30):
            # 右斜め下に向かって奥へ回転させる
            angle = -(i / 30) * (2 * np.pi) 
            r_ball = rotate_vecs(ball_mesh, axis, angle)
            r_st_center = rotate_vecs(st_oriented, axis, angle)
            
            rx, ry, rz = [], [], []
            off = 0.05
            for j in range(108):
                p = r_st_center[:, j]
                # 縫い目の厚み表現（軸に対して垂直にオフセット）
                side = np.cross(p, axis)
                if np.linalg.norm(side) < 0.01: side = np.array([0, 1, 0])
                side = side / np.linalg.norm(side)
                
                p_l = p * 1.01 + side * off
                p_r = p * 1.01 - side * off
                rx.extend([float(p_l[0]), float(p_r[0]), None])
                ry.extend([float(p_l[1]), float(p_r[1]), None])
                rz.extend([float(p_l[2]), float(p_r[2]), None])

            frames.append(go.Frame(data=[
                go.Surface(x=r_ball[0].reshape(bx.shape), y=r_ball[1].reshape(by.shape), z=r_ball[2].reshape(bz.shape),
                           colorscale=[[0, '#FFFFFF'], [1, '#EAEAEA']], showscale=False),
                go.Scatter3d(x=rx, y=ry, z=rz, mode='lines', line=dict(color='#BC1010', width=12))
            ], name=f'f{i}'))

        fig = go.Figure(
            data=frames[0].data,
            layout=go.Layout(
                scene=dict(xaxis_visible=False, yaxis_visible=False, zaxis_visible=False, aspectmode='cube',
                           camera=dict(eye=dict(x=0, y=-1.8, z=0))),
                updatemenus=[{
                    "type": "buttons", "showactive": False,
                    "buttons": [{"label": "Play", "method": "animate", 
                                 "args": [None, {"frame": {"duration": 30, "redraw": True}, "fromcurrent": True, "loop": True}]}]
                }],
                title="12:48方向へのスライス回転 (U字初期姿勢: 左膨らみ)",
                margin=dict(l=0, r=0, b=0, t=50)
            ),
            frames=frames
        )
        return fig

    st.plotly_chart(create_1248_spin_model(), use_container_width=True)

    st.components.v1.html(
        """<script>
        var itv = setInterval(function() {
            var btns = window.parent.document.querySelectorAll('button');
            btns.forEach(function(b) { if (b.innerText === 'Play') { b.click(); clearInterval(itv); } });
        }, 100);
        </script>""", height=0
    )
else:
    st.info("CSVファイルをアップロードしてください。")
