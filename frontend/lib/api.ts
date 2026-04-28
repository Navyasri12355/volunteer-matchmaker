
import axios, { AxiosInstance } from 'axios';

class APIClient {
  client: AxiosInstance;

  constructor(baseURL: string = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000') {
    this.client = axios.create({
      baseURL,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    this.client.interceptors.request.use((config) => {
      if (typeof window !== 'undefined') {
        const token = localStorage.getItem('authToken');
        if (token) {
          config.headers = config.headers || {};
          config.headers['Authorization'] = `Bearer ${token}`;
        }
      }
      return config;
    });
  }

  setAuthToken(token: string) {
    if (typeof window !== 'undefined') {
      localStorage.setItem('authToken', token);
    }
    this.client.defaults.headers.common['Authorization'] = `Bearer ${token}`;
  }

  async registerNGO(data: any) {
    return this.client.post('/auth/register/ngo', data);
  }

  async registerVolunteer(data: any) {
    return this.client.post('/auth/register/volunteer', data);
  }

  async login(email: string, password: string) {
    return this.client.post('/auth/login', { email, password });
  }

  async getNGOProfile() {
    return this.client.get('/ngo/me');
  }

  async uploadNGODocuments(ngoId: string, files: File[]) {
    const formData = new FormData();
    files.forEach((file) => formData.append('files[]', file));
    return this.client.post(`/ngo/${ngoId}/documents`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  }

  async listNGODocuments(ngoId: string) {
    return this.client.get(`/ngo/${ngoId}/documents`);
  }

  async downloadNGODocument(documentId: string) {
    return this.client.get(`/ngo/documents/${documentId}/download`, { responseType: 'blob' });
  }

  async deleteNGODocument(documentId: string) {
    return this.client.delete(`/ngo/documents/${documentId}`);
  }

  async getVolunteerProfile() {
    return this.client.get('/volunteer/me');
  }

  async listEvents(params: any = {}) {
    return this.client.get('/events', { params });
  }

  async getEvent(eventId: string) {
    return this.client.get(`/events/${eventId}`);
  }

  async createEvent(data: any, files?: File[]) {
    const formData = new FormData();
    formData.append('data', JSON.stringify(data));
    if (files) {
      files.forEach((file) => formData.append('files[]', file));
    }
    return this.client.post('/events', formData, { headers: { 'Content-Type': 'multipart/form-data' } });
  }

  async uploadEventDocuments(eventId: string, files: File[]) {
    const formData = new FormData();
    files.forEach((file) => formData.append('files[]', file));
    return this.client.post(`/events/${eventId}/documents`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  }

  async listEventDocuments(eventId: string) {
    return this.client.get(`/events/${eventId}/documents`);
  }

  async downloadEventDocument(documentId: string) {
    return this.client.get(`/events/documents/${documentId}/download`, { responseType: 'blob' });
  }

  async uploadVolunteerCertificate(skillKey: string, file: File) {
    const formData = new FormData();
    formData.append('skill_key', skillKey);
    formData.append('file', file);
    return this.client.post('/volunteer/certificates', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  }

  async listVolunteerDocuments() {
    return this.client.get('/volunteer/documents');
  }

  async downloadVolunteerDocument(documentId: string) {
    return this.client.get(`/volunteer/documents/${documentId}/download`, { responseType: 'blob' });
  }

  async deleteVolunteerDocument(documentId: string) {
    return this.client.delete(`/volunteer/documents/${documentId}`);
  }

  async applyToEvent(eventId: string) {
    return this.client.post(`/assignments/${eventId}/apply`);
  }

  async confirmAssignment(assignmentId: string, accept: boolean) {
    return this.client.post(`/assignments/${assignmentId}/confirm`, { accept });
  }

  async submitNGOAudit(eventId: string, data: any) {
    return this.client.post(`/audit/${eventId}/ngo-feedback`, data);
  }

  async submitVolunteerReview(assignmentId: string, data: any) {
    return this.client.post(`/audit/${assignmentId}/volunteer-review`, data);
  }
}

export const apiClient = new APIClient();
