# LLM Text Summarizer with Streamlit

## 🚀 Overview

This Python application provides text summarization capabilities using a Large Language Model (LLM) accessed via a Cloudflare Worker proxy. It features a user-friendly web interface built with Streamlit and can handle long texts by implementing a MapReduce approach. This project was developed as a Trainee ML Engineer test task.

## ✨ Features

*   **Flexible Input:** Summarize text pasted directly or extracted from a URL.
*   **Customizable Summaries:**
    *   Choose between "Краткое саммари" (Short) or "Развернутое саммари" (Long).
    *   Select output format: "Простой текст (text)", "Markdown (markdown)", or "HTML (html)".
    *   Adjust "Уровень Креативности" (Creativity Level - Low, Medium, High) which influences the LLM's temperature.
*   **Selectable LLM Models:** Choose from a configurable list of LLM models (defined in `models.json`), including a local placeholder for testing.
*   **Handles Long Texts:** Implements a MapReduce strategy (chunking, intermediate summarization, final summarization) for texts exceeding token limits.
*   **Downloadable Results:** Download the generated summary in the chosen format (`.txt`, `.md`, `.html`).
*   **Simple UI:** Easy-to-use interface built with Streamlit.

## 🛠️ Tech Stack

*   **Python 3.x**
*   **Streamlit:** For the web interface.
*   **Requests:** For making HTTP calls to the LLM proxy (`get_summary_from_llama`).
*   **crawler4ai:** Python library for advanced web crawling and content extraction from URLs.
*   **BeautifulSoup4:** For cleaning user-inputted text (removing HTML from `st.text_area` content via `clean_user_text`).
*   **Tiktoken:** For token counting and text chunking in the MapReduce process.
*   **python-dotenv:** For managing environment variables locally via a `.env` file.
*   **LLM:** Designed to work with models like Llama 3 (e.g., 70B) via a Cloudflare Worker.
*   **Crawl4AI API:** Used for extracting main content from URLs.

## ⚙️ Setup and Running Instructions

1.  **Clone the Repository:**
    ```bash
    git clone <repository_url>
    cd <repository_directory>
    ```

2.  **Create and Activate a Virtual Environment:**
    (Recommended)
    ```bash
    python -m venv .venv
    # On Windows
    # .venv\Scripts\activate
    # On macOS/Linux
    source .venv/bin/activate
    ```

3.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure Environment Variables:**
    Create a file named `.env` in the root of the project directory. Add the following lines:

    ```env
    # For the LLM Cloudflare Worker
    PROXY_WORKER_URL="https://your-llm-proxy.workers.dev/api"
    PROXY_MASTER_KEY="your_secret_key_for_llm_proxy"

    # For Crawl4AI API (Optional)
    # CRAWL4AI_API_KEY="your_crawl4ai_api_key_if_needed"

    # USE_PLACEHOLDER_LLM (Largely Superseded by UI Model Selection via models.json)
    # This environment variable previously controlled placeholder behavior or forced a specific model.
    # Its role is now significantly reduced:
    # - If a model (including the "ЗАГЛУШКА") is selected in the UI via `models.json`,
    #   this environment variable is IGNORED for that summarization request.
    # - It might only have an effect as an ultimate fallback if `models.json` is completely missing
    #   or fails to load in such a way that the UI cannot even offer the default placeholder model
    #   (the application attempts to prevent this by always loading a default placeholder config).
    # For clarity, rely on the `models.json` configuration and UI selection for choosing models or placeholders.
    # Example (mostly for legacy or extreme fallback reference):
    # USE_PLACEHOLDER_LLM="true"
    ```
    *   `PROXY_WORKER_URL`: The URL of your Cloudflare Worker that proxies requests to the LLM.
    *   `PROXY_MASTER_KEY`: The master API key your Cloudflare Worker expects for authorization.
    *   `CRAWL4AI_API_KEY` (Optional): If your Crawl4AI endpoint (`https://crawl4ai.interfabrika.online/md`) requires an API key, provide it here. The application will include it as a Bearer token.
    *   `USE_PLACEHOLDER_LLM`: See comments above for its now limited role.

5.  **Configure Available LLM Models (`models.json`)**

    The application loads the list of available LLM models from a `models.json` file located in the root directory. This allows you to customize which models are presented to the user in the UI.

    **Structure:**
    The file should be a JSON array of objects, where each object represents a model:
    ```json
    [
      {
        "displayName": "Llama 3.3 70B Instruct (FP8)",
        "modelId": "@cf/meta/llama-3.3-70b-instruct-fp8-fast",
        "provider": "Cloudflare AI",
        "notes": "Мощная модель, быстрая версия с FP8 квантованием."
      },
      {
        "displayName": "Mistral 7B Instruct v0.1",
        "modelId": "@cf/mistral/mistral-7b-instruct-v0.1",
        "provider": "Cloudflare AI",
        "notes": "Компактная и быстрая модель."
      },
      {
        "displayName": "ЗАГЛУШКА (Тест UI)",
        "modelId": "placeholder",
        "provider": "Local",
        "notes": "Использует локальную заглушку, не делает реальный вызов LLM."
      }
    ]
    ```
    *   `displayName`: The name shown in the UI's model selection dropdown.
    *   `modelId`: The identifier passed to the LLM proxy (e.g., specific Cloudflare AI model ID). Use the special value `"placeholder"` to indicate that selecting this option should use the local dummy/placeholder summarization logic.
    *   `provider`: Informational field indicating the source of the model.
    *   `notes`: Additional information about the model.

    If `models.json` is missing, corrupted, or empty, the application will default to using a single placeholder model entry defined internally.

6.  **Run the Streamlit Application:**
    ```bash
    streamlit run app.py
    ```
    The application should now be accessible in your web browser (usually at `http://localhost:8501`).

## ☁️ Cloudflare Worker LLM Proxy

This application is designed to interact with an LLM (e.g., Llama 3) through a Cloudflare Worker. The Worker acts as a secure proxy, managing requests to the underlying LLM API.

**Key Responsibilities of the Proxy Worker:**
*   Receive summarization requests from this Streamlit application.
*   Validate the `Authorization` header using the `PROXY_MASTER_KEY`.
*   Forward the request payload (system prompt, user prompt, text, temperature) to the actual LLM API endpoint.
*   If a specific LLM model (not the 'ЗАГЛУШКА') is selected in the application's UI, its `modelId` (e.g., `@cf/meta/llama-3.3-70b-instruct-fp8-fast`) is passed to this Cloudflare Worker in the `model` field of the JSON request payload. The Worker should be configured to use this `modelId` to route the request to the corresponding backend LLM.
*   Include necessary authentication for the LLM provider (e.g., `LLAMA_API_KEY` configured as a secret in Cloudflare).
*   Return the LLM's response to the Streamlit application.

**Deployment:**
*   The `index.js` (or similar) for such a worker needs to be deployed to Cloudflare Workers.
*   **Example:** A simplified `index.js` for a Cloudflare Worker that proxies requests to Cloudflare's own Llama models might look something like [this hypothetical example gist](https://gist.github.com/anonymous/some_id_if_i_could_create_one). (Note: This link is a placeholder. You would replace this with an actual link to your worker code or a template.)
*   **Configuration:**
    *   Deploy using Wrangler CLI.
    *   Set secrets in Cloudflare dashboard:
        *   `LLAMA_API_KEY`: Your API key for the LLM provider.
        *   `WORKER_MASTER_KEY`: The key that this Streamlit app will use as `PROXY_MASTER_KEY` to authenticate with the worker. The worker should check for `Authorization: Bearer <WORKER_MASTER_KEY>`.

## 🔗 URL Content Extraction (crawler4ai Library)

For summarizing content from URLs, the application now uses the `crawler4ai` Python library. This library provides more robust and higher-quality extraction of main textual content from web pages.

Key configurations for `crawler4ai` in this application include:
*   `AsyncWebCrawler` is used for performing the asynchronous crawling operations.
*   `BrowserConfig(headless=True)` ensures that no visible browser window is opened during content extraction.
*   `CrawlerRunConfig(cache_mode=CacheMode.BYPASS)` is used to fetch fresh content on each request, bypassing any local caching by the crawler.

The library's default mechanisms for identifying and extracting the primary content (which are generally designed to be adaptive and 'fit' the main article) are utilized. The extracted content is expected in Markdown format.
This replaces the previous direct use of an external API endpoint for URL content extraction.

## 🧼 User Text Cleaning
When text is input directly by the user into the text area, it might contain unwanted HTML formatting. The application uses a function `clean_user_text` which utilizes `BeautifulSoup4` to remove these HTML tags and also normalizes excessive whitespace before summarization.

## 🧠 LLM System Prompt

The application employs a detailed system prompt specifically crafted for Llama 3 70B (or compatible models) to guide the summarization process effectively. This prompt instructs the LLM on:
*   **AI's Role:** A highly qualified AI assistant specializing in text summarization.
*   **Task Definition:** To carefully read and summarize text based on specified length and format.
*   **Parameter Interpretation:**
    *   `summary_length`: Defines "short" (2-3 key sentences) vs. "long" (1-2 detailed paragraphs).
    *   `output_format`: Specifies output as plain "text", "markdown" (using correct syntax), or "html" (using basic tags like `<p>, <h2>, <ul>, <li>`, excluding full document structure).
*   **Style & Language:** Summaries should be coherent, informative, accurate, objective, concise, and in Russian.
*   **MapReduce Context:** A distinct, very concise prompt is used for summarizing intermediate text chunks during the MapReduce process, requesting a plain text, factual summary.

This structured system prompt aims to improve the quality, relevance, and formatting accuracy of the generated summaries.

## 🧩 Handling Long Texts (MapReduce)

To manage texts that exceed the LLM's context window limit, this application implements a MapReduce strategy:

1.  **Token Counting:** The input text's token count is estimated using `tiktoken`.
2.  **Direct Summarization (if short):** If the token count is below a predefined `TOKEN_THRESHOLD`, the text is summarized directly in a single call to the LLM.
3.  **Chunking (if long):** If the text is too long:
    *   It's split into smaller, manageable chunks using an intelligent text splitter (`text_splitter_intelligent`). This splitter tries to respect paragraph and sentence boundaries.
    *   Chunks have a target token size and a small overlap to maintain context.
4.  **Map Step:** Each chunk is individually summarized by calling the LLM. These intermediate summaries are typically short and factual, in plain text.
5.  **Reduce Step:** The intermediate summaries are concatenated. This combined text is then sent to the LLM for a final summarization, using the user's original length, format, and creativity preferences.

This approach allows the application to process and summarize texts of considerable length, albeit with potentially increased processing time and cost (due to multiple LLM calls).

## 🚀 Example Usage

1.  **Launch the application:** `streamlit run app.py`.
2.  **Choose Input Method:**
    *   **Text Input Tab:** Paste your text directly into the text area.
    *   **URL Input Tab:** Enter a URL of a webpage containing the text you want to summarize.
3.  **Select Options:**
    *   **Длина Саммари (Summary Length):** "Краткое" (Short) or "Развернутое" (Long).
    *   **Формат Вывода (Output Format):** "Простой текст", "Markdown", or "HTML".
    *   **Уровень Креативности (Creativity):** "Низкий", "Средний", or "Высокий".
    *   **Выберите Модель LLM:** Select your desired LLM from the dropdown.
4.  **Generate:** Click the "Сгенерировать Саммари" button.
5.  **View & Download:** The summary will appear in the output area. If successful, a "Скачать Саммари" button will allow you to download the result.

---
*This README provides setup and operational details for the LLM Text Summarizer application.*
