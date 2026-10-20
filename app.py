import os
import re
import json
import math
import random
import hashlib
import urllib.parse
from datetime import datetime, timezone
import streamlit as st
import pandas as pd
from PIL import Image
from google import genai
from google.genai import types

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ───────────────────────── 1. Cấu hình Trang & Giao diện ─────────────────────────
st.set_page_config(
    page_title="Shopee Copilot AI - GMAP 2027",
    page_icon="🛍️",
    layout="wide"
)

st.markdown("""
<style>
.main-title { font-size: 28px; font-weight: 800; color: #EE4D2D; margin-bottom: 2px; }
.sub-title { font-size: 15px; color: #555; margin-bottom: 20px; }
.stButton>button { background-color: #EE4D2D; color: white; border-radius: 8px; font-weight: bold; border: none; }
.stButton>button:hover { background-color: #d73211; color: white; }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">🛍️ Shopee Smart Lens & Multi-Seller Copilot</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Nhận diện sản phẩm qua Ảnh/Link/Tên ➔ Quét đối soát đa seller Shopee ➔ Bóc tách đánh giá thực tế bằng AI.</div>', unsafe_allow_html=True)


# ───────────────────────── 2. Đọc Cấu hình Môi trường ─────────────────────────
def get_env(key, default=None):
    val = os.getenv(key)
    if val: return val
    try:
        return st.secrets.get(key, default)
    except Exception:
        return default

GEMINI_KEY = get_env("GEMINI_API_KEY")
APIFY_TOKEN = get_env("APIFY_TOKEN")
ACTOR_SEARCH = get_env("APIFY_ACTOR_SEARCH", "gio21/shopee-scraper")
ACTOR_REVIEWS = get_env("APIFY_ACTOR_REVIEWS", "zen-studio/shopee-product-reviews-scraper")


# ───────────────────────── 3. Utility & Xử lý Dữ liệu ─────────────────────────
def extract_product_name_from_url(raw_input: str) -> str:
    """Bóc tách từ khóa sản phẩm nếu người dùng dán cả đường link Shopee."""
    raw = raw_input.strip()
    if "shopee.vn" not in raw:
        return raw
    try:
        match = re.search(r"shopee\.vn/([^/?]+)-i\.\d+\.\d+", raw)
        if match:
            slug = match.group(1)
            return urllib.parse.unquote(slug.replace("-", " "))
        path = urllib.parse.urlparse(raw).path.strip("/").split("/")[-1]
        return urllib.parse.unquote(path.replace("-", " "))
    except Exception:
        return raw

def to_num(v, default=0.0):
    if v is None: return default
    if isinstance(v, (int, float)): return float(v)
    s = re.sub(r"[^\d.]", "", str(v).replace(",", "."))
    if s.count(".") > 1: s = s.replace(".", "")
    try: return float(s)
    except ValueError: return default

def to_bool(v):
    if isinstance(v, bool): return v
    return str(v).strip().lower() in {"1", "true", "yes"}

def parse_sold(v):
    if v is None: return None
    if isinstance(v, (int, float)): return int(v)
    s = str(v).lower().strip().replace(",", ".")
    m = re.match(r"^([\d.]+)\s*([kmb]?)", s)
    try:
        return int(float(m.group(1)) * {"": 1, "k": 1e3, "m": 1e6, "b": 1e9}[m.group(2)]) if m else 0
    except Exception:
        return None

def pick(d, *keys, default=None):
    for k in keys:
        if d.get(k) not in (None, ""): return d[k]
    return default

def vnd(x):
    if x is None: return "Chưa xác minh"
    return f"{x:,.0f}".replace(",", ".") + "đ"

def normalize_search_item(raw):
    """Chuẩn hóa dữ liệu trả về từ Search Scraper của Apify."""
    price = to_num(pick(raw, "price", "priceMin", "currentPrice", "salePrice"))
    if price <= 0: return None

    orig = to_num(pick(raw, "originalPrice", "priceBeforeDiscount"), default=None)
    if orig is not None and orig < price: orig = None
    discount_pct = int(round((orig - price) / orig * 100)) if orig and orig > price else None

    # Phát hiện Flash Sale
    is_flash = to_bool(pick(raw, "is_on_flash_sale", "flash_sale")) or "flash sale" in str(raw).lower()
    
    # Phát hiện Freeship Xtra
    freeship_val = pick(raw, "freeShipping", "is_freeship", "freeship_xtra")
    has_freeship = to_bool(freeship_val) or "freeship" in str(raw).lower()

    t = str(pick(raw, "shopType", "shop_type", default="")).lower()
    mall = to_bool(pick(raw, "isOfficialShop", "shopee_verified")) or "mall" in t
    fav = to_bool(pick(raw, "isPreferred")) or "yêu thích" in t

    sold = parse_sold(pick(raw, "historicalSoldEstimated", "sold", "historical_sold", "sales"))
    rating = to_num(pick(raw, "rating", "ratingStar"), default=None)
    rating_count = to_num(pick(raw, "reviewCount", "rating_count"), default=None)

    voucher_name = str(raw.get("voucher_name") or "Chưa có voucher")
    voucher_val = to_num(pick(raw, "voucher_discount"), default=0)
    final_price = int(price - voucher_val) if voucher_val > 0 else int(price)

    return {
        "shop": str(pick(raw, "shopName", "shop_name", "shop", "seller", default="Shop Shopee")),
        "shop_type": "Mall" if mall else "Yêu thích+" if fav else "Thường",
        "title": str(pick(raw, "name", "title", "productName", default="")),
        "price": int(price),
        "orig_price": int(orig) if orig is not None else None,
        "is_flash": is_flash,
        "has_freeship": has_freeship,
        "promo_tag": "⚡ Flash Sale" if is_flash else (f"Giảm {discount_pct}%" if discount_pct else "Bán tiêu chuẩn"),
        "freeship_tag": "🟢 Freeship Xtra" if has_freeship else "⚪ Tiêu chuẩn",
        "discount_pct": discount_pct,
        "rating": round(rating, 1) if rating is not None else None,
        "rating_count": int(rating_count) if rating_count is not None else None,
        "sold": sold,
        "voucher": voucher_name,
        "final": final_price,
        "url": str(pick(raw, "url", "productUrl", "link", default="")),
        "flag": "",
        "source": "Apify Real-time"
    }


# ───────────────────────── 4. Tích hợp Apify Scraping ─────────────────────────
@st.cache_data(show_spinner=False, ttl=300)
def fetch_apify_search(token, keyword, max_items=20):
    """Giai đoạn 1: Quét danh sách seller bán sản phẩm."""
    from apify_client import ApifyClient
    cli = ApifyClient(token)
    run_input = {"keywords": [keyword], "country": "VN", "maxItems": max_items}
    run = cli.actor(ACTOR_SEARCH).call(run_input=run_input, timeout_secs=120)
    raw_dataset = cli.dataset(run["defaultDatasetId"]).iterate_items()
    items = [x for x in (normalize_search_item(r) for r in raw_dataset) if x]
    return items

@st.cache_data(show_spinner=False, ttl=600)
def fetch_apify_reviews(token, product_url, max_reviews=15):
    """Giai đoạn 2: Cào bình luận thực tế từ shop dẫn đầu bằng zen-studio."""
    if not token or not product_url or "shopee.vn" not in product_url:
        return []
    from apify_client import ApifyClient
    try:
        cli = ApifyClient(token)
        run_input = {
            "startUrls": [{"url": product_url}],
            "maxReviewsPerProduct": max_reviews,
            "starFilter": "all"
        }
        run = cli.actor(ACTOR_REVIEWS).call(run_input=run_input, timeout_secs=70)
        raw_items = cli.dataset(run["defaultDatasetId"]).iterate_items()
        reviews = []
        for r in raw_items:
            cmt = (r.get("comment") or r.get("text") or r.get("buyerFeedback") or "").strip()
            star = r.get("rating_star") or r.get("star") or 5
            if cmt:
                reviews.append({"star": int(to_num(star, 5)), "comment": cmt[:250]})
        return reviews
    except Exception as e:
        print(f"Lỗi cào review: {e}")
        return []

def fetch_mock(keyword, brand):
    """Dữ liệu mô phỏng dự phòng phòng khi Apify hết quota."""
    rng = random.Random(int(hashlib.md5(keyword.lower().encode()).hexdigest(), 16) % 2**32)
    b = (brand or "Chính Hãng").title()
    spec = [
        (f"{b} Official Store", "Mall", 1.05, 4.9, 15000, 20, True, True),
        (f"{b} Flagship Store", "Mall", 1.0, 4.8, 8000, 15, False, True),
        ("Thế Giới Phụ Kiện Uy Tín", "Yêu thích+", 0.88, 4.7, 4500, 25, True, True),
        ("Kho Sỉ Công Nghệ Hà Nội", "Thường", 0.75, 4.5, 1200, 10, False, False),
        ("Săn Sale Xả Kho 247", "Thường", 0.32, 3.8, 25, 70, True, False)  # Cố tình tạo 1 shop giá ảo để test flag
    ]
    base = 450_000
    items = []
    for s, t, f, r, n, disc, is_fl, is_free in spec:
        p = int(round(base * f * rng.uniform(0.96, 1.04) / 1000) * 1000)
        orig = int(round(p / (1 - disc / 100) / 1000) * 1000)
        items.append({
            "shop": s, "shop_type": t, "title": f"{keyword} ({b})",
            "price": p, "orig_price": orig, "is_flash": is_fl, "has_freeship": is_free,
            "promo_tag": f"⚡ Flash Sale (-{disc}%)" if is_fl else f"Giảm {disc}%",
            "freeship_tag": "🟢 Freeship Xtra" if is_free else "⚪ Tiêu chuẩn",
            "discount_pct": disc, "rating": r, "rating_count": int(n * 0.2), "sold": n,
            "voucher": "Voucher Shop 15k" if disc > 20 else "Chưa có",
            "final": p - (15000 if disc > 20 else 0),
            "url": "https://shopee.vn", "flag": "", "source": "Dữ liệu Mô Phỏng"
        })
    return items

def prepare_and_flag(items):
    """Gắn cờ kiểm tra giá ảo/rủi ro hàng giả."""
    if len(items) >= 4:
        valid_prices = sorted([i["price"] for i in items if i["price"] > 0])
        med = valid_prices[len(valid_prices) // 2]
        for i in items:
            if i["price"] < 0.35 * med and (i["sold"] or 0) < 100:
                i["flag"] = "⚠️ Giá quá thấp so với thị trường (Nguy cơ hàng giả/treo đầu dê)"
    return items

def rank_items(items, mode):
    def legit_score(p):
        r = p["rating"] or 0
        cnt = p["rating_count"] or 0
        mall_bonus = 0.5 if p["shop_type"] == "Mall" else (0.25 if p["shop_type"] == "Yêu thích+" else 0)
        return r + 0.3 * min(math.log10(cnt + 1), 3) + mall_bonus - (2.0 if p["flag"] else 0)

    if mode == "price":
        return sorted(items, key=lambda p: (bool(p["flag"]), p["final"] or p["price"]))
    elif mode == "sales":
        return sorted(items, key=lambda p: p["sold"] or 0, reverse=True)
    elif mode == "flash":
        return sorted(items, key=lambda p: (not p["is_flash"], bool(p["flag"]), p["price"]))
    # Mặc định: Uy tín
    return sorted(items, key=lambda p: -legit_score(p))


# ───────────────────────── 5. Gemini AI Engine ─────────────────────────
def identify_product(client, image, text_query):
    """Gemini Vision: Nhận diện thực thể sản phẩm từ ảnh và mô tả."""
    prompt = """Bạn là Chuyên gia bóc tách sản phẩm E-commerce của Shopee.
Phân tích ảnh và/hoặc mô tả của người dùng, trả về DUY NHẤT một chuỗi JSON chuẩn:
{
  "name": "Tên thương mại đầy đủ",
  "brand": "Thương hiệu",
  "keyword": "Từ khóa tìm kiếm tối ưu trên Shopee (3-6 từ)"
}"""
    contents = []
    if image is not None: contents.append(image)
    if text_query: contents.append(f"Mô tả của người dùng: {text_query}")
    contents.append(prompt)

    res = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=contents,
        config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.1)
    )
    return json.loads(re.sub(r"```json|```", "", res.text).strip())

def generate_verdict_with_reviews(client, product_info, top_shop, ranked_list, reviews, is_mock):
    """Phân tích deal và bóc tách đánh giá người mua bằng Gemini."""
    reviews_formatted = "\n".join([f"- [{r['star']}⭐]: {r['comment']}" for r in reviews]) if reviews else "Chưa cào được bình luận chi tiết (Shop có thể mới hoặc cần đăng nhập để xem)."
    
    prompt = f"""Bạn là Trợ lý Mua sắm Cấp cao của Shopee Việt Nam. Hãy đưa ra nhận định sắc sảo, khách quan, định dạng Markdown.
Sản phẩm: {product_info.get('name')}
{'[LƯU Ý: ĐANG SỬ DỤNG DỮ LIỆU MÔ PHỎNG]' if is_mock else '[DỮ LIỆU THẬT THU THẬP TỪ SHOPEE]'}

SHOP ĐƯỢC ĐỀ XUẤT TỐI ƯU NHẤT:
- Tên shop: {top_shop['shop']} ({top_shop['shop_type']})
- Giá niêm yết: {top_shop['price']:,}đ | Giá sau voucher: {top_shop['final']:,}đ
- Flash Sale: {'Có' if top_shop['is_flash'] else 'Không'} | Freeship: {top_shop['freeship_tag']}
- Lượt bán: {top_shop['sold']} | Điểm sao: {top_shop['rating']}⭐

BÌNH LUẬN THỰC TẾ TỪ KHÁCH HÀNG ĐÃ MUA:
{reviews_formatted}

NHIỆM VỤ:
### 1. 📊 Phân tích Deal & Lý do Chọn Shop Này
- Đánh giá mức giá {top_shop['final']:,}đ so với mặt bằng chung các shop khác trong bảng.
- Nhận xét về độ an toàn dựa vào huy hiệu ({top_shop['shop_type']}) và cờ cảnh báo (nếu có).

### 2. 💬 Bóc tách Bình luận Người mua (Buyer Sentiment)
- 👍 **Điểm khen nhiều nhất:** (tính năng, đóng gói, tốc độ giao hàng...).
- 👎 **Điểm phàn nàn / Rủi ro cần lưu ý:** (lỗi vặt, thời lượng pin, shop rep chậm...).

### 3. 🎯 Lời khuyên Chốt đơn (Smart Verdict)
- Có nên mua ngay lúc này hay chờ khung giờ Flash Sale / Siêu Sale (11.11, 12.12)?
- Nhắc nhở quy tắc đồng kiểm và quay video mở hộp Shopee."""

    res = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[prompt],
        config=types.GenerateContentConfig(temperature=0.2)
    )
    return res.text


# ───────────────────────── 6. Sidebar Điều khiển ─────────────────────────
with st.sidebar:
    st.header("⚙️ Cấu hình Hệ thống")
    if not GEMINI_KEY:
        GEMINI_KEY = st.text_input("Gemini API Key:", type="password")
    if not APIFY_TOKEN:
        APIFY_TOKEN = st.text_input("Apify API Token (Scraper):", type="password")
    
    st.divider()
    sort_choice = st.selectbox(
        "🎯 Tiêu chí ưu tiên chọn shop:",
        [
            ("🌟 Uy tín nhất (Shopee Mall / Đánh giá cao)", "legit"),
            ("💰 Giá rẻ nhất (Tối ưu túi tiền)", "price"),
            ("🔥 Bán chạy nhất (Nhiều người mua)", "sales"),
            ("⚡ Đang có Flash Sale sâu", "flash")
        ],
        format_func=lambda x: x[0]
    )[1]

    allow_mock = st.checkbox("Cho phép dùng Dữ liệu Mô phỏng (nếu Apify hết quota)", value=True)
    st.caption("Sea GMAP 2027 Demo · Shopee Copilot PoC")


# ───────────────────────── 7. Giao diện Nhập liệu ─────────────────────────
col1, col2 = st.columns(2)
image_input = None

with col1:
    st.subheader("📷 1. Shopee Lens (Tìm bằng ảnh)")
    uploaded_file = st.file_uploader("Tải ảnh sản phẩm cần tìm...", type=["jpg", "jpeg", "png"])
    if uploaded_file:
        image_input = Image.open(uploaded_file)
        st.image(image_input, use_container_width=True)

with col2:
    st.subheader("🔗 2. Tên hoặc Link Shopee")
    text_query = st.text_area(
        "Dán link sản phẩm Shopee hoặc gõ tên:",
        placeholder="Ví dụ:\n- https://shopee.vn/Tai-nghe-Baseus-Bowie-M2-i.131112.341412\n- Loa bluetooth Marshall Emberton II",
        height=140
    )

st.divider()

# ───────────────────────── 8. Thực thi Pipeline ─────────────────────────
if st.button("🚀 Quét Toàn Diện Shopee & Bóc Tách Review", use_container_width=True):
    if not image_input and not text_query.strip():
        st.error("👉 Vui lòng cung cấp ít nhất 1 ảnh hoặc nhập tên / link sản phẩm.")
        st.stop()

    if not GEMINI_KEY:
        st.error("Vui lòng nhập Gemini API Key ở thanh bên trái!")
        st.stop()

    gemini_client = genai.Client(api_key=GEMINI_KEY)

    # BƯỚC 1: Xử lý link & Nhận diện sản phẩm
    cleaned_text = extract_product_name_from_url(text_query)
    with st.spinner("🤖 AI đang nhận diện sản phẩm & chuẩn hóa từ khóa..."):
        try:
            prod_info = identify_product(gemini_client, image_input, cleaned_text)
        except Exception as e:
            prod_info = {"name": cleaned_text[:80], "brand": "", "keyword": cleaned_text[:60]}

    keyword = prod_info.get("keyword") or prod_info.get("name")
    st.subheader(f"📦 Sản phẩm: {prod_info.get('name')} | Hãng: {prod_info.get('brand') or 'Đa dạng'}")

    # BƯỚC 2: Quét thị trường Shopee (Giai đoạn 1)
    items, is_mock = [], False
    if APIFY_TOKEN:
        with st.spinner(f"🛒 Apify đang quét các shop bán '{keyword}' trên Shopee..."):
            try:
                items = fetch_apify_search(APIFY_TOKEN, keyword)
            except Exception as e:
                st.warning(f"Không thể cào dữ liệu thật từ Apify: {str(e)[:120]}")

    if not items:
        if allow_mock:
            items = fetch_mock(keyword, prod_info.get("brand"))
            is_mock = True
            st.info("ℹ️ Đang hiển thị **Dữ liệu Mô phỏng** để bạn trải nghiệm luồng giao diện.")
        else:
            st.error("Không thể lấy dữ liệu thật từ Shopee và chế độ mô phỏng đang tắt.")
            st.stop()

    # Xếp hạng & hiển thị bảng
    ranked_items = rank_items(prepare_and_flag(items), sort_choice)
    top_deal = ranked_items[0]

    df_display = pd.DataFrame([{
        "#": i,
        "Shop": p["shop"],
        "Loại Shop": p["shop_type"],
        "Flash Sale": p["promo_tag"],
        "Freeship": p["freeship_tag"],
        "Giá gốc": vnd(p["orig_price"]),
        "Giá bán": vnd(p["price"]),
        "Sau Voucher": vnd(p["final"]),
        "Đánh giá": f"{p['rating']} ⭐" if p["rating"] else "Chưa có",
        "Đã bán": f"{p['sold']:,}".replace(",", ".") if p["sold"] else "0",
        "Cảnh báo": p["flag"] if p["flag"] else "An toàn",
        "Link": p["url"]
    } for i, p in enumerate(ranked_items[:8], 1)])

    st.dataframe(
        df_display,
        use_container_width=True,
        hide_index=True,
        column_config={"Link": st.column_config.LinkColumn("Shopee Link", display_text="Xem shop")}
    )

    st.success(f"🏆 **Shop đề xuất:** {top_deal['shop']} ({top_deal['shop_type']}) | Giá chốt: **{vnd(top_deal['final'])}** | Ưu đãi: **{top_deal['promo_tag']}**")

    # BƯỚC 3: Cào Review thực tế & AI Bóc tách (Giai đoạn 2)
    reviews = []
    if APIFY_TOKEN and not is_mock and "shopee.vn" in top_deal["url"]:
        with st.spinner(f"🕵️ Đang dùng `zen-studio` cào bình luận người mua từ shop: {top_deal['shop']}..."):
            reviews = fetch_apify_reviews(APIFY_TOKEN, top_deal["url"], max_reviews=12)

    if is_mock or not reviews:
        # Giả lập review mô phỏng nếu đang ở chế độ mock
        reviews = [
            {"star": 5, "comment": "Giao hàng siêu nhanh, tai nghe nghe êm, bass căng, hàng nguyên seal chính hãng."},
            {"star": 5, "comment": "Đóng gói kỹ 2 lớp bọt khí, kết nối app nhanh, dùng 3 ngày mới phải sạc pin."},
            {"star": 4, "comment": "Chống ồn tạm ổn trong tầm giá, đi ngoài đường ồn vẫn nghe tiếng gió."},
            {"star": 2, "comment": "Hộp hơi móp do vận chuyển, shop trả lời tin nhắn hơi chậm trễ."}
        ]

    # BƯỚC 4: Gemini tổng hợp báo cáo chuyên sâu
    with st.spinner("🤖 AI đang phân tích ưu/nhược điểm và đánh giá rủi ro..."):
        analysis_markdown = generate_verdict_with_reviews(
            gemini_client, prod_info, top_deal, ranked_items, reviews, is_mock
        )
        st.markdown(analysis_markdown)
