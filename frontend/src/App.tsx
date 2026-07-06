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
  Euro,
  AlertCircle,
  CheckCircle2,
  X,
  Send,
  HelpCircle,
  Calendar,
  User,
  LogOut
} from 'lucide-react'

// Backend API Base URL
const API_BASE = window.location.origin.includes('localhost:5173') ? 'http://localhost:8000/api' : window.location.origin + '/api'

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
  by_season?: Record<string, number>
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
  },
  by_season: {
    'Winter': 0.0,
    'Spring': 656.00,
    'Summer': 2473.25,
    'Autumn': 0.0
  }
}

function App() {
  const [activeTab, setActiveTab] = useState<'home' | 'monthly' | 'yearly' | 'expenses' | 'agent' | 'upload' | 'profile'>('home')
  const [expenses, setExpenses] = useState<Expense[]>([])
  const [summary, setSummary] = useState<Summary | null>(null)
  const [selectedMonth, setSelectedMonth] = useState<string>('')
  const [profile, setProfile] = useState<{ email: string; total_spent: number; transaction_count: number; created_at: string | null } | null>(null)
  
  // UI states
  const [loading, setLoading] = useState(true)
  const [isDemoMode, setIsDemoMode] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [filterCategory, setFilterCategory] = useState('')
  const [chartYearFilter, setChartYearFilter] = useState<string>('last12')
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

  // OCR Ingestion confirmation states
  const [ocrResult, setOcrResult] = useState<{
    date: string
    description: string
    category: string
    amount: number
    bill_image_url: string
  } | null>(null)
  const [ocrDate, setOcrDate] = useState('')
  const [ocrDesc, setOcrDesc] = useState('')
  const [ocrCat, setOcrCat] = useState('')
  const [ocrAmt, setOcrAmt] = useState('')

  // Upload States
  const [isDragging, setIsDragging] = useState(false)
  const [uploadFile, setUploadFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)

  // Helper to get season from date
  const getSeasonFromDate = (dateStr: string) => {
    const month = parseInt(dateStr.substring(5, 7))
    if (isNaN(month)) return 'Unknown'
    if (month === 12 || month === 1 || month === 2) return 'Winter'
    if (month >= 3 && month <= 5) return 'Spring'
    if (month >= 6 && month <= 8) return 'Summer'
    return 'Autumn'
  }
  
  // Calculate seasonal spends dynamically if missing
  const getSeasonalData = () => {
    if (summary?.by_season) return summary.by_season
    
    const seasonal: Record<string, number> = {
      'Winter': 0,
      'Spring': 0,
      'Summer': 0,
      'Autumn': 0
    }
    expenses.forEach(e => {
      const season = getSeasonFromDate(e.date)
      if (season in seasonal) {
        seasonal[season] += e.amount
      }
    })
    return seasonal
  }

  // Get dominant category for season
  const getDominantCategoryForSeason = (seasonName: string) => {
    const seasonExpenses = expenses.filter(e => getSeasonFromDate(e.date) === seasonName)
    if (seasonExpenses.length === 0) return 'None'
    const catMap: Record<string, number> = {}
    seasonExpenses.forEach(e => {
      catMap[e.category] = (catMap[e.category] || 0) + e.amount
    })
    return Object.keys(catMap).reduce((a, b) => catMap[a] > catMap[b] ? a : b, 'None')
  }

  // Get all unique months in data
  const getAvailableMonths = () => {
    if (expenses.length === 0) return []
    const months = Array.from(new Set(expenses.map(e => e.date.substring(0, 7))))
    return months.sort().reverse()
  }

  // Auto set selected month
  useEffect(() => {
    const months = getAvailableMonths()
    if (months.length > 0 && !selectedMonth) {
      setSelectedMonth(months[0])
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [expenses])

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
      // Fetch summary, expenses, and profile in parallel
      const [expRes, sumRes, profRes] = await Promise.all([
        fetch(`${API_BASE}/expenses/`),
        fetch(`${API_BASE}/expenses/summary`),
        fetch(`${API_BASE}/expenses/profile`)
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

      if (profRes.ok) {
        const profData = await profRes.json()
        setProfile(profData)
      }
    } catch (err) {
      console.warn("Backend not reachable. Falling back to Demo Mode.", err)
      setExpenses(DEMO_EXPENSES)
      setSummary(DEMO_SUMMARY)
      setProfile({
        email: "demo-user@gmail.com",
        total_spent: DEMO_SUMMARY.total_spent,
        transaction_count: DEMO_SUMMARY.transaction_count,
        created_at: "2026-07-06"
      })
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
    } catch {
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
    } catch {
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
      showToast('error', 'Cannot upload files in sandbox mode. Please start the backend FastAPI server first!')
      setUploading(false)
      return
    }

    const ext = uploadFile.name.substring(uploadFile.name.lastIndexOf('.')).toLowerCase()
    const isImage = ['.png', '.jpg', '.jpeg', '.webp'].includes(ext)

    try {
      const url = isImage 
        ? `${API_BASE}/expenses/upload?save=false`
        : `${API_BASE}/expenses/upload`
        
      const res = await fetch(url, {
        method: 'POST',
        body: formData
      })
      const data = await res.json()
      
      if (res.ok) {
        if (isImage) {
          showToast('success', 'OCR reading completed successfully!')
          const parsed = data.expense
          setOcrResult(parsed)
          setOcrDate(parsed.date || '')
          setOcrDesc(parsed.description || '')
          setOcrCat(parsed.category || '')
          setOcrAmt(String(parsed.amount || ''))
        } else {
          showToast('success', data.message || 'Spreadsheet uploaded successfully!')
          setUploadFile(null)
          setActiveTab('home')
          fetchData()
        }
      } else {
        showToast('error', data.detail || 'Upload processing failed')
      }
    } catch {
      showToast('error', 'Server connection error during upload')
    } finally {
      setUploading(false)
    }
  }

  const handleOcrConfirm = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!ocrResult) return

    try {
      const res = await fetch(`${API_BASE}/expenses/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          date: ocrDate,
          description: ocrDesc,
          category: ocrCat,
          amount: parseFloat(ocrAmt) || 0.0,
          bill_image_url: ocrResult.bill_image_url
        })
      })
      
      if (res.ok) {
        showToast('success', 'Expense confirmed and saved to database!')
        setOcrResult(null)
        setUploadFile(null)
        setActiveTab('home')
        fetchData()
      } else {
        const data = await res.json()
        showToast('error', data.detail || 'Failed to save transaction')
      }
    } catch {
      showToast('error', 'Could not reach server')
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
    } catch {
      // Local fallback parsing for sandbox mode
      setTimeout(() => {
        let reply = "Sorry, I had trouble reaching my AI core. Check your server connection."
        const lower = msgText.toLowerCase()
        const total = summary?.total_spent || 0
        const count = expenses.length
        
        if (lower.includes("total") || lower.includes("how much")) {
          reply = `In this sandbox, your total spending is **€${total.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}** across **${count}** transaction(s).`
        } else if (lower.includes("category") || lower.includes("categories")) {
          const cats = summary ? Object.keys(summary.by_category).map(c => `- **${c}**: €${summary.by_category[c].toLocaleString()}`).join('\n') : '';
          reply = `Here is your sandbox category spending:\n\n${cats || 'No categories found.'}`
        } else if (lower.includes("highest") || lower.includes("max")) {
          if (expenses.length > 0) {
            const highest = expenses.reduce((prev, current) => (prev.amount > current.amount) ? prev : current)
            reply = `Your single largest expense in the sandbox is **€${highest.amount.toLocaleString()}** for **${highest.description}** (${highest.category}) on **${highest.date}**.`
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
      if (['.csv', '.xlsx', '.xls', '.png', '.jpg', '.jpeg', '.webp'].includes(ext)) {
        setUploadFile(file)
      } else {
        showToast('error', 'Only CSV/Excel spreadsheets or PNG/JPG/WEBP images are supported')
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

  // Selected Month Calculations
  const selectedMonthExpenses = expenses.filter(e => e.date.substring(0, 7) === selectedMonth)
  const selectedMonthTotal = selectedMonthExpenses.reduce((sum, e) => sum + e.amount, 0)
  const selectedMonthCount = selectedMonthExpenses.length
  const selectedMonthAvg = selectedMonthCount > 0 ? selectedMonthTotal / selectedMonthCount : 0
  
  const selectedMonthCats: Record<string, number> = {}
  selectedMonthExpenses.forEach(e => {
    selectedMonthCats[e.category] = (selectedMonthCats[e.category] || 0) + e.amount
  })
  
  const utilityCategories = ['rent', 'wifi', 'electricity', 'gas']
  const utilityTotals: Record<string, number> = {
    'rent': 0,
    'wifi': 0,
    'electricity': 0,
    'gas': 0
  }
  selectedMonthExpenses.forEach(e => {
    const catLower = e.category.toLowerCase()
    if (utilityCategories.includes(catLower)) {
      utilityTotals[catLower] += e.amount
    }
  })

  // SVG Chart Helper Data Calculations
  const renderSvgChart = () => {
    if (!summary || !summary.by_month || Object.keys(summary.by_month).length === 0) {
      return (
        <div style={{ margin: 'auto', textAlign: 'center', color: 'var(--text-muted)' }}>
          No data available for chart. Upload data.
        </div>
      )
    }

    const allMonths = Object.keys(summary.by_month).sort()
    
    // Apply filter
    let months = [...allMonths]
    if (chartYearFilter === 'last12') {
      months = months.slice(-12)
    } else if (chartYearFilter === 'last24') {
      months = months.slice(-24)
    } else if (chartYearFilter !== 'all') {
      months = months.filter(m => m.startsWith(chartYearFilter))
    }

    if (months.length === 0) {
      return (
        <div style={{ margin: 'auto', padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>
          No data available for the selected range.
        </div>
      )
    }

    const values = months.map(m => summary.by_month[m])
    const maxVal = Math.max(...values, 100)
    
    // Grid values
    const chartHeight = 220
    const paddingLeft = 60
    const paddingBottom = 35
    const colWidth = 55
    const chartWidth = Math.max(500, paddingLeft + months.length * colWidth)
    const barWidth = 26
    
    return (
      <svg 
        className="chart-svg" 
        viewBox={`0 0 ${chartWidth} ${chartHeight + paddingBottom}`}
        style={{ width: `${chartWidth}px`, height: '100%', minWidth: `${chartWidth}px` }}
      >
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
                €{val >= 1000 ? (val / 1000).toFixed(1) + 'k' : val}
              </text>
            </g>
          )
        })}

        {/* X Axis labels & Bars */}
        {months.map((month, index) => {
          const val = summary.by_month[month]
          const ratio = val / maxVal
          const barHeight = chartHeight * ratio
          
          const x = paddingLeft + index * colWidth + (colWidth - barWidth) / 2
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
                <title>{`${month}: €${val.toLocaleString()}`}</title>
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
              <text
                x={x + barWidth / 2}
                y={y - 6}
                textAnchor="middle"
                fill="var(--text-secondary)"
                fontSize="9px"
                fontWeight="600"
              >
                €{val >= 1000 ? (val/1000).toFixed(0)+'k' : Math.round(val)}
              </text>
            </g>
          )
        })}
      </svg>
    )
  }

  const renderSeasonalSvgChart = () => {
    const seasonalData = getSeasonalData()
    const seasons = ['Winter', 'Spring', 'Summer', 'Autumn']
    const values = seasons.map(s => seasonalData[s] || 0)
    const maxVal = Math.max(...values, 100)
    
    const chartHeight = 220
    const chartWidth = 500
    const paddingLeft = 60
    const paddingBottom = 30
    const barWidth = 60
    
    const colors = {
      'Winter': 'var(--winter-color, #38bdf8)',
      'Spring': 'var(--spring-color, #4ade80)',
      'Summer': 'var(--summer-color, #fbbf24)',
      'Autumn': 'var(--autumn-color, #fb923c)'
    }
    
    return (
      <svg className="chart-svg" viewBox={`0 0 ${chartWidth} ${chartHeight + paddingBottom}`}>
        {/* Y Axis Gridlines */}
        {[0, 0.25, 0.5, 0.75, 1].map((ratio, index) => {
          const y = chartHeight * (1 - ratio)
          const val = Math.round(maxVal * ratio)
          return (
            <g key={index}>
              <line x1={paddingLeft} y1={y} x2={chartWidth} y2={y} className="chart-grid-line" />
              <text x={paddingLeft - 10} y={y + 4} textAnchor="end" className="chart-text">
                €{val >= 1000 ? (val / 1000).toFixed(1) + 'k' : val}
              </text>
            </g>
          )
        })}

        {/* X Axis labels & Bars */}
        {seasons.map((season, index) => {
          const val = seasonalData[season] || 0
          const ratio = val / maxVal
          const barHeight = chartHeight * ratio
          
          const sectionWidth = (chartWidth - paddingLeft) / seasons.length
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
                fill={colors[season as keyof typeof colors]}
                rx="6"
                style={{ transition: 'all 0.3s ease' }}
              >
                <title>{`${season}: €${val.toLocaleString()}`}</title>
              </rect>
              {/* Label */}
              <text
                x={x + barWidth / 2}
                y={chartHeight + 18}
                textAnchor="middle"
                className="chart-text"
              >
                {season}
              </text>
              {/* Value on bar */}
              <text
                x={x + barWidth / 2}
                y={y - 6}
                textAnchor="middle"
                fill="var(--text-secondary)"
                fontSize="9px"
                fontWeight="600"
              >
                €{val >= 1000 ? (val/1000).toFixed(0)+'k' : Math.round(val)}
              </text>
            </g>
          )
        })}
      </svg>
    )
  }

  const allMonthsList = summary && summary.by_month ? Object.keys(summary.by_month).sort() : []
  const availableYears = Array.from(new Set(allMonthsList.map(m => m.split('-')[0]))).sort().reverse()

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
            onClick={() => setActiveTab('home')}
            className={`tab-btn ${activeTab === 'home' ? 'active' : ''}`}
          >
            <LayoutDashboard /> Home
          </button>
          <button
            onClick={() => setActiveTab('monthly')}
            className={`tab-btn ${activeTab === 'monthly' ? 'active' : ''}`}
          >
            <Calendar /> Monthly
          </button>
          <button
            onClick={() => setActiveTab('yearly')}
            className={`tab-btn ${activeTab === 'yearly' ? 'active' : ''}`}
          >
            <TrendingUp /> Yearly / Seasonal
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
          <button
            onClick={() => setActiveTab('profile')}
            className={`tab-btn ${activeTab === 'profile' ? 'active' : ''}`}
          >
            <User /> Profile
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
          {activeTab === 'home' && (
            <div>
              {/* Metric Cards Grid */}
              <div className="dashboard-grid">
                <div className="metric-card success">
                  <div className="metric-header">
                    <span>Total Tracked Spend</span>
                    <div className="metric-icon">
                      <Euro size={18} />
                    </div>
                  </div>
                  <div className="metric-value">
                    €{(summary?.total_spent || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </div>
                  <div className="metric-sub">Aggregated budget total</div>
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
                  <div className="card-title" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span>Monthly Spends Analysis</span>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>Range:</span>
                      <select
                        className="filter-select"
                        value={chartYearFilter}
                        onChange={(e) => setChartYearFilter(e.target.value)}
                        style={{ padding: '4px 8px', fontSize: '12px', minWidth: '120px', height: '28px' }}
                      >
                        <option value="last12">Last 12 Months</option>
                        <option value="last24">Last 24 Months</option>
                        {availableYears.map(year => (
                          <option key={year} value={year}>{year}</option>
                        ))}
                        <option value="all">All Months</option>
                      </select>
                    </div>
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
                              <span className="category-amount">€{amt.toLocaleString()} ({pct}%)</span>
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

          {/* TAB: MONTHLY TRACKER */}
          {activeTab === 'monthly' && (
            <div>
              {/* Month Selection Control */}
              <div className="card" style={{ marginBottom: '24px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
                  <div>
                    <h3 style={{ fontSize: '18px', fontWeight: '600', marginBottom: '4px' }}>Monthly Spend Analysis</h3>
                    <p style={{ color: 'var(--text-secondary)', fontSize: '13px' }}>Drill down into detailed monthly category aggregates and utility expenses.</p>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <label style={{ fontSize: '14px', fontWeight: '500', color: 'var(--text-secondary)' }}>Select Month:</label>
                    <select
                      className="filter-select"
                      value={selectedMonth}
                      onChange={(e) => setSelectedMonth(e.target.value)}
                      style={{ minWidth: '150px' }}
                    >
                      {getAvailableMonths().map((m, i) => (
                        <option key={i} value={m}>{m}</option>
                      ))}
                    </select>
                  </div>
                </div>
              </div>

              {selectedMonth ? (
                <>
                  {/* Selected Month Stats Grid */}
                  <div className="dashboard-grid" style={{ marginBottom: '24px' }}>
                    <div className="metric-card success">
                      <div className="metric-header">
                        <span>Month's Total Spend</span>
                        <div className="metric-icon">
                          <Euro size={18} />
                        </div>
                      </div>
                      <div className="metric-value">
                        €{selectedMonthTotal.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </div>
                      <div className="metric-sub">Total spent in {selectedMonth}</div>
                    </div>

                    <div className="metric-card primary">
                      <div className="metric-header">
                        <span>Average Monthly Expense</span>
                        <div className="metric-icon">
                          <TrendingUp size={18} />
                        </div>
                      </div>
                      <div className="metric-value">
                        €{selectedMonthAvg.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </div>
                      <div className="metric-sub">Per-transaction average</div>
                    </div>

                    <div className="metric-card warning">
                      <div className="metric-header">
                        <span>Month's Transactions</span>
                        <div className="metric-icon">
                          <ReceiptText size={18} />
                        </div>
                      </div>
                      <div className="metric-value">
                        {selectedMonthCount}
                      </div>
                      <div className="metric-sub">Total items in selected month</div>
                    </div>
                  </div>

                  {/* Monthly Category & Utility Breakdowns */}
                  <div className="visuals-section" style={{ marginBottom: '24px' }}>
                    {/* Category List */}
                    <div className="card">
                      <div className="card-title">
                        <span>Category Breakdown ({selectedMonth})</span>
                        <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Shares</span>
                      </div>
                      <div className="category-list">
                        {Object.keys(selectedMonthCats).length > 0 ? (
                          Object.keys(selectedMonthCats).map((category, idx) => {
                            const amt = selectedMonthCats[category]
                            const pct = Math.round((amt / (selectedMonthTotal || 1)) * 100)
                            
                            return (
                              <div className="category-row" key={idx}>
                                <div className="category-info">
                                  <span className="category-name">
                                    <span className="category-dot" style={{ backgroundColor: `hsl(${(idx * 65) % 360}, 75%, 60%)` }} />
                                    {category}
                                  </span>
                                  <span className="category-amount">€{amt.toLocaleString()} ({pct}%)</span>
                                </div>
                                <div className="category-bar-bg">
                                  <div
                                    className="category-bar-fill"
                                    style={{
                                      width: `${pct}%`,
                                      background: `linear-gradient(90deg, hsl(${(idx * 65) % 360}, 75%, 50%), var(--success))`
                                    }}
                                  />
                                </div>
                              </div>
                            )
                          })
                        ) : (
                          <div style={{ margin: 'auto', textAlign: 'center', color: 'var(--text-muted)', paddingTop: '60px' }}>
                            No category data for this month.
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Utility Invoices Tracker */}
                    <div className="card">
                      <div className="card-title">
                        <span>Utility & Core Expense Tracker</span>
                        <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Core</span>
                      </div>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', marginTop: '16px' }}>
                        {[
                          { name: 'Rent', key: 'rent', desc: 'Monthly Housing Bill', color: '#6366f1' },
                          { name: 'Electricity', key: 'electricity', desc: 'Power Statement (Enel, etc.)', color: '#fbbf24' },
                          { name: 'Gas', key: 'gas', desc: 'Heating/Gas Invoices', color: '#fb923c' },
                          { name: 'WiFi', key: 'wifi', desc: 'Internet/WiFi Bill (Fastweb, etc.)', color: '#38bdf8' }
                        ].map((util, i) => {
                          const amt = utilityTotals[util.key] || 0
                          return (
                            <div key={i} style={{
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'space-between',
                              padding: '12px 16px',
                              background: 'rgba(255,255,255,0.02)',
                              border: '1px solid var(--border-color)',
                              borderRadius: '8px'
                            }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                                <div style={{
                                  width: '8px',
                                  height: '8px',
                                  borderRadius: '50%',
                                  backgroundColor: util.color
                                }} />
                                <div>
                                  <div style={{ fontWeight: '600', fontSize: '14px' }}>{util.name}</div>
                                  <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{util.desc}</div>
                                </div>
                              </div>
                              <div style={{ fontWeight: '700', fontSize: '16px', color: amt > 0 ? 'var(--text-primary)' : 'var(--text-muted)' }}>
                                €{amt.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                              </div>
                            </div>
                          )
                        })}
                      </div>
                    </div>
                  </div>

                  {/* Monthly Transactions List */}
                  <div className="card">
                    <div className="card-title" style={{ marginBottom: '16px' }}>
                      <span>Ledger Items for {selectedMonth}</span>
                      <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>{selectedMonthCount} items</span>
                    </div>
                    <div className="table-container">
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
                          {selectedMonthExpenses.map((expense) => (
                            <tr key={expense.id}>
                              <td style={{ color: 'var(--text-secondary)' }}>{expense.date}</td>
                              <td style={{ fontWeight: '500' }}>{expense.description}</td>
                              <td>
                                <span className="tag tag-category">
                                  {expense.category}
                                </span>
                              </td>
                              <td style={{ textAlign: 'right' }} className="amount-text negative">
                                €{expense.amount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </>
              ) : (
                <div className="card" style={{ padding: '60px', textAlign: 'center', color: 'var(--text-secondary)' }}>
                  No months available. Please ingest database expenses.
                </div>
              )}
            </div>
          )}

          {/* TAB: YEARLY / SEASONAL ANALYTICS */}
          {activeTab === 'yearly' && (
            <div>
              {/* Seasonal spends bar chart & breakdowns */}
              <div className="visuals-section" style={{ marginBottom: '24px' }}>
                <div className="card">
                  <div className="card-title">
                    <span>Seasonal Spending Distribution</span>
                    <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Breakdown</span>
                  </div>
                  <div className="chart-container">
                    {renderSeasonalSvgChart()}
                  </div>
                </div>

                <div className="card">
                  <div className="card-title">
                    <span>Seasonal Breakdown Grids</span>
                    <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Comparison</span>
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginTop: '16px' }}>
                    {[
                      { name: 'Winter', range: 'Dec - Feb', color: 'var(--winter-color, #38bdf8)' },
                      { name: 'Spring', range: 'Mar - May', color: 'var(--spring-color, #4ade80)' },
                      { name: 'Summer', range: 'Jun - Aug', color: 'var(--summer-color, #fbbf24)' },
                      { name: 'Autumn', range: 'Sep - Nov', color: 'var(--autumn-color, #fb923c)' }
                    ].map((season, idx) => {
                      const total = getSeasonalData()[season.name] || 0
                      const count = expenses.filter(e => getSeasonFromDate(e.date) === season.name).length
                      const domCat = getDominantCategoryForSeason(season.name)
                      
                      return (
                        <div key={idx} style={{
                          padding: '14px',
                          background: 'rgba(255,255,255,0.01)',
                          border: '1px solid var(--border-color)',
                          borderRadius: '10px',
                          borderLeft: `4px solid ${season.color}`
                        }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
                            <div>
                              <div style={{ fontWeight: '700', fontSize: '15px' }}>{season.name}</div>
                              <div style={{ fontSize: '10px', color: 'var(--text-muted)' }}>{season.range}</div>
                            </div>
                            <div style={{ fontWeight: '700', fontSize: '15px', color: total > 0 ? 'var(--text-primary)' : 'var(--text-muted)' }}>
                              €{total.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                            </div>
                          </div>
                          <div style={{ fontSize: '12px', color: 'var(--text-secondary)', display: 'flex', flexDirection: 'column', gap: '2px' }}>
                            <div>Transactions: <strong style={{ color: '#fff' }}>{count}</strong></div>
                            <div>Dominant: <strong style={{ color: '#fff' }}>{domCat}</strong></div>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </div>
              </div>

              {/* Dynamic Analytics Insights */}
              <div className="card">
                <div className="card-title" style={{ marginBottom: '16px' }}>
                  <span>Seasonal Spending Analysis & Insights</span>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', fontSize: '14px', lineHeight: '1.6', color: 'var(--text-secondary)' }}>
                  <p>
                    🌱 <strong>Spring (Mar - May)</strong>: Spends are typically dominated by infrastructure renewals and spring activities.
                    {getSeasonalData()['Spring'] > 0 ? ` You spent €${getSeasonalData()['Spring'].toLocaleString()} this season.` : ' Currently no data tracked for Spring.'}
                  </p>
                  <p>
                    ☀️ <strong>Summer (Jun - Aug)</strong>: Often spikes due to travel, gelato excursions, and vacations.
                    {getSeasonalData()['Summer'] > 0 ? ` You spent €${getSeasonalData()['Summer'].toLocaleString()} this season.` : ' Currently no data tracked for Summer.'}
                  </p>
                  <p>
                    🍂 <strong>Autumn (Sep - Nov)</strong>: Seasonal transitions generally register standard utility operations.
                    {getSeasonalData()['Autumn'] > 0 ? ` You spent €${getSeasonalData()['Autumn'].toLocaleString()} this season.` : ' Currently no data tracked for Autumn.'}
                  </p>
                  <p>
                    ❄️ <strong>Winter (Dec - Feb)</strong>: Usually experiences budget spikes on heating utilities (Electricity/Gas) and holiday shopping.
                    {getSeasonalData()['Winter'] > 0 ? ` You spent €${getSeasonalData()['Winter'].toLocaleString()} this season.` : ' Currently no data tracked for Winter.'}
                  </p>
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
                            €{expense.amount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
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
            <div style={{ maxWidth: ocrResult ? '900px' : '600px', margin: '0 auto' }}>
              {ocrResult ? (
                /* OCR Confirmation Widget */
                <div className="card" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '28px', padding: '32px' }}>
                  {/* Left Column: Image Preview */}
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                    <div className="card-title" style={{ fontSize: '16px', margin: 0 }}>Receipt / Bill Document</div>
                    <div style={{
                      borderRadius: '12px',
                      overflow: 'hidden',
                      border: '1px solid var(--border-color)',
                      background: 'rgba(0,0,0,0.2)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      aspectRatio: '3/4',
                      position: 'relative'
                    }}>
                      <img
                        src={`${API_BASE.replace('/api', '')}${ocrResult.bill_image_url}`}
                        alt="Scanned Bill Document"
                        style={{ width: '100%', height: '100%', objectFit: 'contain' }}
                      />
                    </div>
                  </div>

                  {/* Right Column: Edit/Confirm Form */}
                  <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
                    <div>
                      <div className="card-title" style={{ fontSize: '18px', fontWeight: '700', marginBottom: '8px', color: 'var(--success)' }}>
                        Gemini OCR Extraction Results
                      </div>
                      <p style={{ color: 'var(--text-secondary)', fontSize: '13px', marginBottom: '20px' }}>
                        We identified the following ledger properties from your document. Please verify or correct them before saving.
                      </p>

                      <form onSubmit={handleOcrConfirm} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                        <div className="form-group">
                          <label className="form-label">Transaction Date</label>
                          <input
                            type="date"
                            className="form-input"
                            required
                            value={ocrDate}
                            onChange={(e) => setOcrDate(e.target.value)}
                          />
                        </div>

                        <div className="form-group">
                          <label className="form-label">Merchant / Payee Name</label>
                          <input
                            type="text"
                            className="form-input"
                            required
                            value={ocrDesc}
                            onChange={(e) => setOcrDesc(e.target.value)}
                          />
                        </div>

                        <div className="form-group">
                          <label className="form-label">Category</label>
                          <input
                            type="text"
                            className="form-input"
                            required
                            placeholder="e.g. Electricity, Gas, WiFi"
                            value={ocrCat}
                            onChange={(e) => setOcrCat(e.target.value)}
                          />
                        </div>

                        <div className="form-group">
                          <label className="form-label">Amount (€ EUR equivalent)</label>
                          <input
                            type="number"
                            step="0.01"
                            className="form-input"
                            required
                            value={ocrAmt}
                            onChange={(e) => setOcrAmt(e.target.value)}
                          />
                        </div>

                        <div style={{ display: 'flex', gap: '12px', marginTop: '24px' }}>
                          <button
                            type="button"
                            className="btn btn-secondary"
                            style={{ flex: 1 }}
                            onClick={() => {
                              setOcrResult(null)
                              setUploadFile(null)
                            }}
                          >
                            Discard
                          </button>
                          <button type="submit" className="btn" style={{ flex: 2 }}>
                            Confirm & Save
                          </button>
                        </div>
                      </form>
                    </div>
                  </div>
                </div>
              ) : (
                /* Upload File Form */
                <div className="card">
                  <div className="card-title">Import Expense Ledger or Bills</div>
                  <p style={{ color: 'var(--text-secondary)', fontSize: '14px', marginBottom: '24px' }}>
                    Upload your tracked expenses spreadsheet (CSV, Excel) or upload bill/receipt photos (PNG, JPG, WebP) for automated AI OCR parsing.
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
                        accept=".csv, .xlsx, .xls, .png, .jpg, .jpeg, .webp"
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
                        Supported formats: CSV, XLS, XLSX, PNG, JPG, WEBP
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
                              <Loader2 className="animate-spin" size={16} /> {
                                ['.png', '.jpg', '.jpeg', '.webp'].includes(uploadFile.name.substring(uploadFile.name.lastIndexOf('.')).toLowerCase())
                                  ? "Reading Bill with Gemini OCR..."
                                  : "Parsing Ledger..."
                              }
                            </>
                          ) : (
                            "Import Document"
                          )}
                        </button>
                      </div>
                    )}
                  </form>
                </div>
              )}
            </div>
          )}

          {/* TAB: PROFILE */}
          {activeTab === 'profile' && profile && (
            <div style={{ maxWidth: '600px', margin: '0 auto' }}>
              <div className="card" style={{ padding: '32px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '20px', marginBottom: '28px' }}>
                  <div style={{
                    width: '64px',
                    height: '64px',
                    borderRadius: '50%',
                    background: 'linear-gradient(135deg, var(--primary) 0%, var(--primary-dark) 100%)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: '#fff',
                    fontSize: '24px',
                    fontWeight: 'bold',
                    boxShadow: '0 4px 14px rgba(99, 102, 241, 0.4)'
                  }}>
                    {profile.email.charAt(0).toUpperCase()}
                  </div>
                  <div>
                    <h2 style={{ fontSize: '20px', fontWeight: '600', margin: '0 0 4px 0', color: '#fff' }}>User Profile</h2>
                    <p style={{ color: 'var(--text-secondary)', margin: 0, fontSize: '14px' }}>{profile.email}</p>
                  </div>
                </div>

                <hr style={{ border: 'none', borderTop: '1px solid var(--border-color)', margin: '24px 0' }} />

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px', marginBottom: '28px' }}>
                  <div className="card" style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid var(--border-color)', padding: '16px', borderRadius: '12px' }}>
                    <div style={{ color: 'var(--text-secondary)', fontSize: '12px', fontWeight: '600', textTransform: 'uppercase', marginBottom: '4px' }}>Total Spend</div>
                    <div style={{ fontSize: '24px', fontWeight: 'bold', color: 'var(--primary)' }}>€{profile.total_spent.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</div>
                  </div>
                  
                  <div className="card" style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid var(--border-color)', padding: '16px', borderRadius: '12px' }}>
                    <div style={{ color: 'var(--text-secondary)', fontSize: '12px', fontWeight: '600', textTransform: 'uppercase', marginBottom: '4px' }}>Transactions</div>
                    <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#fff' }}>{profile.transaction_count}</div>
                  </div>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', color: 'var(--text-secondary)', fontSize: '14px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span>Account Status</span>
                    <span style={{ color: 'var(--success)', fontWeight: '600' }}>Active (Verified via IAP)</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span>Member Since</span>
                    <span style={{ color: '#fff' }}>{profile.created_at || 'Recently'}</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span>Environment</span>
                    <span style={{ color: '#fff' }}>{isDemoMode ? 'Sandbox (Demo)' : 'Google Cloud Production'}</span>
                  </div>
                </div>

                {isDemoMode && (
                  <div style={{ marginTop: '28px', padding: '12px', background: 'rgba(234, 179, 8, 0.1)', border: '1px solid var(--warning)', borderRadius: '8px', color: 'var(--warning)', fontSize: '13px', lineHeight: '1.5' }}>
                    <strong>Note:</strong> You are currently in local sandbox demo mode. To see your actual Google-authenticated profile and secure database, run the app in Google Cloud.
                  </div>
                )}

                <div style={{ marginTop: '32px', display: 'flex', justifyContent: 'center' }}>
                  <a
                    href="/_gcp_iap/clear_login_cookie"
                    className="btn"
                    style={{
                      background: 'rgba(239, 68, 68, 0.12)',
                      color: '#f87171',
                      border: '1px solid rgba(239, 68, 68, 0.25)',
                      padding: '10px 24px',
                      borderRadius: '8px',
                      fontWeight: '600',
                      textDecoration: 'none',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                      transition: 'all 0.2s ease',
                      cursor: 'pointer'
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.background = 'rgba(239, 68, 68, 0.2)';
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.background = 'rgba(239, 68, 68, 0.12)';
                    }}
                  >
                    <LogOut size={16} /> Log Out
                  </a>
                </div>
              </div>
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
                <label className="form-label">Amount (€ EUR)</label>
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
