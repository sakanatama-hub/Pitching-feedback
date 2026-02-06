import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

st.set_page_config(layout="wide")
st.title("⚾ 投手分析：リアル・スピン・ビジュアライザー")

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

    def create_dynamic_baseball(spin_dir_str):
        # 1. 回転軸と傾きの計算
        # Rapsodoの時計盤：12:00は0度, 3:00は90度
        hour, minute = map(int, spin_dir_str.split(':'))
        tilt_deg = (hour % 12 + minute / 60) * 30
        tilt_rad = np.deg2rad(tilt_deg)
        
        # 回転軸（軸そのものが時計の針のように傾く）
        # 12:00の時、軸は水平(X軸)
        axis = np.array([np.cos(tilt_rad), 0, -np.sin(tilt_rad)])

        # 2. 野球ボール曲線の生成 (U字構造)
        t = np.linspace(0, 2 * np.pi, 200)
        alpha = 0.4 
        
        # 12:00の時に「U字の膨らみが左」に見えるように初期位相を調整
        # 媒介変数の位相を +np.pi/2 ずらす
        t_adj = t + np.pi/2
        
        sx_raw = np.cos(t_adj) + alpha * np.cos(3*t_adj)
        sy_raw = np.sin(t_adj) - alpha * np.sin(3*t_adj)
        sz_raw = 2 * np.sqrt(alpha * (1 - alpha)) * np.sin(2*t_adj)
        
        # 正規化
        norm = np.sqrt(sx_raw**2 + sy_raw**2 + sz_raw**2)
        sx, sy, sz = sx_raw/norm, sy_raw/norm, sz_raw/norm

        # 3. ステッチの生成 (太さを出すためにオフセット)
        t_stitch = np.linspace(0, 2 * np.pi, 108) + np.pi/2
        ssx_r = (np.cos(t_stitch) + alpha * np.cos(3*t_stitch))
        ssy_r = (np.sin(t_stitch) - alpha * np.sin(3*t_stitch))
        ssz_r = 2 * np.sqrt(alpha * (1 - alpha)) * np.sin(2*t_stitch)
        snorm = np.sqrt(ssx_r**2 + ssy_r**2 + ssz_r**2)
        ssx, ssy, ssz = ssx_r/snorm, ssy_r/snorm, ssz_r/snorm

        stitches_x, stitches_y, stitches_z = [], [], []
        off = 0.045 # ステッチの幅をわずかに広げる
        
        for i in range(108):
            p = np.array([ssx[i], ssy[i], ssz[i]])
            n = p / np.linalg.norm(p)
            tang = np.array([-ssy[i], ssx[i], 0])
            if np.linalg.norm(tang) < 0.1: tang = np.array([0, 1, 0])
            side = np.cross(n, tang)
            side /= np.linalg.norm(side)
            
            p_l, p_r = p * 1.01 + side * off, p * 1.01 - side * off
            stitches_x.extend([p_l[0], p_r[0], None])
            stitches_y.extend([p_l[1], p_r[1], None])
            stitches_z.extend([p_l[2], p_r[2], None])

        # 球体メッシュ
        u, v = np.mgrid[0:2*np.pi:40j, 0:np.pi:40j]
        bx, by, bz = np.cos(u)*np.sin(v), np.sin(u)*np.sin(v), np.cos(v)

        def rotate(pts, ax, ang):
            ax = ax / np.linalg.norm(ax)
            c, s = np.cos(ang), np.sin(ang)
            K = np.array([[0, -ax[2], ax[1]], [ax[2], 0, -ax[0]], [-ax[1], ax[0], 0]])
            R = np.eye(3) + s * K + (1 - c) * np.dot(K, K)
            return R @ pts

        # 4. アニメーション
        frames = []
        for i in range(30):
            angle = (i / 30) * (2 * np.pi)
            r_ball = rotate(np.vstack([bx.flatten(), by.flatten(), bz.flatten()]), axis, angle)
            
            s_pts = np.vstack([stitches_x, stitches_y, stitches_z])
            mask = ~np.isnan(np.array(stitches_x, dtype=float))
            r_valid = rotate(s_pts[:, mask], axis, angle)
            
            rx, ry, rz = [], [], []
            ptr = 0
            for val in stitches_x:
                if val is None:
                    rx.append(None); ry.append(None); rz.append(None)
                else:
                    rx.append(r_valid[0, ptr]); ry.append(r_valid[1, ptr]); rz.append(r_valid[2, ptr])
                    ptr += 1

            frames.append(go.Frame(data=[
                go.Surface(x=r_ball[0].reshape(bx.shape), y=r_ball[1].reshape(by.shape), z=r_ball[2].reshape(bz.shape),
                           colorscale=[[0, '#FDFDFD'], [1, '#EAEAEA']], showscale=False),
                # 縫い目の線を太く (width=10)
                go.Scatter3d(x=rx, y=ry, z=rz, mode='lines', line=dict(color='#BC1010', width=10))
            ], name=f'f{i}'))

        fig = go.Figure(
            data=frames[0].data,
            layout=go.Layout(
                scene=dict(xaxis_visible=False, yaxis_visible=False, zaxis_visible=False, aspectmode='cube',
                           camera=dict(eye=dict(x=0, y=-1.8, z=0))), # 真後ろ（投手視点）から固定
                updatemenus=[{
                    "type": "buttons", "showactive": False,
                    "buttons": [{"label": "Play", "method": "animate", 
                                 "args": [None, {"frame": {"duration": 30, "redraw": True}, "fromcurrent": True, "loop": True}]}]
                }],
                title=f"球種: {p_type} | Spin Direction: {spin_str}",
                margin=dict(l=0, r=0, b=0, t=50)
            ),
            frames=frames
        )
        return fig

    st.plotly_chart(create_dynamic_baseball(spin_str), use_container_width=True)

    # 自動再生JS
    st.components.v1.html(
        """<script>
        var itv = setInterval(function() {
            var btns = window.parent.document.querySelectorAll('button');
            btns.forEach(function(b) { if (b.innerText === 'Play') { b.click(); clearInterval(itv); } });
        }, 100);
        </script>""", height=0
    )

    # 統計
    st.subheader("📊 統計データ")
    st.dataframe(df.groupby('Pitch Type')[['Velocity', 'Total Spin']].agg(['mean', 'max']).dropna().round(1))

else:
    st.info("CSVファイルをアップロードしてください。")
