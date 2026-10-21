# 🛍️ Shopee VN Copilot: Multimodal Decision & Price Optimization Engine
> **Proof of Concept (PoC) | Strategic Product Initiative for Sea GMAP 2027 (Shopee & Monee Track)**
> 🔗 **Live Demo Web App:** [https://your-app-name.streamlit.app](https://shopee-smart-copilot-minhnguyet.streamlit.app/)

> *Transforming external discovery hype into frictionless, high-conversion transactions.*

---

## 1. Executive Summary & Market Context
The Southeast Asian e-commerce landscape is witnessing a fierce rivalry between traditional search-based marketplaces and entertainment-driven social commerce. 

While **TikTok Shop** has rapidly expanded through algorithmic content discovery and impulse buying, empirical market studies ( *Koswara, 2025*) reveal a critical structural behavior:
* **The 52% "Showrooming" Phenomenon:** **52% of Gen Z consumers** discover viral lifestyle and fashion items on short-form video platforms (TikTok/Instagram), but cross-check prices on **Shopee** before executing the actual purchase.
* **The Operational Divide:** Despite TikTok's top-of-funnel attention dominance, it suffers from a **2.6x higher return rate** and **77% slower delivery turnaround** compared to Shopee’s proprietary logistics network (**Shopee Xpress - SPX**).

However, Shopee faces a massive **drop-off rate at the bottom of the funnel**: consumers arriving from TikTok often abandon their carts due to extreme search friction and choice overload. 

**Shopee Lens AI** was engineered to eliminate this friction—converting external browsing intent into immediate, confident checkouts.
Source: Koswara, A. (2025). E-commerce rivalry in Southeast Asia: A Google Trends analysis of TikTok Shop, Shopee, and Lazada. Mingzhi International Journal of Business, 1(1), 23–34. https://doi.org/10.55927/mijb.v1i1.2
---

## 2. Problem Statement: The Three Friction Points on Shopee

### ❌ Friction 1: The "Search Matrix" & Decision Fatigue
When users transition from a TikTok video to Shopee, text-based search queries yield hundreds of identical stock photos with wide price discrepancies. Consumers spend **15–20 minutes** opening multiple tabs, manually comparing listings, verifying shop legitimacy, and calculating final costs. This cognitive overload leads to high bounce and cart-abandonment rates.

### ❌ Friction 2: Review Pollution & Sentiment Opacity
Shopee’s rating ecosystem is saturated with "incentivized" and low-intent feedback (e.g., *"Rating 5 stars for Shopee Coins"*, *"Fast delivery, haven't tested the item"*). Authentic sentiment regarding sizing discrepancies, fragile materials, or counterfeit risks is buried under thousands of superficial 5-star comments. Buyers lack actionable clarity on product defects.

### ❌ Friction 3: The "Voucher Matrix" Calculation Gap
Shopee's competitive edge lies in its deep subsidy infrastructure (Freeship Xtra, Live/Video Vouchers, Mall Vouchers, Payment discounts via Monee/SPayLater). However, calculating the actual **Net Landing Price** requires complex stacking logic that search listing APIs do not disclose. Price-sensitive shoppers often cannot determine which seller truly offers the lowest final price.

---

## 3. Product Rationale: Why Shopee Lens AI Was Born

Instead of attempting to out-entertain TikTok with unsustainable content marketing budgets, Shopee’s winning playbook lies in **Asymmetric Warfare**:

> **"Let TikTok spend millions subsidizing creators to generate initial demand; Shopee will be the ultimate, frictionless Decision & Fulfillment Engine that captures the final transaction."**

**Shopee Lens AI** operates as a smart, multimodal shopping copilot:
1. **Zero-Text Visual Retrieval:** Users upload a screenshot or photo from TikTok/Instagram. The **Gemini Multimodal Vision Engine** instantly recognizes the exact SKU, category, and specifications.
2. **Dynamic Heuristic Promotion Engine:** Automatically applies tiered platform voucher rules (Live/Video -15%, Mall -8%, Freeship Xtra) to calculate the true **Post-Voucher Net Price** across multiple sellers.
3. **Automated Sentiment Synthesis:** Ingests and parses real buyer comments using Natural Language Processing (NLP) to generate transparent **Pros, Cons, and Risk Alerts** (`⚠️ Abnormally low price / Counterfeit risk`).
4. **Actionable Buying Verdict:** Eliminates decision paralysis by delivering a clear, ranked recommendation tailored to user priorities (Best Reputation, Lowest Net Price, or Top Sales Volume).

---

## 4. Enterprise Roadmap & Strategic Value (Sea / Shopee)

This Proof of Concept is architected to transition into Shopee's internal infrastructure:

### 1. Architecture Migration (Scraper to Internal RPC)
- Replace third-party scrapers with direct gRPC connections to Shopee's internal `SearchService` and `ReviewService`.
- Reduce data retrieval latency from ~15 seconds to under 200 milliseconds.

### 2. Personalized Margin & Voucher Stacking
- Integrate with ShopeePay and SPayLater engines to compute real-time, user-specific net prices, taking into account user voucher wallets and shipping subsidies.

### 3. Core Business Metrics Impact
- **Conversion Rate (CVR):** Reduces decision paralysis by curating trustworthy listings for complex, high-consideration purchases.
- **Return & Refund Rate (RRR):** Mitigates buyer remorse and product mismatches through transparent review sentiment analysis.

---

## 5. Technical Architecture Summary
* **Frontend Interface:** Streamlit (Responsive web interface optimized for rapid prototyping)
* **Vision & NLP Backbone:** Google Gemini API (Multimodal entity recognition & zero-shot sentiment parsing)
* **Data Ingestion:** Apify Shopee Scraper actor integration paired with local fallback heuristics
* **Promotion Rule Engine:** Custom-built Python logic simulating real-time Shopee voucher stacking and discount caps

## 6. Installation & Local Setup

### Prerequisites
- Python 3.10 or higher
- Git

### Step 1: Clone the Repository
```bash
git clone https://github.com/EmiliaLunetta/shopee-smart-copilot.git
cd shopee-smart-copilot
```

## Step 2:  Install Dependencies
```bash
pip install -r requirements.txt
```

## Step 3: Configure Environment Variables
Copy the sample environment file to create .env:
```bash
cp .env.example .env
```
Populate .env with your API credentials:
```bash
# Required for vision extraction and sentiment analysis
GEMINI_API_KEY=your_gemini_api_key_here

# Required for live Shopee scraping (Optional: fallback to mock data if omitted)
APIFY_TOKEN=your_apify_token_here
```

## Step 4: Run the Application

```bash
streamlit run app.py
```
Open your browser at http://localhost:8501.
## 
