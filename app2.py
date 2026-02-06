import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

st.set_page_config(layout="wide")
st.title("⚾ 投手分析：構造再現スピンビジュアライザー")

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

    def create_structural_baseball(spin_dir_str):
        # 1. Rapsodo回転軸の計算
        hour, minute = map(int, spin_dir_str.split(':'))
        tilt_rad = np.deg2rad((hour % 12 + minute / 60) * 30)
        axis = np.array([np.cos(tilt_rad), 0, -np.sin(tilt_rad)])

        # 2. 幾何学的に正しい「野球ボール曲線」の生成
        # 表裏のU字と側面の平行線（Hの形）を再現する数式
        t = np.linspace(0, 2 * np.pi, 200)
        # alphaがパネルの「食い込み」を決定
        alpha = 0.4 
        
        # 本物の野球ボールの縫い目の軌跡（球面上の構造線）
        sx = np.cos(t) + alpha * np.cos(3*t)
        sy = np.sin(t) - alpha * np.sin(3*t)
        sz = 2 * np.sqrt(alpha * (1 - alpha)) * np.sin(2*t)
        
        # 半径を1に正規化
        norm = np.sqrt(sx**2 + sy**2 + sz**2)
        sx, sy, sz = sx/norm, sy/norm, sz/norm
        
        # 3. 108本のステッチを構造線に沿って配置
        # 縫い目は中央の溝を挟んで左右に並行して走る
        t_stitch = np.linspace(0, 2 * np.pi, 108)
        # 再計算して正規化
        ssx = (np.cos(t_stitch) + alpha * np.cos(3*t_stitch))
        ssy = (np.sin(t_stitch) - alpha * np.sin(3*t_stitch))
        ssz = 2 * np.sqrt(alpha * (1 - alpha)) * np.sin(2*t_stitch)
        snorm = np.sqrt(ssx**2 + ssy**2 + ssz**2)
        ssx, ssy, ssz = ssx/snorm, ssy/snorm, ssz/snorm

        # 溝を表現するための左右のオフセット
        off = 0.04
        stitches_x, stitches_y, stitches_z = [], [], []
        
        for i in range(108):
            p = np.array([ssx[i], ssy[i], ssz[i]])
            # 法線方向
            n = p / np.linalg.norm(p)
            # 接線方向
            tang = np.array([-ssy[i], ssx[i], 0])
            if np.linalg.norm(tang) < 0.1: tang = np.array([0, 1, 0])
            side = np.cross(n, tang)
            side /= np.linalg.norm(side)
            
            # ステッチの左右の点を「U字」の溝として結ぶ
            p_left = p * 1.01 + side * off
            p_right = p * 1.01 - side * off
            
            stitches_x.extend([p_left[0], p_right[0], None])
            stitches_y.extend([p_left[1], p_right[1], None])
            stitches_z.extend([p_left[2], p_right[2], None])

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
            
            # ステッチの回転処理（Noneを避けるため個別に計算）
            s_pts = np.vstack([stitches_x, stitches_y, stitches_z])
            # None以外のインデックスを取得
            mask = ~np.isnan(np.array(stitches_x, dtype=float))
            valid_pts = s_pts[:, mask]
            r_valid = rotate(valid_pts, axis, angle)
            
            # 元の構造（None入り）に戻す
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
                go.Scatter3d(x=rx, y=ry, z=rz, mode='lines', line=dict(color='#BC1010', width=6))
            ], name=f'f{i}'))

        fig = go.Figure(
            data=frames[0].data,
            layout=go.Layout(
                scene=dict(xaxis_visible=False, yaxis_visible=False, zaxis_visible=False, aspectmode='cube',
                           camera=dict(eye=dict(x=1.3, y=-1.3, z=0.8))),
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

    st.plotly_chart(create_structural_baseball(spin_str), use_container_width=True)

    # 自動再生
    st.components.v1.html(
        """<script>
        var itv = setInterval(function() {
            var btns = window.parent.document.querySelectorAll('button');
            btns.forEach(function(b) { if (b.innerText === 'Play') { b.click(); clearInterval(itv); } });
        }, 100);
        </script>""", height=0
    )

    # 統計
    st.subheader("📊 解析データ概要")
    st.dataframe(df.groupby('Pitch Type')[['Velocity', 'Total Spin']].agg(['mean', 'max']).dropna().round(1))

else:
    st.info("CSVファイルをアップロードしてください。")
