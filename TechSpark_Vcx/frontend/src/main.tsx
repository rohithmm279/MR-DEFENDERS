import { FormEvent, useState } from 'react'
import { createRoot } from 'react-dom/client'
import './styles.css'

type Citation = { id: string; act_name: string; section_number: string; source_url: string; excerpt: string }
type Block = { type: string; title: string; content: string | string[]; citation_ids: string[] }
type Answer = { status: string; domain?: string; answer: string; steps: string[]; citations: Citation[]; confidence: number; disclaimer: string; model_mode: string; blocks?: Block[]; follow_up_questions?: { id: string; question: string; reason: string }[]; needs_clarification?: boolean }
const API = 'http://127.0.0.1:8000/api/v1'

function App() {
  const [query, setQuery] = useState('How can I file a consumer complaint for a defective product?')
  const [answer, setAnswer] = useState<Answer | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function submit(event: FormEvent) {
    event.preventDefault(); setLoading(true); setError('')
    try {
      const response = await fetch(`${API}/chat`, { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ query }) })
      if (!response.ok) throw new Error('The local service is unavailable. Start the FastAPI backend and try again.')
      setAnswer(await response.json())
    } catch (e) { setError(e instanceof Error ? e.message : 'Unable to reach the local service.') }
    finally { setLoading(false) }
  }

  return <main><header><p className="eyebrow">OFFLINE LEGAL GUIDANCE</p><h1>MR DEFENDERS</h1><p>Clear first steps. Verified local sources. Always consult a qualified professional for case-specific advice.</p></header>
    <section className="notice"><strong>Important:</strong> This tool provides general legal information only. If you are in immediate danger or facing an arrest now, contact local emergency or legal-aid services immediately.</section>
    <form onSubmit={submit}><label htmlFor="query">Ask about consumer complaints, FIR/bail basics, marriage registration, or dowry law</label><textarea id="query" value={query} onChange={e => setQuery(e.target.value)} minLength={3}/><button disabled={loading}>{loading ? 'Checking local sources…' : 'Get guidance'}</button></form>
    {error && <p className="error">{error}</p>}
    {answer && <section className={`answer ${answer.status}`}><div className="meta"><span>{answer.domain ?? 'Safety routing'}</span><span>Confidence: {Math.round(answer.confidence * 100)}%</span></div><h2>{answer.status === 'escalated' ? 'Please seek urgent support' : 'Guidance'}</h2><p>{answer.answer}</p>
      {answer.blocks && answer.blocks.filter(block => block.type !== 'explanation' && block.type !== 'sources').map(block => <article className="guidance-block" key={`${block.type}-${block.title}`}><h3>{block.title}</h3>{Array.isArray(block.content) ? <ul>{block.content.map(item => <li key={item}>{item}</li>)}</ul> : <p>{block.content}</p>}</article>)}
      {answer.follow_up_questions && answer.follow_up_questions.length > 0 && <><h3>Information needed</h3><ul>{answer.follow_up_questions.map(item => <li key={item.id}>{item.question}</li>)}</ul></>}
      {answer.steps.length > 0 && <><h3>Suggested next steps</h3><ol>{answer.steps.map(step => <li key={step}>{step}</li>)}</ol></>}
      {answer.citations.length > 0 && <><h3>Local sources used</h3><div className="sources">{answer.citations.map(c => <article key={c.id}><strong>{c.act_name}, {c.section_number}</strong><p>{c.excerpt}</p><a href={c.source_url} target="_blank" rel="noreferrer">Original statutory source</a></article>)}</div></>}
      <footer>{answer.disclaimer}<br/><small>Response mode: {answer.model_mode.replaceAll('_', ' ')}</small></footer></section>}
  </main>
}
createRoot(document.getElementById('root')!).render(<App />)
