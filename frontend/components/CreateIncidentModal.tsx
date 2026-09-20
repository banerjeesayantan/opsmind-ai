"use client";

import { FormEvent, useState } from "react";
import { Modal } from "./Modal";
import { Button, ErrorBanner, Input, Label, Select, Textarea } from "./ui";
import { incidentsApi } from "@/lib/incidents-api";
import { ApiError } from "@/lib/api-client";
import type { IncidentResponse, Severity } from "@/lib/types";

export function CreateIncidentModal({ onClose, onCreated }: { onClose: () => void; onCreated: (incident: IncidentResponse) => void }) {
  const [title, setTitle] = useState("");
  const [service, setService] = useState("");
  const [severity, setSeverity] = useState<Severity>("medium");
  const [description, setDescription] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const incident = await incidentsApi.create({ title, service, severity, description });
      onCreated(incident);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't create the incident. Try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Modal title="New incident" onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-4">
        {error && <ErrorBanner message={error} />}

        <div>
          <Label htmlFor="title">Title</Label>
          <Input
            id="title"
            required
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Checkout latency spike"
            autoFocus
          />
        </div>

        <div>
          <Label htmlFor="service">Service</Label>
          <Input
            id="service"
            required
            value={service}
            onChange={(e) => setService(e.target.value)}
            placeholder="checkout"
          />
        </div>

        <div>
          <Label htmlFor="severity">Severity</Label>
          <Select id="severity" value={severity} onChange={(e) => setSeverity(e.target.value as Severity)}>
            <option value="low">Low</option>
            <option value="medium">Medium</option>
            <option value="high">High</option>
            <option value="critical">Critical</option>
          </Select>
        </div>

        <div>
          <Label htmlFor="description">Description (optional)</Label>
          <Textarea
            id="description"
            rows={3}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="What did you observe?"
          />
        </div>

        <div className="flex justify-end gap-2 pt-1">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" variant="primary" loading={loading}>
            Create incident
          </Button>
        </div>
      </form>
    </Modal>
  );
}
