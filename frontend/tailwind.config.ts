import type { Config } from "tailwindcss";

// Memora Design System
// Calm, professional, low-sensory-overload color palette and 8-point spacing scale.
export default {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Core neutrals
        background: "#F4F7F7",
        surface: "#FFFFFF",
        border: "#DCE5E6",
        foreground: "#1B2B34",
        muted: {
          DEFAULT: "#EAF0F0",
          foreground: "#566A72",
        },
        // Brand
        primary: {
          50: "#EAF6F6",
          100: "#CFEBEC",
          200: "#A2D8DA",
          300: "#6FBFC4",
          400: "#3FA3AA",
          500: "#238A93",
          600: "#0F7079",
          700: "#0B5A62",
          DEFAULT: "#0F7079",
          foreground: "#FFFFFF",
        },
        secondary: {
          50: "#F3F1FC",
          100: "#E6E2F8",
          200: "#CDC5F0",
          300: "#ADA1E5",
          400: "#8D7DD8",
          500: "#7461C9",
          600: "#5F4CB0",
          700: "#4C3C90",
          DEFAULT: "#5F4CB0",
          foreground: "#FFFFFF",
        },
        success: {
          50: "#F0FDF4",
          100: "#DCFCE7",
          200: "#BBF7D0",
          300: "#86EFAC",
          400: "#4ADE80",
          500: "#22C55E",
          600: "#16A34A",
          700: "#15803D",
          800: "#166534",
          900: "#14532D",
          DEFAULT: "#16A34A",
          foreground: "#FFFFFF",
        },
        warning: {
          50: "#FFFBEB",
          100: "#FEF3C7",
          200: "#FDE68A",
          300: "#FCD34D",
          400: "#FBBF24",
          500: "#F59E0B",
          600: "#D97706",
          700: "#B45309",
          800: "#92400E",
          900: "#78350F",
          DEFAULT: "#D97706",
          foreground: "#FFFFFF",
        },
        error: {
          50: "#FEF2F2",
          100: "#FEE2E2",
          200: "#FECACA",
          300: "#FCA5A5",
          400: "#F87171",
          500: "#EF4444",
          600: "#DC2626",
          700: "#B91C1C",
          800: "#991B1B",
          900: "#7F1D1D",
          DEFAULT: "#DC2626",
          foreground: "#FFFFFF",
        },
      },
      spacing: {
        // 8-point spacing system
        "1": "4px",
        "2": "8px",
        "3": "12px",
        "4": "16px",
        "5": "20px",
        "6": "24px",
        "8": "32px",
        "10": "40px",
        "12": "48px",
        "16": "64px",
        "20": "80px",
      },
      borderRadius: {
        sm: "8px",
        DEFAULT: "12px",
        md: "12px",
        lg: "16px",
        xl: "20px",
        "2xl": "24px",
      },
      fontFamily: {
        sans: ["Lexend", "Inter", "-apple-system", "BlinkMacSystemFont", "Segoe UI", "sans-serif"],
        display: ["Fraunces", "Georgia", "serif"],
      },
      boxShadow: {
        soft: "0 1px 2px rgba(20, 50, 58, 0.05), 0 4px 14px rgba(20, 50, 58, 0.05)",
        softMd: "0 2px 4px rgba(20, 50, 58, 0.05), 0 12px 28px rgba(20, 50, 58, 0.08)",
        // Student surfaces: soft lifted "pebble" depth, one gentle shadow, no harsh edges.
        clay: "0 1px 0 rgba(255,255,255,0.9) inset, 0 2px 4px rgba(20, 50, 58, 0.05), 0 10px 24px rgba(20, 50, 58, 0.07)",
        clayMd: "0 1px 0 rgba(255,255,255,0.9) inset, 0 4px 8px rgba(20, 50, 58, 0.06), 0 16px 36px rgba(20, 50, 58, 0.10)",
        clayInset: "inset 0 0 0 1.5px rgba(15, 112, 121, 0.22)",
        clayPressed: "inset 0 2px 4px rgba(20, 50, 58, 0.12)",
        // Teacher/admin/login: airy frosted panels.
        glass: "0 1px 0 rgba(255,255,255,0.8) inset, 0 12px 40px rgba(20, 50, 58, 0.10)",
        glassLg: "0 1px 0 rgba(255,255,255,0.8) inset, 0 24px 60px rgba(20, 50, 58, 0.16)",
      },
      keyframes: {
        "fade-in": {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        "gentle-pulse": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.6" },
        },
      },
      animation: {
        "fade-in": "fade-in 0.2s ease-out",
        "gentle-pulse": "gentle-pulse 2s ease-in-out infinite",
      },
    },
  },
  plugins: [],
} satisfies Config;
