export function MascotCat() {
  return (
    <div className="fixed bottom-4 right-4 z-40 pointer-events-none">
      <svg
        className="animate-cat-nod origin-[50%_92%] motion-reduce:animate-none"
        viewBox="0 0 120 120"
        width="90"
        height="90"
      >
        <defs>
          <linearGradient id="mascot-band" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#B48CE0" />
            <stop offset="100%" stopColor="#8C64C0" />
          </linearGradient>
          <radialGradient id="mascot-cup" cx="35%" cy="30%" r="75%">
            <stop offset="0%" stopColor="#F3E9FF" />
            <stop offset="55%" stopColor="#C9A8EE" />
            <stop offset="100%" stopColor="#9A6FCB" />
          </radialGradient>
        </defs>

        {/* two short ears, outer + inner pink */}
        <path d="M32,50 L27,26 L54,40 Z" fill="#F5B87A" stroke="#B5763A" strokeWidth="2.5" strokeLinejoin="round" />
        <path d="M88,50 L93,26 L66,40 Z" fill="#F5B87A" stroke="#B5763A" strokeWidth="2.5" strokeLinejoin="round" />

        {/* head */}
        <ellipse cx="60" cy="65" rx="34" ry="32" fill="#F5B87A" stroke="#B5763A" strokeWidth="2.5" />

        {/* inner ear pink */}
        <path d="M33,46 L30,32 L48,39 Z" fill="#F3B6C4" />
        <path d="M87,46 L90,32 L72,39 Z" fill="#F3B6C4" />

        {/* headband over the top */}
        <path d="M17 60 Q17 8 60 8 Q103 8 103 60" fill="none" stroke="url(#mascot-band)" strokeWidth="8" strokeLinecap="round" />
        <path d="M22 55 Q22 16 60 16" fill="none" stroke="#EBDCFF" strokeWidth="2" strokeLinecap="round" opacity="0.7" />

        {/* ear cups */}
        <circle cx="15" cy="62" r="15" fill="#7C5AA6" />
        <circle cx="15" cy="62" r="11.5" fill="url(#mascot-cup)" />
        <ellipse cx="11" cy="57" rx="4" ry="2.5" fill="#ffffff" opacity="0.8" />
        <circle cx="105" cy="62" r="15" fill="#7C5AA6" />
        <circle cx="105" cy="62" r="11.5" fill="url(#mascot-cup)" />
        <ellipse cx="101" cy="57" rx="4" ry="2.5" fill="#ffffff" opacity="0.8" />

        {/* face */}
        <circle cx="46" cy="62" r="7" fill="#3A2A20" />
        <circle cx="48" cy="59" r="2" fill="#fff" />
        <circle cx="74" cy="62" r="7" fill="#3A2A20" />
        <circle cx="76" cy="59" r="2" fill="#fff" />
        <ellipse cx="60" cy="73" rx="4" ry="3" fill="#E8849A" />
        <path d="M55 78 Q60 82 65 78" fill="none" stroke="#B5763A" strokeWidth="2" strokeLinecap="round" />
        <path d="M38 72 L20 68 M38 76 L19 78 M82 72 L100 68 M82 76 L101 78" stroke="#B5763A" strokeWidth="1.5" strokeLinecap="round" />

        {/* bow on the right ear, tilted, drawn last so it's on top */}
        <g transform="rotate(25 85 35)">
          <path d="M85,35 L75,29 L77,41 Z" fill="#E85D8A" stroke="#B5397A" strokeWidth="1.5" strokeLinejoin="round" />
          <path d="M85,35 L95,29 L93,41 Z" fill="#E85D8A" stroke="#B5397A" strokeWidth="1.5" strokeLinejoin="round" />
          <circle cx="85" cy="35" r="3" fill="#C6437A" stroke="#B5397A" strokeWidth="1" />
        </g>

        <text x="112" y="46" fontSize="16" fill="#8C64C0">♪</text>
      </svg>
    </div>
  );
}
