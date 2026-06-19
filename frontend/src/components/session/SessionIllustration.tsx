export function SessionIllustration({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 200 160"
      className={className}
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      <rect
        x="44"
        y="18"
        width="140"
        height="92"
        rx="8"
        fill="#FFFFFF"
        stroke="#BFDBFE"
        strokeWidth="2"
      />
      <line x1="60" y1="40" x2="150" y2="40" stroke="#93C5FD" strokeWidth="4" strokeLinecap="round" />
      <line x1="60" y1="56" x2="132" y2="56" stroke="#BFDBFE" strokeWidth="4" strokeLinecap="round" />
      <line x1="60" y1="72" x2="142" y2="72" stroke="#BFDBFE" strokeWidth="4" strokeLinecap="round" />
      <rect x="124" y="84" width="44" height="14" rx="4" fill="#DBEAFE" />
      <line x1="114" y1="110" x2="114" y2="132" stroke="#93C5FD" strokeWidth="3" strokeLinecap="round" />
      <circle cx="38" cy="90" r="12" fill="#2563EB" />
      <path d="M18 132c0-13 9-22 20-22s20 9 20 22" fill="#3B82F6" />
      <line x1="50" y1="94" x2="66" y2="78" stroke="#2563EB" strokeWidth="4" strokeLinecap="round" />
    </svg>
  )
}
