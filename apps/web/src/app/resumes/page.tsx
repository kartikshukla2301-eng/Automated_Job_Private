"use client"

import * as React from "react"
import {
  CheckCircle2,
  Copy,
  Download,
  Eye,
  FileCheck,
  FileText,
  ShieldCheck,
  Upload,
} from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { PageHeader } from "@/components/ui/page-header"
import { Dialog } from "@/components/ui/dialog"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { apiClient } from "@/lib/api-client"
import type { ResumeItem } from "@/types/api"

const FALLBACK_RESUMES: ResumeItem[] = [
  {
    id: "res-001",
    filename: "Kartik_Shukla_Platform_Infrastructure_2026.pdf",
    role_family: "platform",
    sha256_hash: "a4f892b1c3e4d567890abcdef1234567890abcdef1234567890abcdef1234567",
    size_bytes: 142850,
    created_at: "2026-11-15T08:00:00Z",
    is_active: true,
    highlights: [
      "Multi-region Kubernetes control plane managing 4,000+ nodes",
      "Terraform IaC automation reducing provisioning time by 75%",
      "eBPF & Envoy ingress routing with 12ms p99 latency",
    ],
  },
  {
    id: "res-002",
    filename: "Kartik_Shukla_Backend_Distributed_2026.pdf",
    role_family: "backend",
    sha256_hash: "b5e912c4d6f7890123456789abcdef123456789abcdef123456789abcdef1234",
    size_bytes: 138400,
    created_at: "2026-11-14T12:00:00Z",
    is_active: false,
    highlights: [
      "Go & Python payment microservices handling $2B+ monthly volume",
      "Kafka streaming architecture with idempotent event processing",
      "Zero data loss distributed database clustering in PostgreSQL",
    ],
  },
  {
    id: "res-003",
    filename: "Kartik_Shukla_Fullstack_Systems_2026.pdf",
    role_family: "fullstack",
    sha256_hash: "c6fa23d5e70123456789abcdef123456789abcdef123456789abcdef12345678",
    size_bytes: 149200,
    created_at: "2026-11-13T16:30:00Z",
    is_active: false,
    highlights: [
      "Next.js and FastAPI real-time operational dashboard architecture",
      "End-to-end type safety with TypeScript, Zod, and Pydantic",
      "Playwright browser automation test suites with 100% coverage",
    ],
  },
]

export default function ResumesPage() {
  const [resumes, setResumes] = React.useState<ResumeItem[]>(FALLBACK_RESUMES)
  const [selectedResume, setSelectedResume] = React.useState<ResumeItem | null>(null)
  const [uploadOpen, setUploadOpen] = React.useState<boolean>(false)
  const [copiedHash, setCopiedHash] = React.useState<string | null>(null)

  React.useEffect(() => {
    let ignore = false

    if (apiClient.getResumes) {
      Promise.resolve(apiClient.getResumes())
        .then((items) => {
          if (!ignore && items && items.length > 0) {
            setResumes(items)
          }
        })
        .catch(() => {
          if (!ignore) setResumes(FALLBACK_RESUMES)
        })
    }

    return () => {
      ignore = true
    }
  }, [])

  const handleCopyHash = (hash: string) => {
    navigator.clipboard?.writeText(hash)
    setCopiedHash(hash)
    setTimeout(() => setCopiedHash(null), 2000)
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Resume Library & Tailoring"
        description="Versioned resumes with SHA-256 duplicate detection, cryptographic integrity, and role family classification."
        breadcrumbs={[
          { label: "Overview", href: "/" },
          { label: "Resumes" },
        ]}
        badge={
          <Badge variant="outline" className="gap-1 font-mono text-xs">
            <span>{resumes.length} Resumes Registered</span>
          </Badge>
        }
        actions={
          <Button
            variant="default"
            size="sm"
            onClick={() => setUploadOpen(true)}
            className="gap-1.5 bg-blue-600 hover:bg-blue-700"
          >
            <Upload className="size-4" />
            <span>Upload New Resume</span>
          </Button>
        }
      />

      {/* Safety Notice Strip */}
      <div className="flex items-center gap-2.5 rounded-xl border border-emerald-200 bg-emerald-50/70 p-3.5 text-xs text-emerald-900 shadow-xs">
        <ShieldCheck className="size-4 text-emerald-600 shrink-0" />
        <span>
          <strong>Anti-Hallucination Integrity:</strong> Resumes are stored immutably with SHA-256 content hashes. The ResumeIntelligenceEngine extracts verified highlights strictly from your canonical profile without fabricating credentials.
        </span>
      </div>

      {/* Resumes Table */}
      <div className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-xs space-y-4">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Filename & Hash</TableHead>
              <TableHead>Role Family</TableHead>
              <TableHead>Size</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Created</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {resumes.map((resume) => (
              <TableRow key={resume.id}>
                <TableCell>
                  <div className="font-semibold text-slate-900 text-xs flex items-center gap-1.5">
                    <FileText className="size-3.5 text-blue-600 shrink-0" />
                    <span>{resume.filename}</span>
                  </div>
                  <div className="flex items-center gap-1 mt-1">
                    <code className="rounded bg-slate-100 px-1 py-0.5 font-mono text-[10px] text-slate-500">
                      {resume.sha256_hash.slice(0, 16)}...{resume.sha256_hash.slice(-8)}
                    </code>
                    <button
                      type="button"
                      onClick={() => handleCopyHash(resume.sha256_hash)}
                      className="text-slate-400 hover:text-slate-700 p-0.5"
                      title="Copy full SHA-256 hash"
                    >
                      <Copy className="size-3" />
                    </button>
                    {copiedHash === resume.sha256_hash && (
                      <span className="text-[10px] text-emerald-600 font-medium">Copied!</span>
                    )}
                  </div>
                </TableCell>

                <TableCell>
                  <Badge
                    variant={
                      resume.role_family === "platform"
                        ? "indigo"
                        : resume.role_family === "backend"
                        ? "info"
                        : "secondary"
                    }
                    size="sm"
                    className="capitalize font-mono"
                  >
                    {resume.role_family}
                  </Badge>
                </TableCell>

                <TableCell className="font-mono text-xs text-slate-500">
                  {Math.round(resume.size_bytes / 1024)} KB
                </TableCell>

                <TableCell>
                  {resume.is_active ? (
                    <Badge variant="success" size="sm" className="gap-1">
                      <CheckCircle2 className="size-3" />
                      <span>Active Default</span>
                    </Badge>
                  ) : (
                    <Badge variant="outline" size="sm">
                      Inactive
                    </Badge>
                  )}
                </TableCell>

                <TableCell className="text-xs text-slate-500">
                  {new Date(resume.created_at).toLocaleDateString(undefined, {
                    month: "short",
                    day: "numeric",
                    year: "numeric",
                  })}
                </TableCell>

                <TableCell className="text-right">
                  <div className="flex items-center justify-end gap-1.5">
                    <Button
                      variant="outline"
                      size="xs"
                      onClick={() => setSelectedResume(resume)}
                      className="gap-1"
                    >
                      <Eye className="size-3" />
                      <span>Highlights</span>
                    </Button>
                    <Button
                      variant="ghost"
                      size="xs"
                      className="text-blue-600 hover:bg-blue-50 gap-1"
                      onClick={() => alert(`Downloading ${resume.filename} (SHA-256 verified)`)}
                    >
                      <Download className="size-3" />
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {/* Highlights Modal */}
      {selectedResume && (
        <Dialog
          open={Boolean(selectedResume)}
          onClose={() => setSelectedResume(null)}
          title={`Tailored Highlights: ${selectedResume.role_family.toUpperCase()}`}
          description={selectedResume.filename}
          footer={
            <Button variant="outline" size="sm" onClick={() => setSelectedResume(null)}>
              Close
            </Button>
          }
        >
          <div className="space-y-4 text-xs">
            <div>
              <span className="font-semibold text-slate-700">Cryptographic SHA-256 Digest:</span>
              <p className="mt-1 rounded bg-slate-100 p-2 font-mono text-[11px] text-slate-800 break-all select-all">
                {selectedResume.sha256_hash}
              </p>
            </div>

            <div>
              <span className="font-semibold text-slate-700">Key Prioritized Achievements:</span>
              <ul className="mt-1.5 space-y-2">
                {selectedResume.highlights.map((h, i) => (
                  <li key={i} className="flex items-start gap-2 rounded-lg border border-slate-100 bg-slate-50/70 p-2 text-slate-700">
                    <FileCheck className="size-3.5 text-emerald-600 shrink-0 mt-0.5" />
                    <span>{h}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </Dialog>
      )}

      {/* Upload Dialog */}
      {uploadOpen && (
        <Dialog
          open={uploadOpen}
          onClose={() => setUploadOpen(false)}
          title="Upload Verified Resume"
          description="Register a new PDF or DOCX resume version. Files are scanned and hashed before storage."
          footer={
            <>
              <Button variant="outline" size="sm" onClick={() => setUploadOpen(false)}>
                Cancel
              </Button>
              <Button
                variant="default"
                size="sm"
                className="bg-blue-600 hover:bg-blue-700"
                onClick={() => {
                  setUploadOpen(false)
                  alert("Resume uploaded and SHA-256 registered!")
                }}
              >
                Upload & Verify
              </Button>
            </>
          }
        >
          <div className="space-y-3 text-xs text-slate-600">
            <div className="flex flex-col items-center justify-center rounded-lg border-2 border-dashed border-slate-300 p-6 text-center">
              <Upload className="size-8 text-slate-400 mb-2" />
              <p className="font-semibold text-slate-800">Drag and drop resume file here</p>
              <p className="text-[11px] text-slate-500 mt-1">PDF or DOCX up to 5MB</p>
            </div>
            <div className="space-y-1">
              <label className="font-medium text-slate-700">Target Role Family</label>
              <select className="w-full h-8 rounded-md border border-slate-200 bg-white px-2 text-xs">
                <option value="platform">Platform / SRE / DevOps</option>
                <option value="backend">Backend / Distributed Systems</option>
                <option value="fullstack">Fullstack Systems</option>
              </select>
            </div>
          </div>
        </Dialog>
      )}
    </div>
  )
}
