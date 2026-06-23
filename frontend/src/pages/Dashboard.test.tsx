﻿import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import Dashboard from './Dashboard'
import { dashboardApi } from '@/services/api'

vi.mock('@/services/api', () => ({
  dashboardApi: {
    getStats: vi.fn(),
  },
  evaluationApi: {
    evaluate: vi.fn(),
    getResult: vi.fn(),
    listEvaluators: vi.fn(),
  },
}))

const mockMatchMedia = vi.fn().mockImplementation((query) => ({
  matches: false,
  media: query,
  onchange: null,
  addListener: vi.fn(),
  removeListener: vi.fn(),
  addEventListener: vi.fn(),
  removeEventListener: vi.fn(),
  dispatchEvent: vi.fn(),
}))

Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: mockMatchMedia,
})

const originalGetComputedStyle = window.getComputedStyle
Object.defineProperty(window, 'getComputedStyle', {
  writable: true,
  value: (elt, pseudoElt) => {
    if (pseudoElt) {
      return { width: '0px', height: '0px' }
    }
    return originalGetComputedStyle(elt, pseudoElt)
  },
})

class ResizeObserver {
  observe = vi.fn()
  unobserve = vi.fn()
  disconnect = vi.fn()
}

global.ResizeObserver = ResizeObserver

const mockStats = {
  total_records: 1500,
  evaluator_types: 15,
  recent_records: [
    { id: 1, case_id: 'test_001', adapter_name: 'general', model_name: 'gpt-4', status: 'passed', score: 0.95, latency_ms: 245, created_at: '2024-01-01' },
    { id: 2, case_id: 'test_002', adapter_name: 'code', model_name: 'claude-3', status: 'failed', score: 0.65, latency_ms: 310, created_at: '2024-01-01' },
  ],
  status_distribution: { passed: 1470, failed: 30 },
}

describe('Dashboard Page', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockMatchMedia.mockImplementation((query) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }))
  })

  it('should render loading state initially', async () => {
    ;(dashboardApi.getStats as vi.Mock).mockResolvedValue(mockStats)

    const { container } = render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>
    )

    expect(container.querySelector('.ant-spin')).toBeInTheDocument()
  })

  it('should render dashboard stats successfully', async () => {
    ;(dashboardApi.getStats as vi.Mock).mockResolvedValue(mockStats)

    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(screen.getByText('1,500')).toBeInTheDocument()
    })

    expect(screen.getAllByText('15').length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('1,470')).toBeInTheDocument()
    expect(screen.getByText('98.5%')).toBeInTheDocument()
  })

  it('should render recent records table', async () => {
    ;(dashboardApi.getStats as vi.Mock).mockResolvedValue(mockStats)

    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(screen.getByText('test_001')).toBeInTheDocument()
    })

    expect(screen.getByText('general')).toBeInTheDocument()
    expect(screen.getByText('gpt-4')).toBeInTheDocument()
    expect(screen.getByText('test_002')).toBeInTheDocument()
    expect(screen.getByText('code')).toBeInTheDocument()
    expect(screen.getByText('claude-3')).toBeInTheDocument()
  })

  it('should handle API error gracefully', async () => {
    ;(dashboardApi.getStats as vi.Mock).mockRejectedValue(new Error('Network error'))
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(screen.getByText('数据加载失败')).toBeInTheDocument()
    })

    expect(consoleSpy).toHaveBeenCalled()
    consoleSpy.mockRestore()
  })

  it('should render stat cards', async () => {
    ;(dashboardApi.getStats as vi.Mock).mockResolvedValue(mockStats)

    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(screen.getByText('总评测次数')).toBeInTheDocument()
      expect(screen.getByText('评估器类型')).toBeInTheDocument()
      expect(screen.getByText('通过记录')).toBeInTheDocument()
      expect(screen.getByText('平均延迟')).toBeInTheDocument()
      expect(screen.getByText('成功率')).toBeInTheDocument()
      expect(screen.getByText('月度成本')).toBeInTheDocument()
    })
  })
})
