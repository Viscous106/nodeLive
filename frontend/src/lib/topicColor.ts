// Topic-coded thumbnail colors, mirroring the Scaler reference (see
// docs/design-tokens.md). Title keyword → accent color.
const TOPIC_COLORS: Record<string, string> = {
  os: '#3B82F6',
  system: '#3B82F6',
  infrastructure: '#3B82F6',
  operating: '#3B82F6',
  process: '#22C55E',
  data: '#22C55E',
  sql: '#F43F5E',
  database: '#F43F5E',
  quer: '#F43F5E',
  isolation: '#F43F5E',
  network: '#14B8A6',
}

export function getTopicColor(title: string): string {
  const t = title.toLowerCase()
  for (const [key, color] of Object.entries(TOPIC_COLORS)) {
    if (t.includes(key)) return color
  }
  return '#14B8A6'
}
