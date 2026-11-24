// SPDX-License-Identifier: GPL-2.0-or-later
//
// A stand-in unit for mtp.js: an MTP responder in memory, with the transport's write(), read()
// and mps. The tests drive it, and on localhost ?demo= copies to it instead of a real unit.
//
//     new FakeUnit({ files: { 'os.ldr': bytes }, folders: ['user'], free, access, corrupt, stale })
//
// corrupt flips a byte of whatever is stored; stale leaves a data container from an earlier
// transaction in the queue; access other than 0 is a read-only store.

import { Timeout, Reader, container, concat, mtpString, OP, OK, ROOT, FORMAT_FOLDER, FORMAT_UNDEFINED }
	from './mtp.js';

const CMD = 1, DATA = 2, RESP = 3;
const STORAGE = 0x00010001;
const u16 = (n) => Uint8Array.of(n & 0xFF, n >> 8);
const u32 = (n) => Uint8Array.of(n & 0xFF, (n >> 8) & 0xFF, (n >> 16) & 0xFF, n >>> 24);
const u64 = (n) => concat([u32(n % 2 ** 32), u32(Math.floor(n / 2 ** 32))]);

export class FakeUnit {
	constructor(o = {}) {
		this.mps = 512;
		this.o = o;
		this.total = 64 << 20;
		this.free = o.free === undefined ? 32 << 20 : o.free;
		this.objects = new Map();
		this.nextHandle = 1;
		this.ops = [];                  // every operation code received, in order
		this.inq = [];                  // packets waiting for read()
		this.buf = new Uint8Array(0);
		this.cmd = null;                // a command waiting for its data phase
		this.pendingInfo = null;
		for (const name of o.folders || [])
			this.add(name, new Uint8Array(0), true);
		for (const [name, data] of Object.entries(o.files || {}))
			this.add(name, data, false);
		if (o.stale)
			this.queue(container(DATA, OP.GET_OBJECT, 999, [], new Uint8Array(40)));
	}

	add(name, data, folder) {
		this.objects.set(this.nextHandle, { name, data, folder, modified: '20260101T000000' });
		return this.nextHandle++;
	}
	file(name) {
		for (const o of this.objects.values())
			if (o.name === name)
				return o.data;
		return null;
	}

	// One container becomes the packets a bulk pipe would carry: full ones, then a short one.
	queue(bytes) {
		for (let off = 0; off < bytes.length; off += 65536)
			this.inq.push(bytes.subarray(off, off + 65536));
		if (bytes.length % this.mps === 0)
			this.inq.push(new Uint8Array(0));
	}
	respond(tid, code, params = []) {
		this.queue(container(RESP, code, tid, params));
	}
	data(code, tid, payload) {
		this.queue(container(DATA, code, tid, [], payload));
		this.respond(tid, OK);
	}

	async read() {
		if (this.o.delay)
			await new Promise((r) => setTimeout(r, this.o.delay));
		if (!this.inq.length)
			throw new Timeout('the stand-in has nothing to say');
		return this.inq.shift();
	}

	async write(bytes) {
		if (this.o.delay)
			await new Promise((r) => setTimeout(r, this.o.delay));
		this.buf = concat([this.buf, bytes]);
		while (this.buf.length >= 12) {
			const total = new DataView(this.buf.buffer, this.buf.byteOffset).getUint32(0, true);
			if (this.buf.length < total)
				return;
			const one = this.buf.subarray(0, total);
			this.buf = this.buf.slice(total);
			this.take(one);
		}
	}

	take(c) {
		const r = new Reader(c);
		r.num(4);
		const kind = r.num(2), code = r.num(2), tid = r.num(4);
		if (kind === CMD) {
			const params = [];
			while (r.pos + 4 <= c.length)
				params.push(r.num(4));
			this.ops.push(code);
			if (code === OP.SEND_INFO || code === OP.SEND)
				this.cmd = { code, tid, params };
			else
				this.run(code, tid, params);
		} else if (kind === DATA && this.cmd && this.cmd.tid === tid) {
			const cmd = this.cmd;
			this.cmd = null;
			this.run(cmd.code, tid, cmd.params, c.subarray(12));
		}
	}

	run(code, tid, p, sent) {
		const obj = this.objects.get(p[0]);
		if (code === OP.DEVICE_INFO) {
			this.data(code, tid, concat([u16(100), u32(6), u16(100), mtpString(''), u16(0),
				...Array.from({ length: 5 }, () => concat([u32(this.o.arrays || 0),
					...Array.from({ length: this.o.arrays || 0 }, () => u16(0x1001))])),
				mtpString('teenage engineering'), mtpString('OP-XY (stand-in)'), mtpString('0.0.0'), mtpString('')]));
		} else if (code === OP.OPEN || code === OP.CLOSE) {
			this.respond(tid, OK);
		} else if (code === OP.STORAGE_IDS) {
			this.data(code, tid, concat([u32(1), u32(STORAGE)]));
		} else if (code === OP.STORAGE_INFO) {
			this.data(code, tid, concat([u16(3), u16(2), u16(this.o.access || 0), u64(this.total), u64(this.free),
				u32(0xFFFFFFFF), mtpString('yaffs2'), mtpString('')]));
		} else if (code === OP.HANDLES) {
			const handles = p[2] === ROOT || p[2] === 0 ? [...this.objects.keys()] : [];
			this.data(code, tid, concat([u32(handles.length), ...handles.map(u32)]));
		} else if (code === OP.OBJECT_INFO && obj) {
			const head = new Uint8Array(52);
			const v = new DataView(head.buffer);
			v.setUint32(0, STORAGE, true);
			v.setUint16(4, obj.folder ? FORMAT_FOLDER : FORMAT_UNDEFINED, true);
			v.setUint32(8, obj.data.length, true);
			this.data(code, tid, concat([head, mtpString(obj.name), mtpString(obj.modified),
				mtpString(obj.modified), mtpString('')]));
		} else if (code === OP.GET_OBJECT && obj) {
			this.data(code, tid, obj.data);
		} else if (code === OP.DELETE && obj) {
			this.free += obj.data.length;
			this.objects.delete(p[0]);
			this.respond(tid, OK);
		} else if (code === OP.SEND_INFO) {
			const r = new Reader(sent);
			r.pos = 8;
			const size = r.num(4);
			r.pos = 52;
			this.pendingInfo = { name: r.string(), size };
			this.respond(tid, OK, [STORAGE, ROOT, this.nextHandle]);
		} else if (code === OP.SEND && this.pendingInfo) {
			const data = sent.slice();
			if (this.o.corrupt)
				data[data.length >> 1] ^= 0x01;
			this.free -= data.length;
			this.add(this.pendingInfo.name, data, false);
			this.pendingInfo = null;
			this.respond(tid, OK);
		} else {
			this.respond(tid, 0x2009);
		}
	}

	async close() {}
}
