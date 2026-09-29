import { FormEvent, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { AuthShell } from "@/components/ui/AuthShell";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { useAuth } from "@/contexts/AuthContext";
import { loginAdmin } from "@/services/authService";

export function AdminLogin() {
  const navigate = useNavigate();
  const location = useLocation();
  const { setRole } = useAuth();
  const sessionExpired = Boolean((location.state as { sessionExpired?: boolean } | null)?.sessionExpired);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await loginAdmin(email, password);
      setRole("admin");
      navigate("/admin", { replace: true });
    } catch {
      setError("Incorrect email or password. Please try again.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <AuthShell
      audience="admin"
      title="Admin sign in"
      description="Platform oversight access."
      footer={
        <>
          <Link to="/role-select" className="font-medium text-primary-700 underline decoration-primary-300 underline-offset-4 hover:decoration-primary-600">Choose a different role</Link>
        </>
      }
    >
      {sessionExpired && (
        <p role="status" className="mb-5 rounded-xl border border-secondary-200 bg-secondary-50 p-3 text-sm text-secondary-700">
          Your session ended. Please sign in again.
        </p>
      )}
      <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
        <Input
          label="Email"
          type="email"
          autoComplete="username"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <Input
          label="Password"
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        {error && (
          <p role="alert" className="text-sm text-error-600">
            {error}
          </p>
        )}
        <Button type="submit" disabled={isSubmitting} className="mt-2">
          {isSubmitting ? "Signing in..." : "Sign In"}
        </Button>
      </form>
    </AuthShell>
  );
}
