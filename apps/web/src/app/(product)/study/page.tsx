"use client";

import { BookOpen, Check, FileText, LoaderCircle, Plus, Sparkles } from "lucide-react";
import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  createStudyCard,
  createStudyCourse,
  createStudySource,
  errorMessage,
  generateStudyCards,
  getStudyCourse,
  listStudyCourses,
  updateStudyCard,
  type StudyCard,
  type StudyCourse,
  type StudyCourseDetail,
} from "@/lib/api";

const inputClass = "w-full rounded-lg border bg-white px-3 py-2 text-sm focus-visible:outline-2 focus-visible:outline-green-800";

export default function StudyPage() {
  const [courses, setCourses] = useState<StudyCourse[]>([]);
  const [course, setCourse] = useState<StudyCourseDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showCourseForm, setShowCourseForm] = useState(false);

  const loadCourses = useCallback(async () => {
    const rows = await listStudyCourses();
    setCourses(rows);
    if (!course && rows[0]) setCourse(await getStudyCourse(rows[0].id));
  }, [course]);

  useEffect(() => {
    listStudyCourses()
      .then(async (rows) => { setCourses(rows); if (rows[0]) setCourse(await getStudyCourse(rows[0].id)); })
      .catch((reason: unknown) => setError(errorMessage(reason, "Could not load your courses.")))
      .finally(() => setLoading(false));
  }, []);

  async function selectCourse(id: string) {
    setError(null);
    try { setCourse(await getStudyCourse(id)); } catch (reason) { setError(errorMessage(reason, "Could not open that course.")); }
  }

  async function addCourse(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setBusy(true);
    try {
      const created = await createStudyCourse({ name: String(data.get("name")), description: String(data.get("description")) });
      await loadCourses();
      setCourse(await getStudyCourse(created.id));
      setShowCourseForm(false);
    } catch (reason) { setError(errorMessage(reason, "Could not create the course.")); } finally { setBusy(false); }
  }

  async function addCard(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!course) return;
    const data = new FormData(event.currentTarget);
    setBusy(true);
    try {
      await createStudyCard(course.id, {
        concept_id: String(data.get("concept_id")),
        card_type: String(data.get("card_type")) as StudyCard["card_type"],
        prompt: String(data.get("prompt")),
        answer: String(data.get("answer")),
        tags: String(data.get("tags")).split(",").map((tag) => tag.trim()).filter(Boolean),
      });
      event.currentTarget.reset();
      setCourse(await getStudyCourse(course.id));
      await loadCourses();
    } catch (reason) { setError(errorMessage(reason, "Could not create the card.")); } finally { setBusy(false); }
  }

  async function generate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!course) return;
    const data = new FormData(event.currentTarget);
    setBusy(true);
    setError(null);
    try {
      const source = await createStudySource(course.id, { title: String(data.get("title")), body: String(data.get("notes")) });
      await generateStudyCards(source.id);
      setCourse(await getStudyCourse(course.id));
      event.currentTarget.reset();
    } catch (reason) { setError(errorMessage(reason, "Could not generate cards.")); } finally { setBusy(false); }
  }

  async function activate(card: StudyCard) {
    setBusy(true);
    try { await updateStudyCard(card.id, { status: "active" }); if (course) setCourse(await getStudyCourse(course.id)); }
    catch (reason) { setError(errorMessage(reason, "Could not activate that card.")); }
    finally { setBusy(false); }
  }

  if (loading) return <p className="flex items-center gap-2 text-[var(--muted)]"><LoaderCircle className="animate-spin" size={18} /> Loading your study library…</p>;

  return (
    <div className="mx-auto max-w-7xl">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-sm font-bold uppercase tracking-[0.18em] text-green-800">AI-native spaced repetition</p>
          <h1 className="mt-3 text-4xl font-bold tracking-tight">Study anything worth remembering</h1>
          <p className="mt-3 max-w-2xl text-[var(--muted)]">Build cards yourself or turn class notes into drafts. Reps schedules each idea from your actual recall history.</p>
        </div>
        <div className="flex gap-2">
          <Button onClick={() => setShowCourseForm((value) => !value)} variant="secondary"><Plus size={16} /> New course</Button>
          <Link className="rounded-lg bg-green-800 px-4 py-2 text-sm font-semibold text-white hover:bg-green-900" href="/study/review">Review due cards</Link>
        </div>
      </div>
      {error ? <p className="mt-5 rounded-lg bg-red-50 p-3 text-sm text-red-900" role="alert">{error}</p> : null}
      {showCourseForm ? (
        <form className="mt-6 grid gap-3 rounded-2xl border bg-white p-5 sm:grid-cols-[1fr_2fr_auto]" onSubmit={(event) => void addCourse(event)}>
          <input aria-label="Course name" className={inputClass} name="name" placeholder="EECS 482" required />
          <input aria-label="Course description" className={inputClass} name="description" placeholder="Operating systems" />
          <Button disabled={busy} type="submit">Create</Button>
        </form>
      ) : null}
      {courses.length === 0 ? (
        <section className="mt-10 rounded-3xl border border-dashed bg-white/70 p-12 text-center">
          <BookOpen className="mx-auto text-green-800" size={36} />
          <h2 className="mt-4 text-xl font-bold">Create your first course</h2>
          <p className="mt-2 text-[var(--muted)]">A course can be a class, certification, book, or any body of knowledge.</p>
        </section>
      ) : (
        <div className="mt-8 grid gap-6 lg:grid-cols-[16rem_1fr]">
          <aside>
            <h2 className="text-xs font-bold uppercase tracking-wider text-[var(--muted)]">Courses</h2>
            <div className="mt-3 space-y-2">
              {courses.map((item) => <button className={`w-full rounded-xl border p-4 text-left ${course?.id === item.id ? "border-green-700 bg-green-50" : "bg-white hover:border-green-300"}`} key={item.id} onClick={() => void selectCourse(item.id)} type="button"><span className="font-bold">{item.name}</span><span className="mt-1 block text-xs text-[var(--muted)]">{item.due_count} due · {item.card_count} cards</span></button>)}
            </div>
          </aside>
          {course ? <CourseWorkspace busy={busy} course={course} onActivate={activate} onAddCard={addCard} onGenerate={generate} /> : null}
        </div>
      )}
    </div>
  );
}

function CourseWorkspace({ course, busy, onAddCard, onGenerate, onActivate }: { course: StudyCourseDetail; busy: boolean; onAddCard: (event: FormEvent<HTMLFormElement>) => Promise<void>; onGenerate: (event: FormEvent<HTMLFormElement>) => Promise<void>; onActivate: (card: StudyCard) => Promise<void> }) {
  const drafts = course.cards.filter((card) => card.status === "draft");
  return (
    <section className="min-w-0">
      <div className="flex items-start justify-between gap-4"><div><h2 className="text-3xl font-bold">{course.name}</h2><p className="mt-1 text-[var(--muted)]">{course.description || "Your adaptive study deck"}</p></div><span className="rounded-full bg-green-100 px-3 py-1 text-sm font-bold text-green-900">{course.due_count} due</span></div>
      <div className="mt-6 grid gap-5 xl:grid-cols-2">
        <form className="rounded-2xl border bg-white p-5" onSubmit={(event) => void onAddCard(event)}>
          <h3 className="flex items-center gap-2 font-bold"><Plus size={17} /> Make a card</h3>
          <div className="mt-4 grid gap-3">
            <select aria-label="Concept" className={inputClass} name="concept_id" required>{course.concepts.map((concept) => <option key={concept.id} value={concept.id}>{concept.name}</option>)}</select>
            <select aria-label="Card type" className={inputClass} defaultValue="basic" name="card_type"><option value="basic">Basic recall</option><option value="typed">Typed answer</option><option value="cloze">Cloze deletion</option><option value="explain">Explain</option><option value="compare">Compare</option><option value="reversed">Reversed</option></select>
            <textarea aria-label="Prompt" className={inputClass} name="prompt" placeholder="Question or prompt" required rows={3} />
            <textarea aria-label="Answer" className={inputClass} name="answer" placeholder="Expected answer" required rows={3} />
            <input aria-label="Tags" className={inputClass} name="tags" placeholder="Tags, comma separated" />
            <Button disabled={busy} type="submit">Add to review queue</Button>
          </div>
        </form>
        <form className="rounded-2xl border bg-white p-5" onSubmit={(event) => void onGenerate(event)}>
          <h3 className="flex items-center gap-2 font-bold"><Sparkles className="text-green-700" size={17} /> Generate drafts from notes</h3>
          <p className="mt-1 text-sm text-[var(--muted)]">The AI only proposes drafts. You approve each card before scheduling.</p>
          <div className="mt-4 grid gap-3"><input aria-label="Source title" className={inputClass} name="title" placeholder="Lecture 7 — Virtual memory" required /><textarea aria-label="Source notes" className={inputClass} name="notes" placeholder="Paste lecture notes, a study guide, or your own summary…" required rows={8} /><Button disabled={busy} type="submit">{busy ? <LoaderCircle className="animate-spin" size={16} /> : <Sparkles size={16} />} Generate card drafts</Button></div>
        </form>
      </div>
      {drafts.length ? <section className="mt-6"><h3 className="flex items-center gap-2 text-lg font-bold"><FileText size={18} /> Drafts awaiting approval ({drafts.length})</h3><div className="mt-3 grid gap-3">{drafts.map((card) => <article className="rounded-xl border border-amber-200 bg-amber-50/60 p-4" key={card.id}><p className="text-xs font-bold uppercase tracking-wider text-amber-900">{card.concept} · {card.card_type}</p><p className="mt-2 font-semibold">{card.prompt}</p><p className="mt-2 text-sm text-[var(--muted)]">{card.answer}</p><Button className="mt-3" disabled={busy} onClick={() => void onActivate(card)} variant="secondary"><Check size={15} /> Approve and schedule</Button></article>)}</div></section> : null}
      <section className="mt-8"><h3 className="text-lg font-bold">Card library ({course.cards.length})</h3>{course.cards.length === 0 ? <p className="mt-2 text-[var(--muted)]">No cards yet. Make one or generate drafts from notes.</p> : <div className="mt-3 overflow-hidden rounded-xl border bg-white"><div className="divide-y">{course.cards.filter((card) => card.status !== "draft").map((card) => <div className="flex items-start justify-between gap-4 p-4" key={card.id}><div><p className="font-semibold">{card.prompt}</p><p className="mt-1 text-sm text-[var(--muted)]">{card.concept} · {card.card_type} · reviewed {card.review_count}×</p></div><span className="rounded-full bg-stone-100 px-2 py-1 text-xs font-semibold">{card.status}</span></div>)}</div></div>}</section>
    </section>
  );
}
