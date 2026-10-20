import os
import re
import urllib.parse
import streamlit as st
from PIL import Image
from dotenv import load_dotenv
from google import genai
from google.genai import types

# ───────────────────────── 1. Cấu hình trang ─────────────────────────
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

st.set_page_config(
    page_title="Shopee Smart Lens AI - GMAP 2027 PoC",
    page_icon="🛍️",
    layout="wide"
)

st.markdown("""
    <style>
    .main-title { font-size: 30px; font-weight: 800; color: #EE4D2D; margin-bottom: 0px; }
    .sub-title { font-size: 15px; color: #666; margin-bottom: 20px; }
    .shopee-badge { background-color: #EE4D2D; color: white; padding: 3px 8px; border-radius: 4px; font-size: 12px; font-weight: bold; }
    .stButton>button { background-color: #EE4D2D; color: white; border-radius: 8px; font-weight: bold; border: none; }
    .stButton>button:hover { background-color: #d73211; color: white; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">🛍️ Shopee Copilot: Multi-Seller & Review Analyzer</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">AI Engine hỗ trợ nhận diện sản phẩm, quét các seller trên Shopee, đối soát Flash Sale, Freeship Xtra & bóc tách bình luận người mua.</div>', unsafe_allow_html=True)


# ───────────────────────── 2. Utility & Helpers ─────────────────────────
def extract_product_name_from_url(url: str) -> str:
    """Bóc tách tên sản phẩm từ URL Shopee nếu người dùng chỉ dán link."""
    url = url.strip()
    if "shopee.vn" not in url:
        return url
    try:
        parsed = urllib.parse.urlparse(url)
        path = parsed.path.strip("/")
        # URL Shopee dạng: /Ten-San-Pham-i.123456.7891011
        if "-i." in path:
            slug = path.split("-i.")[0]
            clean_name = slug.replace("-", " ")
            return urllib.parse.unquote(clean_name)
    except Exception:
        pass
    return url


@st.cache_data(show_spinner=False, ttl=3600)
def get_available_models(key: str) -> list[str]:
    """Lấy danh sách các model Flash khả dụng từ Google."""
    client = genai.Client(api_key=key)
    names = []
    for m in client.models.list():
        actions = getattr(m, "supported_actions", None) or []
        if "generateContent" in actions:
            names.append(m.name.replace("models/", ""))

    skip = ["image", "tts", "live", "audio", "embedding", "robotics", "computer"]
    flash = [n for n in names if "flash" in n and not any(s in n for s in skip)]

    def sort_key(n: str):
        v = re.search(r"gemini-(\d+(?:\.\d+)?)", n)
        version = float(v.group(1)) if v else 0.0
        return (version, "lite" not in n)

    return sorted(flash, key=sort_key, reverse=True)


# ───────────────────────── 3. System Instructions & Prompt Engine ─────────────────────────
SYSTEM_INSTRUCTION = """
Bạn là Trợ lý Mua sắm Thông minh Độc quyền của Shopee Việt Nam (Shopee Copilot AI).
Nhiệm vụ của bạn là phục vụ người mua hàng bằng cách phân tích ĐA ĐỐI TÁC BÁN HÀNG (Multi-Seller) trên Shopee.

QUY TẮC CỐT LÕI:
1. TRUNG THỰC TUYỆT ĐỐI: Dữ liệu về giá, Flash Sale, voucher, lượt bán, đánh giá review PHẢI dựa trên kết quả tìm kiếm thực tế trên Shopee (qua Google Search grounding). Nếu không tìm thấy, ghi rõ "Chưa có dữ liệu xác minh", KHÔNG tự bịa đặt.
2. CHUYÊN BIỆT SHOPEE: Tập trung tìm kiếm các seller trên shopee.vn. Nhận diện các nhãn đặc trưng: Shopee Mall, Shop Yêu Thích (SYT), Shop Yêu Thích+ (SYT+), Shop thường.
3. PHÂN TÍCH ƯU ĐÃI: Cố gắng phát hiện các nhãn "Freeship Xtra", "Flash Sale" hoặc "Voucher Giảm Giá" nếu thông tin hiển thị.
4. BÓC TÁCH BÌNH LUẬN: Đọc và lọc các phản hồi thực tế của khách hàng (khen điểm gì, chê lỗi kỹ thuật/đóng gói/giao hàng thế nào).
""".strip()


def build_copilot_prompt(product_hint: str, sort_criteria: str) -> str:
    return f"""
MỤC TIÊU PHÂN TÍCH MUA SẮM TẠI SHOPEE VIỆT NAM
Sản phẩm đầu vào: "{product_hint}"
Tiêu chí ưu tiên của người mua: "{sort_criteria}"

Hãy thực hiện các bước sau (sử dụng Google Search tìm kiếm tập trung cú pháp `site:shopee.vn`):

### 1. NHẬN DIỆN SẢN PHẨM
- Tên chính xác, Thương hiệu (Brand), Model/Mã sản phẩm, Phân khúc giá trung bình trên thị trường.

### 2. MA TRẬN SO SÁNH CÁC SELLER TRÊN SHOPEE (Tìm từ 2-4 Seller đại diện)
Hãy lập bảng Markdown so sánh chi tiết:
| Tên Shop / Link Shopee | Phân loại Shop (Mall / Yêu Thích / Shop thường) | Mức giá niêm yết & Giá ưu đãi | Trạng thái Flash Sale / Freeship Xtra | Đánh giá (Sao / Lượt bán) |
|---|---|---|---|---|

*Lưu ý:* Hãy sắp xếp thứ tự bảng theo đúng tiêu chí người dùng chọn: "{sort_criteria}".

### 3. TỔNG HỢP REVIEW & BÌNH LUẬN NGƯỜI MUA THỰC TẾ (User Sentiment)
Dựa vào đánh giá của người mua từ các link tìm thấy trên Shopee:
- 👍 **Điểm khen nhiều nhất:** (Chất lượng, tính năng, tốc độ giao hàng...)
- ⚠️ **Điểm phàn nàn / Rủi ro cần chú ý:** (Ví dụ: hộp móp méo, pin tụt nhanh, khó kết nối, shop phản hồi chậm...)

### 4. ĐỀ XUẤT MUA TỐI ƯU (Shopee Smart Verdict)
- **Shop đề xuất nên chốt đơn:** Chỉ định rõ nên mua ở shop nào trong bảng trên và lý do phù hợp nhất với tiêu chí "{sort_criteria}".
- **Tips săn sale Shopee:** Gợi ý cách áp dụng voucher Freeship Xtra hoặc khung giờ Flash Sale để có giá tốt nhất.
""".strip()


def call_gemini(client, model_name, contents):
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        tools=[types.Tool(google_search=types.GoogleSearch())],
        temperature=0.2,  # Giảm nhiệt độ để đảm bảo tính chính xác của dữ liệu
    )
    return client.models.generate_content(model=model_name, contents=contents, config=config)


# ───────────────────────── 4. Sidebar ─────────────────────────
with st.sidebar:
    st.header("⚙️ Tiêu chí & Cấu hình")

    if not api_key:
        api_key = st.text_input("Nhập Google Gemini API Key:", type="password")
        if not api_key:
            st.warning("Vui lòng cấp API key để tiếp tục.")
            st.stop()

    sort_criteria = st.selectbox(
        "🎯 Tiêu chí ưu tiên chọn shop:",
        [
            "🌟 Uy tín hàng đầu (Ưu tiên Shopee Mall & Đánh giá 4.9*+)",
            "💰 Giá rẻ nhất (Tối ưu ngân sách, kèm Freeship Xtra)",
            "🔥 Bán chạy nhất & Đánh giá tích cực (Highest Sales Volume)",
            "⚡ Đang có Flash Sale / Ưu đãi sâu nhất",
        ],
    )

    try:
        available_models = get_available_models(api_key)
    except Exception as e:
        available_models = []
        st.error(f"Lỗi nạp model: {str(e)[:100]}")

    AUTO = "Tự động (Model tối ưu nhất)"
    model_choice = st.selectbox("🤖 Model AI:", [AUTO] + available_models)

    st.divider()
    st.markdown("""
    **Shopee Innovation Lab - GMAP 2027**  
    *Mô phỏng tính năng: Contextual Multi-seller Search & Review Grounding Engine.*
    """)


# ───────────────────────── 5. UI Nhập liệu ─────────────────────────
col1, col2 = st.columns([1, 1])
image = None

with col1:
    st.subheader("📷 1. Ảnh sản phẩm (Shopee Lens)")
    uploaded_image = st.file_uploader("Tải ảnh sản phẩm cần đối soát giá...", type=["jpg", "jpeg", "png"])
    if uploaded_image:
        image = Image.open(uploaded_image)
        st.image(image, caption="Ảnh nhận diện", use_container_width=True)

with col2:
    st.subheader("🔗 2. Tên hoặc Link Shopee")
    raw_input = st.text_area(
        "Nhập tên sản phẩm hoặc dán thẳng link Shopee:",
        placeholder="Ví dụ:\n- https://shopee.vn/Tai-nghe-Bluetooth-Baseus-Bowie-M2-i.123456.789\n- Robot hút bụi Xiaomi Dreame D9 Max",
        height=140,
    )

st.divider()

# ───────────────────────── 6. Xử lý logic ─────────────────────────
if st.button("🔎 Quét Seller Shopee & Phân tích Đánh giá", use_container_width=True):
    if not uploaded_image and not raw_input.strip():
        st.error("👉 Vui lòng tải ít nhất một ảnh hoặc nhập tên/link Shopee!")
    else:
        with st.spinner("🚀 AI đang quét các seller Shopee, đối chiếu Flash Sale & bóc tách đánh giá..."):
            try:
                client = genai.Client(api_key=api_key)

                # 1. Tiền xử lý link nếu có
                parsed_text = extract_product_name_from_url(raw_input)

                contents = []
                if image is not None:
                    contents.append(image)
                if parsed_text:
                    contents.append(f"Thông tin sản phẩm/từ khóa truy vấn: {parsed_text}")
                
                # Nạp prompt phân tích đa chiều
                contents.append(build_copilot_prompt(parsed_text, sort_criteria))

                # 2. Quyết định model
                models_to_try = [model_choice] if model_choice != AUTO else available_models[:3]
                if not models_to_try:
                    models_to_try = ["gemini-2.5-flash", "gemini-1.5-flash"]

                response = None
                used_model = None

                for m in models_to_try:
                    try:
                        res = call_gemini(client, m, contents)
                        if res and res.text:
                            response = res
                            used_model = m
                            break
                    except Exception:
                        continue

                if not response:
                    raise RuntimeError("Không thể kết nối hoặc đã vượt quá hạn mức quota API.")

                # 3. Hiển thị kết quả
                st.success(f"✅ Hoàn tất đối soát thị trường qua model: **{used_model}**")
                st.markdown(response.text)

                # 4. Hiển thị nguồn trích dẫn thật từ Shopee
                try:
                    meta = response.candidates[0].grounding_metadata
                    sources = []
                    for chunk in (meta.grounding_chunks or []):
                        if chunk.web and chunk.web.uri:
                            sources.append((chunk.web.title or chunk.web.uri, chunk.web.uri))
                    
                    if sources:
                        st.divider()
                        st.subheader("📍 Các link Shopee & trang nguồn AI đã thu thập:")
                        for title, uri in sources:
                            st.markdown(f"- [{title}]({uri})")
                except Exception:
                    pass

            except Exception as e:
                st.error(f"Đã xảy ra lỗi: {e}")
