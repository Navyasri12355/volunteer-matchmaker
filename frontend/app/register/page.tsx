'use client';

import { useState } from 'react';
import Layout from '@/components/Layout';
import { apiClient } from '@/lib/api';
import { auth } from '@/lib/firebase';
import { createUserWithEmailAndPassword, sendEmailVerification } from 'firebase/auth';

export default function Register() {
  const [role, setRole] = useState('volunteer');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [orgName, setOrgName] = useState('');
  const [error, setError] = useState('');

  const handleRegister = async () => {
    try {
      const firebaseUserCredential = await createUserWithEmailAndPassword(auth, email, password);

      if (role === 'ngo') {
        await apiClient.registerNGO({
          email,
          password,
          org_name: orgName,
          org_registration_number: '',
          allowed_categories: [],
        });
      } else {
        await apiClient.registerVolunteer({
          email,
          password,
          full_name: fullName,
        });
      }

      await sendEmailVerification(firebaseUserCredential.user);
      await auth.signOut();

      window.location.href = '/login';
    } catch (err: any) {
      const resp = err.response?.data;
      let message = 'Registration failed';
      if (resp) {
        if (typeof resp.detail === 'string') message = resp.detail;
        else if (Array.isArray(resp.detail)) message = resp.detail.map((d:any) => (d.msg || JSON.stringify(d))).join('; ');
        else message = JSON.stringify(resp);
      }
      if (!resp && err?.code === 'auth/email-already-in-use') {
        message = 'This email is already registered in Firebase';
      }
      setError(message);
    }
  };

  return (
    <Layout>
      <div className="max-w-md mx-auto bg-white p-8 rounded-lg shadow">
        <h2 className="text-2xl font-bold mb-4">Register</h2>
        {error && <p className="text-red-600 mb-4">{error}</p>}

        <div className="mb-4">
          <label className="block mb-2">Role</label>
          <select
            value={role}
            onChange={(e) => setRole(e.target.value)}
            className="w-full p-2 border rounded"
          >
            <option value="volunteer">Volunteer</option>
            <option value="ngo">NGO Manager</option>
          </select>
        </div>

        <input
          type="email"
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="w-full p-2 border rounded mb-4"
        />
        <input
          type="password"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="w-full p-2 border rounded mb-4"
        />

        {role === 'volunteer' ? (
          <input
            type="text"
            placeholder="Full Name"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            className="w-full p-2 border rounded mb-4"
          />
        ) : (
          <input
            type="text"
            placeholder="Organization Name"
            value={orgName}
            onChange={(e) => setOrgName(e.target.value)}
            className="w-full p-2 border rounded mb-4"
          />
        )}

        <button
          onClick={handleRegister}
          className="w-full bg-blue-600 text-white p-2 rounded hover:bg-blue-700"
        >
          Register
        </button>
        <p className="text-center mt-4">
          Already have an account? <a href="/login" className="text-blue-600">Login</a>
        </p>
      </div>
    </Layout>
  );
}
