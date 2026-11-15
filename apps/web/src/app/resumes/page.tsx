"use client"

import * as React from "react"
import { FileText, Upload, Download, CheckCircle2 } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { PageHeader } from "@/components/ui/page-header"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

export default function ResumesPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Resume Management"
        description="Versioned resumes with SHA-256 duplicate detection and role family classification."
        breadcrumbs={[
          { label: "Overview", href: "/" },
          { label: "Resumes" },
        ]}
        actions={
          <Button variant="default" size="sm" className="gap-1.5 bg-blue-600 hover:bg-blue-700">
            <Upload className="size-4" />
            <span>Upload Resume</span>
          </Button>
        }
      />

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Filename & Hash</TableHead>
            <TableHead>Role Family</TableHead>
            <TableHead>Version</TableHead>
            <TableHead>File Type</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Upload Date</TableHead>
            <TableHead className="text-right">Action</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {[
            {
              name: "Jane_Doe_Platform_SRE_2026.pdf",
              hash: "e3b0c442...98b7",
              roleFamily: "platform",
              version: "v2.1",
              type: "PDF",
              active: true,
              uploadedAt: "2 days ago",
            },
            {
              name: "Jane_Doe_Backend_Distributed_2026.pdf",
              hash: "8f4b231a...44cd",
              roleFamily: "backend",
              version: "v2.0",
              type: "PDF",
              active: false,
              uploadedAt: "1 week ago",
            },
            {
              name: "Jane_Doe_Fullstack_General.pdf",
              hash: "12fa998c...77ea",
              roleFamily: "fullstack",
              version: "v1.4",
              type: "PDF",
              active: false,
              uploadedAt: "3 weeks ago",
            },
          ].map((r) => (
            <TableRow key={r.name}>
              <TableCell>
                <div className="font-semibold text-slate-900 text-xs flex items-center gap-1.5">
                  <FileText className="size-4 text-blue-600 shrink-0" />
                  <span>{r.name}</span>
                </div>
                <div className="font-mono text-[10px] text-slate-400 mt-0.5">
                  SHA-256: {r.hash}
                </div>
              </TableCell>
              <TableCell>
                <Badge variant="secondary" className="capitalize">
                  {r.roleFamily}
                </Badge>
              </TableCell>
              <TableCell>
                <span className="font-mono text-xs font-semibold text-slate-700">
                  {r.version}
                </span>
              </TableCell>
              <TableCell className="text-xs text-slate-600">{r.type}</TableCell>
              <TableCell>
                {r.active ? (
                  <Badge variant="success" className="gap-1">
                    <CheckCircle2 className="size-3" />
                    <span>Active</span>
                  </Badge>
                ) : (
                  <Badge variant="outline">Standby</Badge>
                )}
              </TableCell>
              <TableCell className="text-xs text-slate-500">
                {r.uploadedAt}
              </TableCell>
              <TableCell className="text-right">
                <Button variant="outline" size="xs" className="gap-1">
                  <Download className="size-3" />
                  <span>Download</span>
                </Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
