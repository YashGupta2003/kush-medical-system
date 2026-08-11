import "@testing-library/jest-dom";

// Mock localStorage (jsdom implements it but this ensures clean state)
beforeEach(() => {
  localStorage.clear();
});

// Mock window.matchMedia — not implemented in jsdom
Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: (query) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => {},
  }),
});

// Mock IntersectionObserver — used by framer-motion and recharts
global.IntersectionObserver = class {
  constructor() {}
  observe() {}
  unobserve() {}
  disconnect() {}
};
