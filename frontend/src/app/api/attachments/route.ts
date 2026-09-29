import { NextRequest, NextResponse } from 'next/server';
import { writeFile, mkdir } from 'node:fs/promises';
import { join } from 'node:path';
import { randomBytes } from 'node:crypto';

// Max file size: 5MB
const MAX_FILE_SIZE = 5 * 1024 * 1024;
const ALLOWED_MIME_TYPES = new Set([
  'image/png',
  'image/jpeg',
  'image/jpg',
  'image/webp',
  'image/gif',
]);

const EXTENSION_MAP: Record<string, string> = {
  'image/png': 'png',
  'image/jpeg': 'jpg',
  'image/jpg': 'jpg',
  'image/webp': 'webp',
  'image/gif': 'gif',
};

export async function POST(request: NextRequest) {
  try {
    const contentType = request.headers.get('content-type') || '';

    let buffer: Buffer;
    let mimeType = 'image/png';
    let originalName = 'screenshot.png';

    if (contentType.includes('multipart/form-data')) {
      const formData = await request.formData();
      const file = formData.get('file') as File | null;

      if (!file) {
        return NextResponse.json({ error: 'Aucun fichier transmis' }, { status: 400 });
      }

      if (file.size > MAX_FILE_SIZE) {
        return NextResponse.json(
          { error: 'Le fichier dépasse la taille maximale de 5 Mo' },
          { status: 413 }
        );
      }

      mimeType = file.type || 'image/png';
      if (!ALLOWED_MIME_TYPES.has(mimeType)) {
        return NextResponse.json(
          { error: 'Format non autorisé. Formats acceptés : PNG, JPEG, WebP, GIF' },
          { status: 415 }
        );
      }

      originalName = file.name || 'screenshot.png';
      const arrayBuffer = await file.arrayBuffer();
      buffer = Buffer.from(arrayBuffer);
    } else if (contentType.includes('application/json')) {
      const body = await request.json();
      const dataUrl = body?.dataUrl || body?.image;

      if (!dataUrl || typeof dataUrl !== 'string') {
        return NextResponse.json({ error: 'Données image invalides' }, { status: 400 });
      }

      const match = dataUrl.match(/^data:([^;]+);base64,(.+)$/);
      if (!match) {
        return NextResponse.json({ error: 'Format Data-URL invalide' }, { status: 400 });
      }

      mimeType = match[1];
      if (!ALLOWED_MIME_TYPES.has(mimeType)) {
        return NextResponse.json(
          { error: 'Format non autorisé. Formats acceptés : PNG, JPEG, WebP, GIF' },
          { status: 415 }
        );
      }

      const base64Data = match[2];
      buffer = Buffer.from(base64Data, 'base64');

      if (buffer.length > MAX_FILE_SIZE) {
        return NextResponse.json(
          { error: 'Le fichier dépasse la taille maximale de 5 Mo' },
          { status: 413 }
        );
      }

      if (body?.name) originalName = body.name;
    } else {
      return NextResponse.json({ error: 'Type de contenu non supporté' }, { status: 400 });
    }

    const ext = EXTENSION_MAP[mimeType] || 'png';
    const randomHex = randomBytes(8).toString('hex');
    const safeFilename = `ticket-${Date.now()}-${randomHex}.${ext}`;

    const uploadsDir = join(process.cwd(), 'public', 'uploads');
    await mkdir(uploadsDir, { recursive: true });

    const filePath = join(uploadsDir, safeFilename);
    await writeFile(filePath, buffer);

    const publicUrl = `/uploads/${safeFilename}`;

    return NextResponse.json({
      success: true,
      url: publicUrl,
      filename: safeFilename,
      originalName,
      size: buffer.length,
      mimeType,
    });
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Erreur interne lors du téléversement';
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
