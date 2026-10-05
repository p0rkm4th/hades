const generalPrivatePatterns = [
  /\b(?:\d{1,3}\.){3}\d{1,3}\b/i,
  /https?:\/\//i,
  /\b[\w.-]+\.(?:local|ts\.net|lan|internal)\b/i,
  /\b(?:VM|VMID|CT)\s*#?\s*\d{2,}\b/i,
  /\b(?:Proxmox|NetBox|Uptime Kuma)\b/i,
];

function escapeRegex(value) { return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); }

function createPrivateLabelPatterns(labels) {
  if (!Array.isArray(labels) || labels.length === 0) throw new Error('private labels are required');
  if (labels.some(label => typeof label !== 'string' || label.trim().length < 3)) {
    throw new Error('private labels must be nonempty names of at least three characters');
  }
  return labels.map(label => new RegExp(
    `(^|[^\\p{L}\\p{N}])${escapeRegex(label.trim())}(?=$|[^\\p{L}\\p{N}])`, 'iu',
  ));
}

function containsPrivateTopology(value, privateLabelPatterns) {
  const text = String(value || '');
  return generalPrivatePatterns.some(pattern => pattern.test(text))
    || privateLabelPatterns.some(pattern => pattern.test(text));
}

function validatePrivateLabelDetectors(labels, patterns) {
  return labels.every(label => containsPrivateTopology(label, patterns)
    && containsPrivateTopology(`node (${label}), status`, patterns)
    && containsPrivateTopology(`—${label}—`, patterns));
}

module.exports = { createPrivateLabelPatterns, containsPrivateTopology, validatePrivateLabelDetectors };
