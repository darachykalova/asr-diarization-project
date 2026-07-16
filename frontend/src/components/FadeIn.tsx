import { useEffect, useState } from "react";

export function FadeIn({ children }: { children: React.ReactNode }) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    const id = requestAnimationFrame(() => setMounted(true));
    return () => cancelAnimationFrame(id);
  }, []);

  return (
    <div
      className={`transition-[opacity,transform] duration-200 ease-[cubic-bezier(0.23,1,0.32,1)] motion-reduce:translate-y-0 ${
        mounted ? "opacity-100 translate-y-0" : "opacity-0 translate-y-1.5"
      }`}
    >
      {children}
    </div>
  );
}
