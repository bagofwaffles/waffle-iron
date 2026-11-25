// Checks the MTP copy against a stand-in unit: what it sends, what it refuses, what it proves.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { Mtp, putFile, mtpString, objectInfoDataset, findMtpInterface, describeDevice, openUnit, sha256Hex,
	mtpDate, OP }
	from '../docs/mtp.js';
import { FakeUnit } from '../docs/mtpfake.js';
import { parseRelease, identify } from '../docs/release.js';

const bytes = (n, seed = 1) => Uint8Array.from({ length: n }, (_, i) => (i * 31 + seed) & 0xFF);
const put = (unit, content) => putFile(new Mtp(unit), 'os.ldr', content, '20261123T000000');

test('strings and the ObjectInfo dataset have the wire layout', () => {
	assert.deepEqual([...mtpString('')], [0]);
	assert.deepEqual([...mtpString('os')], [3, 0x6F, 0, 0x73, 0, 0, 0]);
	const d = objectInfoDataset(0x00010001, 'os.ldr', 0x1234, '20261123T000000');
	assert.deepEqual([...d.subarray(0, 12)], [1, 0, 1, 0, 0x00, 0x30, 0, 0, 0x34, 0x12, 0, 0]);
	assert.equal(d[52], 7);
	assert.equal(mtpDate(new Date(Date.UTC(2026, 10, 23, 6, 5, 4))), '20261123T060504');
});

test('put replaces an old os.ldr and reads the new one back', async () => {
	const unit = new FakeUnit({ files: { 'os.ldr': bytes(5000, 9), 'keep.txt': bytes(10) }, folders: ['user'] });
	const content = bytes(200000);
	const r = await put(unit, content);
	assert.deepEqual(r, { size: 200000, sha256: await sha256Hex(content) });
	assert.deepEqual(unit.file('os.ldr'), content);
	assert.deepEqual(unit.file('keep.txt'), bytes(10));
	assert.equal(unit.ops.filter((op) => op === OP.DELETE).length, 1);
	assert.ok(unit.ops.every((op) => Object.values(OP).includes(op)));
});

test('the device information is read past its arrays', async () => {
	const mtp = new Mtp(new FakeUnit({ arrays: 3 }));
	assert.deepEqual(await mtp.deviceInfo(),
		{ manufacturer: 'teenage engineering', model: 'OP-XY (stand-in)', version: '0.0.0' });
});

test('put works when there is no os.ldr yet, and when the container fills whole packets', async () => {
	const unit = new FakeUnit();
	const content = bytes(512 * 4 - 12);        // header and payload end on a packet boundary
	await put(unit, content);
	assert.deepEqual(unit.file('os.ldr'), content);
	assert.ok(!unit.ops.includes(OP.DELETE));
});

test('a data container left from an earlier transaction is dropped', async () => {
	const unit = new FakeUnit({ stale: true });
	await put(unit, bytes(3000));
	assert.deepEqual(unit.file('os.ldr'), bytes(3000));
});

test('nothing is changed on a read-only store, a full one, or a folder named os.ldr', async () => {
	const old = bytes(5000, 9);
	for (const o of [{ files: { 'os.ldr': old }, access: 1 }, { files: { 'os.ldr': old }, free: 100 },
		{ folders: ['os.ldr'] }]) {
		const unit = new FakeUnit(o);
		await assert.rejects(put(unit, bytes(200000)), (e) => /nothing was changed/.test(e.message) && !e.changed);
		assert.ok(!unit.ops.includes(OP.DELETE) && !unit.ops.includes(OP.SEND_INFO));
	}
	await assert.rejects(put(new FakeUnit(), new Uint8Array(0)), /empty/);
});

test('a copy that reads back differently fails, and says the unit was changed', async () => {
	const unit = new FakeUnit({ files: { 'os.ldr': bytes(5000, 9) }, corrupt: true });
	await assert.rejects(put(unit, bytes(200000)),
		(e) => /does not match/.test(e.message) && /offset 100000/.test(e.message) && e.changed === true);
});

test('the MTP interface is found by its class, vendor or standard', () => {
	const ep = (direction, n) => ({ type: 'bulk', direction, endpointNumber: n, packetSize: 512 });
	const alt = (c, s, p, endpoints) => ({ alternateSetting: 0, interfaceClass: c, interfaceSubclass: s,
		interfaceProtocol: p, endpoints });
	const dev = (...alts) => ({ configurations: [{ configurationValue: 1,
		interfaces: alts.map((a, k) => ({ interfaceNumber: k, alternates: [a] })) }] });
	assert.equal(findMtpInterface(dev(alt(1, 3, 0, [ep('in', 7), ep('out', 8)]))), null);
	assert.deepEqual(findMtpInterface(dev(alt(1, 1, 0, []), alt(0xFF, 1, 1, [ep('out', 2), ep('in', 1)]))),
		{ config: 1, number: 1, alt: 0, epIn: 1, epOut: 2, mps: 512 });
	assert.equal(findMtpInterface(dev(alt(6, 1, 1, [ep('in', 1), ep('out', 2)]))).number, 0);
});

test('the unit is asked for by maker or by MTP class, and an empty list is explained', async () => {
	let asked = null;
	const usb = { getDevices: async () => [], requestDevice: async (o) => {
		asked = o.filters;
		throw Object.assign(new Error('none'), { name: 'NotFoundError' });
	} };
	await assert.rejects(openUnit(usb), (e) => e.notChosen && /list was empty/.test(e.message));
	assert.deepEqual(asked, [{ vendorId: 0x2367 }, { classCode: 6, subclassCode: 1, protocolCode: 1 },
		{ classCode: 0xFF, subclassCode: 1, protocolCode: 1 }]);
	await assert.rejects(openUnit(usb, () => {}, true), (e) => e.notChosen);
	assert.deepEqual(asked, []);

	const midi = { vendorId: 0x2367, productId: 0x21, manufacturerName: 'te', productName: 'OP-XY Boot',
		configurations: [{ configurationValue: 1, interfaces: [{ interfaceNumber: 1, alternates: [
			{ interfaceClass: 1, interfaceSubclass: 3, interfaceProtocol: 0,
				endpoints: [{ type: 'bulk', direction: 'out' }, { type: 'bulk', direction: 'in' }] }] }] }] };
	assert.equal(describeDevice(midi),
		'USB 2367:0021  te / OP-XY Boot\nconfiguration 1, interface 1: 01/03/00 [bulk out, bulk in]');
	const lines = [];
	await assert.rejects(openUnit({ getDevices: async () => [], requestDevice: async () => midi }, (t) => lines.push(t)),
		/OP-XY Boot is not offering MTP/);
	assert.equal(lines.length, 1);
});

test('a release is read, and a file is known by its SHA-256', () => {
	const rel = parseRelease({ tag_name: 'v1', assets: [
		{ name: 'waffle-install.ldr', size: 5, digest: 'sha256:aa', browser_download_url: 'u' },
		{ name: 'waffle-boot.ldr', size: 6, digest: 'sha256:bb', browser_download_url: 'v' },
		{ name: 'SHA256SUMS', size: 1, browser_download_url: 'w' }] });
	assert.deepEqual(identify(rel, 'aa'), { tag: 'v1', name: 'waffle-install.ldr' });
	assert.equal(identify(rel, 'bb').name, 'waffle-boot.ldr');
	assert.equal(identify(rel, 'cc'), null);
	assert.equal(identify(null, 'aa'), null);
});
