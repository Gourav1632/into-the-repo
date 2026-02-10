'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import axios from 'axios';
import { motion, AnimatePresence } from 'framer-motion';
import { GridBackground } from '@/components/GridBackground';
import Loading from '@/components/Loading';
import LoadingScreen from '@/components/LoadingScreen';
import { useAuth } from '@/contexts/AuthContext';
import { userHistoryRoute, repoAnalysisRoute } from '@/utils/APIRoutes';
import { clearAll, setItem } from '@/utils/indexedDB';
import { Analysis } from '@/types/repo_analysis_type';
import { v4 as uuidv4 } from 'uuid';
import { useRouter } from 'next/navigation';
import { getAuthToken } from '@/utils/auth';

type HistoryItem = {
  id: number;
  repo_url: string;
  branch: string;
  analyzed_at: string | null;
  notes?: string | null;
  repo_analysis_id?: number;
};

export default function HistoryPage() {
  const [loading, setLoading] = useState(true);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [error, setError] = useState<string>('');
  const [requestId, setRequestId] = useState<string>('');
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const router = useRouter();
  const { isLoggedIn } = useAuth();

  useEffect(() => {
    const fetchHistory = async () => {
      const token = getAuthToken();
      if (!token) {
        setLoading(false);
        return;
      }

      try {
        const response = await axios.get(userHistoryRoute, {
          headers: { Authorization: `Bearer ${token}` },
        });
        const items = response.data?.history || [];
        setHistory(items);
      } catch (err) {
        console.error('Failed to load history:', err);
        setError('Could not load history. Please try again.');
      } finally {
        setLoading(false);
      }
    };

    fetchHistory();
  }, []);

  const handleAnalyzeAgain = async (repo_url: string, branch: string) => {
    const token = getAuthToken();
    const id = uuidv4();
    setRequestId(id);
    setIsAnalyzing(true);
    try {
      const headers = token ? { Authorization: `Bearer ${token}` } : undefined;
      const response = await axios.post(
        repoAnalysisRoute,
        { repo_url, branch, request_id: id },
        { headers }
      );

      if (response.data?.error) {
        setError(response.data.error);
        return;
      }

      const analysisData = { repo_url, branch, ...response.data };
      await clearAll();
      await setItem<Analysis>('repoAnalysis', analysisData);
      router.push('/analyze');
    } catch (err) {
      console.error('Failed to analyze repo:', err);
      setError('Failed to start analysis. Please try again.');
    } finally {
      setIsAnalyzing(false);
    }
  };

  if (isAnalyzing) {
    return <LoadingScreen requestId={requestId} />;
  }

  if (loading) return <Loading message="Loading your recent scans..." />;

  return (
    <div className="min-h-screen w-full relative overflow-y-auto">
      <div className="fixed h-screen w-full">
        <GridBackground />
      </div>

      <div className="relative z-10 w-full px-6 py-10 max-w-5xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="mb-8"
        >
          <h1 className="text-3xl font-semibold text-neutral-100">
            Recent scans
          </h1>
          <p className="text-sm text-neutral-400 mt-2">
            {isLoggedIn ? 'Your saved analysis history' : 'Sign in to see your saved analysis history. Guest scans stay on this device.'}
          </p>
        </motion.div>

        {!isLoggedIn ? (
          <div className="rounded-xl border border-neutral-800 bg-neutral-950/80 p-6 text-neutral-200">
            <p className="text-sm text-neutral-300">
              You are currently browsing as a guest. Log in to store and retrieve your scans across devices.
            </p>
            <div className="mt-4 flex gap-3">
              <Link
                className="rounded-full bg-emerald-500 px-4 py-2 text-xs font-semibold text-neutral-900"
                href="/auth/login"
              >
                Sign in
              </Link>
              <Link
                className="rounded-full border border-neutral-700 px-4 py-2 text-xs font-semibold text-neutral-200"
                href="/auth/signup"
              >
                Create account
              </Link>
            </div>
          </div>
        ) : (
          <AnimatePresence mode="wait">
            {error && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="mb-4 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200"
              >
                {error}
              </motion.div>
            )}

            {history.length === 0 ? (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="rounded-xl border border-neutral-800 bg-neutral-950/70 p-6 text-sm text-neutral-300"
              >
                No scans yet. Analyze a repository to build your history.
              </motion.div>
            ) : (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.5 }}
                className="grid gap-4"
              >
                {history.map((item) => (
                  <div
                    key={item.id}
                    className="rounded-xl border border-neutral-800 bg-neutral-950/70 p-5"
                  >
                    <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                      <div>
                        <h2 className="text-base font-semibold text-neutral-100 break-all">
                          {item.repo_url}
                        </h2>
                        <p className="text-xs text-neutral-400">
                          Branch: {item.branch} • {item.analyzed_at ? new Date(item.analyzed_at).toLocaleString() : 'Unknown time'}
                        </p>
                        {item.notes && (
                          <p className="text-xs text-neutral-300 mt-2">{item.notes}</p>
                        )}
                      </div>
                      <div className="flex gap-2">
                        <button
                          onClick={() => handleAnalyzeAgain(item.repo_url, item.branch)}
                          className="rounded-full bg-emerald-500 px-4 py-2 text-xs font-semibold text-neutral-900"
                        >
                          Analyze again
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </motion.div>
            )}
          </AnimatePresence>
        )}
      </div>
    </div>
  );
}
