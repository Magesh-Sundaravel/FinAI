import React, { useState, useEffect, useRef } from 'react'
import {
  LayoutDashboard,
  ReceiptText,
  MessageSquareCode,
  UploadCloud,
  Plus,
  Search,
  Trash2,
  Loader2,
  TrendingUp,
  Coins,
  DollarSign,
  AlertCircle,
  CheckCircle2,
  X,
  Send,
  HelpCircle
} from 'lucide-react'

// Backend API Base URL
const API_BASE = 'http://localhost:8000/api'

interface Expense {
  id: string
  date: string
  description: string
  category: string
  amount: number
}

interface Summary {
  total_spent: number
  average_transaction: number
  transaction_count: number
  by_category: Record<string, number>
  by_month: Record<string, number>
}

// High quality mock data for demo fallback
const DEMO_EXPENSES: Expense[] = [
  { id: '1', date: '2026-06-28', description: 'Amazon Web Services', category: 'Infrastructure', amount: 345.20 },
  { id: '2', date: '2026-06-25', description: 'Whole Foods Market', category: 'Groceries', amount: 156.80 },
  { id: '3', date: '2026-06-22', description: 'Uber Trip', category: 'Transport', amount: 24.50 },
  { id: '4', date: '2026-06-20', description: 'OpenAI API subscription', category: 'AI Tools', amount: 120.00 },
  { id: '5', date: '2026-06-18', description: 'Blue Bottle Coffee', category: 'Dining Out', amount: 18.75 },
  { id: '6', date: '2026-06-15', description: 'Landlord Rent', category: 'Rent', amount: 1800.00 },
  { id: '7', date: '2026-05-28', description: 'Amazon Web Services', category: 'Infrastructure', amount: 312.40 },
  { id: '8', date: '2026-05-24', description: 'Whole Foods Market', category: 'Groceries', amount: 142.10 },
  { id: '9', date: '2026-05-19', description: 'GitHub Copilot Enterprise', category: 'AI Tools', amount: 39.00 },
  { id: '10', date: '2026-05-14', description: 'Starbucks Coffee', category: 'Dining Out', amount: 12.50 },
]

const DEMO_SUMMARY: Summary = {
  total_spent: 3129.25,
  average_transaction: 312.93,
  transaction_count: 10,
  by_category: {
    'Rent': 1800.00,
    'Infrastructure': 657.60,
    'Groceries': 298.90,
    'AI Tools': 159.00,
    'Dining Out': 31.25,
    'Transport': 24.50
  },
  by_month: {
    '2026-05': 656.00,
    '2026-06': 2473.25
  }
}

function App() {
  const [activeTab, setActiveTab] = useState<'dashboard' | 'expenses' | 'agent' | 'upload'>('dashboard')
  const [expenses, setExpenses] = useState<Expense[]>([])
  const [summary, setSummary] = useState<Summary | null>(null)
  
  // UI states
  const [loading, setLoading] = useState(true)
  const [isDemoMode, setIsDemoMode] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [filterCategory, setFilterCategory] = useState('')
  const [showAddModal, setShowAddModal] = useState(false)
  const [toast, setToast] = useState<{ type: 'success' | 'error' | 'info'; message: string } | null>(null)
  
  // Form states
  const [newDate, setNewDate] = useState(new Date().toISOString().split('T')[0])
  const [newDesc, setNewDesc] = useState('')
  const [newCat, setNewCat] = useState('')
  const [newAmt, setNewAmt] = useState('')
  
  // Chat states
  const [chatMessages, setChatMessages] = useState<Array<{ sender: 'user' | 'agent'; text: string }>>([
    {
      sender: 'agent',
      text: "Hello! I'm your Finance AI Agent. Upload your expenses spreadsheet to get started, or ask me questions about your budget!"
    }
  ])
  const [chatInput, setChatInput] = useState('')
  const [chatLoading, setChatLoading] = useState(false)
  const chatBottomRef = useRef<HTMLDivElement>(null)

  // Upload States
  const [isDragging, setIsDragging] = useState(false)
  const [uploadFile, setUploadFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)

  // Load data
  useEffect(() => {
    fetchData()
  }, [])

  // Auto scroll chat
  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [chatMessages])

  const showToast = (type: 'success' | 'error' | 'info', message: string) => {
    setToast({ type, message })
    setTimeout(() => setToast(null), 4000)
  }

  const fetchData = async () => {
    setLoading(true)
    try {
      // Fetch summary and expenses in parallel
      const [expRes, sumRes] = await Promise.all([
        fetch(`${API_BASE}/expenses/`),
        fetch(`${API_BASE}/expenses/summary`)
      ])

      if (expRes.ok && sumRes.ok) {
        const expData = await expRes.json()
        const sumData = await sumRes.json()
        
        if (expData.length === 0) {
          // If connection succeeds but data is empty, set to empty state
          setExpenses([])
          setSummary(null)
          setIsDemoMode(false)
        } else {
          setExpenses(expData)
          setSummary(sumData)
          setIsDemoMode(false)
        }
      } else {
        throw new Error("Failed to fetch data")
      }
    } catch (err) {
      console.warn("Backend not reachable. Falling back to Demo Mode.", err)
      setExpenses(DEMO_EXPENSES)
      setSummary(DEMO_SUMMARY)
      setIsDemoMode(true)
      showToast('info', 'Running in local sandbox mode. Start the FastAPI server to save your actual data.')
    } finally {
      setLoading(false)
    }
  }

  const handleManualAdd = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!newDesc || !newAmt) {
      showToast('error', 'Please fill out description and amount')
      return
    }

    const payload = {
      date: newDate,
      description: newDesc,
      category: newCat || 'Uncategorized',
      amount: parseFloat(newAmt)
    }

    if (isDemoMode) {
      // Mock save
      const mockNew: Expense = {
        id: String(Date.now()),
        ...payload
      }
      const updated = [mockNew, ...expenses]
      setExpenses(updated)
      
      // Update summary
      const newTotal = (summary?.total_spent || 0) + payload.amount
      const newCount = (summary?.transaction_count || 0) + 1
      const newCategories = { ...(summary?.by_category || {}) }
      newCategories[payload.category] = (newCategories[payload.category] || 0) + payload.amount
      
      const newMonths = { ...(summary?.by_month || {}) }
      const monthKey = payload.date.substring(0, 7)
      newMonths[monthKey] = (newMonths[monthKey] || 0) + payload.amount

      setSummary({
        total_spent: newTotal,
        average_transaction: newTotal / newCount,
        transaction_count: newCount,
        by_category: newCategories,
        by_month: newMonths
      })

      showToast('success', 'Transaction added to local sandbox')
      setShowAddModal(false)
      // reset form
      setNewDesc('')
      setNewAmt('')
      setNewCat('')
      return
    }

    try {
      const res = await fetch(`${API_BASE}/expenses/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })

      if (res.ok) {
        showToast('success', 'Expense created successfully!')
        setShowAddModal(false)
        setNewDesc('')
        setNewAmt('')
        setNewCat('')
        fetchData()
      } else {
        showToast('error', 'Failed to save transaction')
      }
    } catch (err) {
      showToast('error', 'Could not reach server')
    }
  }

  const handleClear = async () => {
    if (!window.confirm("Are you sure you want to clear ALL expense data?")) return
    
    if (isDemoMode) {
      setExpenses([])
      setSummary(null)
      showToast('success', 'Sandbox expenses cleared')
      return
    }

    try {
      const res = await fetch(`${API_BASE}/expenses/clear`, { method: 'DELETE' })
      if (res.ok) {
        showToast('success', 'Expenses database cleared')
        fetchData()
      } else {
        showToast('error', 'Failed to clear database')
      }
    } catch (err) {
      showToast('error', 'Server error')
    }
  }

  const handleFileUpload = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!uploadFile) return

    setUploading(true)
    const formData = new FormData()
    formData.append('file', uploadFile)

    if (isDemoMode) {
      showToast('error', 'Cannot upload spreadsheets in sandbox mode. Please start the backend FastAPI server first!')
      setUploading(false)
      return
    }

    try {
      const res = await fetch(`${API_BASE}/expenses/upload`, {
        method: 'POST',
        body: formData
      })
      const data = await res.json()
      if (res.ok) {
        showToast('success', data.message || 'File uploaded successfully!')
        setUploadFile(null)
        setActiveTab('dashboard')
        fetchData()
      } else {
        showToast('error', data.detail || 'Upload processing failed')
      }
    } catch (err) {
      showToast('error', 'Server connection error during upload')
    } finally {
      setUploading(false)
    }
  }

  const handleChatSend = async (msgText: string) => {
    if (!msgText.trim()) return

    const userMsg = { sender: 'user' as const, text: msgText }
    setChatMessages(prev => [...prev, userMsg])
    setChatInput('')
    setChatLoading(true)

    // Append loading placeholder
    try {
      const res = await fetch(`${API_BASE}/agent/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: msgText })
      })
      
      if (res.ok) {
        const data = await res.json()
        setChatMessages(prev => [...prev, { sender: 'agent', text: data.response }])
      } else {
        throw new Error("Chat error")
      }
    } catch (err) {
      // Local fallback parsing for sandbox mode
      setTimeout(() => {
        let reply = "Sorry, I had trouble reaching my AI core. Check your server connection."
        const lower = msgText.toLowerCase()
        const total = summary?.total_spent || 0
        const count = expenses.length
        
        if (lower.includes("total") || lower.includes("how much")) {
          reply = `In this sandbox, your total spending is **$${total.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}** across **${count}** transaction(s).`
        } else if (lower.includes("category") || lower.includes("categories")) {
          const cats = summary ? Object.keys(summary.by_category).map(c => `- **${c}**: $${summary.by_category[c].toLocaleString()}`).join('\n') : '';
          reply = `Here is your sandbox category spending:\n\n${cats || 'No categories found.'}`
        } else if (lower.includes("highest") || lower.includes("max")) {
          if (expenses.length > 0) {
            const highest = expenses.reduce((prev, current) => (prev.amount > current.amount) ? prev : current)
            reply = `Your single largest expense in the sandbox is **$${highest.amount.toLocaleString()}** for **${highest.description}** (${highest.category}) on **${highest.date}**.`
          } else {
            reply = "You don't have any sandbox expenses loaded yet!"
          }
        } else {
          reply = `I am running in local sandbox mode. Ask me about your:
- *"Total spending"*
- *"Spending by category"*
- *"Highest expense"*

Or start the backend server to link actual spreadsheet parser results!`
        }
        
        setChatMessages(prev => [...prev, { sender: 'agent', text: reply }])
      }, 600)
    } finally {
      setChatLoading(false)
    }
  }

  // Drag & drop handlers
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }

  const handleDragLeave = () => {
    setIsDragging(false)
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const file = e.dataTransfer.files[0]
      const ext = file.name.substring(file.name.lastIndexOf('.')).toLowerCase()
      if (['.csv', '.xlsx', '.xls'].includes(ext)) {
        setUploadFile(file)
      } else {
        showToast('error', 'Only CSV or Excel spreadsheets are supported')
      }
    }
  }

  // Filter and search calculations
  const filteredExpenses = expenses.filter(e => {
    const matchesSearch = e.description.toLowerCase().includes(searchQuery.toLowerCase()) || 
                          e.category.toLowerCase().includes(searchQuery.toLowerCase())
    const matchesCategory = filterCategory === '' || e.category.toLowerCase() === filterCategory.toLowerCase()
    return matchesSearch && matchesCategory
  })

  const uniqueCategories = Array.from(new Set(expenses.map(e => e.category)))

  // SVG Chart Helper Data Calculations
  const renderSvgChart = () => {
    if (!summary || !summary.by_month || Object.keys(summary.by_month).length === 0) {
      return (
        <div style={{ margin: 'auto', textAlign: 'center', color: 'var(--text-muted)' }}>
          No data available for chart. Upload data.
        </div>
      )
    }

    const months = Object.keys(summary.by_month).sort()
    const values = months.map(m => summary.by_month[m])
    const maxVal = Math.max(...values, 100)
    
    // Grid values
    const chartHeight = 220
    const chartWidth = 500
    const paddingLeft = 60
    const paddingBottom = 30
    const barWidth = Math.min(45, (chartWidth - paddingLeft) / months.length - 15)
    
    return (
      <svg className="chart-svg" viewBox={`0 0 ${chartWidth} ${chartHeight + paddingBottom}`}>
        <defs>
          <linearGradient id="barGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--primary)" />
            <stop offset="100%" stopColor="var(--primary-glow)" />
          </linearGradient>
          <linearGradient id="barHoverGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--success)" />
            <stop offset="100%" stopColor="var(--success-glow)" />
          </linearGradient>
        </defs>

        {/* Y Axis Gridlines */}
        {[0, 0.25, 0.5, 0.75, 1].map((ratio, index) => {
          const y = chartHeight * (1 - ratio)
          const val = Math.round(maxVal * ratio)
          return (
            <g key={index}>
              <line x1={paddingLeft} y1={y} x2={chartWidth} y2={y} className="chart-grid-line" />
              <text x={paddingLeft - 10} y={y + 4} textAnchor="end" className="chart-text">
                ${val >= 1000 ? (val / 1000).toFixed(1) + 'k' : val}
              </text>
            </g>
          )
        })}

        {/* X Axis labels & Bars */}
        {months.map((month, index) => {
          const val = summary.by_month[month]
          const ratio = val / maxVal
          const barHeight = chartHeight * ratio
          
          // spacing
          const sectionWidth = (chartWidth - paddingLeft) / months.length
          const x = paddingLeft + (index * sectionWidth) + (sectionWidth - barWidth) / 2
          const y = chartHeight - barHeight

          return (
            <g key={index}>
              {/* Bar */}
              <rect
                x={x}
                y={y}
                width={barWidth}
                height={barHeight}
                className="chart-bar"
              >
                <title>{`${month}: $${val.toLocaleString()}`}</title>
              </rect>
              {/* Label */}
              <text
                x={x + barWidth / 2}
                y={chartHeight + 18}
                textAnchor="middle"
                className="chart-text"
              >
                {month}
              </text>
              {/* Value on bar */}
              {barHeight > 25 && (
                <text
                  x={x + barWidth / 2}
                  y={y + 15}
                  textAnchor="middle"
                  fill="#ffffff"
                  fontSize="9px"
                  fontWeight="600"
                >
                  ${val >= 1000 ? (val/1000).toFixed(0)+'k' : Math.round(val)}
                </text>
              )}
            </g>
          )
        })}
      </svg>
    )
  }

  return (
    <>
      {/* Header */}
      <header className="app-header">
        <div className="logo-container">
          <div className="logo-icon">
            <Coins />
          </div>
          <div className="logo-text">
            <h1>FinAI</h1>
            <p>Finance AI Agents</p>
          </div>
        </div>

        {isDemoMode && (
          <div style={{
            background: 'var(--warning)',
            color: '#000',
            padding: '6px 12px',
            borderRadius: '6px',
            fontSize: '12px',
            fontWeight: '600',
            display: 'flex',
            alignItems: 'center',
            gap: '6px'
          }}>
            <AlertCircle size={14} /> Local Sandbox Mode
          </div>
        )}

        <nav className="nav-tabs">
          <button
            onClick={() => setActiveTab('dashboard')}
            className={`tab-btn ${activeTab === 'dashboard' ? 'active' : ''}`}
          >
            <LayoutDashboard /> Dashboard
          </button>
          <button
            onClick={() => setActiveTab('expenses')}
            className={`tab-btn ${activeTab === 'expenses' ? 'active' : ''}`}
          >
            <ReceiptText /> Expenses
          </button>
          <button
            onClick={() => setActiveTab('agent')}
            className={`tab-btn ${activeTab === 'agent' ? 'active' : ''}`}
          >
            <MessageSquareCode /> AI Agent
          </button>
          <button
            onClick={() => setActiveTab('upload')}
            className={`tab-btn ${activeTab === 'upload' ? 'active' : ''}`}
          >
            <UploadCloud /> Ingest
          </button>
        </nav>
      </header>

      {/* Main Content Area */}
      {loading ? (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '400px', gap: '16px' }}>
          <Loader2 className="animate-spin" size={48} style={{ color: 'var(--primary)' }} />
          <p style={{ color: 'var(--text-secondary)' }}>Loading financial environment...</p>
        </div>
      ) : (
        <main>
          {/* TAB: DASHBOARD */}
          {activeTab === 'dashboard' && (
            <div>
              {/* Metric Cards Grid */}
              <div className="dashboard-grid">
                <div className="metric-card success">
                  <div className="metric-header">
                    <span>Total Tracked Spend</span>
                    <div className="metric-icon">
                      <DollarSign size={18} />
                    </div>
                  </div>
                  <div className="metric-value">
                    ${(summary?.total_spent || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </div>
                  <div className="metric-sub">Aggregated budget total</div>
                </div>

                <div className="metric-card primary">
                  <div className="metric-header">
                    <span>Average Expense</span>
                    <div className="metric-icon">
                      <TrendingUp size={18} />
                    </div>
                  </div>
                  <div className="metric-value">
                    ${(summary?.average_transaction || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </div>
                  <div className="metric-sub">Average transaction size</div>
                </div>

                <div className="metric-card warning">
                  <div className="metric-header">
                    <span>Total Transactions</span>
                    <div className="metric-icon">
                      <ReceiptText size={18} />
                    </div>
                  </div>
                  <div className="metric-value">
                    {(summary?.transaction_count || 0)}
                  </div>
                  <div className="metric-sub">Receipts & ledger statements</div>
                </div>

                <div className="metric-card success">
                  <div className="metric-header">
                    <span>Active Categories</span>
                    <div className="metric-icon">
                      <Coins size={18} />
                    </div>
                  </div>
                  <div className="metric-value">
                    {summary ? Object.keys(summary.by_category).length : 0}
                  </div>
                  <div className="metric-sub">Categorized spending pools</div>
                </div>
              </div>

              {/* Charts & Visual Analytics */}
              <div className="visuals-section">
                {/* Monthly SVG Chart */}
                <div className="card">
                  <div className="card-title">
                    <span>Monthly Spends Analysis</span>
                    <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Trend</span>
                  </div>
                  <div className="chart-container">
                    {renderSvgChart()}
                  </div>
                </div>

                {/* Category Aggregates */}
                <div className="card">
                  <div className="card-title">
                    <span>Category Breakdown</span>
                    <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Share</span>
                  </div>
                  <div className="category-list">
                    {summary && Object.keys(summary.by_category).length > 0 ? (
                      Object.keys(summary.by_category).map((category, idx) => {
                        const amt = summary.by_category[category]
                        const total = summary.total_spent || 1
                        const pct = Math.round((amt / total) * 100)
                        
                        return (
                          <div className="category-row" key={idx}>
                            <div className="category-info">
                              <span className="category-name">
                                <span className="category-dot" style={{ backgroundColor: `hsl(${(idx * 60) % 360}, 70%, 60%)` }} />
                                {category}
                              </span>
                              <span className="category-amount">${amt.toLocaleString()} ({pct}%)</span>
                            </div>
                            <div className="category-bar-bg">
                              <div
                                className="category-bar-fill"
                                style={{
                                  width: `${pct}%`,
                                  background: `linear-gradient(90deg, hsl(${(idx * 60) % 360}, 70%, 50%), var(--success))`
                                }}
                              />
                            </div>
                          </div>
                        )
                      })
                    ) : (
                      <div style={{ margin: 'auto', textAlign: 'center', color: 'var(--text-muted)', paddingTop: '60px' }}>
                        No categories found.
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB: EXPENSES TABLE */}
          {activeTab === 'expenses' && (
            <div className="card">
              <div className="search-bar-row">
                <div className="search-input-wrapper">
                  <Search />
                  <input
                    type="text"
                    className="search-input"
                    placeholder="Search expenses by vendor or description..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                  />
                </div>

                <div style={{ display: 'flex', gap: '12px' }}>
                  <select
                    className="filter-select"
                    value={filterCategory}
                    onChange={(e) => setFilterCategory(e.target.value)}
                  >
                    <option value="">All Categories</option>
                    {uniqueCategories.map((c, i) => (
                      <option key={i} value={c}>{c}</option>
                    ))}
                  </select>

                  <button className="btn" onClick={() => setShowAddModal(true)}>
                    <Plus size={16} /> Add Expense
                  </button>

                  {expenses.length > 0 && (
                    <button className="btn btn-danger" onClick={handleClear}>
                      <Trash2 size={16} /> Clear All
                    </button>
                  )}
                </div>
              </div>

              <div className="table-container">
                {filteredExpenses.length > 0 ? (
                  <table className="expenses-table">
                    <thead>
                      <tr>
                        <th>Date</th>
                        <th>Description</th>
                        <th>Category</th>
                        <th style={{ textAlign: 'right' }}>Amount</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredExpenses.map((expense) => (
                        <tr key={expense.id}>
                          <td style={{ color: 'var(--text-secondary)' }}>{expense.date}</td>
                          <td style={{ fontWeight: '500' }}>{expense.description}</td>
                          <td>
                            <span className="tag tag-category">
                              {expense.category}
                            </span>
                          </td>
                          <td style={{ textAlign: 'right' }} className="amount-text negative">
                            ${expense.amount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : (
                  <div style={{ padding: '60px', textAlign: 'center', color: 'var(--text-secondary)' }}>
                    <HelpCircle size={36} style={{ marginBottom: '12px', color: 'var(--text-muted)' }} />
                    <p>No transaction items found matching your filters.</p>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* TAB: AI AGENT */}
          {activeTab === 'agent' && (
            <div className="chat-layout">
              <div className="chat-header">
                <div className="chat-agent-info">
                  <div className="chat-avatar">
                    <MessageSquareCode size={18} />
                  </div>
                  <div className="chat-agent-name">
                    <h3>Finance AI Agent</h3>
                    <div className="chat-agent-status">Online</div>
                  </div>
                </div>
                <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                  Active Agent Engine
                </div>
              </div>

              {/* Chat Message Panel */}
              <div className="chat-messages">
                {chatMessages.map((msg, index) => (
                  <div key={index} className={`chat-bubble ${msg.sender}`}>
                    <div style={{ whiteSpace: 'pre-line' }}>{msg.text}</div>
                  </div>
                ))}
                {chatLoading && (
                  <div className="chat-bubble agent loading">
                    <div className="dot-pulse"></div>
                    <div className="dot-pulse"></div>
                    <div className="dot-pulse"></div>
                  </div>
                )}
                <div ref={chatBottomRef} />
              </div>

              {/* Chat Quick Actions */}
              <div className="chat-suggestions">
                <button className="suggestion-chip" onClick={() => handleChatSend("How much did I spend in total?")}>
                  How much did I spend in total?
                </button>
                <button className="suggestion-chip" onClick={() => handleChatSend("Show spending by category")}>
                  Show spending by category
                </button>
                <button className="suggestion-chip" onClick={() => handleChatSend("What is my highest expense?")}>
                  What is my highest expense?
                </button>
              </div>

              {/* Chat Input */}
              <div className="chat-input-row">
                <input
                  type="text"
                  className="chat-input"
                  placeholder="Ask the Finance Agent about your spreadsheet expenses..."
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') handleChatSend(chatInput)
                  }}
                  disabled={chatLoading}
                />
                <button className="btn" onClick={() => handleChatSend(chatInput)} disabled={chatLoading}>
                  <Send size={16} /> Send
                </button>
              </div>
            </div>
          )}

          {/* TAB: INGEST/UPLOAD */}
          {activeTab === 'upload' && (
            <div className="card" style={{ maxWidth: '600px', margin: '0 auto' }}>
              <div className="card-title">Import Expense Spreadsheets</div>
              <p style={{ color: 'var(--text-secondary)', fontSize: '14px', marginBottom: '24px' }}>
                Upload your tracked expenses spreadsheet. We accept **CSV** or **Excel (.xlsx, .xls)**.
                Our parser automatically detects date, transaction description, category labels, and pricing columns.
              </p>

              <form onSubmit={handleFileUpload}>
                <div
                  className="upload-container"
                  onDragOver={handleDragOver}
                  onDragLeave={handleDragLeave}
                  onDrop={handleDrop}
                  style={{
                    borderColor: isDragging ? 'var(--primary)' : 'rgba(255,255,255,0.1)',
                    background: isDragging ? 'rgba(99, 102, 241, 0.05)' : 'rgba(255,255,255,0.01)'
                  }}
                  onClick={() => document.getElementById('file-upload-input')?.click()}
                >
                  <input
                    type="file"
                    id="file-upload-input"
                    className="upload-file-input"
                    accept=".csv, .xlsx, .xls"
                    onChange={(e) => {
                      if (e.target.files && e.target.files[0]) {
                        setUploadFile(e.target.files[0])
                      }
                    }}
                  />
                  <div className="upload-icon">
                    <UploadCloud size={32} />
                  </div>
                  
                  {uploadFile ? (
                    <div>
                      <div className="upload-title" style={{ color: 'var(--success)' }}>
                        File Selected
                      </div>
                      <div className="upload-sub" style={{ fontWeight: '600', color: '#fff' }}>
                        {uploadFile.name} ({(uploadFile.size / 1024).toFixed(1)} KB)
                      </div>
                    </div>
                  ) : (
                    <div>
                      <div className="upload-title">Drag & drop your file here</div>
                      <div className="upload-sub">or click to browse from files</div>
                    </div>
                  )}
                  
                  <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                    Supported formats: CSV, XLS, XLSX
                  </span>
                </div>

                {uploadFile && (
                  <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', marginTop: '24px' }}>
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={() => setUploadFile(null)}
                      disabled={uploading}
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      className="btn"
                      disabled={uploading}
                    >
                      {uploading ? (
                        <>
                          <Loader2 className="animate-spin" size={16} /> Parsing Ledger...
                        </>
                      ) : (
                        "Import Ledger"
                      )}
                    </button>
                  </div>
                )}
              </form>
            </div>
          )}
        </main>
      )}

      {/* Manual Add Expense Modal */}
      {showAddModal && (
        <div className="modal-overlay">
          <div className="modal-content">
            <div className="modal-header">
              <h3>Track Manual Expense</h3>
              <button className="close-btn" onClick={() => setShowAddModal(false)}>
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleManualAdd}>
              <div className="form-group">
                <label className="form-label">Transaction Date</label>
                <input
                  type="date"
                  className="form-input"
                  required
                  value={newDate}
                  onChange={(e) => setNewDate(e.target.value)}
                />
              </div>

              <div className="form-group">
                <label className="form-label">Description / Payee</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="e.g. AWS Subscriptions, Target Store"
                  required
                  value={newDesc}
                  onChange={(e) => setNewDesc(e.target.value)}
                />
              </div>

              <div className="form-group">
                <label className="form-label">Category</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="e.g. Infrastructure, Groceries, Rent"
                  value={newCat}
                  onChange={(e) => setNewCat(e.target.value)}
                />
              </div>

              <div className="form-group">
                <label className="form-label">Amount ($ USD)</label>
                <input
                  type="number"
                  step="0.01"
                  className="form-input"
                  placeholder="0.00"
                  required
                  value={newAmt}
                  onChange={(e) => setNewAmt(e.target.value)}
                />
              </div>

              <div className="form-actions">
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setShowAddModal(false)}
                >
                  Cancel
                </button>
                <button type="submit" className="btn">
                  Add to Ledger
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Alert Toasts */}
      {toast && (
        <div className={`alert-toast ${toast.type}`}>
          {toast.type === 'success' && <CheckCircle2 size={16} />}
          {toast.type === 'error' && <AlertCircle size={16} />}
          <span>{toast.message}</span>
        </div>
      )}
    </>
  )
}

export default App
