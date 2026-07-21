import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

export function ReportView({ text, streaming }: { text: string; streaming: boolean }) {
  if (!text && streaming) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-4 w-1/3" />
        <Skeleton className="h-3 w-full" />
        <Skeleton className="h-3 w-11/12" />
        <Skeleton className="h-3 w-10/12" />
        <Skeleton className="h-4 w-1/4 mt-6" />
        <Skeleton className="h-3 w-full" />
        <Skeleton className="h-3 w-9/12" />
      </div>
    );
  }
  if (!text) return <div className="text-sm text-muted-foreground italic">Report will appear once writing begins.</div>;

  return (
    <article className={cn("prose-aether text-sm leading-relaxed", streaming && "cursor-blink")}>
      {renderMarkdownLite(text)}
    </article>
  );
}

// Tiny markdown renderer for ## headings, **bold**, lists, line breaks
function renderMarkdownLite(text: string) {
  const lines = text.split("\n");
  const out: React.ReactNode[] = [];
  let listBuffer: string[] = [];
  const flushList = (key: string) => {
    if (!listBuffer.length) return;
    out.push(
      <ul key={key} className="my-3 ml-5 list-disc space-y-1 text-foreground/90">
        {listBuffer.map((it, i) => <li key={i}>{renderInline(it)}</li>)}
      </ul>
    );
    listBuffer = [];
  };
  lines.forEach((raw, i) => {
    const line = raw.trimEnd();
    if (line.startsWith("## ")) {
      flushList(`l-${i}`);
      out.push(<h3 key={i} className="mt-5 mb-2 text-base font-semibold text-gradient">{line.slice(3)}</h3>);
    } else if (line.startsWith("- ") || /^\d+\.\s/.test(line)) {
      listBuffer.push(line.replace(/^(-\s|\d+\.\s)/, ""));
    } else if (line === "") {
      flushList(`l-${i}`);
    } else {
      flushList(`l-${i}`);
      out.push(<p key={i} className="my-2 text-foreground/85">{renderInline(line)}</p>);
    }
  });
  flushList("end");
  return out;
}

function renderInline(s: string) {
  const parts = s.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((p, i) =>
    p.startsWith("**") && p.endsWith("**")
      ? <strong key={i} className="text-foreground">{p.slice(2, -2)}</strong>
      : <span key={i}>{p}</span>
  );
}
