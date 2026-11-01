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
    const api = {format};
    if (typeof module !== 'undefined' && module.exports) module.exports = api;
    else root.ResumeOutput = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);
