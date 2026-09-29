import { useLayoutEffect, useRef, useState } from "react";

// Frame 815:1241: the 1219 × 4550 background at x=-241 uses an image
// fill matrix(0.000612553, 0, 0, 0.000164057, -0.139189, -0.0630965).
// Preserve that crop and 70% opacity, keeping the supplied SVG unchanged.
export function FeedBackground() {
  const container = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState(370 / 739);

  useLayoutEffect(() => {
    const element = container.current;
    if (!element) return;
    const resize = () => setScale(element.getBoundingClientRect().width / 739);
    resize();
    const observer = new ResizeObserver(resize);
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  return (
    <div className="feed-background" ref={container} aria-hidden="true">
      <img
        src="/assets/figma/aggregator-gradient.svg"
        width="792"
        height="1546"
        alt=""
        style={{
          left: (-241 - 0.139189 * 1219) * scale,
          top: -0.0630965 * 4550 * scale,
          transform: `scale(${2098 * 0.000612553 * 1219 / 792 * scale}, ${4096 * 0.000164057 * 4550 / 1546 * scale})`,
        }}
      />
    </div>
  );
}
