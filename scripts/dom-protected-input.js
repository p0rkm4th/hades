const fs = require('node:fs');

/**
 * Read a DOM-test credential without putting its value in a command line.
 * Direct environment variables remain supported for CI, but protected files
 * are preferred for owner/household acceptance runs.
 */
function protectedInput(name) {
  const inline = process.env[name];
  if (inline) return inline;
  const file = process.env[`${name}_FILE`];
  if (!file) return '';
  const stat = fs.statSync(file);
  if (!stat.isFile()) throw new Error(`${name}_FILE is not a regular file`);
  if ((stat.mode & 0o077) !== 0) {
    throw new Error(`${name}_FILE must be mode 0600 or stricter`);
  }
  return fs.readFileSync(file, 'utf8').replace(/[\r\n]+$/, '');
}

module.exports = { protectedInput };
