// SPDX-License-Identifier: GPL-2.0-or-later
import test from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';

import { publishedCopy, PUBLISHED } from '../docs/release.js';

const bytes = new Uint8Array([1, 2, 3, 4]);
const sha = createHash('sha256').update(bytes).digest('hex');

// A stand-in for waffle-boot's site: path -> body, anything else a 404.
function site(files) {
	return async (url) => {
		const body = files[String(url).slice(PUBLISHED.length)];
		if (body === undefined)
			return { ok: false, status: 404 };
		return { ok: true, status: 200, json: async () => body, arrayBuffer: async () => body.buffer };
	};
}

test('the published installer is taken when latest.json names it and its SHA-256 matches', async () => {
	const got = await publishedCopy('waffle-install.ldr', site({
		'latest.json': { version: '0.9.52', file: 'waffle-install.ldr', sha256: sha },
		'waffle-install.ldr': bytes }));
	assert.equal(got.tag, 'v0.9.52');
	assert.equal(got.sha256, sha);
	assert.deepEqual(got.bytes, bytes);
});

test('an installer the site does not publish is null, and a mismatched one is refused', async () => {
	const files = { 'latest.json': { version: '0.9.52', file: 'waffle-install.ldr', sha256: sha },
		'waffle-install.ldr': new Uint8Array([9]) };
	assert.equal(await publishedCopy('waffle-boot.ldr', site(files)), null);
	await assert.rejects(publishedCopy('waffle-install.ldr', site(files)), /not the file its latest.json names/);
	await assert.rejects(publishedCopy('waffle-install.ldr', site({})), /answered 404/);
});
