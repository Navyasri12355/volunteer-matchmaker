import { ReactNode } from 'react';

export default function Navbar() {
  return (
    <nav className="bg-white shadow-md">
      <div className="max-w-7xl mx-auto px-4 py-4 flex justify-between items-center">
        <div className="text-2xl font-bold text-blue-600">NGO Volunteer Platform</div>
        <div className="space-x-4">
          <a href="/events" className="text-gray-600 hover:text-gray-900">
            Events
          </a>
          <a href="/profile" className="text-gray-600 hover:text-gray-900">
            Profile
          </a>
          <a href="/logout" className="text-gray-600 hover:text-gray-900">
            Logout
          </a>
        </div>
      </div>
    </nav>
  );
}
