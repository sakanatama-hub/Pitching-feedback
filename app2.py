import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

st.set_page_config(layout="wide")
st.title("⚾ 投手分析フィードバック（Rapsodo形式）")

uploaded_file = st.file_uploader("CSVファイルをアップロード", type='csv')

if uploaded_file is not None:
    # 5行目からデータ開始
    df = pd.read_csv(uploaded_file, skiprows=4)
    
    # 数値化と不要データの削除
    cols_to_fix = ['Velocity', 'Total Spin', 'VB (trajectory)', 'HB (trajectory)']
    for col in cols_to_fix:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    
    # 1. 統計表示 (ハイフンなどの欠損値を含む球種を除外、または数値のみ計算)
    st.subheader("📊 球種別統計")
    stats = df.groupby('Pitch Type')[['Velocity', 'Total Spin']].agg(['mean', 'max'])
    # 全てNaNの行を削除
    stats = stats.dropna(how='all').round(1)
    stats.columns = ['平均球速', '最高球速', '平均回転数', '最高回転数']
    st.dataframe(stats)

    # 2. 変化量チャート (白背景 & 見やすさ重視)
    st.subheader("⚾ 変化量チャート (Movement Profile)")
    fig_mov = px.scatter(df.dropna(subset=['HB (trajectory)', 'VB (trajectory)']), 
                         x='HB (trajectory)', y='VB (trajectory)', 
                         color='Pitch Type',
                         template="plotly_white", # 背景を白に
                         labels={'HB (trajectory)': '横 (cm)', 'VB (trajectory)': '縦 (cm)'})
    
    # 基準線の追加
    fig_mov.add_shape(type="line", x0=-60, y0=0, x1=60, y1=0, line=dict(color="LightGray", width=2))
    fig_mov.add_shape(type="line", x0=0, y0=-60, x1=0, y1=60, line=dict(color="LightGray", width=2))
    
    fig_mov.update_layout(width=700, height=700, xaxis=dict(range=[-60, 60]), yaxis=dict(range=[-60, 60]))
    st.plotly_chart(fig_mov)

    # 3. 野球ボールの回転視覚化 (Rapsodo定義準拠)
    st.subheader("🔄 回転の視覚化 (最新の1球)")
    
    valid_data = df.dropna(subset=['Spin Direction', 'Pitch Type']).iloc[0]
    spin_str = valid_data['Spin Direction']
    pitch_type = valid_data['Pitch Type']

    def create_spinning_ball(spin_str):
        try:
            # Rapsodoの時計盤表記を角度に変換
            hour, minute = map(int, spin_str.split(':'))
            # 0度は12時方向 (真上)
            angle_deg = (hour % 12 + minute / 60) * 30
            angle_rad = np.deg2rad(angle_deg)
            
            # 回転軸ベクトル（投手視点：y軸が奥行き）
            axis_vector = [np.sin(angle_rad), 0, np.cos(angle_rad)]
            
            # ボールの球体作成
            u = np.linspace(0, 2 * np.pi, 30)
            v = np.linspace(0, np.pi, 15)
            x = np.outer(np.cos(u), np.sin(v))
            y = np.outer(np.sin(u), np.sin(v))
            z = np.outer(np.ones(np.size(u)), np.cos(v))

            # 縫い目のような模様（赤いライン）を生成
            theta = np.linspace(0, 2*np.pi, 100)
            seam_x = np.cos(theta) * 1.01
            seam_y = np.sin(theta) * 1.01
            seam_z = 0.5 * np.sin(2*theta)

            fig = go.Figure()

            # 球体の描画
            fig.add_trace(go.Surface(x=x, y=y, z=z, colorscale=[[0, 'white'], [1, '#eeeeee']], showscale=False, opacity=0.8))
            
            # 縫い目の描画
            fig.add_trace(go.Scatter3d(x=seam_x, y=seam_y, z=seam_z, mode='lines', line=dict(color='red', width=5), name="Seam"))

            # 固定された回転軸 (赤い棒)
            fig.add_trace(go.Scatter3d(x=[-axis_vector[0]*1.5, axis_vector[0]*1.5], 
                                     y=[0, 0], 
                                     z=[-axis_vector[2]*1.5, axis_vector[2]*1.5],
                                     mode='lines', line=dict(color='black', width=8), name="Spin Axis"))

            fig.update_layout(
                scene=dict(
                    xaxis_visible=False, yaxis_visible=False, zaxis_visible=False,
                    aspectmode='cube',
                    camera=dict(eye=dict(x=0, y=-2, z=0)) # 投手後ろからの視点
                ),
                title=f"{pitch_type} - 回転方向: {spin_str}",
                margin=dict(l=0, r=0, b=0, t=40)
            )
            return fig
        except:
            return None

    st.plotly_chart(create_spinning_ball(spin_str))
    st.write(f"**解説:** 黒い棒がRapsodoが示す回転軸です。{spin_str}の方向にボールを押し出す力が働いています。")

else:
    st.info("CSVファイルをアップロードしてください。")
