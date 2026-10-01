// chat_logic.js
// This script handles the client-side logic for the AI Advisor chat interface.
// It is loaded by chat_template.html and is driven from Python (main_window.py)
// through ai_chat_view.page().runJavaScript(...). Python passes every argument
// as a JSON-encoded string literal, so arguments can never break out of the call.

// Security model: all text is HTML-escaped FIRST, and only afterwards is a small,
// fixed set of tags (p, strong, em, code, pre, ul, ol, li, h3-h6, hr) added by the
// markdown renderer below. No attributes or links from the text are ever produced,
// so model output can't inject HTML or script.

const messageContainer = document.getElementById('message-container');

function escapeHTML(text) {
    const temp = document.createElement('div');
    temp.textContent = text;
    return temp.innerHTML;
}

function renderInline(escaped) {
    // Pull out inline code first so its contents aren't formatted.
    const codeSpans = [];
    let s = escaped.replace(/`([^`]+)`/g, (_, code) => {
        codeSpans.push(code);
        return `\u0000${codeSpans.length - 1}\u0000`;
    });
    s = s.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    s = s.replace(/__(.+?)__/g, '<strong>$1</strong>');
    s = s.replace(/(^|[^*\w])\*(?!\s)([^*]+?)\*(?!\*)/g, '$1<em>$2</em>');
    return s.replace(/\u0000(\d+)\u0000/g, (_, i) => `<code>${codeSpans[i]}</code>`);
}

function renderMarkdown(text) {
    const lines = escapeHTML(text.replace(/\u0000/g, '')).split('\n');
    const out = [];
    let paragraph = [];
    let codeLines = null;
    // Open lists, innermost last. Each list's current <li> is left open so sub-lists can nest inside it.
    const listStack = [];

    const flushParagraph = () => {
        if (paragraph.length) {
            out.push('<p>' + paragraph.map(renderInline).join('<br>') + '</p>');
            paragraph = [];
        }
    };
    const closeTopList = () => {
        out.push(`</li></${listStack.pop().type}>`);
    };
    const closeLists = () => {
        while (listStack.length) {
            closeTopList();
        }
    };
    const top = () => listStack[listStack.length - 1];
    const addListItem = (type, indent, start, content) => {
        flushParagraph();
        while (listStack.length && indent < top().indent) {
            closeTopList();
        }
        if (top() && indent === top().indent && top().type !== type) {
            closeTopList();
        }
        if (top() && indent <= top().indent) {
            out.push('</li>');
        } else {
            out.push(type === 'ol' && start !== 1 ? `<ol start="${start}">` : `<${type}>`);
            listStack.push({ type, indent });
        }
        out.push(`<li>${renderInline(content)}`);
    };

    for (const line of lines) {
        if (/^\s*```/.test(line)) {
            if (codeLines) {
                out.push('<pre><code>' + codeLines.join('\n') + '</code></pre>');
                codeLines = null;
            } else {
                flushParagraph();
                closeLists();
                codeLines = [];
            }
            continue;
        }
        if (codeLines) {
            codeLines.push(line);
            continue;
        }

        const indent = line.match(/^\s*/)[0].replace(/\t/g, '    ').length;
        let m;
        if (/^\s*([-*_])(\s*\1){2,}\s*$/.test(line)) {
            flushParagraph();
            closeLists();
            out.push('<hr>');
        } else if ((m = line.match(/^\s*(#{1,6})\s+(.*)$/))) {
            flushParagraph();
            closeLists();
            const level = Math.min(m[1].length + 2, 6);
            out.push(`<h${level}>${renderInline(m[2])}</h${level}>`);
        } else if ((m = line.match(/^\s*[-*+•]\s+(.*)$/))) {
            addListItem('ul', indent, 1, m[1]);
        } else if ((m = line.match(/^\s*(\d+)[.)]\s+(.*)$/))) {
            addListItem('ol', indent, parseInt(m[1], 10), m[2]);
        } else if (!line.trim()) {
            // Blank lines end paragraphs, but lists may continue after them.
            flushParagraph();
        } else if (listStack.length && indent > 0) {
            // Indented continuation of the current list item.
            out.push('<br>' + renderInline(line.trim()));
        } else {
            closeLists();
            paragraph.push(line);
        }
    }
    // A code block may still be open while a response is streaming in.
    if (codeLines) {
        out.push('<pre><code>' + codeLines.join('\n') + '</code></pre>');
    }
    flushParagraph();
    closeLists();
    return out.join('');
}

function stripThinking(text) {
    // Reasoning models (such as deepseek-r1) wrap their chain of thought in <think> tags.
    const withoutClosed = text.replace(/<think>[\s\S]*?<\/think>/g, '');
    const openIndex = withoutClosed.indexOf('<think>');
    if (openIndex !== -1) {
        return { text: withoutClosed.slice(0, openIndex), thinking: true };
    }
    return { text: withoutClosed, thinking: false };
}

function createMessage(type, labelText) {
    const messageDiv = document.createElement('div');
    messageDiv.classList.add('message', `${type}-message`);
    const label = document.createElement('div');
    label.className = 'label';
    label.textContent = labelText;
    messageDiv.appendChild(label);
    const body = document.createElement('div');
    body.className = 'body';
    messageDiv.appendChild(body);
    messageContainer.appendChild(messageDiv);
    return messageDiv;
}

function addUserMessage(text) {
    createMessage('user', 'You').querySelector('.body').textContent = text;
    scrollToBottom();
}

function startAIMessage(messageId) {
    const messageDiv = createMessage('ai', 'AI');
    messageDiv.id = messageId;
    setThinking(messageDiv.querySelector('.body'));
    scrollToBottom();
}

function setThinking(body) {
    body.innerHTML = '';
    const indicator = document.createElement('span');
    indicator.className = 'thinking-indicator';
    indicator.textContent = 'Thinking...';
    body.appendChild(indicator);
}

function updateAIMessage(messageId, text) {
    const el = document.getElementById(messageId);
    if (!el) {
        return;
    }
    const shouldScroll = isNearBottom();
    const body = el.querySelector('.body');
    const result = stripThinking(text);
    if (!result.text.trim()) {
        setThinking(body);
    } else {
        body.innerHTML = renderMarkdown(result.text.trim());
    }
    if (shouldScroll) {
        scrollToBottom();
    }
}

function showAIError(messageId, errorText) {
    const el = document.getElementById(messageId);
    if (!el) {
        return;
    }
    el.classList.add('error');
    el.querySelector('.body').textContent = 'Error: ' + errorText;
    scrollToBottom();
}

function finishAIMessage(messageId, note) {
    const el = document.getElementById(messageId);
    if (!el) {
        return;
    }
    if (el.querySelector('.thinking-indicator')) {
        el.querySelector('.body').textContent = '(No response)';
    }
    if (note) {
        const noteDiv = document.createElement('div');
        noteDiv.className = 'note';
        noteDiv.textContent = note;
        el.appendChild(noteDiv);
    }
}

function clearChat() {
    messageContainer.innerHTML = '';
}

function isNearBottom() {
    const scroller = document.scrollingElement;
    return scroller.scrollHeight - scroller.scrollTop - scroller.clientHeight < 80;
}

function scrollToBottom() {
    const scroller = document.scrollingElement;
    scroller.scrollTop = scroller.scrollHeight;
}
