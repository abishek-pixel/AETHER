import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";
import { Download, FileText, FileType, FileCode, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { exportResearch, downloadFile } from "@/lib/api";
import { useState } from "react";

export interface ExportMenuProps {
  filename: string;
  content: string;
  sessionId?: string;
}

export function ExportMenu({ filename, content, sessionId }: ExportMenuProps) {
  const [isExporting, setIsExporting] = useState(false);

  const downloadLocal = (ext: string, mime: string, body: string) => {
    const blob = new Blob([body], { type: mime });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${filename}.${ext}`;
    a.click();
    URL.revokeObjectURL(url);
    toast.success(`Exported ${ext.toUpperCase()}`);
  };

  const exportFromBackend = async (format: "markdown" | "pdf" | "docx") => {
    if (!sessionId) {
      toast.error("Session ID required for backend export");
      return;
    }

    try {
      setIsExporting(true);
      const blob = await exportResearch(sessionId, {
        format,
        include_citations: true,
        include_reasoning: true,
      });
      
      downloadFile(blob, `${filename}.${format === "markdown" ? "md" : format}`);
      toast.success(`Exported ${format.toUpperCase()}`);
    } catch (error) {
      console.error("Export failed:", error);
      toast.error("Export failed. Using local export instead.");
      downloadLocal(format === "markdown" ? "md" : format, "text/plain", content);
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button size="sm" variant="outline" className="gap-2" disabled={isExporting}>
          {isExporting ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <Download className="h-3.5 w-3.5" />
          )}
          Export
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem onClick={() => downloadLocal("md", "text/markdown", content)}>
          <FileCode className="mr-2 h-4 w-4" /> Markdown (Local)
        </DropdownMenuItem>
        {sessionId && (
          <DropdownMenuItem onClick={() => exportFromBackend("markdown")}>
            <FileCode className="mr-2 h-4 w-4" /> Markdown (Formatted)
          </DropdownMenuItem>
        )}
        <DropdownMenuItem onClick={() => downloadLocal("txt", "text/plain", content)}>
          <FileText className="mr-2 h-4 w-4" /> Plain Text
        </DropdownMenuItem>
        {sessionId && (
          <>
            <DropdownMenuItem onClick={() => exportFromBackend("pdf")}>
              <FileType className="mr-2 h-4 w-4" /> PDF
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => exportFromBackend("docx")}>
              <FileType className="mr-2 h-4 w-4" /> DOCX
            </DropdownMenuItem>
          </>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
