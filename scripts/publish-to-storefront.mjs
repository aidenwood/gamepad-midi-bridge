#!/usr/bin/env node
/**
 * publish-to-storefront.mjs — push CI-built release artefacts into the
 * Universal Controller MIDI storefront's Netlify Blobs.
 *
 * Called from .github/workflows/build-release.yml after the per-OS build
 * matrix finishes. Matches each downloaded artefact by filename substring
 * (`macos` / `windows` / `linux`), uploads to the site-scoped 'releases'
 * blob store under <tag>/<os>, then writes the 'current' manifest pointer
 * that /api/latest-release.json + /api/download/[os] read from.
 *
 * Env vars (set in the CI step):
 *   NETLIFY_AUTH_TOKEN  — Personal Access Token with Blobs API write scope.
 *                         Stored as a repo secret in the desktop-app repo.
 *   STOREFRONT_SITE_ID  — Override the default (production storefront).
 *   GITHUB_REF_NAME     — Provided by Actions; the pushed tag (e.g. v2.0.0-alpha.1).
 *   ARTEFACT_DIR        — Folder containing all downloaded artefact zips.
 *
 * Naming convention this script expects:
 *   - macOS  artefact has 'macos'   somewhere in the filename
 *   - Windows artefact has 'windows' somewhere in the filename
 *   - Linux  artefact has 'linux'   somewhere in the filename
 *   - Any .zip / .dmg / .exe / .AppImage / .deb / .tar.gz inside ARTEFACT_DIR is fair game.
 *
 * Pre-release detection: any tag containing -alpha / -beta / -rc is flagged
 * prerelease in the manifest, which surfaces the amber 'pre-release' badge
 * on the storefront downloads page.
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, basename } from 'node:path';
import { getStore } from '@netlify/blobs';

// Default to the production storefront. Override with STOREFRONT_SITE_ID env
// var if testing against a staging Netlify site.
const SITE_ID = process.env.STOREFRONT_SITE_ID || 'cbd6454a-c842-406a-9ff7-93e9730983cc';
const TOKEN = process.env.NETLIFY_AUTH_TOKEN;
const TAG = process.env.GITHUB_REF_NAME;
const ARTEFACT_DIR = process.env.ARTEFACT_DIR || 'release-assets';

if (!TOKEN) {
    console.error('Missing NETLIFY_AUTH_TOKEN env var. Add it as a repo secret.');
    process.exit(1);
}
if (!TAG) {
    console.error('Missing GITHUB_REF_NAME env var. This script expects to run on a tag push.');
    process.exit(1);
}

// Scan the artefact dir for files matching each OS by substring. Skip dotfiles
// and anything that obviously isn't a release binary.
const VALID_EXT = /\.(dmg|exe|AppImage|zip|deb|tar\.gz)$/i;
const OS_MATCHERS = {
    mac:   /macos|darwin|osx/i,
    win:   /windows|win32|win64|-win-/i,
    linux: /linux|ubuntu|debian|appimage/i,
};

const CONTENT_TYPES = {
    '.dmg':      'application/x-apple-diskimage',
    '.exe':      'application/vnd.microsoft.portable-executable',
    '.AppImage': 'application/x-executable',
    '.zip':      'application/zip',
    '.deb':      'application/vnd.debian.binary-package',
    '.tar.gz':   'application/gzip',
};

function detectExt(name) {
    if (name.endsWith('.tar.gz')) return '.tar.gz';
    const dot = name.lastIndexOf('.');
    return dot >= 0 ? name.slice(dot) : '';
}

let entries;
try {
    entries = readdirSync(ARTEFACT_DIR)
        .filter((n) => !n.startsWith('.') && VALID_EXT.test(n))
        .map((n) => join(ARTEFACT_DIR, n));
} catch (err) {
    console.error(`Could not read ${ARTEFACT_DIR}: ${err.message}`);
    process.exit(1);
}

if (entries.length === 0) {
    console.error(`No release artefacts found in ${ARTEFACT_DIR}.`);
    process.exit(1);
}

// Map each artefact to an OS slot. First match wins; warn on duplicates so
// we don't silently overwrite (rare but worth surfacing).
const picks = {};
for (const path of entries) {
    const name = basename(path);
    for (const [os, re] of Object.entries(OS_MATCHERS)) {
        if (re.test(name)) {
            if (picks[os]) {
                console.warn(`Multiple ${os} candidates — keeping ${picks[os].name}, ignoring ${name}`);
            } else {
                picks[os] = { path, name };
            }
            break;
        }
    }
}

if (Object.keys(picks).length === 0) {
    console.error('No artefacts matched any OS pattern. Filenames seen:');
    for (const path of entries) console.error('  ' + basename(path));
    process.exit(1);
}

const store = getStore({ name: 'releases', siteID: SITE_ID, token: TOKEN });
const uploaded = {};

for (const [os, info] of Object.entries(picks)) {
    const buf = readFileSync(info.path);
    const size = statSync(info.path).size;
    const ext = detectExt(info.name);
    const contentType = CONTENT_TYPES[ext] || 'application/octet-stream';
    const key = `${TAG}/${os}`;

    process.stdout.write(`Uploading ${os} (${(size / 1024 / 1024).toFixed(1)} MB) → blobs/releases/${key} ... `);
    await store.set(key, buf, {
        metadata: { filename: info.name, size, contentType, uploadedAt: new Date().toISOString() },
    });
    console.log('done');
    uploaded[os] = { filename: info.name, size, contentType };
}

// Merge with any prior partial publish under the same tag so re-runs are safe.
let current = null;
try { current = await store.get('current', { type: 'json' }); } catch { /* none yet */ }
const assets = current?.tag === TAG ? { ...(current.assets || {}) } : {};
for (const [os, meta] of Object.entries(uploaded)) assets[os] = meta;

const prerelease = /-(alpha|beta|rc)(\.|$|-)/i.test(TAG);

const manifest = {
    tag: TAG,
    prerelease,
    published_at: new Date().toISOString(),
    assets,
};
await store.setJSON('current', manifest);
console.log('\nPublished manifest:\n' + JSON.stringify(manifest, null, 2));
