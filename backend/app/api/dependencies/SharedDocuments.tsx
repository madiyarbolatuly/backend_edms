import React, { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/services/apiclient";
import { useToast } from "@/hooks/use-toast";
import { SearchBar } from "@/components/SearchBar";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Breadcrumb, BreadcrumbItem, BreadcrumbLink, BreadcrumbList, BreadcrumbPage, BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import {
  Share2, Download, File, FileImage, FileText, Folder, Timer, ChevronDown, ChevronRight, Eye
} from "lucide-react";
import { Table, TableHeader, TableRow, TableHead, TableBody, TableCell } from "@/components/ui/table";
import { downloadByFileId } from "@/services/downloadService";
import { durableUploadFolder } from "@/services/durableUpload";
import { UserButton } from "@/components/UserButton";

// ──────────────────────────────────────────────────────────────────────────────
// Minimal DOM types for directory drag-drop (Chromium/Safari)
// ──────────────────────────────────────────────────────────────────────────────
type FileSystemEntry = {
  isFile: boolean;
  isDirectory: boolean;
  name: string;
  fullPath?: string;
};
type FileSystemFileEntry = FileSystemEntry & {
  file: (cb: (file: File) => void) => void;
};
type FileSystemDirectoryEntry = FileSystemEntry & {
  createReader: () => { readEntries: (cb: (entries: FileSystemEntry[]) => void) => void };
};

type WebkitFileSystemEntry = {
  isFile: boolean;
  isDirectory: boolean;
  name: string;
  fullPath?: string;
};
type WebkitFileSystemFileEntry = WebkitFileSystemEntry & {
  file: (cb: (file: File) => void) => void;
};
type WebkitFileSystemDirectoryEntry = WebkitFileSystemEntry & {
  createReader: () => { readEntries: (cb: (entries: WebkitFileSystemEntry[]) => void) => void };
};


// ──────────────────────────────────────────────────────────────────────────────
// Types
// ──────────────────────────────────────────────────────────────────────────────
type SharedWithMeItem = {
  id: number;
  token: string;
  shared_with: string;
  filename: string;
  expires_at: string;
  document_id: number;
  shared_by: string;
  created_at: string;
  file_type?: string; // "folder" | file ext inferred server-side
};

interface SharedDocCard {
  id: string;               // share id (stringified)
  name: string;
  type: "folder" | "file";
  documentId: number;       // numeric id (for /children and uploads)
  sharedBy: string;
  createdAt: string;
  expiresAt: string;        // ISO
  token: string;
}

interface TreeNode {
  id: string;
  name: string;
  type: "folder" | "file";
  _nid: number;
  _parentId: number | null;
}

type RoDoc = {
  id: number;
  name: string;
  type: "folder" | "file";
  sizeText: string;
  modified: string | null;
  owner?: string | null;
  parent_id: number | null;
};

// ──────────────────────────────────────────────────────────────────────────────
// Utils
// ──────────────────────────────────────────────────────────────────────────────
const clamp = (v: number, min = 0, max = 100) => Math.min(max, Math.max(min, v));

const fileTypeFromName = (name: string, forceFolder = false): "folder" | "file" => {
  if (forceFolder) return "folder";
  const lower = name.toLowerCase();
  return /\.(pdf|pptx?|xlsx?|docx?|png|jpe?g|gif|webp|bmp|tiff|zip|7z|rar|dwg)$/i.test(lower) ? "file" : "folder";
};

const renderIcon = (type: "folder" | "file", name?: string) => {
  if (type === "folder") return <Folder className="h-5 w-5 text-yellow-500" />;
  const n = (name || "").toLowerCase();
  if (n.endsWith(".pdf")) return <FileText className="h-5 w-5 text-red-500" />;
  if (/\.(png|jpe?g|gif|webp|bmp|tiff)$/i.test(n)) return <FileImage className="h-5 w-5 text-purple-500" />;
  return <File className="h-5 w-5 text-gray-500" />;
};

const fmtBytes = (n?: number | null) => {
  if (!n || n <= 0) return "—";
  const u = ["B","KB","MB","GB","TB"];
  const i = Math.floor(Math.log(n)/Math.log(1024));
  return `${(n/Math.pow(1024, i)).toFixed(i ? 1 : 0)} ${u[i]}`;
};

// Progress helpers
const formatBytes = (n: number) => {
  if (!n) return "0 B";
  const u = ["B","KB","MB","GB","TB"];
  const i = Math.floor(Math.log(n)/Math.log(1024));
  return `${(n/Math.pow(1024, i)).toFixed(i ? 1 : 0)} ${u[i]}`;
};
const formatDuration = (s: number) => {
  if (!isFinite(s) || s <= 0) return "—";
  const m = Math.floor(s/60), sec = Math.floor(s%60);
  return m ? `${m}м ${sec}с` : `${sec}с`;
};

// ──────────────────────────────────────────────────────────────────────────────
/** Countdown */
// ──────────────────────────────────────────────────────────────────────────────
function useCountdown(targetIso: string) {
  const [now, setNow] = useState<number>(Date.now());
  const target = useMemo(() => {
    const t = Date.parse(targetIso);
    return Number.isFinite(t) ? t : 0;
  }, [targetIso]);

  useEffect(() => {
    if (!target) return;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [target]);

  const msLeft = Math.max(0, target - now);
  const expired = msLeft <= 0;
  const s = Math.floor(msLeft / 1000);
  const dd = Math.floor(s / 86400);
  const hh = Math.floor((s % 86400) / 3600);
  const mm = Math.floor((s % 3600) / 60);
  const ss = s % 60;

  return { expired, dd, hh, mm, ss };
}

const CountdownBadge: React.FC<{ iso: string }> = ({ iso }) => {
  const { expired, dd, hh, mm, ss } = useCountdown(iso);
  return (
    <div
      className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-semibold border ${
        expired ? "bg-red-50 text-red-700 border-red-200" : "bg-emerald-50 text-emerald-700 border-emerald-200"
      }`}
      title={new Date(iso).toLocaleString()}
      aria-live="polite"
    >
      <Timer className="h-4 w-4" />
      {expired ? "Ссылка истекла" : `Осталось: ${dd ? dd + "д " : ""}${hh}ч ${mm}м ${ss}с`}
    </div>
  );
};

// ──────────────────────────────────────────────────────────────────────────────
/** Read-only folder tree for quick preview */
// ──────────────────────────────────────────────────────────────────────────────
const FolderTree = React.memo(function FolderTree({
  node,
  expired,
  fetchChildrenCached,
}: {
  node: TreeNode;
  expired: boolean;
  fetchChildrenCached: (parentId: number) => Promise<TreeNode[]>;
}) {
  const [expanded, setExpanded] = useState(false);
  const [children, setChildren] = useState<TreeNode[]>([]);

  const toggle = useCallback(async () => {
    if (!expanded && node.type === "folder" && children.length === 0) {
      const list = await fetchChildrenCached(node._nid);
      setChildren(list);
    }
    setExpanded((e) => !e);
  }, [expanded, node.type, children.length, fetchChildrenCached, node._nid]);

  const onDownload = useCallback(async () => {
    if (expired) return;
    const token = localStorage.getItem("authToken") || "";
    await downloadByFileId(node._nid, token, node.name);
  }, [expired, node._nid, node.name]);

  return (
    <div className="ml-2">
      <div className="flex items-center gap-2 py-1">
        {node.type === "folder" ? (
          <button onClick={toggle} className="flex items-center gap-1 text-left hover:bg-gray-100 rounded px-1 py-0.5">
            {expanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
            <Folder className="h-5 w-5 text-yellow-500" />
            <span className="font-medium truncate max-w-[18rem]">{node.name}</span>
          </button>
        ) : (
          <div className="flex items-center gap-2">
            <File className="h-5 w-5 text-gray-500" />
            <span className="truncate max-w-[18rem]">{node.name}</span>
            <Button
              size="sm"
              variant={expired ? "secondary" : "default"}
              className="ml-2"
              disabled={expired}
              onClick={onDownload}
            >
              <Download className="h-4 w-4 mr-1" /> Скачать
            </Button>
          </div>
        )}
      </div>

      {expanded && children.length > 0 && (
        <div className="ml-4">
          {children.map((c) => (
            <FolderTree key={c.id} node={c} expired={expired} fetchChildrenCached={fetchChildrenCached} />
          ))}
        </div>
      )}
      {expanded && node.type === "folder" && children.length === 0 && (
        <div className="ml-6 text-sm text-gray-500 py-1">Пусто</div>
      )}
    </div>
  );
});

// ──────────────────────────────────────────────────────────────────────────────
/** Read-only Folder Browser + drag&drop upload */
// ──────────────────────────────────────────────────────────────────────────────
const ReadOnlyFolderView: React.FC<{
  rootId: number;
  rootName: string;
  expired: boolean;
  onExit: () => void;
}> = ({ rootId, rootName, expired, onExit }) => {
  const token = localStorage.getItem("authToken") || "";
  const { toast } = useToast();

  const [currentId, setCurrentId] = useState<number>(rootId);
  const [path, setPath] = useState<Array<{ id: number; name: string }>>([{ id: rootId, name: rootName }]);
  const [items, setItems] = useState<RoDoc[]>([]);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState<"name" | "size" | "modified">("name");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");

  const [isDragging, setIsDragging] = useState(false);
  const [dragCounter, setDragCounter] = useState(0);

  const [isUploading, setIsUploading] = useState(false);
  const [overallPct, setOverallPct] = useState(0);
  const [uploadStats, setUploadStats] = useState({ totalBytes: 0, uploadedBytes: 0, startedAt: 0, speedBps: 0, etaSec: 0 });

  const mapDoc = (d: any): RoDoc => {
    const type: "folder" | "file" = d.file_type === "folder" ? "folder" : "file";
    const sizeText = type === "folder" ? "—" : fmtBytes(typeof d.size === "number" ? d.size : null);
    return {
      id: Number(d.id),
      name: d.name || d.title || "Без названия",
      type,
      sizeText,
      modified: d.created_at || d.modified_at || null,
      owner: d.owner_id || null,
      parent_id: d.parent_id == null ? null : Number(d.parent_id),
    };
  };

  const fetchFolderItems = useCallback(async (parentId: number) => {
    setLoading(true);
    try {
      const qs = new URLSearchParams({
        limit: "1000",
        offset: "0",
        recursive: "false",
        parent_id: String(parentId),
      });
      const res = await fetch(`/api/v2/metadata?${qs.toString()}`, {
        headers: { Authorization: `Bearer ${token}`, Accept: "application/json" },
      });
      if (!res.ok) throw new Error(String(res.status));
      const data = await res.json();
      const docs = Array.isArray(data?.documents) ? data.documents : [];
      const mapped = docs.map(mapDoc);
      mapped.sort((a: RoDoc, b: RoDoc) => (a.type === b.type ? a.name.localeCompare(b.name) : a.type === "folder" ? -1 : 1));
      setItems(mapped);
    } catch (e: any) {
      console.error(e);
      toast({ title: "Ошибка", description: "Не удалось загрузить папку", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  }, [token, toast]);

  useEffect(() => {
    fetchFolderItems(currentId);
  }, [currentId, fetchFolderItems]);

  const onEnterFolder = (id: number, name: string) => {
    setCurrentId(id);
    setPath((p) => [...p, { id, name }]);
  };
  const onCrumb = (id: number, index: number) => {
    setCurrentId(id);
    setPath((p) => p.slice(0, index + 1));
  };

  // ── DnD upload helpers
  const traverseFileTree = async (
    item: WebkitFileSystemEntry,
    path = "",
    fileList: File[] = []
  ): Promise<void> =>
    new Promise((resolve) => {
      if ((item as WebkitFileSystemFileEntry).file) {
        (item as WebkitFileSystemFileEntry).file((file) => {
          (file as any).relativePath = path + item.name;
          fileList.push(file);
          resolve();
        });
      } else if ((item as WebkitFileSystemDirectoryEntry).createReader) {
        const dirReader = (item as WebkitFileSystemDirectoryEntry).createReader();
        dirReader.readEntries(async (entries: WebkitFileSystemEntry[]) => {
          for (const entry of entries) {
            await traverseFileTree(entry, path + item.name + "/", fileList);
          }
          resolve();
        });
      } else {
        resolve();
      }
    });

  const gatherDroppedFiles = async (e: React.DragEvent): Promise<File[]> => {
    const files: File[] = [];
    const items = e.dataTransfer?.items;
    if (items && items.length > 0) {
      for (let i = 0; i < items.length; i++) {
        const dtItem = items[i];
        theLoop: {
          const entry = typeof dtItem.webkitGetAsEntry === "function" ? dtItem.webkitGetAsEntry() : null;
          if (entry) {
            await traverseFileTree(entry, "", files);
            break theLoop;
          }
          const file = dtItem.getAsFile?.();
          if (file) {
            (file as any).relativePath = (file as any).webkitRelativePath || file.name;
            files.push(file);
          }
        }
      }
    }
    if (files.length === 0) {
      const fallback = Array.from(e.dataTransfer.files || []);
      fallback.forEach((f) => ((f as any).relativePath = (f as any).webkitRelativePath || f.name));
      files.push(...fallback);
    }
    return files;
  };

  const uploadFiles = async (files: File[], destFolderId?: number) => {
    if (!files?.length) return;
    const totalBytes = files.reduce((a, f) => a + (f.size || 0), 0);
    setIsUploading(true);
    setUploadStats({ totalBytes, uploadedBytes: 0, startedAt: Date.now(), speedBps: 0, etaSec: 0 });
    try {
      await durableUploadFolder(
        files,
        token!,
        { base: "/api/v2", folderId: destFolderId ?? currentId ?? undefined },
        {
          targetBatchMB: 100,
          maxFilesPerBatch: 250,
          concurrency: 3,
          timeoutMs: 10 * 60 * 1000,
          onProgress: (pct) => {
            const safe = clamp(Number.isFinite(pct) ? pct : 0, 0, 100);
            setOverallPct(safe);
            setUploadStats((prev) => {
              const uploadedBytes = Math.round(totalBytes * (safe / 100));
              const elapsedSec = (Date.now() - (prev.startedAt || Date.now())) / 1000;
              const speedBps = elapsedSec > 0 ? uploadedBytes / elapsedSec : 0;
              const remaining = Math.max(totalBytes - uploadedBytes, 0);
              const etaSec = speedBps > 0 ? Math.ceil(remaining / speedBps) : 0;
              return { ...prev, uploadedBytes, speedBps, etaSec };
            });
          }
        }
      );
      toast({ title: "Готово", description: `Загружено ${files.length} объект(ов)`, variant: "default" });
      await fetchFolderItems(currentId);
    } catch (err: any) {
      console.error(err);
      toast({ title: "Ошибка загрузки", description: err?.message || "Не удалось загрузить", variant: "destructive" });
    } finally {
      setIsUploading(false);
      setOverallPct(0);
    }
  };

  const onDragEnterArea = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault(); e.stopPropagation();
    setDragCounter((c) => c + 1);
    setIsDragging(true);
  };
  const onDragLeaveArea = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault(); e.stopPropagation();
    setDragCounter((c) => {
      const next = c - 1;
      if (next <= 0) { setIsDragging(false); return 0; }
      return next;
    });
  };
  const onDragOverArea = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault(); e.stopPropagation();
  };
  const onDropArea = async (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault(); e.stopPropagation();
    setDragCounter(0);
    setIsDragging(false);
    if (expired) return;
    const files = await gatherDroppedFiles(e);
    await uploadFiles(files, currentId);
  };

  // Preview/download in list
  const onPreview = useCallback(async (doc: RoDoc) => {
    if (expired || doc.type !== "file") return;
    try {
      const res = await fetch(`/api/v2/preview/${encodeURIComponent(doc.id)}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        const ct = (res.headers.get("content-type") || "").toLowerCase();
        if (!ct.includes("application/json")) throw new Error(String(res.status));
        const data = await res.json();
        if (data?.url) {
          window.open(data.url, "_blank", "noopener");
          return;
        }
        throw new Error("Нет URL предпросмотра");
      }
      const ct = (res.headers.get("content-type") || "").toLowerCase();
      if (ct.includes("application/json")) {
        const data = await res.json();
        if (data?.url) {
          window.open(data.url, "_blank", "noopener");
          return;
        }
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      window.open(url, "_blank", "noopener");
    } catch (e: any) {
      console.error(e);
      toast({ title: "Ошибка предпросмотра", description: e?.message || "Не удалось открыть предпросмотр", variant: "destructive" });
    }
  }, [expired, token, toast]);

  const onDownload = useCallback(async (doc: RoDoc) => {
    if (expired) return;
    await downloadByFileId(doc.id, token, doc.type === "folder" ? `${doc.name}.zip` : doc.name);
  }, [expired, token]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return items;
    return items.filter((d) => d.name.toLowerCase().includes(q));
  }, [items, search]);

  const toBytesForSort = (s: string) => {
    if (s === "—") return -1;
    const m = s.match(/^([\d.]+)\s*(B|KB|MB|GB|TB)$/i);
    if (!m) return 0;
    const num = parseFloat(m[1]);
    const unit = m[2].toUpperCase();
    const mul = unit === "B" ? 1 : unit === "KB" ? 1024 : unit === "MB" ? 1024 ** 2 : unit === "GB" ? 1024 ** 3 : 1024 ** 4;
    return num * mul;
  };

  const sorted = useMemo(() => {
    const arr = [...filtered];
    arr.sort((a, b) => (a.type === b.type ? 0 : a.type === "folder" ? -1 : 1));
    arr.sort((a, b) => {
      let A: any, B: any;
      if (sortBy === "name") { A = a.name.toLowerCase(); B = b.name.toLowerCase(); }
      else if (sortBy === "size") { A = toBytesForSort(a.sizeText); B = toBytesForSort(b.sizeText); }
      else { A = a.modified || ""; B = b.modified || ""; }
      if (A < B) return sortDir === "asc" ? -1 : 1;
      if (A > B) return sortDir === "asc" ? 1 : -1;
      return 0;
    });
    return arr;
  }, [filtered, sortBy, sortDir]);

  const SortHead: React.FC<{ id: "name" | "size" | "modified"; children: React.ReactNode }> = ({ id, children }) => (
    <TableHead
      onClick={() => {
        if (sortBy === id) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
        else { setSortBy(id); setSortDir("asc"); }
      }}
      className="cursor-pointer select-none"
      title="Сортировать"
    >
      <span className="inline-flex items-center gap-1">
        {children}
        {sortBy === id ? <span className="text-xs">{sortDir === "asc" ? "▲" : "▼"}</span> : null}
      </span>
    </TableHead>
  );

  return (
    <div
      className="w-full relative"
      onDragEnter={onDragEnterArea}
      onDragOver={onDragOverArea}
      onDragLeave={onDragLeaveArea}
      onDrop={onDropArea}
    >
      {/* Overlay */}
      {isDragging && (
        <div className="fixed inset-0 z-50 bg-blue-100/50 border-4 border-dashed border-blue-400 flex items-center justify-center">
          <p className="text-lg font-semibold text-blue-600">Перетащите файлы или папки для загрузки</p>
        </div>
      )}

      {/* Header & controls */}
      <div className="mb-6">
        <Breadcrumb className="mb-4">
          <BreadcrumbList>
            <BreadcrumbItem>
              <BreadcrumbLink
                href="#"
                onClick={(e) => {
                  e.preventDefault();
                  onExit();
                }}
              >
                Общие
              </BreadcrumbLink>
            </BreadcrumbItem>
            <BreadcrumbSeparator />
            {path.map((p, idx) => (
              <React.Fragment key={p.id}>
                {idx < path.length - 1 ? (
                  <>
                    <BreadcrumbItem>
                      <BreadcrumbLink
                        href="#"
                        onClick={(e) => {
                          e.preventDefault();
                          onCrumb(p.id, idx);
                        }}
                      >
                        {p.name}
                      </BreadcrumbLink>
                    </BreadcrumbItem>
                    <BreadcrumbSeparator />
                  </>
                ) : (
                  <BreadcrumbItem>
                    <BreadcrumbPage>{p.name}</BreadcrumbPage>
                  </BreadcrumbItem>
                )}
              </React.Fragment>
            ))}
          </BreadcrumbList>
        </Breadcrumb>

        <div className="flex items-center justify-between gap-3">
          <h2 className="text-2xl font-bold text-gray-900">Содержимое: {path[path.length - 1]?.name}</h2>
          <div className="flex gap-2">
            <Button variant="outline" onClick={onExit}>Назад к ссылкам</Button>
          </div>
        </div>

        <div className="mt-4">
          <SearchBar
            query={search}
            setQuery={setSearch}
            placeholder="Поиск в папке…"
            showFilterButton={false}
          />
        </div>
      </div>

      {/* List */}
      <div className="rounded-xl border bg-white shadow-sm">
        <Table>
          <TableHeader>
            <TableRow>
              <SortHead id="name">Имя</SortHead>
              <SortHead id="size">Размер</SortHead>
              <SortHead id="modified">Обновлено</SortHead>
              <TableHead className="w-56 text-right pr-6">Действия</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow><TableCell colSpan={4} className="p-6 text-center text-muted-foreground">Загрузка…</TableCell></TableRow>
            ) : sorted.length === 0 ? (
              <TableRow><TableCell colSpan={4} className="p-6 text-center text-muted-foreground">Пусто</TableCell></TableRow>
            ) : sorted.map((it) => (
              <TableRow key={it.id}>
                <TableCell>
                  <div
                    className={`flex items-center gap-3 ${it.type === "folder" ? "text-blue-600 font-semibold cursor-pointer" : ""}`}
                    onClick={() => it.type === "folder" ? onEnterFolder(it.id, it.name) : undefined}
                    title={it.name}
                  >
                    {renderIcon(it.type, it.name)}
                    <span className="truncate">{it.type === "folder" ? `${it.name}/` : it.name}</span>
                  </div>
                </TableCell>
                <TableCell className="text-muted-foreground">{it.sizeText}</TableCell>
                <TableCell className="text-muted-foreground">
                  {it.modified ? new Date(it.modified).toLocaleString() : "—"}
                </TableCell>
                <TableCell className="text-right pr-6">
                  <div className="flex justify-end gap-2">
                    {it.type !== "folder" && (
                      <Button size="sm" variant="outline" onClick={() => onPreview(it)}>
                        <Eye className="h-4 w-4 mr-1" /> Предпросмотр
                      </Button>
                    )}
                    <Button size="sm" onClick={() => onDownload(it)}>
                      <Download className="h-4 w-4 mr-1" /> Скачать
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {/* Upload progress */}
      {isUploading && (
        <div className="fixed right-4 bottom-4 z-[70] w-96 rounded-xl border bg-white/95 shadow-lg p-4">
          <div className="flex items-center justify-between mb-2">
            <div className="font-medium">Загрузка… {Math.round(clamp(overallPct))}%</div>
            <div className="text-xs text-muted-foreground">
              Осталось {formatDuration(uploadStats.etaSec)}
            </div>
          </div>
          <div className="h-2 w-full rounded bg-gray-200 overflow-hidden mb-2">
            <div
              className="h-2 bg-blue-600 transition-all"
              style={{ width: `${clamp(overallPct || 0, 0, 100)}%` }}
            />
          </div>
          <div className="text-xs text-muted-foreground">
            {formatBytes(uploadStats.uploadedBytes)} / {formatBytes(uploadStats.totalBytes)}
            {" • "}
            {formatBytes(uploadStats.speedBps)}/с
          </div>
        </div>
      )}
    </div>
  );
};

// ──────────────────────────────────────────────────────────────────────────────
/** Card item with external file drop to upload into that folder */
// ──────────────────────────────────────────────────────────────────────────────
const CardItem = React.memo(function CardItem({
  card,
  fetchChildrenCached,
  onDownload,
  open,
  onToggleOpen,
  onOpenAsList,
  onDropExternalToFolder,
  dragOverActive,
  setDragOverActive,
}: {
  card: SharedDocCard;
  fetchChildrenCached: (parentId: number) => Promise<TreeNode[]>;
  onDownload: (card: SharedDocCard, expired: boolean) => Promise<void>;
  open: boolean;
  onToggleOpen: () => void;
  onOpenAsList: () => void;
  onDropExternalToFolder: (folderId: number, e: React.DragEvent<HTMLDivElement>) => void;
  dragOverActive: boolean;
  setDragOverActive: (v: boolean) => void;
}) {
  const { expired } = useCountdown(card.expiresAt);
  const isFolder = card.type === "folder";

  return (
    <div
      className={`group bg-white border-0 shadow-lg hover:shadow-2xl transition-all overflow-hidden select-none ${
        dragOverActive ? "ring-2 ring-blue-500 ring-offset-2" : ""
      }`}
      draggable={false}
      onDragEnter={(e) => {
        if (!isFolder) return;
        e.preventDefault(); e.stopPropagation();
        setDragOverActive(true);
      }}
      onDragOver={(e) => {
        if (!isFolder) return;
        e.preventDefault(); e.stopPropagation();
      }}
      onDragLeave={(e) => {
        if (!isFolder) return;
        e.preventDefault(); e.stopPropagation();
        const related = e.relatedTarget as Node | null;
        if (related && (e.currentTarget as Element).contains(related)) return;
        setDragOverActive(false);
      }}
      onDrop={(e) => {
        if (!isFolder) return;
        setDragOverActive(false);
        onDropExternalToFolder(card.documentId, e);
      }}
    >
      <Card>
        <CardContent className="p-0">
          {/* Preview */}
          <div className="relative aspect-[4/3] bg-gradient-to-br from-gray-100 to-gray-200 flex items-center justify-center">
            {isFolder ? <Folder className="h-12 w-12 text-yellow-500" /> : <File className="h-12 w-12 text-gray-500" />}
            <div className="absolute top-3 left-3">
              <CountdownBadge iso={card.expiresAt} />
            </div>
            {expired && (
              <div className="absolute inset-0 bg-white/70 backdrop-blur-sm flex items-center justify-center text-red-700 font-semibold">
                Доступ истёк
              </div>
            )}
          </div>

          <div className="p-6 space-y-4">
            <div>
              <h3 className="font-bold text-lg text-gray-900 mb-1 line-clamp-2" title={card.name}>
                {card.name}
              </h3>
              <div className="text-sm text-gray-500">
                Поделился: <span className="font-medium">{card.sharedBy || "админ"}</span>
              </div>
            </div>

            <div className="space-y-3">
              <Button
                className="w-full bg-gradient-to-r from-blue-500 to-purple-600 hover:from-blue-600 hover:to-purple-700 text-white font-semibold py-3 rounded-xl shadow-lg hover:shadow-xl transition-all duration-300 disabled:opacity-60"
                disabled={expired}
                aria-disabled={expired}
                onClick={() => onDownload(card, expired)}
              >
                <Download className="h-5 w-5 mr-2" />
                {isFolder ? "Скачать всё (.zip)" : "Скачать файл"}
              </Button>

              {isFolder && (
                <FolderContents
                  rootId={card.documentId}
                  expired={expired}
                  fetchChildrenCached={fetchChildrenCached}
                  open={open}
                  onToggleOpen={onToggleOpen}
                  onOpenAsList={onOpenAsList}
                />
              )}
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
});

// ──────────────────────────────────────────────────────────────────────────────
/** Compact folder contents under a card */
// ──────────────────────────────────────────────────────────────────────────────
const FolderContents = React.memo(function FolderContents({
  rootId,
  expired,
  fetchChildrenCached,
  open,
  onToggleOpen,
  onOpenAsList,
}: {
  rootId: number;
  expired: boolean;
  fetchChildrenCached: (parentId: number) => Promise<TreeNode[]>;
  open: boolean;
  onToggleOpen: () => void;
  onOpenAsList: () => void;
})  {
  const [rootChildren, setRootChildren] = useState<TreeNode[] | null>(null);
  const [loading, setLoading] = useState(false);

  const toggle = useCallback(async () => {
    if (!open && !rootChildren) {
      setLoading(true);
      try {
        const direct = await fetchChildrenCached(rootId);
        setRootChildren(direct);
      } finally {
        setLoading(false);
      }
    }
    onToggleOpen();
  }, [open, rootChildren, fetchChildrenCached, rootId, onToggleOpen]);

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-2">
        <Button
          variant="secondary"
          className="w-full bg-white hover:bg-gray-50 text-gray-900 font-semibold py-3 rounded-xl border border-gray-200 shadow-sm hover:shadow transition-all duration-300"
          onClick={toggle}
        >
          {open ? "Скрыть содержимое" : "Быстрый просмотр"}
        </Button>
        <Button
          variant="outline"
          className="w-full font-semibold py-3 rounded-xl border border-gray-200"
          onClick={onOpenAsList}
        >
          Открыть списком
        </Button>
      </div>

      {open && (
        <div className="w-full mt-2 rounded-xl border border-gray-200 bg-gray-50 p-3 max-h-[50vh] overflow-auto">
          {loading ? (
            <div className="text-sm text-gray-500">Загрузка…</div>
          ) : rootChildren && rootChildren.length > 0 ? (
            rootChildren.map((child) => (
              <FolderTree key={child.id} node={child} expired={expired} fetchChildrenCached={fetchChildrenCached} />
            ))
          ) : (
            <div className="text-sm text-gray-500">Пусто</div>
          )}
        </div>
      )}
    </div>
  );
});

// ──────────────────────────────────────────────────────────────────────────────
/** Page */
// ──────────────────────────────────────────────────────────────────────────────
const SharedDocuments: React.FC = () => {
  const { toast } = useToast();
  const token = localStorage.getItem("authToken") || "";

  const [isLoading, setIsLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [cards, setCards] = useState<SharedDocCard[]>([]);
  const [browseRoot, setBrowseRoot] = useState<{ id: number; name: string; expiresAt: string } | null>(null);

  // open/close per documentId
  const [openByCard, setOpenByCard] = useState<Record<number, boolean>>({});
  // drag-over highlight per card
  const [dragOverMap, setDragOverMap] = useState<Record<number, boolean>>({});

  // global drop overlay
  const [isDragging, setIsDragging] = useState(false);
  const [dragCounter, setDragCounter] = useState(0);

  // upload progress
  const [isUploading, setIsUploading] = useState(false);
  const [overallPct, setOverallPct] = useState(0);
  const [uploadStats, setUploadStats] = useState({ totalBytes: 0, uploadedBytes: 0, startedAt: 0, speedBps: 0, etaSec: 0 });

  const fetchSharedWithMe = useCallback(async () => {
    setIsLoading(true);
    try {
      const { data } = await api.get<SharedWithMeItem[]>(`/sharing/shared-with-me`);
      const mapped: SharedDocCard[] = data.map((x) => ({
        id: String(x.id),
        name: x.filename,
        type: (x.file_type === "folder") ? "folder" : fileTypeFromName(x.filename),
        documentId: x.document_id,
        sharedBy: x.shared_by,
        createdAt: x.created_at,
        expiresAt: x.expires_at,
        token: x.token,
      }));
      // Sort by expires_at (sooner first)
      setCards(mapped.sort((a, b) => new Date(a.expiresAt).getTime() - new Date(b.expiresAt).getTime()));
    } catch (e) {
      console.error(e);
      toast({ title: "Ошибка", description: "Не удалось загрузить список общих элементов", variant: "destructive" });
    } finally {
      setIsLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    fetchSharedWithMe();
  }, [fetchSharedWithMe]);

  const filtered = useMemo(
    () => cards.filter(c => c.name.toLowerCase().includes(searchQuery.toLowerCase())),
    [cards, searchQuery]
  );

  const mapDocsToTree = (arr: any[]): TreeNode[] =>
    (arr || []).map((d: any) => ({
      id: String(d.id),
      name: d.name || d.title || "Без названия",
      type: (d.file_type === "folder") ? "folder" : "file",
      _nid: Number(d.id),
      _parentId: d.parent_id == null ? null : Number(d.parent_id),
    }));

  const fetchChildren = useCallback(async (parentId: number): Promise<TreeNode[]> => {
    const res = await api.get(`/children/${parentId}`);
    const data = Array.isArray(res.data) ? res.data : res.data?.items || [];
    return mapDocsToTree(data);
  }, []);

  // ── DnD upload building blocks
  const traverseFileTree = async (item: FileSystemEntry, path = "", fileList: File[] = []): Promise<void> =>
    new Promise((resolve) => {
      if ((item as FileSystemFileEntry).file) {
        (item as FileSystemFileEntry).file((file) => {
          (file as any).relativePath = path + item.name;
          fileList.push(file);
          resolve();
        });
      } else if ((item as FileSystemDirectoryEntry).createReader) {
        const dirReader = (item as FileSystemDirectoryEntry).createReader();
        dirReader.readEntries(async (entries) => {
          for (const entry of entries) {
            await traverseFileTree(entry, path + item.name + "/", fileList);
          }
          resolve();
        });
      } else {
        resolve();
      }
    });

  const gatherDroppedFiles = async (e: React.DragEvent): Promise<File[]> => {
    const files: File[] = [];
    const items = e.dataTransfer?.items;
    if (items && items.length > 0) {
      for (let i = 0; i < items.length; i++) {
        const dtItem = items[i];
        const entry = typeof dtItem.webkitGetAsEntry === "function" ? dtItem.webkitGetAsEntry() : null;
        if (entry) {
          await traverseFileTree(entry, "", files);
        } else {
          const file = dtItem.getAsFile?.();
          if (file) {
            (file as any).relativePath = (file as any).webkitRelativePath || file.name;
            files.push(file);
          }
        }
      }
    }
    if (files.length === 0) {
      const fallback = Array.from(e.dataTransfer.files || []);
      fallback.forEach((f) => ((f as any).relativePath = (f as any).webkitRelativePath || f.name));
      files.push(...fallback);
    }
    return files;
  };

  const uploadFiles = async (files: File[], destFolderId?: number) => {
    if (!files?.length) return;
    const totalBytes = files.reduce((a, f) => a + (f.size || 0), 0);
    setIsUploading(true);
    setUploadStats({ totalBytes, uploadedBytes: 0, startedAt: Date.now(), speedBps: 0, etaSec: 0 });
    try {
      await durableUploadFolder(
        files,
        token!,
        { base: "/api/v2", folderId: destFolderId ?? undefined },
        {
          targetBatchMB: 100,
          maxFilesPerBatch: 250,
          concurrency: 3,
          timeoutMs: 10 * 60 * 1000,
          onProgress: (pct) => {
            const safe = clamp(Number.isFinite(pct) ? pct : 0, 0, 100);
            setOverallPct(safe);
            setUploadStats((prev) => {
              const uploadedBytes = Math.round(totalBytes * (safe / 100));
              const elapsedSec = (Date.now() - (prev.startedAt || Date.now())) / 1000;
              const speedBps = elapsedSec > 0 ? uploadedBytes / elapsedSec : 0;
              const remaining = Math.max(totalBytes - uploadedBytes, 0);
              const etaSec = speedBps > 0 ? Math.ceil(remaining / speedBps) : 0;
              return { ...prev, uploadedBytes, speedBps, etaSec };
            });
          }
        }
      );
      // список "Общие" не нужно рефрешить — это список ссылок, не содержимое папок
    } catch (err: any) {
      console.error(err);
      toast({ title: "Ошибка загрузки", description: err?.message || "Не удалось загрузить", variant: "destructive" });
    } finally {
      setIsUploading(false);
      setOverallPct(0);
    }
  };

  // global overlay handlers
  const onDragEnterArea = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault(); e.stopPropagation();
    setDragCounter((c) => c + 1);
    setIsDragging(true);
  };
  const onDragLeaveArea = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault(); e.stopPropagation();
    setDragCounter((c) => {
      const next = c - 1;
      if (next <= 0) { setIsDragging(false); return 0; }
      return next;
    });
  };
  const onDragOverArea = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault(); e.stopPropagation();
  };
  const onDropArea = async (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault(); e.stopPropagation();
    setDragCounter(0);
    setIsDragging(false);
    const files = await gatherDroppedFiles(e);
    await uploadFiles(files); // сервер сам определит назначение (корень или текущая)
  };

  // per-folder external drop
  const onDropExternalToFolder = async (folderId: number, e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault(); e.stopPropagation();
    const files = await gatherDroppedFiles(e);
    setDragOverMap((m) => ({ ...m, [folderId]: false }));
    await uploadFiles(files, folderId);
  };

  // open/close handlers
  const isOpen = useCallback((docId: number) => !!openByCard[docId], [openByCard]);
  const toggleOpen = useCallback((docId: number) => {
    setOpenByCard(prev => ({ ...prev, [docId]: !prev[docId] }));
  }, []);

  // switch to list view
  const openAsList = useCallback((card: SharedDocCard) => {
    setBrowseRoot({ id: card.documentId, name: card.name, expiresAt: card.expiresAt });
  }, []);

  // keep hooks order stable
  const listExpired = useCountdown(browseRoot?.expiresAt || "").expired;

  if (browseRoot) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-purple-50">
        <div className="w-full px-4 sm:px-6 lg:px-8 py-8">
          <ReadOnlyFolderView
            rootId={browseRoot.id}
            rootName={browseRoot.name}
            expired={listExpired}
            onExit={() => setBrowseRoot(null)}
          />
        </div>
      </div>
    );
  }

  // Card grid with global drop
  return (
    <div
      className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-purple-50 relative"
      onDragEnter={onDragEnterArea}
      onDragOver={onDragOverArea}
      onDragLeave={onDragLeaveArea}
      onDrop={onDropArea}
    >
      {/* Global overlay */}
      {isDragging && (
        <div className="fixed inset-0 z-50 bg-blue-100/50 border-4 border-dashed border-blue-400 flex items-center justify-center">
          <p className="text-lg font-semibold text-blue-600">Перетащите файлы или папки для загрузки</p>
        </div>
      )}

      <div className="w-full px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center justify-between mb-6">
            <Breadcrumb>
              <BreadcrumbList>
                <BreadcrumbItem>
                  <BreadcrumbLink href="/" className="text-blue-600 hover:text-blue-800">Документы</BreadcrumbLink>
                </BreadcrumbItem>
                <BreadcrumbSeparator />
                <BreadcrumbItem>
                  <BreadcrumbPage className="text-gray-700">Общие</BreadcrumbPage>
                </BreadcrumbItem>
              </BreadcrumbList>
            </Breadcrumb>
            <UserButton />
          </div>

          <div className="text-center mb-8">
            <h1 className="text-4xl font-bold text-gray-900 mb-3">Общие файлы</h1>
            <p className="text-xl text-gray-600 max-w-2xl mx-auto">
              Просматривайте и скачивайте. Перетащите файлы или папки на карточку папки, чтобы загрузить их внутрь.
            </p>
          </div>

          <div className="w-full">
            <SearchBar
              query={searchQuery}
              setQuery={setSearchQuery}
              placeholder="Поиск по имени…"
              showFilterButton={false}
            />
          </div>
        </div>

        {/* Content */}
        {isLoading ? (
          <div className="text-center py-16">
            <div className="bg-white rounded-2xl shadow-lg p-12 max-w-md mx-auto">
              <div className="w-20 h-20 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-6 animate-pulse">
                <Share2 className="h-10 w-10 text-blue-600" />
              </div>
              <h3 className="text-2xl font-semibold text-gray-900 mb-3">Загрузка…</h3>
              <p className="text-gray-600">Пожалуйста, подождите</p>
            </div>
          </div>
        ) : filtered.length === 0 ? (
          <div className="text-center py-16">
            <div className="bg-white rounded-2xl shadow-lg p-12 max-w-md mx-auto">
              <div className="w-20 h-20 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-6">
                <Share2 className="h-10 w-10 text-blue-600" />
              </div>
              <h3 className="text-2xl font-semibold text-gray-900 mb-3">Нет ссылок</h3>
              <p className="text-gray-600">Активные общие папки и файлы появятся здесь</p>
            </div>
          </div>
        ) : (
          <div className="grid w-full grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
            {filtered.map((card) => (
              <CardItem
                key={card.documentId}
                card={card}
                fetchChildrenCached={async (pid) => {
                  const res = await fetch(`/api/v2/metadata?${new URLSearchParams({
                    limit: "1000", offset: "0", recursive: "false", parent_id: String(pid)
                  })}`, { headers: { Authorization: `Bearer ${token}`, Accept: "application/json" }});
                  const data = await res.json();
                  return (data?.documents || []).map((d: any) => ({
                    id: String(d.id),
                    name: d.name || d.title || "Без названия",
                    type: d.file_type === "folder" ? "folder" : "file",
                    _nid: Number(d.id),
                    _parentId: d.parent_id == null ? null : Number(d.parent_id),
                  }));
                }}
                onDownload={async (c, expired) => {
                  if (expired) return;
                  const suggested = c.type === "folder" ? `${c.name}.zip` : c.name;
                  await downloadByFileId(c.documentId, token, suggested);
                }}
                open={!!openByCard[card.documentId]}
                onToggleOpen={() => toggleOpen(card.documentId)}
                onOpenAsList={() => openAsList(card)}
                onDropExternalToFolder={onDropExternalToFolder}
                dragOverActive={!!dragOverMap[card.documentId]}
                setDragOverActive={(v) => setDragOverMap((m) => ({ ...m, [card.documentId]: v }))}
              />
            ))}
          </div>
        )}
      </div>

      {/* Upload progress */}
      {isUploading && (
        <div className="fixed right-4 bottom-4 z-[70] w-96 rounded-xl border bg-white/95 shadow-lg p-4">
          <div className="flex items-center justify-between mb-2">
            <div className="font-medium">Загрузка… {Math.round(clamp(overallPct))}%</div>
            <div className="text-xs text-muted-foreground">
              Осталось {formatDuration(uploadStats.etaSec)}
            </div>
          </div>
          <div className="h-2 w-full rounded bg-gray-200 overflow-hidden mb-2">
            <div
              className="h-2 bg-blue-600 transition-all"
              style={{ width: `${clamp(overallPct || 0, 0, 100)}%` }}
            />
          </div>
          <div className="text-xs text-muted-foreground">
            {formatBytes(uploadStats.uploadedBytes)} / {formatBytes(uploadStats.totalBytes)}
            {" • "}
            {formatBytes(uploadStats.speedBps)}/с
          </div>
        </div>
      )}
    </div>
  );
};

export default SharedDocuments;
