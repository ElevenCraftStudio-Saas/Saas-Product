'use client';

import { useEffect, useRef, useState } from 'react';
import { UploadCloud, FolderUp } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';

export function UploadDropzone({ onFiles }: { onFiles: (files: File[]) => void }) {
  const [drag, setDrag] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const folderInput = useRef<HTMLInputElement>(null);

  // webkitdirectory/directory aren't in the React typings — set imperatively.
  useEffect(() => {
    if (folderInput.current) {
      folderInput.current.setAttribute('webkitdirectory', '');
      folderInput.current.setAttribute('directory', '');
    }
  }, []);

  const pick = (list: FileList | null) => {
    if (list && list.length) onFiles(Array.from(list));
  };

  return (
    <div
      onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
      onDragLeave={() => setDrag(false)}
      onDrop={(e) => { e.preventDefault(); setDrag(false); pick(e.dataTransfer.files); }}
      className={cn(
        'flex flex-col items-center justify-center rounded-2xl border-2 border-dashed p-10 text-center transition-colors',
        drag ? 'border-primary bg-primary/5' : 'border-border bg-card',
      )}
    >
      <UploadCloud className="mb-3 h-10 w-10 text-muted-foreground" aria-hidden />
      <p className="font-medium">Drag &amp; drop photos here</p>
      <p className="mt-1 text-sm text-muted-foreground">JPG, PNG or WebP · up to 25 MB each</p>
      <div className="mt-4 flex flex-wrap justify-center gap-2">
        <Button variant="outline" onClick={() => fileInput.current?.click()}>Browse files</Button>
        <Button variant="ghost" onClick={() => folderInput.current?.click()}>
          <FolderUp className="mr-1 h-4 w-4" /> Upload folder
        </Button>
      </div>
      <input
        ref={fileInput}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        multiple
        hidden
        onChange={(e) => { pick(e.target.files); e.target.value = ''; }}
      />
      <input
        ref={folderInput}
        type="file"
        multiple
        hidden
        onChange={(e) => { pick(e.target.files); e.target.value = ''; }}
      />
    </div>
  );
}
