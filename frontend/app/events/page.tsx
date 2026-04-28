'use client';

import { useEffect, useState } from 'react';
import Layout from '@/components/Layout';
import EventCard from '@/components/EventCard';
import MapView from '@/components/MapView';
import { apiClient } from '@/lib/api';

export default function Events() {
  const [events, setEvents] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({ category: '', band: '' });
  const [eventIdForUpload, setEventIdForUpload] = useState('');
  const [uploadFiles, setUploadFiles] = useState<File[]>([]);
  const [uploadMessage, setUploadMessage] = useState('');
  const [eventDocuments, setEventDocuments] = useState<any[]>([]);
  const [loadingDocs, setLoadingDocs] = useState(false);
  const [isNgoManager, setIsNgoManager] = useState(false);

  useEffect(() => {
    setIsNgoManager(localStorage.getItem('userRole') === 'ngo_manager');
    loadEvents();
  }, [filters]);

  const loadEvents = async () => {
    try {
      const response = await apiClient.listEvents(filters);
      setEvents(response.data.events || []);
    } catch (error) {
      console.error('Failed to load events:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleUpload = async () => {
    try {
      setUploadMessage('');
      const token = localStorage.getItem('authToken');
      if (!token) {
        setUploadMessage('Please login first');
        return;
      }
      if (!eventIdForUpload.trim()) {
        setUploadMessage('Please provide an event ID');
        return;
      }
      if (!uploadFiles.length) {
        setUploadMessage('Please select at least one file');
        return;
      }

      const invalid = uploadFiles.find((f) => {
        const name = f.name.toLowerCase();
        return !(name.endsWith('.pdf') || name.endsWith('.docx'));
      });
      if (invalid) {
        setUploadMessage('Only PDF and DOCX files are allowed');
        return;
      }

      apiClient.setAuthToken(token);
      const response = await apiClient.uploadEventDocuments(eventIdForUpload.trim(), uploadFiles);
      const count = response?.data?.uploaded_documents?.length || 0;
      setUploadMessage(`Uploaded ${count} document(s) successfully`);
      setUploadFiles([]);
      await loadEventDocuments();
    } catch (error: any) {
      const detail = error?.response?.data?.detail;
      if (typeof detail === 'string') setUploadMessage(detail);
      else setUploadMessage('Upload failed');
    }
  };

  const loadEventDocuments = async () => {
    try {
      setLoadingDocs(true);
      const token = localStorage.getItem('authToken');
      if (!token || !eventIdForUpload.trim()) {
        setEventDocuments([]);
        return;
      }
      apiClient.setAuthToken(token);
      const response = await apiClient.listEventDocuments(eventIdForUpload.trim());
      setEventDocuments(response?.data?.documents || []);
    } catch (error) {
      console.error('Failed to load event documents:', error);
      setEventDocuments([]);
    } finally {
      setLoadingDocs(false);
    }
  };

  const downloadEventDocument = async (doc: any) => {
    try {
      const token = localStorage.getItem('authToken');
      if (!token) return;
      apiClient.setAuthToken(token);
      const response = await apiClient.downloadEventDocument(doc.document_id);
      const blob = new Blob([response.data], { type: doc.content_type || 'application/octet-stream' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = doc.file_name || 'document';
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Failed to download event document:', error);
    }
  };

  if (loading) return <div>Loading events...</div>;

  return (
    <Layout>
      <h1 className="text-3xl font-bold mb-6">Community Needs & Opportunities</h1>

      <MapView events={events} />

      <div className="my-6 flex gap-4">
        <input
          type="text"
          placeholder="Filter by category"
          value={filters.category}
          onChange={(e) => setFilters({ ...filters, category: e.target.value })}
          className="p-2 border rounded"
        />
        <select
          value={filters.band}
          onChange={(e) => setFilters({ ...filters, band: e.target.value })}
          className="p-2 border rounded"
        >
          <option value="">All Severity Levels</option>
          <option value="CRITICAL">Critical</option>
          <option value="MODERATE">Moderate</option>
          <option value="LOW">Low</option>
        </select>
      </div>

      {isNgoManager && <div className="bg-white p-4 rounded border mb-6">
        <h2 className="text-xl font-semibold mb-3">NGO: Upload Event Documents</h2>
        <p className="text-sm text-gray-600 mb-3">Allowed file types: PDF, DOCX</p>
        <div className="grid gap-3 md:grid-cols-3">
          <input
            type="text"
            placeholder="Event ID (e.g. evt_123)"
            value={eventIdForUpload}
            onChange={(e) => setEventIdForUpload(e.target.value)}
            className="p-2 border rounded"
          />
          <input
            type="file"
            accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            multiple
            onChange={(e) => setUploadFiles(Array.from(e.target.files || []))}
            className="p-2 border rounded"
          />
          <button onClick={handleUpload} className="bg-blue-600 text-white rounded px-4 py-2">
            Upload
          </button>
        </div>
        <div className="mt-3">
          <button onClick={loadEventDocuments} className="text-sm px-3 py-1 border rounded">
            Refresh Document List
          </button>
        </div>
        {uploadMessage && <p className="mt-3 text-sm">{uploadMessage}</p>}
        <div className="mt-4">
          <h3 className="font-semibold mb-2">Uploaded Documents</h3>
          {loadingDocs ? <p className="text-sm text-gray-600">Loading...</p> : null}
          {!loadingDocs && eventDocuments.length === 0 ? <p className="text-sm text-gray-600">No documents found for this event.</p> : null}
          <ul className="space-y-2">
            {eventDocuments.map((doc) => (
              <li key={doc.document_id} className="flex items-center justify-between border rounded p-2">
                <div>
                  <p className="text-sm font-medium">{doc.file_name}</p>
                  <p className="text-xs text-gray-600">{doc.content_type} • {doc.size_bytes} bytes</p>
                </div>
                <button
                  onClick={() => downloadEventDocument(doc)}
                  className="text-sm px-3 py-1 bg-gray-800 text-white rounded"
                >
                  Download
                </button>
              </li>
            ))}
          </ul>
        </div>
      </div>}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {events.map((event) => (
          <EventCard key={event.event_id} event={event} />
        ))}
      </div>
    </Layout>
  );
}
