import fs from 'node:fs';
import path from 'node:path';

/**
 * Test asset resolution.
 *
 * Face matching only works with REAL faces. Drop your own images into
 * e2e/assets/ (gitignored) and set E2E_REAL_FACES=1:
 *   - studio-photo.jpg  a photo of person A (uploaded by the studio)
 *   - selfie.jpg        a selfie of the SAME person A (the guest)
 *   - selfie-noface.jpg an image with no detectable face
 *   - selfie-multi.jpg  an image with 2+ faces
 *
 * For flow-only runs (no real faces) we synthesize throwaway files so the
 * upload/validation/error paths still execute end-to-end.
 */

const ASSET_DIR = path.resolve(__dirname, '..', 'assets');
const TMP_DIR = path.resolve(__dirname, '..', '.results', 'assets');

export const REAL_FACES = process.env.E2E_REAL_FACES === '1';

function ensureTmp(): string {
  fs.mkdirSync(TMP_DIR, { recursive: true });
  return TMP_DIR;
}

/** Smallest valid 1x1 JPEG — enough to pass MIME checks, no detectable face. */
const TINY_JPEG = Buffer.from(
  '/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAP//////////////////////////////////////////' +
    '////////////////////////////////////////////////////wAALCAABAAEBAREA/8QAFAAB' +
    'AAAAAAAAAAAAAAAAAAAAA//EABQQAQAAAAAAAAAAAAAAAAAAAAD/2gAIAQEAAD8AfwD/2Q==',
  'base64',
);

function synth(name: string, buf: Buffer): string {
  const p = path.join(ensureTmp(), name);
  if (!fs.existsSync(p)) fs.writeFileSync(p, buf);
  return p;
}

/** A real asset if present, else a synthesized stand-in. */
function asset(name: string, fallback: () => string): string {
  const real = path.join(ASSET_DIR, name);
  if (fs.existsSync(real)) return real;
  return fallback();
}

export const studioPhoto = () => asset('studio-photo.jpg', () => synth('studio-photo.jpg', TINY_JPEG));
export const selfie = () => asset('selfie.jpg', () => synth('selfie.jpg', TINY_JPEG));
export const selfieNoFace = () => asset('selfie-noface.jpg', () => synth('selfie-noface.jpg', TINY_JPEG));
export const selfieMultiFace = () => asset('selfie-multi.jpg', () => synth('selfie-multi.jpg', TINY_JPEG));

/** Not an image — exercises the invalid-file rejection path. */
export const invalidFile = () => synth('notes.txt', Buffer.from('this is not an image', 'utf8'));
