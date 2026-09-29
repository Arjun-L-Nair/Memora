import { FormEvent, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { AuthShell } from "@/components/ui/AuthShell";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { useAuth } from "@/contexts/AuthContext";
import { loginStudent } from "@/services/authService";

/**
 * Student login: kept extremely simple per spec — Student ID + 4-digit
 * PIN only, large touch-friendly controls, minimal text, no clutter.
 * Visually uses the glassmorphism + spatial-background language shared
 * by every login/pre-session screen (see globals.css); the calmer,
 * flatter claymorphism styling begins once the student is actually
 * inside the app.
 */
export function StudentLogin() {
  const navigate = useNavigate();
  const location = useLocation();
  const { setRole } = useAuth();
  const sessionExpired = Boolean(
    (location.state as { sessionExpired?: boolean } | null)?.sessionExpired
  );

  const [studentCode, setStudentCode] = useState("");
  const [pin, setPin] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await loginStudent(studentCode, pin);
      setRole("student");
      navigate("/student", { replace: true });
    } catch {
      setError("That Student ID or PIN isn't right. Try again.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <AuthShell
      audience="student"
      title="Welcome back"
      description="Enter your Student ID and PIN to start learning."
      footer={
        <>
          Are you a teacher? <Link to="/login/teacher" className="font-medium text-primary-700 underline decoration-primary-300 underline-offset-4 hover:decoration-primary-600">Teacher login</Link>{" · "}<Link to="/role-select" className="font-medium text-primary-700 underline decoration-primary-300 underline-offset-4 hover:decoration-primary-600">Choose a different role</Link>
        </>
      }
    >
      {sessionExpired && (
        <p role="status" className="mb-5 rounded-xl border border-secondary-200 bg-secondary-50 p-3 text-sm text-secondary-700">
          Your session ended. Please sign in again.
        </p>
      )}
      <form className="flex flex-col gap-5" onSubmit={handleSubmit}>
        <Input
          label="Student ID"
          autoComplete="username"
          required
          value={studentCode}
          onChange={(e) => setStudentCode(e.target.value)}
          className="h-14 bg-white/80 text-lg"
        />
        <Input
          label="4-Digit PIN"
          type="password"
          inputMode="numeric"
          pattern="\d{4}"
          maxLength={4}
          autoComplete="off"
          required
          value={pin}
          onChange={(e) => setPin(e.target.value.replace(/\D/g, "").slice(0, 4))}
          className="h-14 bg-white/80 text-lg tracking-widest"
        />
        {error && (
          <p role="alert" className="text-sm text-error-600">
            {error}
          </p>
        )}
        <Button type="submit" size="lg" disabled={isSubmitting}>
          {isSubmitting ? "Signing in..." : "Start Learning"}
        </Button>
      </form>
    </AuthShell>
  );
}
