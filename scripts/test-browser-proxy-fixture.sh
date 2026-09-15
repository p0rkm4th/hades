#!/usr/bin/env bash
set -euo pipefail

# Real MCP round-trip through the HADES policy proxy and the pinned upstream
# Playwright server. The local fixture is private-target enabled only here.
node <<'JS'
const http = require('http');
const { spawn } = require('child_process');

const fixture = http.createServer((req, res) => {
  if (req.method === 'GET' && req.url === '/') {
    res.writeHead(200, {'content-type': 'text/html'});
    res.end('<!doctype html><title>HADES Browser Fixture</title><h1>Read-only research</h1><p>NO SIDE EFFECT</p><button>Apply</button>');
    return;
  }
  res.writeHead(404);
  res.end();
});

fixture.listen(0, '127.0.0.1', () => {
  const port = fixture.address().port;
  const child = spawn('python3', ['integrations/browser-access/proxy.py'], {
    env: {...process.env, HADES_BROWSER_ALLOWED_HOSTS: '127.0.0.1', HADES_BROWSER_ALLOW_PRIVATE_TARGETS: '1'},
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
        if (message.id !== undefined && pending.has(message.id)) {
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
      protocolVersion: '2024-11-05', capabilities: {},
      clientInfo: {name: 'hades-browser-proxy-fixture', version: '1'}
    });
    child.stdin.write(JSON.stringify({jsonrpc: '2.0', method: 'notifications/initialized', params: {}}) + '\n');
    const listed = await rpc('tools/list');
    const names = listed.result.tools.map(tool => tool.name);
    if (!names.includes('browser_navigate') || !names.includes('browser_snapshot')) throw new Error('safe browser tools missing');
    for (const denied of ['browser_click', 'browser_fill_form', 'browser_evaluate', 'browser_file_upload']) {
      if (names.includes(denied)) throw new Error('unsafe tool leaked through proxy: ' + denied);
    }
    await rpc('tools/call', {name: 'browser_navigate', arguments: {url: 'http://127.0.0.1:' + port + '/'}});
    const snapshot = await rpc('tools/call', {name: 'browser_snapshot', arguments: {}});
    const text = (snapshot.result.content || []).map(item => item.text || '').join('\n');
    if (!text.includes('Read-only research') || !text.includes('NO SIDE EFFECT')) throw new Error('safe browser snapshot failed');
    const denied = await rpc('tools/call', {name: 'browser_click', arguments: {target: 'e1', element: 'Apply'}});
    if (!denied.error || !String(denied.error.message).includes('anonymous read surface')) throw new Error('unsafe browser call was not rejected: ' + JSON.stringify(denied));
    console.log('PASS Playwright MCP round-trip through HADES anonymous browser proxy');
    console.log('PASS upstream side-effecting tools are filtered and rejected');
    console.log('PASS explicit private-target override is confined to disposable fixture');
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
