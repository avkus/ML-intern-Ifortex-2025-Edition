# LLM Text Summarizer with Streamlit

## 🚀 Overview
This Python application provides text summarization capabilities using a Large Language Model (LLM) accessed via a Cloudflare Worker proxy. It features a user-friendly web interface built with Streamlit, can handle long texts using a MapReduce approach, and extracts content from URLs using the `crawler4ai` library. Users can also select their preferred LLM model from a configurable list.

## ✨ Features

*   **Flexible Input:** Summarize text pasted directly or extracted from a URL.
*   **Selectable LLM Models:** Choose from a configurable list of LLM models (defined in `models.json`), including a local placeholder for testing.
*   **Customizable Summaries:**
    *   Choose between "Краткое саммари" (Short) or "Развернутое саммари" (Long).
    *   Select output format: "Простой текст (text)", "Markdown (markdown)", or "HTML (html)".
    *   Adjust "Уровень Креативности" (Creativity Level - Low, Medium, High) which influences the LLM's temperature.
*   **Advanced URL Content Extraction:** Uses the `crawler4ai` library for high-quality main content extraction from web pages.
*   **User Text Cleaning:** Automatically cleans user-pasted text by removing HTML tags and normalizing whitespace.
*   **Handles Long Texts:** Implements a MapReduce strategy for texts exceeding token limits.
*   **Downloadable Results:** Download the generated summary in the chosen format (`.txt`, `.md`, `.html`).
*   **Simple UI:** Easy-to-use interface built with Streamlit.
*   **Dockerized:** Includes a `Dockerfile` for easy containerization and deployment.

## 🛠️ Tech Stack

*   **Python 3.x** (specifically 3.11-slim in Docker)
*   **Streamlit:** For the web interface.
*   **Requests:** For making HTTP calls to the LLM proxy.
*   **crawler4ai:** Python library for advanced web crawling and content extraction from URLs.
*   **Playwright:** Used by `crawler4ai` for browser automation (specifically Chromium).
*   **BeautifulSoup4:** For cleaning user-inputted text (removing HTML from `st.text_area` content).
*   **Tiktoken:** For token counting and text chunking.
*   **python-dotenv:** For managing environment variables locally.
*   **LLM:** Designed to work with models like Llama 3 (e.g., 70B) via a Cloudflare Worker, with model selection support.

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
    # On Windows: .venv\Scripts\activate
    # On macOS/Linux: source .venv/bin/activate
    ```

3.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Install Playwright Browser Dependencies:**
    `crawler4ai` uses Playwright for browser automation. You need to install the necessary browser binaries (Chromium is used by default in the Dockerfile):
    ```bash
    python -m playwright install --with-deps chromium
    ```

5.  **Run `crawler4ai` Setup:**
    This step performs any necessary post-installation setup for `crawler4ai`.
    ```bash
    crawl4ai-setup
    ```
    *(Optional: You can run `crawl4ai-doctor` to check if the setup was successful).*

6.  **Configure Environment Variables:**
    Create a file named `.env` in the project root. See the "Environment Variables" section below for details.

7.  **Configure LLM Models (`models.json`):**
    Create or modify the `models.json` file in the root directory. See the "Configuring Available LLM Models (`models.json`)" section below.

8.  **Run the Streamlit Application:**
    ```bash
    streamlit run app.py
    ```
    The application should now be accessible in your web browser (usually at `http://localhost:8501`).

##  एन Environment Variables

Create a `.env` file in the project root with the following (adjust values as needed):
```env
PROXY_WORKER_URL="your_cloudflare_worker_url_here/api"
PROXY_MASTER_KEY="your_master_api_key_for_the_proxy_here"

# Optional: API Key for Crawl4AI service, if required by its endpoint.
# The current direct SDK usage of crawler4ai does not use this key,
# but it's included as a placeholder if a future version or a different
# crawling strategy (e.g., via a Crawl4AI API endpoint) were to need it.
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
*   `PROXY_WORKER_URL`: URL of your Cloudflare Worker for LLM proxy.
*   `PROXY_MASTER_KEY`: Authorization key for your Cloudflare Worker.
*   `CRAWL4AI_API_KEY` (Optional): Currently not used by the direct `crawler4ai` SDK integration but reserved for potential future use if accessing a Crawl4AI API endpoint.
*   `USE_PLACEHOLDER_LLM`: Its role is mostly superseded by the UI model selection via `models.json`. See comments above.


## 📋 Configuring Available LLM Models (`models.json`)

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

If `models.json` is missing, corrupted, or empty, the application will default to using a single placeholder model entry defined internally, allowing the UI to still function in a limited capacity.

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

For summarizing content from URLs, the application now uses the **`crawler4ai` Python library**. This library provides robust and high-quality extraction of main textual content from web pages.

Key configurations for `crawler4ai` within the application:
*   `AsyncWebCrawler` is used to perform the crawling asynchronously (called via `asyncio.run()` from synchronous code).
*   `BrowserConfig(headless=True)` ensures that no visible browser window is opened during the crawling process.
*   `CrawlerRunConfig(cache_mode=CacheMode.BYPASS)` is used to fetch fresh content on each request, ensuring the latest version of the page is processed.
The library's default mechanisms for identifying and extracting the primary content (which generally aim for a 'fit' or main content focus) are utilized. The extracted content is returned in Markdown format.

## 🧼 User Text Cleaning
When text is input directly by the user, it might contain unwanted HTML formatting. The application includes a `clean_user_text` function that uses `BeautifulSoup4` to parse and remove these HTML tags. It also normalizes excessive whitespace to ensure cleaner text is sent for summarization.

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

## 🐳 Running with Docker

A `Dockerfile` is provided to build and run this application as a Docker container.

1.  **Build the Docker Image:**
    Navigate to the project's root directory (where the `Dockerfile` is located) and run:
    ```bash
    docker build -t llm-summarizer-app .
    ```

2.  **Run the Docker Container:**
    ```bash
    docker run -p 8501:8501 --env-file .env llm-summarizer-app
    ```
    *   `-p 8501:8501`: Maps port 8501 from the container to port 8501 on your host machine.
    *   `--env-file .env`: Passes the environment variables defined in your local `.env` file to the container. Make sure your `.env` file is correctly configured with `PROXY_WORKER_URL` and `PROXY_MASTER_KEY`.
    *   `llm-summarizer-app`: The name you tagged your image with.

    The application will then be accessible at `http://localhost:8501`.

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

1.  **Launch the application:** `streamlit run app.py` (or via Docker).
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

## Новая архитектура: Crawl4AI как отдельный сервис

В проекте теперь используется отдельный сервис `crawl4ai_service` (FastAPI + crawler4ai + Playwright) для извлечения контента из URL. Streamlit-приложение обращается к нему по HTTP API (POST /scrape/). Это решает проблемы с Playwright/asyncio на Windows и упрощает поддержку.

- Все зависимости Playwright/crawler4ai теперь инкапсулированы в Docker-образе crawl4ai_service.
- Streamlit-приложение не требует установки Playwright/crawler4ai.
- Запуск проекта: `docker-compose up` (поднимает оба сервиса).

### Пример запроса к сервису crawl4ai_service

POST http://crawl4ai_service:8000/scrape/
```json
{
  "url": "https://docs.crawl4ai.com/"
}
```
Ответ:
```json
{
  "status": "success",
  "extracted_markdown": "...контент..."
}
```

---
*This README provides setup and operational details for the LLM Text Summarizer application.*
