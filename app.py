import os
import re
import json
import math
import random
import hashlib
import urllib.parse
from datetime import timedelta
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
    if val:
        return val
    try:
        return st.secrets.get(key, default)
    except Exception:
        return default

GEMINI_KEY = get_env("GEMINI_API_KEY")
GEMINI_MODEL = get_env("GEMINI_MODEL", "gemini-3.8-flash")
APIFY_TOKEN = get_env("APIFY_TOKEN")
# Đặt GEMINI_USE_VERTEX=1 nếu khóa Gemini dạng "AQ." bị lỗi 401 ACCESS_TOKEN_TYPE_UNSUPPORTED với Gemini API thường
GEMINI_USE_VERTEX = str(get_env("GEMINI_USE_VERTEX", "")).strip().lower() in ("1", "true", "yes")
# Actor tìm kiếm: https://console.apify.com/actors/XjUm7zx5pJe3kYukv  (lergassy/shopee-scraper)
ACTOR_SEARCH = get_env("APIFY_ACTOR_SEARCH", "lergassy/shopee-scraper")
# Actor review: https://console.apify.com/actors/ordFA3h76hclTx5tv  (wyle/shopee-product-reviews-scraper)
# (actor cũ zen-studio/shopee-product-reviews-scraper hay bị FAILED; vẫn dùng được nếu đặt biến APIFY_ACTOR_REVIEWS)
ACTOR_REVIEWS = get_env("APIFY_ACTOR_REVIEWS", "wyle/shopee-product-reviews-scraper")
# Shopee chặn IP datacenter ở luồng review. Nếu gói Apify của bạn có residential proxy, đặt APIFY_REVIEWS_PROXY_GROUP=RESIDENTIAL
REVIEWS_PROXY_GROUP = get_env("APIFY_REVIEWS_PROXY_GROUP")


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
    """Đổi giá trị về số, hiểu đúng định dạng Việt Nam ('450.000' = 450000)."""
    if v is None or isinstance(v, bool):
        return default
    if isinstance(v, (int, float)):
        return float(v)
    s = re.sub(r"[^\d.,]", "", str(v))
    if not s:
        return default
    if re.fullmatch(r"\d{1,3}([.,]\d{3})+", s):
        s = re.sub(r"[.,]", "", s)
    else:
        s = s.replace(",", ".")
        if s.count(".") > 1:
            s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return default

def vnd(x):
    if x is None:
        return "—"
    return f"{x:,.0f}".replace(",", ".") + "đ"

def normalize_search_item(raw, rank=0):
    """Chuẩn hóa 1 dòng của actor lergassy/shopee-scraper (type = product)."""
    if raw.get("type", "product") not in ("product", "product_detail"):
        return None

    price = to_num(raw.get("price"))
    if price <= 0:
        price = to_num(raw.get("priceMin"))
    if price <= 0:
        return None

    orig = to_num(raw.get("originalPrice"), default=None)
    if orig is not None and orig <= price:
        orig = None
    discount = raw.get("discountPercent")
    discount = int(to_num(discount)) if discount not in (None, "") else None
    if not discount and orig:
        discount = int(round((orig - price) / orig * 100))
    discount = discount or None

    labels = raw.get("labels") or []
    if isinstance(labels, str):
        labels = [labels]
    labels = [str(x) for x in labels if x]
    low = " | ".join(labels).lower()
    is_flash = "flash" in low
    has_freeship = ("freeship" in low) or ("free ship" in low) or ("vận chuyển" in low)

    seller = raw.get("seller") if isinstance(raw.get("seller"), dict) else {}
    shop = str(raw.get("shopName") or seller.get("name") or "Shop Shopee")
    # Actor không trả cờ Mall/Yêu thích -> chỉ đoán theo tên shop, ghi rõ là ước đoán.
    name_low = shop.lower()
    official_guess = any(k in name_low for k in ("official", "mall", "flagship", "chính hãng"))

    rating = to_num(raw.get("rating"), default=None) or None
    rating_count = to_num(raw.get("ratingCount"), default=None)
    rating_count = int(rating_count) if rating_count else None
    shop_rating = to_num(raw.get("shopRating"), default=None) or None

    shop_id = str(raw.get("shopId") or "")
    item_id = str(raw.get("itemId") or "")
    url = str(raw.get("url") or "")
    # Actor review bắt buộc URL dạng -i.<shopId>.<itemId>
    review_url = f"https://shopee.vn/product-i.{shop_id}.{item_id}" if shop_id and item_id else url

    return {
        "shop": shop,
        "shop_type": "Official (đoán theo tên)" if official_guess else "Thường",
        "title": str(raw.get("title") or raw.get("name") or ""),
        "price": int(price),
        "orig_price": int(orig) if orig else None,
        "discount_pct": discount,
        "final": int(price),  # Actor không có thông tin voucher -> giá cuối = giá bán
        "is_flash": is_flash,
        "has_freeship": has_freeship,
        "labels": labels,
        "promo_tag": "⚡ Flash Sale" if is_flash else (f"Giảm {discount}%" if discount else "Bán tiêu chuẩn"),
        "freeship_tag": "🟢 Freeship" if has_freeship else "—",
        "location": str(raw.get("location") or ""),
        "rating": round(rating, 1) if rating else None,
        "rating_count": rating_count,
        "shop_rating": round(shop_rating, 2) if shop_rating else None,
        "sold": None,  # Shopee không công khai lượt bán cho khách chưa đăng nhập
        "position": int(to_num(raw.get("position"), default=rank) or rank),
        "url": url,
        "review_url": review_url,
        "flag": "",
        "source": "Apify Real-time",
    }


# ───────────────────────── 4. Tích hợp Apify Scraping ─────────────────────────
def _run_actor(cli, actor_id, run_input, wait_secs):
    """Gọi actor, tương thích nhiều phiên bản apify-client."""
    actor = cli.actor(actor_id)
    try:
        return actor.call(run_input=run_input, wait_duration=timedelta(seconds=wait_secs))
    except TypeError:
        return actor.call(run_input=run_input, wait_secs=wait_secs)

def _run_field(run, snake):
    if run is None:
        return None
    if isinstance(run, dict):
        camel = re.sub(r"_([a-z])", lambda m: m.group(1).upper(), snake)
        return run.get(camel, run.get(snake))
    return getattr(run, snake, None)

def _run_status(run):
    s = _run_field(run, "status")
    s = getattr(s, "value", s)
    return str(s or "").upper().replace("RUNSTATUS.", "")

def _wait_until_done(cli, run, max_secs):
    """Nếu run còn RUNNING sau lần chờ đầu, chờ tiếp (tối đa max_secs) thay vì coi là lỗi."""
    import time
    deadline = time.time() + max_secs
    while run is not None and _run_status(run) in ("RUNNING", "READY") and time.time() < deadline:
        run_id = _run_field(run, "id")
        try:
            new = cli.run(run_id).wait_for_finish(wait_duration=timedelta(seconds=30))
        except TypeError:
            new = cli.run(run_id).wait_for_finish(wait_secs=30)
        if new is not None:
            run = new
        time.sleep(1)
    return run

def _load_dataset(cli, run, actor_id, wait_more=240):
    """Chờ run xong, kiểm tra thành công rồi đọc toàn bộ dataset."""
    if run is None:
        raise TimeoutError(f"{actor_id}: không nhận được thông tin run.")
    run = _wait_until_done(cli, run, wait_more)
    status = _run_status(run)
    run_id = _run_field(run, "id")
    if status in ("RUNNING", "READY"):
        raise TimeoutError(f"{actor_id}: run {run_id} vẫn đang chạy sau {wait_more}s. Mở Apify Console để xem kết quả, hoặc thử lại sau ít phút.")
    if status != "SUCCEEDED":
        raise RuntimeError(f"{actor_id}: run {run_id} kết thúc với trạng thái {status or 'không rõ'} (xem Log trong Apify Console).")
    ds_id = _run_field(run, "default_dataset_id")
    return list(cli.dataset(ds_id).iterate_items())

@st.cache_data(show_spinner=False, ttl=300)
def fetch_apify_search(token, actor_id, keyword, sort_by="relevancy", max_items=20):
    """Giai đoạn 1: quét danh sách shop bán sản phẩm (lergassy/shopee-scraper).
    Lỗi/kết quả rỗng được raise để KHÔNG bị cache."""
    from apify_client import ApifyClient
    cli = ApifyClient(token)
    run_input = {
        "mode": "search",
        "country": "VN",
        "searchTerms": [keyword],
        "maxItems": max_items,
        "sortBy": sort_by,               # relevancy | sales | latest | price_asc | price_desc
        "includeShopAndReviews": True,   # thêm shopName, shopRating, ratingCount (không tính thêm phí)
    }
    run = _run_actor(cli, actor_id, run_input, wait_secs=150)
    rows = _load_dataset(cli, run, actor_id)
    if not rows:
        raise RuntimeError("Dataset rỗng: actor không trả về dòng nào.")

    items = []
    others = []
    for i, r in enumerate(rows, 1):
        it = normalize_search_item(r, rank=i)
        if it:
            items.append(it)
        elif r.get("type") != "product":
            others.append({k: r.get(k) for k in ("type", "error", "kind", "note", "message") if r.get(k)})
    meta = {
        "raw_count": len(rows),
        "sample": rows[0],
        "non_product_rows": others[:5],
        "run_id": _run_field(run, "id"),
    }
    if not items:
        raise RuntimeError(f"Có {len(rows)} dòng nhưng không có sản phẩm hợp lệ. Dòng đầu: {json.dumps(rows[0], ensure_ascii=False)[:400]}")
    return items, meta

@st.cache_data(show_spinner=False, ttl=600)
def _fetch_reviews_cached(token, actor_id, product_url, max_reviews):
    from apify_client import ApifyClient
    cli = ApifyClient(token)
    run_input = {
        "startUrls": [{"url": product_url}],
        "maxReviewsPerProduct": max_reviews,
        "starFilter": "all",
        "contentFilter": "with comments",
        "includeSummary": True,  # giữ lại để biết khi nào Shopee chặn (chỉ có summary, không có review)
    }
    if REVIEWS_PROXY_GROUP:
        run_input["proxyConfiguration"] = {"useApifyProxy": True, "apifyProxyGroups": [REVIEWS_PROXY_GROUP]}
    run = _run_actor(cli, actor_id, run_input, wait_secs=90)
    rows = _load_dataset(cli, run, actor_id)
    reviews = []
    for r in rows:
        if r.get("recordType") == "summary":
            continue
        cmt = str(r.get("comment") or "").strip()
        if cmt:
            reviews.append({"star": int(to_num(r.get("ratingStar"), 0)), "comment": cmt[:250]})
    if not reviews:
        if any(r.get("recordType") == "summary" for r in rows):
            raise RuntimeError("Actor chỉ trả bản tóm tắt, không có bình luận: nhiều khả năng Shopee đã chặn luồng review (IP datacenter). Thử đặt APIFY_REVIEWS_PROXY_GROUP=RESIDENTIAL.")
        raise RuntimeError("Actor chạy xong nhưng không có bình luận nào.")
    return reviews

def fetch_apify_reviews(token, actor_id, product_url, max_reviews=20):
    """Giai đoạn 2: cào bình luận. Trả về (reviews, lỗi hoặc None)."""
    if not token:
        return [], "Chưa có Apify token."
    if not product_url or "-i." not in product_url:
        return [], "Không dựng được URL sản phẩm dạng -i.<shopId>.<itemId>."
    try:
        return _fetch_reviews_cached(token, actor_id, product_url, max_reviews), None
    except Exception as e:
        return [], f"{type(e).__name__}: {e}"

def fetch_mock(keyword, brand):
    """Dữ liệu mô phỏng dự phòng (CHỈ để demo giao diện)."""
    rng = random.Random(int(hashlib.md5(keyword.lower().encode()).hexdigest(), 16) % 2**32)
    b = (brand or "Chính Hãng").title()
    spec = [
        (f"{b} Official Store", True, 1.05, 4.9, 15000, 20, True, True),
        (f"{b} Flagship Store", True, 1.0, 4.8, 8000, 15, False, True),
        ("Thế Giới Phụ Kiện Uy Tín", False, 0.88, 4.7, 4500, 25, True, True),
        ("Kho Sỉ Công Nghệ Hà Nội", False, 0.75, 4.5, 1200, 10, False, False),
        ("Săn Sale Xả Kho 247", False, 0.32, 3.8, 25, 70, True, False),  # cố tình tạo shop giá ảo để test cờ cảnh báo
    ]
    base = 450_000
    items = []
    for pos, (s, off, f, r, n, disc, is_fl, is_free) in enumerate(spec, 1):
        p = int(round(base * f * rng.uniform(0.96, 1.04) / 1000) * 1000)
        orig = int(round(p / (1 - disc / 100) / 1000) * 1000)
        items.append({
            "shop": s, "shop_type": "Official (đoán theo tên)" if off else "Thường",
            "title": f"{keyword} ({b})", "price": p, "orig_price": orig, "discount_pct": disc, "final": p,
            "is_flash": is_fl, "has_freeship": is_free, "labels": [],
            "promo_tag": f"⚡ Flash Sale (-{disc}%)" if is_fl else f"Giảm {disc}%",
            "freeship_tag": "🟢 Freeship" if is_free else "—",
            "location": "Hà Nội", "rating": r, "rating_count": n, "shop_rating": None,
            "sold": None, "position": pos, "url": "https://shopee.vn", "review_url": "",
            "flag": "", "source": "Dữ liệu Mô Phỏng",
        })
    return items

MOCK_REVIEWS = [
    {"star": 5, "comment": "[MÔ PHỎNG] Giao hàng nhanh, đóng gói kỹ, hàng đúng mô tả."},
    {"star": 4, "comment": "[MÔ PHỎNG] Chất lượng ổn trong tầm giá."},
    {"star": 2, "comment": "[MÔ PHỎNG] Hộp hơi móp do vận chuyển, shop trả lời chậm."},
]

def filter_relevant(items, keyword, brand):
    """Loại kết quả lạc đề (vd tìm Marshall nhưng ra JBL): hãng phải có trong tên
    và ít nhất 50% từ khóa đặc trưng xuất hiện trong tên sản phẩm."""
    generic = {"tai", "nghe", "loa", "điện", "thoại", "cho", "và", "the", "pro"}
    def norm(s):
        return re.sub(r"[^\w\s]", " ", str(s).lower())
    brand_n = norm(brand).strip() if brand and brand.lower() not in ("đa dạng", "chính hãng") else ""
    brand_toks = set(brand_n.split())
    toks = [t for t in norm(keyword).split() if len(t) >= 2 and t not in generic and t not in brand_toks]
    accessory = ("ốp", "case", "vỏ bảo vệ", "miếng dán", "dây sạc", "đệm tai", "túi đựng", "bao đựng", "phụ kiện", "mút tai")
    kw_low = norm(keyword)
    kept = []
    for p in items:
        title = norm(p["title"])
        if brand_n and brand_n not in title:
            continue
        if any(a in title and a not in kw_low for a in accessory):
            continue
        if toks and sum(t in title.split() for t in toks) / len(toks) < 0.5:
            continue
        kept.append(p)
    return kept, len(items) - len(kept)

def prepare_and_flag(items):
    """Gắn cờ giá bất thường: thấp hơn 35% trung vị và ít đánh giá."""
    if len(items) >= 4:
        prices = sorted(i["price"] for i in items if i["price"] > 0)
        med = prices[len(prices) // 2]
        for i in items:
            if i["price"] < 0.35 * med and (i["rating_count"] or 0) < 50:
                i["flag"] = "⚠️ Giá thấp bất thường so với thị trường, ít đánh giá (nguy cơ hàng giả/treo đầu dê)"
    return items

def rank_items(items, mode):
    def legit_score(p):
        r = p["rating"] or 0
        cnt = p["rating_count"] or 0
        shop_bonus = 0.3 * ((p["shop_rating"] or 0) / 5)
        off_bonus = 0.5 if p["shop_type"].startswith("Official") else 0
        return r + 0.3 * min(math.log10(cnt + 1), 3) + shop_bonus + off_bonus - (2.0 if p["flag"] else 0)

    if mode == "price":
        return sorted(items, key=lambda p: (bool(p["flag"]), p["final"]))
    if mode == "sales":
        # Actor đã xếp theo "bán chạy" của Shopee (sortBy=sales); giữ thứ tự position
        return sorted(items, key=lambda p: (bool(p["flag"]), p["position"]))
    if mode == "flash":
        return sorted(items, key=lambda p: (not p["is_flash"], bool(p["flag"]), p["price"]))
    return sorted(items, key=lambda p: -legit_score(p))

SORT_TO_ACTOR = {"legit": "relevancy", "price": "price_asc", "sales": "sales", "flash": "relevancy"}


# ───────────────────────── 5. Gemini AI Engine ─────────────────────────
def identify_product(client, image, text_query):
    """Gemini Vision: nhận diện thực thể sản phẩm từ ảnh và mô tả."""
    prompt = """Bạn là Chuyên gia bóc tách sản phẩm E-commerce của Shopee.
Phân tích ảnh và/hoặc mô tả của người dùng, trả về DUY NHẤT một chuỗi JSON chuẩn:
{
  "name": "Tên thương mại đầy đủ",
  "brand": "Thương hiệu",
  "keyword": "Từ khóa tìm kiếm tối ưu trên Shopee (3-6 từ)"
}"""
    contents = []
    if image is not None:
        contents.append(image)
    if text_query:
        contents.append(f"Mô tả của người dùng: {text_query}")
    contents.append(prompt)

    res = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=contents,
        config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.1)
    )
    return json.loads(re.sub(r"```json|```", "", res.text).strip())

def generate_verdict_with_reviews(client, product_info, top_shop, ranked_list, reviews, is_mock, reviews_note):
    """Phân tích deal và bóc tách đánh giá người mua bằng Gemini."""
    if reviews:
        reviews_formatted = "\n".join(f"- [{r['star'] or '?'}⭐]: {r['comment']}" for r in reviews)
        review_rule = ""
    else:
        reviews_formatted = "(KHÔNG có bình luận nào được thu thập.)"
        review_rule = "\n- Vì KHÔNG có bình luận, mục 2 chỉ ghi rõ là chưa có dữ liệu bình luận để phân tích. TUYỆT ĐỐI không bịa nội dung khen/chê."

    prices = sorted(p["price"] for p in ranked_list)
    market = "\n".join(
        f"- {p['shop']} | {vnd(p['price'])} | {p['rating'] or 'chưa có'}⭐ ({p['rating_count'] or 0} đánh giá)"
        f"{' | ' + p['flag'] if p['flag'] else ''}"
        for p in ranked_list[:8]
    )

    prompt = f"""Bạn là Trợ lý Mua sắm Cấp cao của Shopee Việt Nam. Hãy đưa ra nhận định sắc sảo, khách quan, định dạng Markdown.
Sản phẩm: {product_info.get('name')}
{'[LƯU Ý: ĐANG SỬ DỤNG DỮ LIỆU MÔ PHỎNG]' if is_mock else '[DỮ LIỆU THẬT THU THẬP TỪ SHOPEE]'}

GIỚI HẠN DỮ LIỆU (phải tôn trọng): không có số lượt bán, không có thông tin voucher, không có huy hiệu Mall/Yêu thích chính thức.
Chỉ dùng đúng các con số bên dưới, không suy diễn thêm.

SHOP ĐƯỢC ĐỀ XUẤT:
- Tên shop: {top_shop['shop']} ({top_shop['shop_type']})
- Giá bán: {vnd(top_shop['price'])} | Giá gốc: {vnd(top_shop['orig_price'])}
- Khuyến mãi: {top_shop['promo_tag']} | Nhãn Shopee: {', '.join(top_shop['labels']) or 'không có'}
- Điểm sao sản phẩm: {top_shop['rating'] or 'chưa có'}⭐ ({top_shop['rating_count'] or 0} đánh giá) | Điểm shop: {top_shop['shop_rating'] or 'chưa có'}
- Cảnh báo: {top_shop['flag'] or 'không'}

MẶT BẰNG GIÁ ({len(prices)} shop): thấp nhất {vnd(prices[0])}, trung vị {vnd(prices[len(prices)//2])}, cao nhất {vnd(prices[-1])}
{market}

BÌNH LUẬN NGƯỜI MUA ({reviews_note or 'thu thập thành công'}):
{reviews_formatted}

NHIỆM VỤ:
### 1. 📊 Phân tích Deal & Lý do Chọn Shop Này
- So sánh mức giá của shop đề xuất với mặt bằng giá ở trên.
- Nhận xét độ an toàn dựa vào số đánh giá, điểm shop và cờ cảnh báo (nếu có).

### 2. 💬 Bóc tách Bình luận Người mua (Buyer Sentiment)
- 👍 **Điểm khen nhiều nhất**
- 👎 **Điểm phàn nàn / Rủi ro cần lưu ý**{review_rule}

### 3. 🎯 Lời khuyên Chốt đơn (Smart Verdict)
- Nên mua ngay hay chờ Flash Sale / Siêu Sale (11.11, 12.12)?
- Nhắc quy tắc đồng kiểm và quay video mở hộp."""

    res = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[prompt],
        config=types.GenerateContentConfig(temperature=0.2)
    )
    return res.text


class GeminiClient:
    """Dùng khóa Gemini bất kể định dạng (AIza... hay AQ....). Nếu bị 401 thì tự thử chế độ còn lại
    (Gemini API <-> Vertex express) và nhớ chế độ chạy được."""
    def __init__(self, key):
        self.key = key
        self.modes = [True, False] if GEMINI_USE_VERTEX else [False, True]
        self._clients = {}
        self.models = self  # để gọi được client.models.generate_content(...)

    def _client(self, vertex):
        if vertex not in self._clients:
            self._clients[vertex] = (genai.Client(vertexai=True, api_key=self.key) if vertex
                                     else genai.Client(api_key=self.key))
        return self._clients[vertex]

    def generate_content(self, **kwargs):
        first_error = None
        for vertex in list(self.modes):
            try:
                res = self._client(vertex).models.generate_content(**kwargs)
                self.modes = [vertex] + [m for m in self.modes if m != vertex]
                return res
            except Exception as e:
                first_error = first_error or e
                s = str(e)
                if not ("401" in s or "UNAUTHENTICATED" in s or "ACCESS_TOKEN" in s):
                    raise
        raise first_error


# ───────────────────────── 6. Sidebar Điều khiển ─────────────────────────
with st.sidebar:
    st.header("⚙️ Cấu hình Hệ thống")
    def _mask(k):
        k = (k or "").strip().strip("\"'")
        return f"{k[:4]}…{k[-4:]}" if len(k) > 8 else "(quá ngắn)"

    # Có khóa trong .env/secrets thì tự dùng, không hiện ô nhập; thiếu mới hiện ô
    if GEMINI_KEY:
        st.caption(f"✅ Gemini key từ cấu hình: `{_mask(GEMINI_KEY)}`")
    else:
        GEMINI_KEY = st.text_input("Gemini API Key:", type="password")
    if APIFY_TOKEN:
        st.caption(f"✅ Apify token từ cấu hình: `{_mask(APIFY_TOKEN)}`")
    else:
        APIFY_TOKEN = st.text_input("Apify API Token (Scraper):", type="password")

    st.divider()
    sort_choice = st.selectbox(
        "🎯 Tiêu chí ưu tiên chọn shop:",
        [
            ("🌟 Uy tín nhất (đánh giá cao, nhiều review)", "legit"),
            ("💰 Giá rẻ nhất (Tối ưu túi tiền)", "price"),
            ("🔥 Bán chạy nhất (theo xếp hạng của Shopee)", "sales"),
            ("⚡ Đang có Flash Sale", "flash")
        ],
        format_func=lambda x: x[0]
    )[1]

    allow_mock = st.checkbox("Cho phép dùng Dữ liệu Mô phỏng (nếu Apify lỗi)", value=True)
    show_debug = st.checkbox("Hiện thông tin gỡ lỗi Apify", value=True)
    st.caption(f"Search: `{ACTOR_SEARCH}`\n\nReviews: `{ACTOR_REVIEWS}`")
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

    GEMINI_KEY = GEMINI_KEY.strip().strip("\"'")
    gemini_client = GeminiClient(GEMINI_KEY)  # nhận mọi định dạng khóa, tự thử lại nếu 401

    # BƯỚC 1: Xử lý link & Nhận diện sản phẩm
    cleaned_text = extract_product_name_from_url(text_query)
    with st.spinner("🤖 AI đang nhận diện sản phẩm & chuẩn hóa từ khóa..."):
        try:
            prod_info = identify_product(gemini_client, image_input, cleaned_text)
        except Exception as e:
            st.warning(f"Gemini không nhận diện được sản phẩm, dùng nguyên văn đầu vào. Chi tiết: {str(e)[:300]}")
            prod_info = {"name": cleaned_text[:80], "brand": "", "keyword": cleaned_text[:60]}

    keyword = prod_info.get("keyword") or prod_info.get("name")
    if not keyword:
        st.error("Không xác định được từ khóa tìm kiếm. Hãy nhập tên sản phẩm cụ thể hơn.")
        st.stop()
    st.subheader(f"📦 Sản phẩm: {prod_info.get('name')} | Hãng: {prod_info.get('brand') or 'Đa dạng'}")
    st.caption(f"Từ khóa tìm kiếm: `{keyword}`")

    # BƯỚC 2: Quét thị trường Shopee (Giai đoạn 1)
    items, is_mock, meta = [], False, None
    if APIFY_TOKEN:
        with st.spinner(f"🛒 Apify đang quét các shop bán '{keyword}' trên Shopee Việt Nam..."):
            try:
                items, meta = fetch_apify_search(APIFY_TOKEN, ACTOR_SEARCH, keyword, SORT_TO_ACTOR[sort_choice])
            except Exception as e:
                st.warning(f"Không lấy được dữ liệu thật từ Apify: {type(e).__name__}: {e}")
    else:
        st.warning("Chưa có Apify token nên không thể quét dữ liệu thật.")

    if not items:
        if allow_mock:
            items = fetch_mock(keyword, prod_info.get("brand"))
            is_mock = True
            st.info("ℹ️ Đang hiển thị **Dữ liệu Mô phỏng** để bạn trải nghiệm luồng giao diện (không phải giá thật).")
        else:
            st.error("Không thể lấy dữ liệu thật từ Shopee và chế độ mô phỏng đang tắt.")
            st.stop()

    if show_debug and meta:
        with st.expander("🔧 Thông tin gỡ lỗi Apify"):
            st.write(f"Run ID: `{meta['run_id']}` · Số dòng thô: {meta['raw_count']} · Sản phẩm hợp lệ: {len(items)}")
            if meta["non_product_rows"]:
                st.write("Các dòng không phải sản phẩm (error/notice):")
                st.json(meta["non_product_rows"])
            st.write("Dòng thô đầu tiên:")
            st.json(meta["sample"])

    # Lọc kết quả lạc đề (chỉ với dữ liệu thật)
    if not is_mock:
        kept, dropped = filter_relevant(items, keyword, prod_info.get("brand"))
        if len(kept) >= 3:
            items = kept
            if dropped:
                st.caption(f"Đã loại {dropped} kết quả không khớp tên sản phẩm/hãng, còn {len(kept)} shop.")
        else:
            st.warning(f"Chỉ {len(kept)} kết quả khớp đúng sản phẩm nên giữ nguyên toàn bộ {len(items)} kết quả. Hãy kiểm tra lại cột Shop/tên trước khi mua.")

    # Xếp hạng & hiển thị bảng
    ranked_items = rank_items(prepare_and_flag(items), sort_choice)
    top_deal = ranked_items[0]

    if sort_choice == "flash" and not any(p["is_flash"] for p in ranked_items):
        st.info("Không shop nào được gắn nhãn Flash Sale trong dữ liệu; danh sách xếp theo giá thấp nhất.")

    df_display = pd.DataFrame([{
        "#": i,
        "Shop": p["shop"],
        "Loại shop": p["shop_type"],
        "Khuyến mãi": p["promo_tag"],
        "Freeship": p["freeship_tag"],
        "Giá gốc": vnd(p["orig_price"]),
        "Giá bán": vnd(p["price"]),
        "Đánh giá": (f"{p['rating']} ⭐ ({p['rating_count']:,})".replace(",", ".") if p["rating"] and p["rating_count"]
                     else (f"{p['rating']} ⭐" if p["rating"] else "Chưa có")),
        "Điểm shop": p["shop_rating"] if p["shop_rating"] else "—",
        "Nơi gửi": p["location"] or "—",
        "Cảnh báo": p["flag"] if p["flag"] else "Không có",
        "Link": p["url"],
    } for i, p in enumerate(ranked_items[:8], 1)])

    st.dataframe(
        df_display,
        use_container_width=True,
        hide_index=True,
        column_config={"Link": st.column_config.LinkColumn("Shopee Link", display_text="Xem shop")}
    )
    if not is_mock:
        st.caption("Nguồn: Apify · Shopee không công khai lượt bán và voucher cho khách chưa đăng nhập nên các cột này không có.")

    st.success(f"🏆 **Shop đề xuất:** {top_deal['shop']} ({top_deal['shop_type']}) | Giá bán: **{vnd(top_deal['final'])}** | Ưu đãi: **{top_deal['promo_tag']}**")

    # BƯỚC 3: Cào Review thực tế (Giai đoạn 2)
    reviews, reviews_note = [], None
    if is_mock:
        reviews, reviews_note = MOCK_REVIEWS, "bình luận MÔ PHỎNG"
    else:
        with st.spinner(f"🕵️ Đang cào bình luận người mua của shop: {top_deal['shop']}..."):
            reviews, err = fetch_apify_reviews(APIFY_TOKEN, ACTOR_REVIEWS, top_deal["review_url"], max_reviews=20)
        if err:
            reviews_note = "không thu thập được"
            st.warning(
                f"Không lấy được bình luận ({err[:300]}). "
                "Báo cáo bên dưới sẽ KHÔNG có phần phân tích bình luận."
            )

    # BƯỚC 4: Gemini tổng hợp báo cáo chuyên sâu
    with st.spinner("🤖 AI đang phân tích ưu/nhược điểm và đánh giá rủi ro..."):
        try:
            analysis_markdown = generate_verdict_with_reviews(
                gemini_client, prod_info, top_deal, ranked_items, reviews, is_mock, reviews_note
            )
            st.markdown(analysis_markdown)
        except Exception as e:
            st.error(f"Gemini không tạo được báo cáo: {type(e).__name__}: {str(e)[:300]}")
