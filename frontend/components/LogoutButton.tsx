"use client";

import { useEffect, useState } from 'react';

export default function LogoutButton() {
  const [isLoggedIn, setIsLoggedIn] = useState(false);

  useEffect(() => {
    setIsLoggedIn(Boolean(localStorage.getItem('authToken')));
  }, []);

  const handleLogout = () => {
    localStorage.removeItem('authToken');
    localStorage.removeItem('userRole');
    localStorage.removeItem('userId');
    localStorage.removeItem('firebaseEmailVerified');
    window.location.href = '/';
  };

  if (!isLoggedIn) return null;

  return (
    <button
      onClick={handleLogout}
      className="px-3 py-2 rounded border border-primary text-sm bg-surface hover:opacity-90 transition-opacity"
      aria-label="Log out"
    >
      Logout
    </button>
  );
}
