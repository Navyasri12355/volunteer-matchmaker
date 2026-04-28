'use client';

import { useEffect, useMemo, useState } from 'react';
import Layout from '@/components/Layout';
import { apiClient } from '@/lib/api';

function isAllowedFile(file: File) {
  const name = file.name.toLowerCase();
  return name.endsWith('.pdf') || name.endsWith('.docx');
}

function DownloadIcon() {
  return (
    <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M10 3v8" />
      <path d="M6.5 8.5 10 12l3.5-3.5" />
      <path d="M4 15.5h12" />
    </svg>
  );
}

function TrashIcon() {
  return (
    <svg viewBox="0 0 20 20" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M4 6h12" />
      <path d="M8 6V4.8A.8.8 0 0 1 8.8 4h2.4a.8.8 0 0 1 .8.8V6" />
      <path d="M6.5 6l.6 9a1 1 0 0 0 1 .9h3.8a1 1 0 0 0 1-.9l.6-9" />
      <path d="M8.5 9v4" />
      <path d="M11.5 9v4" />
    </svg>
  );
}

export default function Dashboard() {
  const [role, setRole] = useState('');
  const [user, setUser] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [isVerified, setIsVerified] = useState(true);

  const [skillKey, setSkillKey] = useState('first_aid');
  const [volunteerFile, setVolunteerFile] = useState<File | null>(null);
  const [ngoFile, setNgoFile] = useState<File | null>(null);
  const [uploadMessage, setUploadMessage] = useState('');
  const [uploadPipeline, setUploadPipeline] = useState<any>(null);

  const [documents, setDocuments] = useState<any[]>([]);
  const [loadingDocuments, setLoadingDocuments] = useState(false);

  const isNgoManager = role === 'ngo_manager';
  const isVolunteer = role === 'volunteer';

  useEffect(() => {
    const token = localStorage.getItem('authToken');
    if (!token) {
      window.location.href = '/login';
      return;
    }

    apiClient.setAuthToken(token);
    const storedRole = localStorage.getItem('userRole') || '';
    setIsVerified(localStorage.getItem('firebaseEmailVerified') === 'true');
    setRole(storedRole);
    loadUserProfile(storedRole);
  }, []);

  const loadUserProfile = async (currentRole: string) => {
    try {
      if (currentRole === 'ngo_manager') {
        const response = await apiClient.getNGOProfile();
        setUser(response.data);
      } else {
        const response = await apiClient.getVolunteerProfile();
        setUser(response.data);
      }
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  };

  const loadDocuments = async () => {
    try {
      setLoadingDocuments(true);
      if (isNgoManager && user?.ngo_id) {
        const response = await apiClient.listNGODocuments(user.ngo_id);
        setDocuments(response?.data?.documents || []);
      } else if (isVolunteer) {
        const response = await apiClient.listVolunteerDocuments();
        setDocuments(response?.data?.documents || []);
      } else {
        setDocuments([]);
      }
    } catch {
      setDocuments([]);
    } finally {
      setLoadingDocuments(false);
    }
  };

  useEffect(() => {
    if (!loading && user) {
      loadDocuments();
    }
  }, [loading, user]);

  const identity = useMemo(() => {
    if (!user) return undefined;
    if (isNgoManager) {
      return {
        display_name: user.org_name || user.email || 'NGO Manager',
        subtitle: user.org_name || 'NGO',
        is_verified: isVerified,
      };
    }
    return {
      display_name: user.full_name || user.email || 'Volunteer',
      subtitle: 'Volunteer',
      is_verified: isVerified,
    };
  }, [user, isNgoManager, isVerified]);

  const handleUpload = async () => {
    try {
      setUploadMessage('');
      setUploadPipeline(null);
      if (isNgoManager) {
        if (!ngoFile) {
          setUploadMessage('Please choose a file.');
          return;
        }
        if (!isAllowedFile(ngoFile)) {
          setUploadMessage('Only PDF and DOCX files are allowed.');
          return;
        }
        const response = await apiClient.uploadNGODocuments(user.ngo_id, [ngoFile]);
        setNgoFile(null);
        const pipeline = response?.data?.pipeline || null;
        setUploadPipeline({
          title: 'NGO document pipeline',
          message: response?.data?.message || 'NGO document uploaded successfully.',
          count: response?.data?.count,
          pipeline,
        });
        setUploadMessage(response?.data?.message || 'NGO document uploaded successfully.');
      } else {
        if (!volunteerFile) {
          setUploadMessage('Please choose a file.');
          return;
        }
        if (!skillKey.trim()) {
          setUploadMessage('Please provide a skill key.');
          return;
        }
        if (!isAllowedFile(volunteerFile)) {
          setUploadMessage('Only PDF and DOCX files are allowed.');
          return;
        }
        const response = await apiClient.uploadVolunteerCertificate(skillKey.trim(), volunteerFile);
        setVolunteerFile(null);
        const pipeline = response?.data?.pipeline || null;
        setUploadPipeline({
          title: 'Volunteer certificate pipeline',
          message: response?.data?.message || 'Volunteer document uploaded successfully.',
          certificate: response?.data?.certificate || null,
          pipeline,
        });
        setUploadMessage(response?.data?.message || 'Volunteer document uploaded successfully.');
      }
      await loadDocuments();
    } catch (error: any) {
      const detail = error?.response?.data?.detail;
      setUploadMessage(typeof detail === 'string' ? detail : 'Upload failed.');
    }
  };

  const downloadDocument = async (doc: any) => {
    try {
      const response = isNgoManager
        ? await apiClient.downloadNGODocument(doc.document_id)
        : await apiClient.downloadVolunteerDocument(doc.document_id);
      const blob = new Blob([response.data], { type: doc.content_type || 'application/octet-stream' });
      const url = window.URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = doc.file_name || 'document';
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.URL.revokeObjectURL(url);
    } catch {
      setUploadMessage('Download failed.');
    }
  };

  const deleteDocument = async (doc: any) => {
    try {
      await (isNgoManager
        ? apiClient.deleteNGODocument(doc.document_id)
        : apiClient.deleteVolunteerDocument(doc.document_id));
      setUploadMessage('Document deleted successfully.');
      await loadDocuments();
    } catch {
      setUploadMessage('Delete failed.');
    }
  };

  const renderPipelineSection = () => {
    if (!uploadPipeline) return null;
    const pipeline = uploadPipeline.pipeline || {};
    const stages = pipeline.stage_status || {};
    const details = { ...pipeline };

    return (
      <div className="bg-slate-950 text-slate-100 p-5 rounded-lg shadow border border-slate-800 mt-4">
        <div className="flex items-start justify-between gap-4 mb-4">
          <div>
            <h3 className="text-lg font-semibold">{uploadPipeline.title}</h3>
            <p className="text-sm text-slate-300 mt-1">{uploadPipeline.message}</p>
          </div>
          {typeof uploadPipeline.count === 'number' ? (
            <div className="rounded-full bg-slate-800 px-3 py-1 text-xs text-slate-200">
              {uploadPipeline.count} file{uploadPipeline.count === 1 ? '' : 's'}
            </div>
          ) : null}
        </div>

        {uploadPipeline.certificate ? (
          <div className="mb-4 rounded border border-slate-800 bg-slate-900 p-3">
            <h4 className="text-sm font-semibold mb-2">Certificate Result</h4>
            <pre className="whitespace-pre-wrap break-words text-xs text-slate-200">{JSON.stringify(uploadPipeline.certificate, null, 2)}</pre>
          </div>
        ) : null}

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
          {Object.entries(stages).map(([stage, value]) => (
            <div key={stage} className="rounded border border-slate-800 bg-slate-900 p-3">
              <p className="text-[11px] uppercase tracking-wide text-slate-400">{stage}</p>
              <p className="text-sm font-medium text-slate-100 break-words">{String(value)}</p>
            </div>
          ))}
        </div>

        <div className="rounded border border-slate-800 bg-slate-900 p-3">
          <h4 className="text-sm font-semibold mb-2">Full Pipeline Payload</h4>
          <pre className="max-h-96 overflow-auto whitespace-pre-wrap break-words text-xs text-slate-200">
            {JSON.stringify(details, null, 2)}
          </pre>
        </div>
      </div>
    );
  };

  if (loading) return <div>Loading...</div>;

  return (
    <Layout user={identity}>
      <h1 className="text-3xl font-bold mb-6">Dashboard</h1>
      {!user ? <p>Unable to load profile data.</p> : null}

      {user ? (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="bg-white p-6 rounded-lg shadow border">
            <h2 className="text-xl font-bold mb-3">{isNgoManager ? 'NGO Manager View' : 'Volunteer View'}</h2>
            <p className="text-sm text-gray-700 mb-2">Email: {user.email}</p>
            {isNgoManager ? (
              <>
                <p className="text-sm text-gray-700 mb-1">Organization: {user.org_name}</p>
                <p className="text-sm text-gray-700 mb-1">Trust Score: {user.trust_score}</p>
                <a href="/events" className="inline-block mt-3 px-4 py-2 rounded bg-blue-600 text-white text-sm">
                  Manage Events
                </a>
              </>
            ) : (
              <>
                <p className="text-sm text-gray-700 mb-1">Name: {user.full_name}</p>
                <p className="text-sm text-gray-700 mb-1">Points: {user.total_points}</p>
                <p className="text-sm text-gray-700 mb-1">Reliability: {user.reliability_score}</p>
                <a href="/events" className="inline-block mt-3 px-4 py-2 rounded bg-blue-600 text-white text-sm">
                  Find Events
                </a>
              </>
            )}
          </div>

          <div className="bg-white p-6 rounded-lg shadow border">
            <h2 className="text-xl font-bold mb-3">Upload Documents</h2>
            <p className="text-sm text-gray-600 mb-3">Allowed file types: PDF, DOCX</p>

            {isVolunteer ? (
              <input
                type="text"
                value={skillKey}
                onChange={(e) => setSkillKey(e.target.value)}
                className="w-full p-2 border rounded mb-3"
                placeholder="Skill key (example: first_aid)"
              />
            ) : null}

            <input
              type="file"
              accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
              onChange={(e) => {
                const selected = e.target.files?.[0] || null;
                if (isNgoManager) setNgoFile(selected);
                else setVolunteerFile(selected);
              }}
              className="w-full p-2 border rounded mb-3"
            />

            <button onClick={handleUpload} className="px-4 py-2 rounded bg-gray-900 text-white text-sm">
              Upload
            </button>
            {uploadMessage ? <p className="text-sm mt-2">{uploadMessage}</p> : null}
            {renderPipelineSection()}
          </div>
        </div>
      ) : null}

      <div className="bg-white p-6 rounded-lg shadow border mt-6">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-xl font-bold">Uploaded Documents</h2>
          <button onClick={loadDocuments} className="px-3 py-1 border rounded text-sm">Refresh</button>
        </div>
        {loadingDocuments ? <p className="text-sm text-gray-600">Loading...</p> : null}
        {!loadingDocuments && documents.length === 0 ? (
          <p className="text-sm text-gray-600">No uploaded documents yet.</p>
        ) : null}
        <ul className="space-y-2">
          {documents.map((doc) => (
            <li key={doc.document_id} className="flex items-center justify-between border rounded p-2">
              <div>
                <p className="text-sm font-medium">{doc.file_name}</p>
                <p className="text-xs text-gray-600">{doc.content_type} • {doc.size_bytes} bytes</p>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => downloadDocument(doc)}
                  className="inline-flex items-center justify-center rounded bg-gray-800 p-2 text-white"
                  aria-label={`Download ${doc.file_name}`}
                  title="Download"
                >
                  <DownloadIcon />
                </button>
                <button
                  onClick={() => deleteDocument(doc)}
                  className="inline-flex items-center justify-center rounded border border-red-200 bg-red-50 p-2 text-red-600 hover:bg-red-100"
                  aria-label={`Delete ${doc.file_name}`}
                  title="Delete"
                >
                  <TrashIcon />
                </button>
              </div>
            </li>
          ))}
        </ul>
      </div>
    </Layout>
  );
}
