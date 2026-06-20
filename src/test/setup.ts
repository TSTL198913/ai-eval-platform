﻿﻿﻿﻿import { afterEach } from 'vitest'
import { cleanup } from '@testing-library/react'
import '@testing-library/jest-dom/vitest'

afterEach(() => {
  cleanup()
})

global.fetch = vi.fn(() =>
  Promise.resolve({
    json: () => Promise.resolve({}),
    ok: true,
  })
) as typeof global.fetch

const mockMediaQueryList = {
  matches: false,
  media: '',
  onchange: null,
  addListener: vi.fn(),
  removeListener: vi.fn(),
  addEventListener: vi.fn(),
  removeEventListener: vi.fn(),
  dispatchEvent: vi.fn(),
}

Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation(() => ({
    ...mockMediaQueryList,
    media: '',
    matches: false,
  })),
})

class ResizeObserver {
  observe = vi.fn()
  unobserve = vi.fn()
  disconnect = vi.fn()
}

global.ResizeObserver = ResizeObserver
