// SPDX-License-Identifier: GPL-2.0-or-later
//
// The page asks for MIDI on its own and watches for the unit's port. With a unit found, the user
// chooses to install waffle-boot or to set developer mode. Installing restarts the unit into the
// bootloader's upload screen as a USB disk, and the page makes the firmware.zip to copy there.
// Developer mode is written from the boot menu, which the page restarts the unit into before and
// after. What the page sends and hears is logged in the browser's console; the serial number is
// never shown or logged, and neither is a message that carries it. On localhost, ?demo=NAME stands
// in for a unit without touching real MIDI.

import { parseCarrier, fsnRequest, devRequest, rebootToBootMenu, rebootToUpload, CMD, DEVICE } from './devmode.js';
import { Mtp, putFile, openUnit, sha256Hex, mtpDate } from './mtp.js';
import { FakeUnit } from './mtpfake.js';
import { INSTALLER, RELEASES, latestRelease, commitOf, publishedCopy, identify } from './release.js';
import { firmwareZip, versionLine } from './fwzip.js';

const UNITS = {
	'op-xy': { name: 'OP-XY', boot: 'com', ferret: 'https://bagofwaffles.github.io/ferret/op-xy/', disk: 'OP-XY',
		tfw: ['https://teenage.engineering/_software/op-xy/opxy_content_snaps_1_0_0.tfw', 'Download the .tfw'] },
	'op-1-field': { name: 'OP-1 Field', boot: 'com', ferret: 'https://bagofwaffles.github.io/ferret/op-1f/', disk: 'OP-1',
		tfw: ['https://teenage.engineering/_software/op-1/field/op1_field_firmware_1_7_3+1.tfw', 'Download the .tfw'],
		more: ['https://teenage.engineering/downloads/op-1/field', 'pick another from Teenage Engineering’s downloads'] },
};
// Which unit a MIDI port names.
function unitOf(name) {
	if (/op.?1/i.test(name))
		return 'op-1-field';
	if (/op.?xy/i.test(name))
		return 'op-xy';
	return null;
}
// The device byte the unit in hand answers to; an unnamed one is tried as an OP-XY.
const devByte = () => DEVICE[state.unit] || DEVICE['op-xy'];
const isUnit = (p) => /op.?xy|op.?1|teenage/i.test(p.name + ' ' + (p.manufacturer || ''));

const hex = (n, w) => (n === undefined || n === null ? '?'.repeat(w) : n.toString(16).padStart(w, '0'));
const wait = (ms) => new Promise((r) => setTimeout(r, ms));
const bytesHex = (b) => Array.from(b, (x) => hex(x, 2)).join(' ');
const bytesText = (b) => Array.from(b, (x) => (x >= 0x20 && x < 0x7F ? String.fromCharCode(x) : '.')).join('');

// ---- the page scaffolding ----

const $ = (id) => document.getElementById(id);

// h('p.note', 'text', node, { attr }): an element with classes, attributes and children.
function h(spec, ...kids) {
	const [tag, ...cls] = spec.split('.');
	const e = document.createElement(tag || 'div');
	if (cls.length)
		e.className = cls.join(' ');
	for (const k of kids.flat()) {
		if (k === null || k === undefined || k === false)
			continue;
		if (typeof k === 'object' && !(k instanceof Node)) {
			for (const [a, v] of Object.entries(k)) {
				if (a.startsWith('on'))
					e.addEventListener(a.slice(2), v);
				else if (v === true)
					e.setAttribute(a, '');
				else if (v !== false && v !== null && v !== undefined)
					e.setAttribute(a, v);
			}
		} else {
			e.append(k);
		}
	}
	return e;
}
const link = (href, text) => h('a', { href, target: '_blank', rel: 'noopener' }, text);

// The log goes to the browser's own console.
function log(text) {
	console.log(new Date().toTimeString().slice(0, 8) + '  ' + text);
}

const art = { svg: {} };
function unitDrawing(unit) {
	const box = h('figure');
	box.innerHTML = art.svg[unit] || '';
	return box;
}

// ---- stand-in states, for localhost ----

const DEMOS = {
	none: { phase: 'no-unit' },
	present: { phase: 'present', unit: 'op-xy' },
	field: { phase: 'present', unit: 'op-1-field' },
	boot: { phase: 'boot', unit: 'op-xy' },
	'field-boot': { phase: 'boot', unit: 'op-1-field' },
	nomidi: { phase: 'nomidi' },
};
const demo = ['localhost', '127.0.0.1'].includes(location.hostname) &&
	DEMOS[new URLSearchParams(location.search).get('demo')];

// ---- MIDI: find the unit, see whether it is in the boot menu, restart it ----

const state = { phase: 'init', unit: null, busy: false, note: '', step: 1, focus: false,
	mode: null,          // what the user chose to do with the unit: 'install' or 'dev'
	release: null,       // the latest release, once GitHub has answered
	own: false,          // firmware.zip is made from the user's own .ldr, not the release
	zip: {},             // firmware.zip for the upload disk: { url, size, version, text }
	inst: {},            // the installer to copy: { bytes, sha256, title, text, link, bad, looking }
	copy: {} };          // the copy to the unit: { busy, text, done, total, failed, changed, ok }
// Move on to a step, and have the next render put the focus on its heading.
function goStep(n) {
	state.step = n;
	state.focus = true;
	if (n >= 2 && !state.own && !state.inst.bytes && !state.inst.looking)
		findInstaller();
}
let midi = null;         // the MIDIAccess
let scanning = 0;        // guards overlapping scans
const pending = [];      // waiters for a reply of a given command id

// Every matching input routes here: log it, and wake any waiter for that reply.
function onMidi(m) {
	if (m.data[0] !== 0xF0)
		return;
	const p = parseCarrier(m.data);
	log('MIDI in: ' + (p && p.id === CMD.FSN_REPLY ? 'the serial number, not shown' : bytesHex(m.data)) +
		(p ? '  (id ' + hex(p.id, 2) + ', ' + p.payload.length + ' bytes)' : ''));
	if (!p)
		return;
	for (let i = pending.length - 1; i >= 0; i--)
		if (pending[i].id === p.id) {
			pending[i].resolve(p);
			pending.splice(i, 1);
		}
}
function expect(id, ms) {
	return new Promise((resolve) => {
		const w = { id, resolve };
		pending.push(w);
		setTimeout(() => {
			const i = pending.indexOf(w);
			if (i >= 0) {
				pending.splice(i, 1);
				resolve(null);
			}
		}, ms);
	});
}
function unitPorts() {
	const list = (map) => [...map.values()].filter(isUnit);
	return { ins: list(midi.inputs), outs: list(midi.outputs) };
}
function send(outs, bytes, what, secret = false) {
	log('MIDI out' + (what ? ' (' + what + ')' : '') + ': ' + (secret ? bytes.length + ' bytes, not shown' : bytesHex(bytes)));
	for (const p of outs)
		p.send(Array.from(bytes));
}

async function startMidi() {
	if (!navigator.requestMIDIAccess) {
		state.phase = 'nomidi';
		state.note = 'This browser has no Web MIDI. Use Chrome or Edge on a computer.';
		render();
		return;
	}
	try {
		log('Asking the browser for MIDI with system-exclusive messages.');
		midi = await navigator.requestMIDIAccess({ sysex: true });
	} catch (e) {
		state.phase = 'nomidi';
		state.note = 'MIDI access was declined. Allow it to look for the unit.';
		log('MIDI: ' + (e && e.message ? e.message : e));
		render();
		return;
	}
	midi.onstatechange = (e) => {
		log('MIDI port ' + e.port.state + ': ' + e.port.type + ' "' + e.port.name + '".');
		scan();
	};
	scan();
}

// Look for the unit's port; if it is there, ask whether it is in the boot menu.
async function scan() {
	if (demo || state.busy)
		return;
	const run = ++scanning;
	const { ins, outs } = unitPorts();
	for (const p of [...midi.inputs.values()])
		p.onmidimessage = isUnit(p) ? onMidi : null;
	await Promise.all(ins.map((p) => p.open().catch(() => {})));

	if (!ins.length || !outs.length) {
		state.phase = 'no-unit';
		if (state.step === 1)
			state.unit = null;              // later steps keep it: the upload disk has no MIDI port
		render();
		return;
	}
	state.unit = unitOf(ins.concat(outs).map((p) => p.name).join(' ')) || state.unit;
	// A serial-number read is answered only once the unit is in the boot menu (held mode).
	send(outs, fsnRequest(0, devByte()), 'read serial number');
	const got = await expect(CMD.FSN_REPLY, 1500);
	if (run !== scanning)
		return;                                   // a newer scan took over
	if (got && got.payload.length === 16) {
		state.phase = 'boot';
		log('The unit is in the boot menu (serial number read, 16 bytes, not shown).');
	} else {
		state.phase = 'present';
	}
	render();
}

// The restarts the page can ask for over the unit's USB MIDI port: [what the log calls it, the message].
const RESTART = {
	disk: ['the upload screen as a USB disk', () => rebootToUpload(true, 0, devByte())],
};
// Ask the unit to restart into one of them. The boot menu takes
// this; whether the OS does is what the button is there to find out. Anything the unit answers is
// logged by onMidi.
async function restart(kind) {
	const [how, message] = RESTART[kind];
	const from = state.phase === 'boot' ? 'the boot menu' : 'its OS';
	if (demo) {
		log('Demo: would ask for a restart into ' + how + ' while the unit is in ' + from + '.');
		state.note = 'Demo: nothing was sent.';
		if (kind === 'disk') {
			state.note = '';
			goStep(2);
		}
		render();
		return;
	}
	state.busy = true;
	state.note = '';
	render();
	try {
		const { ins, outs } = unitPorts();
		if (!outs.length)
			throw new Error('the unit’s MIDI port is not here.');
		for (const p of ins)
			p.onmidimessage = onMidi;
		await Promise.all(ins.map((p) => p.open().catch(() => {})));
		log('Restart into ' + how + ' asked while the unit is in ' + from + ', device byte ' + hex(devByte(), 2) + '.');
		send(outs, message(), 'restart into ' + how);
		await wait(500);
		state.note = 'The restart command was sent while the unit was in ' + from + '. If the unit took it, it ' +
			'restarts into ' + how + '. If nothing happens on the unit, it did not take the command.';
		if (kind === 'disk') {
			state.note = '';
			goStep(2);
		}
	} catch (e) {
		log('Restart: ' + (e && e.name ? e.name + ': ' : '') + (e && e.message ? e.message : e));
		state.note = 'The restart command was not sent: ' + (e && e.message ? e.message : e);
	}
	state.busy = false;
	render();
	scan();
}

// The unit's serial number, which only the boot menu gives: 16 bytes, or null.
async function readSerial() {
	const { ins, outs } = unitPorts();
	if (!ins.length || !outs.length)
		return null;
	for (const p of ins)
		p.onmidimessage = onMidi;
	await Promise.all(ins.map((p) => p.open().catch(() => {})));
	send(outs, fsnRequest(0, devByte()), 'read serial number');
	const got = await expect(CMD.FSN_REPLY, 1500);
	return got && got.payload.length === 16 ? got.payload : null;
}

// Turn developer mode on or off. The boot menu takes the change, so the unit is restarted into it
// first when it is not there, and again afterwards so its screen shows the new state.
async function setDev(on) {
	const word = on ? 'on' : 'off';
	if (demo) {
		log('Demo: would turn developer mode ' + word + ' and restart into the boot menu.');
		state.note = 'Demo: nothing was sent.';
		render();
		return;
	}
	state.busy = true;
	state.note = 'Turning developer mode ' + word + '.';
	render();
	try {
		let fsn = await readSerial();
		if (!fsn) {
			const { outs } = unitPorts();
			if (!outs.length)
				throw new Error('the unit’s MIDI port is not here.');
			send(outs, rebootToBootMenu(0, devByte()), 'restart into the boot menu');
			state.note = 'Restarting the unit into its boot menu.';
			render();
			for (const end = Date.now() + 40000; !fsn && Date.now() < end;) {
				await wait(1000);
				fsn = await readSerial();
			}
			if (!fsn)
				throw new Error('the unit did not come back in its boot menu.');
		}
		log('The unit is in the boot menu (serial number read, 16 bytes, not shown).');
		const { outs } = unitPorts();
		send(outs, devRequest(fsn, on, 0, devByte()), 'developer mode ' + word, true);
		await wait(500);
		send(outs, rebootToBootMenu(0, devByte()), 'restart into the boot menu');
		await wait(500);
		state.note = 'Developer mode is ' + word + '. The unit restarts into its boot menu.';
	} catch (e) {
		log('Developer mode: ' + (e && e.message ? e.message : e));
		state.note = 'Developer mode was not changed: ' + (e && e.message ? e.message : e);
	}
	state.busy = false;
	render();
	scan();
}

// ---- the installer: the latest release's, or the user's own file ----

const count = (n) => n.toLocaleString('en-US');

async function findInstaller() {
	const name = INSTALLER;
	state.inst = { looking: true };
	render();
	let rel = null, copy = null;
	try {
		rel = await latestRelease();
		log('The latest waffle-boot release is ' + rel.tag + '.');
	} catch (e) {
		log('Release lookup: ' + (e && e.message ? e.message : e));
	}
	state.release = rel;
	try {
		copy = await publishedCopy(name);
	} catch (e) {
		log('Published installer: ' + (e && e.message ? e.message : e));
	}
	if (state.inst.bytes || state.own)
		return;                                   // the user chose their own file meanwhile
	const want = rel && rel.assets[name];
	if (copy && want && want.sha256 === copy.sha256) {
		state.inst = { bytes: copy.bytes, sha256: copy.sha256, title: name + ' from release ' + rel.tag,
			text: 'Its SHA-256 is the one GitHub lists for the release.' };
	} else {
		state.inst = want ?
			{ text: 'The page could not get ' + name + ' of release ' + rel.tag + ' by itself. Download it, ' +
				'then choose the file.', link: [want.url, 'Download ' + name + ' (' + rel.tag + ')'] } :
			{ text: 'The latest release' + (rel ? ' (' + rel.tag + ')' : '') + ' has no ' + name +
				'. Download one from an earlier waffle-boot release, then choose the file.', link: [RELEASES, 'waffle-boot releases'] };
	}
	await makeZip(async () => {
		return versionLine(rel.tag, ((await commitOf(rel.tag)) || '').slice(0, 8));
	}, (version) => 'The waffle-boot installer (v' + version.split('+')[0] + ')');
	log(state.inst.bytes ? 'Installer: ' + state.inst.title + ', ' + state.inst.bytes.length + ' bytes, sha256 ' +
		state.inst.sha256 + '.' : 'Installer: waffle-boot does not publish one the page can read for the latest release.');
	render();
}

// What the packager names an image of no known release.
const OWN_VERSION = '0.0.1+0@50bc4cef';

// firmware.zip from the installer the page holds. version() gives its version line; label(version)
// is what the page says the zip holds.
async function makeZip(version, label) {
	if (state.zip.url)
		URL.revokeObjectURL(state.zip.url);
	state.zip = {};
	if (!state.inst.bytes) {
		state.zip = { text: state.inst.text || 'The page has no copy of the latest installer, so it cannot make firmware.zip.' };
		return;
	}
	if (state.inst.bad) {
		state.zip = { text: state.inst.text };
		return;
	}
	try {
		version = await version();
		const bytes = await firmwareZip(state.inst.bytes, version);
		state.zip = { url: URL.createObjectURL(new Blob([bytes], { type: 'application/zip' })), size: bytes.length,
			version, label: label(version) };
		log('firmware.zip: ' + bytes.length + ' bytes, version ' + version + ', os.ldr sha256 ' + state.inst.sha256 + '.');
	} catch (e) {
		log('firmware.zip: ' + (e && e.message ? e.message : e));
		state.zip = { text: 'firmware.zip could not be made: ' + (e && e.message ? e.message : e) };
	}
}

// Which image firmware.zip is made from: the latest release's, or a file the user gives.
function setOwn(own) {
	if (state.own === own)
		return;
	state.own = own;
	if (state.zip.url)
		URL.revokeObjectURL(state.zip.url);
	state.inst = {};
	state.zip = own ? { text: 'choose a .ldr file.', label: 'Your own file' } : {};
	if (own)
		render();
	else
		findInstaller();
}
// One choice of several, as a row of buttons: [label, chosen, onclick] each.
const seg = (...options) => h('span.seg', options.map(([label, on, onclick]) =>
	h('button', { type: 'button', 'aria-pressed': on ? 'true' : 'false', onclick }, label)));

async function takeFile(file) {
	const bytes = new Uint8Array(await file.arrayBuffer());
	if (!bytes.length) {
		state.inst = { bad: true, text: file.name + ' is empty.' };
		state.zip = { text: state.inst.text };
		render();
		return;
	}
	const sha256 = await sha256Hex(bytes);
	const id = identify(state.release, sha256);
	state.inst = { bytes, sha256, modified: new Date(file.lastModified),
		title: id ? id.name + ' from release ' + id.tag : file.name + ', your own file',
		text: id ? 'Its SHA-256 is the one GitHub lists for the release.' :
			'This is not a file of the latest release' + (state.release ? ' (' + state.release.tag + ')' : '') +
			'. It is copied as it is.' };
	if (id && id.name !== INSTALLER) {
		state.inst.bad = true;
		state.inst.text = 'This is ' + id.name + ' of release ' + id.tag + ', not the installer. Choose ' + INSTALLER + '.';
	}
	state.copy = {};
	log('Installer: ' + state.inst.title + ', ' + bytes.length + ' bytes, sha256 ' + sha256 + '.');
	await makeZip(async () => (id ? versionLine(id.tag, (await commitOf(id.tag)).slice(0, 8)) : OWN_VERSION),
		(version) => (id ? 'The waffle-boot installer (v' + version.split('+')[0] + ')' : 'Your own file, ' + file.name));
	render();
}
const pick = h('input', { type: 'file', accept: '.ldr', hidden: true, onchange: (e) => {
	if (e.target.files[0])
		takeFile(e.target.files[0]);
	e.target.value = '';
} });

// Copy the installer to the unit as /os.ldr and read it back. On localhost ?demo= copies to a stand-in.
async function copyInstaller(every = false) {
	const { bytes, modified } = state.inst;
	state.copy = { busy: true, text: 'Connecting to the unit' };
	render();
	let unit = null;
	try {
		unit = demo ? new FakeUnit({ files: { 'os.ldr': new Uint8Array(4096) }, delay: 40 }) : await openUnit(navigator.usb, (t) => log('USB: ' + t), every);
		const mtp = new Mtp(unit);
		mtp.onProgress = (what, done, total) => {
			state.copy = { busy: true, text: what === 'upload' ? 'Copying to the unit' : 'Reading it back', done, total };
			render();
		};
		state.copy = { busy: true, text: 'Looking at the unit’s volume' };
		render();
		const r = await putFile(mtp, 'os.ldr', bytes, mtpDate(modified || new Date()), (t) => log('MTP: ' + t));
		state.copy = { ok: true, text: '/os.ldr on the unit is ' + state.inst.title + ': ' + count(r.size) +
			' bytes read back, identical.' };
		state.note = '';
		goStep(4);
	} catch (e) {
		log('MTP: ' + (e && e.name ? e.name + ': ' : '') + (e && e.message ? e.message : e));
		state.copy = { failed: true, changed: !!(e && e.changed), notChosen: !!(e && e.notChosen),
			text: e && e.message ? e.message : String(e) };
	}
	if (unit)
		await unit.close();
	render();
}

function stepCopy(name) {
	const { inst, copy } = state;
	const out = [h('h1', 'Copy the installer'),
		h('p.lead', 'The page copies the installer to ' + name + ' as /os.ldr, replacing the one there, and ' +
			'reads it back to check it.')];
	if (state.unit === 'op-1-field')
		return out.concat(h('div.do.bad', h('p', 'An OP-1 Field needs its volume arranged before the copy, and ' +
			'this page does not do that yet. Use waffle-boot’s tools/mtpcp.py prepare-1f.')));
	if (!navigator.usb && !demo)
		return out.concat(h('div.do.bad', h('p', 'This browser has no WebUSB. Use Chrome or Edge on a computer.')));

	out.push(h('div.do' + (inst.bad ? '.bad' : ''), h('h2', 'The installer'),
		inst.looking ? h('p', 'Looking up the latest release.') : null,
		inst.title ? h('p.big', inst.title) : null,
		inst.bytes ? h('p.sha', count(inst.bytes.length) + ' bytes, SHA-256 ' + inst.sha256) : null,
		inst.text ? h('p', inst.text) : null,
		inst.link ? h('p', link(...inst.link)) : null,
		h('p', h('button.text', { onclick: () => pick.click(), disabled: !!copy.busy },
			inst.bytes ? 'Use your own file instead' : 'Choose a file'))));

	// The MTP device has no MIDI port, so a unit still on MIDI has not switched to file transfer.
	if (!demo && (state.phase === 'boot' || state.phase === 'present'))
		out.push(h('div.do.bad', h('h2', 'Not in file transfer yet'), h('p', name + ' is still showing its MIDI ' +
			'port, so MTP file transfer is not on. On the unit press ', h('kbd', '3. dev menu'), ', then ',
			h('kbd', '2. mtp file transfer (mac)'), '.')));
	if (copy.busy)
		out.push(h('p.note', copy.text + (copy.total ? ', ' + Math.floor(100 * copy.done / copy.total) + '%' : '') + '.'),
			copy.total ? h('progress', { value: copy.done, max: copy.total }) : null);
	if (copy.failed)
		out.push(h('div.do.bad', h('h2', 'Not copied'), h('p', copy.text),
			copy.changed ? h('p', h('b', '/os.ldr on the unit is not a good copy now. Do not write it to the boot ' +
				'partition: copy again first.')) : null));
	out.push(h('div.actions',
		h('button.go.amber', { onclick: () => copyInstaller(), disabled: !inst.bytes || !!inst.bad || !!copy.busy },
			copy.failed ? 'Copy again' : 'Copy to the unit'),
		copy.notChosen ? h('button.text', { onclick: () => copyInstaller(true), disabled: !inst.bytes || !!inst.bad },
			'Show every USB device') : null));
	return out;
}

// Back to the first screen, as if the page had just been opened: nothing chosen, nothing made.
function startOver() {
	if (state.zip.url)
		URL.revokeObjectURL(state.zip.url);
	Object.assign(state, { step: 1, mode: null, note: '', own: false, zip: {}, inst: {}, copy: {},
		focus: true });
	render();
	scan();
}

// ---- rendering ----

// The two things to do with a unit, drawn as keys: a line glyph, a name, and what it does.
const GLYPH = {
	// A chip with an arrow going into it: writing the bootloader onto the unit.
	install: '<rect x="7" y="7" width="18" height="18" rx="3"/><path d="M12.5 3v4M19.5 3v4M12.5 25v4M19.5 25v4' +
		'M3 12.5h4M3 19.5h4M25 12.5h4M25 19.5h4"/><path d="M16 10.5v10M12 16.5l4 4 4-4"/>',
	// Code brackets: the unit's developer features.
	dev: '<path d="M10.5 9 3.5 16l7 7M21.5 9l7 7-7 7M18.5 6l-5 20"/>',
};
function choice(kind, title, text, onclick) {
	const glyph = h('span.glyph');
	glyph.innerHTML = '<svg viewBox="0 0 32 32" width="36" height="36" aria-hidden="true">' + GLYPH[kind] + '</svg>';
	return h('button.choice.' + kind, { type: 'button', onclick, disabled: !onclick, 'aria-labelledby': 'choice-' + kind,
		'aria-describedby': 'choice-' + kind + '-what' }, glyph,
		h('span.name', { id: 'choice-' + kind }, title), h('span.what', { id: 'choice-' + kind + '-what' }, text));
}

// Both choices, live once a unit is found. Before that they show what the page does, locked, with
// the status above them saying what unlocks them.
function choices(unit, pick) {
	const the = unit ? 'the ' + UNITS[unit].name : 'the unit';
	return h('div.choices',
		choice('install', 'Install waffle-boot', 'Restarts ' + the + ' into its upload screen, then shows the two ' +
			'files to copy onto it.', pick && pick('install')),
		choice('dev', 'Manage Dev Mode', 'Turns developer mode on or off from ' + the + '’s boot menu.',
			pick && pick('dev')));
}

function render() {
	const { phase, unit } = state;
	const box = $('device');
	if (unit && (phase !== 'no-unit' || state.step > 1)) {
		box.className = 'device';
		box.replaceChildren(unitDrawing(unit));
	} else {
		box.className = 'device two';
		box.replaceChildren(...Object.keys(UNITS).map((u) => unitDrawing(u)));
	}
	const name = unit ? UNITS[unit].name : 'your unit';
	const found = state.step === 1 && (phase === 'present' || phase === 'boot');
	const out = [state.step > 1 || (found && state.mode === 'install') ? h('p.tag', 'Step ' + state.step) : null];
	const landing = state.step === 1 && !found;

	if (state.step === 2) {
		const u = UNITS[unit || 'op-xy'];
		out.push(h('h1', 'Copy two files to the disk'),
			h('p.lead', 'A disk named ', h('b', u.disk), ' appears. Copy both files onto it.'),
			h('div.do', h('h2', 'Onto the ' + u.disk + ' disk'), h('ol',
				h('li', link(u.tfw[0], 'Teenage Engineering .tfw'),
					u.more ? [' (', link(u.more[0], 'other versions'), ')'] : null,
					h('span.sub', 'Used only to open door for update, not installed.')),
				h('li', state.zip.url ? h('a', { href: state.zip.url, download: 'firmware.zip' }, 'firmware.zip') :
					['firmware.zip: ', state.inst.looking ? 'looking up the latest release.' : state.zip.text || ''],
					h('span.sub', state.zip.label || 'The waffle-boot installer'),
					h('span.from', seg(['Latest release', !state.own, () => setOwn(false)],
						['Your own .ldr', state.own, () => setOwn(true)]),
						state.own ? h('button.alt.small', { onclick: () => pick.click() },
							state.inst.bytes ? 'Choose another file' : 'Choose file') : null))),
				h('p', h('b', 'Both files must be copied, firmware.zip must be named exactly that.'))),
			state.zip.text && state.inst.link ? h('p.note', link(...state.inst.link)) : null,
			h('p.tag', 'Step 3'),
			h('h1', 'Eject and restart'),
			h('div.do', h('ol',
				h('li', 'Eject the ' + u.disk + ' disk.'),
				h('li', 'Wait for the install on the unit.'),
				h('li', 'Power cycle the unit.'),
				h('li', 'Follow the installer’s instructions on the unit.'))));
	} else if (state.step === 3) {
		out.push(...stepCopy(name));
	} else if (state.step === 4) {
		out.push(h('h1', 'Write it and restart'),
			state.copy.ok ? h('div.do.ok', h('h2', 'Copied'), h('p', state.copy.text)) : null,
			h('p.lead', 'The installer is on ' + name + '. The unit writes it itself, from its own menu.'),
			h('div.do', h('h2', 'On the unit'), h('ol',
				h('li', 'Press ', h('kbd', '2. exit'), '.'),
				h('li', 'Press ', h('kbd', '5. write os to boot partition'), '.'),
				h('li', 'Wait until it says ', h('b', 'firmware written ok!'), ', then press ', h('kbd', '2'), '.'),
				h('li', 'Press ', h('kbd', '6. reset'), '.'))));
	} else if (landing) {
		out.push(h('h1', 'Install waffle-boot or manage dev mode'));
		if (phase === 'nomidi')
			out.push(h('div.do.bad', h('p', state.note || 'This browser cannot reach the unit over MIDI.'),
				h('p', 'Web MIDI needs Chrome or Edge on a computer, over https or on localhost.')));
		else
			out.push(h('p.status', h('span.dot', { 'aria-hidden': 'true' }), phase === 'init' ?
				'Allow MIDI when the browser asks, so the page can look for your unit.' :
				'Plug in your OP-XY or OP-1 Field over USB and turn it on.'));
		out.push(choices(null, null));
	} else if (phase === 'present' || phase === 'boot') {
		const choose = (mode) => () => {
			state.mode = mode;
			state.note = '';
			state.focus = true;
			render();
		};
		if (state.mode === 'install')
			out.push(h('h1', 'Install waffle-boot'),
				h('div.actions', h('button.go.amber', { onclick: () => restart('disk'), disabled: state.busy },
					'Restart to the Upload Menu')));
		else if (state.mode === 'dev')
			out.push(h('h1', 'Manage Dev Mode'),
				h('p.lead', 'The unit restarts into its boot menu.'),
				h('div.actions', h('button.go.amber', { onclick: () => setDev(true), disabled: state.busy }, 'Enable'),
					h('button.go', { onclick: () => setDev(false), disabled: state.busy }, 'Disable')));
		else
			out.push(h('h1', 'This is an ' + name), h('p.status.on', h('span.dot', { 'aria-hidden': 'true' }),
				'Found over USB. Choose what to do.'), choices(unit, choose));
	}

	if (state.note && phase !== 'nomidi')
		out.push(h('p.note', state.note));

	// Away from the first screen, one way back to it, set apart below the steps.
	if (state.step > 1 || state.mode)
		out.push(h('div.restart', h('button.alt', { onclick: startOver,
			disabled: !!state.busy || !!state.copy.busy }, 'Start over')));
	// A step's heading takes the focus when the step opens, and keeps it through redraws.
	const held = document.activeElement && document.activeElement === $('panel').querySelector('h1');
	$('panel').replaceChildren(...out.filter(Boolean));
	if (state.focus || held) {
		const head = $('panel').querySelector('h1');
		head.tabIndex = -1;
		head.focus({ preventScroll: !state.focus });
		if (state.focus)
			head.scrollIntoView({ block: 'nearest' });
		state.focus = false;
	}
}

async function start() {
	document.body.append(pick);
	log('Page loaded. Web MIDI ' + (navigator.requestMIDIAccess ? 'yes' : 'NO') + ', secure page ' +
		(window.isSecureContext ? 'yes' : 'NO') + (demo ? ', a stand-in unit (?demo)' : '') + '.');
	log(navigator.userAgent);

	const text = (n) => fetch(new URL('devices/' + n, import.meta.url)).then((x) => x.text());
	[art.svg['op-xy'], art.svg['op-1-field']] = await Promise.all([text('op-xy.svg'), text('op-1-field.svg')]);

	if (demo) {
		Object.assign(state, demo);
		log('Demo: standing in as "' + new URLSearchParams(location.search).get('demo') + '".');
		render();
		return;
	}
	render();
	startMidi();
}

start();
