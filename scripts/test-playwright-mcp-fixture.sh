#!/usr/bin/env bash
set -euo pipefail

# Disposable browser acceptance for the pinned Microsoft Playwright MCP
# package. The fixture is local and the browser profile is in-memory.
node <<'JS'
const http = require('http');
const { spawn } = require('child_process');

let submissions = 0;
const fixture = http.createServer((req, res) => {
  if (req.method === 'GET' && req.url === '/') {
    res.writeHead(200, {'content-type': 'text/html'});
    res.end('<!doctype html><title>HADES Fixture</title><h1>Recipe intake</h1><form method="POST" action="/submit"><label>Item <input name="item"></label><button type="submit">Apply</button></form><p id="state">DRAFT ONLY</p>');
  } else if (req.method === 'POST' && req.url === '/submit') {
    submissions += 1;
    res.writeHead(200, {'content-type': 'text/html'});
    res.end('<h1>Submitted</h1>');
  } else {
    res.writeHead(404);
    res.end();
  }
});

fixture.listen(0, '127.0.0.1', () => {
  const port = fixture.address().port;
  const child = spawn('npx', ['--yes', '@playwright/mcp@0.0.81', '--isolated', '--headless', '--browser', 'chromium'], {
    stdio: ['pipe', 'pipe', 'inherit']
  });
  let buffer = '';
  let nextId = 1;
  const pending = new Map();
  child.stdout.on('data', chunk => {
    buffer += chunk;
    while (buffer.includes('\n')) {
      const index = buffer.indexOf('\n');
      const line = buffer.slice(0, index);
      buffer = buffer.slice(index + 1);
      if (!line.trim()) continue;
      try {
        const message = JSON.parse(line);
        if (message.id && pending.has(message.id)) {
          pending.get(message.id)(message);
          pending.delete(message.id);
        }
      } catch (_) {}
    }
  });
  function rpc(method, params = {}) {
    return new Promise((resolve, reject) => {
      const id = nextId++;
      pending.set(id, resolve);
      child.stdin.write(JSON.stringify({jsonrpc: '2.0', id, method, params}) + '\n');
      setTimeout(() => reject(new Error('MCP timeout: ' + method)), 30000);
    });
  }
  (async () => {
    await rpc('initialize', {
      protocolVersion: '2024-11-05',
      capabilities: {},
      clientInfo: {name: 'hades-fixture', version: '1'}
    });
    child.stdin.write(JSON.stringify({jsonrpc: '2.0', method: 'notifications/initialized', params: {}}) + '\n');
    const listed = await rpc('tools/list');
    const names = listed.result.tools.map(tool => tool.name);
    if (!names.includes('browser_navigate') || !names.includes('browser_snapshot')) {
      throw new Error('required Playwright tools are missing');
    }
    await rpc('tools/call', {name: 'browser_navigate', arguments: {url: 'http://127.0.0.1:' + port + '/'}});
    const snapshot = await rpc('tools/call', {name: 'browser_snapshot', arguments: {}});
    const text = (snapshot.result.content || []).map(item => item.text || '').join('\n');
    if (!text.includes('Recipe intake') || !text.includes('DRAFT ONLY') || text.includes('Submitted')) {
      throw new Error('unexpected fixture snapshot or premature submission');
    }
    if (submissions !== 0) throw new Error('fixture submitted before explicit browser action');
    const button = text.match(/button "Apply" \[ref=(e[0-9]+)\]/);
    if (!button) throw new Error('Apply button ref missing from accessibility snapshot');
    const click = await rpc('tools/call', {name: 'browser_click', arguments: {element: 'Apply button', target: button[1]}});
    await new Promise(resolve => setTimeout(resolve, 250));
    if (submissions !== 1) throw new Error('explicit Apply action did not produce exactly one submission: ' + JSON.stringify(click));
    console.log('PASS Playwright MCP isolated navigation and accessibility snapshot');
    console.log('PASS disposable browser fixture remains draft-only before submit');
    console.log('PASS explicit browser click produces exactly one fixture submission');
    child.kill();
    fixture.close();
  })().catch(error => {
    console.error(error.stack);
    child.kill();
    fixture.close();
    process.exitCode = 1;
  });
});
JS
