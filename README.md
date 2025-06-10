# LLM Text Summarizer with Streamlit

## 🚀 Overview

This Python application provides text summarization capabilities using a Large Language Model (LLM) accessed via a Cloudflare Worker proxy. It features a user-friendly web interface built with Streamlit and can handle long texts by implementing a MapReduce approach. This project was developed as a Trainee ML Engineer test task.

## ✨ Features

*   **Flexible Input:** Summarize text pasted directly or extracted from a URL.
*   **Customizable Summaries:**
    *   Choose between "Краткое саммари" (Short) or "Развернутое саммари" (Long).
    *   Select output format: "Простой текст (text)", "Markdown (markdown)", or "HTML (html)".
    *   Adjust "Уровень Креативности" (Creativity Level - Low, Medium, High) which influences the LLM's temperature.
*   **Handles Long Texts:** Implements a MapReduce strategy (chunking, intermediate summarization, final summarization) for texts exceeding token limits.
*   **Downloadable Results:** Download the generated summary in the chosen format (`.txt`, `.md`, `.html`).
*   **Simple UI:** Easy-to-use interface built with Streamlit, including a conceptual theme preference.

## 🛠️ Tech Stack

*   **Python 3.x**
*   **Streamlit:** For the web interface.
*   **Requests:** For making HTTP calls to the LLM proxy and fetching URL content.
*   **BeautifulSoup4:** For parsing HTML and extracting text from URLs.
*   **Tiktoken:** For token counting and text chunking.
*   **python-dotenv:** For managing environment variables locally.
*   **LLM:** Designed to work with models like Llama 3 (8B or 70B) via a Cloudflare Worker.

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
    Create a file named `.env` in the root of the project directory. Add the following lines, replacing the placeholder values with your actual Cloudflare Worker URL and Master API Key:

    ```env
    PROXY_WORKER_URL="your_cloudflare_worker_url_here/api"
    PROXY_MASTER_KEY="your_master_api_key_for_the_proxy_here"

    # Optional: Set to "true" to use placeholder LLM responses for UI testing
    # USE_PLACEHOLDER_LLM="false"
    ```
    *   `PROXY_WORKER_URL`: The full URL to your deployed Cloudflare Worker endpoint that proxies requests to the LLM.
    *   `PROXY_MASTER_KEY`: The bearer token your Cloudflare Worker expects for authorization.
    *   `USE_PLACEHOLDER_LLM`: If set to `true`, the app will return dummy summaries instead of calling the actual LLM. Useful for frontend development or when an LLM endpoint is not available. Defaults to `false`.

5.  **Run the Streamlit Application:**
    ```bash
    streamlit run app.py
    ```
    The application should now be accessible in your web browser (usually at `http://localhost:8501`).

## ☁️ Cloudflare Worker LLM Proxy

This application is designed to interact with an LLM (e.g., Llama 3) through a Cloudflare Worker. The Worker acts as a secure proxy, managing requests to the underlying LLM API.

**Key Responsibilities of the Proxy Worker:**
*   Receive summarization requests from this Streamlit application.
*   Validate the `Authorization` header using the `PROXY_MASTER_KEY`.
*   Forward the request payload (system prompt, user prompt, text, temperature) to the actual LLM API endpoint (e.g., Cloudflare AI, Together AI, or any other Llama provider).
*   Include necessary authentication for the LLM provider (e.g., `LLAMA_API_KEY` configured as a secret in Cloudflare).
*   Return the LLM's response to the Streamlit application.

**Deployment:**
*   The `index.js` (or similar) for such a worker needs to be deployed to Cloudflare Workers.
*   **Example:** A simplified `index.js` for a Cloudflare Worker that proxies requests to Cloudflare's own Llama models might look something like [this hypothetical example gist](https://gist.github.com/anonymous/some_id_if_i_could_create_one). (Note: This link is a placeholder as I cannot create external content. You would replace this with an actual link to your worker code or a template.)
*   **Configuration:**
    *   Deploy using Wrangler CLI.
    *   Set secrets in Cloudflare dashboard:
        *   `LLAMA_API_KEY`: Your API key for the LLM provider.
        *   `WORKER_MASTER_KEY`: The key that this Streamlit app will use as `PROXY_MASTER_KEY` to authenticate with the worker. The worker should check for `Authorization: Bearer <WORKER_MASTER_KEY>`.

## 🔗 URL Content Extraction (Crawl4AI Stand-in)

For summarizing content from URLs, the application currently uses an internal function (`fetch_text_from_url` in `app.py`). This function employs the `requests` library to fetch the webpage and `BeautifulSoup4` to parse the HTML and extract the main textual content.

This is a basic implementation and serves as a stand-in for a more robust, specialized solution like the mentioned "Crawl4AI". For complex websites or to get higher quality text extraction, integrating a dedicated library or service would be beneficial.

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
4.  **Generate:** Click the "Сгенерировать Саммари" button.
5.  **View & Download:** The summary will appear in the output area. If successful, a "Скачать Саммари" button will allow you to download the result.

---
*This README provides setup and operational details for the LLM Text Summarizer application.*
