const test = require('node:test');
const assert = require('node:assert/strict');
const {format} = require('../app/static/output.js');
test('prose remains unchanged',()=>assert.equal(format('Professional profile\nSQL analyst [D1-C1].'),'Professional profile\nSQL analyst [D1-C1].'));
test('JSON skills become labelled bullet lists',()=>assert.equal(format('{"technical_skills":["SQL","Python"],"experience":null}'),'Technical skills\n• SQL\n• Python\n\nExperience: Not provided'));
test('fenced and nested JSON preserves evidence and values',()=>{
 const result=format('```json\n{"matches":[{"skill":"SQL","evidence":"Built queries [D2-C1]","years":0}],"verified":false}\n```');
 assert.ok(result.includes('Matches\n• Skill: SQL'));
 assert.ok(result.includes('Built queries [D2-C1]'));
 assert.ok(result.includes('Years: 0'));
 assert.ok(result.includes('Verified: false'));
 assert.ok(!result.includes('```'));
});
test('malformed JSON is not discarded',()=>assert.equal(format('{"skills": ["SQL"'),'{"skills": ["SQL"'));
test('source text remains literal for textContent rendering',()=>assert.ok(format('{"profile":"<script>alert(1)</script>"}').includes('<script>alert(1)</script>')));
test('deep JSON is bounded and never changes the saved string',()=>{
 let value='SQL';for(let i=0;i<100;i++)value={nested:value};
 const input=JSON.stringify(value);assert.ok(format(input).includes('original response'));assert.equal(JSON.stringify(value),input);
});

test('report rendering groups headings, labels and nested evidence under the right role', t => {
    const element = tag => ({
        tag, children: [],
        append(...nodes) { this.children.push(...nodes); },
        get lastElementChild() { return this.children.findLast(child => typeof child === 'object'); },
        set textContent(text) { this.children = [text]; },
        get textContent() { return this.children.map(child => child.textContent ?? child).join(''); }
    });
    const prior = globalThis.document;
    globalThis.document = {createElement: element};
    t.after(() => { if (prior === undefined) delete globalThis.document; else globalThis.document = prior; });
    const {render} = require('../app/static/output.js');
    const report = render('### Relevant Experience\n* **Project Associate Intern** [D3-C2]\n  * Monitored temperature [D3-C2, D3-C3].\n* **Web Development Intern**\n\n### Projects\nBuilt <img src=x> dashboards.');
    assert.deepEqual(report.children.map(node => node.tag), ['h3', 'ul', 'h3', 'p']);
    const [role, nextRole] = report.children[1].children;
    assert.equal(role.children.find(node => node.tag === 'strong').textContent, 'Project Associate Intern');
    assert.equal(role.lastElementChild.tag, 'ul');
    assert.equal(role.lastElementChild.children[0].textContent, 'Monitored temperature [D3-C2, D3-C3].');
    assert.equal(nextRole.textContent, 'Web Development Intern');
    assert.equal(report.children[3].children[0], 'Built <img src=x> dashboards.');
});
