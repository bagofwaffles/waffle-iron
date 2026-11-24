// Checks firmware.zip against Python's zipfile, which is what the packager it follows is written with.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { crc32, firmwareZip, versionLine } from '../docs/fwzip.js';

const READ = `
import json, sys, zipfile
z = zipfile.ZipFile(sys.argv[1])
assert z.testzip() is None
print(json.dumps([[i.filename, i.compress_type, list(i.date_time), i.external_attr, i.create_system,
                   i.file_size, z.read(i).hex() if i.file_size < 100 else None] for i in z.infolist()]))
`;

test('CRC-32 of the usual check string', () => {
	assert.equal(crc32(new TextEncoder().encode('123456789')), 0xCBF43926);
});

test('the version line is the tag without its v, a build and the commit', () => {
	assert.equal(versionLine('v0.9.48', '461cf86d'), '0.9.48+0@461cf86d');
	assert.throws(() => versionLine('v0.9', '461cf86d'));
	assert.throws(() => versionLine('v0.9.48', ''));
});

test('firmware.zip opens in Python with the packager\'s three entries', async () => {
	const ldr = Uint8Array.from({ length: 20000 }, (_, k) => (k * 7) & 0xFF);
	const bytes = await firmwareZip(ldr, '0.9.48+0@461cf86d');
	const dir = mkdtempSync(join(tmpdir(), 'fwzip-'));
	try {
		writeFileSync(join(dir, 'firmware.zip'), bytes);
		const got = JSON.parse(execFileSync('python3', ['-I', '-B', '-c', READ, join(dir, 'firmware.zip')]));
		const line = Buffer.from('0.9.48+0@461cf86d\n').toString('hex');
		const meta = [8, [2026, 1, 1, 0, 0, 0], (0o600 << 16) >>> 0, 3];
		assert.deepEqual(got, [
			['firmware/firmware.version', ...meta, 18, line],
			['firmware/blackfin/bin/os.ldr', ...meta, 20000, null],
			['firmware/blackfin/bin/os.version', ...meta, 18, line],
		]);
	} finally {
		rmSync(dir, { recursive: true });
	}
});

test('an image the unit would not take is refused', async () => {
	await assert.rejects(firmwareZip(new Uint8Array(9486), '0.0.1+0@461cf86d'));
	await assert.rejects(firmwareZip(new Uint8Array(4096), '0.0.1+0@461cf86d'));
});
