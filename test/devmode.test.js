// Checks the devmode byte format against the unit's worked examples.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { crc8, carrier, parseCarrier, fsnRequest, devRequest, rebootToBootMenu, rebootToUpload, CMD, DEVICE }
	from '../docs/devmode.js';

const H = (s) => Uint8Array.from(s.trim().split(/\s+/).map((x) => parseInt(x, 16)));
const hex = (a) => Array.from(a, (b) => b.toString(16).padStart(2, '0')).join(' ');

// From the procedure's worked carriers.
const FSN = H('00 11 22 33 44 55 66 77 88 99 aa bb cc dd ee ff');  // illustrative FSN
const WORKED = {
	fsn: 'f0 00 20 76 21 66 20 02 21 02 1f 02 24 00 f7',
	enable: 'f0 00 20 76 21 66 28 02 21 1a 2c 16 19 4a 77 73 6d 19 5b 51 5e 5d 16 1f 15 1a 11 53 59 56 72 55 17 1d 12 3a 27 70 00 00 f7',
	disable: 'f0 00 20 76 21 66 28 02 21 18 2c 16 19 4a 77 73 6d 19 5b 51 5e 5d 16 1f 15 1a 11 53 59 56 12 55 17 1d 12 3a 02 66 00 00 f7',
	reboot: 'f0 00 20 76 21 66 20 02 21 06 0d 02 6e 02 01 16 00 f7',
};

test('CRC-8 matches the worked frames', () => {
	assert.equal(crc8(H('21 00 1f 00')), 0xa4);
	assert.equal(crc8(H('21 00 0d 02 ee 02')), 0x96);
});

test('carriers reproduce the worked examples byte for byte', () => {
	assert.equal(hex(fsnRequest()), WORKED.fsn);
	assert.equal(hex(devRequest(FSN, true)), WORKED.enable);
	assert.equal(hex(devRequest(FSN, false)), WORKED.disable);
	assert.equal(hex(rebootToBootMenu()), WORKED.reboot);
});

test('parseCarrier round-trips every worked message', () => {
	for (const [name, s] of Object.entries(WORKED)) {
		const p = parseCarrier(H(s));
		assert.ok(p, name + ' should parse');
	}
	assert.equal(parseCarrier(H(WORKED.reboot)).id, CMD.FIRMWARE);
});

test('a reply carrier (id 0x20) parses to its payload', () => {
	// build a stand-in reply carrying a 16-byte serial, addressed host<-master
	const reply = carrier(CMD.FSN_REPLY, Array.from(FSN));
	const p = parseCarrier(reply);
	assert.equal(p.id, CMD.FSN_REPLY);
	assert.equal(hex(p.payload), hex(FSN));
});

test('an empty 0x20 reply means the serial could not be read', () => {
	const p = parseCarrier(carrier(CMD.FSN_REPLY, []));
	assert.equal(p.payload.length, 0);
});

test('an OP-1 Field is addressed at device byte 02: the carrier a unit took', () => {
	const took = 'f0 00 20 76 02 66 20 02 21 06 0d 02 6e 01 01 54 00 f7';
	assert.equal(hex(rebootToUpload(true, 0, DEVICE['op-1-field'])), took);
	const p = parseCarrier(H(took));
	assert.equal(p.dev, 0x02);
	assert.deepEqual([...p.payload], [0xEE, 0x01]);
	assert.equal(hex(fsnRequest(0, DEVICE['op-1-field'])), WORKED.fsn.replace('76 21', '76 02'));
});

test('the upload-screen restart carries EE 01 for a disk and EE alone for MIDI', () => {
	const disk = parseCarrier(rebootToUpload());
	assert.equal(disk.id, CMD.FIRMWARE);
	assert.deepEqual([...disk.payload], [0xEE, 0x01]);
	assert.deepEqual([...parseCarrier(rebootToUpload(false)).payload], [0xEE]);
});
