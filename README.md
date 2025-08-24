# Corporate News Article Extraction Pipeline

An intelligent system for automatically discovering and extracting structured content from corporate press releases. This repository contains the data collection components of a larger machine learning pipeline that uses market reactions as ground truth labels for training financial news analysis models.

## Overview

This system addresses the challenge of systematically collecting and processing corporate news data at scale. Rather than relying on expensive human labeling, the complete pipeline leverages actual market movements as the ultimate validation of news impact.

## What's Included

### 1. News URL Discovery (`news_url_extractor.py`)
- **Input**: Corporate press release page URLs
- **Output**: Individual news article URLs
- **Features**:
  - Handles diverse website architectures across thousands of companies
  - Multi-modal pagination (year selectors, load more buttons, numbered pages)
  - Advanced anti-detection web scraping
  - Intelligent link classification to separate news from boilerplate

### 2. Article Content Extraction (`article_content_extractor.py`)
- **Input**: Individual news article URLs
- **Output**: Clean HTML with labeled content sections
- **Features**:
  - Multi-method title and date detection (meta tags, schema.org, text patterns)
  - Intelligent boilerplate filtering (removes "Forward Looking Statements", "About Us")
  - Table structure preservation with proper labeling
  - Sequential text node wrapping for precise content control

## Pipeline Architecture
Russell 2000 Companies → Press Release URLs → Individual Article URLs → Clean Article Content → [Proprietary ML Pipeline]

### Complete System Workflow

1. **Data Discovery**: Identify press release pages for publicly traded companies
2. **URL Extraction**: Extract individual news article URLs (this repository)
3. **Content Extraction**: Clean and structure article content (this repository)
4. **Market Data Integration**: Calculate abnormal returns using WRDS API (proprietary)
5. **ML Training**: Fine-tune language models using market reactions as labels (proprietary)

## Key Innovation

The system uses **market reactions as ground truth labels** rather than expensive human annotation. This approach:
- Eliminates subjective human bias in labeling
- Scales infinitely across all publicly traded companies
- Provides the ultimate validation (market aggregate wisdom)
- Enables training of models that understand actual financial impact

## Technical Highlights

- **Domain-specific expertise**: Handles financial boilerplate and legal disclaimers
- **Robust pagination**: Works across diverse corporate website architectures
- **Scale-oriented design**: Processes thousands of companies systematically
- **Anti-detection capabilities**: Bypasses bot protection for reliable data collection

## Installation

```bash
pip install -r requirements.txt

from news_url_extractor import NewsGroupFinder
from article_content_extractor import ArticleExtractor

# Step 1: Discover article URLs
finder = NewsGroupFinder("https://news.company.com/")
news_groups = finder.find_all_news_groups()
article_urls = []
for group in news_groups:
    article_urls.extend(group['urls'].iloc[0])

# Step 2: Extract clean content
extractor = ArticleExtractor()
for url in article_urls:
    soup = extractor.extract_article(url)
    # Process structured content...

## Proprietary Components

The complete pipeline includes additional proprietary components:

- **Market Data Integration**: WRDS API integration for calculating abnormal returns
- **ML Training Pipeline**: Custom reinforcement learning implementation using market reactions as reward signals
- **Entity Anonymization**: Sophisticated company name redaction to prevent model memorization
- **Model Architecture**: Fine-tuned language models for financial news analysis

These components remain proprietary due to their commercial value and novel methodologies.

## Applications

- **Quantitative Finance**: Systematic news analysis for trading strategies
- **Risk Management**: Automated monitoring of corporate developments
- **Research**: Academic studies on news impact and market efficiency
- **International Expansion**: Language-agnostic analysis for global markets

## Contact

For questions about the complete pipeline or potential collaboration, please contact the repository owner.

## License

This repository is licensed under MIT License. The proprietary ML training components are not included and remain under separate commercial licensing.
