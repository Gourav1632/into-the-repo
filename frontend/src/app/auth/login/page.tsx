'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import axios from 'axios';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';
import { authLoginRoute } from '@/utils/APIRoutes';
import { setAuthToken } from '@/utils/auth';

const BottomGradient = () => {
  return (
    <>
      <span className="absolute inset-x-0 -bottom-px block h-px w-full bg-gradient-to-r from-transparent via-cyan-500 to-transparent opacity-0 transition duration-500 group-hover/btn:opacity-100" />
      <span className="absolute inset-x-10 -bottom-px mx-auto block h-px w-1/2 bg-gradient-to-r from-transparent via-indigo-500 to-transparent opacity-0 blur-sm transition duration-500 group-hover/btn:opacity-100" />
    </>
  );
};

const LabelInputContainer = ({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) => {
  return (
    <div className={cn('flex w-full flex-col space-y-2', className)}>
      {children}
    </div>
  );
};

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const router = useRouter();

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const response = await axios.post(authLoginRoute, { email, password });
      const token = response.data?.access_token;
      if (!token) {
        setError('Login failed. Please check your credentials.');
        return;
      }
      setAuthToken(token);
      router.push('/analyze/history');
    } catch (err) {
      console.error('Login failed:', err);
      if (axios.isAxiosError(err)) {
        setError(err.response?.data?.detail || 'Login failed. Please check your credentials.');
      } else {
        setError('Login failed. Please check your credentials.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen w-full flex items-center justify-center bg-white px-4 dark:bg-black">
      <div className="shadow-input mx-auto w-full max-w-md rounded-none bg-white p-4 md:rounded-2xl md:p-8 dark:bg-black">
        <h2 className="text-xl font-bold text-neutral-800 dark:text-neutral-200">
          Welcome back to Into The Repo
        </h2>
        <p className="mt-2 max-w-sm text-sm text-neutral-600 dark:text-neutral-300">
          Sign in to save your analysis history and continue where you left off.
          <br />
          <span className="text-xs mt-1 block">Tip: You can still use the app without logging in!</span>
        </p>

        <form className="my-8" onSubmit={handleSubmit}>
          <LabelInputContainer className="mb-4">
            <Label htmlFor="email">Email Address</Label>
            <Input
              id="email"
              placeholder="your@email.com"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </LabelInputContainer>

          <LabelInputContainer className="mb-8">
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              placeholder="••••••••"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </LabelInputContainer>

          {error && (
            <p className="text-sm text-red-400 mb-4 p-2 bg-red-400/10 rounded">{error}</p>
          )}

          <button
            className="group/btn relative block h-10 w-full rounded-md bg-gradient-to-br from-black to-neutral-600 font-medium text-white shadow-[0px_1px_0px_0px_#ffffff40_inset,0px_-1px_0px_0px_#ffffff40_inset] dark:bg-zinc-800 dark:from-zinc-900 dark:to-zinc-900 dark:shadow-[0px_1px_0px_0px_#27272a_inset,0px_-1px_0px_0px_#27272a_inset] disabled:opacity-60"
            type="submit"
            disabled={loading}
          >
            {loading ? 'Signing in...' : 'Sign in'} &rarr;
            <BottomGradient />
          </button>
        </form>

        <div className="my-6 flex flex-col space-y-3 text-sm text-neutral-600 dark:text-neutral-400">
          <div className="flex justify-between">
            <Link
              href="/auth/signup"
              className="text-neutral-800 hover:text-neutral-600 dark:text-neutral-200 dark:hover:text-neutral-300 underline underline-offset-4"
            >
              Create an account
            </Link>
            <Link
              href="/"
              className="text-neutral-800 hover:text-neutral-600 dark:text-neutral-200 dark:hover:text-neutral-300 underline underline-offset-4"
            >
              Continue as guest
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
