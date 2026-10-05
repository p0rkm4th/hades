#!/usr/bin/env node

const assert = require('node:assert/strict');
const {
  createPrivateLabelPatterns,
  containsPrivateTopology,
  validatePrivateLabelDetectors,
} = require('./homelab-household-redaction');

const labels = ['Synthetic Node', 'x[1] synthetic'];
const patterns = createPrivateLabelPatterns(labels);
assert.equal(validatePrivateLabelDetectors(labels, patterns), true);
assert.equal(containsPrivateTopology('Synthetic Node is offline.', patterns), true);
assert.equal(containsPrivateTopology('—synthetic node—', patterns), true);
assert.equal(containsPrivateTopology('The x[1] synthetic node is degraded.', patterns), true);
assert.equal(containsPrivateTopology('The syntheticly named service is online.', patterns), false);
assert.equal(containsPrivateTopology('The service is online at 192.0.2.8.', patterns), true);
assert.equal(containsPrivateTopology('See https://example.invalid/status.', patterns), true);
assert.equal(containsPrivateTopology('The guest VMID 802 is running.', patterns), true);
assert.equal(containsPrivateTopology('Proxmox reports a running guest.', patterns), true);
assert.throws(() => createPrivateLabelPatterns([]), /private labels are required/);
assert.throws(() => createPrivateLabelPatterns(['ab']), /at least three characters/);
console.log('PASS generic household topology redaction contracts');
