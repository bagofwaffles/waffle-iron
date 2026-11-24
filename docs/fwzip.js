// SPDX-License-Identifier: GPL-2.0-or-later
//
// firmware.zip for the bootloader's upload screen: a package whose only component is one OS image.
//
//     firmware/firmware.version
//     firmware/blackfin/bin/os.ldr
//     firmware/blackfin/bin/os.version
//
// Both version files hold "major.minor.patch+build@githash\n". Every entry is deflated, dated
// 2026-01-01 00:00:00 and marked mode 0600 from a Unix system, so the same input gives the same
// layout each time.

const enc = new TextEncoder();
const MIN = 9488, MAX = 0x800000;       // what the unit takes as an OS image, in bytes

const TABLE = Array.from({ length: 256 }, (_, n) => {
	for (let k = 0; k < 8; k++)
		n = n & 1 ? (n >>> 1) ^ 0xEDB88320 : n >>> 1;
	return n >>> 0;
});
export function crc32(bytes) {
	let c = 0xFFFFFFFF;
	for (const b of bytes)
		c = TABLE[(c ^ b) & 0xFF] ^ (c >>> 8);
	return (c ^ 0xFFFFFFFF) >>> 0;
}

async function deflate(bytes) {
	const stream = new Blob([bytes]).stream().pipeThrough(new CompressionStream('deflate-raw'));
	return new Uint8Array(await new Response(stream).arrayBuffer());
}

// Little-endian fields: [value, width in bytes] pairs, then any byte arrays, as one array.
function record(fields, ...tails) {
	const out = [];
	for (const [value, width] of fields)
		for (let k = 0; k < width; k++)
			out.push(Math.floor(value / 2 ** (8 * k)) & 0xFF);
	return Uint8Array.from([...out, ...tails.flatMap((t) => [...t])]);
}

const DATE = ((2026 - 1980) << 9) | (1 << 5) | 1, TIME = 0;
const UNIX = 3 << 8, VERSION = 20, DEFLATED = 8, MODE = (0o600 << 16) >>> 0;

// A zip of [name, bytes] entries, in order.
export async function zip(entries) {
	const parts = [], central = [];
	let at = 0;
	for (const [name, data] of entries) {
		const packed = await deflate(data);
		const common = [[VERSION, 2], [0, 2], [DEFLATED, 2], [TIME, 2], [DATE, 2], [crc32(data), 4],
			[packed.length, 4], [data.length, 4], [name.length, 2], [0, 2]];
		const local = record([[0x04034B50, 4], ...common], enc.encode(name));
		central.push(record([[0x02014B50, 4], [UNIX | VERSION, 2], ...common, [0, 2], [0, 2], [0, 2],
			[MODE, 4], [at, 4]], enc.encode(name)));
		parts.push(local, packed);
		at += local.length + packed.length;
	}
	const size = central.reduce((n, c) => n + c.length, 0);
	parts.push(...central, record([[0x06054B50, 4], [0, 2], [0, 2], [entries.length, 2], [entries.length, 2],
		[size, 4], [at, 4], [0, 2]]));
	const out = new Uint8Array(parts.reduce((n, p) => n + p.length, 0));
	let pos = 0;
	for (const p of parts) {
		out.set(p, pos);
		pos += p.length;
	}
	return out;
}

// "major.minor.patch+build@githash" for a release: its tag, with any leading v dropped.
export function versionLine(tag, githash, build = 0) {
	const version = String(tag).replace(/^v/, '');
	if (!/^\d+\.\d+\.\d+$/.test(version))
		throw new Error('the release tag ' + tag + ' is not major.minor.patch');
	if (!/^[0-9a-f]{7,40}$/.test(githash || ''))
		throw new Error('no commit hash for ' + tag);
	return version + '+' + build + '@' + githash;
}

// firmware.zip holding the installer as the OS image.
export async function firmwareZip(ldr, version) {
	if (ldr.length % 4 || ldr.length < MIN || ldr.length > MAX)
		throw new Error('the file is ' + ldr.length + ' bytes; an OS image must be 4-byte aligned and ' +
			MIN + ' to ' + MAX + ' bytes');
	const line = enc.encode(version + '\n');
	return zip([['firmware/firmware.version', line], ['firmware/blackfin/bin/os.ldr', ldr],
		['firmware/blackfin/bin/os.version', line]]);
}
