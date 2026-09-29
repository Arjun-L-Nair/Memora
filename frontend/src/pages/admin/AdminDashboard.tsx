import { useEffect, useState } from "react";
import { GraduationCap, Users, ListChecks, ClipboardList, Sparkles } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/Card";
import { LoadingSpinner } from "@/components/ui/LoadingSpinner";
import {
  getSystemStatistics,
  seedDemoData,
  type SystemStatistics,
} from "@/services/adminService";

export function AdminDashboard() {
  const [stats, setStats] = useState<SystemStatistics | null>(null);
  const [error, setError] = useState(false);
  const [seeding, setSeeding] = useState(false);
  const [seedMessage, setSeedMessage] = useState<string | null>(null);
  const [seedError, setSeedError] = useState<string | null>(null);

  function loadStats() {
    getSystemStatistics()
      .then(setStats)
      .catch(() => setError(true));
  }

  useEffect(() => {
    loadStats();
  }, []);

  async function handleSeedDemoData() {
    setSeeding(true);
    setSeedMessage(null);
    setSeedError(null);
    try {
      const result = await seedDemoData();
      setSeedMessage(
        result.already_seeded
          ? "Demo data already exists — nothing was changed."
          : "Demo dataset created: 6 students, learning plans, sessions, quiz attempts, reflections, and engagement predictions."
      );
      loadStats(); // refresh the stat cards to reflect newly-seeded data
    } catch {
      setSeedError(
        "Couldn't seed demo data. Make sure the backend server is reachable and try again."
      );
    } finally {
      setSeeding(false);
    }
  }

  const cards = stats
    ? [
        {
          title: "Teachers",
          description: `${stats.active_teachers} active / ${stats.total_teachers} total`,
          icon: GraduationCap,
        },
        {
          title: "Students",
          description: `${stats.active_students} active / ${stats.total_students} total`,
          icon: Users,
        },
        {
          title: "Learning Sessions",
          description: `${stats.total_learning_sessions} total`,
          icon: ClipboardList,
        },
        {
          title: "Quiz Attempts",
          description: `${stats.total_quiz_attempts} total`,
          icon: ListChecks,
        },
      ]
    : [];

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold text-foreground">Admin Dashboard</h1>
        <p className="mt-1 text-muted-foreground">Basic platform oversight.</p>
      </div>

      {!stats && !error && (
        <div className="flex justify-center py-12">
          <LoadingSpinner />
        </div>
      )}

      {error && (
        <p className="text-sm text-error-600">
          Couldn't load platform statistics. Please try again.
        </p>
      )}

      {stats && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {cards.map(({ title, description, icon: Icon }) => (
            <Card variant="glass" key={title}>
              <CardHeader>
                <div className="mb-2 flex h-10 w-10 items-center justify-center rounded-md bg-primary-50">
                  <Icon className="h-5 w-5 text-primary-600" />
                </div>
                <CardTitle>{title}</CardTitle>
                <CardDescription>{description}</CardDescription>
              </CardHeader>
            </Card>
          ))}
        </div>
      )}

      {/* Demo dataset seeding — makes the previously-hidden backend
          seed script a visible, one-click action, useful for setting
          up a populated demo instead of an empty database. */}
      <Card variant="glass">
        <CardHeader>
          <div className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-primary-500" aria-hidden="true" />
            <CardTitle className="text-base">Demo Dataset</CardTitle>
          </div>
          <CardDescription>
            Populate the platform with 6 sample students, learning plans, varied content,
            completed sessions, quiz attempts, reflections, and engagement predictions — useful
            for demonstrations or testing analytics with realistic data.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <Button
            variant="outline"
            disabled={seeding}
            onClick={handleSeedDemoData}
            className="self-start"
          >
            {seeding ? "Seeding... this can take up to a minute" : "Seed Demo Dataset"}
          </Button>
          {seedMessage && <p className="text-sm text-success-600">{seedMessage}</p>}
          {seedError && <p className="text-sm text-error-600">{seedError}</p>}
          <p className="text-xs text-muted-foreground">
            Safe to click even if demo data already exists — this action never creates
            duplicates.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
