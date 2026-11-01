// Optional preview runner. Normal use: python -m uvicorn app.main:app --reload
import {
    spawn
} from 'node:child_process';
import {
    existsSync
} from 'node:fs';
const args = process.argv.slice(2);
const option = (name, fallback) => args.includes(name) ? args[args.indexOf(name) + 1] : fallback;
const localPython = process.platform === 'win32' ? '.venv/Scripts/python.exe' : '.venv/bin/python';
const python = existsSync(localPython) ? localPython : process.platform === 'win32' ? 'python' : 'python3';
const child = spawn(python, ['-m', 'uvicorn', 'app.main:app', '--host', option('--host', '127.0.0.1'), '--port', option('--port', process.env.PORT || '3000')], {
    stdio: 'inherit'
});
child.on('error', error => {
    console.error(error.message);
    process.exit(1);
});
child.on('exit', code => process.exit(code ?? 1));
for (const signal of ['SIGINT', 'SIGTERM']) process.on(signal, () => child.kill(signal));
