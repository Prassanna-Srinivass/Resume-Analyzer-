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
