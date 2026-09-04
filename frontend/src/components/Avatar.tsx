import React, { useEffect, useState } from 'react';
import { fetchAvatarUrl } from '../api/client';

/**
 * The athlete's picture, where they have set one.
 *
 * Falls back to whatever the caller would otherwise have shown rather than to
 * a placeholder person: on the home page that is the level number, which is
 * real information and better than a grey silhouette.
 */
export const Avatar: React.FC<{
  size?: number;
  className?: string;
  fallback: React.ReactNode;
  /** Changing this re-reads the picture, so an upload shows immediately. */
  version?: number;
}> = ({ size = 56, className = '', fallback, version = 0 }) => {
  const [url, setUrl] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    let created: string | null = null;
    fetchAvatarUrl().then((next) => {
      if (cancelled) {
        // Resolved after unmount: nothing will revoke it but this.
        if (next) URL.revokeObjectURL(next);
        return;
      }
      created = next;
      setUrl(next);
    });
    return () => {
      cancelled = true;
      if (created) URL.revokeObjectURL(created);
    };
  }, [version]);

  if (!url) {
    return <>{fallback}</>;
  }
  return (
    <img src={url} alt="" width={size} height={size}
         className={`object-cover ${className}`}
         style={{ width: size, height: size }} />
  );
};
