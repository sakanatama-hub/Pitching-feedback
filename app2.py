import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

st.set_page_config(layout="wide")
st.title("⚾ 投手分析：12:48 ジャイロ回転・完全再現")

uploaded_file = st.file_uploader("CSVをアップロード", type='csv')

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file, skiprows=4)
    for col in ['Velocity', 'Total Spin', 'VB (trajectory)', 'HB (trajectory)']:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    valid_data = df.dropna(subset=['Spin Direction', 'Pitch Type'])
    if not valid_data.empty:
        row = valid_data.iloc[0]
        # spin_str = row['Spin Direction'] # Rapsodoの値は使いつつ、軸は12:48に固定
        p_type = row['Pitch Type']
    else:
        st.stop()

    def create_gyro_spinning_ball():
        # 1. 12:48 の方向を回転軸として定義
        # 12:48 は 12時から数えて 48/60 * 360度 = 288度 (または反時計回りに傾いた方向)
        gyro_hour = 12
        gyro_min = 48
        # 時計の12:48を数学的な角度(ラジアン)に変換
        # 12:00が真上(Z軸)とした場合
        tilt_deg = (gyro_hour % 12 + gyro_min / 60) * 30
        tilt_rad = np.deg2rad(tilt_deg)
        
        # 軸：指定された「12:48」の方向へドリル回転する軸
        # 投手から見てその方向を向くベクトル
        axis = np.array([np.sin(tilt_rad), 0, np.cos(tilt_rad)])

        # 2. 野球ボール曲線 (U字構造) の生成
        t = np.linspace(0, 2 * np.pi, 200)
        alpha = 0.4
        sx_raw = np.cos(t) + alpha * np.cos(3*t)
        sy_raw = np.sin(t) - alpha * np.sin(3*t)
        sz_raw = 2 * np.sqrt(alpha * (1 - alpha)) * np.sin(2*t)
        norm = np.sqrt(sx_raw**2 + sy_raw**2 + sz_raw**2)
        s_base = np.vstack([sx_raw/norm, sy_raw/norm, sz_raw/norm])

        # 108本のステッチ
        t_st = np.linspace(0, 2 * np.pi, 108)
        ssx = np.cos(t_st) + alpha * np.cos(3*t_st)
        ssy = np.sin(t_st) - alpha * np.sin(3*t_st)
        ssz = 2 * np.sqrt(alpha * (1 - alpha)) * np.sin(2*t_st)
        sn = np.sqrt(ssx**2 + ssy**2 + ssz**2)
        st_base = np.vstack([ssx/sn, ssy/sn, ssz/sn])

        # 3. 初期姿勢：U字の膨らみが左（⊂）の状態でセット
        R_init = np.array([
            [0, 1, 0],
            [0, 0, 1],
            [1, 0, 0]
        ])
        s_oriented = R_init @ s_base
        st_oriented = R_init @ st_base

        # 4. 回転シミュレーション
        u, v = np.mgrid[0:2*np.pi:40j, 0:np.pi:40j]
        bx, by, bz = np.cos(u)*np.sin(v), np.sin(u)*np.sin(v), np.cos(v)
        ball_mesh = np.vstack([bx.flatten(), by.flatten(), bz.flatten()])

        def rotate_vecs(pts, ax, a):
            ax = ax / np.linalg.norm(ax)
            c, s = np.cos(a), np.sin(a)
            K = np.array([[0, -ax[2], ax[1]], [ax[2], 0, -ax[0]], [-ax[1], ax[0], 0]])
            R = np.eye(3) + s * K + (1 - c) * (K @ K)
            return R @ pts

        frames = []
        for i in range(30):
            angle = (i / 30) * (2 * np.pi)
            r_ball = rotate_vecs(ball_mesh, axis, angle)
            r_st_center = rotate_vecs(st_oriented, axis, angle)
            
            rx, ry, rz = [], [], []
            off = 0.05
            for j in range(108):
                p = r_st_center[:, j]
                # 側面方向の広がり（常に軸に対して垂直にオフセット）
                side = np.cross(p, axis)
                if np.linalg.norm(side) < 0.01: side = np.array([0, 1, 0])
                side /= np.linalg.norm(side)
                
                p_l, p_r = p * 1.01 + side * off, p * 1.01 - side * off
                rx.extend([p_l[0], p_r[0], None])
                ry.extend([p_l[1], p_r[1], None])
                rz.extend([p_l[2], p_r[2], None])

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
                title=f"【{p_type}】 12:48 軸回転シミュレーション",
                margin=dict(l=0, r=0, b=0, t=50)
            ),
            frames=frames
        )
        return fig

    st.plotly_chart(create_gyro_spinning_ball(), use_container_width=True)

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
    st.info("CSVファイルをアップロードしてください。")
