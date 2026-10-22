/**
 * WYSIWYG-Editor auf Basis von TipTap.
 *
 * Gespeichert wird Markdown, nicht HTML: der Versionsvergleich wird damit ein
 * lesbarer Zeilen-Diff, die Volltextsuche bleibt einfach, und der Inhalt ist in
 * der Datenbank noch von Hand lesbar. `tiptap-markdown` übernimmt die Umwandlung
 * in beide Richtungen.
 */

import Image from "@tiptap/extension-image";
import Link from "@tiptap/extension-link";
import { Table, TableCell, TableHeader, TableRow } from "@tiptap/extension-table";
import { EditorContent, useEditor, type Editor as TipTapEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import {
  Bold,
  CircleCheck,
  Code,
  Heading1,
  Heading2,
  Heading3,
  Info,
  Italic,
  FileSymlink,
  Link2,
  List,
  ListOrdered,
  Minus,
  NotebookPen,
  Quote,
  Redo2,
  Strikethrough,
  Table as TableIcon,
  TriangleAlert,
  Undo2,
} from "lucide-react";
import { useRef, type ComponentType, type ReactNode } from "react";
import { Markdown } from "tiptap-markdown";

import type { HinweisArt } from "../lib/markdown";
import { cn } from "../lib/utils";
import { Hinweis } from "../tiptap/hinweis";

interface Props {
  /**
   * Markdown-Startinhalt. Bewusst nur der Startwert: der Editor führt seinen
   * Zustand danach selbst. Soll er einen anderen Inhalt zeigen (andere Seite,
   * Abbrechen), hängt der Aufrufer ein anderes `key` an die Komponente und
   * erzwingt so eine frische Instanz.
   */
  initialWert: string;
  /**
   * Wird beim Aufbau gesetzt und liefert danach jederzeit den aktuellen Stand.
   *
   * Der Aufrufer holt sich den Inhalt beim Speichern hierüber ab, statt ihn in
   * eigenem State mitzuführen: gespiegelter State kann dem Editor eine
   * Aktualisierung hinterherhinken, und dann wird ein veralteter Stand
   * gespeichert.
   */
  holeMarkdown: { current: (() => string) | null };
  /** Wird beim Einfügen oder Ablegen einer Bilddatei aufgerufen; liefert die URL. */
  onBildEinfuegen?: (datei: File) => Promise<string>;
  /**
   * Öffnet die Auswahl einer Wiki-Seite und liefert Titel und Ziel, oder `null`
   * bei Abbruch. Der Editor kennt die Seitenliste nicht selbst.
   */
  onWikiLink?: () => Promise<{ titel: string; href: string } | null>;
}

const EXTENSIONS = [
  StarterKit.configure({
    // Auf drei Überschriftenebenen begrenzt — mehr braucht eine Wiki-Seite nicht,
    // und das Inhaltsverzeichnis bleibt übersichtlich.
    heading: { levels: [1, 2, 3] },
  }),
  Link.configure({ openOnClick: false }),
  Image,
  Table.configure({ resizable: false }),
  TableRow,
  TableHeader,
  TableCell,
  Hinweis,
  Markdown.configure({ html: false, transformPastedText: true }),
];

/** Die vier Hinweis-Panels in der Werkzeugleiste. */
const HINWEIS_KNOEPFE: {
  art: HinweisArt;
  titel: string;
  Symbol: ComponentType<{ className?: string }>;
}[] = [
  { art: "info", titel: "Hinweis: Info", Symbol: Info },
  { art: "erfolg", titel: "Hinweis: Erfolg", Symbol: CircleCheck },
  { art: "warnung", titel: "Hinweis: Warnung", Symbol: TriangleAlert },
  { art: "notiz", titel: "Hinweis: Notiz", Symbol: NotebookPen },
];

export function Editor({ initialWert, holeMarkdown, onBildEinfuegen, onWikiLink }: Props) {
  // Die Einfüge-Handler brauchen den Editor, der zu diesem Zeitpunkt noch nicht
  // existiert. Der Ref schließt die Lücke.
  const editorRef = useRef<TipTapEditor | null>(null);

  const editor = useEditor({
    extensions: EXTENSIONS,
    content: initialWert,
    editorProps: {
      attributes: { class: "wiki-inhalt focus:outline-none min-h-[24rem]" },
      handlePaste: (_view, ereignis) =>
        bildUebernehmen(ereignis, editorRef, onBildEinfuegen),
      handleDrop: (_view, ereignis) =>
        bildUebernehmen(ereignis as DragEvent, editorRef, onBildEinfuegen),
    },
  });
  editorRef.current = editor;
  holeMarkdown.current = editor ? () => editor.storage.markdown.getMarkdown() : null;

  if (!editor) return null;

  return (
    <div className="rounded-lg border border-border bg-card">
      <Werkzeugleiste editor={editor} onWikiLink={onWikiLink} />
      <div className="px-4 py-3">
        <EditorContent editor={editor} />
      </div>
    </div>
  );
}

/**
 * Bild aus Zwischenablage oder Drag-and-drop übernehmen.
 *
 * Der Upload läuft asynchron; erst wenn die URL da ist, wird das Bild an der
 * aktuellen Cursorposition eingesetzt.
 */
function bildUebernehmen(
  ereignis: ClipboardEvent | DragEvent,
  editorRef: { current: TipTapEditor | null },
  onBildEinfuegen?: (datei: File) => Promise<string>,
): boolean {
  if (!onBildEinfuegen) return false;
  const daten =
    "clipboardData" in ereignis ? ereignis.clipboardData : (ereignis as DragEvent).dataTransfer;
  const bild = Array.from(daten?.files ?? []).find((f) => f.type.startsWith("image/"));
  if (!bild) return false;

  ereignis.preventDefault();
  void onBildEinfuegen(bild)
    .then((url) => {
      editorRef.current?.chain().focus().setImage({ src: url, alt: bild.name }).run();
    })
    .catch(() => {
      window.alert("Bild konnte nicht hochgeladen werden.");
    });
  return true;
}

function Werkzeugleiste({
  editor,
  onWikiLink,
}: {
  editor: TipTapEditor;
  onWikiLink?: () => Promise<{ titel: string; href: string } | null>;
}) {
  const wikiSeiteVerlinken = () => {
    if (!onWikiLink) return;
    void onWikiLink().then((wahl) => {
      if (wahl === null) return;
      // Auswahl vorhanden? Dann nur verlinken. Sonst den Titel als Text einsetzen.
      const leer = editor.state.selection.empty;
      const kette = editor.chain().focus();
      if (leer) {
        kette.insertContent({
          type: "text",
          text: wahl.titel,
          marks: [{ type: "link", attrs: { href: wahl.href } }],
        });
      } else {
        kette.extendMarkRange("link").setLink({ href: wahl.href });
      }
      kette.run();
    });
  };

  const linkSetzen = () => {
    const bisher = (editor.getAttributes("link").href as string | undefined) ?? "";
    const ziel = window.prompt("Link-Adresse", bisher);
    if (ziel === null) return;
    if (ziel === "") {
      editor.chain().focus().unsetLink().run();
      return;
    }
    editor.chain().focus().extendMarkRange("link").setLink({ href: ziel }).run();
  };

  return (
    <div className="flex flex-wrap items-center gap-0.5 border-b border-border px-2 py-1.5">
      <Knopf
        titel="Fett"
        aktiv={editor.isActive("bold")}
        onClick={() => editor.chain().focus().toggleBold().run()}
      >
        <Bold className="h-4 w-4" />
      </Knopf>
      <Knopf
        titel="Kursiv"
        aktiv={editor.isActive("italic")}
        onClick={() => editor.chain().focus().toggleItalic().run()}
      >
        <Italic className="h-4 w-4" />
      </Knopf>
      <Knopf
        titel="Durchgestrichen"
        aktiv={editor.isActive("strike")}
        onClick={() => editor.chain().focus().toggleStrike().run()}
      >
        <Strikethrough className="h-4 w-4" />
      </Knopf>

      <Trenner />

      {([1, 2, 3] as const).map((stufe) => {
        const Symbol = stufe === 1 ? Heading1 : stufe === 2 ? Heading2 : Heading3;
        return (
          <Knopf
            key={stufe}
            titel={`Überschrift ${stufe}`}
            aktiv={editor.isActive("heading", { level: stufe })}
            onClick={() => editor.chain().focus().toggleHeading({ level: stufe }).run()}
          >
            <Symbol className="h-4 w-4" />
          </Knopf>
        );
      })}

      <Trenner />

      <Knopf
        titel="Aufzählung"
        aktiv={editor.isActive("bulletList")}
        onClick={() => editor.chain().focus().toggleBulletList().run()}
      >
        <List className="h-4 w-4" />
      </Knopf>
      <Knopf
        titel="Nummerierte Liste"
        aktiv={editor.isActive("orderedList")}
        onClick={() => editor.chain().focus().toggleOrderedList().run()}
      >
        <ListOrdered className="h-4 w-4" />
      </Knopf>
      <Knopf
        titel="Zitat"
        aktiv={editor.isActive("blockquote")}
        onClick={() => editor.chain().focus().toggleBlockquote().run()}
      >
        <Quote className="h-4 w-4" />
      </Knopf>
      <Knopf
        titel="Codeblock"
        aktiv={editor.isActive("codeBlock")}
        onClick={() => editor.chain().focus().toggleCodeBlock().run()}
      >
        <Code className="h-4 w-4" />
      </Knopf>
      <Knopf
        titel="Trennlinie"
        onClick={() => editor.chain().focus().setHorizontalRule().run()}
      >
        <Minus className="h-4 w-4" />
      </Knopf>

      <Trenner />

      {HINWEIS_KNOEPFE.map(({ art, titel, Symbol }) => (
        <Knopf
          key={art}
          titel={titel}
          aktiv={editor.isActive("hinweis", { art })}
          onClick={() => editor.chain().focus().hinweisUmschalten(art).run()}
        >
          <Symbol className="h-4 w-4" />
        </Knopf>
      ))}

      <Trenner />

      <Knopf titel="Link" aktiv={editor.isActive("link")} onClick={linkSetzen}>
        <Link2 className="h-4 w-4" />
      </Knopf>
      {onWikiLink && (
        <Knopf titel="Wiki-Seite verlinken" onClick={wikiSeiteVerlinken}>
          <FileSymlink className="h-4 w-4" />
        </Knopf>
      )}
      <Knopf
        titel="Tabelle einfügen"
        onClick={() =>
          editor.chain().focus().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run()
        }
      >
        <TableIcon className="h-4 w-4" />
      </Knopf>

      <Trenner />

      <Knopf titel="Rückgängig" onClick={() => editor.chain().focus().undo().run()}>
        <Undo2 className="h-4 w-4" />
      </Knopf>
      <Knopf titel="Wiederherstellen" onClick={() => editor.chain().focus().redo().run()}>
        <Redo2 className="h-4 w-4" />
      </Knopf>
    </div>
  );
}

function Trenner() {
  return <span className="mx-1 h-5 w-px bg-border" />;
}

function Knopf({
  titel,
  aktiv,
  onClick,
  children,
}: {
  titel: string;
  aktiv?: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      title={titel}
      aria-label={titel}
      aria-pressed={aktiv}
      // Verhindert, dass der Knopf den Fokus aus dem Editor zieht. Sonst kommt
      // er erst asynchron zurück, und wer sofort nach dem Klick weitertippt,
      // verliert die ersten Anschläge.
      onMouseDown={(e) => e.preventDefault()}
      onClick={onClick}
      className={cn(
        "rounded p-1.5 transition",
        aktiv ? "bg-primary-light text-primary" : "text-text-secondary hover:bg-background",
      )}
    >
      {children}
    </button>
  );
}
