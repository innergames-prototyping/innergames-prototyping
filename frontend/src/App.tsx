import { useEffect, useState, type DragEvent } from 'react'

type Extraction = {
  id: string
  state: 'running' | 'done' | 'failed'
  pdfs: string[]
  activity: string
  seconds: number
  results: string[]
  result: string | null
  cost_usd: number | null
}

type Components = { components: { kind: string; count: number }[] }

const api = '/api/extractions'

async function getJson(url: string, init?: RequestInit) {
  const res = await fetch(url, init)
  const data = await res.json()
  if (!res.ok) {
    throw new Error(typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail))
  }
  return data
}

function duration(seconds: number) {
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`
}

export default function App() {
  const [files, setFiles] = useState<File[]>([])
  const [over, setOver] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [job, setJob] = useState<Extraction | null>(null)

  useEffect(() => {
    const id = location.hash.slice(1)
    if (id) getJson(`${api}/${id}`).then(setJob, (e) => setError(e.message))
  }, [])

  useEffect(() => {
    if (job?.state !== 'running') return
    const timer = setTimeout(
      () => getJson(`${api}/${job.id}`).then(setJob, (e) => setError(e.message)),
      3000,
    )
    return () => clearTimeout(timer)
  }, [job])

  function drop(e: DragEvent) {
    e.preventDefault()
    setOver(false)
    setFiles([...e.dataTransfer.files])
  }

  async function extract() {
    setError(null)
    const body = new FormData()
    for (const f of files) body.append('files', f)
    try {
      const started = await getJson(api, { method: 'POST', body })
      location.hash = started.id
      setJob(started)
    } catch (e) {
      setError((e as Error).message)
    }
  }

  function reset() {
    history.replaceState(null, '', location.pathname)
    setJob(null)
    setFiles([])
  }

  return (
    <main>
      <h1>Extract a game</h1>
      {error && <p className="error">{error}</p>}
      {job ? (
        <>
          <p>
            {job.pdfs.join(', ')}: <strong>{job.state}</strong> after {duration(job.seconds)}
            {job.state === 'running' && <> · {job.activity}</>}
          </p>
          {job.state !== 'running' && <button onClick={reset}>Extract another game</button>}
          {job.result && <pre>{job.result}</pre>}
          {job.cost_usd !== null && <p>Orchestration cost: ${job.cost_usd.toFixed(2)}</p>}
          {job.state === 'done' && <Results id={job.id} />}
        </>
      ) : (
        <>
          <label
            className={over ? 'drop over' : 'drop'}
            onDragOver={(e) => {
              e.preventDefault()
              setOver(true)
            }}
            onDragLeave={() => setOver(false)}
            onDrop={drop}
          >
            <p>Drop the game's PDFs here, or click to choose them.</p>
            <input
              type="file"
              accept=".pdf,application/pdf"
              multiple
              hidden
              onChange={(e) => setFiles([...(e.target.files ?? [])])}
            />
            {files.length > 0 && <p>{files.map((f) => f.name).join(', ')}</p>}
          </label>
          <p>
            <button disabled={files.length === 0} onClick={extract}>
              Extract
            </button>
          </p>
        </>
      )}
    </main>
  )
}

function Results({ id }: { id: string }) {
  const [rules, setRules] = useState<string | null>(null)
  const [components, setComponents] = useState<Components | null>(null)

  useEffect(() => {
    fetch(`${api}/${id}/results/rules.txt`)
      .then((res) => res.text())
      .then(setRules)
    getJson(`${api}/${id}/results/components.json`).then(setComponents)
  }, [id])

  const counts = new Map<string, number>()
  for (const piece of components?.components ?? [])
    counts.set(piece.kind, (counts.get(piece.kind) ?? 0) + piece.count)

  return (
    <>
      <h2>
        <a href={`${api}/${id}/results/components.json`}>components.json</a>
      </h2>
      <table>
        <tbody>
          {[...counts].map(([kind, count]) => (
            <tr key={kind}>
              <td>{kind}</td>
              <td>{count}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <h2>
        <a href={`${api}/${id}/results/rules.txt`}>rules.txt</a>
      </h2>
      <pre>{rules}</pre>
    </>
  )
}
