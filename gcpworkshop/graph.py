
from langchain_google_vertexai import ChatVertexAI, VertexAIImageGeneratorChat
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.graph import END, START, StateGraph
from langchain import hub
from langgraph.prebuilt import create_react_agent
import requests
import json
from bs4 import BeautifulSoup
import urllib.parse
import base64
import os
from typing import List, Dict, Any, Optional, Callable, Tuple



# Create a Vertex AI chat model instance using LangChain
def chat_model(max_tokens=1024, temperature=0.2, model_name="gemini-2.5-flash-preview-05-20"):
    # Initialize the chat model with your specific parameters
    chat = ChatVertexAI(
        model_name=model_name,
        project="PROJECTID",
        location="us-central1",
        endpoint_version="v1",
        max_output_tokens=max_tokens,  # Optional: adjust based on your needs
        temperature=temperature,         # Optional: adjust based on your needs
    )
    return chat

# Function to generate an image using Imagen API
def generate_header_image(query: str, status_callback: Optional[Callable] = None) -> Tuple[str, str]:
    """
    Generate a header image for the report using Google's Imagen API.
    
    Args:
        query: The search query to base the image on
        status_callback: Optional callback function to report status
        
    Returns:
        Tuple of (base64-encoded image, image prompt used)
    """
    if status_callback:
        status_callback(f"Generating header image for 'report'")
    
    # Construct a detailed prompt for the image based on the query
    model = chat_model(temperature=0.7)
    image_prompt_request = f"""Create an image prompt about this report: {query[:500]} that would work well for a business report header.
    The image should look professional and be related to business, or the specific company/industry/theme.
    Do not include any text in the image prompt as Imagen cannot render text.
    Keep the prompt under 200 characters. 
    Just return the prompt text and nothing else."""
    
    image_prompt_response = model.invoke([HumanMessage(content=image_prompt_request)])
    image_prompt = image_prompt_response.content.strip()
    
    if status_callback:
        status_callback(f"Created image prompt: '{image_prompt}'")
    
    try:
        image_generator = VertexAIImageGeneratorChat(
        project="genaibuilders25osl-4814",
        location="us-central1",
        model_name="imagen-4.0-generate-preview-05-20"
        )
        response = image_generator.invoke(image_prompt)
        generated_image = response.content[0]
        # Parse response object to get base64 string for image
        img_base64 = generated_image["image_url"]["url"].split(",")[-1]
        
        return img_base64, image_prompt
    
    except Exception as e:
        if status_callback:
            status_callback(f"Error generating image: {str(e)}")
        print(f"Error generating image: {str(e)}")
        return "", image_prompt


# Function to search using Google Custom Search API
def google_search(query: str, api_key: str, cx: str, num_results: int = 5) -> List[Dict[str, str]]:
    """
    Perform a Google Custom Search and return the top N results.
    
    Args:
        query: Search query string
        api_key: Google API key
        cx: Google Custom Search Engine ID
        num_results: Number of results to return
        
    Returns:
        List of dictionaries with title, link, and snippet for each result
    """
    # URL encode the query
    encoded_query = urllib.parse.quote_plus(query)
    
    # Build the API URL
    base_url = "https://customsearch.googleapis.com/customsearch/v1"
    params = {
        "key": api_key,
        "cx": cx,
        "q": encoded_query,
        "num": num_results
    }
    
    # Make the request
    response = requests.get(base_url, params=params)
    if response.status_code != 200:
        print(f"Error: API request failed with status code {response.status_code}")
        return []
    
    # Parse the response
    data = response.json()
    results = []
    
    if "items" in data:
        for item in data["items"]:
            results.append({
                "title": item.get("title", "No title"),
                "link": item.get("link", ""),
                "snippet": item.get("snippet", "No snippet")
            })
    
    return results

import requests
from typing import List, Dict

def tavily_news_search(query: str, api_key: str, num_results: int = 5, time="day", status_callback: Optional[Callable] = None) -> List[Dict[str, str]]:
    """
    Perform a Tavily search with a focus on news and return the top N results.

    Args:
        query: Search query string
        api_key: Tavily API key
        num_results: Number of results to return
        status_callback: Optional callback function to report status

    Returns:
        List of dictionaries with title, url, and content for each result
    """
    if status_callback:
        status_callback(f"Searching for news about '{query}'")
        
    url = "https://api.tavily.com/search"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "query": query,
        "time_range": time,
        "search_depth": "basic",
        "max_results": num_results,
        "include_answer": False,
        "include_images": False,
        "include_raw_content": False,
        "include_domains": ["*.no"],
        "type": "news"
    }

    response = requests.post(url, headers=headers, json=payload)
    if response.status_code != 200:
        print(f"Error: Tavily request failed with status code {response.status_code}")
        return []

    data = response.json()
    results = []

    if status_callback:
        status_callback(f"Found {len(data.get('results', []))} news articles")
        
    for result in data.get("results", []):
        results.append({
            "title": result.get("title", "No title"),
            "link": result.get("url", ""),
            "snippet": result.get("content", "No snippet")
        })

    return results

def extract_text_from_url(url: str, status_callback: Optional[Callable] = None) -> str:
    """
    Extract the main text content from a webpage.
    
    Args:
        url: URL of the webpage
        status_callback: Optional callback function to report status
        
    Returns:
        String containing the main text from the webpage
    """
    if status_callback:
        status_callback(f"Extracting content from {url}")
        
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()  # Raise an exception for HTTP errors
        
        # Parse HTML with BeautifulSoup
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.extract()
            
        # Get the text content
        text = soup.get_text(separator=' ', strip=True)
        
        # Remove extra whitespace and normalize
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = ' '.join(chunk for chunk in chunks if chunk)
        
        return text[:10000]  # Limit to first 10K characters to avoid oversized requests
    except Exception as e:
        print(f"Error extracting text from {url}: {str(e)}")
        if status_callback:
            status_callback(f"Failed to extract content from {url}: {str(e)}")
        return f"Failed to extract content from {url}: {str(e)}"

def summarize_text(model, text: str, status_callback: Optional[Callable] = None) -> str:
    """
    Use the LLM to summarize the text.
    
    Args:
        model: LLM model instance
        text: Text to summarize
        status_callback: Optional callback function to report status
        
    Returns:
        Summarized text
    """
    if not text or len(text) < 100:
        return "Insufficient content to summarize."
    
    if status_callback:
        status_callback("Summarizing article content")
        
    prompt = f"Please summarize the following text in a concise manner:\n\n{text[:7000]}"
    response = model.invoke([HumanMessage(content=prompt)])
    return response.content

def analyze_sentiment(model, text: str, status_callback: Optional[Callable] = None) -> str:
    """
    Use the LLM to analyze the sentiment of the text.
    
    Args:
        model: LLM model instance
        text: Text to analyze
        status_callback: Optional callback function to report status
        
    Returns:
        Sentiment analysis
    """
    if status_callback:
        status_callback("Analyzing sentiment of content")
        
    prompt = f"Please analyze the sentiment of the following text. Is it positive, negative, or neutral? Provide a brief explanation why:\n\n{text[:7000]}"
    response = model.invoke([HumanMessage(content=prompt)])
    return response.content

def relevant_content(model, prompt: str, text: str, title: str, status_callback: Optional[Callable] = None) -> str:
    """
    Use the LLM to determine if the text is relevant to the prompt.

    Return True or False, and nothing else.
    """
    if status_callback:
        status_callback(f"Checking relevance of article: '{title}'")
        
    prompt = f"""Please determine if the following text is relevant to the prompt.
    The prompt is asking for news about Norwegian companies, and you should verify
    that the text has some mention of the company mentioned in the prompt, and that the source is a credible news site in Norway. 
    finn.no and sites named after the company in the prompt are not credible news sites, and you should not use them as sources.
    Respond with 'True' or 'False' only.\n\nPrompt: {prompt}\n\nText: {text[:7000]}"""
    response = model.invoke([HumanMessage(content=prompt)])
    return response.content.strip()

def generate_report(model, query: str, results_data: List[Dict[str, Any]], status_callback: Optional[Callable] = None) -> str:
    """
    Generate a comprehensive report based on the search results.
    
    Args:
        model: LLM model instance
        query: Original search query
        results_data: List of dictionaries containing result information with summaries and sentiment
        status_callback: Optional callback function to report status
        
    Returns:
        Generated report text
    """
    if status_callback:
        status_callback(f"Generating comprehensive report from {len(results_data)} sources")
        
    formatted_results = "\n\n".join([
        f"SOURCE {i+1}: {result['title']}\n" +
        f"URL: {result['link']}\n" +
        # f"SUMMARY: {result['summary']}\n" +
        f"CONTENT: {result['content']}\n" +
        f"SENTIMENT: {result['sentiment']}"
        for i, result in enumerate(results_data)
    ])
    
    prompt = f"""Based on the search query "{query}", please write a comprehensive report that synthesizes 
the information from these sources: 

{formatted_results}

You will be shut down if you use sources not in the list above.

Your report should be made in Markdown format and include the following:

Provide a summary of the main findings.
Discuss the sentiment of the information.
Identify any trends or patterns.


Format the report with appropriate headings and structure.
Call sources by their title with a hyperlink to the url, and do not use the word "source" in the report.
"""
    
    if status_callback:
        status_callback("Finalizing report, adding citations and formatting")
        
    response = model.invoke([HumanMessage(content=prompt)])
    return response.content

def web_search_report(query: str, num_results: int = 5, time="day", status_callback: Optional[Callable] = None) -> Dict:
    """
    Perform a complete web search and report generation workflow.
    
    Args:
        query: Search query
        num_results: Number of search results to process
        status_callback: Optional callback function to report status updates
        
    Returns:
        Dictionary containing the report and header image
    """
    print("Starting web search report generation...")
    if status_callback:
        status_callback("Initializing report generation")

    api_key_tavily = "KEY"

    
    # Generate header image first
    
    
    # Initialize the model
    model = chat_model()
    
    # Step 1: Perform the search
    print(f"Searching for: {query}")
    search_results = tavily_news_search(query, api_key_tavily, num_results, time=time, status_callback=status_callback)

    if not search_results:
        if status_callback:
            status_callback("No results found. Please try a different query.")
        return {
            "report": "The search didn't return any results.",
        }
    
    # Step 2-4: Process each result
    results_data = []
    max_result = 5
    accepted = 0
    for i, result in enumerate(search_results):
        if accepted >= max_result:
            break
        print(f"Processing result {i+1}/{len(search_results)}: {result['title']}")
        
        # Extract text from the URL
        content = extract_text_from_url(result['link'], status_callback)
        if relevant_content(model, query, content, result['title'], status_callback) == "False":
            print(f"Skipping irrelevant content for {result['title']}")
            if status_callback:
                status_callback(f"Article '{result['title']}' determined to be irrelevant - skipping")
            continue
        # Summarize the content
        accepted += 1
        # summary = summarize_text(model, content)
        
        # Analyze sentiment
        sentiment = analyze_sentiment(model, content, status_callback)
        
        if status_callback:
            status_callback(f"Processing article {accepted}/{max_result}: '{result['title']}' complete")

        # Store all the data
        results_data.append({
            "title": result["title"],
            "link": result["link"],
            "snippet": result["snippet"],
            "content": content[:1000] + "...",  # Store just a preview
            # "summary": summary,
            "sentiment": sentiment
        })
    
    # Step 5: Generate the report
    print("Generating final report...")
    summary_model = chat_model(max_tokens=7000, temperature=0.5, model_name="gemini-2.5-pro-preview-05-06")
    report_md = generate_report(summary_model, query, results_data, status_callback)
    header_image, image_prompt = generate_header_image(report_md, status_callback)
    if status_callback:
        status_callback("Report generation complete")
    
    return {
        "report": report_md,
        "header_image": header_image,
        "image_prompt": image_prompt
    }

# Example usage
if __name__ == "__main__":
    search_query = "Rema"
    result = web_search_report(search_query, 3, time="day")
    print("\n\nFINAL REPORT:")
    print(result["report"])
    print("\nImage prompt used:", result["image_prompt"])
