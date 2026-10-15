// Tests for assets/sun-compare.js (suite SU-20). Run: node --test tools/tests/test_sun_compare.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const C = require('../../assets/sun-compare.js');

test('arrow keys move the divider five percent and stop at the edges', () => {
  assert.equal(C.keyValue('ArrowRight', 50), 55);
  assert.equal(C.keyValue('ArrowUp', 50), 55);
  assert.equal(C.keyValue('ArrowLeft', 50), 45);
  assert.equal(C.keyValue('ArrowDown', 50), 45);
  assert.equal(C.keyValue('ArrowRight', 98), 100);
  assert.equal(C.keyValue('ArrowLeft', 3), 0);
});

test('page keys move 25, Home and End go to the edges, Enter resets to the middle', () => {
  assert.equal(C.keyValue('PageUp', 50), 75);
  assert.equal(C.keyValue('PageDown', 10), 0);
  assert.equal(C.keyValue('Home', 63), 0);
  assert.equal(C.keyValue('End', 12), 100);
  assert.equal(C.keyValue('Enter', 5), 50);
});

test('other keys are left alone (Tab keeps moving focus)', () => {
  assert.equal(C.keyValue('Tab', 50), null);
  assert.equal(C.keyValue('a', 50), null);
});

test('clamp rounds and bounds pointer positions', () => {
  assert.equal(C.clamp(-12.3), 0);
  assert.equal(C.clamp(33.6), 34);
  assert.equal(C.clamp(140), 100);
});
