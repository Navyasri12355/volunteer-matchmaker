'use client';

import { useState } from 'react';
import Layout from '@/components/Layout';
import { apiClient } from '@/lib/api';
import { auth } from '@/lib/firebase';
import { signInWithEmailAndPassword, signOut } from 'firebase/auth';

export default function Login() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  const handleLogin = async () => {
    try {
      const firebaseUserCredential = await signInWithEmailAndPassword(auth, email, password);
      // if (!firebaseUserCredential.user.emailVerified) {
      //   await signOut(auth);
      //   setError('Please verify your email before logging in. Check your inbox for the verification link.');
      //   return;
      // }

      const response = await apiClient.login(email, password);
      const token = response?.data?.access_token;
      const role = response?.data?.role;
      if (!token) {
        setError('Login succeeded but no token was returned by the server');
        return;
      }
      apiClient.setAuthToken(token);
      if (role) {
        localStorage.setItem('userRole', role);
      }
      if (response?.data?.user_id) {
        localStorage.setItem('userId', response.data.user_id);
      }
      localStorage.setItem('firebaseEmailVerified', firebaseUserCredential.user.emailVerified ? 'true' : 'false');
      // Redirect to dashboard
      window.location.href = '/dashboard';
    } catch (err: any) {
      const resp = err.response?.data;
      let message = 'Login failed';
      if (resp) {
        if (typeof resp.detail === 'string') message = resp.detail;
        else if (Array.isArray(resp.detail)) message = resp.detail.map((d:any) => (d.msg || JSON.stringify(d))).join('; ');
        else message = JSON.stringify(resp);
      }
      if (!resp && err?.code === 'auth/invalid-credential') {
        message = 'Invalid email or password';
      }
      setError(message);
    }
  };

  return (
    <Layout>
      <div className="max-w-md mx-auto bg-white p-8 rounded-lg shadow">
        <h2 className="text-2xl font-bold mb-4">Login</h2>
        {error && <p className="text-red-600 mb-4">{error}</p>}
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
        <button
          onClick={handleLogin}
          className="w-full bg-blue-600 text-white p-2 rounded hover:bg-blue-700"
        >
          Login
        </button>
        <p className="text-center mt-4">
          Don't have an account? <a href="/register" className="text-blue-600">Register</a>
        </p>
      </div>
    </Layout>
  );
}
