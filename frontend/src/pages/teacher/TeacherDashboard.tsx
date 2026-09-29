import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Users, ClipboardList, BarChart3, UserPlus, Plus, AlertTriangle, Brain, Puzzle } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/Card";
import { LoadingSpinner } from "@/components/ui/LoadingSpinner";
import { listLearningPlans } from "@/services/learningPlanService";
import { listStudents, type StudentRecord } from "@/services/studentService";
import { getAtRiskStudents, type AtRiskStudent } from "@/services/earlyWarningService";
import { getStudentSkillProgress, type TeacherSkillProgressEntry } from "@/services/skillService";

const RISK_LEVEL_STYLES: Record<string, string> = {
  "At Risk": "bg-error-50 text-error-600 border-error-100",
  "Needs Attention": "bg-warning-50 text-warning-600 border-warning-100",
};

interface StudentSkillSummary {
  student: StudentRecord;
  easyPassed: number;
  easyTotal: number;
  mediumPassed: number;
  mediumTotal: number;
  hardPassed: number;
  hardTotal: number;
}

function summarizeSkillProgress(student: StudentRecord, entries: TeacherSkillProgressEntry[]): StudentSkillSummary {
  const byTier = (tier: string) => entries.filter((e) => e.tier === tier);
  const passedIn = (tier: string) => byTier(tier).filter((e) => e.passed).length;
  return {
    student,
    easyPassed: passedIn("Easy"),
    easyTotal: byTier("Easy").length,
    mediumPassed: passedIn("Medium"),
    mediumTotal: byTier("Medium").length,
    hardPassed: passedIn("Hard"),
    hardTotal: byTier("Hard").length,
  };
}

export function TeacherDashboard() {
  const navigate = useNavigate();
  const [studentCount, setStudentCount] = useState<number | null>(null);
  const [planCount, setPlanCount] = useState<number | null>(null);
  const [atRisk, setAtRisk] = useState<AtRiskStudent[] | null>(null);
  const [atRiskError, setAtRiskError] = useState(false);
  const [skillSummaries, setSkillSummaries] = useState<StudentSkillSummary[] | null>(null);
  const [skillSummaryError, setSkillSummaryError] = useState(false);

  useEffect(() => {
    listStudents()
      .then((data) => setStudentCount(data.length))
      .catch(() => setStudentCount(0));
    listLearningPlans()
      .then((data) => setPlanCount(data.length))
      .catch(() => setPlanCount(0));
    getAtRiskStudents()
      .then((data) => setAtRisk(data))
      .catch(() => setAtRiskError(true));

    listStudents()
      .then(async (students) => {
        const summaries = await Promise.all(
          students.map(async (student) => {
            const entries = await getStudentSkillProgress(student.id);
            return summarizeSkillProgress(student, entries);
          })
        );
        setSkillSummaries(summaries);
      })
      .catch(() => setSkillSummaryError(true));
  }, []);

  return (
    <div className="flex flex-col gap-8">
      <div>
        <h1 className="text-2xl font-semibold text-foreground">Dashboard</h1>
        <p className="mt-1 text-muted-foreground">
          Overview of your students and learning activity.
        </p>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Card variant="glass">
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardDescription>Students</CardDescription>
              <div className="flex h-8 w-8 items-center justify-center rounded-md bg-primary-50">
                <Users className="h-4 w-4 text-primary-600" />
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-bold text-foreground">
              {studentCount ?? "—"}
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              {studentCount === 1 ? "student enrolled" : "students enrolled"}
            </p>
          </CardContent>
        </Card>

        <Card variant="glass">
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardDescription>Learning Plans</CardDescription>
              <div className="flex h-8 w-8 items-center justify-center rounded-md bg-primary-50">
                <ClipboardList className="h-4 w-4 text-primary-600" />
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-bold text-foreground">
              {planCount ?? "—"}
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              {planCount === 1 ? "plan created" : "plans created"}
            </p>
          </CardContent>
        </Card>

        <Card variant="glass">
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardDescription>Analytics</CardDescription>
              <div className="flex h-8 w-8 items-center justify-center rounded-md bg-primary-50">
                <BarChart3 className="h-4 w-4 text-primary-600" />
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-bold text-foreground">→</p>
            <p className="mt-1 text-xs text-muted-foreground">engagement & suggestions</p>
          </CardContent>
        </Card>
      </div>

      {/* ── AI Early-Warning: at-risk students ───────────────────────────────
          Surfaces app.ml.early_warning's transparent, rule-weighted risk
          score — every flagged student comes with plain-language
          contributing factors (never a bare number), computed from real
          engagement-trend/session-frequency/accuracy-trend/recency signals. */}
      <Card variant="glass">
        <CardHeader>
          <div className="flex items-center gap-2">
            <Brain className="h-4 w-4 text-primary-500" aria-hidden="true" />
            <CardTitle className="text-base">AI Early Warning</CardTitle>
          </div>
          <CardDescription>
            Students the model flags as needing attention, based on engagement, accuracy, and
            session-frequency trends — with a plain-language reason for every flag.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {atRiskError ? (
            <p className="text-sm text-muted-foreground">Couldn't load early-warning data right now.</p>
          ) : atRisk === null ? (
            <div className="py-4">
              <LoadingSpinner />
            </div>
          ) : atRisk.length === 0 ? (
            <p className="flex items-center gap-2 text-sm text-muted-foreground">
              No students are currently flagged — everyone's trending steady. 🎉
            </p>
          ) : (
            <ul className="flex flex-col gap-3">
              {atRisk.map((s) => (
                <li
                  key={s.student_id}
                  className="rounded-xl border border-white/40 bg-white/50 p-4"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <button
                      onClick={() => navigate("/teacher/students")}
                      className="font-medium text-foreground underline-offset-2 hover:underline"
                    >
                      {s.student_name}
                    </button>
                    <span
                      className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium ${
                        RISK_LEVEL_STYLES[s.risk_level] ?? "bg-muted text-muted-foreground border-border"
                      }`}
                    >
                      <AlertTriangle className="h-3 w-3" />
                      {s.risk_level} · {Math.round(s.risk_score)}/100
                    </span>
                  </div>
                  <ul className="mt-2 list-disc pl-5 text-sm text-muted-foreground">
                    {s.contributing_factors.map((factor, i) => (
                      <li key={i}>{factor}</li>
                    ))}
                  </ul>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      {/* ── Skills Library progress ──────────────────────────────────────────
          Reflects services/skill_service.py's tier-gated pass status for
          every student — this teacher view has no "locked" concept (it
          shows full status regardless of what the student has personally
          unlocked yet), just how far each student has actually progressed. */}
      <Card variant="glass">
        <CardHeader>
          <div className="flex items-center gap-2">
            <Puzzle className="h-4 w-4 text-primary-500" aria-hidden="true" />
            <CardTitle className="text-base">Skills Library Progress</CardTitle>
          </div>
          <CardDescription>
            How far each student has progressed through the Easy / Medium / Hard skill tiers.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {skillSummaryError ? (
            <p className="text-sm text-muted-foreground">Couldn't load skill progress right now.</p>
          ) : skillSummaries === null ? (
            <div className="py-4">
              <LoadingSpinner />
            </div>
          ) : skillSummaries.length === 0 ? (
            <p className="text-sm text-muted-foreground">No students yet.</p>
          ) : (
            <ul className="flex flex-col gap-2">
              {skillSummaries.map((s) => (
                <li
                  key={s.student.id}
                  className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-white/40 bg-white/50 p-3"
                >
                  <span className="font-medium text-foreground">{s.student.full_name}</span>
                  <div className="flex gap-3 text-xs">
                    <span className="rounded-full border border-success-100 bg-success-50 px-2.5 py-0.5 text-success-700">
                      Easy {s.easyPassed}/{s.easyTotal}
                    </span>
                    <span className="rounded-full border border-warning-100 bg-warning-50 px-2.5 py-0.5 text-warning-700">
                      Medium {s.mediumPassed}/{s.mediumTotal}
                    </span>
                    <span className="rounded-full border border-secondary-100 bg-secondary-50 px-2.5 py-0.5 text-secondary-700">
                      Hard {s.hardPassed}/{s.hardTotal}
                    </span>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      {/* Quick actions */}
      <div>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          Quick Actions
        </h2>
        <div className="flex flex-wrap gap-3">
          <Button
            variant="outline"
            onClick={() => navigate("/teacher/students")}
          >
            <UserPlus className="h-4 w-4" />
            Add Student
          </Button>
          <Button
            variant="outline"
            onClick={() => navigate("/teacher/learning-plans")}
          >
            <Plus className="h-4 w-4" />
            New Learning Plan
          </Button>
          <Button
            variant="outline"
            onClick={() => navigate("/teacher/analytics")}
          >
            <BarChart3 className="h-4 w-4" />
            View Analytics
          </Button>
        </div>
      </div>
    </div>
  );
}
