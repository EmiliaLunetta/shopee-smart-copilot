# 🛍️ Shopee Lens AI: Multimodal Decision & Price Optimization Engine
> **Proof of Concept (PoC) | Strategic Product Initiative for Sea GMAP 2027 (Shopee & Monee Track)**
> 🔗 **Live Demo Web App:** [https://your-app-name.streamlit.app](https://your-app-name.streamlit.app)

> *Transforming external discovery hype into frictionless, high-conversion transactions.*

---

## 1. Executive Summary & Market Context
The Southeast Asian e-commerce landscape is witnessing a fierce rivalry between traditional search-based marketplaces and entertainment-driven social commerce. 

While **TikTok Shop** has rapidly expanded through algorithmic content discovery and impulse buying, empirical market studies (e.g., *Koswara, 2025*) reveal a critical structural behavior:
* **The 52% "Showrooming" Phenomenon:** **52% of Gen Z consumers** discover viral lifestyle and fashion items on short-form video platforms (TikTok/Instagram), but cross-check prices on **Shopee** before executing the actual purchase.
* **The Operational Divide:** Despite TikTok's top-of-funnel attention dominance, it suffers from a **2.6x higher return rate** and **77% slower delivery turnaround** compared to Shopee’s proprietary logistics network (**Shopee Xpress - SPX**).

However, Shopee faces a massive **drop-off rate at the bottom of the funnel**: consumers arriving from TikTok often abandon their carts due to extreme search friction and choice overload. 

**Shopee Lens AI** was engineered to eliminate this friction—converting external browsing intent into immediate, confident checkouts.

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

## 4. 📊 Strategic Business Impact for Shopee (The GMAP Lens)

| Core Metric | Problem Before Shopee Lens AI | Impact Delivered by Shopee Lens AI |
| :--- | :--- | :--- |
| **Conversion Rate (CVR)** | Users abandon carts after 15+ mins of manual comparison | **Slashes Time-to-Purchase to < 10 seconds**, directly capturing the 52% showrooming traffic |
| **Return & Refund Rate (RRR)** | Impulse buyers receive subpar items from untrusted sellers | **Proactive risk flags & honest sentiment summaries** prevent purchases from deceptive merchants |
| **Unit Economics & Margins** | Heavy voucher spend without clear differentiation | **Guides users toward high-margin, SPX-fulfilled Mall/Preferred sellers**, optimizing net contribution margin |
| **User Retention & Trust** | Review fatigue erodes buyer confidence | Establishes Shopee as the **most transparent, intelligent e-commerce ecosystem** in ASEAN |

---

## 5. Technical Architecture Summary
* **Frontend Interface:** Streamlit (Responsive web interface optimized for rapid prototyping)
* **Vision & NLP Backbone:** Google Gemini API (Multimodal entity recognition & zero-shot sentiment parsing)
* **Data Ingestion:** Apify Shopee Scraper actor integration paired with local fallback heuristics
* **Promotion Rule Engine:** Custom-built Python logic simulating real-time Shopee voucher stacking and discount caps# 🛍️ Shopee Lens AI: Multimodal Smart Shopping Assistant

## 🛠️ Tech Stack
- **Frontend / Deployment:** Streamlit Community Cloud, Python
- **AI Engine:** Google Gemini API (Multimodal Vision & NLP)
- **Data Architecture:** REST APIs, Python-dotenv, Pillow

