#!/usr/bin/env node
/**
 * Retired by ADR-022. The dashboard now reads a fixed historical snapshot.
 * Original implementation remains in Git at 84879d2.
 */
console.error('[archive] Automatic data refresh is retired. The dashboard preserves its recorded snapshot. See docs/PUBLISHING.md.');
process.exitCode = 1;
