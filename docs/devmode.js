// SPDX-License-Identifier: GPL-2.0-or-later
//
// Developer mode over the boot menu's USB MIDI link: read the unit's serial number, write the
// developer marker, and reboot back into the boot menu. The byte format (framing, the CRC, the
// 8-to-7 packing, the SysEx carrier) is the unit's own; every step here is checked against the
// worked examples in test/devmode.test.js.

// ---- CRC-8 (poly 0x4D, init 0xFF, reflected in and out, final xor 0xFF) ----

const refl = (x) => {
	let r = 0;
	for (let k = 0; k < 8; k++)
		r = (r << 1) | ((x >> k) & 1);
	return r & 0xFF;
};
export function crc8(bytes) {
	let crc = 0xFF;
	for (const byte of bytes) {
		crc ^= refl(byte);
		for (let k = 0; k < 8; k++)
			crc = (crc & 0x80) ? ((crc << 1) ^ 0x4D) & 0xFF : (crc << 1) & 0xFF;
	}
	return refl(crc) ^ 0xFF;
}

// ---- COBS ----

export function cobsEncode(data) {
	const out = [];
	let i = 0;
	const n = data.length;
	for (;;) {
		let j = i;
		while (j < n && data[j] !== 0 && (j - i) < 0xFE)
			j++;
		out.push(j - i + 1);
		for (let k = i; k < j; k++)
			out.push(data[k]);
		if (j >= n)
			break;
		if (data[j] === 0) {
			i = j + 1;
			if (i > n)
				break;
			if (i === n) {          // data ends in a zero
				out.push(1);
				break;
			}
		} else {
			i = j;                  // split at the 0xFE run limit
		}
	}
	return Uint8Array.from(out);
}
export function cobsDecode(buf) {         // buf has no trailing 0 delimiter
	const out = [];
	let i = 0;
	while (i < buf.length) {
		const c = buf[i++];
		for (let k = 0; k < c - 1; k++)
			out.push(buf[i++]);
		if (c < 0xFF && i < buf.length)
			out.push(0);
	}
	return Uint8Array.from(out);
}

// ---- 8-to-7 packing: a header byte of the group's high bits, then up to 7 low-7-bit bytes ----

export function pack(data) {
	const out = [];
	for (let i = 0; i < data.length; i += 7) {
		const grp = data.slice(i, i + 7);
		let hdr = 0;
		grp.forEach((b, k) => { if (b & 0x80) hdr |= 1 << k; });
		out.push(hdr);
		for (const b of grp)
			out.push(b & 0x7F);
	}
	return Uint8Array.from(out);
}
export function unpack(data) {
	const out = [];
	let i = 0;
	while (i < data.length) {
		const hdr = data[i++];
		const grp = data.slice(i, i + 7);
		i += grp.length;
		grp.forEach((b, k) => out.push(b | ((hdr >> k) & 1 ? 0x80 : 0)));
	}
	return Uint8Array.from(out);
}

// ---- frames and the SysEx carrier ----

// The carrier's head: F0, the maker's id 00 20 76, the unit's device byte, 66.
export const DEVICE = { 'op-xy': 0x21, 'op-1-field': 0x02 };
const head = (dev) => Uint8Array.of(0xF0, 0x00, 0x20, 0x76, dev, 0x66);
export const CARRIER_HEAD = head(DEVICE['op-xy']);
const HOST = 2, MASTER = 1;             // source 2 is the host; the master answers it at 2

// One command as one SysEx message: the head for that unit, the packed COBS frame, F7. A unit
// answers only its own device byte.
export function carrier(id, payload = [], seq = 0, dev = DEVICE['op-xy']) {
	const pl = Uint8Array.from(payload);
	const body = Uint8Array.from([(HOST << 4) | MASTER, seq, id, pl.length, ...pl]);
	const frame = Uint8Array.from([...body, crc8(body)]);
	const stream = Uint8Array.from([...cobsEncode(frame), 0]);
	return Uint8Array.from([...head(dev), ...pack(stream), 0xF7]);
}

// A received SysEx message back to { dev, id, seq, src, dst, payload }, or null if it is not one of
// ours. Any device byte is taken.
export function parseCarrier(msg) {
	if (msg.length < CARRIER_HEAD.length + 2 || msg[msg.length - 1] !== 0xF7)
		return null;
	for (let k = 0; k < CARRIER_HEAD.length; k++)
		if (k !== 4 && msg[k] !== CARRIER_HEAD[k])
			return null;
	const stream = unpack(msg.slice(CARRIER_HEAD.length, -1));
	let end = stream.length;
	while (end > 0 && stream[end - 1] === 0)
		end--;                          // drop the delimiter (and any 7-bit group padding)
	const frame = cobsDecode(stream.slice(0, end));
	if (frame.length < 5)
		return null;
	const len = frame[3];
	if (frame.length < 5 + len)
		return null;
	const over = frame.slice(0, 4 + len);
	if (crc8(over) !== frame[4 + len])
		return null;
	return { dev: msg[4], src: frame[0] >> 4, dst: frame[0] & 0xF, seq: frame[1], id: frame[2],
		payload: frame.slice(4, 4 + len) };
}

// ---- the three commands ----

export const CMD = { FSN: 0x1F, FSN_REPLY: 0x20, DEV: 0xAC, FIRMWARE: 0x0D };
const DEV_KEY = [0x99, 0x4A, 0xF3, 0xED];       // marker-request prefix and token key
const TARGET_BOOT = 0xBA;                        // the boot loader's marker (0xBE is the OS's)
const SET = 0xA7;                                // any other value clears it

export function fsnRequest(seq = 0, dev) {
	return carrier(CMD.FSN, [], seq, dev);
}
// The marker request: the key, then serialNumber[i] xor key[i mod 4], then target and set/clear.
export function devRequest(fsn, on = true, seq = 0, dev) {
	if (fsn.length !== 16)
		throw new Error('serial number must be 16 bytes');
	const token = Array.from(fsn, (b, i) => b ^ DEV_KEY[i % 4]);
	return carrier(CMD.DEV, [...DEV_KEY, ...token, TARGET_BOOT, on ? SET : 0x00], seq, dev);
}
// Firmware command EE, mode 02: the next boot opens the boot menu (its main screen).
export function rebootToBootMenu(seq = 0, dev) {
	return carrier(CMD.FIRMWARE, [0xEE, 0x02], seq, dev);
}
// Firmware command EE, mode 01: the next boot opens the bootloader's upload screen, taking the
// firmware as a USB disk. With no mode byte it opens the same screen taking it over MIDI.
export function rebootToUpload(disk = true, seq = 0, dev) {
	return carrier(CMD.FIRMWARE, disk ? [0xEE, 0x01] : [0xEE], seq, dev);
}
