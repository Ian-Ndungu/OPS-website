import { useEffect, useRef } from 'react'

const BTNS = [
  ['bold', 'B'], ['italic', 'I'], ['underline', 'U'],
  ['formatBlock:h2', 'H2'], ['formatBlock:h3', 'H3'], ['formatBlock:p', '¶'],
  ['insertUnorderedList', '• List'], ['insertOrderedList', '1. List'], ['formatBlock:blockquote', '❝'],
]

/** Lightweight rich-text editor. Output is ALWAYS sanitized again on the server (bleach allow-list). */
export default function RichTextEditor({ value, onChange }) {
  const ref = useRef(null)
  useEffect(() => { if (ref.current && ref.current.innerHTML !== value) ref.current.innerHTML = value || '' }, [value])
  const exec = (cmd) => {
    const [c, arg] = cmd.split(':')
    document.execCommand(c, false, arg ? `<${arg}>` : null)
    onChange(ref.current.innerHTML)
  }
  const link = () => {
    const url = window.prompt('Link URL (https://…)')
    if (url && /^(https?:|mailto:)/i.test(url)) { document.execCommand('createLink', false, url); onChange(ref.current.innerHTML) }
  }
  return (
    <div className="rounded-2xl border border-ops-line bg-ops-raised">
      <div className="flex flex-wrap gap-1 border-b border-ops-line p-2">
        {BTNS.map(([cmd, text]) => (
          <button key={cmd} type="button" className="rounded px-2 py-1 text-xs font-semibold hover:bg-ops-line" onMouseDown={(e) => e.preventDefault()} onClick={() => exec(cmd)}>{text}</button>
        ))}
        <button type="button" className="rounded px-2 py-1 text-xs font-semibold hover:bg-ops-line" onMouseDown={(e) => e.preventDefault()} onClick={link}>Link</button>
      </div>
      <div ref={ref} contentEditable suppressContentEditableWarning className="prose-ops min-h-[180px] p-3 text-sm focus:outline-none"
        onInput={(e) => onChange(e.currentTarget.innerHTML)} />
    </div>
  )
}
