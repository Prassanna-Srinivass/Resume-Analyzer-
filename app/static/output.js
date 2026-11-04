/* Readable presentation only: exact model text remains in saved runs/exports. */
(function (root) {
    'use strict';
    function label(key) {
        const words = String(key).replace(/([a-z])([A-Z])/g, '$1 $2').replace(/[_-]+/g, ' ');
        return words.charAt(0).toUpperCase() + words.slice(1);
    }
    function lines(value, depth = 0) {
        if (depth > 24) return ['[Further nested content is available in the original response.]'];
        if (value === null) return ['Not provided'];
        if (Array.isArray(value)) {
            if (!value.length) return ['None listed'];
            return value.flatMap(item => {
                const parts = lines(item, depth + 1);
                return ['• ' + parts[0], ...parts.slice(1).map(line => line ? '  ' + line : '')];
            });
        }
        if (typeof value === 'object') {
            const entries = Object.entries(value);
            if (!entries.length) return ['Not provided'];
            return entries.flatMap(([key, item]) => {
                const title = label(key);
                if (item !== null && typeof item === 'object') return [title, ...lines(item, depth + 1), ''];
                return [title + ': ' + (item === null ? 'Not provided' : String(item)), ''];
            });
        }
        return String(value).split('\n');
    }
    function format(text) {
        const original = String(text ?? '');
        let candidate = original.trim();
        const fenced = candidate.match(/^```(?:json)?\s*\n?([\s\S]*?)\n?```$/i);
        if (fenced) candidate = fenced[1].trim();
        try {
            const parsed = JSON.parse(candidate);
            if (parsed !== null && typeof parsed === 'object') return lines(parsed).join('\n').replace(/\n{3,}/g, '\n\n').trim();
        } catch (_) { /* Ordinary prose or incomplete JSON stays verbatim. */ }
        return original;
    }
    function appendInline(parent, text) {
        for (const part of text.split(/(\*\*[^*\n]+\*\*)/g)) {
            if (part.length > 4 && part.startsWith('**') && part.endsWith('**')) {
                const strong = document.createElement('strong');
                strong.textContent = part.slice(2, -2);
                parent.append(strong);
            } else {
                parent.append(part);
            }
        }
    }

    function render(text) {
        const result = document.createElement('div');
        result.className = 'report-body';
        const readable = format(text);
        if (readable !== text || !/^(?:#{1,6}\s|\s*(?:[-*+] |\d+\. ))|\*\*[^*\n]+\*\*/m.test(readable)) {
            result.textContent = readable;
            return result;
        }

        const lists = [];
        let paragraph;
        for (const line of readable.split(/\r?\n/)) {
            if (!line.trim()) {
                paragraph = null;
                continue;
            }
            const item = line.match(/^(\s*)([-*+]|\d+\.)\s+(.+)$/);
            if (item) {
                paragraph = null;
                const indent = item[1].replace(/\t/g, '    ').length;
                const ordered = item[2].endsWith('.');
                const tag = ordered ? 'ol' : 'ul';
                while (lists.length && lists.at(-1).indent > indent) lists.pop();
                if (lists.at(-1)?.indent === indent && lists.at(-1).tag !== tag) lists.pop();
                if (lists.at(-1)?.indent !== indent) {
                    const list = document.createElement(tag);
                    if (ordered) list.start = parseInt(item[2], 10);
                    (lists.at(-1)?.list.lastElementChild || result).append(list);
                    lists.push({indent, tag, list});
                }
                const li = document.createElement('li');
                appendInline(li, item[3]);
                lists.at(-1).list.append(li);
                continue;
            }
            lists.length = 0;
            const heading = line.match(/^\s{0,3}(#{1,6})\s+(.+)$/);
            if (heading) {
                const title = document.createElement('h' + heading[1].length);
                appendInline(title, heading[2]);
                result.append(title);
                paragraph = null;
            } else {
                if (!paragraph) {
                    paragraph = document.createElement('p');
                    result.append(paragraph);
                } else {
                    paragraph.append('\n');
                }
                appendInline(paragraph, line);
            }
        }
        return result;
    }

    const api = {format, render};
    if (typeof module !== 'undefined' && module.exports) module.exports = api;
    else root.ResumeOutput = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);
