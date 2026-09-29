import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

interface ThemeContextValue {
  theme: string;
  setTheme: (theme: string) => void;
}

const ThemeContext = createContext<ThemeContextValue | undefined>(undefined);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<string>(() => {
    return localStorage.getItem("memora_theme") || "default";
  });

  const setTheme = (newTheme: string) => {
    setThemeState(newTheme);
    localStorage.setItem("memora_theme", newTheme);
  };

  useEffect(() => {
    const root = document.documentElement;

    const themeClasses = Array.from(root.classList).filter(c => c.startsWith("theme-"));
    if (themeClasses.length > 0) root.classList.remove(...themeClasses);
    
    if (theme !== "default") {
      root.classList.add(`theme-${theme}`);
    }

    // We do NOT remove the theme on unmount because ThemeProvider sits at the root
    // and we want the theme to persist.
  }, [theme]);

  return (
    <ThemeContext.Provider value={{ theme, setTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) {
    throw new Error("useTheme must be used within a ThemeProvider");
  }
  return ctx;
}
