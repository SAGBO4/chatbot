// Reads `file` as a data: URL (data:<mime>;base64,<data>) - the exact shape the backend's
// POST /api/tickets/{id}/attachment expects, so the browser never needs to build multipart itself.
export function fileToDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as string);
    reader.onerror = () => reject(reader.error || new Error('Failed to read the file.'));
    reader.readAsDataURL(file);
  });
}

export function cn(...classes: (string | boolean | undefined | null | { [key: string]: boolean })[]): string {
  const result: string[] = [];

  for (const item of classes) {
    if (!item) continue;
    if (typeof item === 'string') {
      result.push(item);
    } else if (typeof item === 'object') {
      for (const [key, value] of Object.entries(item)) {
        if (value) result.push(key);
      }
    }
  }

  return result.join(' ');
}
