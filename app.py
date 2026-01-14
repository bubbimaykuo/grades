import streamlit as st
import google.generativeai as genai
import pandas as pd
from PIL import Image
import io
import json

# --- 設定頁面 ---
st.set_page_config(page_title="成績登記表自動計算器", layout="wide")
st.title("🎓 學生成績登記表自動結算系統")
st.markdown("""
**功能說明：**
1. 批次上傳成績單照片。
2. AI 自動辨識座號與分數。
3. **邏輯判斷**：自動過濾塗改無簽名之無效成績。
4. 取最高 12 次平均並四捨五入，輸出 Excel。
""")

# --- 側邊欄：API Key 設定 ---
with st.sidebar:
    st.header("設定")
    api_key = st.text_input("輸入 Google Gemini API Key", type="password")
    st.markdown("[按此獲取免費 Gemini API Key](https://aistudio.google.com/app/apikey)")
    
    threshold_count = st.number_input("採計最高分數量", min_value=1, value=12)

# --- 核心處理函數 ---
def process_image_with_gemini(image, key):
    genai.configure(api_key=key)
    model = genai.GenerativeModel('gemini-1.5-flash') # 使用 Flash 模型速度快且便宜

    # 設計精準的 Prompt 指令
    prompt = """
    你是一個助教。請分析這張成績登記表的圖片。
    
    任務：
    1. 辨識學生的「座號」(Seat Number)。
    2. 辨識該學生的所有「成績」(Scores)。
    
    重要規則 (塗改判斷)：
    - 仔細檢查每一個分數。
    - 如果分數有被劃掉或塗改的痕跡，檢查旁邊是否有「簽名」或「蓋章」。
    - 如果有塗改但 **沒有** 簽名證明，該分數視為「無效」，不要列入。
    - 如果有塗改且 **有** 簽名，以修正後的數字為準。
    
    請直接回傳 JSON 格式，不要有 markdown 標記，格式如下：
    {
        "seat_number": "座號數字",
        "valid_scores": [分數1, 分數2, 分數3...]
    }
    """
    
    try:
        response = model.generate_content([prompt, image])
        # 清理回傳的字串，確保是純 JSON
        json_str = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(json_str)
    except Exception as e:
        return {"error": str(e)}

def calculate_final_score(scores, top_n):
    if not scores:
        return 0
    # 轉為浮點數並排序
    valid_scores = [float(s) for s in scores if str(s).isdigit() or isinstance(s, (int, float))]
    if not valid_scores:
        return 0
        
    # 取最高的 N 個
    valid_scores.sort(reverse=True)
    top_scores = valid_scores[:top_n]
    
    # 計算平均
    avg = sum(top_scores) / len(top_scores)
    
    # 四捨五入 (Python 的 round 對 .5 會取偶數，這裡用標準四捨五入法)
    import decimal
    context = decimal.getcontext()
    context.rounding = decimal.ROUND_HALF_UP
    final_avg = round(decimal.Decimal(avg), 0)
    
    return int(final_avg)

# --- 主介面 ---
uploaded_files = st.file_uploader("請上傳成績單圖片 (支援多檔)", type=['jpg', 'png', 'jpeg'], accept_multiple_files=True)

if uploaded_files and api_key:
    if st.button("開始辨識與計算"):
        results = []
        progress_bar = st.progress(0)
        
        for i, uploaded_file in enumerate(uploaded_files):
            # 顯示進度
            st.info(f"正在處理：{uploaded_file.name} ...")
            
            # 讀取圖片
            image = Image.open(uploaded_file)
            
            # 呼叫 AI 辨識
            data = process_image_with_gemini(image, api_key)
            
            if "error" in data:
                st.error(f"處理 {uploaded_file.name} 時發生錯誤: {data['error']}")
                continue
            
            # 計算邏輯
            seat_num = data.get("seat_number", "未知")
            raw_scores = data.get("valid_scores", [])
            final_score = calculate_final_score(raw_scores, threshold_count)
            
            results.append({
                "原始檔名": uploaded_file.name,
                "座號": seat_num,
                "採計分數平均": final_score,
                "辨識到的有效分數": str(raw_scores) # 方便人工核對
            })
            
            progress_bar.progress((i + 1) / len(uploaded_files))
            
        st.success("處理完成！")
        
        # --- 顯示與下載結果 ---
        if results:
            df = pd.DataFrame(results)
            # 依照座號排序 (嘗試轉數字排序，若失敗則字串排序)
            try:
                df['座號_Int'] = df['座號'].astype(int)
                df = df.sort_values('座號_Int').drop(columns=['座號_Int'])
            except:
                df = df.sort_values('座號')

            st.dataframe(df)
            
            # 轉換為 Excel 下載
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='成績結算')
            
            st.download_button(
                label="📥 下載 Excel 檔案",
                data=output.getvalue(),
                file_name="學生成績結算表.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
else:
    if not api_key:
        st.warning("請先在左側輸入 API Key 才能開始運作。")
