'use client';

import React from 'react';
import Link from 'next/link';
import { useAuth } from '@/contexts/AuthContext';

export function AuthHeader() {
  const { user, isLoggedIn, isLoading, logout } = useAuth();

  if (isLoading) {
    return (
      <div className="h-16 w-full border-b border-neutral-800 bg-black/50 backdrop-blur-sm flex items-center px-4">
        <div className="ml-auto h-8 w-24 bg-neutral-800 rounded animate-pulse" />
      </div>
    );
  }

  return (
    <div className="h-16 w-full border-b border-neutral-800 bg-black/50 backdrop-blur-sm flex items-center justify-between px-4 sticky top-0 z-40">
      <Link href="/" className="text-lg font-semibold text-white hover:text-neutral-300">
        Into The Repo
      </Link>

      <div className="flex items-center gap-4">
        {isLoggedIn && user ? (
          <>
            <div className="text-sm text-neutral-400">
              <p className="font-medium text-white">{user.username}</p>
              <p className="text-xs">{user.email}</p>
            </div>
            <div className="h-8 w-8 rounded-full bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center">
              <span className="text-white text-xs font-semibold">
                {user.username.charAt(0).toUpperCase()}
              </span>
            </div>
            <button
              onClick={logout}
              className="text-sm px-3 py-1 text-neutral-400 hover:text-white transition"
            >
              Logout
            </button>
            <Link
              href="/analyze/history"
              className="text-sm px-3 py-1.5 rounded bg-neutral-800 text-white hover:bg-neutral-700 transition"
            >
              History
            </Link>
          </>
        ) : (
          <>
            <Link
              href="/auth/login"
              className="text-sm px-4 py-1.5 rounded bg-neutral-800 text-white hover:bg-neutral-700 transition"
            >
              Sign in
            </Link>
            <Link
              href="/auth/signup"
              className="text-sm px-4 py-1.5 rounded bg-gradient-to-r from-purple-600 to-pink-600 text-white hover:from-purple-700 hover:to-pink-700 transition"
            >
              Sign up
            </Link>
          </>
        )}
      </div>
    </div>
  );
}
