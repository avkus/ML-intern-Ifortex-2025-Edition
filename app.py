import streamlit as st
import requests
from bs4 import BeautifulSoup
import os
import json
import tiktoken # Added for MapReduce
from dotenv import load_dotenv # Added for .env support

# Load environment variables from .env file if it exists
# This should be one of the first things to run
load_dotenv()

# --- Constants and Session State ---
TOKEN_THRESHOLD = 3500  # Max tokens for direct summarization (conservative for Llama3 8B)
CHUNK_TARGET_TOKENS = 3000 # Target for each chunk in MapReduce
CHUNK_OVERLAP_TOKENS = 150   # Overlap for chunks

# Initialize session state (ensure all are present)
if 'generated_summary' not in st.session_state:
    st.session_state.generated_summary = ""
if 'summary_generated_once' not in st.session_state:
    st.session_state.summary_generated_once = False
if 'app_theme_preference' not in st.session_state:
    st.session_state.app_theme_preference = "Светлая"
if 'output_format_of_summary' not in st.session_state: # To store the format of the last generated summary
    st.session_state.output_format_of_summary = "Простой текст (text)"


# Environment variables (will be loaded by dotenv later if that step is added)
PROXY_WORKER_URL = os.getenv("PROXY_WORKER_URL")
PROXY_MASTER_KEY = os.getenv("PROXY_MASTER_KEY")
# For local testing without real LLM, set USE_PLACEHOLDER_LLM="true" as env var
USE_PLACEHOLDER_LLM = os.getenv("USE_PLACEHOLDER_LLM", "false").lower() == "true"


# --- LLM Interaction and Text Processing Functions ---

try:
    ENCODING = tiktoken.get_encoding("cl100k_base")
except Exception:
    ENCODING = None

def count_tokens(text: str) -> int:
    if ENCODING is None:
        return len(text.split())
    return len(ENCODING.encode(text))

def fetch_text_from_url(url: str) -> str:
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        for script_or_style in soup(["script", "style"]):
            script_or_style.decompose()
        text = soup.get_text(separator='\n', strip=True)
        cleaned_text = "\n".join([line for line in text.splitlines() if line.strip()])
        if not cleaned_text:
            return "Ошибка: Не удалось извлечь основной текстовый контент со страницы."
        return cleaned_text
    except requests.exceptions.RequestException as e:
        return f"Ошибка при запросе к URL: {e}"
    except Exception as e:
        return f"Ошибка при парсинге страницы: {e}"


def get_summary_from_llama(text_to_summarize: str, summary_length: str, output_format: str, creativity_level: str, is_intermediate_summary: bool = False) -> str:
    if USE_PLACEHOLDER_LLM:
        return (f"[ЗАГЛУШКА LLM{' (Промежуточный этап)' if is_intermediate_summary else ''}] "
                f"Саммари для: '{text_to_summarize[:100]}...'. "
                f"Длина: {summary_length}, Формат: {output_format}, Креативность: {creativity_level}")

    if not PROXY_WORKER_URL or not PROXY_MASTER_KEY:
        return "Ошибка: URL прокси или API ключ не настроены в переменных окружения (PROXY_WORKER_URL, PROXY_MASTER_KEY)."

    actual_summary_length = "short" if "Краткое" in summary_length or "этапа агрегации" in summary_length else "long"

    actual_output_format = "text" # Default for intermediate summary
    if not is_intermediate_summary: # Use user choice for final summary
        if "Markdown" in output_format: actual_output_format = "markdown"
        elif "HTML" in output_format: actual_output_format = "html"

    temperature_map = {"Низкий": 0.2, "Средний": 0.5, "Высокий": 0.8}
    temperature = temperature_map.get(creativity_level, 0.5)

    system_prompt = f"You are an expert summarizer. Your task is to generate a {actual_summary_length} summary of the provided text."
    if is_intermediate_summary:
        system_prompt = ("You are an expert summarizer. Generate a very concise summary of the following text chunk. "
                         "This summary will be used as part of a map-reduce process to summarize a much larger document. "
                         "Focus on extracting key facts and main ideas. The output MUST be in plain text format.")
    else:
        system_prompt += f" The output MUST be in {actual_output_format} format."
        if actual_output_format == "markdown":
            system_prompt += " Use appropriate Markdown syntax, including headings, lists, and emphasis where suitable."
        elif actual_output_format == "html":
            system_prompt += " Use appropriate HTML tags such as <p>, <h2>, <h3>, <ul>, <li>, and <strong> where suitable. Do not include <!DOCTYPE html>, <html>, <head>, or <body> tags, only the content itself."
    system_prompt += " Ensure the summary is coherent, accurate, and captures the main points of the text."

    user_prompt = f"Please summarize the following text:\n\n{text_to_summarize}"
    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]
    payload = {"messages": messages, "temperature": temperature}
    headers = {"Authorization": f"Bearer {PROXY_MASTER_KEY}", "Content-Type": "application/json"}

    try:
        response = requests.post(PROXY_WORKER_URL, headers=headers, json=payload, timeout=180)
        response.raise_for_status()
        result_json = response.json()
        if result_json.get("choices") and isinstance(result_json["choices"], list) and len(result_json["choices"]) > 0 and \
           result_json["choices"][0].get("message") and result_json["choices"][0]["message"].get("content"):
            return result_json["choices"][0]["message"]["content"].strip()
        else: # Fallbacks for different possible proxy response structures
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
    if ENCODING is None:
        words = text.split()
        estimated_words_per_chunk = target_chunk_tokens
        chunks = [" ".join(words[i:i + estimated_words_per_chunk]) for i in range(0, len(words), estimated_words_per_chunk - overlap_tokens if estimated_words_per_chunk > overlap_tokens else estimated_words_per_chunk)]
        return [chunk for chunk in chunks if chunk.strip()]

    tokens = ENCODING.encode(text)
    if not tokens: return []

    chunks = []
    current_pos = 0
    while current_pos < len(tokens):
        end_pos = min(current_pos + target_chunk_tokens, len(tokens))
        chunk_text = ENCODING.decode(tokens[current_pos:end_pos])

        actual_end_pos_in_text = len(chunk_text)

        if end_pos < len(tokens): # If not the last chunk, try to split intelligently
            # Try to find paragraph split (double newline) in the latter part of the chunk
            para_split_index = chunk_text.rfind("\n\n", int(len(chunk_text) * 0.7))
            if para_split_index != -1:
                actual_end_pos_in_text = para_split_index + 2 # Include the \n\n
            else:
                # Try sentence split in the latter part of the chunk
                sent_split_chars = ['.', '!', '?']
                best_sent_idx = -1
                # Search backwards from end for a sentence boundary in the last half or so
                for i in range(len(chunk_text) - 1, int(len(chunk_text) * 0.5) -1, -1):
                    if chunk_text[i] in sent_split_chars:
                        if i + 1 < len(chunk_text) and chunk_text[i+1].isspace(): # Ensure it's followed by space or is at end
                            best_sent_idx = i + 1
                            break
                        elif i + 1 == len(chunk_text): # End of chunk is a boundary
                            best_sent_idx = i + 1
                            break
                if best_sent_idx != -1:
                    actual_end_pos_in_text = best_sent_idx

            chunk_text = chunk_text[:actual_end_pos_in_text]

        # Re-encode the potentially modified chunk to get its true new token length for overlap calculation
        final_chunk_tokens = ENCODING.encode(chunk_text)
        chunks.append(chunk_text)

        # Calculate next starting position with overlap
        # Overlap should be less than the current chunk's token length
        actual_overlap_tokens = min(overlap_tokens, len(final_chunk_tokens) -1 if len(final_chunk_tokens) > 0 else 0)
        current_pos += len(final_chunk_tokens) - actual_overlap_tokens

        # Ensure progress, if overlap is too large or chunk is too small
        if len(final_chunk_tokens) == 0: # Avoid infinite loop on empty chunk
             current_pos = end_pos # Should not happen with proper text, but as safeguard
        elif current_pos <= (end_pos - len(final_chunk_tokens)): # if next start is before or at current chunk's start
             current_pos = end_pos # force move to end of original chunk window

    return [chunk for chunk in chunks if count_tokens(chunk) > overlap_tokens / 4 and len(chunk.strip()) > 10]


def summarize_text_map_reduce(text_to_summarize: str, summary_length: str, output_format: str, creativity_level: str) -> str:
    total_tokens = count_tokens(text_to_summarize)
    st.markdown(f"<small><i>Отладочная информация: Общее количество токенов: {total_tokens}</i></small>", unsafe_allow_html=True)

    if total_tokens <= TOKEN_THRESHOLD:
        st.markdown("<small><i>Отладочная информация: Текст короткий, используется прямое суммирование.</i></small>", unsafe_allow_html=True)
        return get_summary_from_llama(text_to_summarize, summary_length, output_format, creativity_level)

    st.markdown(f"<small><i>Отладочная информация: Текст длинный ({total_tokens} токенов), используется MapReduce.</i></small>", unsafe_allow_html=True)
    chunks = text_splitter_intelligent(text_to_summarize, CHUNK_TARGET_TOKENS, CHUNK_OVERLAP_TOKENS)
    if not chunks:
        return "Ошибка: Не удалось разбить текст на чанки для MapReduce."
    st.markdown(f"<small><i>Отладочная информация: Текст разбит на {len(chunks)} чанков.</i></small>", unsafe_allow_html=True)

    intermediate_summaries = []
    progress_bar = st.progress(0)
    for i, chunk in enumerate(chunks):
        chunk_token_count = count_tokens(chunk)
        # st.markdown(f"<small><i>Отладочная информация: Суммаризация чанка {i+1}/{len(chunks)} ({chunk_token_count} токенов)...</i></small>", unsafe_allow_html=True)
        status_text = st.empty()
        status_text.markdown(f"<small><i>Суммаризация чанка {i+1}/{len(chunks)} ({chunk_token_count} токенов)...</i></small>", unsafe_allow_html=True)

        intermediate_summary = get_summary_from_llama(
            chunk,
            summary_length="Краткое саммари для этапа агрегации",
            output_format="Простой текст (text)",
            creativity_level="Низкий",
            is_intermediate_summary=True
        )
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
        summary_length,
        output_format,
        creativity_level
    )
    status_text.empty()
    return final_summary


# --- Streamlit UI (main function) ---
def main():
    st.set_page_config(page_title="Тестовое задание ML intern в Ifortex (2025 Edition)")
    st.title("Тестовое задание ML intern в Ifortex (2025 Edition)")

    with st.sidebar:
        st.subheader("Настройки")
        theme_preference = st.radio("Предпочтение темы:", ("Светлая", "Темная"), key="app_theme_preference_radio", index=0 if st.session_state.app_theme_preference == "Светлая" else 1, on_change=lambda: st.experimental_rerun()) # Rerun on change for immediate (conceptual) effect
        if theme_preference != st.session_state.app_theme_preference:
            st.session_state.app_theme_preference = theme_preference
        st.caption("Для изменения темы приложения (Светлая/Темная), используйте меню Streamlit (☰) -> Settings.")
        st.caption(f"Текущее предпочтение: {st.session_state.app_theme_preference}")

    tab1, tab2 = st.tabs(["Text Input", "URL Input"])
    text_input_val, url_input_val = "", "" # Initialize
    with tab1: text_input_val = st.text_area("Введите или вставьте текст для суммаризации сюда...", height=250, key="text_area_input", label_visibility="collapsed", placeholder="Введите или вставьте текст для суммаризации сюда...")
    with tab2: url_input_val = st.text_input("Вставьте ссылку на страницу (статья, отчет, Википедия и т.д.)...", key="url_input", label_visibility="collapsed", placeholder="Вставьте ссылку на страницу (статья, отчет, Википедия и т.д.)...")

    st.subheader("Опции Генерации")
    summary_length_val = st.radio("Длина Саммари:", ("Краткое саммари", "Развернутое саммари"), key="summary_length")
    output_format_val = st.selectbox("Формат Вывода:", ("Простой текст (text)", "Markdown (markdown)", "HTML (html)"), key="output_format")
    creativity_level_val = st.select_slider("Уровень Креативности:", options=["Низкий", "Средний", "Высокий"], value="Средний", key="creativity_level")

    if st.button("Сгенерировать Саммари", key="generate_summary_button"):
        st.session_state.summary_generated_once = True
        st.session_state.output_format_of_summary = output_format_val # Store format for rendering/download
        text_to_summarize_final = ""

        if url_input_val:
            with st.spinner(f"Извлечение текста из {url_input_val}..."):
                text_to_summarize_final = fetch_text_from_url(url_input_val)
            if text_to_summarize_final.startswith("Ошибка:"):
                st.error(text_to_summarize_final); st.session_state.generated_summary = ""; return
        elif text_input_val:
            text_to_summarize_final = text_input_val
        else:
            st.warning("Пожалуйста, введите текст или URL для суммаризации."); st.session_state.generated_summary = ""; st.session_state.summary_generated_once = False; return

        if not text_to_summarize_final.strip():
            st.warning("Извлеченный или введенный текст пуст. Нечего суммаризировать."); st.session_state.generated_summary = ""; return

        # Clear previous debug messages area if any
        # (Not strictly necessary as new messages will overwrite, but good for cleanliness if we had a dedicated area)

        st.session_state.generated_summary = summarize_text_map_reduce(
            text_to_summarize_final,
            summary_length_val,
            output_format_val,
            creativity_level_val
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
