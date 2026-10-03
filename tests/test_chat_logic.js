'use strict';

const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const ALLOWED_TAGS = new Set([
  'p', 'strong', 'em', 'code', 'pre', 'ul', 'ol', 'li',
  'h3', 'h4', 'h5', 'h6', 'hr', 'br',
]);

function loadRenderer() {
  const source = fs.readFileSync(
    path.join(__dirname, '..', 'ui', 'html', 'chat_logic.js'),
    'utf8',
  );
  const document = {
    getElementById() {
      return { innerHTML: '', appendChild() {}, querySelector() { return {}; } };
    },
    createElement() {
      let text = '';
      return {
        set textContent(value) { text = String(value); },
        get innerHTML() {
          return String(text)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
        },
      };
    },
  };
  const context = { document, console };
  vm.createContext(context);
  vm.runInContext(source, context);
  return context;
}

function tagsIn(html) {
  return [...html.matchAll(/<\/?([a-zA-Z][a-zA-Z0-9]*)\b[^>]*>/g)].map((m) => m[1].toLowerCase());
}

function assertOnlyWhitelistedTags(html) {
  for (const tag of tagsIn(html)) {
    assert.ok(ALLOWED_TAGS.has(tag), `unexpected tag <${tag}> in ${html}`);
  }
  assert.equal(/<[a-z][^>]*\son\w+\s*=/i.test(html), false, html);
  assert.doesNotMatch(html, /<script/i);
}

test('escapes script tags', () => {
  const { renderMarkdown } = loadRenderer();
  const html = renderMarkdown('<script>alert(1)</script>');
  assert.match(html, /&lt;script&gt;/);
  assert.doesNotMatch(html, /<script>/i);
  assertOnlyWhitelistedTags(html);
});

test('escapes attribute breakouts', () => {
  const { renderMarkdown } = loadRenderer();
  const html = renderMarkdown('"><img src=x onerror=alert(1)>');
  assert.match(html, /&lt;img/);
  assert.doesNotMatch(html, /<img/i);
  assert.doesNotMatch(html, /<[a-z][^>]*onerror=/i);
  assertOnlyWhitelistedTags(html);
});

test('literal NUL placeholders cannot inject code spans', () => {
  const { renderMarkdown } = loadRenderer();
  const html = renderMarkdown('hello \u00000 \u0000 world');
  assert.doesNotMatch(html, /<code>/);
  assert.match(html, /hello\s+0\s+world/);
  assertOnlyWhitelistedTags(html);
});

test('huge ordered-list start stays a numeric attribute', () => {
  const { renderMarkdown } = loadRenderer();
  const html = renderMarkdown('999999999999999999999. item');
  assert.match(html, /<ol start="[0-9.eE+-]+">/);
  assert.doesNotMatch(html, /on\w+\s*=/i);
  assertOnlyWhitelistedTags(html);
});

test('unclosed code fence stays escaped', () => {
  const { renderMarkdown } = loadRenderer();
  const html = renderMarkdown('```\n<script>alert(1)</script>\nstill open');
  assert.match(html, /<pre><code>/);
  assert.match(html, /&lt;script&gt;/);
  assert.doesNotMatch(html, /<script>/i);
  assertOnlyWhitelistedTags(html);
});
