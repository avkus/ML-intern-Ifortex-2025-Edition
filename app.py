import sys
# import asyncio  # Удалено
if sys.platform.startswith("win"):
    # asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    pass
import streamlit as st
import requests # Used by get_summary_from_llama
from bs4 import BeautifulSoup # Still needed for clean_user_text (if any, or general parsing)
import os
import json
import tiktoken
from dotenv import load_dotenv
from typing import Optional # For the return type
import re # For clean_user_text
# import asyncio # Added
# from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode # Added
import traceback
from concurrent.futures import ThreadPoolExecutor, TimeoutError


# Load environment variables from .env file if it exists
# This should be one of the first things to run
load_dotenv()

# --- Constants and Session State ---
CRAWL4AI_API_URL = "https://crawl4ai.interfabrika.online/md"

DEFAULT_PLACEHOLDER_MODEL = {
    "displayName": "ЗАГЛУШКА (Ошибка Загрузки Конфига)", # Consistent displayName for placeholder type
    "modelId": "placeholder", # Changed from "placeholder_true"
    "provider": "Local",
    "notes": "Используется из-за ошибки загрузки models.json. Проверьте файл."
}

def load_models_config(file_path: str = "models.json") -> list[dict]:
    """Loads LLM models configuration from a JSON file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            models = json.load(f)
        if not isinstance(models, list) or not all(isinstance(m, dict) for m in models):
            print(f"ERROR: {file_path} has invalid format. Expected a list of dictionaries.")
            return [DEFAULT_PLACEHOLDER_MODEL]
        # Ensure there's at least one model, or add placeholder if list is empty
        if not models:
             print(f"WARNING: {file_path} is empty. Using default placeholder model.")
             return [DEFAULT_PLACEHOLDER_MODEL]
        return models
    except FileNotFoundError:
        print(f"ERROR: Models configuration file '{file_path}' not found. Using default placeholder model.")
        return [DEFAULT_PLACEHOLDER_MODEL]
    except json.JSONDecodeError as e:
        print(f"ERROR: Failed to decode JSON from '{file_path}': {e}. Using default placeholder model.")
        return [DEFAULT_PLACEHOLDER_MODEL]
    except Exception as e:
        print(f"ERROR: An unexpected error occurred while loading '{file_path}': {e}. Using default placeholder model.")
        return [DEFAULT_PLACEHOLDER_MODEL]

# --- Load models configuration on application start ---
AVAILABLE_MODELS = load_models_config() # Load models globally

# --- Session State Initialization (ensure it's after AVAILABLE_MODELS if it depends on it for defaults) ---
if 'selected_model_display_name' not in st.session_state:
    if AVAILABLE_MODELS: # Check if AVAILABLE_MODELS is not empty
        st.session_state.selected_model_display_name = AVAILABLE_MODELS[0]['displayName']
    else:
        # This case should ideally not happen if load_models_config always returns a default
        st.session_state.selected_model_display_name = "No models loaded"

TOKEN_THRESHOLD = 3500  # Max tokens for direct summarization (conservative for Llama3 8B)
CHUNK_TARGET_TOKENS = 3000 # Target for each chunk in MapReduce
CHUNK_OVERLAP_TOKENS = 150   # Overlap for chunks

# Initialize session state (ensure all are present)
if 'generated_summary' not in st.session_state:
    st.session_state.generated_summary = ""
if 'summary_generated_once' not in st.session_state:
    st.session_state.summary_generated_once = False
# 'app_theme_preference' session state initialization removed.
if 'output_format_of_summary' not in st.session_state: # To store the format of the last generated summary
    st.session_state.output_format_of_summary = "Простой текст (text)"


# Environment variables (will be loaded by dotenv later if that step is added)
PROXY_WORKER_URL = os.getenv("PROXY_WORKER_URL")
PROXY_MASTER_KEY = os.getenv("PROXY_MASTER_KEY")
# For local testing without real LLM, set USE_PLACEHOLDER_LLM="true" as env var
USE_PLACEHOLDER_LLM = os.getenv("USE_PLACEHOLDER_LLM", "false").lower() == "true"

# --- ThreadPoolExecutor for async crawling workaround on Windows ---
# thread_pool_executor = ThreadPoolExecutor(max_workers=2)  # Удалено

# --- LLM Interaction and Text Processing Functions ---

# Удалены: async def _run_crawler, async def _run_crawler_async_part

import requests  # Уже импортирован выше, оставляем для явности

def fetch_text_from_url(url: str) -> Optional[str]:
    """
    Делает POST-запрос к FastAPI-сервису crawl4ai_service для извлечения markdown-контента по URL.
    Возвращает строку markdown или None/ошибку.
    """
    if not url or not url.strip():
        return None
    api_url = "http://crawl4ai_service:8000/scrape/"
    try:
        response = requests.post(api_url, json={"url": url}, timeout=90)
        response.raise_for_status()
        data = response.json()
        if data.get("status") == "success" and data.get("extracted_markdown"):
            return data["extracted_markdown"].strip()
        else:
            print(f"Crawl4ai_service API error: {data.get('error_detail', 'Unknown error')}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"HTTP error when calling crawl4ai_service: {e}")
        return None
    except Exception as e:
        print(f"Unexpected error in fetch_text_from_url: {e}")
        return None

def get_llm_system_prompt(summary_length_key: str, output_format_key: str, is_intermediate: bool) -> str:
    if is_intermediate:
        return (
            "ROLE: You are an information extraction tool.\n"
            "TASK: Analyze the provided text chunk. Your goal is to extract a few key phrases or 1-2 very short sentences in RUSSIAN that represent the main topics or entities in this chunk. This will be used for later aggregation. Focus on factual data.\n"
            "OUTPUT_FORMAT: CRITICAL: Output MUST be plain text ONLY. Do NOT use any Markdown formatting (no headings, no lists, no bold, no italics, no links). Just plain text sentences.\n"
            "LANGUAGE: Generate the output in RUSSIAN, regardless of the input chunk's language.\n"
            "IF_NO_CONTENT_RULE: If the chunk consists mostly of code, navigation links, highly fragmented data, or contains no clear narrative/summarizable information, respond with the exact phrase: 'НЕТ_ДАННЫХ_ДЛЯ_САММАРИ'\n"
            "AVOID: Do not add any conversational fluff, introductions like 'Here is the summary:', or any text not directly related to the extracted key phrases/sentences."
        )

    # Role and Task
    base_prompt = (
        "Ты – высококвалифицированный AI-ассистент, специализирующийся на создании кратких и развернутых саммари для различных текстов.\n"
        "Твоя задача – внимательно прочитать предоставленный текст и сгенерировать его саммари в соответствии с указанными параметрами длины и формата вывода.\n"
    )

    # Summary Length Description
    if "Краткое" in summary_length_key:
        length_desc = '"Краткое саммари" (short): Требуется 2-3 ключевых предложения, передающих самую суть текста.'
    elif "Развернутое" in summary_length_key:
        length_desc = '"Развернутое саммари" (long): Требуется более подробный пересказ, охватывающий основные разделы или аргументы текста, обычно 1-2 абзаца.'
    else:
        length_desc = f"Длина саммари: {summary_length_key}."


    # Output Format Description
    if "Простой текст" in output_format_key:
        format_desc = '"Простой текст (text)": Вывод должен быть представлен как простой текст без специального форматирования.'
    elif "Markdown" in output_format_key:
        format_desc = ('"Markdown (markdown)": Используй корректный Markdown-синтаксис (например, ## для заголовков, - или * для списков, **текст** или __текст__ для выделения), '
                       'если это уместно для структуры и улучшения читаемости саммари.')
    elif "HTML" in output_format_key:
        format_desc = ('"HTML (html)": Используй базовые HTML-теги (например, `<p>` для абзацев, `<h2>` или `<h3>` для подзаголовков если необходимо выделить структуру, `<ul><li>` для списков, `<strong>` или `<em>` для выделения). '
                       'Вывод НЕ должен содержать теги `<html>`, `<head>`, `<body>` или `<!DOCTYPE html>`. Только контентную часть.')
    else:
        format_desc = f"Формат вывода: {output_format_key}."

    # Style and Language
    style_prompt = (
        "Стиль Саммари: Саммари должно быть связным, информативным, точным, без излишней \"воды\" и без выражения личного мнения. " # Escaped quote
        "Оно должно объективно отражать содержание исходного текста.\n"
        "Язык Ответа: Русский."
    )

    return f"{base_prompt}\nПараметры:\n1. {length_desc}\n2. {format_desc}\n\n{style_prompt}"

try:
    ENCODING = tiktoken.get_encoding("cl100k_base")
except Exception:
    ENCODING = None

def count_tokens(text: str) -> int:
    if ENCODING is None:
        return len(text.split())
    return len(ENCODING.encode(text))

def clean_user_text(raw_text: str) -> str:
    """
    Cleans user-inputted text by removing HTML tags and normalizing whitespace.
    """
    if not raw_text or not raw_text.strip():
        return ""

    # 1. Remove HTML tags using BeautifulSoup
    soup = BeautifulSoup(raw_text, "html.parser")
    text_without_html = soup.get_text(separator=" ") # Use space as separator to avoid mashing words

    # 2. Normalize whitespace
    # Replace multiple spaces/tabs with a single space
    cleaned_text = re.sub(r'[ \t]+', ' ', text_without_html)

    # Reduce multiple newlines to a maximum of two
    cleaned_text = re.sub(r'\n{3,}', '\n\n', cleaned_text)

    # Replace \r\n (Windows line endings) with \n
    cleaned_text = cleaned_text.replace('\r\n', '\n')
    # Replace \r (old Mac line endings) with \n
    cleaned_text = cleaned_text.replace('\r', '\n')

    # Trim leading/trailing whitespace from the whole text
    cleaned_text = cleaned_text.strip()

    return cleaned_text

def get_summary_from_llama(text_to_summarize: str, summary_length_ui: str, output_format_ui: str, creativity_level: str, selected_model_id: Optional[str], is_intermediate_summary: bool = False) -> str:
    temperature_map = {"Низкий": 0.2, "Средний": 0.5, "Высокий": 0.8}
    temperature = temperature_map.get(creativity_level, 0.5)

    # Initialize payload_to_send with temperature. Messages will be added after system prompt generation.
    payload_to_send = {"temperature": temperature}

    # --- Final Model Selection Logic ---
    if selected_model_id == "placeholder":
        return (f"[ЗАГЛУШКА LLM{' (Промежуточный этап)' if is_intermediate_summary else ''}] "
                f"Саммари для: '{text_to_summarize[:100]}...'. "
                f"Модель: {selected_model_id}, Длина: {summary_length_ui}, Формат: {output_format_ui}, Креативность: {creativity_level}")

    if selected_model_id and isinstance(selected_model_id, str) and selected_model_id.strip() and selected_model_id != "placeholder":
        payload_to_send["model"] = selected_model_id
        try:
            st.markdown(f"<small><i>LLM DEBUG: Использование модели (из UI): {selected_model_id} через прокси.</i></small>", unsafe_allow_html=True)
        except Exception:
            print(f"LLM DEBUG: Attempting to use model (from UI): {selected_model_id} via proxy.")
    else:
        return "Ошибка: Модель не выбрана или конфигурация моделей не загружена. Пожалуйста, проверьте models.json и выберите модель в UI."

    if not PROXY_WORKER_URL or not PROXY_MASTER_KEY:
        return "Ошибка: URL прокси или API ключ не настроены для обращения к LLM (PROXY_WORKER_URL, PROXY_MASTER_KEY)."

    system_prompt = get_llm_system_prompt(summary_length_ui, output_format_ui, is_intermediate_summary)
    user_prompt = f"Пожалуйста, суммаризируй следующий текст:\n\n{text_to_summarize}"
    payload_to_send["messages"] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    headers = {"Authorization": f"Bearer {PROXY_MASTER_KEY}", "Content-Type": "application/json"}

    # === Логирование payload ===
    try:
        print(f"DEBUG: Payload to send to proxy for model {selected_model_id}:\n{json.dumps(payload_to_send, indent=2, ensure_ascii=False)}")
    except Exception as e:
        print(f"DEBUG: Ошибка при логировании payload: {e}")

    try:
        response = requests.post(PROXY_WORKER_URL, headers=headers, json=payload_to_send, timeout=180)
        response.raise_for_status()
        # === Логирование сырого ответа ===
        try:
            print(f"DEBUG: Raw response text from proxy:\n{response.text}")
        except Exception as e:
            print(f"DEBUG: Ошибка при логировании response.text: {e}")
        result_json = response.json()
        # === Логирование распарсенного JSON ===
        try:
            print(f"DEBUG: Parsed JSON response from proxy:\n{json.dumps(result_json, indent=2, ensure_ascii=False)}")
        except Exception as e:
            print(f"DEBUG: Ошибка при логировании result_json: {e}")
        if result_json.get("choices") and isinstance(result_json["choices"], list) and len(result_json["choices"]) > 0 and \
           result_json["choices"][0].get("message") and result_json["choices"][0]["message"].get("content"):
            return result_json["choices"][0]["message"]["content"].strip()
        else:
            if result_json.get("response") and result_json["response"].get("content"): return result_json["response"]["content"].strip()
            if result_json.get("result") and result_json["result"].get("summary"): return result_json["result"]["summary"].strip()
            return f"Ошибка: Неожиданный формат ответа от LLM прокси: {json.dumps(result_json)}"
    except requests.exceptions.Timeout:
        return "Ошибка: Запрос к LLM прокси превысил время ожидания (180с)."
    except requests.exceptions.RequestException as e:
        return f"Ошибка LLM при запросе к прокси: {e}."
    except json.JSONDecodeError:
        return f"Ошибка: Не удалось декодировать JSON ответ от LLM прокси. Ответ: {response.text if 'response' in locals() else 'No response object'}"
    except Exception as e:
        return f"Неизвестная ошибка при взаимодействии с LLM: {e}"


def text_splitter_intelligent(text: str, target_chunk_tokens: int, overlap_tokens: int) -> list[str]:
    MIN_PROGRESS_TOKENS = 100  # Минимальный гарантированный сдвиг по токенам
    if ENCODING is None:
        words = text.split()
        estimated_words_per_chunk = target_chunk_tokens
        chunks = [" ".join(words[i:i + estimated_words_per_chunk]) for i in range(0, len(words), max(MIN_PROGRESS_TOKENS, estimated_words_per_chunk - overlap_tokens if estimated_words_per_chunk > overlap_tokens else estimated_words_per_chunk))]
        return [chunk for chunk in chunks if len(chunk.strip()) > 10 and len(chunk.split()) > 20]

    tokens = ENCODING.encode(text)
    if not tokens:
        return []

    chunks = []
    current_pos = 0
    text_len = len(tokens)
    while current_pos < text_len:
        # 1. Предлагаемая граница чанка
        end_pos = min(current_pos + target_chunk_tokens, text_len)
        chunk_text = ENCODING.decode(tokens[current_pos:end_pos])
        # 2. Интеллектуальное обрезание по абзацу/предложению
        smart_end = None
        # Поиск границы абзаца (\n\n) в последней трети чанка
        para_split_index = chunk_text.rfind("\n\n", int(len(chunk_text) * 0.5))
        if para_split_index != -1 and para_split_index > int(len(chunk_text) * 0.3):
            smart_end = para_split_index + 2
        else:
            # Поиск конца предложения в последней трети чанка
            sent_split_chars = ['.', '!', '?']
            best_sent_idx = -1
            for i in range(len(chunk_text) - 1, int(len(chunk_text) * 0.3) - 1, -1):
                if chunk_text[i] in sent_split_chars:
                    if i + 1 < len(chunk_text) and chunk_text[i+1].isspace():
                        best_sent_idx = i + 1
                        break
                    elif i + 1 == len(chunk_text):
                        best_sent_idx = i + 1
                        break
            if best_sent_idx != -1:
                smart_end = best_sent_idx
        # 3. Если "умная" граница найдена и чанк не слишком короткий, используем её
        if smart_end is not None:
            smart_chunk = chunk_text[:smart_end]
            smart_chunk_tokens = ENCODING.encode(smart_chunk)
            # Если "умный" чанк слишком короткий (<50% target), пробуем добрать до target_chunk_tokens
            if len(smart_chunk_tokens) < target_chunk_tokens * 0.5:
                # Принудительно берем до target_chunk_tokens
                smart_chunk = chunk_text
                smart_chunk_tokens = ENCODING.encode(smart_chunk)
            chunk_text = smart_chunk
        # 4. Обрезаем чанк, если он вдруг получился больше target_chunk_tokens
        chunk_tokens = ENCODING.encode(chunk_text)
        if len(chunk_tokens) > target_chunk_tokens:
            chunk_tokens = chunk_tokens[:target_chunk_tokens]
            chunk_text = ENCODING.decode(chunk_tokens)
        # 5. Добавляем чанк, если он не слишком короткий
        if count_tokens(chunk_text) > 20 and len(chunk_text.strip()) > 10:
            chunks.append(chunk_text)
        # 6. Гарантированный сдвиг
        progress = max(MIN_PROGRESS_TOKENS, len(chunk_tokens) - overlap_tokens)
        if progress < 1:
            progress = MIN_PROGRESS_TOKENS
        current_pos += progress
        # Защита от зацикливания
        if current_pos <= 0 or current_pos >= text_len:
            break
    return chunks


def summarize_text_map_reduce(text_to_summarize: str, summary_length_ui: str, output_format_ui: str, creativity_level: str, selected_model_id: Optional[str]) -> str:
    total_tokens = count_tokens(text_to_summarize)
    st.markdown(f"<small><i>Отладочная информация: Общее количество токенов: {total_tokens}</i></small>", unsafe_allow_html=True)

    if total_tokens <= TOKEN_THRESHOLD:
        st.markdown("<small><i>Отладочная информация: Текст короткий, используется прямое суммирование.</i></small>", unsafe_allow_html=True)
        return get_summary_from_llama(text_to_summarize, summary_length_ui=summary_length_ui, output_format_ui=output_format_ui, creativity_level=creativity_level, selected_model_id=selected_model_id)

    st.markdown(f"<small><i>Отладочная информация: Текст длинный ({total_tokens} токенов), используется MapReduce.</i></small>", unsafe_allow_html=True)
    chunks = text_splitter_intelligent(text_to_summarize, CHUNK_TARGET_TOKENS, CHUNK_OVERLAP_TOKENS)
    if not chunks:
        return "Ошибка: Не удалось разбить текст на чанки для MapReduce."
    st.markdown(f"<small><i>Отладочная информация: Текст разбит на {len(chunks)} чанков.</i></small>", unsafe_allow_html=True)

    intermediate_summaries = []
    progress_bar = st.progress(0)
    for i, chunk in enumerate(chunks):
        chunk_token_count = count_tokens(chunk)
        status_text = st.empty()
        status_text.markdown(f"<small><i>Суммаризация чанка {i+1}/{len(chunks)} ({chunk_token_count} токенов)...</i></small>", unsafe_allow_html=True)

        # --- Логирование для отладки ---
        with st.expander(f"Отладка Чанка {i+1}/{len(chunks)}", expanded=False):
            st.write("**Текст чанка:**")
            st.code(chunk)
            system_prompt = get_llm_system_prompt(
                summary_length_key="Краткое саммари для этапа агрегации",
                output_format_key="Простой текст (text)",
                is_intermediate=True
            )
            st.write("**System Prompt:**")
            st.code(system_prompt)
            user_prompt = f"Пожалуйста, суммаризируй следующий текст:\n\n{chunk}"
            st.write("**User Prompt:**")
            st.code(user_prompt)
            payload_to_send = {
                "temperature": 0.2,
                "model": selected_model_id,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            }
            st.write("**Payload to send:**")
            st.code(payload_to_send)

        print(f"[DEBUG] Chunk {i+1}/{len(chunks)}")
        print("[DEBUG] System Prompt:\n", system_prompt)
        print("[DEBUG] User Prompt:\n", user_prompt)
        print("[DEBUG] Payload:", payload_to_send)
        print("[DEBUG] Chunk text:\n", chunk)

        intermediate_summary = get_summary_from_llama(
            chunk,
            summary_length_ui="Краткое саммари для этапа агрегации",
            output_format_ui="Простой текст (text)",
            creativity_level="Низкий",
            selected_model_id=selected_model_id,
            is_intermediate_summary=True
        )
        # Пропуск мусорных чанков
        if intermediate_summary.strip() == "НЕТ_ДАННЫХ_ДЛЯ_САММАРИ":
            continue
        if intermediate_summary.startswith("Ошибка:") or intermediate_summary.startswith("[ЗАГЛУШКА LLM] Ошибка"):
            st.warning(f"Не удалось суммаризировать чанк {i+1}: {intermediate_summary}")
        else:
            intermediate_summaries.append(intermediate_summary)
        progress_bar.progress((i + 1) / len(chunks))
        status_text.empty()

    if not intermediate_summaries:
        return "Ошибка: Не удалось создать промежуточные саммари для агрегации."

    st.markdown(f"<small><i>Отладочная информация: Промежуточные саммари ({len(intermediate_summaries)} шт.) собраны. Запуск финальной суммаризации...</i></small>", unsafe_allow_html=True)
    combined_intermediate_summary = "\n\n---\n\n".join(intermediate_summaries)
    combined_tokens = count_tokens(combined_intermediate_summary)
    st.markdown(f"<small><i>Отладочная информация: Общее количество токенов в объединенных промежуточных саммари: {combined_tokens}</i></small>", unsafe_allow_html=True)

    if combined_tokens > TOKEN_THRESHOLD * 1.5: # Allow some leeway
        st.warning(f"_Отладочная информация: Комбинированный текст промежуточных саммари ({combined_tokens} токенов) все еще слишком длинный. Он будет усечен до ~{int(TOKEN_THRESHOLD * 1.4)} токенов для финальной суммаризации._")
        if ENCODING:
            tokens = ENCODING.encode(combined_intermediate_summary)
            combined_intermediate_summary = ENCODING.decode(tokens[:int(TOKEN_THRESHOLD * 1.4)])
        else: # basic string truncate if no encoder
             combined_intermediate_summary = combined_intermediate_summary[:int(TOKEN_THRESHOLD * 1.4 * 4)] # Assuming ~4 chars per token


    status_text = st.empty()
    status_text.markdown("<small><i>Создание финального саммари из промежуточных результатов...</i></small>", unsafe_allow_html=True)
    final_summary = get_summary_from_llama(
        combined_intermediate_summary,
        summary_length_ui=summary_length_ui,
        output_format_ui=output_format_ui,
        creativity_level=creativity_level,
        selected_model_id=selected_model_id
    )
    status_text.empty()
    return final_summary


# --- Streamlit UI (main function) ---
def main():
    st.set_page_config(page_title="Тестовое задание ML intern в Ifortex (2025 Edition)")
    st.title("Тестовое задание ML intern в Ifortex (2025 Edition)")

    with st.sidebar:
        st.subheader("Настройки")
        # Theme switcher UI elements removed.
        # Other settings could be added here in the future.

    tab1, tab2 = st.tabs(["Text Input", "URL Input"])
    text_input_val, url_input_val = "", "" # Initialize
    with tab1: text_input_val = st.text_area("Введите или вставьте текст для суммаризации сюда...", height=250, key="text_area_input", label_visibility="collapsed", placeholder="Введите или вставьте текст для суммаризации сюда...")
    with tab2: url_input_val = st.text_input("Вставьте ссылку на страницу (статья, отчет, Википедия и т.д.)...", key="url_input", label_visibility="collapsed", placeholder="Вставьте ссылку на страницу (статья, отчет, Википедия и т.д.)...")

    st.subheader("Опции Генерации")
    summary_length_val = st.radio("Длина Саммари:", ("Краткое саммари", "Развернутое саммари"), key="summary_length")
    output_format_val = st.selectbox("Формат Вывода:", ("Простой текст (text)", "Markdown (markdown)", "HTML (html)"), key="output_format")
    creativity_level_val = st.select_slider("Уровень Креативности:", options=["Низкий", "Средний", "Высокий"], value="Средний", key="creativity_level")

    # --- LLM Model Selection ---
    if AVAILABLE_MODELS:
        model_display_names = [m['displayName'] for m in AVAILABLE_MODELS]

        # Initial default index for selectbox
        try:
            # Ensure session state has a valid default if it's somehow invalid or not in current list
            if st.session_state.selected_model_display_name not in model_display_names:
                st.session_state.selected_model_display_name = model_display_names[0] if model_display_names else DEFAULT_PLACEHOLDER_MODEL['displayName']

            default_idx = model_display_names.index(st.session_state.selected_model_display_name)
        except (ValueError, AttributeError):
            default_idx = 0
            if model_display_names:
                 st.session_state.selected_model_display_name = model_display_names[default_idx]
            else: # Should not happen if AVAILABLE_MODELS is properly populated with a default
                 st.session_state.selected_model_display_name = DEFAULT_PLACEHOLDER_MODEL['displayName']

        st.selectbox(
            "Выберите Модель LLM:",
            options=model_display_names,
            index=default_idx,
            key='selected_model_display_name' # Binds to st.session_state.selected_model_display_name
        )
    else:
        # This case implies AVAILABLE_MODELS was empty, which load_models_config tries to prevent
        st.error("Конфигурация моделей LLM не загружена или пуста. Проверьте файл models.json.")
        # Provide a dummy value to prevent crashes, though load_models_config should give a default
        st.session_state.selected_model_display_name = DEFAULT_PLACEHOLDER_MODEL['displayName']


    if st.button("Сгенерировать Саммари", key="generate_summary_button"):
        st.session_state.summary_generated_once = True
        st.session_state.output_format_of_summary = output_format_val # Store format for rendering/download
        text_to_summarize_final = "" # Initialize

        # Determine active tab/input source
        # This simple check prioritizes URL input if both have content.
        # A more robust tab detection might be needed if Streamlit offers better native support for it.
        if url_input_val: # User provided a URL
            with st.spinner(f"Извлечение текста из {url_input_val}..."):
                fetched_content = fetch_text_from_url(url_input_val)

            if fetched_content is None or not fetched_content.strip():
                st.error("Не удалось извлечь контент из указанного URL. Пожалуйста, проверьте ссылку или попробуйте другую.")
                st.session_state.generated_summary = "" # Clear previous summary
                return # Stop processing
            text_to_summarize_final = fetched_content
            st.markdown("<small><i>Контент извлечен из URL.</i></small>", unsafe_allow_html=True)

        elif text_input_val: # User provided text directly
            with st.spinner("Очистка введенного текста..."):
                cleaned_text = clean_user_text(text_input_val)
            text_to_summarize_final = cleaned_text
            st.markdown("<small><i>Введенный текст очищен.</i></small>", unsafe_allow_html=True)
        else:
            st.warning("Пожалуйста, введите текст или URL для суммаризации.")
            st.session_state.generated_summary = ""
            st.session_state.summary_generated_once = False # Reset if no input
            return

        # Post-processing check for empty content
        if not text_to_summarize_final.strip():
            st.warning("Нет текста для суммаризации после очистки или извлечения. Пожалуйста, проверьте введенные данные.")
            st.session_state.generated_summary = ""
            return

        # Clear previous debug messages area if any specific one exists
        # For now, new st.markdown messages will appear below previous ones or overwrite if in st.empty

        # --- Get selected model ID from UI choice ---
        actual_model_id_to_use = None # Default to None (proxy will use its default)
        selected_display_name = st.session_state.get('selected_model_display_name')

        if selected_display_name and AVAILABLE_MODELS:
            selected_model_obj = next((m for m in AVAILABLE_MODELS if m['displayName'] == selected_display_name), None)
            if selected_model_obj:
                actual_model_id_to_use = selected_model_obj['modelId']
            else:
                # This case might happen if session_state holds an old/invalid displayName
                # Fallback to first available model's ID or None if list is somehow empty again
                if AVAILABLE_MODELS and AVAILABLE_MODELS[0]['modelId'] != DEFAULT_PLACEHOLDER_MODEL['modelId']: # Check if first model is not the error placeholder
                     actual_model_id_to_use = AVAILABLE_MODELS[0]['modelId']
                     st.warning(f"Выбранное ранее имя модели '{selected_display_name}' не найдено. Используется модель по умолчанию: {AVAILABLE_MODELS[0]['displayName']}.")
                     st.session_state.selected_model_display_name = AVAILABLE_MODELS[0]['displayName'] # Update session state
                elif AVAILABLE_MODELS and len(AVAILABLE_MODELS) == 1 and AVAILABLE_MODELS[0]['modelId'] == DEFAULT_PLACEHOLDER_MODEL['modelId']:
                     # Only the error placeholder model is available.
                     actual_model_id_to_use = DEFAULT_PLACEHOLDER_MODEL['modelId']
                     # st.info(f"Используется модель-заглушка из-за ошибки конфигурации: {DEFAULT_PLACEHOLDER_MODEL['displayName']}") # This info can be noisy here
                else: # Should be prevented by earlier checks on AVAILABLE_MODELS loading
                     st.error("Список моделей пуст или содержит только ошибку, невозможно определить ID модели.")
                     st.session_state.generated_summary = "" # Clear summary and stop
                     return # Cannot proceed

        elif not AVAILABLE_MODELS : # Should be caught by UI selectbox loading, but as a safeguard
            st.error("Список моделей не загружен. Проверьте models.json.")
            st.session_state.generated_summary = "" # Clear summary and stop
            return # Cannot proceed

        # If selected_display_name is None (e.g. models.json failed and only placeholder exists)
        # and that placeholder is selected, actual_model_id_to_use will be "placeholder_true"
        if not selected_display_name and AVAILABLE_MODELS and len(AVAILABLE_MODELS) == 1 and AVAILABLE_MODELS[0]['modelId'] == DEFAULT_PLACEHOLDER_MODEL['modelId']:
            actual_model_id_to_use = DEFAULT_PLACEHOLDER_MODEL['modelId']

        # Call the summarization logic, now passing the selected model ID
        st.session_state.generated_summary = summarize_text_map_reduce(
            text_to_summarize_final,
            summary_length_val,
            output_format_val,
            creativity_level_val,
            actual_model_id_to_use # Pass the selected model ID
        )
        if st.session_state.generated_summary.startswith("Ошибка:"):
             st.error(st.session_state.generated_summary)
        elif st.session_state.generated_summary.startswith("[ЗАГЛУШКА LLM"): # Placeholder output
             st.info(st.session_state.generated_summary)


    st.subheader("Результат Саммаризации")
    if st.session_state.generated_summary:
        # Use the output_format_of_summary that was active when summary was generated
        display_format = st.session_state.output_format_of_summary

        is_error = st.session_state.generated_summary.startswith("Ошибка:")
        is_placeholder = st.session_state.generated_summary.startswith("[ЗАГЛУШКА LLM")

        if is_error:
            pass # Error already shown above
        elif is_placeholder:
            pass # Info already shown above
        elif "HTML (html)" in display_format:
            st.markdown(st.session_state.generated_summary, unsafe_allow_html=True)
        elif "Markdown (markdown)" in display_format:
            st.markdown(st.session_state.generated_summary)
        else: # Plain text
            st.text(st.session_state.generated_summary)

        if st.session_state.summary_generated_once and not is_error and not is_placeholder:
            file_name = "summary.txt"
            mime = "text/plain"
            if "Markdown (markdown)" in display_format: file_name = "summary.md"; mime = "text/markdown"
            elif "HTML (html)" in display_format: file_name = "summary.html"; mime = "text/html"

            try:
                st.download_button("Скачать Саммари", st.session_state.generated_summary, file_name, mime, key="download_summary_button")
            except Exception as e:
                st.error(f"Ошибка при подготовке файла для скачивания: {e}")
    else:
        st.info("Саммари будет отображено здесь после генерации.")

if __name__ == "__main__":
    main()
