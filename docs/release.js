// SPDX-License-Identifier: GPL-2.0-or-later
//
// Which installer to copy: the latest waffle-boot release, or a file the user gives.
//
// GitHub's API says what the latest release is (its tag, and each file's size and SHA-256), and a
// page may read that. The release downloads themselves it may not: they carry no cross-origin leave.
// So the bytes come from waffle-boot's own public site on GitHub Pages, which publishes the latest
// installer with that leave. Nothing is kept beside this page. A copy is used only when its SHA-256
// is the one its own latest.json names, and, when GitHub answers, the one the release lists.

import { sha256Hex } from './mtp.js';

export const REPO = 'bagofwaffles/waffle-boot';
export const RELEASES = 'https://github.com/' + REPO + '/releases';
// The installer for each unit, by its file name in a release.
export const ASSET = { 'op-xy': 'waffle-install.ldr', 'op-1-field': 'waffle-install-1f.ldr' };

// { tag, assets: { name: { size, sha256, url } } } from GitHub's answer for a release.
export function parseRelease(json) {
	const assets = {};
	for (const a of json.assets || [])
		assets[a.name] = { size: a.size, url: a.browser_download_url,
			sha256: typeof a.digest === 'string' && a.digest.startsWith('sha256:') ? a.digest.slice(7) : null };
	return { tag: json.tag_name, assets };
}

export async function latestRelease(fetcher = fetch) {
	const r = await fetcher('https://api.github.com/repos/' + REPO + '/releases/latest',
		{ headers: { Accept: 'application/vnd.github+json' } });
	if (!r.ok)
		throw new Error('GitHub answered ' + r.status);
	return parseRelease(await r.json());
}

// The commit a release's tag names, as GitHub gives it: 40 hex digits.
export async function commitOf(tag, fetcher = fetch) {
	const r = await fetcher('https://api.github.com/repos/' + REPO + '/commits/' + encodeURIComponent(tag),
		{ headers: { Accept: 'application/vnd.github+json' } });
	if (!r.ok)
		throw new Error('GitHub answered ' + r.status);
	return (await r.json()).sha;
}

// waffle-boot's public site, which carries the latest installer and latest.json.
export const PUBLISHED = 'https://bagofwaffles.github.io/waffle-boot/web/release/';

// The installer waffle-boot publishes, when it is the one named: { tag, bytes, sha256 }, or null
// when the site carries no such file. It throws when the file is not the one latest.json describes.
export async function publishedCopy(name, fetcher = fetch) {
	const meta = await fetcher(PUBLISHED + 'latest.json', { cache: 'no-cache' });
	if (!meta.ok)
		throw new Error('waffle-boot’s site answered ' + meta.status);
	const info = await meta.json();
	if (info.file !== name)
		return null;
	const file = await fetcher(PUBLISHED + name, { cache: 'no-cache' });
	if (!file.ok)
		throw new Error('waffle-boot’s site answered ' + file.status + ' for ' + name);
	const bytes = new Uint8Array(await file.arrayBuffer());
	const sha256 = await sha256Hex(bytes);
	if (sha256 !== info.sha256)
		throw new Error(name + ' on waffle-boot’s site is not the file its latest.json names');
	return { tag: 'v' + info.version, bytes, sha256 };
}

// What a file is, by its SHA-256: { tag, name, unit } when it is one of the release's installers.
export function identify(release, sha256) {
	if (!release)
		return null;
	for (const [name, a] of Object.entries(release.assets))
		if (a.sha256 && a.sha256 === sha256)
			return { tag: release.tag, name, unit: Object.keys(ASSET).find((u) => ASSET[u] === name) || null };
	return null;
}
