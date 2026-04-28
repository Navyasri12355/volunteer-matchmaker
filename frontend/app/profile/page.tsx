'use client';

import { useEffect, useState } from 'react';
import Layout from '@/components/Layout';
import { apiClient } from '@/lib/api';

export default function Profile() {
  const [profile, setProfile] = useState<any>(null);
  const [isVolunteer, setIsVolunteer] = useState(true);
  const [skillKey, setSkillKey] = useState('first_aid');
  const [certificateFile, setCertificateFile] = useState<File | null>(null);
  const [uploadStatus, setUploadStatus] = useState('');
  const [documents, setDocuments] = useState<any[]>([]);
  const [loadingDocuments, setLoadingDocuments] = useState(false);

  useEffect(() => {
    const token = localStorage.getItem('authToken');
    if (!token) {
      window.location.href = '/login';
      return;
    }

    apiClient.setAuthToken(token);

    loadProfile();
  }, []);

  const loadProfile = async () => {
    const role = localStorage.getItem('userRole');
    try {
      if (role === 'ngo_manager') {
        const response = await apiClient.getNGOProfile();
        setProfile(response.data);
        setIsVolunteer(false);
      } else if (role === 'volunteer') {
        const response = await apiClient.getVolunteerProfile();
        setProfile(response.data);
        setIsVolunteer(true);
        await loadVolunteerDocuments();
      } else {
        // Fallback for older sessions without stored role.
        const response = await apiClient.getVolunteerProfile();
        setProfile(response.data);
        setIsVolunteer(true);
        await loadVolunteerDocuments();
      }
    } catch {
      setProfile(null);
    }
  };

  const handleCertificateUpload = async () => {
    try {
      setUploadStatus('');
      const token = localStorage.getItem('authToken');
      if (!token) {
        setUploadStatus('Please login first');
        return;
      }
      if (!certificateFile) {
        setUploadStatus('Please choose a file');
        return;
      }

      const name = certificateFile.name.toLowerCase();
      if (!(name.endsWith('.pdf') || name.endsWith('.docx'))) {
        setUploadStatus('Only PDF and DOCX files are allowed');
        return;
      }

      apiClient.setAuthToken(token);
      await apiClient.uploadVolunteerCertificate(skillKey, certificateFile);
      setUploadStatus('Certificate uploaded successfully (pending review)');
      setCertificateFile(null);
      await loadVolunteerDocuments();
    } catch (error: any) {
      const detail = error?.response?.data?.detail;
      if (typeof detail === 'string') setUploadStatus(detail);
      else setUploadStatus('Certificate upload failed');
    }
  };

  const loadVolunteerDocuments = async () => {
    try {
      setLoadingDocuments(true);
      const response = await apiClient.listVolunteerDocuments();
      setDocuments(response?.data?.documents || []);
    } catch {
      setDocuments([]);
    } finally {
      setLoadingDocuments(false);
    }
  };

  const downloadVolunteerDocument = async (doc: any) => {
    try {
      const response = await apiClient.downloadVolunteerDocument(doc.document_id);
      const blob = new Blob([response.data], { type: doc.content_type || 'application/octet-stream' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = doc.file_name || 'certificate';
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch {
      setUploadStatus('Failed to download certificate');
    }
  };

  return (
    <Layout>
      <h1 className="text-3xl font-bold mb-6">Profile</h1>
      {profile ? (
        <div className="bg-white p-8 rounded-lg shadow max-w-2xl">
          <h2 className="text-2xl font-bold mb-4">
            {isVolunteer ? profile.full_name : profile.org_name}
          </h2>
          <dl className="space-y-4">
            <div>
              <dt className="font-semibold">Email</dt>
              <dd className="text-gray-600">{profile.email}</dd>
            </div>
            {isVolunteer ? (
              <>
                <div>
                  <dt className="font-semibold">Points</dt>
                  <dd className="text-gray-600">{profile.total_points}</dd>
                </div>
                <div>
                  <dt className="font-semibold">Reliability</dt>
                  <dd className="text-gray-600">{(profile.reliability_score * 100).toFixed(0)}%</dd>
                </div>
                <div>
                  <dt className="font-semibold">Skills</dt>
                  <dd className="text-gray-600">{profile.skills?.join(', ') || 'None'}</dd>
                </div>
                <div className="pt-3 border-t">
                  <dt className="font-semibold mb-2">Upload Skill Certificate</dt>
                  <div className="grid gap-2 md:grid-cols-3">
                    <input
                      type="text"
                      value={skillKey}
                      onChange={(e) => setSkillKey(e.target.value)}
                      className="p-2 border rounded"
                      placeholder="Skill key (e.g. first_aid)"
                    />
                    <input
                      type="file"
                      accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                      onChange={(e) => setCertificateFile(e.target.files?.[0] || null)}
                      className="p-2 border rounded"
                    />
                    <button
                      onClick={handleCertificateUpload}
                      className="bg-blue-600 text-white rounded px-4 py-2"
                    >
                      Upload Certificate
                    </button>
                  </div>
                  {uploadStatus && <p className="text-sm text-gray-700 mt-2">{uploadStatus}</p>}
                  <div className="mt-4">
                    <div className="flex items-center justify-between mb-2">
                      <p className="font-semibold">My Uploaded Certificates</p>
                      <button onClick={loadVolunteerDocuments} className="text-sm px-3 py-1 border rounded">
                        Refresh
                      </button>
                    </div>
                    {loadingDocuments ? <p className="text-sm text-gray-600">Loading...</p> : null}
                    {!loadingDocuments && documents.length === 0 ? <p className="text-sm text-gray-600">No uploaded certificates yet.</p> : null}
                    <ul className="space-y-2">
                      {documents.map((doc) => (
                        <li key={doc.document_id} className="flex items-center justify-between border rounded p-2">
                          <div>
                            <p className="text-sm font-medium">{doc.file_name}</p>
                            <p className="text-xs text-gray-600">{doc.skill_key || 'unknown skill'} • {doc.status || 'pending_review'}</p>
                          </div>
                          <button
                            onClick={() => downloadVolunteerDocument(doc)}
                            className="text-sm px-3 py-1 bg-gray-800 text-white rounded"
                          >
                            Download
                          </button>
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              </>
            ) : (
              <>
                <div>
                  <dt className="font-semibold">Registration Number</dt>
                  <dd className="text-gray-600">{profile.org_registration_number}</dd>
                </div>
                <div>
                  <dt className="font-semibold">Trust Score</dt>
                  <dd className="text-gray-600">{(profile.trust_score * 100).toFixed(0)}%</dd>
                </div>
                <div>
                  <dt className="font-semibold">Verified</dt>
                  <dd className="text-gray-600">{profile.is_verified ? 'Yes' : 'No'}</dd>
                </div>
              </>
            )}
          </dl>
        </div>
      ) : (
        <p>Failed to load profile</p>
      )}
    </Layout>
  );
}
