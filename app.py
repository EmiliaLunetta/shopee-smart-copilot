import os
import re
import streamlit as st
from PIL import Image
from dotenv import load_dotenv
from google import genai
from google.genai import types

# ───────────────────────── 1. Môi trường & cấu hình ─────────────────────────
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

st.set_page_config(page_title="Shopee Lens AI Copilot", page_icon="🛍️", layout="wide")

st.markdown("""
    <style>
    .main-title { font-size: 32px; font-weight: bold; color: #EE4D2D; margin-bottom: 5px; }
    .sub-title { font-size: 16px; color: #555; margin-bottom: 25px; }
    .stButton>button { background-color: #EE4D2D; color: white; border-radius: 8px; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">🛍️ Shopee Lens AI: Trợ lý Mua sắm Đa phương thức</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Tải ảnh hoặc dán link sản phẩm để AI nhận diện, tra cứu thông tin thật trên web (Google Search) và gợi ý nơi mua tối ưu.</div>', unsafe_allow_html=True)


# ───────────────────────── 2. Hàm hỗ trợ ─────────────────────────
@st.cache_data(show_spinner=False, ttl=3600)
def get_available_models(key: str) -> list[str]:
    """Hỏi Google xem key này gọi được model nào, rồi xếp flash mới nhất lên đầu."""
    client = genai.Client(api_key=key)
    names = []
    for m in client.models.list():
        actions = getattr(m, "supported_actions", None) or []
        if "generateContent" in actions:
            names.append(m.name.replace("models/", ""))

    # Chỉ lấy bản flash dùng được cho text + ảnh
    skip = ["image", "tts", "live", "audio", "embedding", "robotics", "computer"]
    flash = [n for n in names if "flash" in n and not any(s in n for s in skip)]

    def sort_key(n: str):
        v = re.search(r"gemini-(\d+(?:\.\d+)?)", n)
        version = float(v.group(1)) if v else 0.0
        return (version, "lite" not in n)  # bản lite xếp sau

    return sorted(flash, key=sort_key, reverse=True)


SYSTEM_INSTRUCTION = """
Bạn là Trợ lý Mua sắm Cá nhân (AI Shopping Copilot) của Shopee. Trả lời bằng tiếng Việt, định dạng Markdown.

QUY TẮC TRUNG THỰC (RẤT QUAN TRỌNG):
- Chỉ đưa ra giá, số sao, lượt bán, nội dung review nếu bạn TÌM THẤY trong kết quả Google Search.
- Nếu không tìm thấy một thông tin nào đó, ghi rõ "Không tìm thấy dữ liệu". TUYỆT ĐỐI không đoán hoặc bịa số liệu.
- Với mỗi mức giá/đánh giá, ghi rõ nguồn (tên trang web) và nói đây là mức giá tham khảo, có thể đã thay đổi.
- Không khẳng định "shop X bán giá Y" nếu không có nguồn xác nhận.
""".strip()


def build_prompt(sort_criteria: str) -> str:
    return f"""
TIÊU CHÍ ƯU TIÊN XẾP HẠNG CỦA NGƯỜI DÙNG: "{sort_criteria}"

NHIỆM VỤ:
1. NHẬN DIỆN SẢN PHẨM: tên, thương hiệu, model, phân khúc ngành hàng (dựa vào ảnh và/hoặc link/tên người dùng cung cấp).
2. TRA CỨU THỊ TRƯỜNG bằng Google Search (ưu tiên Shopee Việt Nam, sau đó là Lazada, Tiki, TikTok Shop, trang hãng):
   - Lập BẢNG SO SÁNH 2-4 nơi bán/nguồn: Nơi bán | Loại (Mall/chính hãng/shop thường) | Giá tham khảo | Đánh giá | Nguồn.
   - Sắp xếp bảng đúng theo tiêu chí: "{sort_criteria}".
3. TỔNG HỢP REVIEW THỰC TẾ từ các nguồn tìm được:
   - 👍 Điểm khen nhiều nhất.
   - 👎 Điểm chê / rủi ro cần né.
4. KẾT LUẬN MUA HÀNG (Smart Verdict): nên mua ở đâu theo đúng tiêu chí, kèm 1-2 lưu ý để tránh hàng giả/hàng kém chất lượng.
5. Cuối bài, ghi mục "⚠️ Dữ liệu chưa xác minh" liệt kê những thông tin bạn không tìm thấy.
""".strip()


def call_gemini(client, model_name, contents):
    """Gọi 1 model với Google Search grounding bật."""
    return client.models.generate_content(
        model=model_name,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            tools=[types.Tool(google_search=types.GoogleSearch())],
            temperature=0.3,  # thấp để giảm bịa
        ),
    )


def extract_sources(response):
    """Lấy danh sách nguồn web mà Gemini đã dùng (grounding metadata)."""
    sources, seen = [], set()
    try:
        meta = response.candidates[0].grounding_metadata
        for chunk in (meta.grounding_chunks or []):
            if chunk.web and chunk.web.uri and chunk.web.uri not in seen:
                seen.add(chunk.web.uri)
                sources.append((chunk.web.title or chunk.web.uri, chunk.web.uri))
        queries = list(meta.web_search_queries or [])
    except Exception:
        queries = []
    return sources, queries


# ───────────────────────── 3. Sidebar ─────────────────────────
with st.sidebar:
    st.header("⚙️ Tiêu chí ưu tiên")

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
            "🔥 Lượt mua nhiều & Bán chạy nhất (Best Selling)",
        ],
    )

    st.divider()
    st.markdown("""
    **Về dự án:**  
    Mô hình Proof of Concept (PoC) cho **Sea GMAP 2027 (Shopee & Monee)**.  
    *Tech stack: Python, Streamlit, Google Gemini Vision + Google Search grounding.*

    **Lưu ý dữ liệu:** thông tin lấy từ kết quả Google Search công khai, không phải API chính thức của Shopee. Giá và đánh giá chỉ mang tính tham khảo.
    """)


# ───────────────────────── 4. Giao diện nhập liệu ─────────────────────────
col1, col2 = st.columns([1, 1])
image = None

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
        height=140,
    )

st.divider()


# ───────────────────────── 5. Xử lý khi bấm nút ─────────────────────────
if st.button("🚀 Quét thị trường & Xếp hạng nơi mua", use_container_width=True):
    if not uploaded_image and not product_input.strip():
        st.error("👉 Vui lòng cung cấp ít nhất một ảnh hoặc dán link/tên sản phẩm để AI phân tích!")
    else:
        with st.spinner("🤖 AI đang nhận diện sản phẩm và tra cứu giá, đánh giá trên web..."):
            try:
                client = genai.Client(api_key=api_key)

                contents = []
                if image is not None:
                    contents.append(image)
                if product_input.strip():
                    contents.append(f"Thông tin bổ sung/link: {product_input.strip()}")
                contents.append(build_prompt(sort_criteria))

                models_to_try = get_available_models(api_key)[:3]
                if not models_to_try:
                    raise RuntimeError("Key này không gọi được model flash nào. Kiểm tra lại API key.")

                response, used_model, errors = None, None, []
                for m_name in models_to_try:
                    try:
                        r = call_gemini(client, m_name, contents)
                        if r and r.text:
                            response, used_model = r, m_name
                            break
                        errors.append(f"{m_name}: phản hồi rỗng")
                    except Exception as e:
                        errors.append(f"{m_name}: {e}")

                if response is None:
                    raise RuntimeError("\n\n".join(errors))

                st.success(f"✅ Phân tích hoàn tất! (model: {used_model})")
                st.markdown(response.text)

                sources, queries = extract_sources(response)
                st.divider()
                if sources:
                    st.subheader("🔎 Nguồn dữ liệu đã tra cứu")
                    for title, uri in sources:
                        st.markdown(f"- [{title}]({uri})")
                    if queries:
                        st.caption("Từ khóa Google đã tìm: " + " | ".join(queries))
                else:
                    st.warning("⚠️ Gemini không dùng được nguồn web nào cho lần này, nên số liệu giá/đánh giá có thể không đáng tin. Hãy thử lại hoặc nhập tên sản phẩm cụ thể hơn.")

            except Exception as e:
                st.error(f"Đã xảy ra lỗi: {e}")
                st.info("Gợi ý: kiểm tra API key, hạn mức (quota) hoặc kết nối mạng.")
