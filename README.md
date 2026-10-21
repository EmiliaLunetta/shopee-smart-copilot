# 🛍️ Shopee Copilot

**From a product photo to a trustworthy Shopee deal, in one screen.**

Proof of concept built for **Sea GMAP 2027 (Shopee & Monee track)**.
🔗 **Live demo:** https://shopee-smart-copilot-minhnguyet.streamlit.app/

> Independent student project. Demo for SEA GMAP 2027

![demo screenshot](docs/demo.png)
<!-- Add a screenshot or a 60-second GIF at docs/demo.png. This is the first thing a reviewer looks at. -->

---

## What it does

You upload a photo of a product you saw on TikTok or Instagram (or paste a Shopee link, or type a name). The app:

1. **Identifies the product** with Gemini Vision and returns structured JSON: name, brand and an optimised Shopee search keyword.
2. **Scans shopee.vn** through an Apify actor and collects up to 20 listings from different sellers.
3. **Cleans and flags the results**: drops off-topic listings such as cases and accessories, and flags suspiciously cheap listings.
4. **Ranks the sellers** by the priority you choose (see below).
5. **Reads buyer reviews** of the recommended listing and has Gemini write a short report: deal analysis, what buyers praise and complain about, and whether to buy now or wait for a sale.

The interface is in Vietnamese, because the target market is Shopee Vietnam.

### Ranking modes

| Mode | How it works |
|---|---|
| 🌟 Most trusted | Score = rating + 0.3 × min(log10(rating count + 1), 3) + 0.3 × (shop rating / 5) + 0.5 if the shop name suggests an official store − 2 if flagged |
| 💰 Lowest price | Sorted by list price, flagged listings pushed to the bottom |
| 🔥 Best selling | Keeps Shopee's own "sales" ordering. This is a ranking, **not** actual unit sales |
| ⚡ Flash Sale | Listings with a Flash Sale label first, then by price |

---

## How it uses AI, and where it deliberately does not trust it

Most of the engineering effort went into stopping the model from making things up.

- **Structured output for product recognition.** JSON response mode at low temperature (0.1), then parsed in code.
- **The report is grounded in collected data only.** The prompt passes in the real prices, ratings and review text and tells the model to use only those numbers.
- **Missing data is stated, not filled in.** If no review text could be collected, the prompt forces the report to say so instead of inventing praise or complaints.
- **Known data gaps are in the prompt.** The model is told that voucher, unit-sales and official-badge data are not available.
- **Simulated data is labelled.** A demo-only fallback exists for when the scraper fails. It is marked on screen, and the model is told not to give a purchase recommendation on it.
- **The low-price flag is a heuristic, not a verdict.** A listing is flagged when its price is below 35% of the median and it has fewer than 50 ratings. It is a warning, not proof of a counterfeit.
- **Failures are not cached**, so a temporary scraper error does not stick for 5 or 10 minutes.

---

## What is real and what is not

| Capability | Status |
|---|---|
| Photo / link / name → search keyword | ✅ Working (Gemini) |
| Multi-seller price comparison | ✅ Working, list prices, depends on a third-party Apify actor |
| Buyer-review summary | ⚠️ Works when Shopee does not block the review endpoint. Otherwise the app falls back to rating statistics only and says so |
| **Voucher stacking / net landing price** | ❌ **Not implemented.** Prices are list prices before vouchers and shipping |
| Per-shop unit sales | ❌ Not available to logged-out visitors |
| Mall / Preferred badge | ⚠️ Guessed from the shop name and labelled as a guess |

Full detail in [LIMITATION.md](LIMITATION.md).

<!--
## Evaluation  (uncomment after you run it and fill in real numbers)

Tested on N product photos (phones, headphones, skincare, ...), photographed or screenshotted from TikTok.

| Metric | Result |
|---|---|
| Correct product and brand identified | X / N |
| Search keyword returned relevant listings | X / N |
| Report contained a claim not supported by the data | X / N |
| Median time from upload to report | X seconds |

Failure cases I saw, and what I changed in response: ...
-->

---

## Why this problem

Content platforms are now where many Vietnamese shoppers first see a product. Industry data show how close the race has become: TikTok Shop is the second-largest e-commerce platform in Southeast Asia by GMV, and in 2025 its regional GMV (including Tokopedia) reached roughly two-thirds of Shopee's, according to Momentum Works. In Vietnam, Shopee and TikTok Shop together made up about 97% of GMV on the four biggest platforms in 2025, according to Metric.

My working hypothesis is that shoppers who arrive on Shopee after seeing a product elsewhere face three frictions:

1. **Search friction:** a text search returns many near-identical listings at very different prices.
2. **Trust friction:** it is hard to tell genuine reviews and reliable sellers from noise.
3. **Price friction:** the final price after vouchers is hard to compare across sellers.

This PoC addresses the first two. The third is on the roadmap below. These frictions are hypotheses from my own observation, not measured results. Validating them is the first step in the roadmap.

Sources: [Momentum Works via DealStreetAsia](https://www.dealstreetasia.com/stories/momentum-works-report-2025-479044) · [Metric via KrASIA](https://kr-asia.com/tiktok-shop-narrows-the-gap-with-shopee-in-southeast-asias-e-commerce-market)

---

## If this were built inside Shopee

| Step | Idea |
|---|---|
| Replace scraping | Use internal search and review services instead of third-party scrapers. This should cut latency sharply and remove the review-blocking problem (expected, not measured) |
| Real net price | Compute price after vouchers, Freeship and payment offers using real voucher rules and the user's own voucher wallet. The PoC does not attempt this because the data is not public |
| Better matching | Replace the keyword filter with product-model matching to separate near-identical variants |
| Measure it | A/B test with **conversion rate** as the primary metric and **return/refund rate** and **time to purchase** as secondary metrics. Guardrail: share of sessions where the AI report was wrong or unsupported |

---

## Tech stack

Python · Streamlit · Google Gemini API (vision and text) · Apify actors for Shopee search and reviews · pandas · Pillow

## Run it locally

Requires Python 3.10+.

```bash
git clone https://github.com/EmiliaLunetta/shopee-smart-copilot.git
cd shopee-smart-copilot
pip install -r requirements.txt
cp .env.example .env      # then add your keys
streamlit run app.py
```

Open http://localhost:8501. You can also paste the keys into the sidebar instead of using `.env`.

| Variable | Needed | Purpose |
|---|---|---|
| `GEMINI_API_KEY` | Yes | Product recognition and the report |
| `APIFY_TOKEN` | For live data | Without it the app can only use labelled simulated data |
| `GEMINI_MODEL` | No | Override the default Gemini model |
| `GEMINI_USE_VERTEX` | No | Set to `1` if your key type returns a 401 error on the standard Gemini API |
| `APIFY_ACTOR_SEARCH`, `APIFY_ACTOR_REVIEWS` | No | Swap in different Apify actors |
| `APIFY_REVIEWS_PROXY_GROUP` | No | e.g. `RESIDENTIAL`, if your Apify plan includes it |

Each scan uses your own Apify credit and Gemini quota. Never commit your `.env` file.

## Responsible use

The app reads public Shopee pages through a third-party scraper. You are responsible for following the terms of Shopee, Apify and Google. The report is generated by a language model and is for reference only, not purchase advice.
