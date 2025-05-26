# Agent Hackathon Projects
This repository contains two projects from the Google Hackathon in Oslo, May 2025:

## 1. GCP Workshop - News Analysis Tool

### Project Overview
This project is a news analysis tool that uses Google's Vertex AI (Gemini models) to search for news, analyze sentiment, check content relevance, and generate comprehensive reports on topics of interest. The tool is particularly focused on Norwegian company news analysis.

### Main Features

- **Web Search**: Uses Google Custom Search API to find relevant articles
- **Content Relevance Check**: Analyzes if search results are relevant to the query
- **Text Extraction**: Extracts content from web pages
- **Sentiment Analysis**: Analyzes the sentiment of articles
- **Text Summarization**: Creates concise summaries of article content
- **Report Generation**: Synthesizes information from multiple sources into a comprehensive report
- **Web Interface**: Provides a browser-based UI for interacting with the tool

### Technical Components

#### Core Functionality
- **LLM Integration**: Uses Google's Vertex AI (specifically Gemini models) for text processing
- **Web Search**: Integrates with Google Custom Search API
- **Web Scraping**: Extracts text content from URLs
- **Web Interface**: Flask-based web application with real-time status updates

#### Libraries & Dependencies
- `langchain` and `langchain-google-vertexai` for LLM workflows
- `langgraph` for workflow orchestration
- `flask` for web interface
- `bs4` for web scraping
- `markdown2` for rendering reports


### Project Structure

- **graph.py**: Contains the core functions for search, analysis, and report generation
  - `relevant_content()`: Checks if text is relevant to a prompt
  - `extract_text_from_url()`: Extracts content from web pages
  - `chat_model()`: Initializes the Gemini AI model
  - `analyze_sentiment()`: Performs sentiment analysis on texts
  - `summarize_text()`: Creates concise summaries of texts
  - `google_search()`: Performs web searches using Google Custom Search API
  - `generate_report()`: Creates comprehensive reports from multiple sources

- **webview.py**: Handles the web interface functionality
  - `start_report()`: Initiates report generation
  - `index()`: Renders the main web page


