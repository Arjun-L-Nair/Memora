import { FormEvent, useEffect, useState } from "react";
import { ClipboardList } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { Input } from "@/components/ui/Input";
import { LoadingSpinner } from "@/components/ui/LoadingSpinner";
import { Modal } from "@/components/ui/Modal";
import {
  assignPlanToStudents,
  createLearningPlan,
  deactivateLearningPlan,
  listLearningPlans,
  unassignPlanFromStudent,
  updateLearningPlan,
  type LearningPlanRecord,
} from "@/services/learningPlanService";
import {
  createLearningContent,
  deactivateLearningContent,
  listLearningContentForPlan,
  updateLearningContent,
  type LearningContentRecord,
} from "@/services/learningContentService";
import { assignLearningSession } from "@/services/learningSessionService";
import { listStudents, type StudentRecord } from "@/services/studentService";

const DIFFICULTY_LEVELS = ["Beginner", "Easy", "Medium", "Hard"] as const;

export function LearningPlans() {
  const [plans, setPlans] = useState<LearningPlanRecord[] | null>(null);
  const [students, setStudents] = useState<StudentRecord[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // --- Manage Students modal state (per plan) ---
  const [assignPlan, setAssignPlan] = useState<LearningPlanRecord | null>(null);
  const [assignSelection, setAssignSelection] = useState<Set<number>>(new Set());
  const [assignError, setAssignError] = useState<string | null>(null);
  const [assignSubmitting, setAssignSubmitting] = useState(false);

  // --- Edit Plan modal state ---
  const [editPlan, setEditPlan] = useState<LearningPlanRecord | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [editPlanError, setEditPlanError] = useState<string | null>(null);
  const [editPlanSubmitting, setEditPlanSubmitting] = useState(false);

  // --- Add Content modal state (per plan) ---
  const [contentModalPlan, setContentModalPlan] = useState<LearningPlanRecord | null>(null);
  const [contentTitle, setContentTitle] = useState("");
  const [contentBody, setContentBody] = useState("");
  const [contentDifficulty, setContentDifficulty] = useState<string>(DIFFICULTY_LEVELS[0]);
  const [contentVideoUrl, setContentVideoUrl] = useState("");
  const [contentTeacherNotes, setContentTeacherNotes] = useState("");
  const [contentFormError, setContentFormError] = useState<string | null>(null);
  const [contentSubmitting, setContentSubmitting] = useState(false);
  const [contentAdded, setContentAdded] = useState(false);

  // --- Manage/Edit Content modal state (per plan) ---
  const [manageContentPlan, setManageContentPlan] = useState<LearningPlanRecord | null>(null);
  const [manageContentList, setManageContentList] = useState<LearningContentRecord[] | null>(null);
  const [manageContentError, setManageContentError] = useState<string | null>(null);
  const [editingContent, setEditingContent] = useState<LearningContentRecord | null>(null);
  const [editContentTitle, setEditContentTitle] = useState("");
  const [editContentBody, setEditContentBody] = useState("");
  const [editContentDifficulty, setEditContentDifficulty] = useState<string>(DIFFICULTY_LEVELS[0]);
  const [editContentVideoUrl, setEditContentVideoUrl] = useState("");
  const [editContentTeacherNotes, setEditContentTeacherNotes] = useState("");
  const [editContentError, setEditContentError] = useState<string | null>(null);
  const [editContentSubmitting, setEditContentSubmitting] = useState(false);

  // --- Assign Session modal state (per plan) ---
  const [sessionModalPlan, setSessionModalPlan] = useState<LearningPlanRecord | null>(null);
  const [planContent, setPlanContent] = useState<LearningContentRecord[] | null>(null);
  const [selectedContentId, setSelectedContentId] = useState("");
  const [selectedSessionStudentId, setSelectedSessionStudentId] = useState("");
  const [sessionFormError, setSessionFormError] = useState<string | null>(null);
  const [sessionSubmitting, setSessionSubmitting] = useState(false);
  const [sessionAssigned, setSessionAssigned] = useState(false);

  function loadPlans() {
    listLearningPlans()
      .then(setPlans)
      .catch(() => setError("Couldn't load learning plans. Please try again."));
  }

  useEffect(() => {
    loadPlans();
    listStudents()
      .then(setStudents)
      .catch(() => {
        /* Student list is only needed for the create form; a failure here
           doesn't block viewing existing plans. */
      });
  }, []);

  function resetForm() {
    setTitle("");
    setDescription("");
    setFormError(null);
  }

  async function handleCreate(event: FormEvent) {
    event.preventDefault();
    setFormError(null);
    setSubmitting(true);
    try {
      await createLearningPlan({
        title,
        description: description || undefined,
        // No student_id — plans are created as a reusable, unassigned
        // container now. Use "Manage Students" afterward to assign it
        // to any number of students from the roster.
      });
      setIsModalOpen(false);
      resetForm();
      loadPlans();
    } catch {
      setFormError("Couldn't create this learning plan. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDeactivate(planId: number) {
    try {
      await deactivateLearningPlan(planId);
      loadPlans();
    } catch {
      setError("Couldn't deactivate this plan. Please try again.");
    }
  }

  // --- Manage Students (assign / unassign) ---

  function openAssignModal(plan: LearningPlanRecord) {
    setAssignPlan(plan);
    setAssignSelection(new Set(plan.assigned_student_ids));
    setAssignError(null);
  }

  function toggleAssignSelection(studentIdValue: number) {
    setAssignSelection((prev) => {
      const next = new Set(prev);
      if (next.has(studentIdValue)) {
        next.delete(studentIdValue);
      } else {
        next.add(studentIdValue);
      }
      return next;
    });
  }

  async function handleSaveAssignments() {
    if (!assignPlan) return;
    setAssignError(null);
    setAssignSubmitting(true);
    try {
      const currentlyAssigned = new Set(assignPlan.assigned_student_ids);
      const toAdd = [...assignSelection].filter((id) => !currentlyAssigned.has(id));
      const toRemove = [...currentlyAssigned].filter((id) => !assignSelection.has(id));

      if (toAdd.length > 0) {
        await assignPlanToStudents(assignPlan.id, toAdd);
      }
      for (const studentIdToRemove of toRemove) {
        await unassignPlanFromStudent(assignPlan.id, studentIdToRemove);
      }

      setAssignPlan(null);
      loadPlans();
    } catch {
      setAssignError("Couldn't save student assignments. Please try again.");
    } finally {
      setAssignSubmitting(false);
    }
  }

  // --- Edit Plan ---

  function openEditPlanModal(plan: LearningPlanRecord) {
    setEditPlan(plan);
    setEditTitle(plan.title);
    setEditDescription(plan.description ?? "");
    setEditPlanError(null);
  }

  async function handleEditPlan(event: FormEvent) {
    event.preventDefault();
    if (!editPlan) return;
    setEditPlanError(null);
    setEditPlanSubmitting(true);
    try {
      await updateLearningPlan(editPlan.id, {
        title: editTitle,
        description: editDescription || undefined,
      });
      setEditPlan(null);
      loadPlans();
    } catch {
      setEditPlanError("Couldn't save these changes. Please try again.");
    } finally {
      setEditPlanSubmitting(false);
    }
  }

  // --- Add Content ---

  function openContentModal(plan: LearningPlanRecord) {
    setContentModalPlan(plan);
    setContentTitle("");
    setContentBody("");
    setContentDifficulty(DIFFICULTY_LEVELS[0]);
    setContentVideoUrl("");
    setContentTeacherNotes("");
    setContentFormError(null);
    setContentAdded(false);
  }

  async function handleCreateContent(event: FormEvent) {
    event.preventDefault();
    if (!contentModalPlan) return;
    setContentFormError(null);
    setContentSubmitting(true);
    try {
      await createLearningContent({
        title: contentTitle,
        body: contentBody,
        difficulty_level: contentDifficulty,
        learning_plan_id: contentModalPlan.id,
        video_url: contentVideoUrl.trim() || null,
        teacher_notes: contentTeacherNotes.trim() || null,
      });
      // Show success state and reset form so teacher can add another
      setContentAdded(true);
      setContentTitle("");
      setContentBody("");
      setContentDifficulty(DIFFICULTY_LEVELS[0]);
      setContentVideoUrl("");
      setContentTeacherNotes("");
      // If Manage Content modal is open for the same plan, refresh its list
      if (manageContentPlan?.id === contentModalPlan.id) {
        listLearningContentForPlan(contentModalPlan.id)
          .then(setManageContentList)
          .catch(() => {});
      }
    } catch {
      setContentFormError("Couldn't add this content. Please check the details and try again.");
    } finally {
      setContentSubmitting(false);
    }
  }

  // --- Manage/Edit Content ---

  function openManageContentModal(plan: LearningPlanRecord) {
    setManageContentPlan(plan);
    setManageContentList(null);
    setManageContentError(null);
    setEditingContent(null);
    listLearningContentForPlan(plan.id)
      .then(setManageContentList)
      .catch(() => setManageContentError("Couldn't load content for this plan."));
  }

  function startEditingContent(item: LearningContentRecord) {
    setEditingContent(item);
    setEditContentTitle(item.title);
    setEditContentBody(item.body);
    setEditContentDifficulty(item.difficulty_level);
    setEditContentVideoUrl(item.video_url ?? "");
    setEditContentTeacherNotes(item.teacher_notes ?? "");
    setEditContentError(null);
  }

  async function handleEditContent(event: FormEvent) {
    event.preventDefault();
    if (!editingContent || !manageContentPlan) return;
    setEditContentError(null);
    setEditContentSubmitting(true);
    try {
      await updateLearningContent(editingContent.id, {
        title: editContentTitle,
        body: editContentBody,
        difficulty_level: editContentDifficulty,
        video_url: editContentVideoUrl.trim() || null,
        teacher_notes: editContentTeacherNotes.trim() || null,
      });
      setEditingContent(null);
      const refreshed = await listLearningContentForPlan(manageContentPlan.id);
      setManageContentList(refreshed);
    } catch {
      setEditContentError("Couldn't save these changes. Please try again.");
    } finally {
      setEditContentSubmitting(false);
    }
  }

  async function handleDeactivateContent(contentId: number) {
    if (!manageContentPlan) return;
    setManageContentError(null);
    try {
      await deactivateLearningContent(contentId);
      const refreshed = await listLearningContentForPlan(manageContentPlan.id);
      setManageContentList(refreshed);
    } catch {
      setManageContentError("Couldn't deactivate this content. Please try again.");
    }
  }

  // --- Assign Session ---

  function openSessionModal(plan: LearningPlanRecord) {
    setSessionModalPlan(plan);
    setPlanContent(null);
    setSelectedContentId("");
    setSelectedSessionStudentId(plan.assigned_student_ids.length === 1 ? String(plan.assigned_student_ids[0]) : "");
    setSessionFormError(null);
    setSessionAssigned(false);
    listLearningContentForPlan(plan.id)
      .then(setPlanContent)
      .catch(() => setSessionFormError("Couldn't load content for this plan."));
  }

  async function handleAssignSession(event: FormEvent) {
    event.preventDefault();
    if (!sessionModalPlan || !selectedContentId || !selectedSessionStudentId) return;
    setSessionFormError(null);
    setSessionSubmitting(true);
    try {
      await assignLearningSession({
        student_id: Number(selectedSessionStudentId),
        learning_plan_id: sessionModalPlan.id,
        learning_content_id: Number(selectedContentId),
      });
      setSessionAssigned(true);
    } catch {
      setSessionFormError("Couldn't assign this session. Please try again.");
    } finally {
      setSessionSubmitting(false);
    }
  }

  function studentName(id: number): string {
    return students.find((s) => s.id === id)?.full_name ?? `Student #${id}`;
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Learning Plans</h1>
          <p className="mt-1 text-muted-foreground">Assign learning paths to your students.</p>
        </div>
        <Button onClick={() => setIsModalOpen(true)}>
          Create Plan
        </Button>
      </div>

      {plans === null && !error && (
        <div className="flex justify-center py-12">
          <LoadingSpinner />
        </div>
      )}

      {error && (
        <EmptyState icon={ClipboardList} title="Something went wrong" description={error} />
      )}

      {plans !== null && plans.length === 0 && (
        <EmptyState
          icon={ClipboardList}
          title="No learning plans yet"
          description="Create a reusable learning plan, add content to it, then assign it to any of your students."
        />
      )}

      {plans !== null && plans.length > 0 && (
        <div className="flex flex-col gap-3">
          {plans.map((plan) => (
            <Card variant="glass" key={plan.id}>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle>{plan.title}</CardTitle>
                  <Badge variant={plan.is_active ? "success" : "neutral"}>
                    {plan.is_active ? "Active" : "Inactive"}
                  </Badge>
                </div>
                <CardDescription>
                  {plan.assigned_student_ids.length === 0
                    ? "Not assigned to any students yet"
                    : plan.assigned_student_ids.length === 1
                    ? `Assigned to ${studentName(plan.assigned_student_ids[0])}`
                    : `Assigned to ${plan.assigned_student_ids.length} students`}
                  {plan.description ? ` • ${plan.description}` : ""}
                </CardDescription>
              </CardHeader>
              {plan.is_active && (
                <CardContent className="flex flex-wrap gap-2">
                  <Button variant="outline" size="sm" onClick={() => openEditPlanModal(plan)}>
                    Edit
                  </Button>
                  <Button variant="outline" size="sm" onClick={() => openAssignModal(plan)}>
                    Manage Students
                  </Button>
                  <Button variant="outline" size="sm" onClick={() => openContentModal(plan)}>
                    Add Content
                  </Button>
                  <Button variant="outline" size="sm" onClick={() => openManageContentModal(plan)}>
                    Edit Content
                  </Button>
                  <Button variant="outline" size="sm" onClick={() => openSessionModal(plan)}>
                    Assign Session
                  </Button>
                  <Button variant="outline" size="sm" onClick={() => handleDeactivate(plan.id)}>
                    Deactivate
                  </Button>
                </CardContent>
              )}
            </Card>
          ))}
        </div>
      )}

      <Modal
        isOpen={isModalOpen}
        onClose={() => {
          setIsModalOpen(false);
          resetForm();
        }}
        title="Create Learning Plan"
      >
        <form className="flex flex-col gap-4" onSubmit={handleCreate}>
          <Input label="Title" required value={title} onChange={(e) => setTitle(e.target.value)} />
          <Input
            label="Description (optional)"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
          <p className="text-xs text-muted-foreground">
            You can assign this plan to any of your students afterward — it isn't tied to just one.
          </p>
          {formError && (
            <p role="alert" className="text-sm text-error-600">
              {formError}
            </p>
          )}
          <Button type="submit" disabled={submitting}>
            {submitting ? "Creating..." : "Create Plan"}
          </Button>
        </form>
      </Modal>

      <Modal
        isOpen={assignPlan !== null}
        onClose={() => setAssignPlan(null)}
        title={`Manage Students${assignPlan ? ` — ${assignPlan.title}` : ""}`}
      >
        {students.length === 0 ? (
          <p className="text-muted-foreground">Add a student first, then assign this plan to them.</p>
        ) : (
          <div className="flex flex-col gap-4">
            <p className="text-sm text-muted-foreground">
              Choose which of your students this plan is assigned to.
            </p>
            <div className="flex max-h-72 flex-col gap-1 overflow-y-auto">
              {students.map((s) => (
                <label
                  key={s.id}
                  className="flex items-center gap-3 rounded-md border border-border px-3 py-2 hover:bg-muted"
                >
                  <input
                    type="checkbox"
                    checked={assignSelection.has(s.id)}
                    onChange={() => toggleAssignSelection(s.id)}
                    className="h-4 w-4 accent-primary"
                  />
                  <span className="text-foreground">{s.full_name}</span>
                </label>
              ))}
            </div>
            {assignError && (
              <p role="alert" className="text-sm text-error-600">
                {assignError}
              </p>
            )}
            <Button onClick={handleSaveAssignments} disabled={assignSubmitting}>
              {assignSubmitting ? "Saving..." : "Save Assignments"}
            </Button>
          </div>
        )}
      </Modal>

      <Modal
        isOpen={editPlan !== null}
        onClose={() => setEditPlan(null)}
        title={`Edit Plan${editPlan ? ` — ${editPlan.title}` : ""}`}
      >
        <form className="flex flex-col gap-4" onSubmit={handleEditPlan}>
          <Input label="Title" required value={editTitle} onChange={(e) => setEditTitle(e.target.value)} />
          <Input
            label="Description (optional)"
            value={editDescription}
            onChange={(e) => setEditDescription(e.target.value)}
          />
          {editPlanError && (
            <p role="alert" className="text-sm text-error-600">
              {editPlanError}
            </p>
          )}
          <Button type="submit" disabled={editPlanSubmitting}>
            {editPlanSubmitting ? "Saving..." : "Save Changes"}
          </Button>
        </form>
      </Modal>

      <Modal
        isOpen={contentModalPlan !== null}
        onClose={() => setContentModalPlan(null)}
        title={`Add Content${contentModalPlan ? ` — ${contentModalPlan.title}` : ""}`}
      >
        <form className="flex flex-col gap-4" onSubmit={handleCreateContent}>
          <Input
            label="Title"
            required
            value={contentTitle}
            onChange={(e) => setContentTitle(e.target.value)}
          />
          <div className="flex flex-col gap-1.5">
            <label htmlFor="content-body" className="text-sm font-medium text-foreground">
              Content
            </label>
            <textarea
              id="content-body"
              required
              rows={5}
              value={contentBody}
              onChange={(e) => setContentBody(e.target.value)}
              className="w-full rounded-md border border-border bg-surface px-3 py-2 text-base text-foreground focus:border-primary-500 focus:outline-none"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <label htmlFor="content-difficulty" className="text-sm font-medium text-foreground">
              Difficulty Level
            </label>
            <select
              id="content-difficulty"
              required
              value={contentDifficulty}
              onChange={(e) => setContentDifficulty(e.target.value)}
              className="h-11 w-full rounded-md border border-border bg-surface px-3 text-base text-foreground focus:border-primary-500 focus:outline-none"
            >
              {DIFFICULTY_LEVELS.map((level) => (
                <option key={level} value={level}>
                  {level}
                </option>
              ))}
            </select>
          </div>
          <Input
            label="Video URL (optional)"
            type="url"
            placeholder="YouTube or direct video link"
            value={contentVideoUrl}
            onChange={(e) => setContentVideoUrl(e.target.value)}
          />
          <div className="flex flex-col gap-1.5">
            <label htmlFor="content-teacher-notes" className="text-sm font-medium text-foreground">
              Teacher's Notes <span className="text-muted-foreground font-normal">(optional)</span>
            </label>
            <textarea
              id="content-teacher-notes"
              rows={3}
              placeholder="Additional guidance shown below the lesson content..."
              value={contentTeacherNotes}
              onChange={(e) => setContentTeacherNotes(e.target.value)}
              className="w-full rounded-md border border-border bg-surface px-3 py-2 text-base text-foreground focus:border-primary-500 focus:outline-none"
            />
          </div>
          {contentFormError && (
            <p role="alert" className="text-sm text-error-600">
              {contentFormError}
            </p>
          )}
          {contentAdded && (
            <div role="status" className="rounded-md bg-success-50 border border-success-200 px-4 py-3 text-sm text-success-700">
              ✓ Content added successfully. Fill in the form to add another, or close this window.
            </div>
          )}
          <div className="flex gap-3">
            <Button type="submit" disabled={contentSubmitting} className="flex-1">
              {contentSubmitting ? "Adding..." : contentAdded ? "Add Another" : "Add Content"}
            </Button>
            {contentAdded && (
              <Button type="button" variant="secondary" onClick={() => setContentModalPlan(null)}>
                Done
              </Button>
            )}
          </div>
        </form>
      </Modal>

      <Modal
        isOpen={manageContentPlan !== null}
        onClose={() => setManageContentPlan(null)}
        title={`Edit Content${manageContentPlan ? ` — ${manageContentPlan.title}` : ""}`}
      >
        {editingContent ? (
          <form className="flex flex-col gap-4" onSubmit={handleEditContent}>
            <Input
              label="Title"
              required
              value={editContentTitle}
              onChange={(e) => setEditContentTitle(e.target.value)}
            />
            <div className="flex flex-col gap-1.5">
              <label htmlFor="edit-content-body" className="text-sm font-medium text-foreground">
                Content
              </label>
              <textarea
                id="edit-content-body"
                required
                rows={5}
                value={editContentBody}
                onChange={(e) => setEditContentBody(e.target.value)}
                className="w-full rounded-md border border-border bg-surface px-3 py-2 text-base text-foreground focus:border-primary-500 focus:outline-none"
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <label htmlFor="edit-content-difficulty" className="text-sm font-medium text-foreground">
                Difficulty Level
              </label>
              <select
                id="edit-content-difficulty"
                required
                value={editContentDifficulty}
                onChange={(e) => setEditContentDifficulty(e.target.value)}
                className="h-11 w-full rounded-md border border-border bg-surface px-3 text-base text-foreground focus:border-primary-500 focus:outline-none"
              >
                {DIFFICULTY_LEVELS.map((level) => (
                  <option key={level} value={level}>
                    {level}
                  </option>
                ))}
              </select>
            </div>
            <Input
              label="Video URL (optional)"
              type="url"
              placeholder="YouTube or direct video link"
              value={editContentVideoUrl}
              onChange={(e) => setEditContentVideoUrl(e.target.value)}
            />
            <div className="flex flex-col gap-1.5">
              <label htmlFor="edit-content-teacher-notes" className="text-sm font-medium text-foreground">
                Teacher's Notes <span className="text-muted-foreground font-normal">(optional)</span>
              </label>
              <textarea
                id="edit-content-teacher-notes"
                rows={3}
                placeholder="Additional guidance shown below the lesson content..."
                value={editContentTeacherNotes}
                onChange={(e) => setEditContentTeacherNotes(e.target.value)}
                className="w-full rounded-md border border-border bg-surface px-3 py-2 text-base text-foreground focus:border-primary-500 focus:outline-none"
              />
            </div>
            {editContentError && (
              <p role="alert" className="text-sm text-error-600">
                {editContentError}
              </p>
            )}
            <div className="flex gap-2">
              <Button type="submit" disabled={editContentSubmitting}>
                {editContentSubmitting ? "Saving..." : "Save Changes"}
              </Button>
              <Button type="button" variant="outline" onClick={() => setEditingContent(null)}>
                Back
              </Button>
            </div>
          </form>
        ) : manageContentList === null ? (
          <div className="flex justify-center py-8">
            <LoadingSpinner />
          </div>
        ) : manageContentError ? (
          <p className="text-sm text-error-600">{manageContentError}</p>
        ) : manageContentList.length === 0 ? (
          <p className="text-muted-foreground">
            This plan has no content yet. Use "Add Content" first.
          </p>
        ) : (
          <div className="flex flex-col gap-2">
            {manageContentList.map((item) => (
              <div
                key={item.id}
                className={`flex items-center justify-between rounded-md border p-3 ${
                  item.is_active ? "border-border" : "border-border bg-muted opacity-70"
                }`}
              >
                <div>
                  <div className="flex items-center gap-2">
                    <p className="font-medium text-foreground">{item.title}</p>
                    {!item.is_active && (
                      <span className="rounded-full border border-border bg-surface px-2 py-0.5 text-xs text-muted-foreground">
                        Inactive
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-muted-foreground">{item.difficulty_level}</p>
                </div>
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" onClick={() => startEditingContent(item)}>
                    Edit
                  </Button>
                  {item.is_active && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleDeactivateContent(item.id)}
                    >
                      Deactivate
                    </Button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </Modal>

      <Modal
        isOpen={sessionModalPlan !== null}
        onClose={() => setSessionModalPlan(null)}
        title={`Assign Session${sessionModalPlan ? ` — ${sessionModalPlan.title}` : ""}`}
      >
        {sessionAssigned ? (
          <div className="flex flex-col gap-4">
            <p className="text-foreground">
              Session assigned. The student will see this in Today's Learning next time they log in.
            </p>
            <Button onClick={() => setSessionModalPlan(null)}>Done</Button>
          </div>
        ) : planContent === null ? (
          <div className="flex justify-center py-8">
            <LoadingSpinner />
          </div>
        ) : planContent.length === 0 ? (
          <p className="text-muted-foreground">
            This plan has no content yet. Use "Add Content" first, then come back to assign a
            session.
          </p>
        ) : sessionModalPlan && sessionModalPlan.assigned_student_ids.length === 0 ? (
          <p className="text-muted-foreground">
            This plan isn't assigned to any students yet. Use "Manage Students" first.
          </p>
        ) : (
          <form className="flex flex-col gap-4" onSubmit={handleAssignSession}>
            <div className="flex flex-col gap-1.5">
              <label htmlFor="session-student" className="text-sm font-medium text-foreground">
                Student
              </label>
              <select
                id="session-student"
                required
                value={selectedSessionStudentId}
                onChange={(e) => setSelectedSessionStudentId(e.target.value)}
                className="h-11 w-full rounded-md border border-border bg-surface px-3 text-base text-foreground focus:border-primary-500 focus:outline-none"
              >
                <option value="">Choose a student</option>
                {sessionModalPlan?.assigned_student_ids.map((id) => (
                  <option key={id} value={id}>
                    {studentName(id)}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <label htmlFor="session-content" className="text-sm font-medium text-foreground">
                Content
              </label>
              <select
                id="session-content"
                required
                value={selectedContentId}
                onChange={(e) => setSelectedContentId(e.target.value)}
                className="h-11 w-full rounded-md border border-border bg-surface px-3 text-base text-foreground focus:border-primary-500 focus:outline-none"
              >
                <option value="">Choose content</option>
                {planContent.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.title} ({c.difficulty_level})
                  </option>
                ))}
              </select>
            </div>
            {sessionFormError && (
              <p role="alert" className="text-sm text-error-600">
                {sessionFormError}
              </p>
            )}
            <Button type="submit" disabled={sessionSubmitting || !selectedContentId || !selectedSessionStudentId}>
              {sessionSubmitting ? "Assigning..." : "Assign Session"}
            </Button>
          </form>
        )}
      </Modal>
    </div>
  );
}
