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
    
    # Kiểm tra API Key (Nếu trong file .env chưa có thì cho nhập tay)
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
    *Tech stack: Python, Streamlit, Google Gemini Vision & E-commerce Intelligence.*
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
        with st.spinner("🤖 AI đang nhận diện sản phẩm, phân tích thị trường và quét các đánh giá thực tế..."):
            try:
                genai.configure(api_key=api_key)
                
                # Xây dựng System Prompt chi tiết chuẩn phong cách E-commerce Specialist
                prompt = f"""
                Bạn là một Trợ lý Mua sắm Cá nhân Thông minh (AI Shopping Copilot) cấp cao của Shopee.
                Hãy phân tích thông tin đầu vào (hình ảnh và/hoặc link/tên sản phẩm) và thực hiện các bước sau:
                
                MỤC TIÊU NGƯỜI DÙNG:
                - Tiêu chí ưu tiên xếp hạng hiện tại: "{sort_criteria}"
                
                NHIỆM VỤ CỦA BẠN:
                1. NHẬN DIỆN SẢN PHẨM: Xác định chính xác tên sản phẩm, thương hiệu, model và phân khúc ngành hàng.
                2. SO SÁNH CÁC LỰA CHỌN NƠI BÁN (Shopee & Thị trường TMĐT):
                   - Phân tích từ 2 đến 3 phân nhóm nơi bán tiêu biểu: Shop Mall chính hãng, Shop bán giá rẻ nhất, Shop có lượt mua khủng nhất.
                   - Liệt kê: Loại shop, Mức giá ước tính trên Shopee, Đánh giá trung bình sao.
                   - Sắp xếp thứ tự danh sách này dựa đúng theo tiêu chí: "{sort_criteria}".
                3. TỔNG HỢP REVIEW THỰC TẾ CỦA KHÁCH HÀNG:
                   - Điểm KHEN nhiều nhất: Độ bền, thiết kế, chất lượng đóng gói, tốc độ giao hàng.
                   - Điểm CHÊ / RỦI RO cần né: Hàng dễ trầy xước, form chật, lỗi kết nối, shop phục vụ kém.
                4. QUYẾT ĐỊNH MUA HÀNG (SMART VERDICT):
                   - Đưa ra lời khuyên dứt khoát: Người mua nên chọn mua ở đâu để an tâm nhất theo đúng tiêu chí đã chọn?
                
                YÊU CẦU ĐỊNH DẠNG:
                - Trình bày dạng Markdown đẹp mắt, có Bảng so sánh (Comparison Table), gạch đầu dòng rõ ràng, icon sinh động.
                """
                
                # Gom dữ liệu đầu vào
                content_inputs = []
                if uploaded_image:
                    content_inputs.append(image)
                if product_input.strip():
                    content_inputs.append(f"Thông tin bổ sung/link: {product_input}")
                content_inputs.append(prompt)
                
                # Tự động thử lần lượt các model của Google để tránh lỗi 404
                models_to_try = ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"]
                response = None
                last_err = None
                
                for m_name in models_to_try:
                    try:
                        model = genai.GenerativeModel(model_name=m_name)
                        response = model.generate_content(content_inputs)
                        if response:
                            break
                    except Exception as e:
                        last_err = e
                        continue
                
                if response:
                    st.success("✅ Phân tích hoàn tất! Dưới đây là bảng xếp hạng và đánh giá chi tiết:")
                    st.markdown(response.text)
                else:
                    raise last_err
                
            except Exception as e:
                st.error(f"Đã xảy ra lỗi: {str(e)}")
                st.info("Gợi ý: Kiểm tra lại API key trong file .env hoặc kết nối mạng.")
