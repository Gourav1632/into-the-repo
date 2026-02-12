"use client";
import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import axios from "axios";
import { Spotlight } from "@/components/ui/spotlight-new";
import { Cover } from "@/components/ui/cover";
import { progressRoute, host } from "@/utils/APIRoutes";

export default function LoadingScreen({requestId}:{requestId:string}) {
    const [progressMessage, setProgressMessage] = useState("");
    const router = useRouter();

    useEffect(() => {
    const sseUrl = `${progressRoute}?request_id=${requestId}`;
    const eventSource = new EventSource(sseUrl);

    eventSource.onmessage = (event) => {
      const message = event.data;
      setProgressMessage(message);
    };

    eventSource.addEventListener('done', async () => {
      eventSource.close();
      
      // Fetch the completed analysis results
      try {
        const statusUrl = `${host}/api/analyze/status/${requestId}`;
        const statusResponse = await axios.get(statusUrl);
        
        if (statusResponse.data.status === 'completed' && statusResponse.data.result) {
          const result = statusResponse.data.result;
          const repoAnalysisId = result.repo_analysis_id;
          
          if (repoAnalysisId) {
            router.push(`/analyze?id=${repoAnalysisId}`);
          } else {
            console.error('No repo_analysis_id in response. Result:', result);
            setProgressMessage("Analysis completed but could not retrieve ID. Please check history.");
          }
        } else {
          console.error('Analysis failed or incomplete', statusResponse.data);
          setProgressMessage("Analysis failed. Please try again.");
        }
      } catch (error) {
        console.error('Error fetching analysis results:', error);
        setProgressMessage("Error retrieving results. Please try again.");
      }
    });

    eventSource.onerror = () => {
      console.error('SSE connection error');
      eventSource.close();
    };

    return () => {
      eventSource.close();
    };
  }, [requestId, router]);


  const firstSpaceIndex = progressMessage.indexOf(" ");
  const firstWord = firstSpaceIndex === -1 ? progressMessage : progressMessage.slice(0, firstSpaceIndex);
  const restOfMessage = firstSpaceIndex === -1 ? "" : progressMessage.slice(firstSpaceIndex);



return (
  <div className="h-screen flex flex-col justify-center items-center bg-black/96 antialiased bg-grid-white/[0.02] relative overflow-hidden px-4">
    <Spotlight />
    <div className="text-center">
      <h1 className="text-2xl px-4 md:text-3xl lg:text-3xl font-semibold max-w-7xl mx-auto text-center mt-6 relative z-20 py-6 bg-clip-text text-transparent bg-linear-to-b from-neutral-800 via-neutral-700 to-neutral-700 dark:from-neutral-800 dark:via-white dark:to-white transition-opacity duration-500 ease-in-out">
        <Cover>{firstWord}</Cover> 
        <span style={{wordBreak: 'break-word'}}>{restOfMessage}</span>
      </h1>
      {progressMessage.includes('Error') || progressMessage.includes('error') ? (
        <p className="text-red-500 mt-4">Something went wrong. Please try again.</p>
      ) : null}
    </div>
  </div>
);
}