# MercadoLibre Scraper and Marketing Insights Tool

A powerful Python tool for scraping MercadoLibre product data and generating comprehensive marketing insights. This tool helps businesses understand market trends, customer sentiment, and competitive positioning in the MercadoLibre marketplace.

## Features

### Data Collection
- Scrapes product listings from MercadoLibre Argentina
- Extracts detailed product information including:
  - Prices and pricing history
  - Product descriptions
  - Customer reviews
  - Sales data
  - Category information
  - Seller information

### Advanced Analysis
- **Sentiment Analysis**
  - Detailed sentiment scoring
  - Emotion detection
  - Context-specific sentiment analysis
  - Trend detection
  - Key phrase extraction

- **Marketing Insights**
  - Market positioning analysis
  - Customer segmentation
  - Competitive analysis
  - Feature analysis
  - Price analysis
  - Growth opportunities

- **Actionable Recommendations**
  - Marketing channel suggestions
  - Content strategy recommendations
  - Promotional strategy
  - Risk mitigation
  - Growth opportunities

## Requirements

```bash
pip install -r requirements.txt
```

Required packages:
- requests
- beautifulsoup4
- playwright
- textblob
- selenium
- asyncio

## Installation

1. Clone the repository:
```bash
git clone https://github.com/wald16/mercadolibre-scraper.git
cd mercadolibre-scraper
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Install Playwright browsers:
```bash
playwright install
```

## Usage

Basic usage:
```bash
python mercadolibre_scraper.py --keyword "smartphone" --pages 1
```

Advanced usage with all options:
```bash
python mercadolibre_scraper.py \
    --keyword "smartphone" \
    --pages 3 \
    --output_csv "products.csv" \
    --output_json "products.json" \
    --insights_json "marketing_insights.json" \
    --concurrency 3
```

### Command Line Arguments

- `--keyword`: Search keyword (required)
- `--pages`: Number of pages to scrape (default: 1)
- `--output_csv`: Output CSV filename (default: mercadolibre_products.csv)
- `--output_json`: Output JSON filename (default: mercadolibre_products.json)
- `--insights_json`: Marketing insights JSON filename (default: mercadolibre_insights.json)
- `--concurrency`: Number of concurrent product page scrapes (default: 3)

## Output Files

### Products Data (CSV/JSON)
- Product URLs
- Prices
- Descriptions
- Sales data
- Reviews
- Category information

### Marketing Insights (JSON)
- Price analysis
- Feature analysis
- Sentiment analysis
- Customer feedback
- Competitive analysis
- Marketing recommendations

## Marketing Insights Details

### Market Positioning
- Price position (premium/budget)
- Quality position
- Value proposition

### Customer Segments
- Primary target audience
- Secondary target audience
- Customer preferences

### Marketing Strategy
- Recommended channels
- Content strategy
- Promotional approach
- Competitive advantages

### Action Items
- Priority-based recommendations
- Risk mitigation strategies
- Growth opportunities

## Error Handling

The tool includes robust error handling for:
- Network issues
- Rate limiting
- Invalid data
- Missing information
- Scraping failures

## Rate Limiting

The tool implements smart rate limiting to:
- Avoid IP blocks
- Respect server limits
- Maintain stable performance
- Handle concurrent requests

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Disclaimer

This tool is for educational and research purposes only. Please respect MercadoLibre's terms of service and robots.txt when using this tool. 
