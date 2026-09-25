// A study's or a series' first image, small: a fixed black box (as every image
// list in radiology), fetched only when it scrolls into view and decoded off
// the main thread. It shimmers faintly until the image arrives, then the
// image fades in; an image the engine will not render (or a session that has
// ended) leaves a quiet grey box. Nothing here ever moves the row.
import { useEffect, useRef, useState } from 'react';

type State = 'loading' | 'loaded' | 'failed';

export function Thumb({ src, size = 44, className = '' }: { src: string; size?: number; className?: string }) {
  const ref = useRef<HTMLImageElement>(null);
  const [state, setState] = useState<State>('loading');
  // An image the browser already had is complete before React listens.
  useEffect(() => {
    const img = ref.current;
    if (img?.complete && img.naturalWidth > 0) setState('loaded');
  }, []);
  return (
    <span className={`thumbwrap ${className}`} data-state={state} style={{ width: size, height: size }} aria-hidden>
      {state !== 'failed' && (
        <img
          ref={ref}
          className="thumb"
          src={src}
          alt=""
          width={size}
          height={size}
          loading="lazy"
          decoding="async"
          onLoad={() => setState('loaded')}
          onError={() => setState('failed')}
        />
      )}
    </span>
  );
}
