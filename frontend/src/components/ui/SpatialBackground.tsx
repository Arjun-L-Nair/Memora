/**
 * SpatialBackground — a calm mist gradient with three slow, blurred
 * colour washes behind frosted panels. Decorative only (aria-hidden).
 * Motion is slow and disabled under prefers-reduced-motion (globals.css).
 */
export function SpatialBackground() {
  return (
    <div className="spatial-bg pointer-events-none fixed inset-0 -z-10 overflow-hidden" aria-hidden="true">
      <div className="spatial-blob -left-24 -top-24 h-96 w-96 bg-primary-200" />
      <div className="spatial-blob -right-32 top-1/4 h-[28rem] w-[28rem] bg-secondary-200" style={{ animationDelay: "-6s" }} />
      <div className="spatial-blob bottom-[-8rem] left-1/4 h-96 w-96 bg-primary-100" style={{ animationDelay: "-11s" }} />
    </div>
  );
}
