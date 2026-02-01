import { useState, useEffect, useRef } from 'react'
import axios from 'axios'
import { Upload, FileVideo, CheckCircle, Video } from 'lucide-react'

let API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
if (API_BASE && !API_BASE.startsWith('http')) {
  API_BASE = `https://${API_BASE}`;
}

function App() {
  const [file, setFile] = useState(null)
  const [status, setStatus] = useState('idle') // idle, uploading, processing, done, error
  const [jobId, setJobId] = useState(null)
  const [progress, setProgress] = useState('waiting') // queued, processing, etc
  const [clips, setClips] = useState([])
  const [error, setError] = useState(null)

  const [geminiKey, setGeminiKey] = useState(localStorage.getItem('clipper_gemini_key') || '')
  const [openaiKey, setOpenaiKey] = useState(localStorage.getItem('clipper_openai_key') || '')
  const [showKeyModal, setShowKeyModal] = useState(!localStorage.getItem('clipper_gemini_key') || !localStorage.getItem('clipper_openai_key'))

  const fileInputRef = useRef(null)

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0])
    }
  }

  const startUpload = async () => {
    if (!file) return;

    try {
      setStatus('uploading')
      const formData = new FormData()
      formData.append('file', file)

      // 1. Upload
      const uploadRes = await axios.post(`${API_BASE}/api/upload`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: (progressEvent) => {
          const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total)
          setProgress(`uploading: ${percentCompleted}%`)
        }
      })

      const filePath = uploadRes.data.path;

      // 2. Start Process
      setStatus('processing')
      const processRes = await axios.post(`${API_BASE}/api/process?path=${encodeURIComponent(filePath)}&gemini_api_key=${geminiKey}&openai_api_key=${openaiKey}`)
      setJobId(processRes.data.job_id)

    } catch (err) {
      console.error(err)
      setError(err.message)
      setStatus('error')
    }
  }

  // Poll for status
  useEffect(() => {
    if (status === 'processing' && jobId) {
      const interval = setInterval(async () => {
        try {
          const res = await axios.get(`${API_BASE}/api/jobs/${jobId}`)
          const job = res.data
          setProgress(job.status)

          if (job.status === 'done') {
            setClips(job.clips)
            setStatus('done')
            clearInterval(interval)
          } else if (job.status === 'failed') {
            setError(job.error || 'Job failed')
            setStatus('error')
            clearInterval(interval)
          }
        } catch (err) {
          console.error("Polling error", err)
        }
      }, 2000)

      return () => clearInterval(interval)
    }
  }, [status, jobId])

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans p-8">
      <div className="max-w-4xl mx-auto">
        <header className="mb-12 text-center">
          <h1 className="text-4xl font-bold bg-gradient-to-r from-purple-400 to-pink-600 bg-clip-text text-transparent mb-2">
            AI Video Clipper (Private Mode)
          </h1>
          <p className="text-slate-400">Turn long videos into viral shorts in minutes.</p>
          <button
            onClick={() => setShowKeyModal(true)}
            className="text-xs text-slate-500 hover:text-purple-400 mt-2 underline"
          >
            {geminiKey && openaiKey ? 'Update API Keys' : 'Set API Keys'}
          </button>
        </header>

        {showKeyModal && (
          <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
            <div className="bg-slate-900 border border-slate-700 p-8 rounded-2xl max-w-md w-full shadow-2xl">
              <h2 className="text-2xl font-bold mb-4">API Keys Required</h2>
              <p className="text-slate-400 mb-6 text-sm">
                This tool uses <strong>OpenAI Whisper</strong> for accurate transcription and <strong>Google Gemini</strong> for intelligence.
              </p>

              <div className="space-y-4 mb-6">
                <div>
                  <label className="block text-xs font-bold text-slate-500 mb-1 uppercase">Gemini API Key</label>
                  <input
                    type="password"
                    placeholder="AIza..."
                    className="w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-3 focus:outline-none focus:border-purple-500 text-white"
                    value={geminiKey}
                    onChange={(e) => setGeminiKey(e.target.value)}
                  />
                  <a href="https://aistudio.google.com/app/apikey" target="_blank" className="text-xs text-purple-400 hover:underline mt-1 block">Get Gemini Key</a>
                </div>

                <div>
                  <label className="block text-xs font-bold text-slate-500 mb-1 uppercase">OpenAI API Key</label>
                  <input
                    type="password"
                    placeholder="sk-..."
                    className="w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-3 focus:outline-none focus:border-purple-500 text-white"
                    value={openaiKey}
                    onChange={(e) => setOpenaiKey(e.target.value)}
                  />
                  <a href="https://platform.openai.com/api-keys" target="_blank" className="text-xs text-purple-400 hover:underline mt-1 block">Get OpenAI Key</a>
                </div>
              </div>

              <button
                onClick={() => {
                  if (geminiKey.trim() && openaiKey.trim()) {
                    localStorage.setItem('clipper_gemini_key', geminiKey.trim())
                    localStorage.setItem('clipper_openai_key', openaiKey.trim())
                    setShowKeyModal(false)
                  }
                }}
                disabled={!geminiKey.trim() || !openaiKey.trim()}
                className="w-full bg-purple-600 hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed text-white font-bold py-3 rounded-lg transition-colors"
              >
                Save Keys
              </button>
            </div>
          </div>
        )}

        <main>
          {status === 'idle' && (
            <div className="space-y-12">
              <div className="border-2 border-dashed border-slate-700 rounded-xl p-12 text-center bg-slate-900/50 hover:bg-slate-900/80 transition-colors">
                <input
                  type="file"
                  accept="video/*"
                  className="hidden"
                  ref={fileInputRef}
                  onChange={handleFileChange}
                />

                {!file ? (
                  <div
                    className="cursor-pointer flex flex-col items-center gap-4"
                    onClick={() => fileInputRef.current?.click()}
                  >
                    <div className="p-4 bg-slate-800 rounded-full">
                      <Upload className="w-8 h-8 text-purple-400" />
                    </div>
                    <div>
                      <p className="text-lg font-medium">Click to upload video</p>
                      <p className="text-sm text-slate-500">MP4, MKV supported</p>
                    </div>
                  </div>
                ) : (
                  <div className="flex flex-col items-center gap-6">
                    <div className="flex items-center gap-3 text-emerald-400">
                      <FileVideo className="w-6 h-6" />
                      <span className="text-lg">{file.name}</span>
                    </div>
                    <button
                      onClick={startUpload}
                      className="bg-purple-600 hover:bg-purple-700 text-white px-8 py-3 rounded-full font-bold transition-all"
                    >
                      Start Magic
                    </button>
                    <button
                      onClick={() => setFile(null)}
                      className="text-slate-500 text-sm hover:text-slate-300"
                    >
                      Cancel
                    </button>
                  </div>
                )}
              </div>
            </div>
          )}

          {(status === 'uploading' || status === 'processing') && (
            <div className="text-center py-20">
              <div className="relative inline-flex mb-6">
                {(progress.startsWith('transcribing') || progress.startsWith('rendering') || progress.startsWith('uploading')) ? (
                  <div className="w-16 h-16 rounded-full border-4 border-slate-700 flex items-center justify-center relative">
                    <span className="text-xs font-bold text-slate-300">
                      {(() => {
                        const val = progress.split(': ')[1];
                        if (!val) return '...';
                        if (val === 'preparing...') return '5%';
                        return val;
                      })()}
                    </span>
                    <div className="absolute inset-0 rounded-full border-4 border-purple-500 border-t-transparent animate-spin opacity-50"></div>
                  </div>
                ) : (
                  <div className="w-16 h-16 border-4 border-purple-500/30 border-t-purple-500 rounded-full animate-spin"></div>
                )}
              </div>

              <h2 className="text-2xl font-semibold mb-2">
                {status === 'uploading' ? 'Uploading Video...' : 'Processing...'}
              </h2>

              {(progress.startsWith('transcribing') || progress.startsWith('rendering') || progress.startsWith('uploading')) ? (
                <div className="max-w-xs mx-auto mt-4">
                  <div className="flex justify-between text-xs text-slate-400 mb-1">
                    <span className="capitalize">{progress.split(':')[0]}</span>
                    <span>{progress.split(': ')[1]}</span>
                  </div>
                  <div className="w-full bg-slate-800 rounded-full h-2 overflow-hidden">
                    <div
                      className="bg-purple-500 h-full transition-all duration-300 ease-out"
                      style={{
                        width: (() => {
                          const val = progress.split(': ')[1];
                          if (!val) return '5%';
                          if (val === 'preparing...') return '5%';
                          if (progress.startsWith('rendering')) {
                            const parts = val.split('/') || [0, 1];
                            return `${Math.max(5, (parseInt(parts[0]) / parseInt(parts[1])) * 100)}%`;
                          }
                          // Handle percentages (uploading/transcribing)
                          return val.includes('%') ? val : `${val}%`;
                        })()
                      }}
                    ></div>
                  </div>
                </div>
              ) : progress.startsWith('analyzing') ? (
                <div className="max-w-xs mx-auto mt-4">
                  <div className="flex justify-between text-xs text-slate-400 mb-1">
                    <span className="capitalize">{progress}</span>
                    <span>AI is finding clips...</span>
                  </div>
                  <div className="w-full bg-slate-800 rounded-full h-2 overflow-hidden">
                    <div className="bg-purple-500 h-full w-full animate-pulse rounded-full"></div>
                  </div>
                </div>
              ) : (
                <p className="text-slate-400 capitalize mt-2">Current Step: {progress}</p>
              )}
            </div>
          )}

          {status === 'error' && (
            <div className="bg-red-900/20 border border-red-800 text-red-200 p-6 rounded-lg text-center">
              <h3 className="text-xl font-bold mb-2">Error Processing Video</h3>
              <p>{error}</p>
              <button
                onClick={() => { setStatus('idle'); setFile(null); setError(null); }}
                className="mt-4 bg-red-800 hover:bg-red-700 px-4 py-2 rounded"
              >
                Try Again
              </button>
            </div>
          )}

          {status === 'done' && (
            <div>
              <div className="flex items-center justify-between mb-8">
                <h2 className="text-2xl font-bold flex items-center gap-2">
                  <CheckCircle className="w-6 h-6 text-emerald-400" />
                  Generated Clips
                </h2>
                <button
                  onClick={() => { setStatus('idle'); setFile(null); setClips([]); }}
                  className="bg-slate-800 hover:bg-slate-700 px-4 py-2 rounded text-sm"
                >
                  Process New Video
                </button>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {[...clips].sort((a, b) => (b.score || 0) - (a.score || 0)).map((clip, idx) => (
                  <div key={idx} className="bg-slate-900 rounded-xl overflow-hidden border border-slate-800 flex flex-col">
                    <div className="aspect-[9/16] bg-black relative group">
                      <video
                        src={`${API_BASE}/static/${clip.path}`}
                        controls
                        className="w-full h-full object-cover"
                      />
                    </div>
                    <div className="p-4 flex flex-col flex-grow">
                      <div className="flex items-center gap-2 mb-3">
                        <Video className="w-4 h-4 text-purple-400 flex-shrink-0" />
                        <span className="text-sm font-medium truncate w-full" title={clip.title || `Clip ${idx + 1}`}>
                          {clip.title || `Clip ${idx + 1}`}
                        </span>
                        {clip.score != null && (
                          <span className={`text-xs font-bold px-2 py-0.5 rounded-full flex-shrink-0 ${clip.score >= 80 ? 'bg-emerald-900/50 text-emerald-400' :
                            clip.score >= 60 ? 'bg-yellow-900/50 text-yellow-400' :
                              'bg-slate-800 text-slate-400'
                            }`}>
                            {clip.score}
                          </span>
                        )}
                      </div>

                      {clip.transcript_text && (
                        <div className="bg-slate-950/50 p-3 rounded-lg border border-slate-800/50 mb-4 h-32 overflow-y-auto text-xs text-slate-400 leading-relaxed custom-scrollbar">
                          {clip.transcript_text}
                        </div>
                      )}

                      <div className="mt-auto">
                        <a
                          href={`${API_BASE}/static/${clip.path}`}
                          download
                          className="block w-full text-center bg-slate-800 hover:bg-slate-700 py-2 rounded text-sm font-medium transition-colors"
                        >
                          Download
                        </a>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

        </main>
      </div>
    </div>
  )
}

export default App
