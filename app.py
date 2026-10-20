import os
import streamlit as st
import google.generativeai as genai
from PIL import Image
from dotenv import load_dotenv

# 1. Khởi tạo môi trường & Cấu hình API Key
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

st.set_page_config(
    page_title="Shopee Lens AI Copilot",
    page_icon="🛍️",
    layout="wide"
)

# Giao diện phong cách Shopee (Màu cam chủ đạo)
st.markdown("""
    <style>
    .main-title { font-size: 32px; font-weight: bold; color: #EE4D2D; margin-bottom: 5px; }
    .sub-title { font-size: 16px; color: #555; margin-bottom: 25px; }
    .stButton>button { background-color: #EE4D2D; color: white; border-radius: 8px; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">🛍️ Shopee Lens AI: Trợ lý Mua sắm Đa phương thức</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Tải ảnh hoặc dán link sản phẩm để AI tự động quét thị trường, so sánh giá, review và xếp hạng nơi mua tối ưu nhất.</div>', unsafe_allow_html=True)

# 2. Cột bên trái: Thiết lập & Tiêu chí xếp hạng
with st.sidebar:
    st.header("⚙️ Tiêu chí ưu tiên")
    
    # Kiểm tra API Key (Nếu trong .env chưa có thì cho nhập tay)
    if not api_key:
        api_key = st.text_input("Nhập Google Gemini API Key:", type="password")
        if not api_key:
            st.warning("Vui lòng nhập API Key để bắt đầu sử dụng.")
            st.stop()
            
    sort_criteria = st.radio(
        "Bạn muốn ưu tiên xếp hạng theo:",
        [
            "🌟 Đánh giá cao & Uy tín nhất (Rating & Legitimacy)",
            "💰 Giá rẻ & Hời nhất (Lowest Price)",
            "🔥 Lượt mua nhiều & Bán chạy nhất (Best Selling)"
        ]
    )
    
    st.divider()
    st.markdown("""
    **Về dự án:**  
    Mô hình Proof of Concept (PoC) xây dựng cho **Sea GMAP 2027 (Shopee & Monee)**.  
    *Tech stack: Python, Streamlit, Gemini 1.5 Flash Vision & Search.*
    """)

# 3. Giao diện nhập liệu: Ảnh hoặc Link/Tên sản phẩm
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("1. Tải ảnh sản phẩm (Image)")
    uploaded_image = st.file_uploader("Kéo thả ảnh cần tìm vào đây (JPG, PNG)...", type=["jpg", "jpeg", "png"])
    if uploaded_image:
        image = Image.open(uploaded_image)
        st.image(image, caption="Ảnh sản phẩm bạn đã chọn", use_container_width=True)

with col2:
    st.subheader("2. Dán link hoặc Tên sản phẩm (Optional)")
    product_input = st.text_area(
        "Dán link Shopee hoặc gõ mô tả sản phẩm:",
        placeholder="Ví dụ: Link shopee.vn/... hoặc 'Tai nghe Baseus Bowie M2+ chống ồn màu đen'",
        height=140
    )

st.divider()

# 4. Xử lý logic AI khi bấm nút
if st.button("🚀 Quét thị trường & Xếp hạng nơi mua", use_container_width=True):
    if not uploaded_image and not product_input.strip():
        st.error("👉 Vui lòng cung cấp ít nhất một ảnh hoặc dán link/tên sản phẩm để AI phân tích!")
    else:
        with st.spinner("🤖 AI đang nhận diện sản phẩm, quét các sàn và phân tích hàng trăm bình luận thực tế..."):
            try:
                genai.configure(api_key=api_key)
                
                # Cấu hình model Gemini 1.5 Flash hỗ trợ Multimodal và Web Search
                model = genai.GenerativeModel(
                    model_name="gemini-1.5-flash",
                    tools="google_search_retrieval"
                )
                
                # Xây dựng System Prompt chi tiết chuẩn phong cách E-commerce Specialist
                prompt = f"""
                Bạn là một Trợ lý Mua sắm Cá nhân Thông minh (AI Shopping Copilot) cấp cao của Shopee.
                Hãy phân tích thông tin đầu vào (hình ảnh và/hoặc link/tên sản phẩm) và thực hiện các bước sau:
                
                MỤC TIÊU NGƯỜI DÙNG:
                - Tiêu chí ưu tiên xếp hạng hiện tại: "{sort_criteria}"
                
                NHIỆM VỤ CỦA BẠN:
                1. NHẬN DIỆN SẢN PHẨM: Xác định chính xác tên sản phẩm, thương hiệu, model và ngành hàng.
                2. QUÉT THỊ TRƯỜNG & NƠI BÁN (Shopee, các sàn TMĐT):
                   - Tìm và liệt kê từ 2 đến 3 nơi bán/shop tiêu biểu (ví dụ: Shop Mall chính hãng, Shop bán rẻ nhất, Shop có lượt bán cao nhất).
                   - Cung cấp: Tên shop/loại shop, Mức giá ước tính, Lượt bán tham khảo, Số sao đánh giá.
                   - Sắp xếp thứ tự danh sách này dựa đúng theo tiêu chí ưu tiên: "{sort_criteria}".
                3. TỔNG HỢP REVIEW THỰC TẾ:
                   - Bóc tách từ đánh giá của người mua: Điểm KHEN nhiều nhất (Chất liệu, tốc độ giao hàng, đóng gói...)
                   - Điểm CHÊ / Cảnh báo rủi ro (Hàng dễ vỡ, form áo chật, shop giao chậm, lỗi vặt...).
                4. QUYẾT ĐỊNH MUA HÀNG (SMART VERDICT):
                   - Đưa ra lời khuyên dứt khoát: Khách hàng nên bấm MUA Ở ĐÂU để tối ưu nhất theo tiêu chí đã chọn?
                
                YÊU CẦU ĐỊNH DẠNG TRẢ VỀ:
                - Trình bày dạng Markdown chuyên nghiệp, có Bảng so sánh (Comparison Table), gạch đầu dòng rõ ràng, icon sinh động.
                - Khách quan, trung thực, chỉ rõ rủi ro nếu có shop bán hàng quá rẻ khả nghi.
                """
                
                # Gửi dữ liệu đa phương thức (ảnh + text) cho Gemini
                content_inputs = []
                if uploaded_image:
                    content_inputs.append(image)
                if product_input.strip():
                    content_inputs.append(f"Thông tin mô tả/link sản phẩm bổ sung: {product_input}")
                content_inputs.append(prompt)
                
                response = model.generate_content(content_inputs)
                
                # Hiển thị kết quả ra màn hình
                st.success("✅ Phân tích hoàn tất! Dưới đây là bảng xếp hạng và đánh giá chi tiết:")
                st.markdown(response.text)
                
            except Exception as e:
                st.error(f"Đã xảy ra lỗi trong quá trình gọi AI: {str(e)}")
                st.info("Gợi ý: Kiểm tra lại API key hoặc kết nối mạng của bạn.")
