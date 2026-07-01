﻿import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import Login from './Login'
import { authApi } from '@/services/api'

vi.mock('@/services/api', () => ({
  authApi: {
    login: vi.fn(),
  },
}))

vi.mock('@/stores/authStore', () => ({
  default: vi.fn(() => ({
    login: vi.fn(),
  })),
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

class ResizeObserver {
  observe = vi.fn()
  unobserve = vi.fn()
  disconnect = vi.fn()
}

global.ResizeObserver = ResizeObserver

describe('Login Page', () => {
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

  it('should render login form', () => {
    render(
      <MemoryRouter>
        <Login />
      </MemoryRouter>
    )

    expect(screen.getByText('AI 评测平台')).toBeInTheDocument()
    expect(screen.getByLabelText('用户名')).toBeInTheDocument()
    expect(screen.getByLabelText('密码')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '登录' })).toBeInTheDocument()
  })

  it('should show error when form is submitted empty', async () => {
    const user = userEvent.setup()

    render(
      <MemoryRouter>
        <Login />
      </MemoryRouter>
    )

    await user.click(screen.getByRole('button', { name: '登录' }))

    await waitFor(() => {
      expect(screen.getByText('请输入用户名')).toBeInTheDocument()
    })
  })

  it('should show error when login fails', async () => {
    const user = userEvent.setup()
    ;(authApi.login as vi.Mock).mockRejectedValue(new Error('Login failed'))

    render(
      <MemoryRouter>
        <Login />
      </MemoryRouter>
    )

    await user.type(screen.getByLabelText('用户名'), 'admin')
    await user.type(screen.getByLabelText('密码'), 'wrongpassword')
    await user.click(screen.getByRole('button', { name: '登录' }))

    await waitFor(() => {
      expect(screen.getByText('登录失败，请检查用户名和密码')).toBeInTheDocument()
    })
  })

  it('should show loading state during login', async () => {
    const user = userEvent.setup()
    ;(authApi.login as vi.Mock).mockImplementation(() => new Promise(() => {}))

    render(
      <MemoryRouter>
        <Login />
      </MemoryRouter>
    )

    await user.type(screen.getByLabelText('用户名'), 'admin')
    await user.type(screen.getByLabelText('密码'), 'password')
    await user.click(screen.getByRole('button', { name: '登录' }))

    await waitFor(() => {
      expect(screen.getByRole('img', { hidden: true })).toBeInTheDocument()
    })
  })

  it('should render remember me checkbox', () => {
    render(
      <MemoryRouter>
        <Login />
      </MemoryRouter>
    )

    expect(screen.getByText('记住我')).toBeInTheDocument()
  })

  it('should render forgot password link', () => {
    render(
      <MemoryRouter>
        <Login />
      </MemoryRouter>
    )

    expect(screen.getByText('忘记密码?')).toBeInTheDocument()
  })

  it('should render test credentials hint', () => {
    render(
      <MemoryRouter>
        <Login />
      </MemoryRouter>
    )

    expect(screen.getByText('测试账号')).toBeInTheDocument()
    expect(screen.getByText('admin')).toBeInTheDocument()
    expect(screen.getByText('admin123')).toBeInTheDocument()
  })
})
