// SPDX-License-Identifier: GPL-2.0-or-later
//
// A careful MTP copy over WebUSB: put one file at the top of the unit's volume and prove it by
// reading it back. It follows waffle-boot's tools/mtpcp.py step for step, and sends only
// GetDeviceInfo, OpenSession, CloseSession, GetStorageIDs, GetStorageInfo, GetObjectHandles,
// GetObjectInfo, GetObject, DeleteObject, SendObjectInfo and SendObject. In particular:
//
// - a file is read whole with GetObject, never in parts;
// - the root is listed with parent 0xFFFFFFFF;
// - a container's length is not trusted: a data phase ends at a short packet or at its length;
// - a data container left from an earlier transaction is dropped;
// - a successful GetObject proves nothing: the bytes are compared;
// - a folder is never deleted, and nothing is changed on a read-only store.
//
// Mtp talks to a transport with write(bytes), read(size, ms) and mps, so the same code runs over
// WebUSB (UsbTransport) and over the stand-in unit in mtpfake.js that the tests use.

export const VID = 0x2367;
const CMD = 1, DATA = 2, EVENT = 4;
export const OP = {
	DEVICE_INFO: 0x1001, OPEN: 0x1002, CLOSE: 0x1003, STORAGE_IDS: 0x1004, STORAGE_INFO: 0x1005,
	HANDLES: 0x1007, OBJECT_INFO: 0x1008, GET_OBJECT: 0x1009, DELETE: 0x100B, SEND_INFO: 0x100C,
	SEND: 0x100D,
};
export const OK = 0x2001, ALREADY_OPEN = 0x201E, INVALID_HANDLE = 0x2009, INVALID_PARENT = 0x201A;
export const ROOT = 0xFFFFFFFF;
export const FORMAT_UNDEFINED = 0x3000, FORMAT_FOLDER = 0x3001;
// The MTP function's interface: the standard one, and the vendor one the "(mac)" menu item gives.
export const MTP_CLASSES = [[0x06, 0x01, 0x01], [0xFF, 0x01, 0x01]];

const RESPONSES = {
	0x2001: 'OK', 0x2002: 'General_Error', 0x2003: 'Session_Not_Open',
	0x2005: 'Operation_Not_Supported', 0x2006: 'Parameter_Not_Supported',
	0x2007: 'Incomplete_Transfer', 0x2008: 'Invalid_StorageID', 0x2009: 'Invalid_ObjectHandle',
	0x200C: 'Store_Full', 0x200D: 'Object_WriteProtected', 0x200F: 'Access_Denied',
	0x2015: 'No_Valid_ObjectInfo', 0x2019: 'Device_Busy', 0x201A: 'Invalid_ParentObject',
	0x201D: 'Invalid_Parameter', 0x201E: 'Session_Already_Open', 0xA806: 'Invalid_Dataset',
};
const responseName = (code) =>
	(RESPONSES[code] || 'an unknown code') + ' (0x' + code.toString(16).padStart(4, '0') + ')';

const TIMEOUT_MS = 60000;       // one bulk transfer, or the wait for a response
const CHUNK = 65536;            // a multiple of both packet sizes, so a transfer cannot overflow

// The run cannot give its answer; the message says what happened. `changed` is true when the
// unit's copy may no longer be good.
export class Failure extends Error {}
export class Timeout extends Failure {}

// ---- containers and datasets ----

export function concat(parts) {
	const out = new Uint8Array(parts.reduce((n, p) => n + p.length, 0));
	let at = 0;
	for (const p of parts) {
		out.set(p, at);
		at += p.length;
	}
	return out;
}

// A container: length, type, code, transaction id, then 32-bit parameters or a payload.
export function container(kind, code, tid, params = [], payload = null) {
	const out = new Uint8Array(12 + 4 * params.length + (payload ? payload.length : 0));
	const v = new DataView(out.buffer);
	v.setUint32(0, out.length, true);
	v.setUint16(4, kind, true);
	v.setUint16(6, code, true);
	v.setUint32(8, tid, true);
	params.forEach((p, k) => v.setUint32(12 + 4 * k, p >>> 0, true));
	if (payload)
		out.set(payload, 12 + 4 * params.length);
	return out;
}

export function mtpString(text) {
	if (!text)
		return Uint8Array.of(0);
	const out = new Uint8Array(1 + 2 * (text.length + 1));
	out[0] = text.length + 1;
	for (let i = 0; i < text.length; i++) {
		out[1 + 2 * i] = text.charCodeAt(i) & 0xFF;
		out[2 + 2 * i] = text.charCodeAt(i) >> 8;
	}
	return out;
}

// A dataset's fields; a field the dataset does not carry reads as zero or empty.
export class Reader {
	constructor(data) {
		this.view = new DataView(data.buffer, data.byteOffset, data.byteLength);
		this.pos = 0;
	}
	num(size) {
		const at = this.pos;
		this.pos += size;
		if (this.pos > this.view.byteLength)
			return 0;
		if (size === 1)
			return this.view.getUint8(at);
		if (size === 2)
			return this.view.getUint16(at, true);
		if (size === 4)
			return this.view.getUint32(at, true);
		return Number(this.view.getBigUint64(at, true));
	}
	string() {
		const n = this.num(1);
		let out = '';
		for (let i = 0; i < n; i++) {
			const c = this.num(2);
			if (!c)
				out += '\0';
			else
				out += String.fromCharCode(c);
		}
		return out.split('\0', 1)[0];
	}
	skipArray(size) {
		const n = this.num(4);
		this.pos += n * size;
	}
}

function parseObject(handle, data) {
	const r = new Reader(data);
	r.num(4);                       // StorageID
	const format = r.num(2);
	r.num(2);                       // ProtectionStatus
	const size = r.num(4);
	r.pos += 2 + 6 * 4;             // the thumb and image fields
	const parent = r.num(4);
	r.pos += 2 + 4 + 4;             // AssociationType, AssociationDesc, SequenceNumber
	const name = r.string();
	r.string();                     // DateCreated
	return { handle, format, size, parent, name, modified: r.string(), folder: format === FORMAT_FOLDER };
}

// The ObjectInfo dataset of a file to send.
export function objectInfoDataset(storage, name, size, modified) {
	const head = new Uint8Array(52);
	const v = new DataView(head.buffer);
	v.setUint32(0, storage, true);
	v.setUint16(4, FORMAT_UNDEFINED, true);
	v.setUint32(8, size, true);
	return concat([head, mtpString(name), mtpString(modified), mtpString(modified), mtpString('')]);
}

// ---- transactions ----

export class Mtp {
	constructor(transport) {
		this.t = transport;
		this.tid = 0;
		this.session = 0;
		this.stale = 0;
		this.onProgress = null;         // (what, done, total) during a file's data phase
		this.what = '';
	}

	// Drop whatever an earlier client left in the device's IN queue.
	async drain() {
		try {
			for (;;)
				await this.t.read(CHUNK, 100);
		} catch (e) {
			if (!(e instanceof Timeout))
				throw e;
		}
	}

	progress(done, total) {
		if (this.onProgress && this.what)
			this.onProgress(this.what, Math.min(done, total), total);
	}

	// The next container from the device. Zero-length packets between containers are skipped.
	async next() {
		let chunk = new Uint8Array(0);
		while (!chunk.length)
			chunk = await this.t.read(CHUNK, TIMEOUT_MS);
		if (chunk.length < 12)
			throw new Failure('short container from the device');
		const v = new DataView(chunk.buffer, chunk.byteOffset, chunk.byteLength);
		const total = v.getUint32(0, true), kind = v.getUint16(4, true);
		if (kind < DATA || kind > EVENT || total < 12)
			throw new Failure('not a device container');
		const parts = [chunk];
		let got = chunk.length;
		// The length is not trusted: a short packet ends the phase too.
		while (kind === DATA && got < total && chunk.length % this.t.mps === 0) {
			chunk = await this.t.read(CHUNK, TIMEOUT_MS);
			if (!chunk.length)
				break;
			parts.push(chunk);
			got += chunk.length;
			this.progress(got - 12, total - 12);
		}
		return { kind, code: v.getUint16(6, true), tid: v.getUint32(8, true), payload: concat(parts).subarray(12) };
	}

	// Runs one operation: { code, params, data }, data null when there was no data phase.
	async transaction(code, params = [], send = null) {
		this.tid += 1;
		await this.t.write(container(CMD, code, this.tid, params));
		if (send)
			await this.sendData(code, send);
		let data = null;
		for (;;) {
			const c = await this.next();
			if (c.kind === EVENT)
				continue;
			if (c.kind === DATA) {
				if (c.tid !== this.tid)
					this.stale += 1;            // an earlier transaction's
				else
					data = c.payload;
				continue;
			}
			if (c.tid !== this.tid)
				throw new Failure('response to transaction ' + c.tid + ' during transaction ' + this.tid);
			const r = new Reader(c.payload);
			const out = [];
			for (let k = 0; k < Math.min(c.payload.length >> 2, 5); k++)
				out.push(r.num(4));
			return { code: c.code, params: out, data };
		}
	}

	async sendData(code, payload) {
		const blob = container(DATA, code, this.tid, [], payload);
		const step = CHUNK - CHUNK % this.t.mps;
		for (let off = 0; off < blob.length; off += step) {
			await this.t.write(blob.subarray(off, off + step));
			this.progress(off + step - 12, payload.length);
		}
		if (blob.length % this.t.mps === 0)
			await this.t.write(new Uint8Array(0));
	}

	async checked(name, code, params = [], send = null) {
		const r = await this.transaction(code, params, send);
		if (r.code !== OK)
			throw new Failure(name + ' answered ' + responseName(r.code));
		return r;
	}

	// An operation with a data phase from the device. OK without one is not an empty answer.
	async readOp(name, code, params = []) {
		const r = await this.checked(name, code, params);
		if (!r.data)
			throw new Failure(name + ' answered OK with no data phase');
		return r.data;
	}

	async openSession() {
		this.session += 1;
		const r = await this.transaction(OP.OPEN, [this.session]);
		if (r.code !== OK && r.code !== ALREADY_OPEN)
			throw new Failure('OpenSession answered ' + responseName(r.code));
	}

	async closeSession() {
		return (await this.transaction(OP.CLOSE)).code === OK;
	}

	async deviceInfo() {
		const r = new Reader(await this.readOp('GetDeviceInfo', OP.DEVICE_INFO));
		r.pos += 2 + 4 + 2;
		r.string();
		r.pos += 2;
		for (let k = 0; k < 5; k++)
			r.skipArray(2);
		return { manufacturer: r.string(), model: r.string(), version: r.string() };
	}

	async storage() {
		const r = new Reader(await this.readOp('GetStorageIDs', OP.STORAGE_IDS));
		if (r.num(4) === 0)
			throw new Failure('the unit presents no storage');
		return r.num(4);
	}

	async storageInfo(storage) {
		const r = new Reader(await this.readOp('GetStorageInfo', OP.STORAGE_INFO, [storage]));
		r.pos += 4;
		return { access: r.num(2), total: r.num(8), free: r.num(8) };
	}

	async listRoot(storage) {
		const r = new Reader(await this.readOp('GetObjectHandles', OP.HANDLES, [storage, 0, ROOT]));
		const out = [];
		for (let n = r.num(4); n > 0; n--) {
			const h = r.num(4);
			out.push(parseObject(h, await this.readOp('GetObjectInfo', OP.OBJECT_INFO, [h])));
		}
		return out;
	}

	async getObject(handle) {
		this.what = 'check';
		try {
			return await this.readOp('GetObject', OP.GET_OBJECT, [handle]);
		} finally {
			this.what = '';
		}
	}

	async sendFile(storage, name, content, modified) {
		const info = objectInfoDataset(storage, name, content.length, modified);
		// MTP 1.1's root; a responder that reads it as a handle gets 0, the other form.
		let r = await this.transaction(OP.SEND_INFO, [storage, ROOT], info);
		if (r.code === INVALID_HANDLE || r.code === INVALID_PARENT)
			r = await this.transaction(OP.SEND_INFO, [storage, 0], info);
		if (r.code !== OK)
			throw new Failure('SendObjectInfo answered ' + responseName(r.code));
		this.what = 'upload';
		try {
			await this.checked('SendObject', OP.SEND, [], content);
		} finally {
			this.what = '';
		}
	}
}

// ---- put: replace one file at the top of the volume and read it back ----

export async function sha256Hex(bytes) {
	const d = new Uint8Array(await globalThis.crypto.subtle.digest('SHA-256', bytes));
	return Array.from(d, (b) => b.toString(16).padStart(2, '0')).join('');
}

// YYYYMMDDTHHMMSS, in UTC.
export const mtpDate = (date) => date.toISOString().replace(/[-:]/g, '').slice(0, 15);

const named = (objects, name) => objects.filter((o) => o.name === name);

// Throws unless the one object of that name on the unit holds exactly `content`.
async function compare(mtp, storage, name, content, log) {
	const found = named(await mtp.listRoot(storage), name);
	if (!found.length)
		throw new Failure('/' + name + ' is not on the unit');
	if (found.length > 1)
		throw new Failure('/' + name + ' is listed ' + found.length + ' times');
	if (found[0].folder)
		throw new Failure('/' + name + ' is a folder');
	const back = await mtp.getObject(found[0].handle);
	let first = 0;
	const n = Math.min(back.length, content.length);
	while (first < n && back[first] === content[first])
		first++;
	if (first < n || back.length !== content.length || found[0].size !== content.length)
		throw new Failure('the copy on the unit does not match: sent ' + content.length + ' bytes, listed ' +
			found[0].size + ', read back ' + back.length + ', first difference at offset ' + first);
	const sha = await sha256Hex(back);
	log('Verified /' + name + ': ' + back.length + ' bytes read back, identical, sha256 ' + sha);
	return sha;
}

// Delete the old copy, upload `content` as /name, read it back from a new session and compare.
// Resolves { size, sha256 } only when the bytes on the unit are `content`.
export async function putFile(mtp, name, content, modified, log = () => {}) {
	if (!content.length)
		throw new Failure('the file is empty');
	if (content.length >= 2 ** 32)
		throw new Failure('the file is too large for MTP');

	await mtp.drain();
	const info = await mtp.deviceInfo();
	log(info.manufacturer + ' ' + info.model + ', bootloader ' + info.version);
	await mtp.openSession();
	const storage = await mtp.storage();
	const objects = await mtp.listRoot(storage);
	const space = await mtp.storageInfo(storage);
	log(objects.length + ' objects at the top, ' + space.free + ' bytes free of ' + space.total);
	const old = named(objects, name);
	if (space.total === 0)
		throw new Failure('the unit reports no volume: nothing was changed');
	if (space.access !== 0)
		throw new Failure('the unit’s volume is read-only: nothing was changed');
	if (old.some((o) => o.folder))
		throw new Failure('/' + name + ' is a folder on the unit: nothing was changed');
	if (content.length > space.free + old.reduce((n, o) => n + o.size, 0))
		throw new Failure(content.length + ' bytes do not fit in ' + space.free + ' free: nothing was changed');

	let changed = false;
	try {
		for (const o of old) {
			changed = true;
			await mtp.checked('DeleteObject', OP.DELETE, [o.handle, 0]);
			log('Deleted the old /' + name + ' (' + o.size + ' bytes)');
		}
		if (old.length && named(await mtp.listRoot(storage), name).length)
			throw new Failure('/' + name + ' is still listed after its delete');

		changed = true;
		log('Uploading /' + name + ', ' + content.length + ' bytes');
		await mtp.sendFile(storage, name, content, modified);

		// A session of its own, so that the read-back starts from a new listing.
		await mtp.closeSession();
		await mtp.openSession();
		const sha256 = await compare(mtp, storage, name, content, log);
		await mtp.closeSession();
		if (mtp.stale)
			log('Dropped ' + mtp.stale + ' data block(s) left from earlier transactions.');
		return { size: content.length, sha256 };
	} catch (e) {
		const fail = e instanceof Failure ? e : new Failure(e && e.message ? e.message : String(e));
		fail.changed = changed;
		throw fail;
	}
}

// ---- WebUSB ----

// { config, number, alt, epIn, epOut, mps } of a USBDevice's MTP function, or null.
export function findMtpInterface(device) {
	for (const cfg of device.configurations || [])
		for (const ifc of cfg.interfaces)
			for (const alt of ifc.alternates) {
				if (!MTP_CLASSES.some(([c, s, p]) => c === alt.interfaceClass && s === alt.interfaceSubclass &&
						p === alt.interfaceProtocol))
					continue;
				const bulk = (dir) => alt.endpoints.find((e) => e.type === 'bulk' && e.direction === dir);
				const i = bulk('in'), o = bulk('out');
				if (i && o)
					return { config: cfg.configurationValue, number: ifc.interfaceNumber, alt: alt.alternateSetting,
						epIn: i.endpointNumber, epOut: o.endpointNumber, mps: i.packetSize };
			}
	return null;
}

// The MTP interface's two bulk endpoints. read() ends at a short packet, as a bulk transfer does.
// WebUSB cannot cancel a transfer, so a read that timed out is kept and answers the next read.
export class UsbTransport {
	constructor(device, found) {
		this.dev = device;
		Object.assign(this, found);
		this.pending = null;
	}

	async open() {
		await this.dev.open();
		if (!this.dev.configuration || this.dev.configuration.configurationValue !== this.config)
			await this.dev.selectConfiguration(this.config);
		try {
			await this.dev.claimInterface(this.number);
		} catch (e) {
			throw new Failure('something else holds the unit’s MTP interface (' + (e && e.message) + '). Quit ' +
				'any MTP client (Android File Transfer, OpenMTP, Image Capture), and on the unit use the ' +
				'“mtp file transfer (mac)” item.');
		}
		if (this.alt)
			await this.dev.selectAlternateInterface(this.number, this.alt);
	}

	async timed(promise, ms) {
		let timer;
		const late = new Promise((res) => { timer = setTimeout(() => res(null), ms); });
		const got = await Promise.race([promise, late]);
		clearTimeout(timer);
		return got;
	}

	async read(size, ms) {
		if (!this.pending)
			this.pending = this.dev.transferIn(this.epIn, size).then((r) => ({ r }), (e) => ({ e }));
		const got = await this.timed(this.pending, ms);
		if (!got)
			throw new Timeout('the unit did not answer in time');
		this.pending = null;
		if (got.e)
			throw new Failure('USB read: ' + got.e.message);
		if (got.r.status === 'stall')
			await this.dev.clearHalt('in', this.epIn).catch(() => {});
		if (got.r.status !== 'ok')
			throw new Failure('USB read: ' + got.r.status);
		const d = got.r.data;
		return d ? new Uint8Array(d.buffer, d.byteOffset, d.byteLength) : new Uint8Array(0);
	}

	async write(data) {
		const got = await this.timed(this.dev.transferOut(this.epOut, data).then((r) => ({ r }), (e) => ({ e })),
			TIMEOUT_MS);
		if (!got)
			throw new Timeout('the unit did not take the data in time');
		if (got.e)
			throw new Failure('USB write: ' + got.e.message);
		if (got.r.status !== 'ok' || got.r.bytesWritten !== data.length)
			throw new Failure('USB write: ' + got.r.status + ', ' + got.r.bytesWritten + ' of ' + data.length + ' bytes');
	}

	async close() {
		await this.dev.releaseInterface(this.number).catch(() => {});
		await this.dev.close().catch(() => {});
	}
}

// What a USBDevice says of itself, for the log: its ids, names and interfaces. Not its serial number.
export function describeDevice(device) {
	const x = (n, w) => (n || 0).toString(16).padStart(w, '0');
	const rows = ['USB ' + x(device.vendorId, 4) + ':' + x(device.productId, 4) + '  ' +
		(device.manufacturerName || '?') + ' / ' + (device.productName || '?')];
	for (const cfg of device.configurations || [])
		for (const ifc of cfg.interfaces)
			for (const alt of ifc.alternates)
				rows.push('configuration ' + cfg.configurationValue + ', interface ' + ifc.interfaceNumber + ': ' +
					[alt.interfaceClass, alt.interfaceSubclass, alt.interfaceProtocol].map((n) => x(n, 2)).join('/') +
					' [' + alt.endpoints.map((e) => e.type + ' ' + e.direction).join(', ') + ']');
	return rows.join('\n');
}

// The devices the browser's list offers: the unit by its maker, or anything with an MTP interface,
// in case the unit shows another maker id in this mode.
const FILTERS = [{ vendorId: VID }].concat(MTP_CLASSES.map(([classCode, subclassCode, protocolCode]) =>
	({ classCode, subclassCode, protocolCode })));

// Find the unit offering MTP: one the browser already has leave to use, or else ask the user.
// With `every`, the browser's list shows every USB device, to see what the unit presents.
export async function openUnit(usb, log = () => {}, every = false) {
	let device = every ? null : (await usb.getDevices()).find((d) => findMtpInterface(d));
	if (!device) {
		try {
			device = await usb.requestDevice({ filters: every ? [] : FILTERS });
		} catch (e) {
			const none = new Failure(e && e.name === 'NotFoundError' ?
				'no unit was chosen. If the browser’s list was empty, the unit is not showing an MTP device on ' +
				'this computer’s USB: check that its screen shows MTP file transfer and that the cable goes to ' +
				'this computer.' : 'the browser did not give the unit: ' + (e && e.message));
			none.notChosen = true;
			throw none;
		}
	}
	log(describeDevice(device));
	const found = findMtpInterface(device);
	if (!found)
		throw new Failure((device.productName || 'that device') + ' is not offering MTP. On the unit press ' +
			'“3. dev menu”, then “2. mtp file transfer (mac)”.');
	const t = new UsbTransport(device, found);
	try {
		await t.open();
	} catch (e) {
		await t.close();
		throw e instanceof Failure ? e : new Failure('cannot open the unit on USB: ' + (e && e.message));
	}
	return t;
}
