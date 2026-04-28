import { ReactNode } from 'react';
import ThemeToggle from './ThemeToggle';
import LogoutButton from './LogoutButton';

type UserProp = {
  display_name?: string;
  subtitle?: string;
  is_verified?: boolean;
};

export default function Layout({ children, user }: { children: ReactNode; user?: UserProp }) {
  const displayName = user?.display_name || null;
  const subtitle = user?.subtitle || null;

  return (
    <div className="min-h-screen bg-background text-foreground">
      <nav className="bg-surface shadow border-b border-primary/20">
        <div className="max-w-7xl mx-auto px-4 py-4 flex justify-between items-center">
          <a href="/" className="text-2xl font-bold text-foreground hover:opacity-80 transition-opacity">
            Volunteer Platform
          </a>
          
          {user && displayName && (
            <div className="flex flex-col items-center mx-4">
              <div className="flex items-center gap-2">
                <span className="font-semibold text-lg">{displayName}</span>
                {user?.is_verified === false && (
                  <div className="group relative flex items-center justify-center w-5 h-5 rounded-full bg-gray-200 text-gray-600 text-xs font-bold cursor-help">
                    ?
                    <span className="absolute bottom-full mb-2 hidden group-hover:block w-max bg-gray-800 text-white text-xs rounded py-1 px-2">
                      Unverified account
                    </span>
                  </div>
                )}
              </div>
              <span className="text-xs text-gray-500">{subtitle}</span>
            </div>
          )}

          <div className="flex items-center gap-3">
            <LogoutButton />
            <ThemeToggle />
          </div>
        </div>
      </nav>
      <main className="max-w-7xl mx-auto px-4 py-8">{children}</main>
    </div>
  );
}
