import { useClinicalQuery } from "./hooks/useClinicalQuery";
import { Header } from "./components/Header";
import { Disclaimer } from "./components/Disclaimer";
import { QueryBar } from "./components/QueryBar";
import { ExampleQueries } from "./components/ExampleQueries";
import { AnswerPanel } from "./components/AnswerPanel";
import { EvidenceSidebar } from "./components/EvidenceSidebar";

// Edit this list to change the example chips shown under the search bar -
// no other file needs to change.
const EXAMPLE_QUERIES = [
  "What is the recommended anticoagulation approach for atrial fibrillation?",
  "What is guideline-directed medical therapy for heart failure with reduced ejection fraction?",
  "How long should dual antiplatelet therapy continue after PCI?",
  "Should healthy 60 year olds take aspirin to prevent a first heart attack?",
  "What door-to-balloon time is recommended for STEMI?",
];

const DISCLAIMER_TEXT =
  "For informational and educational use by licensed healthcare professionals. " +
  "This does not constitute medical advice for a specific patient.";

export default function App() {
  const {
    query,
    setQuery,
    submit,
    loading,
    error,
    data,
    highlightedChunkId,
    setHighlightedChunkId,
    submitFeedback,
    feedbackStatus,
  } = useClinicalQuery();

  return (
    <div className="max-w-[1180px] mx-auto px-6 py-7 pb-16">
      <Header specialty="Cardiology" />
      <Disclaimer message={DISCLAIMER_TEXT} />

      <QueryBar value={query} onChange={setQuery} onSubmit={() => submit()} loading={loading} />
      <ExampleQueries examples={EXAMPLE_QUERIES} onPick={(ex) => submit(ex)} />

      <div className="grid grid-cols-1 lg:grid-cols-[1.5fr_1fr] gap-5 items-start">
        <AnswerPanel
          answer={data?.answer ?? null}
          confidence={data?.confidence ?? null}
          loading={loading}
          error={error}
          onCitationClick={setHighlightedChunkId}
          feedbackStatus={feedbackStatus}
          onRate={submitFeedback}
        />
        <EvidenceSidebar
          chunks={data?.retrieved_chunks ?? []}
          loading={loading}
          highlightedChunkId={highlightedChunkId}
          hasAnswered={data !== null}
        />
      </div>

      <footer className="mt-10 text-[11.5px] text-ink-soft border-t border-line pt-3.5 font-mono">
        Connected to {import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000"}
      </footer>
    </div>
  );
}
