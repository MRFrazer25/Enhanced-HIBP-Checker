# Enhanced HIBP Checker

**Enhanced HIBP Checker** is a Python desktop application that helps you improve your online security. It checks email addresses or usernames against the [Have I Been Pwned](https://haveibeenpwned.com/) (HIBP) breach database, checks whether a password has appeared in known breaches, and gives AI-powered security advice using a model running locally through [Ollama](https://ollama.com/).

## Features

*   **Breach Check:** See which known data breaches include your email address or username, when they happened, and what kinds of data were exposed.
*   **Password Check:** Find out whether a password has appeared in a data breach using the free Pwned Passwords service. The password never leaves your computer: only the first 5 characters of its SHA-1 hash are sent (k-anonymity), with response padding enabled.
*   **AI Advisor:** Chat with a local AI model for:
    *   Personalized, prioritized advice based on your breach results (one click from the Breach Check tab).
    *   Follow-up questions. The advisor remembers the conversation.
    *   General guidance on passwords, multi-factor authentication, phishing, and more.
    *   Responses stream in live, are formatted (bold, lists, headings), and can be stopped at any time.
    *   Stays focused on security: it answers in English, politely declines off-topic requests, and refuses to help with anything harmful such as breaking into accounts or writing phishing emails.
*   **Secure API Key Storage:** Your HIBP API key is stored in your operating system's keyring, never in plain text, and is masked in the UI.
*   **Local AI Processing:** AI conversations go only to your Ollama server. The chat view loads nothing from the internet.
*   **Responsive UI:** All network requests run in the background, so the window never freezes.

## Prerequisites

*   **Python:** Version 3.10 or newer.
*   **Ollama:** Download and install from [https://ollama.com/](https://ollama.com/). Keep it up to date for security fixes.
*   **HIBP API key** (for breach checks only): available from [haveibeenpwned.com/API/Key](https://haveibeenpwned.com/API/Key). The Password Check does not need a key.
*   **Git:** For cloning the repository.

## Setup Instructions

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/MRFrazer25/Enhanced-HIBP-Checker.git
    cd Enhanced-HIBP-Checker
    ```

2.  **Create and Activate a Virtual Environment:**
    *   **Windows:**
        ```bash
        python -m venv venv
        venv\Scripts\activate
        ```
    *   **macOS/Linux:**
        ```bash
        python3 -m venv venv
        source venv/bin/activate
        ```

3.  **Install Python Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
    This installs `PyQt6`, `PyQt6-WebEngine`, `requests`, and `keyring`.

4.  **Prepare Ollama:**
    *   Make sure Ollama is installed and running.
    *   Pull a model to use with the AI Advisor. The recommended model is Google's Gemma 4 edge model (about 6.6 GB download):
        ```bash
        ollama pull gemma4:e4b
        ```
        The app has no built-in default model. You choose any installed model in Settings (see below). See [Choosing a Model](#choosing-a-model) for how the options compare.

5.  **Run the Application:**
    ```bash
    python main.py
    ```

## Usage Guide

1.  **First-Time Setup (Settings tab):**
    *   **Have I Been Pwned:** Paste your HIBP API key and click **Save API Key**. Use **Show** to reveal it and **Remove API Key** to delete it from the keyring.
    *   **Ollama:**
        *   **Server URL** defaults to `http://localhost:11434`. Change it if Ollama runs elsewhere.
        *   Click **Refresh Models** to list your installed models, then choose one. Picking a model from the list saves it right away. The AI Advisor asks you to choose a model if none has been picked yet.
    *   **No API key yet?** You can try the Breach Check with HIBP's public test key: save `00000000000000000000000000000000` as the API key and check one of HIBP's test accounts, such as `multiple-breaches@hibp-integration-tests.com` (3 breaches) or `opt-out@hibp-integration-tests.com` (no breaches). The test key only works for `@hibp-integration-tests.com` accounts.

2.  **Breach Check tab:**
    *   Enter an email address or username and press Enter or click **Check for Breaches**.
    *   If breaches are found, click **Get AI Advice on These Breaches** to send a summary to the AI Advisor.

3.  **Password Check tab:**
    *   Enter a password and press Enter or click **Check Password** to see how many times it appears in known breaches.

4.  **AI Advisor tab:**
    *   Type a question and press Enter or click **Send**. While a response is streaming, the button becomes **Stop**.
    *   Click **New Chat** to clear the conversation and start fresh.

## Choosing a Model

Any Ollama chat model works. These were tested on the app's real job (advice for an account in 3 breaches, plus a general password question) on a laptop running on CPU only (AMD Ryzen 7 5825U, 32 GB RAM, no dedicated GPU):

| Model | Download | Breach advice | Quality |
|---|---|---|---|
| `gemma4:e4b` (recommended) | 6.6 GB | ~85 s | Best. Correctly prioritised the breach that exposed credit cards and addresses, and tailored advice to each breach. |
| `qwen3.5:4b` | 3.4 GB | ~85 s | Well written, but stated breach details incorrectly (said no credit cards were exposed). |
| `phi4-mini` | 2.5 GB | ~70 s | Fastest, but generic advice that barely used the breach details. |
| `qwen3.5:2b` | 2.7 GB | ~90 s | Not recommended. Downplayed the risk and suggested a website that doesn't exist. |
| `granite4.2:8b` | 5.3 GB | ~7 min | Too slow without a GPU. |

With a dedicated GPU, responses are much faster and larger models (such as `gemma4:12b`) become practical. The app turns off "thinking" mode for reasoning models so answers start without a long silent pause.

## Security and Privacy

*   **HIBP API Key:** Stored with the `keyring` library, which uses your operating system's credential manager (Windows Credential Manager, macOS Keychain, Linux Secret Service).
*   **Password Check:** Only a 5-character prefix of the password's SHA-1 hash is sent to `api.pwnedpasswords.com`. The full password and hash never leave your machine, and passwords are never sent to the AI.
*   **AI Advisor:** Conversations are sent only to the Ollama server configured in Settings (your own machine by default). If you point the app at a remote Ollama server, your messages and breach summaries go to that server.
*   **Chat Rendering:** Model output is HTML-escaped before formatting is applied, and the chat page has a strict Content-Security-Policy, so model output can't run scripts or load remote content.
*   **No Data Collection:** This application does not collect or transmit any personal data or usage statistics.

## Running Tests

```bash
pip install -r requirements-dev.txt
python -m pytest
```

The tests mock all network calls, so they don't need an API key, internet access, or Ollama.

## Project Structure

```
main.py                  Application entry point
core/hibp_client.py      HIBP breach and Pwned Passwords API calls
core/ollama_client.py    Ollama model listing and streaming chat
core/secure_storage.py   API key storage in the system keyring
ui/main_window.py        Main window and tabs
ui/styles.py             Dark theme stylesheet
ui/html/                 AI Advisor chat page (HTML/JS)
tests/                   Unit tests
```

## Troubleshooting

*   **"Could not connect to Ollama..." / AI Advisor not working:**
    *   Make sure Ollama is running. `ollama list` in a terminal should respond.
    *   Check that the Server URL in Settings is correct (default: `http://localhost:11434`).
    *   Make sure you have pulled at least one model (for example `ollama pull gemma4:e4b`).
    *   If you see "model ... not found" or Settings says your saved model isn't installed, click **Refresh Models** and choose a model you have installed.
    *   Responses are slow on computers without a dedicated GPU. Smaller models answer faster but give less accurate advice (see [Choosing a Model](#choosing-a-model)).

*   **"Unauthorized: the HIBP API key is invalid":** Check that the key was pasted correctly and that your HIBP subscription is active.

*   **"Rate limited":** Your HIBP subscription limits how many checks you can make per minute. Wait the number of seconds shown and try again.

*   **"Error saving/retrieving HIBP API Key..." / Keyring issues:**
    *   `keyring` depends on a system credential store. On some Linux distributions you may need to install `gnome-keyring` or `kwallet` and make sure a D-Bus session is running.
    *   If errors persist, see the `keyring` documentation for backend-specific troubleshooting.

*   **Application fails to start / missing dependencies:**
    *   Activate your virtual environment before running `pip install -r requirements.txt` and `python main.py`.
    *   Check the `pip install` output for missing system libraries needed by PyQt6 or PyQt6-WebEngine.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
