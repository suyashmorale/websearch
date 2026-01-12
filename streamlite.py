import streamlit as st
from openai import OpenAI
from typing import Dict, Any
import logging
from firecrawl import Firecrawl
import requests

# OpenAI web search function
def agent_websearch(user_question: str) -> Dict[str, Any]:
    """Performs web search based on the user's query and returns a comprehensive answer with sources."""
    tools = [
        {"type": "web_search"},
    ]

    system_instructions = (
        "You are a helpful research assistant that answers questions using web search.\n\n"
        "Your process:\n"
        "1. Analyze the user's question to determine what information needs to be searched on the web\n"
        "2. Use the web_search tool to find relevant and up-to-date information\n"
        "3. Extract key information from the web search results\n"
        "4. Synthesize the information to provide a clear, accurate, and comprehensive answer\n\n"
        "Guidelines:\n"
        "- Use web_search to find current, factual information relevant to the user's query\n"
        "- Base your answer solely on the information retrieved from web search\n"
        "- If the web search doesn't provide sufficient information, indicate that in your response\n"
        "- Provide a well-structured answer that directly addresses the user's question\n"
        "- Cite sources when relevant information is found"
    )

    # Use environment variable for API key, fallback to hardcoded for local testing
    try:
        api_key = st.secrets.get("OPENAI_API_KEY")
    except:
        return "no key"
    if not api_key:
        logging.warning("OPENAI_API_KEY not found in environment variables")
        return {
            "answer": "Error: API key not found. Please configure your OpenAI API key.",
            "sources": [],
            "search_queries": [],
            "web_search_count": 0,
            "usage": {}
        }
    
    client = OpenAI(api_key=api_key)

    try:  
        response = client.responses.create(
            model="gpt-5",
            input=[
                {
                    "role": "system",
                    "content": [{"type": "input_text", "text": system_instructions}],
                },
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": user_question}],
                },
            ],
            tools=tools,
            tool_choice="auto",
            max_tool_calls=5,
            parallel_tool_calls=False,
        )

        # Extract the answer text and sources from the response
        answer = ""
        sources = []
        search_queries = []
        web_search_count = 0
        
        # Parse the output items
        for item in response.output:
            # Extract text from ResponseOutputMessage
            if hasattr(item, 'type') and item.type == 'message':
                if hasattr(item, 'content'):
                    for content_item in item.content:
                        if hasattr(content_item, 'type') and content_item.type == 'output_text':
                            answer = content_item.text
                            
                            # Extract URL citations from annotations
                            if hasattr(content_item, 'annotations'):
                                for annotation in content_item.annotations:
                                    if hasattr(annotation, 'type') and annotation.type == 'url_citation':
                                        sources.append({
                                            'url': annotation.url,
                                            'title': annotation.title
                                        })
            
            # Extract search queries from web search calls
            if hasattr(item, 'type') and item.type == 'web_search_call':
                web_search_count += 1
                if hasattr(item, 'action') and hasattr(item.action, 'queries'):
                    search_queries.extend(item.action.queries)
        
        # Extract usage information
        usage_info = {}
        if hasattr(response, 'usage'):
            usage_info = {
                'input_tokens': response.usage.input_tokens if hasattr(response.usage, 'input_tokens') else 0,
                'output_tokens': response.usage.output_tokens if hasattr(response.usage, 'output_tokens') else 0,
                'total_tokens': response.usage.total_tokens if hasattr(response.usage, 'total_tokens') else 0,
            }
        
        return {
            "answer": answer,
            "sources": sources,
            "search_queries": search_queries,
            # "web_search_count": web_search_count,
            # "usage": usage_info
        }
    except Exception as e:
        error_msg = f"Error during web search: {str(e)}"
        logging.error(error_msg)
        return {
            "answer": error_msg,
            "sources": [],
            "search_queries": [],
            "web_search_count": 0,
            "usage": {}
        }


# Firecrawl web search function
def firecrawl_websearch(user_question: str) -> str:
    """Performs web search using Firecrawl and returns formatted results."""
    try:
        # Use environment variable for API key, fallback to hardcoded for local testing
        try:
            api_key = st.secrets.get("FIRECRAWL_API_KEY")
        except:
            return "no key"
        firecrawl = Firecrawl(api_key=api_key)
        results = firecrawl.search(
            query=user_question,
            limit=3,
            scrape_options={"formats": ["markdown", "links"]}  # Adds full markdown content
        )

        # Access scraped content
        web_results = results.web if results.web else []
        
        # Format the results for display
        if not web_results:
            return "No results found for your query."
        
        context = "\n\n".join(
            f"TITLE: {r.metadata.title if r.metadata and r.metadata.title else 'N/A'}\n"
            f"URL: {r.metadata.source_url if r.metadata and r.metadata.source_url else (r.metadata.url if r.metadata and r.metadata.url else 'N/A')}\n"
            f"MARKDOWN: {r.markdown if r.markdown else 'No content'}..."
            for r in web_results if hasattr(r, 'markdown')
        )
        
        return context if context else "No results found."
        
    except requests.exceptions.ConnectionError as e:
        return f"Connection Error: Unable to connect to Firecrawl API.\nThis could be due to:\n  - No internet connection\n  - DNS resolution failure\n  - Firewall or proxy blocking the connection\n\nOriginal error: {str(e)}"
    except Exception as e:
        return f"Error occurred while searching: {type(e).__name__}\nDetails: {str(e)}"



# Streamlit App
st.set_page_config(page_title="Web Search App", page_icon="🔍", layout="wide")

st.title("🔍 Web Search Application")
st.markdown("---")

# Sidebar for search provider selection
st.sidebar.header("Configuration")
search_provider = st.sidebar.radio(
    "Choose Search Provider:",
    ["OpenAI", "Firecrawl"],
    help="Select which search engine to use for your query"
)

# Main content area
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("📝 Enter Your Query")
    user_query = st.text_area(
        "Query:",
        height=150,
        placeholder="Enter your search query here...",
        help="Type your question or search query"
    )
    
    search_button = st.button("🔍 Search", type="primary", use_container_width=True)

with col2:
    st.subheader("📄 Results")
    
    if search_button and user_query:
        with st.spinner(f"Searching using {search_provider}..."):
            if search_provider == "OpenAI":
                result = agent_websearch(user_query)
                # Format the result as a string
                result_text = f"Answer:\n{result.get('answer', 'No answer available')}\n\n"
                if result.get('sources'):
                    result_text += "Sources:\n"
                    for source in result['sources']:
                        result_text += f"- {source.get('title', 'N/A')}: {source.get('url', 'N/A')}\n"
                if result.get('search_queries'):
                    result_text += f"\nSearch Queries Used: {', '.join(result['search_queries'])}\n"
                if result.get('usage'):
                    result_text += f"\nToken Usage: {result['usage']}"
            else:  # Firecrawl
                result_text = firecrawl_websearch(user_query)
            
            st.text_area(
                "Result:",
                value=result_text,
                height=400,
                disabled=False,
                key="result_display"
            )
    elif search_button and not user_query:
        st.warning("⚠️ Please enter a query before searching.")
    else:
        st.text_area(
            "Result:",
            value="Results will appear here after you enter a query and click Search...",
            height=400,
            disabled=True,
            key="result_placeholder"
        )

st.markdown("---")
st.caption("Select a search provider from the sidebar and enter your query to get started.")
