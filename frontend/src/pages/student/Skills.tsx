/**
 * pages/student/Skills.tsx
 *
 * Predefined skills library — practice cards grouped by tier (Easy /
 * Medium / Hard), tier-gated: Medium unlocks once every Easy skill is
 * passed, Hard once every Medium skill is passed (enforced server-side
 * by services/skill_service.py — this page only reflects that state,
 * never decides it).
 *
 * Deliberately a single component (not split across files/components
 * with separate state) — the practice flow's state (current exercise
 * index, answer, feedback) all lives in one place to avoid any risk of
 * the kind of cross-component scope bug this project hit once before
 * with a split Settings page.
 */
import { useEffect, useState } from "react";
import { Lock, CheckCircle2, Sparkles, Puzzle, Calculator, Shapes, Brain, Clock } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { LoadingSpinner } from "@/components/ui/LoadingSpinner";
import {
  getSkillExercises,
  listSkills,
  submitSkillAttempt,
  type SkillExercise,
  type SkillSummary,
} from "@/services/skillService";

const TIER_LABELS: Record<string, string> = { Easy: "Easy", Medium: "Medium", Hard: "Hard" };
const TIER_COLORS: Record<string, string> = {
  Easy: "border-success-200 bg-success-50",
  Medium: "border-warning-200 bg-warning-50",
  Hard: "border-secondary-200 bg-secondary-50",
};

const CATEGORY_ICONS: Record<string, typeof Puzzle> = {
  pattern: Sparkles,
  math: Calculator,
  shapes: Shapes,
  logic: Brain,
  time: Clock,
};

function CategoryIcon({ category }: { category: string }) {
  const Icon = CATEGORY_ICONS[category] ?? Puzzle;
  return <Icon className="h-5 w-5" aria-hidden="true" />;
}

// ─── Skill card ─────────────────────────────────────────────────────────────
function SkillCard({ skill, onPractice }: { skill: SkillSummary; onPractice: () => void }) {
  return (
    <button
      onClick={skill.unlocked ? onPractice : undefined}
      disabled={!skill.unlocked}
      className={`clay-card flex flex-col items-start gap-2 p-4 text-left transition-all ${
        skill.unlocked ? "hover:-translate-y-0.5 cursor-pointer" : "opacity-60 cursor-not-allowed"
      }`}
    >
      <div className="flex w-full items-center justify-between">
        <span className="flex h-9 w-9 items-center justify-center rounded-full bg-primary-50 text-primary-600">
          <CategoryIcon category={skill.category} />
        </span>
        {skill.passed ? (
          <CheckCircle2 className="h-5 w-5 text-success-500" aria-label="Passed" />
        ) : !skill.unlocked ? (
          <Lock className="h-5 w-5 text-muted-foreground" aria-label="Locked" />
        ) : null}
      </div>
      <p className="font-semibold text-foreground">{skill.name}</p>
      <p className="text-sm text-muted-foreground">{skill.description}</p>
    </button>
  );
}

// ─── Practice flow (one exercise at a time) ────────────────────────────────
function SkillPractice({ skillId, skillName, onExit }: { skillId: number; skillName: string; onExit: () => void }) {
  const [exercises, setExercises] = useState<SkillExercise[] | null>(null);
  const [index, setIndex] = useState(0);
  const [selected, setSelected] = useState<number | null>(null);
  const [feedback, setFeedback] = useState<{ correct: boolean; correctIndex: number; skillPassed: boolean } | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(false);

  useEffect(() => {
    getSkillExercises(skillId)
      .then((data) => setExercises(data.exercises))
      .catch(() => setError(true));
  }, [skillId]);

  async function handleSubmit() {
    if (!exercises || selected === null) return;
    setSubmitting(true);
    try {
      const result = await submitSkillAttempt(skillId, exercises[index].id, selected);
      setFeedback({ correct: result.is_correct, correctIndex: result.correct_option_index, skillPassed: result.skill_passed });
    } catch {
      setError(true);
    } finally {
      setSubmitting(false);
    }
  }

  function handleNext() {
    setSelected(null);
    setFeedback(null);
    setIndex((i) => i + 1);
  }

  if (error) {
    return (
      <Card variant="clay">
        <CardContent className="py-8 text-center text-sm text-muted-foreground">
          Couldn't load this skill right now.
          <div className="mt-4">
            <Button variant="outline" onClick={onExit}>Back to Skills</Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (exercises === null) {
    return (
      <div className="flex justify-center py-12">
        <LoadingSpinner />
      </div>
    );
  }

  const isLastExercise = index >= exercises.length - 1;
  const allDone = index >= exercises.length;

  if (allDone) {
    return (
      <div className="flex flex-col items-center gap-4 rounded-2xl bg-gradient-to-br from-success-50 to-primary-50 px-6 py-12 text-center">
        <span className="flex h-16 w-16 items-center justify-center rounded-full bg-success-500 text-white shadow-softMd">
          <CheckCircle2 className="h-8 w-8" />
        </span>
        <div>
          <h2 className="text-xl font-bold text-foreground">Great practice!</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            You've gone through every question in {skillName}. Keep practicing anytime to pass it.
          </p>
        </div>
        <Button onClick={onExit}>Back to Skills</Button>
      </div>
    );
  }

  const question = exercises[index];

  return (
    <Card variant="clay">
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg">{skillName}</CardTitle>
          <span className="text-xs text-muted-foreground">
            Question {index + 1} of {exercises.length}
          </span>
        </div>
      </CardHeader>
      <CardContent className="flex flex-col gap-5">
        <p className="text-lg font-medium text-foreground">{question.prompt}</p>

        <div className="flex flex-col gap-3">
          {question.options.map((option, optionIndex) => {
            const isSelected = selected === optionIndex;
            const showFeedback = feedback !== null;
            const isCorrectOption = optionIndex === feedback?.correctIndex;
            return (
              <button
                key={optionIndex}
                disabled={showFeedback}
                onClick={() => setSelected(optionIndex)}
                className={`rounded-xl border-2 p-3 text-left text-base transition-all ${
                  showFeedback
                    ? isCorrectOption
                      ? "border-success-400 bg-success-50"
                      : isSelected
                      ? "border-error-300 bg-error-50"
                      : "border-border opacity-60"
                    : isSelected
                    ? "border-primary bg-primary-50"
                    : "border-border hover:border-primary-200 hover:bg-muted"
                }`}
              >
                {option}
              </button>
            );
          })}
        </div>

        {feedback && (
          <p className={`text-sm font-medium ${feedback.correct ? "text-success-600" : "text-error-600"}`}>
            {feedback.correct ? "Correct! 🎉" : "Not quite — the highlighted answer was correct."}
            {feedback.skillPassed && " You've now passed this skill!"}
          </p>
        )}

        <div className="flex justify-between border-t border-border pt-4">
          <Button variant="outline" onClick={onExit}>
            Exit
          </Button>
          {feedback === null ? (
            <Button onClick={handleSubmit} disabled={selected === null || submitting}>
              {submitting ? "Checking..." : "Submit Answer"}
            </Button>
          ) : (
            <Button onClick={handleNext}>{isLastExercise ? "Finish" : "Next Question"}</Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

// ─── Main page ────────────────────────────────────────────────────────────────
export function Skills() {
  const [skills, setSkills] = useState<SkillSummary[] | null>(null);
  const [error, setError] = useState(false);
  const [practicingSkillId, setPracticingSkillId] = useState<number | null>(null);

  function reload() {
    setSkills(null);
    listSkills()
      .then(setSkills)
      .catch(() => setError(true));
  }

  useEffect(() => {
    reload();
  }, []);

  if (practicingSkillId !== null) {
    const skill = skills?.find((s) => s.id === practicingSkillId);
    return (
      <div className="mx-auto max-w-2xl">
        <SkillPractice
          skillId={practicingSkillId}
          skillName={skill?.name ?? "Skill"}
          onExit={() => {
            setPracticingSkillId(null);
            reload(); // refresh unlock/pass status — this attempt may have unlocked the next tier
          }}
        />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center gap-3">
        <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-primary-50">
          <Puzzle className="h-6 w-6 text-primary-600" aria-hidden="true" />
        </span>
        <div>
          <h1 className="text-2xl font-bold text-foreground">Skills Practice</h1>
          <p className="mt-0.5 text-sm text-muted-foreground">
            Practice at your own pace. Pass every skill in a level to unlock the next one.
          </p>
        </div>
      </div>

      {error && (
        <p className="text-sm text-muted-foreground">Couldn't load skills right now. Please try again.</p>
      )}

      {!error && skills === null && (
        <div className="flex justify-center py-12">
          <LoadingSpinner />
        </div>
      )}

      {skills !== null &&
        (["Easy", "Medium", "Hard"] as const).map((tier) => {
          const tierSkills = skills.filter((s) => s.tier === tier);
          if (tierSkills.length === 0) return null;
          const passedCount = tierSkills.filter((s) => s.passed).length;
          return (
            <div key={tier} className={`rounded-2xl border-2 p-4 ${TIER_COLORS[tier]}`}>
              <div className="mb-3 flex items-center justify-between">
                <h2 className="font-semibold text-foreground">{TIER_LABELS[tier]} Skills</h2>
                <span className="text-xs text-muted-foreground">
                  {passedCount} / {tierSkills.length} passed
                </span>
              </div>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {tierSkills.map((skill) => (
                  <SkillCard key={skill.id} skill={skill} onPractice={() => setPracticingSkillId(skill.id)} />
                ))}
              </div>
            </div>
          );
        })}
    </div>
  );
}
