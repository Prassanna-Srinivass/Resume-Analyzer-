'use strict';
const $ = id => document.getElementById(id);
const state = {
    analysis: null,
    templates: [],
    template: null,
    run: null,
    runs: [],
    live: false
};
const sample = {
    resume_text: 'Alex Morgan\nPython Backend Developer\n\nPROFILE\nBackend developer building practical web services and data tools.\n\nSKILLS\nPython, FastAPI, Flask, PostgreSQL, SQL, Git, Docker, REST APIs, Testing.\n\nEXPERIENCE\nSoftware Developer | Example Studio | 2023–2025\nBuilt REST APIs using Python and FastAPI.\nDesigned PostgreSQL queries and wrote automated tests.\nUsed Git for code review and Docker for local development.\n\nPROJECTS\nResume Insights: a Flask application that extracts text and organizes resume skills.\n\nEDUCATION\nBSc Computer Science, Example University, 2023.',
    job_description: 'Python Backend Developer\nWe need a developer with Python, FastAPI, PostgreSQL, SQL, REST APIs, Git, Docker, AWS, Kubernetes, and Redis. The role includes building backend services, maintaining database queries, collaborating on code reviews, and supporting cloud deployments.',
    target_role: 'Python Backend Developer'
};

function notify(message, error = false) {
    $('notice').textContent = message;
    $('notice').classList.toggle('error', error);
    $('notice').hidden = false;
}

function node(tag, text, cls) {
    const el = document.createElement(tag);
    if (text !== undefined) el.textContent = text;
    if (cls) el.className = cls;
    return el;
}

function date(value) {
    return new Date(value).toLocaleString();
}
async function api(path, options = {}) {
    const headers = options.body instanceof FormData ? {} : {
        'Content-Type': 'application/json'
    };
    const response = await fetch(path, {
        ...options,
        headers: {
            ...headers,
            ...options.headers
        }
    });
    if (response.status === 204) return null;
    const data = await response.json();
    if (!response.ok) {
        const d = data.detail;
        throw new Error(Array.isArray(d) ? d.map(x => x.msg).join(' · ') : d || 'Request failed. Please retry.');
    }
    return data;
}
const post = (path, data, method = 'POST') => api(path, {
    method,
    body: JSON.stringify(data)
});
let busy = false;
async function action(work) {
    if (busy) return;
    busy = true;
    const controls = [...document.querySelectorAll('button,input,textarea,select')],
        prior = controls.map(x => x.disabled);
    controls.forEach(x => x.disabled = true);
    document.body.setAttribute('aria-busy', 'true');
    $('notice').hidden = true;
    try {
        await work();
    } catch (e) {
        notify(e.message || 'Something went wrong.', true);
    } finally {
        controls.forEach((x, i) => x.disabled = prior[i]);
        document.body.removeAttribute('aria-busy');
        busy = false;
    }
}
const bind = (id, work) => $(id).addEventListener('click', () => action(work));

function showView(view) {
    for (const s of document.querySelectorAll('.view')) s.hidden = s.id !== `view-${view}`;
    for (const b of document.querySelectorAll('.nav')) b.classList.toggle('active', b.dataset.view === view);
    $('page-name').textContent = {
        analyzer: 'Resume analysis',
        studio: 'Prompt studio',
        rag: 'RAG & chunks',
        history: 'Analysis history'
    } [view];
    if (view === 'history') return loadHistory();
    if (view === 'rag') return loadDocuments();
}
for (const b of document.querySelectorAll('.nav')) b.addEventListener('click', () => action(() => showView(b.dataset.view)));

function inputValues() {
    return {
        resume_text: $('resume-text').value.trim(),
        job_description: $('job-description').value.trim(),
        target_role: $('target-role').value.trim()
    };
}

function setInputs(values) {
    for (const [key, value] of Object.entries(values)) {
        const id = key.replaceAll('_', '-');
        if ($(id)) $(id).value = value;
    }
}
async function ensureAnalysis() {
    const values = inputValues();
    if (!values.resume_text || !values.job_description) throw new Error('Add resume text and a job description in Resume analysis first.');
    if (!state.analysis || Object.keys(values).some(k => state.analysis[k] !== values[k])) {
        state.analysis = await post('/api/analysis', values);
        clearRun();
        $('comparison-output').replaceChildren();
        renderReport();
        $('retrieved-evidence').replaceChildren();
        await loadDocuments();
    }
    return state.analysis;
}

function chips(id, values, fallback) {
    $(id).replaceChildren(...(values.length ? values : [fallback]).map(v => node('span', v)));
}

function renderReport() {
    const a = state.analysis,
        r = a.report;
    $('empty-report').hidden = true;
    $('report').hidden = false;
    $('analysis-state').textContent = 'Analysis saved';
    $('coverage').textContent = r.skill_coverage === null ? 'N/A' : `${r.skill_coverage}%`;
    $('coverage-title').textContent = r.skill_coverage === null ? 'Review requirements manually' : r.skill_coverage >= 70 ? 'A solid foundation to build on' : 'Make the evidence clearer';
    $('coverage-description').textContent = `${r.matched_skills.length} of ${r.required_skills.length} detected job skills are explicitly mentioned in this resume.`;
    $('matched-count').textContent = r.matched_skills.length;
    $('missing-count').textContent = r.not_demonstrated.length;
    $('similarity').textContent = `${r.lexical_similarity}%`;
    chips('matched-skills', r.matched_skills, 'No explicit matches detected');
    chips('missing-skills', r.not_demonstrated, 'None in the detected dictionary skills');
    $('evidence').replaceChildren(...Object.entries(r.evidence).map(([s, q]) => {
        const el = node('div', undefined, 'evidence-item');
        el.append(node('strong', s), node('p', q));
        return el;
    }));
    $('context-text').textContent = `Analysis #${a.id} · ${a.target_role||'Untitled role'} · Saved ${date(a.created_at)}`;
}

function clearRun() {
    state.run = null;
    $('run-evidence').replaceChildren();
    $('run-evidence-section').hidden = true;
    $('feedback-panel').hidden = true;
    $('single-output').textContent = 'Choose a template and run it against this resume.';
    $('single-output').classList.add('empty-output');
    $('output-mode').textContent = 'No run yet';
    $('run-meta').textContent = 'The exact instructions and result are saved with every run.';
    $('preview-panel').hidden = true;
}
bind('load-sample', async () => {
    setInputs(sample);
    $('upload-label').textContent = 'Sample resume loaded · Alex Morgan';
    await ensureAnalysis();
    notify('Sample analyzed. Explore the matches or open Prompt studio.');
});
bind('analyze', async () => {
    await ensureAnalysis();
    notify('Analysis saved. Every matched skill is linked to resume evidence.');
});
bind('open-studio', async () => {
    await ensureAnalysis();
    await showView('studio');
});
$('resume-file').addEventListener('change', () => action(async () => {
    const file = $('resume-file').files[0];
    if (!file) return;
    if (file.size > 5 * 1024 * 1024) throw new Error('Choose a file no larger than 5 MB.');
    const data = new FormData();
    data.append('file', file);
    const result = await api('/api/upload', {
        method: 'POST',
        body: data
    });
    $('resume-text').value = result.resume_text;
    $('upload-label').textContent = result.filename;
    $('analysis-state').textContent = 'Inputs changed · rerun';
    $('preview-panel').hidden = true;
    notify('Resume text extracted. Check the text and add a job description.');
    $('resume-file').value = '';
}));
for (const id of ['resume-text', 'job-description', 'target-role']) $(id).addEventListener('input', () => {
    if (state.analysis) {
        $('analysis-state').textContent = 'Inputs changed · rerun';
        $('context-text').textContent = 'Inputs changed. The next prompt run will save a new analysis.';
    }
    $('preview-panel').hidden = true;
});

function fillSelect(select, items, label, value) {
    select.replaceChildren(...items.map(x => {
        const opt = node('option', label(x));
        opt.value = value(x);
        return opt;
    }));
}
async function loadTemplates(selected) {
    state.templates = await api('/api/prompts');
    fillSelect($('template-select'), state.templates, t => t.name, t => t.id);
    if (selected) $('template-select').value = selected;
    await loadTemplate();
}
async function loadTemplate() {
    state.template = await api(`/api/prompts/${$('template-select').value}`);
    const versions = state.template.versions;
    for (const id of ['version-select', 'compare-a', 'compare-b']) fillSelect($(id), versions, v => `v${v.version_number} · ${v.change_note||'Saved revision'}`, v => v.id);
    if (versions.length > 1) $('compare-b').value = versions[1].id;
    loadEditor();
    $('comparison-output').replaceChildren();
}

function loadEditor() {
    const v = state.template.versions.find(v => v.id === Number($('version-select').value));
    $('prompt-editor').value = v.prompt_text;
    $('change-note').value = '';
    $('draft-label').textContent = `Saved v${v.version_number}`;
    $('preview-panel').hidden = true;
}
$('template-select').addEventListener('change', () => action(loadTemplate));
$('version-select').addEventListener('change', loadEditor);
$('prompt-editor').addEventListener('input', () => {
    $('draft-label').textContent = 'Unsaved edit · captured when run';
    $('preview-panel').hidden = true;
});
bind('save-version', async () => {
    await post(`/api/prompts/${state.template.id}/versions`, {
        prompt_text: $('prompt-editor').value,
        change_note: $('change-note').value
    });
    await loadTemplate();
    notify('New immutable prompt version saved. Earlier versions remain available.');
});
bind('preview-prompt', async () => {
    const a = await ensureAnalysis();
    const p = await post(`/api/analysis/${a.id}/preview`, {
        prompt_text: $('prompt-editor').value,
        ...ragOptions()
    });
    $('prompt-preview').textContent = p.rendered_prompt;
    renderEvidence($('retrieved-evidence'), p.retrieval_snapshot);
    $('preview-panel').hidden = false;
    $('preview-panel').open = true;
});

function generationOptions() {
    const input = $('temperature');
    if (!input.reportValidity()) throw new Error('Enter a temperature between 0 and 2.');
    return {mode: 'live', temperature: input.value === '' ? null : input.valueAsNumber};
}

function temperatureLabel(run) {
    return run.mode === 'live' ? ` · Temperature: ${run.generation_settings?.temperature ?? 'model default'}` : '';
}

function reportOutput(text) {
    const container = node('div', undefined, 'output');
    container.append(ResumeOutput.render(text));
    return container;
}

function showRun(run) {
    state.run = run;
    renderEvidence($('run-evidence'), run.retrieval_snapshot);
    $('run-evidence-section').hidden = !run.retrieval_snapshot;
    $('run-evidence-meta').textContent = `Run #${run.id} · ${run.prompt_name} · ${date(run.created_at)}`;
    $('single-output').replaceChildren(ResumeOutput.render(run.output_text));
    $('single-output').classList.remove('empty-output');
    $('output-mode').textContent = run.mode === 'demo' ? 'Offline demo · not AI' : 'Live AI';
    $('run-meta').textContent = `Run #${run.id} · ${run.model_name}${temperatureLabel(run)} · ${date(run.created_at)} · ${run.prompt_name}`;
    $('feedback-panel').hidden = false;
    for (const k of ['relevance', 'accuracy', 'coverage', 'clarity']) $(`rating-${k}`).value = run.feedback?.[k] || '';
    $('feedback-note').value = run.feedback?.note || '';
}
bind('run-prompt', async () => {
    const settings = generationOptions();
    const a = await ensureAnalysis();
    const run = await post(`/api/analysis/${a.id}/run-prompt`, {
        prompt_version_id: Number($('version-select').value),
        prompt_text: $('prompt-editor').value,
        ...settings,
        ...ragOptions()
    });
    showRun(run);
    notify(run.mode === 'demo' ? 'Offline report saved. Demo output does not respond to prompt edits; use Live AI for prompt experiments.' : 'Live AI result saved. Review the evidence before relying on the output.');
});
bind('save-feedback', async () => {
    if (!state.run) throw new Error('Run a prompt first.');
    const f = {
        note: $('feedback-note').value
    };
    for (const k of ['relevance', 'accuracy', 'coverage', 'clarity']) {
        if (!$(`rating-${k}`).value) throw new Error('Select all four ratings before saving.');
        f[k] = Number($(`rating-${k}`).value);
    }
    showRun(await post(`/api/prompt-runs/${state.run.id}/feedback`, f));
    notify('Your evaluation has been saved with this run.');
});
bind('compare', async () => {
    const settings = generationOptions();
    if (state.template.versions.length < 2) throw new Error('Edit the prompt and save a second version first.');
    const a = await ensureAnalysis();
    const result = await post(`/api/analysis/${a.id}/compare`, {
        version_a: Number($('compare-a').value),
        version_b: Number($('compare-b').value),
        ...settings,
        ...ragOptions()
    });
    $('comparison-output').replaceChildren(...result.runs.map((run, i) => {
        const v = state.template.versions.find(v => v.id === run.prompt_version_id);
        const box = node('article', undefined, 'compare-result');
        box.append(node('h3', `${i?'B':'A'} · Version ${v.version_number}`), node('p', `${run.model_name} · ${run.mode==='demo'?'Deterministic demo':'Live AI'}${temperatureLabel(run)}`, 'helper'));
        const d = node('details');
        d.append(node('summary', 'View exact prompt instructions'), node('pre', run.prompt_text));
        const evaluate = node('button', 'Evaluate this output', 'button secondary');
        evaluate.addEventListener('click', () => {
            showRun(run);
            $('feedback-panel').scrollIntoView({
                behavior: 'auto',
                block: 'center'
            });
        });
        box.append(d, reportOutput(run.output_text), evaluate);
        return box;
    }));
    renderEvidence($('retrieved-evidence'), result.runs[0].retrieval_snapshot);
    notify('Comparison saved: identical resume, job description, retrieved evidence, model and generation settings.');
});
$('new-template').addEventListener('click', () => {
    $('template-error').textContent = '';
    $('template-dialog').showModal();
});
$('cancel-template').addEventListener('click', () => $('template-dialog').close());
$('template-form').addEventListener('submit', e => {
    e.preventDefault();
    action(async () => {
        try {
            const result = await post('/api/prompts', {
                name: $('template-name').value,
                task_type: $('template-task').value,
                prompt_text: $('prompt-editor').value,
                change_note: 'Custom template'
            });
            await loadTemplates(result.id);
            $('template-dialog').close();
            notify('Custom prompt template created.');
        } catch (error) {
            $('template-error').textContent = error.message;
        }
    });
});
async function loadHistory() {
    const analyses = await api('/api/analysis');
    $('analysis-list').replaceChildren(...analyses.map(a => {
        const item = node('div', undefined, 'history-entry'),
            open = node('button', a.target_role || `Analysis #${a.id}`);
        open.addEventListener('click', () => action(async () => {
            state.analysis = await api(`/api/analysis/${a.id}`);
            setInputs(state.analysis);
            clearRun();
            $('comparison-output').replaceChildren();
            renderReport();
            $('retrieved-evidence').replaceChildren();
            await loadDocuments();
            await loadRuns();
        }));
        const remove = node('button', 'Delete analysis', 'button ghost');
        remove.addEventListener('click', () => action(async () => {
            if (!confirm('Delete this analysis, its resume, indexed documents, and all associated runs? This cannot be undone.')) return;
            await api(`/api/analysis/${a.id}`, {
                method: 'DELETE'
            });
            if (state.analysis?.id === a.id) {
                state.analysis = null;
                state.runs = [];
                clearRun();
                $('report').hidden = true;
                $('empty-report').hidden = false;
                $('analysis-state').textContent = 'Ready when you are';
                $('context-text').textContent = 'Analyze a resume first.';
                $('comparison-output').replaceChildren();
                setInputs({
                    resume_text: '',
                    job_description: '',
                    target_role: ''
                });
            }
            await loadDocuments();
            $('retrieved-evidence').replaceChildren();
            await loadHistory();
            notify('Analysis and associated runs deleted.');
        }));
        item.append(open, node('p', `#${a.id} · ${date(a.created_at)}`), remove);
        return item;
    }));
    if (!analyses.length) $('analysis-list').append(node('p', 'No saved analyses yet.', 'helper'));
    await loadRuns();
}
async function loadRuns() {
    $('run-list').replaceChildren();
    if (!state.analysis) {
        state.runs = [];
        $('history-context').textContent = 'Select an analysis to see its runs.';
        return;
    }
    state.runs = await api(`/api/analysis/${state.analysis.id}/prompt-runs`);
    $('history-context').textContent = `Analysis #${state.analysis.id} · ${state.analysis.target_role||'Untitled role'} · ${state.runs.length} prompt runs`;
    for (const run of state.runs) {
        const box = node('article', undefined, 'history-run');
        box.append(node('h3', `#${run.id} · ${run.prompt_name}`), node('p', `${run.model_name} · ${date(run.created_at)}`), reportOutput(run.output_text));
        const details = node('details');
        details.append(node('summary', 'Exact prompt and saved evaluation'), node('pre', run.rendered_prompt + '\n\nORIGINAL MODEL RESPONSE\n' + run.output_text + '\n\nRETRIEVAL SNAPSHOT\n' + JSON.stringify(run.retrieval_snapshot, null, 2) + '\n\nEVALUATION\n' + (run.feedback ? JSON.stringify(run.feedback, null, 2) : 'Not rated yet')));
        box.append(details);
        const reuse = node('button', 'Reuse prompt & review output', 'button secondary');
        reuse.addEventListener('click', () => action(async () => {
            const t = state.templates.find(t => t.id === run.template_id);
            if (t) {
                $('template-select').value = t.id;
                await loadTemplate();
                $('version-select').value = run.prompt_version_id;
                $('prompt-editor').value = run.prompt_text;
                $('draft-label').textContent = 'Exact prompt restored from run';
            }
            $('rag-query').value = run.retrieval_snapshot?.query || '';
            $('rag-top-k').value = String(run.retrieval_snapshot?.top_k || 5);
            updateMode();
            showRun(run);
            await showView('studio');
        }));
        box.append(reuse);
        $('run-list').append(box);
    }
    if (!state.runs.length) $('run-list').append(node('p', 'No prompt runs for this analysis yet. Open Prompt studio to start.', 'helper'));
}
bind('refresh-history', loadHistory);
bind('export-runs', async () => {
    if (!state.analysis) throw new Error('Select an analysis first.');
    const runs = await api(`/api/analysis/${state.analysis.id}/prompt-runs`);
    const blob = new Blob([JSON.stringify({
        analysis: state.analysis,
        runs
    }, null, 2)], {
        type: 'application/json'
    });
    const url = URL.createObjectURL(blob),
        a = node('a');
    a.href = url;
    a.download = `resume-analysis-${state.analysis.id}.json`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
});

function updateMode() {
    $('mode-banner').replaceChildren(node('span', undefined, 'status-dot'), node('span', `Gemini + automatic RAG · ${state.live?'API key configured':'Set GEMINI_API_KEY in .env and restart'} · Resume embeddings are stored and reused. API charges may apply.`));
}
action(async () => {
    const health = await api('/api/health');
    state.live = health.live_available;
    updateMode();
    await loadTemplates();
});

function ragOptions() {
    return {rag_query: $('rag-query').value.trim(), top_k: Number($('rag-top-k').value)};
}
function renderEvidence(container, snapshot) {
    container.replaceChildren();
    if (!snapshot) return;
    const panel = node('details');
    panel.open = true;
    panel.append(node('summary', `Retrieved evidence · ${snapshot.sources.length} passages`));
    panel.append(node('p', 'Only the retrieved resume passages are supplied as candidate evidence. Retrieval can omit relevant details. Scores indicate similarity, not factual accuracy or candidate suitability.', 'helper'));
    for (const source of snapshot.sources) {
        const item = node('article', undefined, 'evidence-item');
        item.append(node('strong', `[${source.source_id}] ${source.filename} · ${source.page ? 'Page '+source.page : 'Chunk '+source.chunk}`), node('p', `Cosine similarity: ${source.similarity}`, 'helper'), node('pre', source.text));
        panel.append(item);
    }
    if (!snapshot.sources.length) panel.append(node('p', 'No relevant indexed passages retrieved. Do not infer missing ability.'));
    for (const warning of snapshot.citation_check?.warnings || []) panel.append(node('p', warning, 'rag-warning'));
    if (snapshot.citation_check) panel.append(node('p', snapshot.citation_check.note, 'helper'));
    container.append(panel);
}
async function loadDocuments() {
    $('rag-documents').replaceChildren();
    $('rag-chunks').replaceChildren();
    if (!state.analysis) {
        $('rag-context').textContent = 'Analyze a resume, or open a saved analysis from Analysis history.';
        $('chunk-count').textContent = 'No resume selected';
        $('rag-documents').append(node('p', 'Analyze a resume first to create its evidence collection.', 'helper'));
        $('rag-chunks').append(node('p', 'Your saved resume chunks will appear here.', 'helper'));
        return;
    }
    const aid = state.analysis.id;
    const [docs, chunks] = await Promise.all([
        api(`/api/analysis/${aid}/documents`),
        api(`/api/analysis/${aid}/chunks`)
    ]);
    const changed = Object.entries(inputValues()).some(([k,v]) => state.analysis[k] !== v);
    $('rag-context').textContent = `Analysis #${aid} · ${state.analysis.target_role || 'Untitled role'}${changed ? ' · Inputs have changed; analyze again to index them.' : ''}`;
    $('chunk-count').textContent = `${chunks.length} stored chunks`;
    $('rag-documents').append(node('p', docs.length ? `Analysis #${aid} · Resume index ready` : 'Older analysis: the resume will be indexed automatically on the next retrieval.', 'helper'));
    for (const doc of docs) {
        $('rag-documents').append(node('p', `${doc.filename} · ${doc.chunk_count} chunks · ${doc.embedding_model} · ${doc.dimensions} dimensions`, 'helper'));
    }
    for (const chunk of chunks) {
        const item = node('details', undefined, 'stored-chunk');
        item.open = chunks.length === 1;
        item.append(node('summary', `[${chunk.source_id}] Chunk ${chunk.position} · ${chunk.characters} characters`), node('pre', chunk.text, 'chunk-text'));
        $('rag-chunks').append(item);
    }
    if (!chunks.length) $('rag-chunks').append(node('p', 'No stored chunks yet. They will be created automatically on the next retrieval.', 'helper'));
}
bind('refresh-rag', loadDocuments);
bind('retrieve-evidence', async () => {
    const a = await ensureAnalysis();
    const snapshot = await post(`/api/analysis/${a.id}/retrieve`, ragOptions());
    renderEvidence($('retrieved-evidence'), snapshot);
    await loadDocuments();
    notify('Resume evidence retrieved. Every prompt uses retrieval automatically; comparisons share one evidence snapshot.');
});
for (const id of ['rag-query','rag-top-k']) $(id).addEventListener('change', () => {
    $('preview-panel').hidden = true;
    $('retrieved-evidence').replaceChildren();
});
